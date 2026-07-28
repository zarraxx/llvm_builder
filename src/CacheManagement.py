from __future__ import annotations

import hashlib
import inspect
import os
import re
import tempfile
import threading
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from urllib.parse import SplitResult, unquote, urlsplit, urlunsplit

from python_shell import Shell


class URLCache:
    """把 HTTP(S) 资源下载到本地，并按 URL 复用已下载的文件。

    自动生成的文件名包含 URL 摘要，因此不同域名或查询参数下的同名文件
    不会互相覆盖。写入使用临时文件和原子替换，下载失败时不会留下一个
    看似有效的不完整缓存。
    """

    def __init__(
        self,
        root_path: str | os.PathLike[str],
        *,
        connect_timeout: float = 30.0,
        follow_redirects: bool = True,
        retries: int = 3,
    ) -> None:
        if connect_timeout <= 0:
            raise ValueError("connect_timeout must be greater than zero")
        if retries < 0:
            raise ValueError("retries cannot be negative")

        self.root_path = Path(root_path).expanduser().resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)
        if not self.root_path.is_dir():
            raise NotADirectoryError(self.root_path)

        self.connect_timeout = connect_timeout
        self.follow_redirects = follow_redirects
        self.retries = retries
        self._locks: dict[Path, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def path_for(
        self,
        url: str,
        filename: str | os.PathLike[str] | None = None,
    ) -> Path:
        """返回 URL 对应的缓存路径，但不访问网络。"""
        normalized_url, parsed = self._normalize_url(url)
        if filename is None:
            raw_name = PurePosixPath(unquote(parsed.path)).name or "download"
            safe_name = re.sub(
                r"[^\w.+-]+", "_", raw_name, flags=re.ASCII
            ).strip("._")
            safe_name = (safe_name or "download")[:180]
            digest = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()[:16]
            filename = f"{digest}-{safe_name}"

        return self.root_path / self._validate_filename(filename)

    def contains(
        self,
        url: str,
        filename: str | os.PathLike[str] | None = None,
    ) -> bool:
        """缓存中存在对应的普通文件时返回 ``True``。"""
        return self._is_cache_file(self.path_for(url, filename))

    def fetch(
        self,
        url: str,
        filename: str | os.PathLike[str] | None = None,
        *,
        force: bool = False,
        headers: Mapping[str, str] | None = None,
    ) -> Path:
        """返回本地缓存路径；缓存未命中时先下载资源。

        ``force=True`` 会重新下载。刷新失败时，原有的有效缓存仍会保留。
        同一个实例内针对同一路径的并发请求只会执行一次下载。
        """
        normalized_url, _ = self._normalize_url(url)
        target = self.path_for(normalized_url, filename)
        lock = self._lock_for(target)

        with lock:
            if not force and self._is_cache_file(target):
                return target
            self._ensure_target_is_safe(target)
            self._download(normalized_url, target, headers=headers)
            return target

    def __call__(
        self,
        url: str,
        filename: str | os.PathLike[str] | None = None,
        *,
        force: bool = False,
        headers: Mapping[str, str] | None = None,
    ) -> Path:
        """调用缓存对象，等同于 :meth:`fetch`."""
        return self.fetch(
            url,
            filename,
            force=force,
            headers=headers,
        )

    def remove(
        self,
        url: str,
        filename: str | os.PathLike[str] | None = None,
    ) -> bool:
        """删除一项缓存；没有对应文件时返回 ``False``。"""
        target = self.path_for(url, filename)
        with self._lock_for(target):
            if not target.exists() and not target.is_symlink():
                return False
            if target.is_dir() and not target.is_symlink():
                raise IsADirectoryError(target)
            target.unlink()
            return True

    @staticmethod
    def _normalize_url(url: str) -> tuple[str, SplitResult]:
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url must be a non-empty string")

        parsed = urlsplit(url.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute HTTP(S) URL")

        normalized = urlunsplit(
            (parsed.scheme.lower(), parsed.netloc, parsed.path, parsed.query, "")
        )
        return normalized, urlsplit(normalized)

    @staticmethod
    def _validate_filename(filename: str | os.PathLike[str]) -> str:
        value = os.fspath(filename)
        if not isinstance(value, str):
            raise TypeError("filename must be a string or a string path")
        if (
            not value
            or value in {".", ".."}
            or "/" in value
            or "\\" in value
            or Path(value).is_absolute()
            or "\x00" in value
            or len(os.fsencode(value)) > 200
        ):
            raise ValueError(
                "filename must be a single, non-empty file name of at most 200 bytes"
            )
        return value

    @staticmethod
    def _is_cache_file(path: Path) -> bool:
        return path.is_file() and not path.is_symlink()

    @staticmethod
    def _ensure_target_is_safe(path: Path) -> None:
        if path.is_symlink():
            raise FileExistsError(f"cache target is a symbolic link: {path}")
        if path.exists() and not path.is_file():
            raise FileExistsError(f"cache target is not a regular file: {path}")

    def _lock_for(self, path: Path) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(path, threading.Lock())

    def _download(
        self,
        url: str,
        target: Path,
        *,
        headers: Mapping[str, str] | None,
    ) -> None:
        temporary: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                dir=self.root_path,
                prefix=f".{target.name}.",
                suffix=".part",
                delete=False,
            ) as output:
                temporary = Path(output.name)

            arguments = [
                "--fail",
                "--show-error",
                "--connect-timeout",
                str(self.connect_timeout),
                "--retry",
                str(self.retries),
                "--retry-all-errors",
                "--output",
                str(temporary),
            ]
            if self.follow_redirects:
                arguments.append("--location")
            for name, value in (headers or {}).items():
                arguments.extend(("--header", f"{name}: {value}"))
            arguments.append(url)

            # python-shell 默认使用 PIPE；显式传 None 才会继承终端并显示
            # curl 的进度、平均速度、剩余时间和当前速度。
            Shell.curl(*arguments, stdout=None, stderr=None)

            os.replace(temporary, target)
        except BaseException:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise


class CacheManagement(URLCache):
    """兼容草稿中的旧类名；新代码建议使用 :class:`URLCache`."""


def cache_builder(
    source_file: str | os.PathLike[str] | None = None,
    *,
    cache_dir: str | os.PathLike[str] | None = None,
    connect_timeout: float = 30.0,
    follow_redirects: bool = True,
    retries: int = 3,
) -> URLCache:
    """创建属于调用脚本的可调用缓存对象。

    默认以调用 ``cache_builder()`` 的 Python 文件为基准，将缓存放在
    ``Path(__file__).resolve().parents[1] / ".cache" / "downloads"``。
    在交互环境或需要明确指定基准文件时可传入 ``source_file=__file__``；
    也可以用 ``cache_dir`` 完全覆盖默认目录。
    """
    if cache_dir is None:
        if source_file is None:
            frame = inspect.currentframe()
            try:
                caller = frame.f_back if frame is not None else None
                source_file = caller.f_globals.get("__file__") if caller else None
            finally:
                del frame

        if source_file is None:
            raise RuntimeError(
                "cannot determine caller file; pass source_file=__file__ "
                "or provide cache_dir"
            )

        source_path = Path(source_file).resolve()
        try:
            project_root = source_path.parents[1]
        except IndexError as error:
            raise ValueError(
                f"source_file has no project parent directory: {source_path}"
            ) from error
        cache_dir = project_root / ".cache" / "downloads"

    return URLCache(
        cache_dir,
        connect_timeout=connect_timeout,
        follow_redirects=follow_redirects,
        retries=retries,
    )
