import os
from uuid import uuid4

import pytest

os.environ["DEBUG"] = "false"
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-workspace-plan-tests-1234567890")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "a" * 64)

from app.models.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
    WorkspacePlan,
    WorkspaceSubscription,
)
from app.schemas.schemas import CreateWorkspaceRequest
from app.services.auth import create_default_workspace
from app.services.workspace import create_workspace


class _EmptyScalarResult:
    def scalars(self):
        return self

    def first(self):
        return None


class _FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if isinstance(obj, Workspace) and obj.id is None:
                obj.id = uuid4()

    async def execute(self, _stmt):
        return _EmptyScalarResult()

    async def commit(self):
        return None

    async def refresh(self, _obj):
        return None


def _bind_value(column, value):
    processor = column.type.bind_processor(None)
    return processor(value) if processor else value


def test_legacy_workspace_enums_persist_lowercase_values():
    assert Workspace.__table__.c.plan.type.enums == ["free", "creator", "pro", "agency"]
    assert WorkspaceMember.__table__.c.role.type.enums == ["owner", "admin", "member", "viewer"]
    assert _bind_value(Workspace.__table__.c.plan, WorkspacePlan.FREE) == "free"
    assert _bind_value(Workspace.__table__.c.plan, WorkspacePlan.CREATOR) == "creator"
    assert _bind_value(WorkspaceMember.__table__.c.role, WorkspaceMemberRole.OWNER) == "owner"


@pytest.mark.asyncio
async def test_default_workspace_uses_lowercase_workspace_enum_and_uppercase_subscription_plan():
    db = _FakeSession()
    user = type("UserStub", (), {"id": uuid4(), "full_name": "Smoke"})()

    workspace = await create_default_workspace(db, user)

    member = next(obj for obj in db.added if isinstance(obj, WorkspaceMember))
    subscription = next(obj for obj in db.added if isinstance(obj, WorkspaceSubscription))
    assert workspace.plan == WorkspacePlan.FREE
    assert member.role == WorkspaceMemberRole.OWNER
    assert subscription.plan_key == "FREE"


@pytest.mark.asyncio
async def test_create_workspace_uses_lowercase_workspace_enum_and_uppercase_subscription_plan():
    db = _FakeSession()

    workspace = await create_workspace(
        db,
        uuid4(),
        CreateWorkspaceRequest(name="Smoke Workspace", slug="smoke-workspace"),
    )

    member = next(obj for obj in db.added if isinstance(obj, WorkspaceMember))
    subscription = next(obj for obj in db.added if isinstance(obj, WorkspaceSubscription))
    assert workspace.plan == WorkspacePlan.FREE
    assert member.role == WorkspaceMemberRole.OWNER
    assert subscription.plan_key == "FREE"
