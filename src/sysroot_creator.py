import  os
import argparse
import shutil
from python_shell import Shell
from CacheManagement import cache_builder
from pathlib import Path, PurePosixPath

cache = cache_builder()

# GCC_VERSION = "15.2.0"
# ARCH = "x86_64"

DEFAULT_GCC_VERSION = "15.2.0"
DEFAULT_ARCH = "x86_64"

# GCC_ARCHIVE = f"gcc-{GCC_VERSION}-{ARCH}-linux-gnu.tar.xz"
# GCC_URL = f"https://github.com/zarraxx/crosstool-ng/releases/download/gcc-{GCC_VERSION}/{GCC_ARCHIVE}"

BUILD_DIR = Path(__file__).resolve().parents[1] / ".build" / "sysroot"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "dist"
DEST_DIR = OUTPUT_DIR / "sysroot"

MINGW_TRIPLE = "x86_64-w64-mingw32"
MINGW_GCC_RUNTIME_FILES = (
    "crtfastmath.o",
    "libgcc.a",
    "libgcc_eh.a",
    "libgcov.a",
)

triple_list = ['aarch64-unknown-linux-gnu',
               'armv7-unknown-linux-gnueabihf',
               'loongarch64-unknown-linux-gnu',
               'mips64el-unknown-linux-gnu',
               'powerpc64le-unknown-linux-gnu',
               's390x-ibm-linux-gnu',
               'x86_64-unknown-linux-gnu',
               MINGW_TRIPLE
               ]

triple_short_name = {
    'aarch64-unknown-linux-gnu': "aarch64-linux",
    'armv7-unknown-linux-gnueabihf': "armv7-linux",
    'loongarch64-unknown-linux-gnu': "loongarch64-linux",
    'mips64el-unknown-linux-gnu': "mips64el-linux",
    'powerpc64le-unknown-linux-gnu': "powerpc64le-linux",
    's390x-ibm-linux-gnu': "s390x-linux",
    'x86_64-unknown-linux-gnu': "x86_64-linux",
    MINGW_TRIPLE: "x86_64-mingw32"
}

def parse_args():
    parser = argparse.ArgumentParser(
        description="构建 GCC sysroot"
    )

    parser.add_argument(
        "-v",
        "--gcc-version",
        default=DEFAULT_GCC_VERSION,
        help=f"GCC 版本，默认：{DEFAULT_GCC_VERSION}",
    )

    parser.add_argument(
        "-a",
        "--arch",
        default=DEFAULT_ARCH,
        help=f"GCC 工具链宿主架构，默认：{DEFAULT_ARCH}",
    )

    return parser.parse_args()


def _copy_tree(source: Path, destination: Path):
    shutil.copytree(source, destination, symlinks=True, dirs_exist_ok=True)


def _copy_mingw_gcc_runtime(source: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    for filename in MINGW_GCC_RUNTIME_FILES:
        runtime_file = source / filename
        if runtime_file.exists():
            shutil.copy2(runtime_file, destination / filename)


def _build_mingw_sysroot(origin_root: Path, gcc_version: str, triple: str):
    source_prefix = origin_root / triple
    source_sysroot = source_prefix / "sysroot"
    gcc_runtime = origin_root / "lib" / "gcc" / triple / gcc_version

    destination_sysroot = DEST_DIR / triple / "sysroot"
    destination_prefix = destination_sysroot / triple
    destination_include = destination_prefix / "include"

    # Clang's MinGW driver searches <sysroot>/<triple>/{include,lib}.
    _copy_tree(
        source_sysroot / "usr" / triple / "include",
        destination_include,
    )
    _copy_tree(
        source_prefix / "include" / "c++" / gcc_version,
        destination_include / "c++",
    )

    for lib_dir in ("lib", "lib32"):
        destination_lib = destination_prefix / lib_dir
        _copy_tree(
            source_sysroot / "usr" / triple / lib_dir,
            destination_lib,
        )
        _copy_tree(source_sysroot / lib_dir, destination_lib)

        gcc_lib_dir = gcc_runtime if lib_dir == "lib" else gcc_runtime / "32"
        _copy_mingw_gcc_runtime(gcc_lib_dir, destination_lib)


def build(gcc_version: str, arch: str):
    gcc_archive = f"gcc-{gcc_version}-{arch}-linux-gnu.tar.xz"

    gcc_url = (
        "https://github.com/zarraxx/crosstool-ng/releases/download/"
        f"gcc-{gcc_version}/{gcc_archive}"
    )

    print(f"GCC version: {gcc_version}")
    print(f"Host architecture: {arch}")
    print(f"GCC URL: {gcc_url}")

    gcc_archive_path = cache(gcc_url, gcc_archive)
    print(f"GCC archive: {gcc_archive_path}")


    Shell.rm("-rf", DEST_DIR)

    Shell.rm("-rf", BUILD_DIR)
    Shell.mkdir("-p", str(BUILD_DIR), stdout=None, stderr=None)
    Shell.tar('xvf', gcc_archive_path, "-C", BUILD_DIR, stdout=None, stderr=None)

    Shell.mkdir("-p", str(DEST_DIR / "lib" / "gcc" ), stdout=None, stderr=None)

    for triple in triple_list:
        origin_root = BUILD_DIR / f"{triple}-gcc{gcc_version}"
        Shell.mkdir("-p", str(DEST_DIR / triple), stdout=None, stderr=None)
        if triple == MINGW_TRIPLE:
            _build_mingw_sysroot(origin_root, gcc_version, triple)
        else:
            sub_folders = [ 'include', 'lib', 'lib64', 'lib32', 'sysroot']
            for sub_folder in sub_folders:
                if os.path.exists(origin_root / triple/ sub_folder):
                    Shell.cp ("-ar" ,origin_root / triple / sub_folder, DEST_DIR / triple)
            Shell.cp("-ar", origin_root /'lib'/'gcc'/triple, DEST_DIR / "lib"/'gcc')

    Shell.tar('caf', OUTPUT_DIR / f"sysroot-gcc{gcc_version}-full.tar.xz", "-C", DEST_DIR, ".", stdout=None, stderr=None)


if __name__ == "__main__":
    args = parse_args()

    build(
        gcc_version=args.gcc_version,
        arch=args.arch,
    )
