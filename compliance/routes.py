from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from compliance.service import (
    create_draft_policy_set,
    upload_policy_document,
    extract_rules_from_documents,
    get_policy_set_with_rules,
    update_rule,
    finalize_policy_set,
    get_all_policy_sets
)

from compliance.schemas import (
    PolicySetCreate,
    PolicySetOut,
    PolicySetListItem,
    RuleUpdate,
    DocumentOut,
    PolicyExtractionRequest,
    ExtractionResponse,
)

from compliance.models import CompliancePolicyDocument

from common.dependencies import require_permission, get_db
from authentication.models import User
from common.response_handler import ResponseHandler


router = APIRouter(prefix="/compliance", tags=["Compliance"])


# -------------------- LIST ALL POLICY SETS --------------------

@router.get("/policy-sets/list", response_model=List[PolicySetListItem])  # Changed path
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


# -------------------- UPLOAD DOCUMENTS --------------------

@router.post("/policy-sets/{policy_set_id}/documents")
async def upload_documents(
    policy_set_id: int,
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("compliance.documents.upload"))
):
    docs = []
    for file in files:
        doc = await upload_policy_document(db, policy_set_id, file, user.id)
        docs.append(doc)

    return ResponseHandler.created("Documents uploaded", docs)


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
    Extract policy rules from uploaded documents and/or raw text using AI.
    
    Supports:
    - Extracting from previously uploaded documents (if files not provided)
    - Uploading new files during extraction (if files provided)
    - Including raw text (if raw_text provided)
    - Combining all sources: existing documents + new files + raw text
    
    At least one source must be provided (existing documents, new files, or raw_text).
    """
    # Validate that at least one source is provided
    has_files = files and len(files) > 0
    has_raw_text = raw_text and raw_text.strip()
    
    # Check if there are existing documents
    stmt = select(CompliancePolicyDocument).where(
        CompliancePolicyDocument.policy_set_id == policy_set_id
    )
    existing_docs = (await db.execute(stmt)).scalars().all()
    has_existing_docs = len(existing_docs) > 0
    
    if not has_files and not has_raw_text and not has_existing_docs:
        return ResponseHandler.bad_request(
            "At least one source is required: upload files, provide raw_text, or ensure documents are already uploaded"
        )
    
    # Upload new files if provided
    if has_files:
        for file in files:
            try:
                await upload_policy_document(db, policy_set_id, file, user.id)
            except Exception as e:
                return ResponseHandler.bad_request(
                    f"Failed to upload file {file.filename}: {str(e)}"
                )
    
    # Extract rules
    try:
        result = await extract_rules_from_documents(
            db, 
            policy_set_id, 
            user.id,
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
