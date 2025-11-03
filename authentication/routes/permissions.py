from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from authentication.models import User
from common.dependencies import get_db
from common.response_handler import ResponseHandler
from common.dependencies import require_permission
from authentication.models import Permission
from authentication.schemas import PermissionCreate, PermissionOut

permission_router = APIRouter(prefix="/permissions", tags=["Permissions"])


@permission_router.get("/")
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("permission.list"))
):
    """List all permissions - requires 'permission.list' permission"""
    stmt = select(Permission)
    result = await db.execute(stmt)
    permissions = result.scalars().all()

    return ResponseHandler.ok(
        message=f"Retrieved {len(permissions)} permissions",
        data=permissions
    )


@permission_router.post("/", response_model=PermissionOut)
async def create_permission(
    permission_data: PermissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("permission.create"))
):
    """Create a new permission - requires 'permission.create' permission"""
    # Check if permission already exists
    stmt = select(Permission).where(Permission.code == permission_data.code)
    result = await db.execute(stmt)
    existing_permission = result.scalar_one_or_none()

    if existing_permission:
        return ResponseHandler.bad_request(
            message="Permission with this code already exists"
        )

    # Create permission
    db_permission = Permission(
        code=permission_data.code,
        name=permission_data.name,
        description=permission_data.description,
    )
    db.add(db_permission)
    await db.commit()
    await db.refresh(db_permission)

    return ResponseHandler.created(
        message="Permission created successfully",
        data=db_permission
    )


@permission_router.delete("/{permission_id}")
async def delete_permission(
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("permission.delete"))
):
    """Delete permission - requires 'permission.delete' permission"""
    stmt = select(Permission).where(Permission.id == permission_id)
    result = await db.execute(stmt)
    permission = result.scalar_one_or_none()

    if not permission:
        return ResponseHandler.not_found(message="Permission not found")

    await db.delete(permission)
    await db.commit()

    return ResponseHandler.ok(message="Permission deleted successfully")