# ruff: noqa: F821 - builder DSL names are injected by BuilderRunner.
import argparse
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

__PACKAGE_NAME__ = "sysroot_musl_full"
__PACKAGE_VERSION__ = GCC_VERSION

TARGETS = (
    "aarch64-unknown-linux-musl",
    "armv7-unknown-linux-musleabihf",
    "loongarch64-unknown-linux-musl",
    "mips64el-unknown-linux-musl",
    "powerpc64le-unknown-linux-musl",
    "riscv64-unknown-linux-musl",
    "s390x-ibm-linux-musl",
    "x86_64-unknown-linux-musl",
)

TARGET_SHORT_NAMES = {
    "aarch64-unknown-linux-musl": "aarch64-linux-musl",
    "armv7-unknown-linux-musleabihf": "armv7-linux-musl",
    "loongarch64-unknown-linux-musl": "loongarch64-linux-musl",
    "mips64el-unknown-linux-musl": "mips64el-linux-musl",
    "powerpc64le-unknown-linux-musl": "powerpc64le-linux-musl",
    "riscv64-unknown-linux-musl": "riscv64-linux-musl",
    "s390x-ibm-linux-musl": "s390x-linux-musl",
    "x86_64-unknown-linux-musl": "x86_64-linux-musl",
}

QEMU_COMMANDS = {
    "aarch64-unknown-linux-musl": "qemu-aarch64",
    "armv7-unknown-linux-musleabihf": "qemu-arm",
    "loongarch64-unknown-linux-musl": "qemu-loongarch64",
    "mips64el-unknown-linux-musl": "qemu-mips64el",
    "powerpc64le-unknown-linux-musl": "qemu-ppc64le",
    "riscv64-unknown-linux-musl": "qemu-riscv64",
    "s390x-ibm-linux-musl": "qemu-s390x",
    "x86_64-unknown-linux-musl": "qemu-x86_64",
}

RUNTIME_LIBRARY_PATH = "/lib64:/usr/lib64:/lib:/usr/lib"

PACKAGE_DIR = Path(__file__).resolve().parent
SAMPLE_SOURCE_DIR = PACKAGE_DIR / "samples"
TOOLCHAIN_FILE = SAMPLE_SOURCE_DIR / "toolchain.cmake"
BUNDLE_DIR_NAME = f"{__PACKAGE_NAME__}-gcc{GCC_VERSION}"
DEST_DIR = builder.output_dir / BUNDLE_DIR_NAME
VERIFY_BUILD_DIR = builder.build_dir / f"{__PACKAGE_NAME__}-verify"
VERIFY_OUTPUT_DIR = builder.output_dir / f"{__PACKAGE_NAME__}-verify"

gcc_musl_full = prebuild(
    name="gcc",
    version=GCC_VERSION,
    filename_fmt="{{name}}-{{version}}-{{arch}}-linux-musl.tar.xz",
    url_fmt=(
        "https://github.com/zarraxx/crosstool-ng/releases/download/"
        "gcc-musl-{{version}}/{{filename}}"
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
        raise FileNotFoundError(
            f"GCC/musl prebuilt directories are incomplete:\n{paths}"
        )

    print(f"GCC/musl version: {GCC_VERSION}")
    print(f"Host architecture: {HOST_ARCH}")
    print(f"GCC/musl archive: {gcc_musl_full.filename}")


def build() -> None:
    if DEST_DIR.exists():
        shutil.rmtree(DEST_DIR)
    (DEST_DIR / "lib" / "gcc").mkdir(parents=True, exist_ok=True)

    for triple in TARGETS:
        origin_root = builder.prebuild_dir / f"{triple}-gcc{GCC_VERSION}"
        source_prefix = origin_root / triple
        (DEST_DIR / triple).mkdir(parents=True, exist_ok=True)

        for subdir in ("include", "lib", "lib64", "lib32", "sysroot"):
            source_path = source_prefix / subdir
            if source_path.exists():
                _copy_tree(source_path, DEST_DIR / triple / subdir)

        gcc_runtime = origin_root / "lib" / "gcc" / triple
        if not gcc_runtime.is_dir():
            raise FileNotFoundError(f"GCC runtime does not exist: {gcc_runtime}")
        _copy_tree(gcc_runtime, DEST_DIR / "lib" / "gcc" / triple)


def verify() -> None:
    args = _parse_verify_args()
    targets = args.target or list(TARGETS)

    if not SAMPLE_SOURCE_DIR.is_dir() or not TOOLCHAIN_FILE.is_file():
        raise FileNotFoundError(
            f"Verification samples are incomplete: {SAMPLE_SOURCE_DIR}"
        )

    for path in (VERIFY_BUILD_DIR, VERIFY_OUTPUT_DIR):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)

    for triple in targets:
        _verify_target(triple)


def package() -> None:
    archive = builder.output_dir / f"{BUNDLE_DIR_NAME}.tar.xz"
    Shell.tar("caf", archive, "-C", builder.output_dir, BUNDLE_DIR_NAME)
    print(f"Created {archive}")


def _parse_verify_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=f"{Path(__file__).name} [verify options]",
        description="Build and run C/C++ samples with Clang and each musl sysroot",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=TARGETS,
        help="verify only this target; repeat to select multiple targets",
    )
    return parser.parse_args(__sys_argv__)


def _verify_target(triple: str) -> None:
    short_name = TARGET_SHORT_NAMES[triple]
    target_sysroot = DEST_DIR / triple / "sysroot"
    target_build_dir = VERIFY_BUILD_DIR / triple
    if not target_sysroot.is_dir():
        raise FileNotFoundError(f"Target sysroot does not exist: {target_sysroot}")

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
        raise RuntimeError(f"Verification outputs are missing:\n{paths}")

    expected = f"hello {short_name}"
    for executable in outputs:
        actual = _run_output(triple, executable, target_sysroot)
        if actual != expected:
            raise RuntimeError(
                f"{executable} output mismatch: expected={expected!r}, actual={actual!r}"
            )
        print(f"Verified {executable}: {actual}")


def _run_output(triple: str, executable: Path, target_sysroot: Path) -> str:
    completed = subprocess.run(
        [
            QEMU_COMMANDS[triple],
            "-L",
            str(target_sysroot),
            "-E",
            f"LD_LIBRARY_PATH={RUNTIME_LIBRARY_PATH}",
            str(executable),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source}")
    shutil.copytree(source, destination, symlinks=True, dirs_exist_ok=True)
