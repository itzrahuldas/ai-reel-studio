#!/usr/bin/env python3
"""Run staging smoke checks against a deployed AI Reel Studio environment."""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class SmokeFailure(Exception):
    """A smoke step failed."""


class SmokeSkip(Exception):
    """A smoke step was intentionally skipped."""


@dataclass
class StepResult:
    name: str
    status: str
    detail: str


@dataclass
class HttpResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]

    def json(self) -> dict[str, Any] | list[Any]:
        if not self.body:
            return {}
        return json.loads(self.body.decode("utf-8"))

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class SmokeHttpClient:
    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.access_token: str | None = None

    def url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        expected_statuses: set[int] | None = None,
        authenticated: bool = False,
    ) -> HttpResponse:
        request_headers = dict(headers or {})
        request_body = body
        if json_body is not None:
            request_body = json.dumps(json_body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        if authenticated:
            if not self.access_token:
                raise SmokeFailure("Authenticated request attempted before login.")
            request_headers["Authorization"] = f"Bearer {self.access_token}"

        req = Request(self.url(path), data=request_body, headers=request_headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout_seconds) as response:
                smoke_response = HttpResponse(
                    status_code=response.status,
                    body=response.read(),
                    headers=dict(response.headers),
                )
        except HTTPError as exc:
            smoke_response = HttpResponse(
                status_code=exc.code,
                body=exc.read(),
                headers=dict(exc.headers),
            )
        except URLError as exc:
            raise SmokeFailure(f"Request failed: {exc.reason}") from exc

        if expected_statuses and smoke_response.status_code not in expected_statuses:
            body_text = smoke_response.text[:600]
            if self.access_token:
                body_text = body_text.replace(self.access_token, "<access_token>")
            raise SmokeFailure(
                f"{method} {path} returned {smoke_response.status_code}: {body_text}"
            )
        return smoke_response

    def upload_png(self) -> dict[str, Any]:
        boundary = f"smoke-{uuid.uuid4().hex}"
        parts = [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                'Content-Disposition: form-data; name="file"; filename="smoke.png"\r\n'
                "Content-Type: image/png\r\n\r\n"
            ).encode("utf-8"),
            PNG_1X1,
            f"\r\n--{boundary}--\r\n".encode("utf-8"),
        ]
        response = self.request(
            "POST",
            "/api/v1/media-assets/upload",
            body=b"".join(parts),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            expected_statuses={201},
            authenticated=True,
        )
        data = response.json()
        if not isinstance(data, dict) or not data.get("id"):
            raise SmokeFailure("Media upload response did not include an asset id.")
        return data


