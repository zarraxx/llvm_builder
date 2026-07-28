from pathlib import Path

import pytest

import CacheManagement as cache_module
from CacheManagement import CacheManagement, URLCache


def install_fake_curl(monkeypatch, content: bytes = b"archive"):
    calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def fake_curl(*args: str, **kwargs: object):
        calls.append((args, kwargs))
        output = Path(args[args.index("--output") + 1])
        output.write_bytes(content)

    monkeypatch.setattr(cache_module.Shell, "curl", fake_curl)
    return calls


def test_fetch_downloads_with_curl_once_and_returns_a_path(
    monkeypatch,
    tmp_path: Path,
):
    calls = install_fake_curl(monkeypatch)
    cache = URLCache(tmp_path / "cache", connect_timeout=12, retries=2)

    first = cache.fetch("https://example.test/releases/llvm.tar.xz?v=1#section")
    second = cache.fetch("https://example.test/releases/llvm.tar.xz?v=1")

    assert first == second
    assert isinstance(first, Path)
    assert first.name.endswith("-llvm.tar.xz")
    assert first.read_bytes() == b"archive"
    assert len(calls) == 1
    arguments, options = calls[0]
    assert "--location" in arguments
    assert arguments[arguments.index("--connect-timeout") + 1] == "12"
    assert arguments[arguments.index("--retry") + 1] == "2"
    assert arguments[-1] == "https://example.test/releases/llvm.tar.xz?v=1"
    assert options == {"stdout": None, "stderr": None}
    assert cache.contains("https://example.test/releases/llvm.tar.xz?v=1")


def test_url_identity_avoids_filename_collisions(tmp_path: Path):
    cache = URLCache(tmp_path)

    first = cache.path_for("https://a.example/file.tar.xz?target=a")
    second = cache.path_for("https://b.example/file.tar.xz?target=a")
    third = cache.path_for("https://a.example/file.tar.xz?target=b")

    assert len({first, second, third}) == 3
    assert all(path.parent == tmp_path.resolve() for path in (first, second, third))


def test_explicit_filename_headers_and_remove(monkeypatch, tmp_path: Path):
    calls = install_fake_curl(monkeypatch, b"data")
    cache = CacheManagement(tmp_path)
    path = cache.fetch(
        "https://example.test/resource",
        "llvm-source.tar.xz",
        headers={"x-token": "secret"},
    )

    arguments, _ = calls[0]
    header_index = arguments.index("--header")
    assert arguments[header_index + 1] == "x-token: secret"
    assert path == tmp_path.resolve() / "llvm-source.tar.xz"
    assert cache.remove("https://example.test/resource", "llvm-source.tar.xz")
    assert not path.exists()
    assert not cache.remove("https://example.test/resource", "llvm-source.tar.xz")


def test_failed_refresh_keeps_old_cache_and_removes_partial_file(
    monkeypatch,
    tmp_path: Path,
):
    should_fail = False

    def fake_curl(*args: str, **kwargs: object):
        output = Path(args[args.index("--output") + 1])
        output.write_bytes(b"partial" if should_fail else b"old")
        if should_fail:
            raise RuntimeError("curl failed")

    monkeypatch.setattr(cache_module.Shell, "curl", fake_curl)
    cache = URLCache(tmp_path)
    path = cache.fetch("https://example.test/tool.zip")
    should_fail = True

    with pytest.raises(RuntimeError, match="curl failed"):
        cache.fetch("https://example.test/tool.zip", force=True)

    assert path.read_bytes() == b"old"
    assert list(tmp_path.glob(".*.part")) == []


@pytest.mark.parametrize(
    ("url", "filename"),
    [
        ("relative/path", None),
        ("ftp://example.test/file", None),
        ("https://example.test/file", "../outside"),
        ("https://example.test/file", "nested/file"),
        ("https://example.test/file", "nested\\file"),
        ("https://example.test/file", "x" * 201),
    ],
)
def test_rejects_invalid_urls_and_filenames(
    tmp_path: Path,
    url: str,
    filename: str | None,
):
    cache = URLCache(tmp_path)

    with pytest.raises(ValueError):
        cache.path_for(url, filename)


@pytest.mark.parametrize(
    "options",
    [
        {"connect_timeout": 0},
        {"retries": -1},
    ],
)
def test_rejects_invalid_curl_options(tmp_path: Path, options: dict[str, object]):
    with pytest.raises(ValueError):
        URLCache(tmp_path, **options)
