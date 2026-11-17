from __future__ import annotations

import os
import threading
import types
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import certifi
import tinify
from tinify.client import Client
from tinify.errors import AccountError

# Connect / read timeouts (seconds). Read allows up to 5 minutes for large images.
CONNECT_TIMEOUT = 30
READ_TIMEOUT = 300

# Files at/above this size wait until smaller ones finish (concentrate bandwidth).
LARGE_FILE_BYTES = 5 * 1024 * 1024  # 5 MB

# Tinify is network I/O bound; small files can use high concurrency.
_MIN_WORKERS = 2
_MAX_WORKERS = 32
_LARGE_WORKERS = 1  # large files: one at a time so bandwidth isn't split

_thread_local = threading.local()


def _patch_client_session(client: Client) -> Client:
    """Use certifi CA bundle + request timeouts on this client session."""
    client.session.verify = certifi.where()
    original_request = client.session.request

    def request_with_timeout(method, url, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.setdefault("timeout", (CONNECT_TIMEOUT, READ_TIMEOUT))
        return original_request(method, url, **kwargs)

    client.session.request = request_with_timeout  # type: ignore[method-assign]
    return client


def _make_client(key: str, app_identifier: str | None = None, proxy: str | None = None) -> Client:
    return _patch_client_session(Client(key, app_identifier, proxy))


def _thread_local_get_client(self: Any) -> Client:
    """One Client+Session per worker thread (requests.Session is not thread-safe)."""
    if not self._key:
        raise AccountError("Provide an API key with tinify.key = ...")

    client = getattr(_thread_local, "client", None)
    stored_key = getattr(_thread_local, "key", None)
    if client is None or stored_key != self._key:
        client = _make_client(self._key, self._app_identifier, self._proxy)
        _thread_local.client = client
        _thread_local.key = self._key
    return client


# Replace tinify's shared client getter with a thread-local one.
tinify.get_client = types.MethodType(_thread_local_get_client, tinify)  # type: ignore[method-assign]


SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".avif",
    ".jxl",
    ".heic",
    ".heif",
}


@dataclass
class CompressResult:
    source: Path
    output: Path
    original_size: int
    compressed_size: int
    success: bool
    error: str = ""

    @property
    def saved_bytes(self) -> int:
        return max(0, self.original_size - self.compressed_size)

    @property
    def saved_percent(self) -> float:
        if self.original_size <= 0:
            return 0.0
        return (self.saved_bytes / self.original_size) * 100.0


ProgressCallback = Callable[[str], None]
StartCallback = Callable[[Path], None]
DoneCallback = Callable[[CompressResult], None]


def recommended_workers() -> int:
    """Pick concurrency from CPU count; network-bound so allow > CPU, cap at 32."""
    cpus = os.cpu_count() or 4
    return max(_MIN_WORKERS, min(_MAX_WORKERS, cpus * 4))


def is_supported_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def format_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


def set_api_key(api_key: str) -> None:
    tinify.key = api_key.strip()
    # Drop any cached thread-local clients so they pick up the new key.
    _thread_local.client = None
    _thread_local.key = None


def validate_api_key(api_key: str) -> tuple[bool, str, int | None]:
    """Validate key. Returns (ok, message, compression_count)."""
    key = api_key.strip()
    if not key:
        return False, "请先填写 API Key", None
    try:
        set_api_key(key)
        tinify.validate()
        count = tinify.compression_count
        return True, "API Key 有效", count
    except tinify.AccountError as exc:
        return False, f"账号错误: {exc.message}", None
    except tinify.ClientError as exc:
        return False, f"请求错误: {exc.message}", None
    except tinify.ServerError as exc:
        return False, f"服务端错误: {exc.message}", None
    except tinify.ConnectionError as exc:
        return False, f"网络连接失败: {exc.message}", None
    except Exception as exc:  # noqa: BLE001
        return False, f"校验失败: {exc}", None


def get_compression_count() -> int | None:
    try:
        return tinify.compression_count
    except Exception:  # noqa: BLE001
        return None


def resolve_output_path(
    source: Path,
    *,
    output_mode: str,
    suffix: str,
    output_dir: str,
) -> Path:
    if output_mode == "overwrite":
        return source
    if output_mode == "custom":
        target_dir = Path(output_dir) if output_dir else source.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / source.name
    safe_suffix = suffix or "_tinified"
    return source.with_name(f"{source.stem}{safe_suffix}{source.suffix}")