def env_bool(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SmokeFailure(f"{name} is required.")
    return value


def run_step(results: list[StepResult], name: str, func: Any) -> Any:
    started = time.monotonic()
    try:
        detail = func()
    except SmokeSkip as exc:
        results.append(StepResult(name, "SKIPPED", str(exc)))
        print(f"SKIPPED {name}: {exc}")
        return None
    except Exception as exc:
        results.append(StepResult(name, "FAIL", str(exc)))
        print(f"FAIL    {name}: {exc}")
        return None

    elapsed = time.monotonic() - started
    message = str(detail or "ok")
    results.append(StepResult(name, "PASS", f"{message} ({elapsed:.1f}s)"))
    print(f"PASS    {name}: {message} ({elapsed:.1f}s)")
    return detail


def check_liveness(client: SmokeHttpClient) -> str:
    data = client.request("GET", "/health", expected_statuses={200}).json()
    if not isinstance(data, dict) or data.get("status") != "ok":
        raise SmokeFailure(f"Unexpected health response: {data}")
    return f"version={data.get('version')} env={data.get('environment')}"


def check_readiness(client: SmokeHttpClient) -> dict[str, Any]:
    data = client.request(
        "GET",
        "/api/v1/health/readiness",
        expected_statuses={200},
    ).json()
    if not isinstance(data, dict):
        raise SmokeFailure("Readiness response was not a JSON object.")
    status = data.get("status")
    if status == "not_ready":
        raise SmokeFailure(f"Readiness is not_ready: {json.dumps(data.get('checks', {}))[:800]}")
    if status not in {"ready", "degraded"}:
        raise SmokeFailure(f"Unknown readiness status: {status}")
    return data


def check_config(client: SmokeHttpClient) -> dict[str, Any]:
    data = client.request("GET", "/api/v1/health/config", expected_statuses={200}).json()
    if not isinstance(data, dict):
        raise SmokeFailure("Config response was not a JSON object.")
    serialized = json.dumps(data).lower()
    forbidden_fragments = ("secret", "token", "sk_", "api_key")
    if any(fragment in serialized for fragment in forbidden_fragments):
        raise SmokeFailure("Safe config response appears to contain a secret-like field.")
    return data


def authenticate(client: SmokeHttpClient, email: str, password: str) -> str:
    payload = {
        "email": email,
        "password": password,
        "full_name": "Staging Smoke Test",
    }
    register_response = client.request(
        "POST",
        "/api/v1/auth/register",
        json_body=payload,
        expected_statuses={201, 400, 409, 422},
    )
    if register_response.status_code == 201:
        data = register_response.json()
        if isinstance(data, dict) and data.get("access_token"):
            client.access_token = str(data["access_token"])
            return "registered new smoke user"

    login_response = client.request(
        "POST",
        "/api/v1/auth/login",
        json_body={"email": email, "password": password},
        expected_statuses={200},
    )
    data = login_response.json()
    if not isinstance(data, dict) or not data.get("access_token"):
        raise SmokeFailure("Login response did not include an access token.")
    client.access_token = str(data["access_token"])
    return "logged in existing smoke user"


def check_auth_me(client: SmokeHttpClient) -> str:
    data = client.request(
        "GET",
        "/api/v1/auth/me",
        expected_statuses={200},
        authenticated=True,
    ).json()
    if not isinstance(data, dict) or not data.get("email"):
        raise SmokeFailure("Auth me response did not include user email.")
    return f"user={data.get('email')}"


def check_billing(client: SmokeHttpClient) -> dict[str, Any]:
    plans = client.request("GET", "/api/v1/billing/plans", expected_statuses={200}).json()
    if not isinstance(plans, list) or len(plans) < 3:
        raise SmokeFailure("Billing plans response did not include all plans.")
    usage = client.request(
        "GET",
        "/api/v1/billing/usage",
        expected_statuses={200},
        authenticated=True,
    ).json()
    if not isinstance(usage, dict) or "ai_generations_used" not in usage:
        raise SmokeFailure("Billing usage response did not include usage counters.")
    return usage


def maybe_test_stripe_mock(
    client: SmokeHttpClient,
    config: dict[str, Any],
    enabled: bool,
) -> str:
    if not enabled:
        raise SmokeSkip("SMOKE_TEST_STRIPE_MOCK=false")
    if config.get("environment") != "development" or config.get("stripe_mode") != "mock":
        raise SmokeSkip("Dev mock checkout is only enabled for APP_ENV=development and STRIPE_MODE=mock.")
    client.request(
        "POST",
        "/api/v1/billing/dev/mock-checkout-complete",
        json_body={"plan_key": "CREATOR"},
        expected_statuses={200},
        authenticated=True,
    )
    usage = client.request(
        "GET",
        "/api/v1/billing/usage",
        expected_statuses={200},
        authenticated=True,
    ).json()
    if not isinstance(usage, dict) or usage.get("current_plan") != "CREATOR":
        raise SmokeFailure("Mock checkout did not update the workspace to CREATOR.")
    return "mock checkout updated plan to CREATOR"


def poll_project_ready(client: SmokeHttpClient, project_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        data = client.request(
            "GET",
            f"/api/v1/reel-projects/{project_id}",
            expected_statuses={200},
            authenticated=True,
        ).json()
        if not isinstance(data, dict):
            raise SmokeFailure("Project detail response was not a JSON object.")
        status = str(data.get("status", "")).lower()
        latest_version = data.get("latest_version") or {}
        version_ready = isinstance(latest_version, dict) and bool(
            latest_version.get("script") or latest_version.get("hook")
        )
        if version_ready or status in {"ready_for_review", "approved", "rendered"}:
            return data
        if "failed" in status or "error" in status:
            raise SmokeFailure(f"Project generation failed with status {status}.")
        time.sleep(3)
    raise SmokeFailure("Timed out waiting for reel generation.")


def poll_render_ready(client: SmokeHttpClient, project_id: str, timeout_seconds: int) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        data = client.request(
            "GET",
            f"/api/v1/reel-projects/{project_id}/render-jobs",
            expected_statuses={200},
            authenticated=True,
        ).json()
        if isinstance(data, list) and data:
            latest = data[0]
            status = str(latest.get("status", "")).lower()
            if status in {"completed", "complete", "succeeded", "rendered"}:
                return status
            if status in {"failed", "error"}:
                raise SmokeFailure(f"Render job failed with status {status}.")
        time.sleep(3)
    raise SmokeFailure("Timed out waiting for render job.")


def maybe_create_and_render_reel(
    client: SmokeHttpClient,
    enabled: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    if not enabled:
        raise SmokeSkip("SMOKE_CREATE_REEL=false")
    asset = client.upload_png()
    response = client.request(
        "POST",
        "/api/v1/reel-projects/",
        json_body={
            "prompt": "Staging smoke test reel for a small cafe launching a new iced coffee.",
            "language": "en",
            "tone": "professional",
            "duration_seconds": 10,
            "cta_text": "Visit today",
            "title": f"Smoke Test {datetime.now(UTC).isoformat()}",
            "source_image_id": asset["id"],
        },
        expected_statuses={201},
        authenticated=True,
    )
    created = response.json()
    if not isinstance(created, dict) or not isinstance(created.get("project"), dict):
        raise SmokeFailure("Create reel response did not include a project object.")
    project_id = str(created["project"]["id"])
    ready_project = poll_project_ready(client, project_id, timeout_seconds)
    client.request(
        "POST",
        f"/api/v1/reel-projects/{project_id}/render",
        expected_statuses={201},
        authenticated=True,
    )
    render_status = poll_render_ready(client, project_id, timeout_seconds)
    return {"project_id": project_id, "project": ready_project, "render_status": render_status}


def maybe_test_instagram_mock(
    client: SmokeHttpClient,
    config: dict[str, Any],
    reel_context: dict[str, Any] | None,
    enabled: bool,
) -> str:
    if not enabled:
        raise SmokeSkip("SMOKE_TEST_INSTAGRAM_MOCK=false")
    if config.get("environment") != "development" or config.get("instagram_mode") != "mock":
        raise SmokeSkip("Mock Instagram connect is only enabled for APP_ENV=development and mock mode.")
    if not reel_context:
        raise SmokeSkip("Instagram mock publish requires SMOKE_CREATE_REEL=true and a rendered reel.")

    client.request(
        "POST",
        "/api/v1/integrations/instagram/mock-connect",
        expected_statuses={200},
        authenticated=True,
    )
    status_response = client.request(
        "GET",
        "/api/v1/integrations/instagram/status",
        expected_statuses={200},
        authenticated=True,
    ).json()
    if not isinstance(status_response, dict) or not status_response.get("connected"):
        raise SmokeFailure("Mock Instagram account did not connect.")
    accounts = status_response.get("accounts") or []
    if not accounts:
        raise SmokeFailure("Instagram status did not include a mock account.")
    account_id = accounts[0]["id"]
    scheduled_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    publish_response = client.request(
        "POST",
        f"/api/v1/reel-projects/{reel_context['project_id']}/schedule",
        json_body={
            "social_account_id": account_id,
            "caption": "Staging smoke test scheduled publish.",
            "share_to_feed": True,
            "allow_comments": True,
            "scheduled_at": scheduled_at,
            "schedule_timezone": "UTC",
        },
        expected_statuses={200},
        authenticated=True,
    ).json()
    if not isinstance(publish_response, dict) or not isinstance(
        publish_response.get("publish_job"),
        dict,
    ):
        raise SmokeFailure("Schedule publish response did not include a publish job.")
    publish_status = str(publish_response["publish_job"].get("status", "")).lower()
    if publish_status not in {"scheduled", "queued"}:
        raise SmokeFailure(f"Unexpected mock publish status: {publish_status}")
    return f"mock publish job {publish_status}"


def check_frontend(base_url: str | None, timeout_seconds: int) -> str:
    if not base_url:
        raise SmokeSkip("SMOKE_FRONTEND_BASE_URL is not set.")
    client = SmokeHttpClient(base_url, timeout_seconds)
    checked: list[str] = []
    for path in ("/", "/login", "/dashboard/billing"):
        response = client.request("GET", path, expected_statuses={200, 301, 302, 307, 308, 401, 403})
        checked.append(f"{path}:{response.status_code}")
    return ", ".join(checked)


def print_summary(results: list[StepResult]) -> None:
    print("\nSmoke test summary")
    print("------------------")
    for result in results:
        print(f"{result.status:7} {result.name} - {result.detail}")


def main() -> int:
    results: list[StepResult] = []
    try:
        api_base_url = required_env("SMOKE_API_BASE_URL")
        email = required_env("SMOKE_TEST_EMAIL")
        password = required_env("SMOKE_TEST_PASSWORD")
    except SmokeFailure as exc:
        print(f"FAIL    configuration: {exc}")
        return 2

    timeout_seconds = int(os.getenv("SMOKE_TIMEOUT_SECONDS", "120"))
    frontend_base_url = os.getenv("SMOKE_FRONTEND_BASE_URL")
    create_reel = env_bool("SMOKE_CREATE_REEL")
    test_stripe_mock = env_bool("SMOKE_TEST_STRIPE_MOCK")
    test_instagram_mock = env_bool("SMOKE_TEST_INSTAGRAM_MOCK")

    client = SmokeHttpClient(api_base_url, timeout_seconds)

    run_step(results, "API liveness", lambda: check_liveness(client))
    readiness = run_step(results, "API readiness", lambda: check_readiness(client))
    config = run_step(results, "safe config", lambda: check_config(client)) or {}
    run_step(results, "frontend routes", lambda: check_frontend(frontend_base_url, timeout_seconds))
    run_step(results, "auth register/login", lambda: authenticate(client, email, password))
    run_step(results, "auth me", lambda: check_auth_me(client))
    run_step(results, "billing plans and usage", lambda: check_billing(client))
    run_step(
        results,
        "Stripe mock checkout",
        lambda: maybe_test_stripe_mock(client, config, test_stripe_mock),
    )
    reel_context = run_step(
        results,
        "create and render reel",
        lambda: maybe_create_and_render_reel(client, create_reel, timeout_seconds),
    )
    run_step(
        results,
        "Instagram mock publish",
        lambda: maybe_test_instagram_mock(client, config, reel_context, test_instagram_mock),
    )

    print_summary(results)
    failed = [result for result in results if result.status == "FAIL"]
    if failed:
        print("\nFAIL: staging smoke test failed.")
        return 1
    if isinstance(readiness, dict) and readiness.get("status") == "degraded":
        print("\nPASS with degraded readiness: inspect /api/v1/health/readiness before promoting.")
    else:
        print("\nPASS: staging smoke test completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
