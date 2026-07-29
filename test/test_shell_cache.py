from pathlib import Path

import CacheManagement as cache_module


def test_cache_builder_can_use_explicit_source_file(tmp_path: Path):
    source_file = tmp_path / "project" / "src" / "build.py"

    cache = cache_module.cache_builder(source_file)

    assert callable(cache)
    assert cache.root_path == tmp_path / "project" / ".cache" / "downloads"


def test_cache_builder_can_override_cache_directory(tmp_path: Path):
    cache = cache_module.cache_builder(cache_dir=tmp_path / "custom-cache")

    assert cache.root_path == (tmp_path / "custom-cache").resolve()
