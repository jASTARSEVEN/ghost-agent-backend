import os
import uuid
from typing import List, Optional
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
import logging as logger

from compliance.models import (
    CompliancePolicySet,
    CompliancePolicyDocument,
    ComplianceRule,
    PolicySetStatus,
    RuleType,
    Severity
)

from compliance.schemas import PolicySetCreate, RuleCreate, RuleUpdate
from compliance.utils import save_uploaded_file, extract_text_from_file, clean_and_concatenate_text, extract_text_from_upload
from compliance.agents.extraction_agent import ExtractionAgent

from common.response_handler import ResponseHandler


UPLOAD_DIR = "uploads/compliance"


# -------------------- CREATE DRAFT POLICY SET --------------------

async def create_draft_policy_set(db: AsyncSession, payload: PolicySetCreate, user_id: int):
    # Determine next version for the user
    stmt = select(CompliancePolicySet).where(
        CompliancePolicySet.created_by == user_id
    ).order_by(CompliancePolicySet.version.desc()).limit(1)  # Add .limit(1) here

    result = await db.execute(stmt)
    last_set = result.scalar_one_or_none()

    new_version = 1 if not last_set else last_set.version + 1

    policy_set = CompliancePolicySet(
        version=new_version,
        status=PolicySetStatus.draft,
        name=payload.name,  # Add this line
        created_by=user_id
    )

    db.add(policy_set)
    await db.commit()
    await db.refresh(policy_set)
    return policy_set


# -------------------- UPLOAD DOCUMENT --------------------

async def upload_policy_document(db: AsyncSession, policy_set_id: int, file: UploadFile, user_id: int):
    os.makedirs(f"{UPLOAD_DIR}/{policy_set_id}", exist_ok=True)

    file_path = await save_uploaded_file(
        file=file,
        destination=f"{UPLOAD_DIR}/{policy_set_id}/{uuid.uuid4()}_{file.filename}"
    )

    doc = CompliancePolicyDocument(
        policy_set_id=policy_set_id,
        file_name=file.filename,
        file_type=file.content_type,
        file_path=file_path,
        uploaded_by=user_id,
    )

    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


# -------------------- EXTRACT RULES FROM DOCUMENTS --------------------

async def extract_rules_from_documents(
    db: AsyncSession, 
    policy_set_id: int, 
    user_id: int,
    raw_text: str | None = None
):
    """
    Extract policy rules from documents and/or raw text using Gemini LLM.
    
    Args:
        db: Database session
        policy_set_id: ID of the policy set
        user_id: ID of the user performing extraction
        raw_text: Optional raw text to include in extraction (in addition to documents)
        
    Returns:
        Dictionary with extraction results: {"rules_extracted": int, "rules_saved": int}
        
    Raises:
        ValueError: If extraction fails or no documents/rules found
    """
    # Fetch documents
    stmt = select(CompliancePolicyDocument).where(
        CompliancePolicyDocument.policy_set_id == policy_set_id
    )
    docs = (await db.execute(stmt)).scalars().all()

    # Extract raw text from documents
    extracted_texts = []
    for doc in docs:
        try:
            text = await extract_text_from_file(doc.file_path)
            extracted_texts.append(text)
        except Exception as e:
            # Log error but continue with other documents
            # In production, you might want to log this properly
            print(f"Warning: Failed to extract text from {doc.file_name}: {str(e)}")
            continue
    
    # Add raw text if provided
    if raw_text and raw_text.strip():
        extracted_texts.append(raw_text.strip())
    
    # Validate that we have at least one text source
    if not extracted_texts:
        if not docs and not raw_text:
            raise ValueError("No documents found for extraction and no raw text provided")
        elif not docs:
            raise ValueError("No documents found and raw text is empty")
        else:
            raise ValueError("Failed to extract text from any documents")
    
    # Clean and concatenate all extracted text
    all_text = clean_and_concatenate_text(extracted_texts)
    
    if not all_text or not all_text.strip():
        raise ValueError("No extractable text found in documents or raw text")

    # Extract rules using Gemini LLM
    try:
        extraction_agent = ExtractionAgent()
        extracted_rules = await extraction_agent.extract_rules(all_text)
    except Exception as e:
        error_msg = f"Failed to extract rules from documents: {str(e)}"
        print(f"Extraction error: {error_msg}")
        raise ValueError(error_msg)

    if not extracted_rules:
        raise ValueError("No rules could be extracted from the documents")

    # Save rules to database
    saved_count = 0
    for rule in extracted_rules:
        try:
            new_rule = ComplianceRule(
                policy_set_id=policy_set_id,
                category=rule["category"],
                rule_type=RuleType(rule["rule_type"]),
                title=rule["title"],
                description=rule["description"],
                severity=Severity(rule["severity"]),
                ai_generated=True,
                example_snippets=rule.get("example_snippets", []),
                created_by=user_id,
            )
            db.add(new_rule)
            saved_count += 1
        except Exception as e:
            # Log error but continue with other rules
            print(f"Warning: Failed to save rule '{rule.get('title', 'unknown')}': {str(e)}")
            continue

    if saved_count == 0:
        raise ValueError("Failed to save any rules to database")

    await db.commit()
    return {"rules_extracted": len(extracted_rules), "rules_saved": saved_count}


