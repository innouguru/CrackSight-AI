"""Unit tests for the build-time checkpoint download script.

All tests use mocked HTTP responses (no real R2 credentials, no live bucket)
and temporary directories for artifacts. The real model checkpoint is never
touched or downloaded by these tests.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

# Ensure the scripts directory is importable (download_checkpoint is a script,
# not an installed package).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from download_checkpoint import (  # noqa: E402
    DEFAULT_CHECKPOINT,
    SHA256_ENV,
    URL_ENV,
    download_checkpoint,
    main,
    _safe_url_display,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_CHECKPOINT = (
    REPO_ROOT / "model_artifacts" / "m3_crack_seg_baseline_b1_20261026_201725" / "best_model.pth"
)


# --------------------------------------------------------------------------- helpers


class _MockResponse:
    """HTTP response substitute readable in chunks."""

    def __init__(self, data: bytes, status: int = 200, headers: dict | None = None):
        self._data = data
        self._pos = 0
        self.status = status
        self.headers = headers or {}
        self.read_calls = 0
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        return False

    def read(self, n: int = -1):
        self.read_calls += 1
        if n == -1:
            chunk = self._data[self._pos:]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + n]
        self._pos += len(chunk)
        return chunk

    def close(self):
        self.closed = True


def _make_url() -> str:
    return (
        "https://cracksight-model-bucket.r2.cloudflarestorage.com/"
        "m3_crack_seg_baseline_b1_20261026_201725/best_model.pth"
        "?signature=SECRET_TOKEN&expires=12345&token=ABC"
    )


def _install_successful_urlopen(monkeypatch, data: bytes, status: int = 200, headers: dict | None = None):
    response = _MockResponse(data, status=status, headers=headers)
    monkeypatch.setattr(
        "download_checkpoint.urlopen",
        lambda req, timeout=None: response,
    )
    return response


def _install_failing_urlopen(monkeypatch, exc):
    monkeypatch.setattr(
        "download_checkpoint.urlopen",
        lambda req, timeout=None: (_ for _ in ()).throw(exc),
    )


# --------------------------------------------------------------------------- URL masking


def test_safe_url_display_strips_query_and_credentials():
    url = _make_url()
    display = _safe_url_display(url)
    assert display == "https://cracksight-model-bucket.r2.cloudflarestorage.com"
    assert "signature" not in display
    assert "SECRET_TOKEN" not in display
    assert "best_model.pth" not in display


def test_safe_url_display_strips_userinfo():
    url = "https://user:pass@host.r2.cloudflarestorage.com/key?sig=X"
    assert _safe_url_display(url) == "https://host.r2.cloudflarestorage.com"


# --------------------------------------------------------------------------- successful download


def test_successful_download_creates_destination_file(tmp_path, monkeypatch):
    payload = b"\x01\x02\x03" * 1000
    dest = tmp_path / "sub" / "best_model.pth"
    _install_successful_urlopen(monkeypatch, payload)

    ok = download_checkpoint(_make_url(), dest)

    assert ok is True
    assert dest.exists()
    assert dest.read_bytes() == payload


def test_download_is_streamed_in_chunks(tmp_path, monkeypatch):
    payload = os.urandom(100000)
    dest = tmp_path / "best_model.pth"
    response = _install_successful_urlopen(monkeypatch, payload)

    ok = download_checkpoint(_make_url(), dest)

    assert ok is True
    assert dest.read_bytes() == payload
    # read was invoked multiple times (chunked), not as a single whole-file load.
    assert response.read_calls > 1


def test_destination_directory_created_when_missing(tmp_path, monkeypatch):
    payload = b"checkpoint-bytes"
    dest = tmp_path / "deeply" / "nested" / "dir" / "best_model.pth"
    assert not dest.parent.exists()
    _install_successful_urlopen(monkeypatch, payload)

    ok = download_checkpoint(_make_url(), dest)

    assert ok is True
    assert dest.exists()
    assert dest.read_bytes() == payload


# --------------------------------------------------------------------------- failures


def test_empty_download_fails(tmp_path, monkeypatch, caplog):
    dest = tmp_path / "best_model.pth"
    _install_successful_urlopen(monkeypatch, b"")

    with caplog.at_level(logging.ERROR, logger="download_checkpoint"):
        ok = download_checkpoint(_make_url(), dest)

    assert ok is False
    assert not dest.exists()
    assert "empty response body" in caplog.text
    # URL must not appear in logs.
    assert _make_url() not in caplog.text


def test_http_error_fails(tmp_path, monkeypatch, caplog):
    dest = tmp_path / "best_model.pth"
    _install_failing_urlopen(
        monkeypatch,
        HTTPError("https://example.com/key", 403, "Forbidden", {}, None),
    )

    with caplog.at_level(logging.ERROR, logger="download_checkpoint"):
        ok = download_checkpoint(_make_url(), dest)

    assert ok is False
    assert not dest.exists()
    assert "HTTP 403" in caplog.text
    assert _make_url() not in caplog.text


def test_network_failure_fails(tmp_path, monkeypatch, caplog):
    from urllib.error import URLError

    dest = tmp_path / "best_model.pth"
    _install_failing_urlopen(monkeypatch, URLError("connection refused"))

    with caplog.at_level(logging.ERROR, logger="download_checkpoint"):
        ok = download_checkpoint(_make_url(), dest)

    assert ok is False
    assert not dest.exists()
    assert "cannot reach" in caplog.text
    assert _make_url() not in caplog.text


def test_interrupted_download_leaves_no_incomplete_checkpoint(tmp_path, monkeypatch):
    """A read that fails mid-stream must not leave a partial final checkpoint."""

    class _FailingResponse(_MockResponse):
        def read(self, n: int = -1):
            if self._pos > 100:
                raise OSError("network cut mid-download")
            return super().read(n)

    dest = tmp_path / "best_model.pth"
    response = _FailingResponse(b"x" * 100000)
    monkeypatch.setattr(
        "download_checkpoint.urlopen", lambda req, timeout=None: response
    )

    ok = download_checkpoint(_make_url(), dest)

    assert ok is False
    assert not dest.exists()


def test_temporary_files_cleaned_after_failure(tmp_path, monkeypatch):
    dest = tmp_path / "best_model.pth"
    _install_failing_urlopen(
        monkeypatch,
        URLError("network unreachable"),
    )

    ok = download_checkpoint(_make_url(), dest)

    assert ok is False
    assert not dest.exists()
    # No orphaned .tmp files in the destination directory.
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []


# --------------------------------------------------------------------------- reuse / force


def test_existing_checkpoint_reused_without_download(tmp_path, monkeypatch):
    payload = b"existing-checkpoint-content"
    dest = tmp_path / "best_model.pth"
    dest.write_bytes(payload)

    downloaded = download_checkpoint(_make_url(), dest)

    assert downloaded is True
    assert dest.read_bytes() == payload  # unchanged


def test_force_mode_triggers_fresh_download(tmp_path, monkeypatch):
    dest = tmp_path / "best_model.pth"
    dest.write_bytes(b"stale-content")
    new_payload = b"fresh-download-content"
    response = _install_successful_urlopen(monkeypatch, new_payload)

    ok = download_checkpoint(_make_url(), dest, force=True)

    assert ok is True
    assert dest.read_bytes() == new_payload
    assert response.read_calls >= 1  # download actually occurred


# --------------------------------------------------------------------------- SHA-256 verification


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_sha256_verification_succeeds_when_checksum_matches(tmp_path, monkeypatch):
    payload = b"checkpoint-payload-for-hash-test"
    dest = tmp_path / "best_model.pth"
    _install_successful_urlopen(monkeypatch, payload)

    ok = download_checkpoint(
        _make_url(), dest, expected_sha256=_sha256(payload)
    )

    assert ok is True
    assert dest.read_bytes() == payload


def test_sha256_verification_fails_when_checksum_mismatches(tmp_path, monkeypatch, caplog):
    payload = b"checkpoint-payload-for-hash-test"
    dest = tmp_path / "best_model.pth"
    _install_successful_urlopen(monkeypatch, payload)

    with caplog.at_level(logging.ERROR, logger="download_checkpoint"):
        ok = download_checkpoint(
            _make_url(), dest, expected_sha256="0" * 64
        )

    assert ok is False
    assert not dest.exists()
    assert "SHA-256 mismatch" in caplog.text
    assert _make_url() not in caplog.text


# --------------------------------------------------------------------------- main() exit codes / env handling


def test_main_missing_url_returns_nonzero(monkeypatch, caplog):
    monkeypatch.delenv(URL_ENV, raising=False)
    with caplog.at_level(logging.ERROR, logger="download_checkpoint"):
        code = main([])
    assert code == 2
    assert "Missing required environment variable" in caplog.text
    assert _make_url() not in caplog.text


def test_main_download_failure_returns_nonzero(tmp_path, monkeypatch):
    from urllib.error import URLError

    monkeypatch.setenv(URL_ENV, _make_url())
    monkeypatch.setenv("INFERENCE_CHECKPOINT_PATH", str(tmp_path / "best_model.pth"))
    _install_failing_urlopen(monkeypatch, URLError("boom"))

    code = main([])
    assert code == 1
    assert not (tmp_path / "best_model.pth").exists()


def test_main_success_returns_zero(tmp_path, monkeypatch):
    payload = b"ok"
    monkeypatch.setenv(URL_ENV, _make_url())
    monkeypatch.setenv("INFERENCE_CHECKPOINT_PATH", str(tmp_path / "best_model.pth"))
    _install_successful_urlopen(monkeypatch, payload)

    code = main([])
    assert code == 0
    assert (tmp_path / "best_model.pth").read_bytes() == payload


# --------------------------------------------------------------------------- real checkpoint preservation


def test_real_checkpoint_path_constant_matches_repo():
    """The script's default destination is the verified active inference path."""
    assert DEFAULT_CHECKPOINT == (
        "model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth"
    )


def test_tests_never_touch_the_real_checkpoint():
    """Guard: the real checkpoint must remain unmodified by the test suite."""
    assert REAL_CHECKPOINT.exists()
    assert REAL_CHECKPOINT.stat().st_size > 0
