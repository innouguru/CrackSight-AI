"""Build-time downloader for the U-Net ResNet-34 inference checkpoint.

Downloads the trained checkpoint from a private Cloudflare R2 bucket using a
pre-signed URL supplied through the ``MODEL_CHECKPOINT_URL`` environment
variable. The checkpoint itself is never committed to Git and is fetched at
build time so the Render Web Service has the weights available when the
FastAPI backend starts.

Usage (Render build command)::

    MODEL_CHECKPOINT_URL="https://<account>.r2.cloudflarestorage.com/<bucket>/<key>?<sig>" \
    python scripts/download_checkpoint.py

Environment variables:
    MODEL_CHECKPOINT_URL    Required. Pre-signed R2 download URL. Never logged,
                            hardcoded, or committed. Expires and must be
                            refreshed whenever a future build needs a new download.
    MODEL_CHECKPOINT_SHA256 Optional. Expected SHA-256 digest of the checkpoint
                            file. When set, the download is verified against it
                            (computed in a streaming fashion) and the build
                            fails on mismatch.
    INFERENCE_CHECKPOINT_PATH Optional. Destination path. Defaults to the path
                            expected by the inference pipeline
                            (model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth).

Design:
    * Streams the download in 1 MiB chunks (urllib standard library only --
      the whole checkpoint is never loaded into memory).
    * Writes to a temporary file in the destination directory, then atomically
      renames it to the final path, so an incomplete file never becomes the
      checkpoint.
    * Verifies the transfer completed (nonempty body, Content-Length match when
      advertised) and optionally the SHA-256 digest.
    * Skips the download when a valid checkpoint already exists unless --force
      is given.
    * Returns a nonzero exit code on any failure and removes partial temp files.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

logger = logging.getLogger("download_checkpoint")

DEFAULT_CHECKPOINT = (
    "model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth"
)

URL_ENV = "MODEL_CHECKPOINT_URL"
SHA256_ENV = "MODEL_CHECKPOINT_SHA256"
DEST_ENV = "INFERENCE_CHECKPOINT_PATH"

CHUNK_SIZE = 1024 * 1024  # 1 MiB -- stream, never load the full checkpoint in memory.
DOWNLOAD_TIMEOUT_SECONDS = 60


def _safe_url_display(url: str) -> str:
    """Return a URL fragment safe for logs: scheme and host only.

    Strips credentials, path, query string (which may carry the R2 signature
    token), and fragment so secrets are never written to logs.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<unparseable url>"
    host = parts.hostname or parts.netloc
    if "@" in (parts.netloc or ""):
        host = host.split("@")[-1]
    if parts.port:
        host = f"{host}:{parts.port}"
    scheme = parts.scheme or "https"
    return f"{scheme}://{host}"


