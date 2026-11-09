"""Backend smoke-test script for CrackSight AI (Milestone 12, sub-deliverable 6).

Performs non-mutating health checks against a deployed CrackSight AI backend.
Designed to be run against a live Render Web Service URL to verify the service
is operational after deployment. All checks are read-only GET requests; no
inference, no database writes, no file uploads, no authenticated operations.

Usage::

    python scripts/smoke_test_backend.py --base-url https://cracksight-backend.onrender.com

    # or via environment variable:
    SMOKE_TEST_BASE_URL=https://cracksight-backend.onrender.com python scripts/smoke_test_backend.py

Exit codes:
    0  All smoke checks passed.
    1  One or more smoke checks failed.
    2  Missing or invalid base URL.

The script never prints secrets, tokens, or credentials. It only logs the
scheme and host of the target URL (never the full URL with query parameters).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("smoke_test_backend")

DEFAULT_TIMEOUT_SECONDS = 10


def _safe_url_display(url: str) -> str:
    """Return scheme+host only, never the full URL with query parameters.

    Ensures no tokens, credentials, or signature strings are ever written to
    logs.
    """
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(url)
    except ValueError:
        return "<unparseable url>"
    host = parts.hostname or parts.netloc
    if "@" in (parts.netloc or ""):
        host = host.split("@")[-1]
    if parts.port:
        host = f"{host}:{parts.port}"
    return f"{parts.scheme or 'https'}://{host}"


def _fetch(
    url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> tuple[int, dict[str, Any] | None]:
    """Perform a GET request and return (status_code, parsed_json_or_None).

    Never raises on HTTP errors; returns the status code and parsed body so the
    caller can decide how to report. Network failures return (0, None).
    """
    try:
        with urlopen(Request(url), timeout=timeout) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                data = None
            return status, data
    except HTTPError as exc:
        # HTTPError is raised for 4xx/5xx responses; read the body if present.
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover - best effort
            body = ""
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            data = None
        return exc.code, data
    except (URLError, OSError) as exc:
        logger.error("Network error reaching %s: %s", _safe_url_display(url), exc)
        return 0, None


def check_liveness(base_url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> bool:
    """Check the /live liveness endpoint.

    Returns True if the service responds HTTP 200 with status "alive".
    """
    url = base_url.rstrip("/") + "/live"
    status, data = _fetch(url, timeout=timeout)

    if status != 200:
        logger.error(
            "/live returned HTTP %s from %s (expected 200)",
            status,
            _safe_url_display(url),
        )
        return False

    if not isinstance(data, dict) or data.get("status") != "alive":
        logger.error(
            "/live returned unexpected payload from %s: %r",
            _safe_url_display(url),
            data,
        )
        return False

    logger.info("/live OK (HTTP 200, status=alive)")
    return True


def check_readiness(base_url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> bool:
    """Check the /ready readiness endpoint.

    Returns True if the service responds HTTP 200. The /ready endpoint may
    report "not_ready" if dependencies (Neon, R2) are not yet configured; that
    is expected before live credentials are provisioned and does not fail the
    smoke test by itself. We log the readiness details for visibility.
    """
    url = base_url.rstrip("/") + "/ready"
    status, data = _fetch(url, timeout=timeout)

    if status != 200:
        logger.error(
            "/ready returned HTTP %s from %s (expected 200)",
            status,
            _safe_url_display(url),
        )
        return False

    if not isinstance(data, dict):
        logger.error(
            "/ready returned unexpected payload from %s: %r",
            _safe_url_display(url),
            data,
        )
        return False

    ready = data.get("status")
    checks = data.get("checks", {})
    logger.info(
        "/ready OK (HTTP 200, status=%s, checks=%s)",
        ready,
        checks,
    )
    # /ready may legitimately be "not_ready" before external services are
    # provisioned; this is informational, not a smoke-test failure.
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test the CrackSight AI backend health endpoints."
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=(
            "Base URL of the deployed backend (e.g. "
            "https://cracksight-backend.onrender.com). "
            "Defaults to the SMOKE_TEST_BASE_URL environment variable."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP request timeout in seconds (default: 10).",
    )
    args = parser.parse_args(argv)

    base_url = args.base_url or os.environ.get("SMOKE_TEST_BASE_URL", "").strip()
    if not base_url:
        logger.error(
            "Missing backend base URL: provide --base-url or set the "
            "SMOKE_TEST_BASE_URL environment variable. Do not hardcode the URL "
            "in scripts or commit it to version control."
        )
        return 2

    # Strip trailing slash for consistent URL construction.
    base_url = base_url.rstrip("/")

    logger.info("Smoke-testing backend at %s", _safe_url_display(base_url))

    failures: list[str] = []

    if not check_liveness(base_url, timeout=args.timeout):
        failures.append("/live liveness check failed")

    if not check_readiness(base_url, timeout=args.timeout):
        failures.append("/ready readiness check failed")

    if failures:
        logger.error("Smoke test FAILED: %s", "; ".join(failures))
        return 1

    logger.info("Smoke test PASSED: backend is reachable and /live + /ready respond.")
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    sys.exit(main())
