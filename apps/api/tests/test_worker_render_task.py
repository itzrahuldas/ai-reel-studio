"""
Tests for the Celery render task.

Covers:
1. render_session_scope creates a fresh engine and disposes it on exit.
2. render_reel_task calls _run_render_pipeline_with_db (not _run_render_pipeline_inline)
   so the global AsyncSessionLocal is never touched from a Celery task.
3. A pipeline that returns False → task returns status=failed, no complete log.
4. A pipeline that raises  → task logs safely and returns status=failed immediately (no retry).
5. Mock visual metadata is plumbed through when pipeline succeeds.
"""

import importlib
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest

os.environ["DEBUG"] = "false"
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-worker-render-tests")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "a" * 64)


@contextmanager
def _worker_import_context() -> Iterator[None]:
    api_root = Path(__file__).resolve().parents[1]
    worker_root = Path(__file__).resolve().parents[2] / "worker"
    saved_path = sys.path[:]
    saved_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }

    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]

    sys.path[:] = [str(worker_root), str(api_root)] + [
        path for path in sys.path if path not in {str(worker_root), str(api_root)}
    ]

    try:
        yield
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_modules)
        sys.path[:] = saved_path


# ── render_session_scope isolation test ───────────────────────────────────────

@pytest.mark.asyncio
async def test_render_session_scope_disposes_local_engine(monkeypatch) -> None:
    """render_session_scope must create a fresh engine and dispose it on exit."""
    with _worker_import_context():
        render_task_mod = importlib.import_module("app.tasks.render_reel")
        fake_engine = _FakeEngine()
        fake_session = _FakeSession()
        captured: dict[str, object] = {}

        def fake_create_async_engine(*args, **kwargs):
            captured["engine_args"] = args
            captured["engine_kwargs"] = kwargs
            return fake_engine

        def fake_async_sessionmaker(**kwargs):
            captured["sessionmaker_kwargs"] = kwargs
            return _FakeSessionFactory(fake_session)

        monkeypatch.setattr(render_task_mod, "create_async_engine", fake_create_async_engine)
        monkeypatch.setattr(render_task_mod, "async_sessionmaker", fake_async_sessionmaker)

        async with render_task_mod.render_session_scope() as db:
            assert db is fake_session
            assert fake_session.entered is True
            assert fake_engine.disposed is False

        assert fake_session.exited is True
        assert fake_engine.disposed is True
        assert captured["engine_args"][0] == render_task_mod.settings.DATABASE_URL


# ── Task uses _run_render_pipeline_with_db, not _run_render_pipeline_inline ──

def test_render_task_uses_pipeline_with_db_not_inline(monkeypatch) -> None:
    """
    The task must call _run_render_pipeline_with_db via _run_render_with_isolated_session.
    _run_render_pipeline_inline (which opens AsyncSessionLocal) must NOT be called.
    """
    with _worker_import_context():
        render_task_mod = importlib.import_module("app.tasks.render_reel")
        render_service_mod = importlib.import_module("app.services.render_service")

        inline_called: list[bool] = []
        with_db_called: list[bool] = []

        async def fake_inline(**_kwargs) -> bool:
            inline_called.append(True)
            return True

        async def fake_with_db(db, **_kwargs) -> bool:  # noqa: ANN001
            with_db_called.append(True)
            return True

        monkeypatch.setattr(render_service_mod, "_run_render_pipeline_inline", fake_inline)
        monkeypatch.setattr(render_service_mod, "_run_render_pipeline_with_db", fake_with_db)

        # Patch render_session_scope to yield a fake db and call through
        import contextlib

        @contextlib.asynccontextmanager
        async def fake_scope():
            yield object()  # fake db

        monkeypatch.setattr(render_task_mod, "render_session_scope", fake_scope)

        result = render_task_mod.render_reel_task.run(
            project_id=str(uuid4()),
            version_id=str(uuid4()),
            render_job_id=str(uuid4()),
        )

        assert result["status"] == "complete"
        assert not inline_called, "_run_render_pipeline_inline must NOT be called from Celery task"
        assert with_db_called, "_run_render_pipeline_with_db must be called"


# ── Failed pipeline → task returns failed, no complete log ───────────────────