# -------------------- EXTRACT RULES FROM UPLOADS (IN-MEMORY) --------------------

async def extract_rules_from_uploads(
    db: AsyncSession, 
    policy_set_id: int, 
    user_id: int,
    files: List[UploadFile] | None = None,
    raw_text: str | None = None
):
    """
    Extract policy rules from uploaded files (in-memory) and/or raw text using Azure OpenAI LLM.
    Does NOT save files to disk or create document records.
    
    Args:
        db: Database session
        policy_set_id: ID of the policy set
        user_id: ID of the user performing extraction
        files: Optional list of uploaded files to process in-memory
        raw_text: Optional raw text to include in extraction
        
    Returns:
        Dictionary with extraction results: {"rules_extracted": int, "rules_saved": int}
        
    Raises:
        ValueError: If extraction fails or no files/text found
    """
    extracted_texts = []
    
    # Extract text from uploaded files (in-memory)
    if files:
        for file in files:
            try:
                text = await extract_text_from_upload(file)
                extracted_texts.append(text)
            except Exception as e:
                # Log error but continue with other files
                print(f"Warning: Failed to extract text from {file.filename}: {str(e)}")
                continue
    
    # Add raw text if provided
    if raw_text and raw_text.strip():
        extracted_texts.append(raw_text.strip())
    
    # Validate that we have at least one text source
    if not extracted_texts:
        raise ValueError("No extractable text found in files or raw text")
    
    # Clean and concatenate all extracted text
    all_text = clean_and_concatenate_text(extracted_texts)
    
    if not all_text or not all_text.strip():
        raise ValueError("No extractable text found after cleaning")

    # Extract rules using Azure OpenAI LLM
    try:
        extraction_agent = ExtractionAgent()
        extracted_rules = await extraction_agent.extract_rules(all_text)
    except Exception as e:
        error_msg = f"Failed to extract rules: {str(e)}"
        print(f"Extraction error: {error_msg}")
        raise ValueError(error_msg)

    if not extracted_rules:
        raise ValueError("No rules could be extracted from the provided content")

    # Save rules to database
    saved_count = 0
    for rule in extracted_rules:
        try:
            new_rule = ComplianceRule(
                policy_set_id=policy_set_id,
                category=rule["category"],
                rule_type=RuleType(rule["rule_type"]),
                title=rule["title"],
                description=rule["description"],
                severity=Severity(rule["severity"]),
                ai_generated=True,
                example_snippets=rule.get("example_snippets", []),
                created_by=user_id,
            )
            db.add(new_rule)
            saved_count += 1
        except Exception as e:
            # Log error but continue with other rules
            print(f"Warning: Failed to save rule '{rule.get('title', 'unknown')}': {str(e)}")
            continue

    if saved_count == 0:
        raise ValueError("Failed to save any rules to database")

    await db.commit()
    return {"rules_extracted": len(extracted_rules), "rules_saved": saved_count}


# -------------------- GET POLICY SET + RULES --------------------

