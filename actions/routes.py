# actions/routes.py
from fastapi import APIRouter, Depends
from actions.schemas import RefundRequest
from actions.service import process_refund_request, deny_refund_request
from common.dependencies import require_authenticated_user
from authentication.models import User

router = APIRouter(prefix="/actions", tags=["Refund Actions"])

@router.post("/refund/process")
async def trigger_refund_action(data: RefundRequest, current_user: User = Depends(require_authenticated_user)):
    result = await process_refund_request(data, current_user.id)
    return result

@router.post("/refund/deny")
async def trigger_refund_denial(data: RefundRequest, current_user: User = Depends(require_authenticated_user)):
    result = await deny_refund_request(data, current_user.id)
    return result
