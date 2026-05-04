import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException


class _ScalarResult:
    def __init__(self, value=None):
        self.value = value

    def scalars(self):
        return self

    def first(self):
        return self.value


class FakeAsyncDb:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.refreshed = []

    async def execute(self, _stmt):
        return _ScalarResult(None)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if hasattr(obj, "id") and getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshed.append(obj)


def _publish_fixtures(user_id=None):
    user_id = user_id or uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    version_id = uuid.uuid4()
    social_account_id = uuid.uuid4()
    project = SimpleNamespace(
        id=project_id,
        workspace_id=workspace_id,
        created_by=user_id,
        status="ready_to_publish",
    )
    version = SimpleNamespace(
        id=version_id,
        project_id=project_id,
        caption="Caption",
        hashtags=["ai"],
        video_asset_id=uuid.uuid4(),
        status="ready_to_publish",
    )
    social_account = SimpleNamespace(
        id=social_account_id,
        workspace_id=workspace_id,
        connected_by_user_id=user_id,
    )
    asset = SimpleNamespace(
        id=uuid.uuid4(),
        mime_type="video/mp4",
        url="https://cdn.example.com/reel.mp4",
    )
    return user_id, project, version, social_account, asset


@pytest.mark.asyncio
async def test_create_workspace_creates_free_subscription():
    from app.models.models import WorkspaceSubscription
    from app.schemas.schemas import CreateWorkspaceRequest
    from app.services.workspace import create_workspace

    db = FakeAsyncDb()
    user_id = uuid.uuid4()

    workspace = await create_workspace(
        db,
        user_id,
        CreateWorkspaceRequest(name="Side Studio", slug="side-studio"),
    )

    subscriptions = [obj for obj in db.added if isinstance(obj, WorkspaceSubscription)]
    assert workspace.owner_id == user_id
    assert len(subscriptions) == 1
    assert subscriptions[0].plan_key == "FREE"
    assert subscriptions[0].status == "active"


@pytest.mark.asyncio
async def test_publish_consumes_after_url_validation_with_job_id(monkeypatch):
    from app.models.models import UsageEventType
    from app.services import publish_service

    db = FakeAsyncDb()
    user_id, project, version, social_account, asset = _publish_fixtures()
    data = SimpleNamespace(
        social_account_id=social_account.id,
        caption=None,
        share_to_feed=True,
        allow_comments=True,
    )

    monkeypatch.setattr(publish_service.settings, "PUBLISH_MODE", "async")

    with patch(
        "app.services.publish_service.validate_publish_preflight",
        new=AsyncMock(return_value=(project, version, social_account, asset)),
    ), patch(
        "app.services.publish_service.consume_usage",
        new=AsyncMock(),
    ) as mock_consume, patch(
        "app.workers.celery_client.celery_client.send_task",
        return_value=SimpleNamespace(id="celery-task-id"),
    ):
        job, _, _ = await publish_service.create_publish_job(db, user_id, project.id, data)

    assert str(job.id) != "None"
    mock_consume.assert_awaited_once()
    kwargs = mock_consume.await_args.kwargs
    assert kwargs["event_type"] == UsageEventType.PUBLISH
    assert kwargs["related_job_id"] == str(job.id)


@pytest.mark.asyncio
async def test_publish_does_not_consume_when_live_url_validation_fails(monkeypatch):
    from app.services import publish_service

    db = FakeAsyncDb()
    user_id, project, version, social_account, asset = _publish_fixtures()
    asset.url = "http://cdn.example.com/reel.mp4"
    data = SimpleNamespace(
        social_account_id=social_account.id,
        caption=None,
        share_to_feed=True,
        allow_comments=True,
    )

    monkeypatch.setattr(publish_service.settings, "INSTAGRAM_INTEGRATION_MODE", "live")

    with (
        patch(
            "app.services.publish_service.validate_publish_preflight",
            new=AsyncMock(return_value=(project, version, social_account, asset)),
        ),
        patch(
            "app.services.publish_service.consume_usage",
            new=AsyncMock(),
        ) as mock_consume,
        pytest.raises(HTTPException) as exc_info,
    ):
        await publish_service.create_publish_job(db, user_id, project.id, data)

    assert exc_info.value.status_code == 400
    mock_consume.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_validates_time_before_usage_write():
    from app.services import publish_service

    db = FakeAsyncDb()
    user_id, project, version, social_account, asset = _publish_fixtures()
    data = SimpleNamespace(
        social_account_id=social_account.id,
        caption=None,
        share_to_feed=True,
        allow_comments=True,
        scheduled_at=datetime.now(UTC) + timedelta(seconds=30),
        schedule_timezone="UTC",
    )

    with (
        patch(
            "app.services.publish_service.validate_publish_preflight",
            new=AsyncMock(return_value=(project, version, social_account, asset)),
        ),
        patch(
            "app.services.publish_service.check_usage_limit",
            new=AsyncMock(),
        ) as mock_check,
        patch(
            "app.services.publish_service.consume_usage",
            new=AsyncMock(),
        ) as mock_consume,
        pytest.raises(HTTPException) as exc_info,
    ):
        await publish_service.schedule_publish_job(db, user_id, project.id, data)

    assert exc_info.value.status_code == 400
    mock_check.assert_not_called()
    mock_consume.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_creates_scheduled_usage_event_with_job_id():
    from app.models.models import UsageEventType
    from app.services import publish_service

    db = FakeAsyncDb()
    user_id, project, version, social_account, asset = _publish_fixtures()
    data = SimpleNamespace(
        social_account_id=social_account.id,
        caption=None,
        share_to_feed=True,
        allow_comments=True,
        scheduled_at=datetime.now(UTC) + timedelta(minutes=5),
        schedule_timezone="UTC",
    )

    with patch(
        "app.services.publish_service.validate_publish_preflight",
        new=AsyncMock(return_value=(project, version, social_account, asset)),
    ), patch(
        "app.services.publish_service.check_usage_limit",
        new=AsyncMock(),
    ) as mock_check, patch(
        "app.services.publish_service.consume_usage",
        new=AsyncMock(),
    ) as mock_consume:
        job, _, _ = await publish_service.schedule_publish_job(db, user_id, project.id, data)

    mock_check.assert_awaited_once()
    mock_consume.assert_awaited_once()
    kwargs = mock_consume.await_args.kwargs
    assert kwargs["event_type"] == UsageEventType.SCHEDULED_PUBLISH
    assert kwargs["related_job_id"] == str(job.id)
    assert kwargs["enforce_limit"] is False