async def get_policy_set_with_rules(db: AsyncSession, policy_set_id: int):
    stmt_set = select(CompliancePolicySet).where(CompliancePolicySet.id == policy_set_id)
    policy_set = (await db.execute(stmt_set)).scalar_one_or_none()

    if not policy_set:
        raise ValueError(f"Policy set not found: {policy_set_id}")

    stmt_rules = select(ComplianceRule).where(ComplianceRule.policy_set_id == policy_set_id)
    rules = (await db.execute(stmt_rules)).scalars().all()

    return {
        "policy_set": policy_set,
        "rules": rules
    }


# -------------------- CREATE RULE --------------------

async def create_rule(db: AsyncSession, policy_set_id: int, payload: RuleCreate, user_id: int):
    """
    Manually create a compliance rule for a policy set.
    
    Args:
        db: Database session
        policy_set_id: ID of the policy set to add the rule to
        payload: Rule creation data
        user_id: ID of the user creating the rule
        
    Returns:
        The created rule object
        
    Raises:
        ValueError: If policy set not found or is not in draft status
    """
    # Check if policy set exists and is in draft status
    stmt = select(CompliancePolicySet).where(CompliancePolicySet.id == policy_set_id)
    policy_set = (await db.execute(stmt)).scalar_one_or_none()
    
    if not policy_set:
        raise ValueError("Policy set not found")
    #also allow to create rules in archived policy sets
    if policy_set.status != PolicySetStatus.draft and policy_set.status != PolicySetStatus.archived:
        raise ValueError("Rules can only be added to draft policy sets")
    
    # Create the new rule
    new_rule = ComplianceRule(
        policy_set_id=policy_set_id,
        category=payload.category,
        rule_type=payload.rule_type,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        enabled=payload.enabled,
        ai_generated=False,  # Manually created, not AI-generated
        example_snippets=payload.example_snippets,
        created_by=user_id,
    )
    
    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)
    
    return new_rule


# -------------------- UPDATE RULE --------------------

async def update_rule(db: AsyncSession, rule_id: int, payload: RuleUpdate, user_id: int):
    stmt = select(ComplianceRule).where(ComplianceRule.id == rule_id)
    rule = (await db.execute(stmt)).scalar_one_or_none()

    if not rule:
        return ResponseHandler.not_found("Rule not found")

    data = payload.dict(exclude_unset=True)
    for k, v in data.items():
        setattr(rule, k, v)

    await db.commit()
    await db.refresh(rule)
    return rule


# -------------------- FINALIZE POLICY SET --------------------

async def finalize_policy_set(db: AsyncSession, policy_set_id: int, user_id: int):

    # Get the new policy set
    stmt = select(CompliancePolicySet).where(CompliancePolicySet.id == policy_set_id)
    policy_set = (await db.execute(stmt)).scalar_one_or_none()

    if not policy_set:
        return ResponseHandler.not_found("Policy set not found")

    # Archive previous active ones for the same user (instead of tenant)
    stmt2 = select(CompliancePolicySet).where(
        CompliancePolicySet.created_by == policy_set.created_by,  # Changed from tenant_id
        CompliancePolicySet.status == PolicySetStatus.active
    )
    active_sets = (await db.execute(stmt2)).scalars().all()

    for active in active_sets:
        active.status = PolicySetStatus.archived

    # Activate this one
    policy_set.status = PolicySetStatus.active
    await db.commit()
    await db.refresh(policy_set)

    return policy_set

# -------------------- ARCHIVE POLICY SET --------------------
async def archive_policy_set(db: AsyncSession, policy_set_id: int, user_id: int):

    # Get the policy set
    stmt = select(CompliancePolicySet).where(CompliancePolicySet.id == policy_set_id)
    policy_set = (await db.execute(stmt)).scalar_one_or_none()

    if not policy_set:
        return ResponseHandler.not_found("Policy set not found")

    # Archive it
    policy_set.status = PolicySetStatus.archived
    await db.commit()
    await db.refresh(policy_set)

    return policy_set


# -------------------- GET ALL POLICY SETS --------------------

