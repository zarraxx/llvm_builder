from pathlib import Path

import CacheManagement as cache_module
import sysroot_thin_creator
import sysroot_creator


def test_scripts_build_callable_local_cache_objects(monkeypatch, tmp_path: Path):
    expected = tmp_path / "llvm.tar.xz"
    calls = []

    def fake_fetch(
        url: str,
        filename: str,
        *,
        force: bool,
        headers: object,
    ) -> Path:
        assert not force
        assert headers is None
        calls.append((url, filename))
        return expected

    monkeypatch.setattr(sysroot_thin_creator.cache, "fetch", fake_fetch)

    result = sysroot_thin_creator.cache("https://example.test/llvm.tar.xz", "llvm.tar.xz")

    assert result == expected
    assert calls == [("https://example.test/llvm.tar.xz", "llvm.tar.xz")]
    assert callable(sysroot_thin_creator.cache)
    assert callable(sysroot_creator.cache)
    assert sysroot_thin_creator.cache is not sysroot_creator.cache
    expected_cache_dir = Path(__file__).resolve().parents[1] / ".cache" / "downloads"
    assert sysroot_thin_creator.cache.root_path == expected_cache_dir
    assert sysroot_creator.cache.root_path == expected_cache_dir


def test_cache_builder_can_use_explicit_source_file(tmp_path: Path):
    source_file = tmp_path / "project" / "src" / "build.py"

    cache = cache_module.cache_builder(source_file)

    assert callable(cache)
    assert cache.root_path == tmp_path / "project" / ".cache" / "downloads"


def test_cache_builder_can_override_cache_directory(tmp_path: Path):
    cache = cache_module.cache_builder(cache_dir=tmp_path / "custom-cache")

    assert cache.root_path == (tmp_path / "custom-cache").resolve()


def test_llvm_download_urls_match_archive_names():
    assert "$" not in sysroot_thin_creator.LLVM_PROJECT_URL
    assert "$" not in sysroot_thin_creator.LLVM_PREBUILD_URL
    assert sysroot_thin_creator.LLVM_PROJECT_URL.endswith(sysroot_thin_creator.LLVM_PROJECT_ARCHIVE)
    assert sysroot_thin_creator.LLVM_PREBUILD_URL.endswith(sysroot_thin_creator.LLVM_PREBUILD_ARCHIVE)
