# ruff: noqa: F821 - builder DSL names are injected by BuilderRunner.
import argparse
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    builder: Any
    Shell: Any
    __sys_argv__: list[str]

    def env(key: str, default_value: Any = None) -> Any: ...

    def source(**kwargs: Any) -> Any: ...


LLVM_VERSION = str(env("LLVM_VERSION", builder.llvm_version))
GCC_VERSION = str(env("GCC_VERSION", "15.2.0"))

__PACKAGE_NAME__ = "compiler_rt"
__PACKAGE_VERSION__ = LLVM_VERSION

SYSROOT_TARGETS = (
    "aarch64-unknown-linux-gnu",
    "armv7-unknown-linux-gnueabihf",
    "loongarch64-unknown-linux-gnu",
    "mips64el-unknown-linux-gnu",
    "powerpc64le-unknown-linux-gnu",
    "s390x-ibm-linux-gnu",
    "x86_64-unknown-linux-gnu",
    "x86_64-w64-mingw32",
)
WASI_TARGETS = (
    "wasm32-wasip1",
    "wasm32-wasip2",
    "wasm32-wasip1-threads",
)
TARGETS = SYSROOT_TARGETS + WASI_TARGETS

SYSROOT_DIR = Path(
    env(
        "SYSROOT_DIR",
        builder.output_dir / f"sysroot_full-{GCC_VERSION}",
    )
).resolve()
BUILD_ROOT = builder.build_dir / f"compiler-rt-{LLVM_VERSION}"
OUTPUT_DIR = builder.output_dir / "compiler-rt"

llvm_project = source(
    name="llvm-project",
    version=LLVM_VERSION,
    filename_fmt="{{name}}-{{version}}.src.tar.xz",
    url_fmt=(
        "https://github.com/llvm/llvm-project/releases/download/"
        "llvmorg-{{version}}/{{filename}}"
    ),
)


def configure() -> None:
    llvm_source_dir = _llvm_source_dir()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for triple in _selected_targets():
        target_build_dir = BUILD_ROOT / triple
        if target_build_dir.exists():
            shutil.rmtree(target_build_dir)
        target_build_dir.mkdir(parents=True, exist_ok=True)

        builder.cmake_configure(
            _cmake_args(triple, llvm_source_dir),
            source_dir=llvm_source_dir / "compiler-rt" / "lib" / "builtins",
            build_dir=target_build_dir,
            output_dir=OUTPUT_DIR,
        )


def build() -> None:
    for triple in _selected_targets():
        builder.cmake_build([], build_dir=BUILD_ROOT / triple)


def install() -> None:
    for triple in _selected_targets():
        builder.cmake_build(
            ["--target", "install-builtins"],
            build_dir=BUILD_ROOT / triple,
        )


def _selected_targets() -> list[str]:
    parser = argparse.ArgumentParser(
        prog=f"{Path(__file__).name} [build options]",
        description="为 sysroot 和 WASI targets 构建 compiler-rt builtins",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=TARGETS,
        help="只构建指定 target；可以重复传入，默认构建全部",
    )
    args = parser.parse_args(__sys_argv__)
    return args.target or list(TARGETS)


def _llvm_source_dir() -> Path:
    for directory in llvm_project.extract_dir:
        candidate = builder.source_dir / directory
        if (candidate / "compiler-rt" / "lib" / "builtins").is_dir():
            return candidate

    raise FileNotFoundError(f"LLVM compiler-rt 源码不存在: {builder.source_dir}")


def _cmake_args(
    triple: str,
    llvm_source_dir: Path,
) -> list[str]:
    builtins_source_dir = llvm_source_dir / "compiler-rt" / "lib" / "builtins"
    llvm_cmake_dir = builder.toolchain_dir / "lib" / "cmake" / "llvm"
    clang_resource_dir = OUTPUT_DIR / "lib" / "clang" / builder.llvm_major_version

    tools = {
        "CMAKE_C_COMPILER": builder.clang,
        "CMAKE_CXX_COMPILER": builder.clangxx,
        "CMAKE_ASM_COMPILER": builder.clang,
        "CMAKE_AR": builder.ar,
        "CMAKE_RANLIB": builder.ranlib,
        "CMAKE_NM": builder.nm,
    }
    required_paths = [builtins_source_dir, llvm_cmake_dir, *tools.values()]
    missing_paths = [path for path in required_paths if not path.exists()]
    if missing_paths:
        missing = "\n".join(f"  - {path}" for path in missing_paths)
        raise FileNotFoundError(f"compiler-rt 构建所需文件不存在:\n{missing}")

    cmake_args = [
        f"-DLLVM_CMAKE_DIR={llvm_cmake_dir}",
        "-DLLVM_ENABLE_PER_TARGET_RUNTIME_DIR=ON",
        f"-DCOMPILER_RT_INSTALL_PATH={clang_resource_dir}",
        f"-DCOMPILER_RT_INSTALL_LIBRARY_DIR={clang_resource_dir / 'lib'}",
        f"-DCMAKE_C_COMPILER_TARGET={triple}",
        f"-DCMAKE_CXX_COMPILER_TARGET={triple}",
        f"-DCMAKE_ASM_COMPILER_TARGET={triple}",
        "-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY",
        "-DCOMPILER_RT_DEFAULT_TARGET_ONLY=ON",
        "-DCOMPILER_RT_INCLUDE_TESTS=OFF",
        "-DCOMPILER_RT_ENABLE_WERROR=OFF",
    ]
    cmake_args.extend(f"-D{name}={path}" for name, path in tools.items())

    if triple in WASI_TARGETS:
        target_flags = "-ffreestanding -nostdlib"
        cmake_args.extend(
            [
                "-DCMAKE_SYSTEM_NAME=WASI",
                "-DCOMPILER_RT_BAREMETAL_BUILD=ON",
                "-DCOMPILER_RT_OS_DIR=wasi",
                f"-DCMAKE_C_FLAGS={target_flags}",
                f"-DCMAKE_CXX_FLAGS={target_flags}",
                f"-DCMAKE_ASM_FLAGS={target_flags}",
            ]
        )
        return cmake_args

    target_sysroot = SYSROOT_DIR / triple / "sysroot"
    if not target_sysroot.is_dir():
        raise FileNotFoundError(f"{triple} 的 sysroot 不存在: {target_sysroot}")

    system_name = "Windows" if triple.endswith("w64-mingw32") else "Linux"
    cmake_args.extend(
        [
            f"-DCMAKE_SYSTEM_NAME={system_name}",
            f"-DCMAKE_SYSROOT={target_sysroot}",
        ]
    )
    if system_name == "Linux":
        gcc_toolchain_flag = f"--gcc-toolchain={SYSROOT_DIR}"
        cmake_args.extend(
            [
                f"-DCMAKE_C_FLAGS={gcc_toolchain_flag}",
                f"-DCMAKE_CXX_FLAGS={gcc_toolchain_flag}",
                f"-DCMAKE_ASM_FLAGS={gcc_toolchain_flag}",
            ]
        )

    return cmake_args