async def get_all_policy_sets(db: AsyncSession, user_id: int):
    """
    Get all policy sets for a user.
    
    Args:
        db: Database session
        user_id: ID of the user
        
    Returns:
        List of policy sets ordered by creation date (newest first)
    """
    stmt = select(CompliancePolicySet).where(
        CompliancePolicySet.created_by == user_id
    ).order_by(CompliancePolicySet.created_at.desc())
    
    result = await db.execute(stmt)
    policy_sets = result.scalars().all()
    
    return policy_sets


# -------------------- CONVERSATION EVALUATION --------------------

async def get_active_policy_set(db: AsyncSession, user_id: int):
    """
    Get the active policy set for a user.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Active policy set or None if no active set found
    """
    stmt = select(CompliancePolicySet).where(
        CompliancePolicySet.created_by == user_id,
        CompliancePolicySet.status == PolicySetStatus.active
    ).order_by(CompliancePolicySet.created_at.desc())
    
    result = await db.execute(stmt)
    policy_set = result.scalar_one_or_none()
    
    return policy_set


async def evaluate_conversation_compliance(
    db: AsyncSession,
    conversation_id: str,
    policy_set_id: int,
    user_id: int,
    force_reevaluate: bool = False
):
    """
    Evaluate a conversation for compliance against policy rules.
    
    Main orchestration function that:
    1. Checks for cached evaluation (unless force_reevaluate)
    2. Validates conversation exists and is complete
    3. Fetches policy rules
    4. Processes conversation events
    5. Calls evaluation agent
    6. Stores results
    7. Returns evaluation
    
    Args:
        db: Database session
        conversation_id: ID of conversation to evaluate
        policy_set_id: Policy set to evaluate against
        user_id: User triggering evaluation
        force_reevaluate: If True, bypass cache and re-evaluate
        
    Returns:
        Evaluation result dictionary
        
    Raises:
        ValueError: If conversation invalid or evaluation fails
    """
    from compliance.conversation_processor import (
        process_conversation_events,
        validate_conversation_for_evaluation
    )
    from compliance.agents.evaluation_agent import EvaluationAgent
    from compliance.models import ConversationComplianceEvaluation
    
    # 0. Check for cached evaluation (permanent cache)
    if not force_reevaluate:
        cached_stmt = select(ConversationComplianceEvaluation).where(
            ConversationComplianceEvaluation.conversation_id == conversation_id,
            ConversationComplianceEvaluation.policy_set_id == policy_set_id
        ).order_by(ConversationComplianceEvaluation.evaluated_at.desc())
        
        cached_result = await db.execute(cached_stmt)
        cached_evaluation = cached_result.scalars().first()  # Get first (most recent) result
        
        if cached_evaluation:
            # Return cached evaluation
            policy_data = await get_policy_set_with_rules(db, policy_set_id)
            policy_set = policy_data.get("policy_set")
            
            logger.info(f"Returning cached evaluation for conversation {conversation_id}")
            
            return {
                "conversation_id": cached_evaluation.conversation_id,
                "policy_set_id": cached_evaluation.policy_set_id,
                "policy_set_name": policy_set.name if policy_set else None,
                "overall_score": cached_evaluation.overall_score,
                "compliance_status": cached_evaluation.compliance_status,
                "conversation_metadata": {},  # Not stored in cache
                "compliance_findings": cached_evaluation.compliance_findings,
                "violations_summary": cached_evaluation.violations_summary,
                "applicable_rules_summary": cached_evaluation.applicable_rules_summary,
                "summary": cached_evaluation.summary,
                "llm_metadata": cached_evaluation.llm_metadata,
                "evaluated_by_user_id": cached_evaluation.evaluated_by_user_id,
                "evaluated_at": cached_evaluation.evaluated_at.isoformat(),
                "evaluation_id": cached_evaluation.id,
                "from_cache": True
            }
    
    # 1. Get policy set with rules
    policy_data = await get_policy_set_with_rules(db, policy_set_id)
    
    if "error" in policy_data:
        raise ValueError(f"Policy set not found: {policy_set_id}")
    
    policy_set = policy_data["policy_set"]
    rules = policy_data["rules"]
    
    if not rules:
        raise ValueError(f"Policy set {policy_set_id} has no rules to evaluate against")
    
    # Filter to only enabled rules
    enabled_rules = [r for r in rules if r.enabled]
    
    if not enabled_rules:
        raise ValueError(f"Policy set {policy_set_id} has no enabled rules")
    
    # 2. Process conversation events
    conversation_data = await process_conversation_events(conversation_id, db)
    
    # 3. Validate conversation is ready for evaluation
    await validate_conversation_for_evaluation(conversation_data)
    
    # 4. Format rules for evaluation
    formatted_rules = [
        {
            "id": rule.id,
            "category": rule.category,
            "rule_type": rule.rule_type.value,
            "title": rule.title,
            "description": rule.description,
            "severity": rule.severity.value
        }
        for rule in enabled_rules
    ]
    
    # 5. Call evaluation agent
    evaluation_agent = EvaluationAgent()
    
    evaluation_result = await evaluation_agent.evaluate_conversation(
        conversation_data=conversation_data.to_dict(),
        policy_rules=formatted_rules
    )
    
    # 6. Store evaluation results
    evaluation_record = ConversationComplianceEvaluation(
        conversation_id=conversation_id,
        policy_set_id=policy_set_id,
        overall_score=evaluation_result["overall_score"],
        compliance_status=evaluation_result["compliance_status"],
        summary=evaluation_result["summary"],
        compliance_findings=evaluation_result["compliance_findings"],
        violations_summary=evaluation_result["violations_summary"],
        applicable_rules_summary=evaluation_result["applicable_rules_summary"],
        llm_metadata=evaluation_result["llm_metadata"],
        evaluated_by_user_id=user_id
    )
    
    db.add(evaluation_record)
    await db.commit()
    await db.refresh(evaluation_record)
    
    # 7. Build response
    response = {
        "conversation_id": conversation_id,
        "policy_set_id": policy_set_id,
        "policy_set_name": policy_set.name,
        "overall_score": evaluation_result["overall_score"],
        "compliance_status": evaluation_result["compliance_status"],
        "conversation_metadata": conversation_data.to_dict()["metadata"],
        "compliance_findings": evaluation_result["compliance_findings"],
        "violations_summary": evaluation_result["violations_summary"],
        "applicable_rules_summary": evaluation_result["applicable_rules_summary"],
        "summary": evaluation_result["summary"],
        "llm_metadata": evaluation_result["llm_metadata"],
        "evaluated_by_user_id": user_id,
        "evaluated_at": evaluation_record.evaluated_at.isoformat(),
        "evaluation_id": evaluation_record.id,
        "from_cache": False
    }
    
    return response


