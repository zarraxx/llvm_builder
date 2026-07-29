# ruff: noqa: F821 - builder DSL names are injected by BuilderRunner.
import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    builder: Any
    Shell: Any
    __sys_argv__: list[str]

    def env(key: str, default_value: Any = None) -> Any: ...

    def prebuild(**kwargs: Any) -> Any: ...


GCC_VERSION = str(env("GCC_VERSION", "15.2.0"))
HOST_ARCH = str(env("HOST_ARCH", "x86_64"))

__PACKAGE_NAME__ = "sysroot_full"
__PACKAGE_VERSION__ = GCC_VERSION

MINGW_TRIPLE = "x86_64-w64-mingw32"
MINGW_GCC_RUNTIME_FILES = (
    "crtfastmath.o",
    "libgcc.a",
    "libgcc_eh.a",
    "libgcov.a",
)

TARGETS = (
    "aarch64-unknown-linux-gnu",
    "armv7-unknown-linux-gnueabihf",
    "loongarch64-unknown-linux-gnu",
    "mips64el-unknown-linux-gnu",
    "powerpc64le-unknown-linux-gnu",
    "s390x-ibm-linux-gnu",
    "x86_64-unknown-linux-gnu",
    MINGW_TRIPLE,
)

TARGET_SHORT_NAMES = {
    "aarch64-unknown-linux-gnu": "aarch64-linux",
    "armv7-unknown-linux-gnueabihf": "armv7-linux",
    "loongarch64-unknown-linux-gnu": "loongarch64-linux",
    "mips64el-unknown-linux-gnu": "mips64el-linux",
    "powerpc64le-unknown-linux-gnu": "powerpc64le-linux",
    "s390x-ibm-linux-gnu": "s390x-linux",
    "x86_64-unknown-linux-gnu": "x86_64-linux",
    MINGW_TRIPLE: "x86_64-mingw32",
}

QEMU_COMMANDS = {
    "aarch64-unknown-linux-gnu": "qemu-aarch64",
    "armv7-unknown-linux-gnueabihf": "qemu-arm",
    "loongarch64-unknown-linux-gnu": "qemu-loongarch64",
    "mips64el-unknown-linux-gnu": "qemu-mips64el",
    "powerpc64le-unknown-linux-gnu": "qemu-ppc64le",
    "s390x-ibm-linux-gnu": "qemu-s390x",
    "x86_64-unknown-linux-gnu": "qemu-x86_64",
}

PACKAGE_DIR = Path(__file__).resolve().parent
SAMPLE_SOURCE_DIR = PACKAGE_DIR / "samples"
TOOLCHAIN_FILE = SAMPLE_SOURCE_DIR / "toolchain.cmake"
DEST_DIR = builder.output_dir / f"{__PACKAGE_NAME__}-{__PACKAGE_VERSION__}"
VERIFY_BUILD_DIR = builder.build_dir / f"{__PACKAGE_NAME__}-verify"
VERIFY_OUTPUT_DIR = builder.output_dir / f"{__PACKAGE_NAME__}-verify"

gcc_full = prebuild(
    name="gcc",
    version=GCC_VERSION,
    filename_fmt="{{name}}-{{version}}-{{arch}}-linux-gnu.tar.xz",
    url_fmt=(
        "https://github.com/zarraxx/crosstool-ng/releases/download/"
        "{{name}}-{{version}}/{{filename}}"
    ),
    arch=HOST_ARCH,
)


def configure() -> None:
    missing = [
        builder.prebuild_dir / f"{triple}-gcc{GCC_VERSION}"
        for triple in TARGETS
        if not (builder.prebuild_dir / f"{triple}-gcc{GCC_VERSION}").is_dir()
    ]
    if missing:
        paths = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"GCC 预编译目录不完整:\n{paths}")

    print(f"GCC version: {GCC_VERSION}")
    print(f"Host architecture: {HOST_ARCH}")
    print(f"GCC archive: {gcc_full.filename}")


def build() -> None:
    if DEST_DIR.exists():
        shutil.rmtree(DEST_DIR)
    (DEST_DIR / "lib" / "gcc").mkdir(parents=True, exist_ok=True)

    for triple in TARGETS:
        origin_root = builder.prebuild_dir / f"{triple}-gcc{GCC_VERSION}"
        (DEST_DIR / triple).mkdir(parents=True, exist_ok=True)

        if triple == MINGW_TRIPLE:
            _build_mingw_sysroot(origin_root, triple)
            continue

        source_prefix = origin_root / triple
        for subdir in ("include", "lib", "lib64", "lib32", "sysroot"):
            source_path = source_prefix / subdir
            if source_path.exists():
                _copy_tree(source_path, DEST_DIR / triple / subdir)

        gcc_runtime = origin_root / "lib" / "gcc" / triple
        if not gcc_runtime.is_dir():
            raise FileNotFoundError(f"GCC runtime 不存在: {gcc_runtime}")
        _copy_tree(gcc_runtime, DEST_DIR / "lib" / "gcc" / triple)


def verify() -> None:
    args = _parse_verify_args()
    targets = args.target or list(TARGETS)

    if not SAMPLE_SOURCE_DIR.is_dir() or not TOOLCHAIN_FILE.is_file():
        raise FileNotFoundError(f"验证样例不完整: {SAMPLE_SOURCE_DIR}")

    for path in (VERIFY_BUILD_DIR, VERIFY_OUTPUT_DIR):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)

    for triple in targets:
        _verify_target(triple)


def package() -> None:
    archive = builder.output_dir / f"{__PACKAGE_NAME__}-gcc{GCC_VERSION}.tar.xz"
    Shell.tar("caf", archive, "-C", DEST_DIR, ".")
    print(f"Created {archive}")


