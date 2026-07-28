import os
from os import PathLike
from pathlib import Path

from CacheManagement import cache_builder
from prepare_clang import prepare_clang_path
from python_shell import Shell

WASI_TRIPLES = ["wasm32-wasip1", "wasm32-wasip2", "wasm32-wasip1-threads"]
cache = cache_builder()


class WASIBuildConfig(object):
    def __init__(
        self,
        triple: str,
        toolchain_dir: PathLike,
        src_path: PathLike,
        compiler_rt_base_dir: PathLike,
    ):
        self.triple = triple
        self.toolchain_dir = Path(toolchain_dir).resolve()
        self.src_path = Path(src_path).resolve()
        self.compiler_rt_base_dir = Path(compiler_rt_base_dir).resolve()
        self.project_dir = Path(__file__).resolve().parents[1]


def build_wasi_libc(
    config: WASIBuildConfig, build_dir: PathLike, output_dir: PathLike
) -> None:
    triple = config.triple
    toolchain_dir = config.toolchain_dir
    src_path = config.src_path
    compiler_rt_base_dir = config.compiler_rt_base_dir
    build_dir = Path(build_dir).resolve()
    output_dir = Path(output_dir).resolve()

    toolchain_bin_dir = toolchain_dir / "bin"
    canonical_triple = triple.replace("wasm32-", "wasm32-unknown-", 1)
    builtins_lib = (
        compiler_rt_base_dir / canonical_triple / "libclang_rt.builtins.a"
    )
    tools = {
        "CMAKE_C_COMPILER": toolchain_bin_dir / "clang",
        "CMAKE_AR": toolchain_bin_dir / "llvm-ar",
        "CMAKE_RANLIB": toolchain_bin_dir / "llvm-ranlib",
        "CMAKE_NM": toolchain_bin_dir / "llvm-nm",
    }

    required_paths = [src_path / "CMakeLists.txt", builtins_lib, *tools.values()]
    missing_paths = [path for path in required_paths if not path.exists()]
    if missing_paths:
        missing = "\n".join(f"  - {path}" for path in missing_paths)
        raise FileNotFoundError(f"wasi-libc 构建所需文件不存在:\n{missing}")

    cmake_args = [
        "-S",
        str(src_path),
        "-B",
        str(build_dir),
        "-G",
        "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={output_dir}",
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

    Shell.cmake(
        *cmake_args,
        stdout=None,
        stderr=None,
    )
    Shell.cmake(
        "--build",
        str(build_dir),
        "--parallel",
        stdout=None,
        stderr=None,
    )
    Shell.cmake(
        "--install",
        str(build_dir),
        stdout=None,
        stderr=None,
    )


# https://github.com/WebAssembly/wasi-libc/archive/refs/tags/wasi-sdk-32.tar.gz
def build(version="32", llvm_version="22.1.8") -> None:
    llvm_major_version = llvm_version.split(".")[0]
    wasi_sdk_archive = f"wasi-sdk-{version}.tar.gz"
    wasi_sdk_url = (
        "https://github.com/WebAssembly/wasi-libc/archive/refs/tags/"
        f"{wasi_sdk_archive}"
    )
    wasi_sdk_archive_path = cache(wasi_sdk_url, wasi_sdk_archive)

    prepare_clang = prepare_clang_path(llvm_version)

    SRC_DIR = Path(__file__).resolve().parents[1] / ".source"
    BUILD_DIR = Path(__file__).resolve().parents[1] / ".build"
    OUTPUT_DIR = Path(__file__).resolve().parents[1] / "dist"

    Shell.mkdir("-p", str(SRC_DIR), stdout=None, stderr=None)
    Shell.mkdir("-p", str(BUILD_DIR), stdout=None, stderr=None)
    Shell.mkdir("-p", str(OUTPUT_DIR), stdout=None, stderr=None)

    print(f"WASI SDK archive: {wasi_sdk_archive_path}")

    toolchain_dir = BUILD_DIR / f"LLVM-{llvm_version}-Linux-X64"
    src_dir = SRC_DIR / f"wasi-libc-wasi-sdk-{version}"
    compiler_rt_base_dir = (
        OUTPUT_DIR
        / "compiler-rt"
        / "lib"
        / "clang"
        / llvm_major_version
        / "lib"
    )

    if not os.path.exists(src_dir):
        Shell.tar(
            "-xvf",
            str(wasi_sdk_archive_path),
            "-C",
            str(SRC_DIR),
            stdout=None,
            stderr=None,
        )

    if not os.path.exists(toolchain_dir):
        Shell.tar(
            "xvf", prepare_clang, "-C", BUILD_DIR, stdout=None, stderr=None
        )

    build_config = WASIBuildConfig(
        triple=f"wasm32-wasip1",
        toolchain_dir=toolchain_dir,
        src_path=src_dir,
        compiler_rt_base_dir=compiler_rt_base_dir,
    )

    for triple in WASI_TRIPLES:
        build_dir = BUILD_DIR / f"wasi-libc-{version}-llvm-{llvm_version}" / triple
        output_dir = (
            OUTPUT_DIR / f"wasi-libc-{version}-llvm-{llvm_version}" / triple
        )
        Shell.mkdir("-p", str(build_dir), stdout=None, stderr=None)
        Shell.mkdir("-p", str(output_dir), stdout=None, stderr=None)
        build_config.triple = triple
        build_wasi_libc(
            config=build_config, build_dir=build_dir, output_dir=output_dir
        )


if __name__ == "__main__":
    build(version="32", llvm_version="22.1.8")
