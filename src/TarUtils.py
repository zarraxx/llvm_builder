import tarfile
from os import PathLike
from pathlib import Path


def list_first_level(archive_path: PathLike):
    with tarfile.open(archive_path, "r:*") as tar_archive:
        first_level = set()

        for member in tar_archive.getmembers():
            # Path 会将 "./"、"."、"./."等归档根目录项规范化为无组件路径。
            # 根目录项不属于任何一级目录，应直接跳过。
            parts = Path(member.name).parts
            if parts:
                first_level.add(parts[0])

        return sorted(first_level)
