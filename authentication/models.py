from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
from datetime import timezone as tz


user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE')),
)

role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE')),
    Column('permission_id', Integer, ForeignKey('permissions.id', ondelete='CASCADE')),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    profile_photo = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))

    # Relationships
    roles = relationship('Role', secondary=user_roles, back_populates='users', lazy='selectin')
    tokens = relationship("UserToken", back_populates="user", cascade="all, delete-orphan")

    def get_permissions(self) -> set[str]:
        """Get all permissions from all assigned roles"""
        permissions = set()
        for role in self.roles:
            permissions.update(perm.code for perm in role.permissions)
        return permissions

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        if self.is_superuser:
            return True

        user_permissions = self.get_permissions()

        # Check for wildcard permissions
        if '*' in user_permissions:
            return True

        # Extract resource and action from permission (e.g., "user.assign-role")
        if '.' in permission:
            resource, action = permission.split('.', 1)
            # Check for resource-level wildcard (e.g., "user.*")
            if f"{resource}.*" in user_permissions:
                return True

        # Check for exact permission match
        return permission in user_permissions


class UserToken(Base):
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token = Column(String, unique=True, nullable=False, index=True)
    access_token = Column(String, unique=True, nullable=False, index=True)
    access_token_expiry = Column(DateTime(timezone=True), nullable=False, index=True)  # Add index
    is_revoked = Column(Boolean, default=False, index=True)  # Add index
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="tokens")



class Role(Base):
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship('User', secondary=user_roles, back_populates='roles')
    permissions = relationship('Permission', secondary=role_permissions, back_populates='roles', lazy='selectin')


class Permission(Base):
    __tablename__ = 'permissions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, unique=True, nullable=False, index=True)  # e.g., "user.assign-role"
    name = Column(String, nullable=False)
    description = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    roles = relationship('Role', secondary=role_permissions, back_populates='permissions')