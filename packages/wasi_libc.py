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


WASI_VERSION = str(env("WASI_VERSION", "32"))
LLVM_VERSION = str(env("LLVM_VERSION", builder.llvm_version))

__PACKAGE_NAME__ = "wasi_libc"
__PACKAGE_VERSION__ = WASI_VERSION

TARGETS = (
    "wasm32-wasip1",
    "wasm32-wasip2",
    "wasm32-wasip1-threads",
)

BUILD_ROOT = builder.build_dir / f"wasi-libc-{WASI_VERSION}-llvm-{LLVM_VERSION}"
OUTPUT_ROOT = builder.output_dir / f"wasi-libc-{WASI_VERSION}-llvm-{LLVM_VERSION}"
COMPILER_RT_LIB_DIR = Path(
    env(
        "COMPILER_RT_LIB_DIR",
        builder.output_dir
        / "compiler-rt"
        / "lib"
        / "clang"
        / builder.llvm_major_version
        / "lib",
    )
).resolve()

wasi_libc = source(
    name="wasi-libc",
    version=WASI_VERSION,
    filename_fmt="wasi-sdk-{{version}}.tar.gz",
    url_fmt=("https://github.com/WebAssembly/wasi-libc/archive/refs/tags/{{filename}}"),
)


def configure() -> None:
    source_dir = _source_dir()

    for triple in _selected_targets():
        target_build_dir = BUILD_ROOT / triple
        target_output_dir = OUTPUT_ROOT / triple
        if target_build_dir.exists():
            shutil.rmtree(target_build_dir)
        target_build_dir.mkdir(parents=True, exist_ok=True)
        target_output_dir.mkdir(parents=True, exist_ok=True)

        builder.cmake_configure(
            _cmake_args(triple, source_dir),
            source_dir=source_dir,
            build_dir=target_build_dir,
            output_dir=target_output_dir,
        )


def build() -> None:
    for triple in _selected_targets():
        builder.cmake_build([], build_dir=BUILD_ROOT / triple)


def install() -> None:
    for triple in _selected_targets():
        builder.cmake_install([], build_dir=BUILD_ROOT / triple)


def _selected_targets() -> list[str]:
    parser = argparse.ArgumentParser(
        prog=f"{Path(__file__).name} [build options]",
        description="为 WASI targets 构建 wasi-libc",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=TARGETS,
        help="只构建指定 target；可以重复传入，默认构建全部",
    )
    args = parser.parse_args(__sys_argv__)
    return args.target or list(TARGETS)


def _source_dir() -> Path:
    for directory in wasi_libc.extract_dir:
        candidate = builder.source_dir / directory
        if (candidate / "CMakeLists.txt").is_file():
            return candidate

    raise FileNotFoundError(f"wasi-libc 源码不存在: {builder.source_dir}")


def _cmake_args(
    triple: str,
    source_dir: Path,
) -> list[str]:
    canonical_triple = triple.replace("wasm32-", "wasm32-unknown-", 1)
    builtins_lib = COMPILER_RT_LIB_DIR / canonical_triple / "libclang_rt.builtins.a"
    tools = {
        "CMAKE_C_COMPILER": builder.clang,
        "CMAKE_AR": builder.ar,
        "CMAKE_RANLIB": builder.ranlib,
        "CMAKE_NM": builder.nm,
    }

    required_paths = [source_dir / "CMakeLists.txt", builtins_lib, *tools.values()]
    missing_paths = [path for path in required_paths if not path.exists()]
    if missing_paths:
        missing = "\n".join(f"  - {path}" for path in missing_paths)
        raise FileNotFoundError(f"wasi-libc 构建所需文件不存在:\n{missing}")

    cmake_args = [
        f"-DCMAKE_C_COMPILER_TARGET={triple}",
        f"-DCMAKE_ASM_COMPILER_TARGET={triple}",
        "-DCMAKE_C_LINKER_DEPFILE_SUPPORTED=FALSE",
        f"-DTARGET_TRIPLE={triple}",
        "-DMALLOC=dlmalloc",
        f"-DBUILTINS_LIB={builtins_lib}",
        "-DSETJMP=ON",
        "-DBUILD_TESTS=OFF",
        "-DSIMD=OFF",
        "-DBUILD_SHARED=ON",
        "-DENABLE_WERROR=OFF",
    ]
    cmake_args.extend(f"-D{name}={path}" for name, path in tools.items())
    return cmake_args
