import importlib
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

os.environ["DEBUG"] = "false"
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-worker-scheduler-tests")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "a" * 64)


@contextmanager
def _worker_import_context() -> Iterator[None]:
    """Import worker modules before API modules, matching the worker image."""
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


def test_scheduler_task_routes_to_scheduler_queue() -> None:
    with _worker_import_context():
        worker_main = importlib.import_module("app.main")
        worker_main.celery_app.set_current()
        scheduler = importlib.import_module("app.tasks.scheduler")

        routes = worker_main.celery_app.conf.task_routes
        schedule = worker_main.celery_app.conf.beat_schedule[
            "scan-scheduled-publish-jobs-every-minute"
        ]

        assert routes["app.tasks.scheduler.*"]["queue"] == worker_main.SCHEDULER_QUEUE
        assert schedule["options"]["queue"] == worker_main.SCHEDULER_QUEUE
        assert scheduler.scan_scheduled_publish_jobs.queue == worker_main.SCHEDULER_QUEUE


def test_worker_compose_queues_keep_scheduler_off_generation_workers() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    for compose_file in ("docker-compose.yml", "docker-compose.staging.yml"):
        compose_text = (repo_root / compose_file).read_text(encoding="utf-8")
        assert "--queues=generation,default" not in compose_text
        assert "--queues=generation" in compose_text
        assert "--queues=publishing,scheduler" in compose_text


def test_scheduler_imports_with_worker_namespace_package() -> None:
    with _worker_import_context():
        scheduler = importlib.import_module("app.tasks.scheduler")
        config = importlib.import_module("app.core.config")

        assert Path(scheduler.__file__).as_posix().endswith("apps/worker/app/tasks/scheduler.py")
        assert Path(config.__file__).as_posix().endswith("apps/api/app/core/config.py")


@pytest.mark.asyncio
async def test_scheduler_session_scope_disposes_local_engine(monkeypatch) -> None:
    with _worker_import_context():
        scheduler = importlib.import_module("app.tasks.scheduler")
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

        monkeypatch.setattr(scheduler, "create_async_engine", fake_create_async_engine)
        monkeypatch.setattr(scheduler, "async_sessionmaker", fake_async_sessionmaker)

        async with scheduler.scheduler_session_scope() as db:
            assert db is fake_session
            assert fake_session.entered is True
            assert fake_engine.disposed is False

        assert fake_session.exited is True
        assert fake_engine.disposed is True
        assert captured["engine_args"][0] == scheduler.settings.DATABASE_URL


def test_generation_worker_imports_still_validate() -> None:
    with _worker_import_context():
        generate_reel = importlib.import_module("app.tasks.generate_reel")
        reel_project_service = importlib.import_module("app.services.reel_project")

        assert generate_reel.generate_reel_task.name == "app.tasks.generate_reel.generate_reel_task"
        assert Path(reel_project_service.__file__).as_posix().endswith(
            "apps/api/app/services/reel_project.py"
        )


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
