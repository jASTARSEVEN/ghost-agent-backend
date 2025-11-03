from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from authentication.models import User
from common.dependencies import get_db
from common.response_handler import ResponseHandler
from common.dependencies import require_permission
from authentication.models import Permission
from authentication.schemas import RoleCreate, RoleOut, RoleUpdate
from authentication.models import Role
from sqlalchemy.orm import selectinload

role_router = APIRouter(prefix="/roles", tags=["Roles"])


@role_router.get("/")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role.list"))
):
    """List all roles - requires 'role.list' permission"""
    stmt = select(Role).options(selectinload(Role.permissions))
    result = await db.execute(stmt)
    roles = result.scalars().all()

    return ResponseHandler.ok(
        message=f"Retrieved {len(roles)} roles",
        data=roles
    )


@role_router.post("/", response_model=RoleOut)
async def create_role(
    role_data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role.create"))
):
    """Create a new role - requires 'role.create' permission"""
    # Check if role already exists
    stmt = select(Role).where(Role.name == role_data.name)
    result = await db.execute(stmt)
    existing_role = result.scalar_one_or_none()

    if existing_role:
        return ResponseHandler.bad_request(
            message="Role with this name already exists"
        )

    # Get permissions
    permissions = []
    if role_data.permission_ids:
        stmt = select(Permission).where(Permission.id.in_(role_data.permission_ids))
        result = await db.execute(stmt)
        permissions = result.scalars().all()

        if len(permissions) != len(role_data.permission_ids):
            return ResponseHandler.bad_request(
                message="One or more permissions not found"
            )

    # Create role
    db_role = Role(
        name=role_data.name,
        description=role_data.description,
        permissions=permissions
    )
    db.add(db_role)
    await db.commit()
    await db.refresh(db_role)

    return ResponseHandler.created(
        message="Role created successfully",
        data=db_role
    )


@role_router.get("/{role_id}", response_model=RoleOut)
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role.retrieve"))
):
    """Get role by ID - requires 'role.retrieve' permission"""
    stmt = select(Role).options(
        selectinload(Role.permissions)
    ).where(Role.id == role_id)
    result = await db.execute(stmt)
    role = result.scalar_one_or_none()

    if not role:
        return ResponseHandler.not_found(message="Role not found")

    return ResponseHandler.ok(
        message="Role retrieved successfully",
        data=role
    )


@role_router.put("/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role.update"))
):
    """Update role - requires 'role.update' permission"""
    stmt = select(Role).options(
        selectinload(Role.permissions)
    ).where(Role.id == role_id)
    result = await db.execute(stmt)
    role = result.scalar_one_or_none()

    if not role:
        return ResponseHandler.not_found(message="Role not found")

    # Update basic fields
    if role_data.name is not None:
        # Check if name already exists
        stmt = select(Role).where(Role.name == role_data.name, Role.id != role_id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            return ResponseHandler.bad_request(
                message="Role with this name already exists"
            )
        role.name = role_data.name

    if role_data.description is not None:
        role.description = role_data.description

    # Update permissions if provided
    if role_data.permission_ids is not None:
        stmt = select(Permission).where(Permission.id.in_(role_data.permission_ids))
        result = await db.execute(stmt)
        permissions = result.scalars().all()

        if len(permissions) != len(role_data.permission_ids):
            return ResponseHandler.bad_request(
                message="One or more permissions not found"
            )
        role.permissions = permissions

    await db.commit()
    await db.refresh(role)

    return ResponseHandler.ok(
        message="Role updated successfully",
        data=role
    )


@role_router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role.delete"))
):
    """Delete role - requires 'role.delete' permission"""
    stmt = select(Role).where(Role.id == role_id)
    result = await db.execute(stmt)
    role = result.scalar_one_or_none()

    if not role:
        return ResponseHandler.not_found(message="Role not found")

    await db.delete(role)
    await db.commit()

    return ResponseHandler.ok(message="Role deleted successfully")
