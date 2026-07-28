import os
from python_shell import Shell
from os import PathLike
from pathlib import Path
from typing import List

from CacheManagement import cache_builder

class Dependency(object):
    def __init__(self, filename: str, url: str, d_type: str = "source", extract_dir:str = None):
        self.filename = filename
        self.url = url
        self.type = d_type
        self.extract_dir = extract_dir


class PackageBuilder(object):
    def __init__(self, workspace:PathLike ):
        self.workspace = Path(workspace).resolve()
        self.dependencies = []
        self.cache_dir = self.workspace / ".cache"
        self.build_dir = self.workspace / ".build"
        self.output_dir = self.workspace / "dist"
        self.source_dir = self.workspace / ".source"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.source_dir.mkdir(parents=True, exist_ok=True)

        self._cache = cache_builder(cache_dir=self.cache_dir )

    def add_source_dependance(self, filename:str, url:str, extract_dir:str = None) -> None:
        self.dependencies.append(Dependency(filename=filename, url=url, d_type="source",extract_dir=extract_dir))

    def add_tool_dependance(self, filename:str, url:str, extract_dir:str = None) -> None:
        self.dependencies.append(Dependency(filename=filename, url=url, d_type="tool",extract_dir=extract_dir))

    def extract_dependencies(self) -> None:
        for dependency in self.dependencies:
            archive_path = self._cache(dependency.url, dependency.filename)

            EXTRACT_BASE_DIR = self.source_dir
            if dependency.type == "tool":
                EXTRACT_BASE_DIR = self.build_dir

            EXTRACT_FINAL_DIR = None
            if dependency.extract_dir:
                EXTRACT_FINAL_DIR = EXTRACT_BASE_DIR / dependency.extract_dir

            if (EXTRACT_FINAL_DIR is None) or (not EXTRACT_FINAL_DIR.exists()):
                Shell.tar("-xvf", archive_path, "-C", EXTRACT_BASE_DIR,stdout=None, stderr=None)

    def cmake_configure(self, source_dir:str, build_dir:str, output_dir:str, cmake_args:List[str]) -> None:
        _src_dir = self.source_dir / source_dir
        _build_dir = self.build_dir / build_dir
        _output_dir = self.output_dir / output_dir
        _build_dir.mkdir(parents=True, exist_ok=True)
        _output_dir.mkdir(parents=True, exist_ok=True)

        configure_cmake_args = [
             "-S",
            str(_src_dir),
            "-B",
            str(_build_dir),
            "-G",
            "Ninja",
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DCMAKE_INSTALL_PREFIX={_output_dir}",
            ]

        if cmake_args:
            configure_cmake_args.extend(cmake_args)

        Shell.cmake(
        *configure_cmake_args,
        stdout=None,
        stderr=None,
        )

    def cmake_build(self,  build_dir:str, cmake_args:List[str]) -> None:
        _build_dir = self.build_dir / build_dir

        build_cmake_args = ["--build", str(_build_dir),"--parallel"]
        if cmake_args:
            build_cmake_args.extend(cmake_args)
        Shell.cmake(
        *build_cmake_args,
        stdout=None,
        stderr=None,
        )

    def cmake_install(self, build_dir:str, cmake_args:List[str]) -> None:
        _build_dir = self.build_dir / build_dir

        install_cmake_args = ["--install", str(_build_dir)]

        if cmake_args:
            install_cmake_args.extend(cmake_args)

        Shell.cmake(
        *install_cmake_args,
        stdout=None,
        stderr=None,
        )


class PackageBuilderWithPreparedClang(PackageBuilder):
    def __init__(self, workspace:PathLike , llvm_version:str = "22.1.8"):
        super().__init__(workspace=workspace)
        self.llvm_version = llvm_version
        self.llvm_major_version = llvm_version.split(".")[0]
        extract_dir_name = f"LLVM-{self.llvm_version}-Linux-X64"
        self.toolchain_dir = self.build_dir / extract_dir_name
        self.clang = self.toolchain_dir / "bin" / "clang"
        self.clangxx = self.toolchain_dir / "bin" / "clang++"
        self.ld = self.toolchain_dir / "bin" / "ld.lld"
        self.lldb = self.toolchain_dir / "bin" / "lldb"
        self.llvm_as = self.toolchain_dir / "bin" / "llvm-as"
        self.ar = self.toolchain_dir / "bin" / "llvm-ar"
        self.ranlib = self.toolchain_dir / "bin" / "llvm-ranlib"
        self.nm = self.toolchain_dir / "bin" / "llvm-nm"


    def prepare_clang(self):
        LLVM_PREBUILD_ARCHIVE = f"LLVM-{self.llvm_version}-Linux-X64.tar.xz"

        LLVM_PREBUILD_URL = (
        "https://github.com/llvm/llvm-project/releases/download/"
        f"llvmorg-{self.llvm_version}/{LLVM_PREBUILD_ARCHIVE}"
        )

        if not os.path.exists(self.toolchain_dir):
            archive_path = self._cache(LLVM_PREBUILD_URL, LLVM_PREBUILD_ARCHIVE)
            Shell.tar("-xvf", archive_path, "-C", self.build_dir,stdout=None, stderr=None)

if __name__ == "__main__":

    workspace = Path(__file__).resolve().parents[1]
    llvm_version = "22.1.8"
    wasi_libc_version = "32"

    LLVM_PROJECT_ARCHIVE = f"llvm-project-{llvm_version}.src.tar.xz"
    LLVM_PROJECT_URL = (
    "https://github.com/llvm/llvm-project/releases/download/"
    f"llvmorg-{llvm_version}/{LLVM_PROJECT_ARCHIVE}"
    )

    LLVM_PREBUILD_ARCHIVE = f"LLVM-{llvm_version}-Linux-X64.tar.xz"

    LLVM_PREBUILD_URL = (
    "https://github.com/llvm/llvm-project/releases/download/"
    f"llvmorg-{llvm_version}/{LLVM_PREBUILD_ARCHIVE}"
    )

    builder = PackageBuilder(workspace=workspace)

    builder.add_source_dependance(filename=LLVM_PROJECT_ARCHIVE, url=LLVM_PROJECT_URL,extract_dir=f"llvm-project-{llvm_version}.src")
    builder.add_tool_dependance(filename=LLVM_PREBUILD_ARCHIVE, url=LLVM_PREBUILD_URL, extract_dir=f"LLVM-{llvm_version}-Linux-X64")

    builder.extract_dependencies()