def download_checkpoint(
    url: str,
    dest: str | os.PathLike[str],
    expected_sha256: str | None = None,
    force: bool = False,
) -> bool:
    """Stream-download the checkpoint to ``dest``.

    Returns ``True`` on success, ``False`` on failure. On any failure the
    destination is left untouched and any partial temporary file is removed.
    """
    dest = Path(dest)
    dest_dir = dest.parent

    # Reuse a valid existing checkpoint unless the caller forces a refresh.
    if not force and dest.exists():
        if dest.stat().st_size > 0:
            logger.info(
                "Checkpoint already present at %s; skipping download.", dest
            )
            return True
        logger.warning("Existing checkpoint at %s is empty; re-downloading.", dest)

    dest_dir.mkdir(parents=True, exist_ok=True)

    hasher = hashlib.sha256() if expected_sha256 else None
    total = 0
    expected_len: int | None = None
    tmp_path: Path | None = None
    tmp_consumed = False

    def _cleanup_tmp() -> None:
        nonlocal tmp_consumed
        if tmp_consumed:
            return
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError as exc:  # pragma: no cover - best effort
                logger.warning(
                    "Failed to remove temporary file %s: %s", tmp_path, exc
                )
        tmp_consumed = True

    try:
        try:
            response = urlopen(Request(url), timeout=DOWNLOAD_TIMEOUT_SECONDS)
        except HTTPError as exc:
            _cleanup_tmp()
            logger.error(
                "Checkpoint download failed: HTTP %s from %s",
                exc.code,
                _safe_url_display(url),
            )
            return False
        except URLError as exc:
            _cleanup_tmp()
            logger.error(
                "Checkpoint download failed: cannot reach %s: %s",
                _safe_url_display(url),
                exc.reason,
            )
            return False
        except OSError as exc:
            _cleanup_tmp()
            logger.error("Checkpoint download failed: %s", exc)
            return False

        try:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                response.close()
                _cleanup_tmp()
                logger.error(
                    "Checkpoint download failed: HTTP %s from %s",
                    status,
                    _safe_url_display(url),
                )
                return False

            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    expected_len = int(content_length)
                except ValueError:
                    expected_len = None

            # Temporary file in the same directory so the final rename is
            # atomic (same filesystem) and a partial write can never become
            # the checkpoint. The mkstemp handle is released immediately so
            # the file can be closed and removed on Windows.
            tmp_fd, tmp_name = tempfile.mkstemp(
                prefix=dest.name + ".", suffix=".tmp", dir=str(dest_dir)
            )
            os.close(tmp_fd)
            tmp_path = Path(tmp_name)

            try:
                with open(tmp_path, "wb") as tmp_file:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        tmp_file.write(chunk)
                        total += len(chunk)
                        if hasher is not None:
                            hasher.update(chunk)
            finally:
                response.close()
        except Exception:
            _cleanup_tmp()
            raise

        # The transfer must have produced a nonempty file.
        if total == 0:
            _cleanup_tmp()
            logger.error(
                "Checkpoint download failed: empty response body from %s",
                _safe_url_display(url),
            )
            return False

        # Content-Length match when the server advertises it.
        if expected_len is not None and total != expected_len:
            _cleanup_tmp()
            logger.error(
                "Checkpoint download failed: incomplete transfer "
                "(%d of %d bytes) from %s",
                total,
                expected_len,
                _safe_url_display(url),
            )
            return False

        # Streaming SHA-256 integrity verification (file never loaded into memory).
        if hasher is not None:
            actual = hasher.hexdigest()
            if actual.lower() != expected_sha256.strip().lower():
                _cleanup_tmp()
                logger.error(
                    "Checkpoint download failed: SHA-256 mismatch for %s "
                    "(computed %s, expected digest did not match)",
                    dest,
                    actual,
                )
                return False
            logger.info("Checkpoint SHA-256 verified for %s.", dest)

        # Atomic promotion: temporary file -> final destination.
        os.replace(tmp_path, dest)
        tmp_consumed = True
        logger.info(
            "Checkpoint downloaded successfully to %s (%d bytes).", dest, total
        )
        return True
    except Exception as exc:  # any unexpected error -> fail closed, clean temp
        _cleanup_tmp()
        logger.error("Checkpoint download failed unexpectedly: %s", exc)
        return False


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Download the inference checkpoint from a pre-signed R2 URL at build time."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if a valid checkpoint already exists.",
    )
    parser.add_argument(
        "--checkpoint-path",
        default=None,
        help=(
            "Destination path (default: INFERENCE_CHECKPOINT_PATH env var, "
            "else the standard inference checkpoint path)."
        ),
    )
    args = parser.parse_args(argv)

    url = os.environ.get(URL_ENV, "").strip()
    if not url:
        logger.error(
            "Missing required environment variable %s: provide a pre-signed R2 "
            "download URL. Do not hardcode the URL; it expires and must be "
            "refreshed when a future build needs a new download.",
            URL_ENV,
        )
        return 2

    expected_sha256 = os.environ.get(SHA256_ENV, "").strip() or None
    dest = Path(
        args.checkpoint_path
        or os.environ.get(DEST_ENV, DEFAULT_CHECKPOINT)
    )

    ok = download_checkpoint(
        url, dest, expected_sha256=expected_sha256, force=args.force
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