def test_render_task_returns_failed_without_complete_log(monkeypatch) -> None:
    with _worker_import_context():
        render_service = importlib.import_module("app.services.render_service")
        render_task = importlib.import_module("app.tasks.render_reel")
        fake_logger = _FakeLogger()

        async def fake_pipeline_with_db(db, **_kwargs) -> bool:  # noqa: ANN001
            return False

        import contextlib

        @contextlib.asynccontextmanager
        async def fake_scope():
            yield object()

        monkeypatch.setattr(render_service, "_run_render_pipeline_with_db", fake_pipeline_with_db)
        monkeypatch.setattr(render_task, "render_session_scope", fake_scope)
        monkeypatch.setattr(render_task, "logger", fake_logger)

        result = render_task.render_reel_task.run(
            project_id=str(uuid4()),
            version_id=str(uuid4()),
            render_job_id=str(uuid4()),
        )

        assert result["status"] == "failed"
        assert "render_reel_task.failed" in fake_logger.warning_events
        assert "render_reel_task.complete" not in fake_logger.info_events


# ── Raising pipeline → task error-logs and returns failed ────────────────────

def test_render_task_exception_returns_failed(monkeypatch) -> None:
    with _worker_import_context():
        render_service = importlib.import_module("app.services.render_service")
        render_task = importlib.import_module("app.tasks.render_reel")
        fake_logger = _FakeLogger()

        async def fake_pipeline_with_db(db, **_kwargs) -> bool:  # noqa: ANN001
            msg = "boom"
            raise RuntimeError(msg)

        import contextlib

        @contextlib.asynccontextmanager
        async def fake_scope():
            yield object()

        monkeypatch.setattr(render_service, "_run_render_pipeline_with_db", fake_pipeline_with_db)
        monkeypatch.setattr(render_task, "render_session_scope", fake_scope)
        monkeypatch.setattr(render_task, "logger", fake_logger)

        result = render_task.render_reel_task.run(
            project_id=str(uuid4()),
            version_id=str(uuid4()),
            render_job_id=str(uuid4()),
        )

        assert result["status"] == "failed"
        assert "error" in result
        assert "render_reel_task.error" in fake_logger.warning_events
        assert "render_reel_task.complete" not in fake_logger.info_events


# ── _run_render_pipeline_inline delegates to _run_render_pipeline_with_db ────

@pytest.mark.asyncio
async def test_inline_pipeline_delegates_to_with_db(monkeypatch) -> None:
    """_run_render_pipeline_inline must open AsyncSessionLocal and pass it to _with_db."""
    with _worker_import_context():
        render_service = importlib.import_module("app.services.render_service")

        fake_session = _FakeSession()
        called_with_db: list[object] = []

        async def fake_with_db(db, **_kwargs) -> bool:  # noqa: ANN001
            called_with_db.append(db)
            return True

        monkeypatch.setattr(render_service, "_run_render_pipeline_with_db", fake_with_db)

        import contextlib

        @contextlib.asynccontextmanager
        async def fake_async_session_local():
            yield fake_session

        # Patch the lazy import inside _run_render_pipeline_inline
        import app.db.session as session_mod  # noqa: PLC0415 (inside context)
        monkeypatch.setattr(session_mod, "AsyncSessionLocal", fake_async_session_local)

        result = await render_service._run_render_pipeline_inline(
            project_id=uuid4(),
            version_id=uuid4(),
            render_job_id=uuid4(),
        )

        assert result is True
        assert len(called_with_db) == 1
        assert called_with_db[0] is fake_session


# ── Helpers ───────────────────────────────────────────────────────────────────

class _FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class _FakeSession:
    def __init__(self) -> None:
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    def __call__(self) -> _FakeSession:
        return self.session


class _FakeLogger:
    def __init__(self) -> None:
        self.info_events: list[str] = []
        self.warning_events: list[str] = []

    def info(self, event: str, **_kwargs) -> None:
        self.info_events.append(event)

    def warning(self, event: str, **_kwargs) -> None:
        self.warning_events.append(event)

    def exception(self, event: str, **_kwargs) -> None:
        self.warning_events.append(event)
