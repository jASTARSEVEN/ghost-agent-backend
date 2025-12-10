from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from compliance.service import (
    create_draft_policy_set,
    extract_rules_from_uploads,
    get_policy_set_with_rules,
    create_rule,
    update_rule,
    finalize_policy_set,
    get_all_policy_sets,
    get_active_policy_set,
    evaluate_conversation_compliance,
    get_conversation_evaluation
)

from compliance.schemas import (
    PolicySetCreate,
    PolicySetOut,
    PolicySetListItem,
    RuleCreate,
    RuleUpdate,
    RuleOut,
    DocumentOut,
    PolicyExtractionRequest,
    ExtractionResponse,
    ConversationEvaluationRequest,
    ConversationEvaluationResponse
)

from common.dependencies import require_permission, get_db
from authentication.models import User
from common.response_handler import ResponseHandler


router = APIRouter(prefix="/compliance", tags=["Compliance"])


# -------------------- LIST ALL POLICY SETS --------------------

@router.get("/policy-sets/lists", response_model=List[PolicySetListItem])
async def list_policy_sets(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("compliance.policy-set.view"))
):
    """
    Get all policy sets for the current user.
    Returns a list with id, name, version, status, and created_at.
    """
    policy_sets = await get_all_policy_sets(db, user.id)
    return ResponseHandler.ok("Policy sets fetched", policy_sets)


# -------------------- CREATE DRAFT POLICY SET --------------------

@router.post("/policy-sets", response_model=PolicySetOut)
async def create_policy_set(
    payload: PolicySetCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("compliance.policy-set.create"))
):
    policy_set = await create_draft_policy_set(db, payload, user.id)
    return ResponseHandler.created("Draft policy set created", policy_set)


# -------------------- EXTRACT RULES FROM DOCUMENTS --------------------

@router.post(
    "/policy-sets/{policy_set_id}/extract",
    response_model=ExtractionResponse
)
async def extract_rules(
    policy_set_id: int,
    files: Optional[List[UploadFile]] = File(default=[]),
    raw_text: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("compliance.extract.run"))
):
    """
    Extract policy rules from uploaded files and/or raw text using AI.
    At least one source must be provided (files or raw_text).
    """
    # Validate that at least one source is provided
    has_files = files and len(files) > 0
    has_raw_text = raw_text and raw_text.strip()
    
    if not has_files and not has_raw_text:
        return ResponseHandler.bad_request(
            "At least one source is required: upload files or provide raw_text"
        )
    
    # Extract rules directly from in-memory files
    try:
        result = await extract_rules_from_uploads(
            db, 
            policy_set_id, 
            user.id,
            files=files if has_files else None,
            raw_text=raw_text
        )
        return ResponseHandler.ok(
            f"Successfully extracted and saved {result['rules_saved']} rules",
            result
        )
    except ValueError as e:
        return ResponseHandler.bad_request(str(e))
    except Exception as e:
        return ResponseHandler.bad_request(f"Extraction failed: {str(e)}")


# -------------------- GET POLICY SET + RULES --------------------

@router.get("/policy-sets/{policy_set_id}")
async def get_policy_set(
    policy_set_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("compliance.policy-set.view"))
):
    data = await get_policy_set_with_rules(db, policy_set_id)
    return ResponseHandler.ok("Policy set fetched", data)


# -------------------- CREATE RULE --------------------

@router.post("/policy-sets/{policy_set_id}/rules", response_model=RuleOut)
async def add_rule(
    policy_set_id: int,
    payload: RuleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("compliance.rules.create"))
):
    """
    Manually create a compliance rule for a policy set.
    
    The policy set must be in draft status to add rules.
    Rules created through this endpoint are marked as manually created (not AI-generated).
    """
    try:
        rule = await create_rule(db, policy_set_id, payload, user.id)
        return ResponseHandler.created("Rule created successfully", rule)
    except ValueError as e:
        return ResponseHandler.bad_request(str(e))
    except Exception as e:
        return ResponseHandler.bad_request(f"Failed to create rule: {str(e)}")


# -------------------- UPDATE RULE --------------------

@router.put("/rules/{rule_id}")
async def edit_rule(
    rule_id: int,
    payload: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("compliance.rules.update"))
):
    updated = await update_rule(db, rule_id, payload, user.id)
    return ResponseHandler.ok("Rule updated", updated)


# -------------------- FINALIZE POLICY SET --------------------

@router.post("/policy-sets/{policy_set_id}/finalize")
async def finalize_policy(
    policy_set_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("compliance.policy-set.finalize"))
):
    result = await finalize_policy_set(db, policy_set_id, user.id)
    return ResponseHandler.ok("Policy set finalized", result)


# -------------------- CONVERSATION EVALUATION --------------------

@router.post("/conversations/{conversation_id}/evaluate", response_model=ConversationEvaluationResponse)
async def evaluate_conversation(
    conversation_id: str,
    request: ConversationEvaluationRequest = ConversationEvaluationRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("compliance.conversation.evaluate"))
):
    """
    Evaluate a conversation for compliance against policy rules.
    
    Args:
        conversation_id: ID of the conversation to evaluate
        request: Evaluation request with optional policy_set_id
        
    Returns:
        Detailed compliance evaluation with findings, score, and violations summary
    """
    try:
        # Determine which policy set to use
        policy_set_id = request.policy_set_id
        
        if not policy_set_id:
            # Use active policy set if not specified
            active_policy = await get_active_policy_set(db, user.id)
            
            if not active_policy:
                return ResponseHandler.bad_request(
                    "No active policy set found. Please activate a policy set or provide policy_set_id in request."
                )
            
            policy_set_id = active_policy.id
        
        # Perform evaluation (with caching support)
        evaluation_result = await evaluate_conversation_compliance(
            db=db,
            conversation_id=conversation_id,
            policy_set_id=policy_set_id,
            user_id=user.id,
            force_reevaluate=request.force_reevaluate or False
        )
        
        return ResponseHandler.ok(
            "Compliance evaluation completed successfully",
            evaluation_result
        )
        
    except ValueError as e:
        return ResponseHandler.bad_request(str(e))
    except Exception as e:
        return ResponseHandler.server_error(f"Evaluation failed: {str(e)}")


@router.get("/conversations/{conversation_id}/evaluation")
async def get_latest_evaluation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("compliance.conversation.view"))
):
    """
    Get the compliance evaluation for a conversation.
    
    Args:
        conversation_id: ID of the conversation
        
    Returns:
        Latest evaluation result or 404 if not found
    """
    try:
        evaluation = await get_conversation_evaluation(db, conversation_id)
        
        if not evaluation:
            return ResponseHandler.not_found(
                f"No evaluation found for conversation {conversation_id}"
            )
        
        return ResponseHandler.ok("Evaluation retrieved", evaluation)
        
    except Exception as e:
        return ResponseHandler.server_error(f"Failed to retrieve evaluation: {str(e)}")
