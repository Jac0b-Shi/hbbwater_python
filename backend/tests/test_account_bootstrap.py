"""Concurrency-focused tests for control-plane account bootstrap."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

IMPORT_ERROR = None

try:
    from fastapi import HTTPException

    from app.database import ControlBase
    from app.models import AdminUser, SystemConfig
    from app.services.account import _hash_registration_code, _registration_key, account_service
except ModuleNotFoundError as exc:  # pragma: no cover - environment-dependent
    IMPORT_ERROR = exc


@unittest.skipIf(IMPORT_ERROR is not None, f"backend dependencies unavailable: {IMPORT_ERROR}")
class AccountBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        database_path = os.path.join(self.tempdir.name, "control-test.db")
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}", future=True)
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

        async with self.engine.begin() as conn:
            await conn.run_sync(ControlBase.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.tempdir.cleanup()

    async def test_profile_and_provider_bootstrap_can_run_on_fresh_sqlite(self):
        async def fetch_profile():
            async with self.session_factory() as session:
                return await account_service.get_profile(session)

        async def fetch_provider_catalog():
            async with self.session_factory() as session:
                return await account_service.get_provider_catalog(session)

        profile, providers = await asyncio.gather(fetch_profile(), fetch_provider_catalog())

        self.assertEqual(profile["username"], "admin")
        self.assertEqual(providers["current"], "local")

        async with self.session_factory() as session:
            user_count = await session.scalar(select(func.count()).select_from(AdminUser))
            provider_count = await session.scalar(
                select(func.count())
                .select_from(SystemConfig)
                .where(SystemConfig.config_key == "account_provider")
            )

        self.assertEqual(user_count, 1)
        self.assertEqual(provider_count, 1)

    async def test_self_registered_users_after_bootstrap_are_inactive(self):
        async with self.session_factory() as session:
            bootstrap_user = await account_service.register_user(
                session,
                {
                    "username": "root",
                    "display_name": "Root Admin",
                    "email": "root@example.com",
                    "password": "Password123!",
                },
            )

            self.assertEqual(bootstrap_user["role"], "super_admin")
            self.assertTrue(bootstrap_user["is_active"])

            pending_email = "pending@example.com"
            verification_code = "123456"
            now = datetime.utcnow()
            session.add(
                SystemConfig(
                    config_key=_registration_key(pending_email),
                    config_value=json.dumps(
                        {
                            "email": pending_email,
                            "code_hash": _hash_registration_code(pending_email, verification_code),
                            "sent_at": now.isoformat(),
                            "expires_at": (now + timedelta(minutes=10)).isoformat(),
                        }
                    ),
                    description="注册验证码",
                )
            )
            await session.commit()

            pending_user = await account_service.register_user(
                session,
                {
                    "username": "pending",
                    "display_name": "Pending User",
                    "email": pending_email,
                    "verification_code": verification_code,
                    "password": "Password123!",
                },
            )

            self.assertEqual(pending_user["role"], "user")
            self.assertFalse(pending_user["is_active"])

            with self.assertRaises(HTTPException) as exc:
                await account_service.authenticate(session, "pending", "Password123!")

            self.assertEqual(exc.exception.status_code, 401)
            self.assertEqual(exc.exception.detail, "账号已停用，请联系超级管理员开通账号权限")
