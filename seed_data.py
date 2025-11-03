from sqlalchemy.future import select
from authentication.models import User, Role, Permission
from database import AsyncSessionLocal
from authentication.utils import hash_password

async def seed_initial_data():
    async with AsyncSessionLocal() as db:
        try:
            # Create permissions
            permissions_data = [
                # User permissions
                ("user.list", "List Users", "View list of users"),
                ("user.create", "Create User", "Create new users"),
                ("user.retrieve", "Retrieve User", "View user details"),
                ("user.update", "Update User", "Update user information"),
                ("user.delete", "Delete User", "Delete users"),
                ("user.assign-role", "Assign Roles", "Assign roles to users"),
                ("user.view-permissions", "View Permissions", "View user permissions"),
                
                # Role permissions
                ("role.list", "List Roles", "View list of roles"),
                ("role.create", "Create Role", "Create new roles"),
                ("role.retrieve", "Retrieve Role", "View role details"),
                ("role.update", "Update Role", "Update role information"),
                ("role.delete", "Delete Role", "Delete roles"),
                
                # Permission permissions
                ("permission.list", "List Permissions", "View list of permissions"),
                ("permission.create", "Create Permission", "Create new permissions"),
                ("permission.delete", "Delete Permission", "Delete permissions"),
                
                # Wildcard permissions
                ("*", "All Permissions", "Full access to all resources"),
            ]

            permissions = []
            for code, name, description in permissions_data:
                # Check if exists
                stmt = select(Permission).where(Permission.code == code)
                result = await db.execute(stmt)
                perm = result.scalar_one_or_none()
                
                if not perm:
                    perm = Permission(code=code, name=name, description=description)
                    db.add(perm)
                permissions.append(perm)

            await db.commit()
            print(f"✓ Created {len(permissions)} permissions")

            # Create Admin Role
            stmt = select(Role).where(Role.name == "Admin")
            result = await db.execute(stmt)
            admin_role = result.scalar_one_or_none()

            if not admin_role:
                # Get wildcard permission
                stmt = select(Permission).where(Permission.code == "*")
                result = await db.execute(stmt)
                wildcard_perm = result.scalar_one()

                admin_role = Role(
                    name="Admin",
                    description="Full system access",
                    permissions=[wildcard_perm]
                )
                db.add(admin_role)
                await db.commit()
                print("✓ Created Admin role")

            # Create User Manager Role
            stmt = select(Role).where(Role.name == "User Manager")
            result = await db.execute(stmt)
            user_manager_role = result.scalar_one_or_none()

            if not user_manager_role:
                # Get user-related permissions
                stmt = select(Permission).where(
                    Permission.code.in_([
                        "user.list", "user.retrieve", "user.update",
                        "user.assign-role", "user.view-permissions"
                    ])
                )
                result = await db.execute(stmt)
                user_perms = result.scalars().all()

                user_manager_role = Role(
                    name="User Manager",
                    description="Manage users and roles",
                    permissions=user_perms
                )
                db.add(user_manager_role)
                await db.commit()
                print("✓ Created User Manager role")

            # Create Viewer Role
            stmt = select(Role).where(Role.name == "Viewer")
            result = await db.execute(stmt)
            viewer_role = result.scalar_one_or_none()

            if not viewer_role:
                # Get read-only permissions
                stmt = select(Permission).where(
                    Permission.code.in_([
                        "user.list", "user.retrieve",
                        "role.list", "role.retrieve",
                        "permission.list"
                    ])
                )
                result = await db.execute(stmt)
                view_perms = result.scalars().all()

                viewer_role = Role(
                    name="Viewer",
                    description="Read-only access",
                    permissions=view_perms
                )
                db.add(viewer_role)
                await db.commit()
                print("✓ Created Viewer role")

            # Create admin user
            stmt = select(User).where(User.email == "admin@example.com")
            result = await db.execute(stmt)
            admin_user = result.scalar_one_or_none()

            if not admin_user:
                admin_user = User(
                    email="admin@example.com",
                    first_name="Admin",
                    last_name="User",
                    password=hash_password("Admin@123"),
                    is_superuser=True,
                    roles=[admin_role]
                )
                db.add(admin_user)
                await db.commit()
                print("✓ Created admin user (admin@example.com / Admin@123)")

            print("\n✅ Initial data seeded successfully!")

        except Exception as e:
            print(f"❌ Error seeding data: {e}")
            await db.rollback()


import asyncio
asyncio.run(seed_initial_data())