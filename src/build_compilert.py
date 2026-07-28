from python_shell import Shell
from pathlib import Path
from os import PathLike
from prepare_clang import prepare_clang_path, clang_src_path
from sysroot_creator import triple_list as sysroot_triple_list


from PackageBuilder import PackageBuilder

WASI_TRIPLES = ["wasm32-wasip1", "wasm32-wasip2", "wasm32-wasip1-threads"]
triple_list = sysroot_triple_list + WASI_TRIPLES


class BuildConfig:
    def __init__(self, llvm_version: str , host_triple: str,toolchain_dir: PathLike,llvm_src_path: PathLike, sysroot_base_dir: PathLike):
        self.llvm_version = llvm_version or "22.1.8"
        self.host_triple = host_triple
        self.toolchain_dir = Path(toolchain_dir).resolve()
        self.llvm_src_path = Path(llvm_src_path).resolve()
        self.sysroot_base_dir = Path(sysroot_base_dir).resolve()
        self.project_dir = Path(__file__).resolve().parents[1]


def build_compiler_rt_builtins(
    build_config: BuildConfig,
    build_dir: PathLike,
    output_dir: PathLike,
) -> None:
    host_triple = build_config.host_triple
    toolchain_dir = build_config.toolchain_dir
    llvm_src_path = build_config.llvm_src_path
    sysroot_base_dir = build_config.sysroot_base_dir
    build_dir = Path(build_dir).resolve()
    output_dir = Path(output_dir).resolve()

    toolchain_bin_dir = toolchain_dir / "bin"
    builtins_src_dir = llvm_src_path / "compiler-rt" / "lib" / "builtins"
    llvm_cmake_dir = toolchain_dir / "lib" / "cmake" / "llvm"
    clang_resource_dir = (
        output_dir / "lib" / "clang" / build_config.llvm_version.split(".")[0]
    )

    tools = {
        "CMAKE_C_COMPILER": toolchain_bin_dir / "clang",
        "CMAKE_CXX_COMPILER": toolchain_bin_dir / "clang++",
        "CMAKE_ASM_COMPILER": toolchain_bin_dir / "clang",
        "CMAKE_AR": toolchain_bin_dir / "llvm-ar",
        "CMAKE_RANLIB": toolchain_bin_dir / "llvm-ranlib",
        "CMAKE_NM": toolchain_bin_dir / "llvm-nm",
    }
    missing_paths = [builtins_src_dir, llvm_cmake_dir, *tools.values()]
    missing_paths = [path for path in missing_paths if not path.exists()]
    if missing_paths:
        missing = "\n".join(f"  - {path}" for path in missing_paths)
        raise FileNotFoundError(f"compiler-rt 构建所需文件不存在:\n{missing}")

    cmake_args = [
        "-S",
        str(builtins_src_dir),
        "-B",
        str(build_dir),
        "-G",
        "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={output_dir}",
        f"-DLLVM_CMAKE_DIR={llvm_cmake_dir}",
        "-DLLVM_ENABLE_PER_TARGET_RUNTIME_DIR=ON",
        f"-DCOMPILER_RT_INSTALL_PATH={clang_resource_dir}",
        f"-DCOMPILER_RT_INSTALL_LIBRARY_DIR={clang_resource_dir / 'lib'}",
        f"-DCMAKE_C_COMPILER_TARGET={host_triple}",
        f"-DCMAKE_CXX_COMPILER_TARGET={host_triple}",
        f"-DCMAKE_ASM_COMPILER_TARGET={host_triple}",
        "-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY",
        "-DCOMPILER_RT_DEFAULT_TARGET_ONLY=ON",
        "-DCOMPILER_RT_INCLUDE_TESTS=OFF",
        "-DCOMPILER_RT_ENABLE_WERROR=OFF",
    ]
    cmake_args.extend(f"-D{name}={path}" for name, path in tools.items())

    if host_triple in WASI_TRIPLES:
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
    else:
        sysroot = sysroot_base_dir / host_triple / "sysroot"
        if not sysroot.is_dir():
            raise FileNotFoundError(f"{host_triple} 的 sysroot 不存在: {sysroot}")

        system_name = "Windows" if host_triple.endswith("w64-mingw32") else "Linux"
        cmake_args.extend(
            [
                f"-DCMAKE_SYSTEM_NAME={system_name}",
                f"-DCMAKE_SYSROOT={sysroot}",
            ]
        )
        if system_name == "Linux":
            gcc_toolchain_flag = f"--gcc-toolchain={sysroot_base_dir}"
            cmake_args.extend(
                [
                    f"-DCMAKE_C_FLAGS={gcc_toolchain_flag}",
                    f"-DCMAKE_CXX_FLAGS={gcc_toolchain_flag}",
                    f"-DCMAKE_ASM_FLAGS={gcc_toolchain_flag}",
                ]
            )

    Shell.cmake(
        *cmake_args,
        stdout=None,
        stderr=None,
    )

    Shell.cmake(
        "--build",
        str(build_dir),
        "--target",
        "install-builtins",
        "--parallel",
        stdout=None,
        stderr=None,
    )


def build(llvm_version: str):
    prepare_clang = prepare_clang_path(llvm_version)
    clang_src = clang_src_path(llvm_version)

    SRC_DIR = Path(__file__).resolve().parents[1] / ".source"
    BUILD_DIR = Path(__file__).resolve().parents[1] / ".build"
    OUTPUT_DIR = Path(__file__).resolve().parents[1] / "dist"


    Shell.mkdir("-p", str(SRC_DIR), stdout=None, stderr=None)
    Shell.mkdir("-p", str(BUILD_DIR), stdout=None, stderr=None)
    Shell.mkdir("-p", str(OUTPUT_DIR), stdout=None, stderr=None)

    Shell.tar('xvf', prepare_clang, "-C", BUILD_DIR , stdout=None, stderr=None)
    Shell.tar('xvf', clang_src, "-C", SRC_DIR , stdout=None, stderr=None)

    LLVM_SRC_DIR = SRC_DIR / f"llvm-project-{llvm_version}.src"

    compiler_rt_build_dir = BUILD_DIR / "compiler-rt"
    compiler_rt_dist_dir = OUTPUT_DIR / "compiler-rt"
    Shell.mkdir("-p", str(compiler_rt_build_dir), stdout=None, stderr=None)
    Shell.mkdir("-p", str(compiler_rt_dist_dir), stdout=None, stderr=None)

    build_config = BuildConfig(
        llvm_version=llvm_version,
        host_triple="x86_64-linux-gnu",
        toolchain_dir=BUILD_DIR / f"LLVM-{llvm_version}-Linux-X64",
        llvm_src_path=LLVM_SRC_DIR,
        sysroot_base_dir=OUTPUT_DIR / "sysroot",
    )

    for  triple in triple_list:
        build_dir = compiler_rt_build_dir / triple
        output_dir = compiler_rt_dist_dir
        Shell.mkdir("-p", str(build_dir), stdout=None, stderr=None)
        Shell.mkdir("-p", str(output_dir), stdout=None, stderr=None)
        build_config.host_triple = triple
        build_compiler_rt_builtins(build_config=build_config, build_dir=build_dir, output_dir=output_dir)

if __name__ == "__main__":
    build(llvm_version="22.1.8")
