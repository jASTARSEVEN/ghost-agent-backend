from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from authentication.models import User
from common.dependencies import get_db
from common.response_handler import ResponseHandler
from common.dependencies import require_permission
from authentication.schemas import UserCreate, UserOut, UserUpdate, AssignRolesRequest, BulkUpdateStatusRequest, BulkDeleteRequest
from authentication.models import Role
from sqlalchemy.orm import selectinload
from authentication.utils import hash_password

user_router = APIRouter(prefix="/users", tags=["Users"])


@user_router.get("/")
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.list"))
):
    """List all users - requires 'user.list' permission"""
    stmt = select(User).options(
        selectinload(User.roles).selectinload(Role.permissions)
    ).order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()

    return ResponseHandler.ok(
        message=f"Retrieved {len(users)} users",
        data=users
    )



@user_router.post("/", response_model=UserOut)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.create"))
):
    """Create a new user with optional role assignment - requires 'user.create' permission"""
    # Check if user already exists
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        return ResponseHandler.bad_request(
            message="User with this email already exists"
        )

    # Validate and fetch roles if role_ids provided
    roles = []
    if user_data.role_ids:
        stmt = select(Role).where(Role.id.in_(user_data.role_ids))
        result = await db.execute(stmt)
        roles = result.scalars().all()

        if len(roles) != len(user_data.role_ids):
            return ResponseHandler.bad_request(
                message="One or more role IDs are invalid"
            )

    # Create new user
    db_user = User(
        email=user_data.email,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        password=hash_password(user_data.password),
        roles=roles  # Assign roles during creation
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return ResponseHandler.created(
        message="User created successfully" + (f" with {len(roles)} role(s)" if roles else ""),
        data=db_user
    )


@user_router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.retrieve"))
):
    """Get user by ID - requires 'user.retrieve' permission"""
    stmt = select(User).options(
        selectinload(User.roles).selectinload(Role.permissions)
    ).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return ResponseHandler.not_found(message="User not found")

    return ResponseHandler.ok(
        message="User retrieved successfully",
        data=user
    )


@user_router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.update"))
):
    """Update user - requires 'user.update' permission"""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return ResponseHandler.not_found(message="User not found")

    update_data = user_data.model_dump(exclude_unset=True, exclude={"role_ids"})
    for field, value in update_data.items():
        setattr(user, field, value)

    if user_data.role_ids:  # correct check
        stmt = select(Role).where(Role.id.in_(user_data.role_ids))
        result = await db.execute(stmt)
        roles = result.scalars().all()

        user.roles = roles 

    await db.commit()
    await db.refresh(user)

    return ResponseHandler.ok(
        message="User updated successfully",
        data=user
    )


@user_router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.delete"))
):
    """Delete user - requires 'user.delete' permission"""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return ResponseHandler.not_found(message="User not found")

    from sqlalchemy import delete
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()

    return ResponseHandler.ok(message="User deleted successfully")


@user_router.post("/{user_id}/assign-roles", response_model=UserOut)
async def assign_roles(
    user_id: int,
    roles_data: AssignRolesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.assign-role"))
):
    """Assign roles to user - requires 'user.assign-role' permission"""
    # Get user
    stmt = select(User).options(
        selectinload(User.roles)
    ).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return ResponseHandler.not_found(message="User not found")

    # Get roles
    stmt = select(Role).where(Role.id.in_(roles_data.role_ids))
    result = await db.execute(stmt)
    roles = result.scalars().all()

    if len(roles) != len(roles_data.role_ids):
        return ResponseHandler.bad_request(message="One or more roles not found")

    # Assign roles
    user.roles = roles
    await db.commit()
    await db.refresh(user)

    return ResponseHandler.ok(
        message="Roles assigned successfully",
        data=user
    )


@user_router.get("/{user_id}/permissions")
async def get_user_permissions(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.view-permissions"))
):
    """Get all permissions for a user - requires 'user.view-permissions' permission"""
    stmt = select(User).options(
        selectinload(User.roles).selectinload(Role.permissions)
    ).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return ResponseHandler.not_found(message="User not found")

    permissions = list(user.get_permissions())
    return ResponseHandler.ok(
        message=f"User has {len(permissions)} permissions",
        data=permissions
    )


@user_router.post("/bulk-update")
async def bulk_update_user_status(
    payload: BulkUpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.delete"))
):
    """
    Bulk update 'is_active' status for multiple users.
    Requires 'user.bulk-update' permission.
    """

    stmt = select(User).where(User.id.in_(payload.ids))
    result = await db.execute(stmt)
    users = result.scalars().all()

    if not users:
        return ResponseHandler.not_found(message="No users found for given IDs")

    # Check for missing IDs
    found_ids = {u.id for u in users}
    missing_ids = set(payload.ids) - found_ids
    if missing_ids:
        return ResponseHandler.bad_request(
            message=f"Some user IDs not found: {list(missing_ids)}"
        )

    # Use bulk update for better performance
    from sqlalchemy import update
    stmt = update(User).where(
        User.id.in_(payload.ids)
    ).values(is_active=payload.is_active)
    
    result = await db.execute(stmt)
    await db.commit()

    return ResponseHandler.ok(
        message=f"Updated is_active={payload.is_active} for {len(users)} user(s)",
        data=[{"id": u.id, "is_active": u.is_active} for u in users]
    )

@user_router.post("/bulk-delete")
async def bulk_delete_users(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.delete"))
):
    """
    Bulk delete multiple users.
    Requires 'user.bulk-delete' permission.
    """

    stmt = select(User).where(User.id.in_(payload.ids))
    result = await db.execute(stmt)
    users = result.scalars().all()

    if not users:
        return ResponseHandler.not_found(message="No users found for given IDs")

    # Check for missing IDs
    found_ids = {u.id for u in users}
    missing_ids = set(payload.ids) - found_ids
    if missing_ids:
        return ResponseHandler.bad_request(
            message=f"Some user IDs not found: {list(missing_ids)}"
        )

    # Delete users
    for user in users:
        await db.delete(user)
    await db.commit()

    return ResponseHandler.ok(
        message=f"Deleted {len(users)} user(s)"
    )    