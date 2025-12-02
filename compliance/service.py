import os
import uuid
from typing import List, Optional
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from compliance.models import (
    CompliancePolicySet,
    CompliancePolicyDocument,
    ComplianceRule,
    PolicySetStatus,
    RuleType,
    Severity
)

from compliance.schemas import PolicySetCreate, RuleUpdate
from compliance.utils import save_uploaded_file, extract_text_from_file, clean_and_concatenate_text
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


# -------------------- GET POLICY SET + RULES --------------------

async def get_policy_set_with_rules(db: AsyncSession, policy_set_id: int):
    stmt_set = select(CompliancePolicySet).where(CompliancePolicySet.id == policy_set_id)
    policy_set = (await db.execute(stmt_set)).scalar_one_or_none()

    if not policy_set:
        return ResponseHandler.not_found("Policy set not found")

    stmt_rules = select(ComplianceRule).where(ComplianceRule.policy_set_id == policy_set_id)
    rules = (await db.execute(stmt_rules)).scalars().all()

    return {
        "policy_set": policy_set,
        "rules": rules
    }


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