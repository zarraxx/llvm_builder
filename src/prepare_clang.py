

from CacheManagement import cache_builder

DEFAULT_LLVM_VERSION = "22.1.8"
cache = cache_builder()


def prepare_clang_path(llvm_version: str) -> None:
    LLVM_VERSION = llvm_version or DEFAULT_LLVM_VERSION
    LLVM_PREBUILD_ARCHIVE = f"LLVM-{LLVM_VERSION}-Linux-X64.tar.xz"

    LLVM_PREBUILD_URL = (
    "https://github.com/llvm/llvm-project/releases/download/"
    f"llvmorg-{LLVM_VERSION}/{LLVM_PREBUILD_ARCHIVE}"
    )

    prebuild_archive = cache(LLVM_PREBUILD_URL, LLVM_PREBUILD_ARCHIVE)

    return  prebuild_archive


def clang_src_path(llvm_version: str) -> str:
    LLVM_VERSION = llvm_version or DEFAULT_LLVM_VERSION
    LLVM_PROJECT_ARCHIVE = f"llvm-project-{LLVM_VERSION}.src.tar.xz"

    LLVM_PROJECT_URL = (
    "https://github.com/llvm/llvm-project/releases/download/"
    f"llvmorg-{LLVM_VERSION}/{LLVM_PROJECT_ARCHIVE}"
    )
    project_archive = cache(LLVM_PROJECT_URL, LLVM_PROJECT_ARCHIVE)
    return project_archive
