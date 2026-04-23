"""Concurrency-focused tests for control-plane account bootstrap."""
import asyncio
import os
import sys
import tempfile
import unittest

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

IMPORT_ERROR = None

try:
    from app.database import ControlBase
    from app.models import AdminUser, SystemConfig
    from app.services.account import account_service
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