async def get_conversation_evaluation(
    db: AsyncSession,
    conversation_id: str
):
    """
    Get the latest evaluation for a conversation.
    
    Args:
        db: Database session
        conversation_id: Conversation ID
        
    Returns:
        Latest evaluation or None if not found
    """
    from compliance.models import ConversationComplianceEvaluation
    
    stmt = select(ConversationComplianceEvaluation).where(
        ConversationComplianceEvaluation.conversation_id == conversation_id
    ).order_by(ConversationComplianceEvaluation.evaluated_at.desc())
    
    result = await db.execute(stmt)
    evaluation = result.scalars().first()
    
    if not evaluation:
        return None
    
    # Get policy set name
    policy_data = await get_policy_set_with_rules(db, evaluation.policy_set_id)
    policy_set = policy_data.get("policy_set")
    
    return {
        "conversation_id": evaluation.conversation_id,
        "policy_set_id": evaluation.policy_set_id,
        "policy_set_name": policy_set.name if policy_set else None,
        "overall_score": evaluation.overall_score,
        "compliance_status": evaluation.compliance_status,
        "compliance_findings": evaluation.compliance_findings,
        "violations_summary": evaluation.violations_summary,
        "applicable_rules_summary": evaluation.applicable_rules_summary,
        "summary": evaluation.summary,
        "llm_metadata": evaluation.llm_metadata,
        "evaluated_by_user_id": evaluation.evaluated_by_user_id,
        "evaluated_at": evaluation.evaluated_at.isoformat(),
        "evaluation_id": evaluation.id
    }