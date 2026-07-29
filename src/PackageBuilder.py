import os
from abc import ABC, abstractmethod
from os import PathLike
from pathlib import Path

from jinja2 import Template
from python_shell import Shell

from CacheManagement import cache_builder
from TarUtils import list_first_level

DEFAULT_LLVM_VERSION = "22.1.8"


class Dependency:
    def __init__(
        self,
        name: str,
        version: str,
        filename: str,
        url: str,
    ):
        self.name = name
        self.version = version
        self.filename = filename
        self.url = url
        self.extract_dir = []


class PackageBuilder(ABC):
    def __init__(self, workspace: PathLike):
        self.workspace = Path(workspace).resolve()
        self.source_dependencies = {}
        self.prebuild_dependencies = {}
        self.tool_dependencies = {}

        self.name = None
        self.version = "unknown"

        self.cache_dir = self.workspace / ".cache"
        self.build_dir = self.workspace / ".build"
        self.output_dir = self.workspace / "dist"
        self.source_dir = self.workspace / ".source"
        self.prebuild_dir = self.workspace / ".prebuild"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.prebuild_dir.mkdir(parents=True, exist_ok=True)

        self._cache = cache_builder(cache_dir=self.cache_dir)

    def _add_dependency(
        self,
        name: str,
        ver: str,
        filename_fmt: str,
        url_fmt: str,
        dep_type: str,
        custom_dict: dict | None = None,
    ) -> Dependency:
        dest_dict = self.source_dependencies
        if dep_type == "tool":
            dest_dict = self.tool_dependencies
        elif dep_type == "prebuild":
            dest_dict = self.prebuild_dependencies

        fmt_dict = {
            "name": name,
            "version": ver,
        }

        if custom_dict:
            fmt_dict.update(custom_dict)

        filename_template = Template(filename_fmt)
        url_template = Template(url_fmt)

        file_name = filename_template.render(**fmt_dict)

        fmt_dict["filename"] = file_name
        url = url_template.render(**fmt_dict)

        dependency = Dependency(name, ver, file_name, url)
        dest_dict[name] = dependency
        return dependency

    def _extract_dependencies(
        self,
        dep_type: str,
    ) -> None:
        dependence_dict = self.source_dependencies
        dest_dir = self.source_dir

        if dep_type == "tool":
            dependence_dict = self.tool_dependencies
            dest_dir = self.build_dir
        elif dep_type == "prebuild":
            dependence_dict = self.prebuild_dependencies
            dest_dir = self.prebuild_dir

        for dependency_key in dependence_dict:
            dependency = dependence_dict[dependency_key]
            archive_path = self._cache(dependency.url, dependency.filename)
            first_level = list_first_level(archive_path)
            if not first_level:
                raise ValueError(f"依赖归档为空：{archive_path}")

            dependency.extract_dir = first_level
            extracted_paths = [dest_dir / name for name in first_level]
            if all(path.exists() for path in extracted_paths):
                print(f"Detected dependency: {dependency.name} exists!")
                continue

            Shell.tar(
                "-xvf",
                archive_path,
                "-C",
                dest_dir,
                stdout=None,
                stderr=None,
            )

    @abstractmethod
    def prepare_builder(self) -> None:
        pass

    def add_source_dependence(
        self, name: str, version: str, filename_fmt: str, url_fmt: str, **kwargs
    ) -> Dependency:
        return self._add_dependency(
            name, version, filename_fmt, url_fmt, "source", kwargs
        )

    def add_tool_dependence(
        self, name: str, version: str, filename_fmt: str, url_fmt: str, **kwargs
    ) -> Dependency:
        return self._add_dependency(
            name, version, filename_fmt, url_fmt, "tool", kwargs
        )

    def add_prebuild_dependence(
        self, name: str, version: str, filename_fmt: str, url_fmt: str, **kwargs
    ) -> Dependency:
        return self._add_dependency(
            name, version, filename_fmt, url_fmt, "prebuild", kwargs
        )

    def extract_tools_dependencies(self) -> None:
        self._extract_dependencies("tool")

    def extract_prebuild_dependencies(self) -> None:
        self._extract_dependencies("prebuild")

    def extract_source_dependencies(self) -> None:
        self._extract_dependencies("source")

    def mk_build_dir(
        self, subdir_base_name: str | None = None, ensure_exist: bool = True
    ) -> Path:
        _sub_dir_name = subdir_base_name if subdir_base_name else self.name
        if _sub_dir_name is None:
            raise ValueError("package name 不能为空")
        p = self.build_dir / _sub_dir_name
        if ensure_exist:
            p.mkdir(parents=True, exist_ok=True)
        return p

    def mk_output_dir(
        self, subdir_base_name: str | None = None, ensure_exist: bool = True
    ) -> Path:
        _sub_dir_name = subdir_base_name if subdir_base_name else self.name
        if _sub_dir_name is None:
            raise ValueError("package name 不能为空")
        p = self.output_dir / _sub_dir_name
        if ensure_exist:
            p.mkdir(parents=True, exist_ok=True)
        return p

    def cmake_configure(
        self,
        cmake_args: list[str],
        source_dir: PathLike | None = None,
        build_dir: PathLike | None = None,
        output_dir: PathLike | None = None,
    ) -> None:

        _src_dir = source_dir

        if _src_dir is None and self.source_dependencies:
            dependency = next(iter(self.source_dependencies.values()))
            if not dependency.extract_dir:
                raise RuntimeError(f"依赖尚未解压：{dependency.name}")
            _src_dir = self.source_dir / dependency.extract_dir[0]

        if _src_dir is None:
            raise ValueError("cmake source_dir 不能为空")
        if self.name is None and (build_dir is None or output_dir is None):
            raise ValueError("package name 不能为空")

        _src_dir = Path(_src_dir).resolve()
        _build_dir = Path(build_dir or self.build_dir / self.name).resolve()
        _output_dir = Path(output_dir or self.output_dir / self.name).resolve()
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

    def cmake_build(
        self, cmake_args: list[str], build_dir: PathLike | None = None
    ) -> None:
        if self.name is None and build_dir is None:
            raise ValueError("package name 不能为空")
        _build_dir = Path(build_dir or self.build_dir / self.name).resolve()

        build_cmake_args = ["--build", str(_build_dir), "--parallel"]
        if cmake_args:
            build_cmake_args.extend(cmake_args)
        Shell.cmake(
            *build_cmake_args,
            stdout=None,
            stderr=None,
        )

    def cmake_install(
        self, cmake_args: list[str], build_dir: PathLike | None = None
    ) -> None:
        if self.name is None and build_dir is None:
            raise ValueError("package name 不能为空")
        _build_dir = Path(build_dir or self.build_dir / self.name).resolve()

        install_cmake_args = ["--install", str(_build_dir)]

        if cmake_args:
            install_cmake_args.extend(cmake_args)

        Shell.cmake(
            *install_cmake_args,
            stdout=None,
            stderr=None,
        )


class PackageBuilderWithPreparedClang(PackageBuilder):
    def __init__(self, workspace: PathLike, llvm_version: str | None = None) -> None:
        super().__init__(workspace=workspace)
        if llvm_version:
            self.llvm_version = llvm_version
        elif os.environ.get("LLVM_VERSION"):
            self.llvm_version = os.environ["LLVM_VERSION"]
        else:
            self.llvm_version = DEFAULT_LLVM_VERSION

        self.llvm_major_version = self.llvm_version.split(".")[0]
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

    def prepare_builder(self) -> None:
        LLVM_PREBUILD_ARCHIVE = f"LLVM-{self.llvm_version}-Linux-X64.tar.xz"

        LLVM_PREBUILD_URL = (
            "https://github.com/llvm/llvm-project/releases/download/"
            f"llvmorg-{self.llvm_version}/{LLVM_PREBUILD_ARCHIVE}"
        )

        if not os.path.exists(self.toolchain_dir):
            archive_path = self._cache(LLVM_PREBUILD_URL, LLVM_PREBUILD_ARCHIVE)
            Shell.tar(
                "-xvf", archive_path, "-C", self.build_dir, stdout=None, stderr=None
            )