def _parse_verify_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=f"{Path(__file__).name} [verify options]",
        description="使用 Clang 和 sysroot 构建并运行各 target 的 C/C++ 样例",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=TARGETS,
        help="只验证指定 target；可以重复传入，默认验证全部",
    )
    return parser.parse_args(__sys_argv__)


def _verify_target(triple: str) -> None:
    short_name = TARGET_SHORT_NAMES[triple]
    target_sysroot = DEST_DIR / triple / "sysroot"
    target_build_dir = VERIFY_BUILD_DIR / triple

    if not target_sysroot.is_dir():
        raise FileNotFoundError(f"Target sysroot 不存在: {target_sysroot}")

    print(f"Configuring {triple} ({short_name})", flush=True)
    builder.cmake_configure(
        [
            f"-DCMAKE_TOOLCHAIN_FILE={TOOLCHAIN_FILE}",
            f"-DTARGET_TRIPLE={triple}",
            f"-DTARGET_SYSROOT={target_sysroot}",
            f"-DSYSROOT_BUNDLE={DEST_DIR}",
            f"-DSAMPLE_ARCH={short_name}",
            f"-DSAMPLE_OUTPUT_DIR={VERIFY_OUTPUT_DIR}",
            f"-DSAMPLE_C_COMPILER={builder.clang}",
            f"-DSAMPLE_CXX_COMPILER={builder.clangxx}",
        ],
        source_dir=SAMPLE_SOURCE_DIR,
        build_dir=target_build_dir,
        output_dir=VERIFY_OUTPUT_DIR,
    )
    builder.cmake_build([], build_dir=target_build_dir)

    outputs = (
        VERIFY_OUTPUT_DIR / f"main.{short_name}",
        VERIFY_OUTPUT_DIR / f"maincxx.{short_name}",
    )
    missing = [path for path in outputs if not path.is_file()]
    if missing:
        paths = "\n".join(f"  - {path}" for path in missing)
        raise RuntimeError(f"缺少验证产物:\n{paths}")

    expected = f"hello {short_name}"
    for executable in outputs:
        actual = _run_output(triple, executable, target_sysroot)
        if actual != expected:
            raise RuntimeError(
                f"{executable} 输出不匹配: expected={expected!r}, actual={actual!r}"
            )
        print(f"Verified {executable}: {actual}")


def _run_output(triple: str, executable: Path, target_sysroot: Path) -> str:
    run_env = None
    if triple == MINGW_TRIPLE:
        runtime_dirs = (
            target_sysroot / triple / "bin",
            target_sysroot / triple / "bin32",
        )
        windows_runtime_dirs = [
            subprocess.run(
                ["winepath", "-w", str(runtime_dir)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            for runtime_dir in runtime_dirs
        ]
        run_env = os.environ.copy()
        run_env.update(
            {
                "WINEDEBUG": "-all",
                "WINEPATH": ";".join(windows_runtime_dirs),
            }
        )
        command = ["wine", str(executable)]
    else:
        command = [
            QEMU_COMMANDS[triple],
            "-L",
            str(target_sysroot),
            "-E",
            "LD_LIBRARY_PATH=/lib:/lib64:/usr/lib:/usr/lib64",
            str(executable),
        ]

    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=run_env,
    )
    return completed.stdout.strip()


def _build_mingw_sysroot(origin_root: Path, triple: str) -> None:
    source_prefix = origin_root / triple
    source_sysroot = source_prefix / "sysroot"
    gcc_runtime = origin_root / "lib" / "gcc" / triple / GCC_VERSION

    destination_sysroot = DEST_DIR / triple / "sysroot"
    destination_prefix = destination_sysroot / triple
    destination_include = destination_prefix / "include"

    # Clang 的 MinGW driver 会查找 <sysroot>/<triple>/{include,lib}。
    _copy_tree(
        source_sysroot / "usr" / triple / "include",
        destination_include,
    )
    _copy_tree(
        source_prefix / "include" / "c++" / GCC_VERSION,
        destination_include / "c++",
    )

    for bin_dir in ("bin", "bin32"):
        source_bin = source_sysroot / "usr" / triple / bin_dir
        destination_bin = destination_prefix / bin_dir
        if source_bin.exists():
            _copy_tree(source_bin, destination_bin)
        else:
            destination_bin.mkdir(parents=True, exist_ok=True)

    for lib_dir, bin_dir in (("lib", "bin"), ("lib32", "bin32")):
        destination_lib = destination_prefix / lib_dir
        _copy_tree(source_sysroot / "usr" / triple / lib_dir, destination_lib)
        _copy_tree(source_sysroot / lib_dir, destination_lib)

        gcc_lib_dir = gcc_runtime if lib_dir == "lib" else gcc_runtime / "32"
        _copy_mingw_gcc_runtime(gcc_lib_dir, destination_lib)
        _move_mingw_dlls(destination_lib, destination_prefix / bin_dir)


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"待复制目录不存在: {source}")
    shutil.copytree(source, destination, symlinks=True, dirs_exist_ok=True)


def _copy_mingw_gcc_runtime(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for filename in MINGW_GCC_RUNTIME_FILES:
        runtime_file = source / filename
        if runtime_file.exists():
            shutil.copy2(runtime_file, destination / filename)


def _move_mingw_dlls(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    dll_files = [
        path
        for path in source.rglob("*")
        if path.is_file() and path.suffix.lower() == ".dll"
    ]

    for dll_file in dll_files:
        relative_path = dll_file.relative_to(source)
        destination_file = destination / relative_path
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        if destination_file.exists():
            destination_file.unlink()
        shutil.move(dll_file, destination_file)
