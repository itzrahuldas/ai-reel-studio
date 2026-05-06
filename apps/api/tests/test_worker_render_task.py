import importlib
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

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


def test_render_task_returns_failed_without_complete_log(monkeypatch) -> None:
    with _worker_import_context():
        render_service = importlib.import_module("app.services.render_service")
        render_task = importlib.import_module("app.tasks.render_reel")
        fake_logger = _FakeLogger()

        async def fake_pipeline(**_kwargs) -> bool:
            return False

        monkeypatch.setattr(render_service, "_run_render_pipeline_inline", fake_pipeline)
        monkeypatch.setattr(render_task, "logger", fake_logger)

        result = render_task.render_reel_task.run(
            project_id=str(uuid4()),
            version_id=str(uuid4()),
            render_job_id=str(uuid4()),
        )

        assert result["status"] == "failed"
        assert "render_reel_task.failed" in fake_logger.warning_events
        assert "render_reel_task.complete" not in fake_logger.info_events


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
