"""Worker package that can also import shared API modules.

The worker owns Celery task modules under ``app.tasks`` while the API owns
shared models/services under ``app.models`` and ``app.services``. Extending the
package path lets both live under the ``app`` namespace when the worker starts
with ``apps/worker`` before ``apps/api`` on ``PYTHONPATH``.
"""

from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

for candidate in (
    Path(__file__).resolve().parents[2] / "api" / "app",
    Path("/api_src/app"),
):
    if candidate.is_dir():
        candidate_path = str(candidate)
        if candidate_path not in __path__:
            __path__.append(candidate_path)