def compress_file(
    source: Path,
    *,
    output_mode: str = "suffix",
    suffix: str = "_tinified",
    output_dir: str = "",
) -> CompressResult:
    source = Path(source)
    original_size = source.stat().st_size
    output = resolve_output_path(
        source,
        output_mode=output_mode,
        suffix=suffix,
        output_dir=output_dir,
    )

    try:
        tinify.from_file(str(source)).to_file(str(output))
        compressed_size = output.stat().st_size
        return CompressResult(
            source=source,
            output=output,
            original_size=original_size,
            compressed_size=compressed_size,
            success=True,
        )
    except tinify.AccountError as exc:
        return CompressResult(
            source=source,
            output=output,
            original_size=original_size,
            compressed_size=original_size,
            success=False,
            error=f"账号错误: {exc.message}",
        )
    except tinify.ClientError as exc:
        return CompressResult(
            source=source,
            output=output,
            original_size=original_size,
            compressed_size=original_size,
            success=False,
            error=f"图片无效: {exc.message}",
        )
    except tinify.ServerError as exc:
        return CompressResult(
            source=source,
            output=output,
            original_size=original_size,
            compressed_size=original_size,
            success=False,
            error=f"服务端错误: {exc.message}",
        )
    except tinify.ConnectionError as exc:
        return CompressResult(
            source=source,
            output=output,
            original_size=original_size,
            compressed_size=original_size,
            success=False,
            error=f"网络错误: {exc.message}",
        )
    except Exception as exc:  # noqa: BLE001
        return CompressResult(
            source=source,
            output=output,
            original_size=original_size,
            compressed_size=original_size,
            success=False,
            error=str(exc),
        )


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _run_pool(
    indexed: list[tuple[int, Path]],
    *,
    workers: int,
    output_mode: str,
    suffix: str,
    output_dir: str,
    results: list[CompressResult | None],
    total: int,
    done_count: list[int],
    lock: threading.Lock,
    on_start: StartCallback | None,
    on_done: DoneCallback | None,
    on_progress: ProgressCallback | None,
    phase_label: str,
) -> None:
    if not indexed:
        return

    workers = max(1, min(workers, len(indexed)))

    def job(index: int, path: Path) -> tuple[int, CompressResult]:
        if on_start:
            on_start(path)
        result = compress_file(
            path,
            output_mode=output_mode,
            suffix=suffix,
            output_dir=output_dir,
        )
        return index, result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(job, index, path): index for index, path in indexed
        }
        for future in as_completed(futures):
            index, result = future.result()
            results[index] = result
            with lock:
                done_count[0] += 1
                current = done_count[0]
            if on_done:
                on_done(result)
            if on_progress:
                on_progress(
                    f"进度 {current}/{total} · {phase_label} · 并发 {workers}"
                )


def compress_many(
    paths: list[Path],
    *,
    output_mode: str = "suffix",
    suffix: str = "_tinified",
    output_dir: str = "",
    max_workers: int | None = None,
    on_start: StartCallback | None = None,
    on_done: DoneCallback | None = None,
    on_progress: ProgressCallback | None = None,
) -> list[CompressResult]:
    """Compress small images first (concurrent), then large ones (serial/low concurrency)."""
    if not paths:
        return []

    workers = max_workers or recommended_workers()
    total = len(paths)
    results: list[CompressResult | None] = [None] * total
    done_count = [0]
    lock = threading.Lock()

    small: list[tuple[int, Path]] = []
    large: list[tuple[int, Path]] = []
    for index, path in enumerate(paths):
        if _file_size(path) >= LARGE_FILE_BYTES:
            large.append((index, path))
        else:
            small.append((index, path))

    if small and large and on_progress:
        on_progress(
            f"先压缩 {len(small)} 张小图，再处理 {len(large)} 张大图（≥5MB）"
        )

    _run_pool(
        small,
        workers=max(1, min(workers, len(small) or 1)),
        output_mode=output_mode,
        suffix=suffix,
        output_dir=output_dir,
        results=results,
        total=total,
        done_count=done_count,
        lock=lock,
        on_start=on_start,
        on_done=on_done,
        on_progress=on_progress,
        phase_label="小图",
    )

    if large and on_progress:
        on_progress(f"小图已完成，开始集中带宽处理 {len(large)} 张大图…")

    _run_pool(
        large,
        workers=_LARGE_WORKERS,
        output_mode=output_mode,
        suffix=suffix,
        output_dir=output_dir,
        results=results,
        total=total,
        done_count=done_count,
        lock=lock,
        on_start=on_start,
        on_done=on_done,
        on_progress=on_progress,
        phase_label="大图",
    )

    return [r for r in results if r is not None]
