from CacheManagement import cache_builder

cache = cache_builder()

LLVM_VERSION = "22.1.8"
LLVM_PROJECT_ARCHIVE = f"llvm-project-{LLVM_VERSION}.src.tar.xz"
LLVM_PREBUILD_ARCHIVE = f"LLVM-{LLVM_VERSION}-Linux-X64.tar.xz"
LLVM_PROJECT_URL = (
    "https://github.com/llvm/llvm-project/releases/download/"
    f"llvmorg-{LLVM_VERSION}/{LLVM_PROJECT_ARCHIVE}"
)
LLVM_PREBUILD_URL = (
    "https://github.com/llvm/llvm-project/releases/download/"
    f"llvmorg-{LLVM_VERSION}/{LLVM_PREBUILD_ARCHIVE}"
)

def mkdir(path: str):
    pass



def main() -> None:
    project_archive = cache(LLVM_PROJECT_URL, LLVM_PROJECT_ARCHIVE)
    prebuild_archive = cache(LLVM_PREBUILD_URL, LLVM_PREBUILD_ARCHIVE)

    print(f"LLVM source: {project_archive}")
    print(f"LLVM prebuilt: {prebuild_archive}")


if __name__ == "__main__":
    main()
