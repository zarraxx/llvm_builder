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
MUSL_GCC_VERSION = str(env("MUSL_GCC_VERSION", GCC_VERSION))

__PACKAGE_NAME__ = "sysroot_thin"
__PACKAGE_VERSION__ = GCC_VERSION
BUNDLE_DIR_NAME = f"{__PACKAGE_NAME__}-gcc{GCC_VERSION}"

# Only the primary ABI of each Linux triple is retained. Multilib variants from
# the full GCC bundle are deliberately omitted.
GLIBC_TARGET_LAYOUTS = {
    "aarch64-unknown-linux-gnu": ("lib", "usr/lib"),
    "armv7-unknown-linux-gnueabihf": ("lib", "usr/lib"),
    "loongarch64-unknown-linux-gnu": ("lib64", "usr/lib64"),
    "mips64el-unknown-linux-gnu": ("lib64", "usr/lib64"),
    "powerpc64le-unknown-linux-gnu": ("lib", "usr/lib"),
    "riscv64-unknown-linux-gnu": ("lib64/lp64d", "usr/lib64/lp64d"),
    "s390x-ibm-linux-gnu": ("lib64", "usr/lib64"),
    "x86_64-unknown-linux-gnu": ("lib64", "usr/lib64"),
}
MUSL_TARGET_LAYOUTS = {
    "aarch64-unknown-linux-musl": ("lib", "usr/lib"),
    "armv7-unknown-linux-musleabihf": ("lib", "usr/lib"),
    "loongarch64-unknown-linux-musl": ("lib", "usr/lib"),
    "mips64el-unknown-linux-musl": ("lib", "usr/lib"),
    "powerpc64le-unknown-linux-musl": ("lib", "usr/lib"),
    "riscv64-unknown-linux-musl": ("lib", "usr/lib"),
    "s390x-ibm-linux-musl": ("lib", "usr/lib"),
    "x86_64-unknown-linux-musl": ("lib64", "usr/lib64"),
}
TARGET_LAYOUTS = {**GLIBC_TARGET_LAYOUTS, **MUSL_TARGET_LAYOUTS}
MUSL_TARGETS = tuple(MUSL_TARGET_LAYOUTS)
MINGW_TRIPLE = "x86_64-w64-mingw32"
TARGETS = (*TARGET_LAYOUTS, MINGW_TRIPLE)

DYNAMIC_LINKERS = {
    "aarch64-unknown-linux-gnu": "/lib/ld-linux-aarch64.so.1",
    "armv7-unknown-linux-gnueabihf": "/lib/ld-linux-armhf.so.3",
    "loongarch64-unknown-linux-gnu": "/lib64/ld-linux-loongarch-lp64d.so.1",
    "mips64el-unknown-linux-gnu": "/lib64/ld.so.1",
    "powerpc64le-unknown-linux-gnu": "/lib64/ld64.so.2",
    "riscv64-unknown-linux-gnu": "/lib/ld-linux-riscv64-lp64d.so.1",
    "s390x-ibm-linux-gnu": "/lib/ld64.so.1",
    "x86_64-unknown-linux-gnu": "/lib64/ld-linux-x86-64.so.2",
    "aarch64-unknown-linux-musl": "/lib/ld-musl-aarch64.so.1",
    "armv7-unknown-linux-musleabihf": "/lib/ld-musl-armhf.so.1",
    "loongarch64-unknown-linux-musl": "/lib/ld-musl-loongarch64.so.1",
    "mips64el-unknown-linux-musl": "/lib/ld-musl-mips64el.so.1",
    "powerpc64le-unknown-linux-musl": "/lib/ld-musl-powerpc64le.so.1",
    "riscv64-unknown-linux-musl": "/lib/ld-musl-riscv64.so.1",
    "s390x-ibm-linux-musl": "/lib/ld-musl-s390x.so.1",
    "x86_64-unknown-linux-musl": "/lib/ld-musl-x86_64.so.1",
}

QEMU_COMMANDS = {
    "aarch64-unknown-linux-gnu": "qemu-aarch64",
    "armv7-unknown-linux-gnueabihf": "qemu-arm",
    "loongarch64-unknown-linux-gnu": "qemu-loongarch64",
    "mips64el-unknown-linux-gnu": "qemu-mips64el",
    "powerpc64le-unknown-linux-gnu": "qemu-ppc64le",
    "riscv64-unknown-linux-gnu": "qemu-riscv64",
    "s390x-ibm-linux-gnu": "qemu-s390x",
    "x86_64-unknown-linux-gnu": "qemu-x86_64",
    "aarch64-unknown-linux-musl": "qemu-aarch64",
    "armv7-unknown-linux-musleabihf": "qemu-arm",
    "loongarch64-unknown-linux-musl": "qemu-loongarch64",
    "mips64el-unknown-linux-musl": "qemu-mips64el",
    "powerpc64le-unknown-linux-musl": "qemu-ppc64le",
    "riscv64-unknown-linux-musl": "qemu-riscv64",
    "s390x-ibm-linux-musl": "qemu-s390x",
    "x86_64-unknown-linux-musl": "qemu-x86_64",
}

# These aliases are part of the ABI paths embedded in glibc linker scripts.
SYSROOT_ALIASES = {
    "aarch64-unknown-linux-gnu": (("lib64", "lib"), ("usr/lib64", "lib")),
    "powerpc64le-unknown-linux-gnu": (("lib64", "lib"), ("usr/lib64", "lib")),
}

# Loaders listed here live outside their target's primary runtime directory.
EXTRA_ENTRIES = {
    "riscv64-unknown-linux-gnu": ("lib/ld-linux-riscv64-lp64d.so.1",),
    "s390x-ibm-linux-gnu": ("lib/ld64.so.1",),
}

GLIBC_RUNTIME_FAMILIES = (
    "libc",
    "libm",
    "libpthread",
    "libdl",
    "librt",
    "libresolv",
    "libnss_files",
    "libnss_dns",
)
GLIBC_LINK_LIBRARIES = (
    "libc.so",
    "libm.so",
    "libpthread.so",
    "libdl.so",
    "librt.so",
    "libresolv.so",
)
GLIBC_START_FILES = ("crt1.o", "Scrt1.o", "crti.o", "crtn.o")
GLIBC_NONSHARED_ARCHIVES = ("libc_nonshared.a", "libpthread_nonshared.a")

MUSL_START_FILES = ("crt1.o", "Scrt1.o", "rcrt1.o", "crti.o", "crtn.o")
MUSL_STATIC_LIBRARIES = (
    "libc.a",
    "libm.a",
    "libpthread.a",
    "libdl.a",
    "librt.a",
    "libresolv.a",
    "libcrypt.a",
    "libutil.a",
    "libxnet.a",
)
MUSL_LINK_FILES = ("libc.so", *MUSL_START_FILES, *MUSL_STATIC_LIBRARIES)

# MinGW keeps the complete 64-bit WinSDK/CRT surface. Unlike Linux, its .a
# files are mostly WinAPI import libraries and cannot be reduced to a small
# generic whitelist. Only GCC and C++ runtimes are removed below.
MINGW_REQUIRED_LIBRARIES = (
    "libmingw32.a",
    "libmsvcrt.a",
    "libkernel32.a",
    "libgdi32.a",
)
MINGW_CRT_OBJECTS = ("crt2.o", "dllcrt2.o")

FORBIDDEN_PREFIXES = (
    "libasan",
    "libatomic",
    "libgcc",
    "libgomp",
    "libgcov",
    "libhwasan",
    "libitm",
    "liblsan",
    "libquadmath",
    "libssp",
    "libstdc++",
    "libsupc++",
    "libtsan",
    "libubsan",
    "libvtv",
    "crtbegin",
    "crtend",
    "crtfastmath",
)

SOURCE_ROOT = Path(
    env(
        "SYSROOT_FULL_DIR",
        builder.prebuild_dir / f"sysroot_full-gcc{GCC_VERSION}",
    )
).resolve()
MUSL_SOURCE_ROOT = Path(
    env(
        "MUSL_SYSROOT_FULL_DIR",
        builder.prebuild_dir / f"sysroot_musl_full-gcc{MUSL_GCC_VERSION}",
    )
).resolve()
DEST_DIR = builder.output_dir / BUNDLE_DIR_NAME
PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_VERIFY_SOURCE = PACKAGE_DIR / "samples" / "main.c"
VERIFY_SOURCE_DIR = PACKAGE_DIR / "thin_verify"
VERIFY_TOOLCHAIN_FILE = VERIFY_SOURCE_DIR / "toolchain.cmake"
VERIFY_BUILD_DIR = builder.build_dir / f"{__PACKAGE_NAME__}-verify"
VERIFY_OUTPUT_DIR = builder.output_dir / f"{__PACKAGE_NAME__}-verify"
VERIFY_EXPECTED_OUTPUT = "thin_a_test=101\nthin_b_test=202"
COMPILER_RT_LIB_DIR = Path(
    env(
        "COMPILER_RT_LIB_DIR",
        builder.output_dir
        / f"compiler_rt_builtins-llvm{builder.llvm_version}"
        / "lib"
        / "clang"
        / builder.llvm_major_version
        / "lib",
    )
).resolve()

sysroot_full = prebuild(
    name="sysroot_full",
    version=GCC_VERSION,
    filename_fmt="{{name}}-gcc{{version}}.tar.xz",
    url_fmt=(
        "https://github.com/zarraxx/llvm_builder/releases/download/"
        "{{name}}-gcc{{version}}/{{filename}}"
    ),
)

sysroot_musl_full = prebuild(
    name="sysroot_musl_full",
    version=MUSL_GCC_VERSION,
    filename_fmt="{{name}}-gcc{{version}}.tar.xz",
    url_fmt=(
        "https://github.com/zarraxx/llvm_builder/releases/download/"
        "{{name}}-gcc{{version}}/{{filename}}"
    ),
)


def configure() -> None:
    missing = []
    for triple in _selected_targets():
        source_sysroot = _source_root(triple) / triple / "sysroot"
        if triple == MINGW_TRIPLE:
            source_prefix = source_sysroot / triple
            required_paths = (
                source_prefix / "include" / "windows.h",
                source_prefix / "lib" / "crt2.o",
                source_prefix / "lib" / "dllcrt2.o",
                source_prefix / "lib" / "libmingw32.a",
                source_prefix / "lib" / "libmsvcrt.a",
            )
            missing.extend(path for path in required_paths if not path.exists())
            continue

        runtime_dir, link_dir = TARGET_LAYOUTS[triple]
        required_paths = [
            source_sysroot / "usr" / "include" / "stdio.h",
            source_sysroot / runtime_dir,
            source_sysroot / link_dir / "libc.so",
        ]
        if triple in MUSL_TARGETS:
            required_paths.extend(
                (
                    source_sysroot / DYNAMIC_LINKERS[triple].removeprefix("/"),
                    source_sysroot / link_dir / "libc.a",
                    *(source_sysroot / link_dir / name for name in MUSL_START_FILES),
                )
            )
        for required in required_paths:
            if not required.exists():
                missing.append(required)

    if missing:
        paths = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"sysroot_full 依赖不完整:\n{paths}")

    print(f"GCC/glibc bundle version: {GCC_VERSION}")
    print(f"GCC/musl bundle version: {MUSL_GCC_VERSION}")
    print(f"Full glibc sysroot source: {SOURCE_ROOT}")
    print(f"Full musl sysroot source: {MUSL_SOURCE_ROOT}")


def build() -> None:
    if DEST_DIR.exists():
        shutil.rmtree(DEST_DIR)

    for triple in _selected_targets():
        source_sysroot = _source_root(triple) / triple / "sysroot"
        destination_sysroot = DEST_DIR / triple / "sysroot"
        if triple == MINGW_TRIPLE:
            _build_mingw_sysroot(source_sysroot, destination_sysroot)
            continue
        if triple in MUSL_TARGETS:
            _build_musl_sysroot(triple, source_sysroot, destination_sysroot)
            continue

        runtime_dir, link_dir = TARGET_LAYOUTS[triple]

        shutil.copytree(
            source_sysroot / "usr" / "include",
            destination_sysroot / "usr" / "include",
            symlinks=True,
            ignore=shutil.ignore_patterns("c++"),
        )
        _copy_runtime_libraries(
            source_sysroot / runtime_dir,
            destination_sysroot / runtime_dir,
        )
        _copy_link_files(
            source_sysroot / link_dir,
            destination_sysroot / link_dir,
        )

        for relative_path in EXTRA_ENTRIES.get(triple, ()):
            _copy_entry(
                source_sysroot / relative_path,
                destination_sysroot / relative_path,
            )

        for relative_path, target in SYSROOT_ALIASES.get(triple, ()):
            alias = destination_sysroot / relative_path
            alias.parent.mkdir(parents=True, exist_ok=True)
            alias.symlink_to(target, target_is_directory=True)


def verify() -> None:
    if not VERIFY_SOURCE_DIR.is_dir() or not VERIFY_TOOLCHAIN_FILE.is_file():
        raise FileNotFoundError(f"thin 验证工程不完整: {VERIFY_SOURCE_DIR}")

    for path in (VERIFY_BUILD_DIR, VERIFY_OUTPUT_DIR):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)

    for triple in _selected_targets():
        _verify_structure(triple)
        _verify_target(triple)


def package() -> None:
    archive = builder.output_dir / f"{BUNDLE_DIR_NAME}.tar.xz"
    Shell.tar("caf", archive, "-C", builder.output_dir, BUNDLE_DIR_NAME)
    print(f"Created {archive}")


def _selected_targets() -> list[str]:
    parser = argparse.ArgumentParser(
        prog=f"{Path(__file__).name} [build options]",
        description="从 full sysroot 裁剪 glibc/musl 主 ABI 的最小 sysroot",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=TARGETS,
        help="只处理指定 target；可以重复传入，默认处理全部 Linux targets",
    )
    args = parser.parse_args(__sys_argv__)
    return args.target or list(TARGETS)


def _source_root(triple: str) -> Path:
    """Resolve both current rooted releases and legacy rootless archives."""
    source_root = MUSL_SOURCE_ROOT if triple in MUSL_TARGETS else SOURCE_ROOT
    if (source_root / triple / "sysroot").is_dir():
        return source_root

    legacy_root = builder.prebuild_dir
    if (legacy_root / triple / "sysroot").is_dir():
        return legacy_root

    return source_root


def _copy_runtime_libraries(source_dir: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for source in source_dir.iterdir():
        if _is_dynamic_loader(source.name) or _is_glibc_runtime(source.name):
            _copy_entry(source, destination_dir / source.name)


def _build_musl_sysroot(
    triple: str,
    source_sysroot: Path,
    destination_sysroot: Path,
) -> None:
    _, link_dir = MUSL_TARGET_LAYOUTS[triple]
    shutil.copytree(
        source_sysroot / "usr" / "include",
        destination_sysroot / "usr" / "include",
        symlinks=True,
        ignore=shutil.ignore_patterns("c++"),
    )

    for name in MUSL_LINK_FILES:
        source = source_sysroot / link_dir / name
        if source.exists() or source.is_symlink():
            _copy_entry(source, destination_sysroot / link_dir / name)

    loader = DYNAMIC_LINKERS[triple].removeprefix("/")
    _copy_entry(source_sysroot / loader, destination_sysroot / loader)


def _build_mingw_sysroot(source_sysroot: Path, destination_sysroot: Path) -> None:
    source_prefix = source_sysroot / MINGW_TRIPLE
    destination_prefix = destination_sysroot / MINGW_TRIPLE
    shutil.copytree(
        source_prefix / "include",
        destination_prefix / "include",
        symlinks=True,
        ignore=shutil.ignore_patterns("c++"),
    )

    destination_lib = destination_prefix / "lib"
    shutil.copytree(source_prefix / "lib", destination_lib, symlinks=True)

    source_bin = source_prefix / "bin"
    destination_bin = destination_prefix / "bin"
    if source_bin.is_dir():
        shutil.copytree(source_bin, destination_bin, symlinks=True)
    else:
        destination_bin.mkdir(parents=True)

    _remove_forbidden_mingw_entries(destination_prefix)

    # Older sysroot_full archives kept runtime DLLs beside import libraries.
    # Normalize them to bin as the current full package does.
    for dll in destination_lib.glob("*.dll"):
        destination = destination_bin / dll.name
        if destination.exists():
            dll.unlink()
        else:
            shutil.move(dll, destination)


def _remove_forbidden_mingw_entries(prefix: Path) -> None:
    forbidden = [
        path
        for path in prefix.rglob("*")
        if path.name.startswith(FORBIDDEN_PREFIXES)
        or "c++" in path.relative_to(prefix).parts
    ]
    for path in sorted(forbidden, key=lambda entry: len(entry.parts), reverse=True):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


def _copy_link_files(source_dir: Path, destination_dir: Path) -> None:
    names = (*GLIBC_START_FILES, *GLIBC_NONSHARED_ARCHIVES, *GLIBC_LINK_LIBRARIES)
    for name in names:
        source = source_dir / name
        if source.exists() or source.is_symlink():
            _copy_entry(source, destination_dir / name)


def _copy_entry(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
    else:
        shutil.copy2(source, destination)


def _is_dynamic_loader(name: str) -> bool:
    return name.startswith(("ld-", "ld-linux-", "ld64.so.", "ld.so."))


def _is_glibc_runtime(name: str) -> bool:
    return any(
        name.startswith((f"{family}-", f"{family}.so"))
        for family in GLIBC_RUNTIME_FAMILIES
    )


def _verify_structure(triple: str) -> None:
    sysroot = DEST_DIR / triple / "sysroot"
    if triple == MINGW_TRIPLE:
        _verify_mingw_structure(sysroot)
        return
    if triple in MUSL_TARGETS:
        _verify_musl_structure(triple, sysroot)
        return

    runtime_dir, link_dir = TARGET_LAYOUTS[triple]
    required = (
        sysroot / "usr" / "include" / "stdio.h",
        sysroot / DYNAMIC_LINKERS[triple].removeprefix("/"),
        sysroot / link_dir / "libc.so",
        sysroot / link_dir / "libc_nonshared.a",
        *(sysroot / link_dir / name for name in GLIBC_START_FILES),
    )
    missing = [path for path in required if not path.exists()]
    if missing:
        paths = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"{triple} 的 thin sysroot 不完整:\n{paths}")

    libc_candidates = list((sysroot / runtime_dir).glob("libc.so.*"))
    if not libc_candidates:
        raise FileNotFoundError(f"{triple} 缺少 glibc 动态库")

    if triple == "riscv64-unknown-linux-gnu":
        multilib_dirs = [
            path
            for root in (sysroot / "lib64", sysroot / "usr" / "lib64")
            if root.is_dir()
            for path in root.iterdir()
            if path.is_dir() and path.name != "lp64d"
        ]
        multilib_dirs.extend(
            path
            for path in (
                sysroot / "lib32",
                sysroot / "usr" / "lib32",
            )
            if path.exists()
        )
        multilib_dirs.extend(
            path
            for root in (sysroot / runtime_dir, sysroot / link_dir)
            if root.is_dir()
            for path in root.iterdir()
            if path.is_dir()
        )
        if multilib_dirs:
            paths = "\n".join(f"  - {path}" for path in multilib_dirs)
            raise RuntimeError(f"{triple} 包含不需要的 multilib 目录:\n{paths}")

    forbidden = [
        path
        for path in sysroot.rglob("*")
        if path.name.startswith(FORBIDDEN_PREFIXES)
        or "c++" in path.relative_to(sysroot).parts
    ]
    if forbidden:
        paths = "\n".join(f"  - {path}" for path in forbidden)
        raise RuntimeError(f"{triple} 包含禁止的 GCC/C++ runtime:\n{paths}")

    allowed_archives = set(GLIBC_NONSHARED_ARCHIVES)
    static_archives = [
        path for path in sysroot.rglob("*.a") if path.name not in allowed_archives
    ]
    if static_archives:
        paths = "\n".join(f"  - {path}" for path in static_archives)
        raise RuntimeError(f"{triple} 包含完整静态库:\n{paths}")


def _verify_musl_structure(triple: str, sysroot: Path) -> None:
    _, link_dir = MUSL_TARGET_LAYOUTS[triple]
    required = (
        sysroot / "usr" / "include" / "stdio.h",
        sysroot / DYNAMIC_LINKERS[triple].removeprefix("/"),
        sysroot / link_dir / "libc.so",
        sysroot / link_dir / "libc.a",
        *(sysroot / link_dir / name for name in MUSL_START_FILES),
    )
    missing = [path for path in required if not path.exists()]
    if missing:
        paths = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"{triple} 的 musl thin sysroot 不完整:\n{paths}")

    forbidden = [
        path
        for path in sysroot.rglob("*")
        if path.name.startswith(FORBIDDEN_PREFIXES)
        or "c++" in path.relative_to(sysroot).parts
    ]
    if forbidden:
        paths = "\n".join(f"  - {path}" for path in forbidden)
        raise RuntimeError(f"{triple} 包含禁止的 GCC/C++ runtime:\n{paths}")

    allowed_archives = set(MUSL_STATIC_LIBRARIES)
    unexpected_archives = [
        path for path in sysroot.rglob("*.a") if path.name not in allowed_archives
    ]
    if unexpected_archives:
        paths = "\n".join(f"  - {path}" for path in unexpected_archives)
        raise RuntimeError(f"{triple} 包含非 musl 静态库:\n{paths}")

    if triple == "x86_64-unknown-linux-musl":
        leaked_multilib = [
            path
            for path in (sysroot / "usr" / "lib", sysroot / "lib" / "ld-musl-i386.so.1")
            if path.exists()
        ]
        if leaked_multilib:
            paths = "\n".join(f"  - {path}" for path in leaked_multilib)
            raise RuntimeError(f"{triple} 包含不需要的 32 位 multilib:\n{paths}")


def _verify_mingw_structure(sysroot: Path) -> None:
    prefix = sysroot / MINGW_TRIPLE
    lib_dir = prefix / "lib"
    required = (
        prefix / "include" / "windows.h",
        prefix / "bin",
        *(lib_dir / name for name in MINGW_CRT_OBJECTS),
        *(lib_dir / name for name in MINGW_REQUIRED_LIBRARIES),
    )
    missing = [path for path in required if not path.exists()]
    if missing:
        paths = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"{MINGW_TRIPLE} 的 thin sysroot 不完整:\n{paths}")

    forbidden = [
        path
        for path in sysroot.rglob("*")
        if path.name.startswith(FORBIDDEN_PREFIXES)
        or "c++" in path.relative_to(sysroot).parts
    ]
    if forbidden:
        paths = "\n".join(f"  - {path}" for path in forbidden)
        raise RuntimeError(f"{MINGW_TRIPLE} 包含禁止的 GCC/C++ runtime:\n{paths}")

    misplaced_dlls = list(lib_dir.rglob("*.dll"))
    if misplaced_dlls:
        paths = "\n".join(f"  - {path}" for path in misplaced_dlls)
        raise RuntimeError(f"{MINGW_TRIPLE} 的 DLL 应放在 bin 而不是 lib:\n{paths}")

    unexpected_dirs = [prefix / "lib32", prefix / "bin32", prefix / "include" / "c++"]
    present_dirs = [path for path in unexpected_dirs if path.exists()]
    if present_dirs:
        paths = "\n".join(f"  - {path}" for path in present_dirs)
        raise RuntimeError(f"{MINGW_TRIPLE} 包含不需要的 multilib/C++ 目录:\n{paths}")


def _verify_target(triple: str) -> None:
    sysroot = DEST_DIR / triple / "sysroot"
    target_build_dir = VERIFY_BUILD_DIR / triple
    target_output_dir = VERIFY_OUTPUT_DIR / triple

    if triple == MINGW_TRIPLE:
        link_path = sysroot / triple / "lib"
        builtins_lib = (
            COMPILER_RT_LIB_DIR / "x86_64-w64-windows-gnu" / "libclang_rt.builtins.a"
        )
        if not builtins_lib.is_file():
            raise FileNotFoundError(
                f"MinGW thin 验证缺少 compiler-rt builtins: {builtins_lib}"
            )
        system_args = [
            "-DTHIN_SYSTEM_NAME=Windows",
            f"-DTHIN_BUILTINS_LIB={builtins_lib}",
        ]
        outputs = (
            target_output_dir / "thin_a.dll",
            target_output_dir / "thin_b.dll",
            target_output_dir / "thin_verify.exe",
        )
    else:
        _, link_dir = TARGET_LAYOUTS[triple]
        link_path = sysroot / link_dir
        system_args = [
            "-DTHIN_SYSTEM_NAME=Linux",
            f"-DTHIN_DYNAMIC_LINKER={DYNAMIC_LINKERS[triple]}",
            f"-DTHIN_DL_LIBRARY={'dl' if (link_path / 'libdl.so').exists() else ''}",
        ]
        outputs = (
            target_output_dir / "thin_a.so",
            target_output_dir / "thin_b.so",
            target_output_dir / "thin_verify",
        )

    print(f"Configuring thin verify project for {triple}", flush=True)
    builder.cmake_configure(
        [
            f"-DCMAKE_TOOLCHAIN_FILE={VERIFY_TOOLCHAIN_FILE}",
            f"-DTHIN_TARGET_TRIPLE={triple}",
            f"-DTHIN_TARGET_SYSROOT={sysroot}",
            f"-DTHIN_CRT_DIR={link_path}",
            f"-DTHIN_C_COMPILER={builder.clang}",
            f"-DTHIN_OUTPUT_DIR={target_output_dir}",
            *system_args,
        ],
        source_dir=VERIFY_SOURCE_DIR,
        build_dir=target_build_dir,
        output_dir=target_output_dir,
    )
    builder.cmake_build([], build_dir=target_build_dir)

    missing = [path for path in outputs if not path.is_file()]
    if missing:
        paths = "\n".join(f"  - {path}" for path in missing)
        raise RuntimeError(f"{triple} 缺少 thin 验证产物:\n{paths}")

    actual = _run_verify_executable(triple, outputs[-1], target_output_dir)
    if actual != VERIFY_EXPECTED_OUTPUT:
        raise RuntimeError(
            f"{triple} 验证输出不匹配: "
            f"expected={VERIFY_EXPECTED_OUTPUT!r}, actual={actual!r}"
        )
    print(f"Verified thin shared libraries for {triple}:\n{actual}")
    if triple in MUSL_TARGETS:
        _verify_static_musl(triple, sysroot, link_path, target_output_dir)


def _verify_static_musl(
    triple: str,
    sysroot: Path,
    link_path: Path,
    output_dir: Path,
) -> None:
    if not STATIC_VERIFY_SOURCE.is_file():
        raise FileNotFoundError(f"musl 静态验证源码不存在: {STATIC_VERIFY_SOURCE}")

    builtins_lib = COMPILER_RT_LIB_DIR / triple / "libclang_rt.builtins.a"
    if not builtins_lib.is_file():
        raise FileNotFoundError(
            f"{triple} 静态验证缺少 compiler-rt builtins: {builtins_lib}"
        )

    executable = output_dir / "thin_verify_static"
    _run_checked(
        [
            str(builder.clang),
            f"--target={triple}",
            f"--sysroot={sysroot}",
            "-fuse-ld=lld",
            "-static",
            "-nostdlib",
            f'-DSAMPLE_ARCH="{triple}"',
            str(link_path / "crt1.o"),
            str(link_path / "crti.o"),
            str(STATIC_VERIFY_SOURCE),
            f"-L{link_path}",
            "-lc",
            str(builtins_lib),
            str(link_path / "crtn.o"),
            "-o",
            str(executable),
        ]
    )
    if not executable.is_file():
        raise RuntimeError(f"{triple} 缺少 musl 静态验证产物: {executable}")

    qemu = shutil.which(QEMU_COMMANDS[triple])
    if qemu is None:
        raise FileNotFoundError(f"验证工具不存在: {QEMU_COMMANDS[triple]}")
    actual = _run_checked([qemu, str(executable)]).stdout.strip()
    expected = f"hello {triple}"
    if actual != expected:
        raise RuntimeError(
            f"{triple} 静态验证输出不匹配: expected={expected!r}, actual={actual!r}"
        )
    print(f"Verified static musl libc for {triple}: {actual}")


def _run_verify_executable(
    triple: str,
    executable: Path,
    library_dir: Path,
) -> str:
    if triple == MINGW_TRIPLE:
        windows_library_dir = _run_checked(
            ["winepath", "-w", str(library_dir)]
        ).stdout.strip()
        run_env = os.environ.copy()
        run_env.update({"WINEDEBUG": "-all", "WINEPATH": windows_library_dir})
        return _run_checked(["wine", str(executable)], env=run_env).stdout.strip()

    sysroot = DEST_DIR / triple / "sysroot"
    qemu = shutil.which(QEMU_COMMANDS[triple])
    if qemu is None:
        raise FileNotFoundError(f"验证工具不存在: {QEMU_COMMANDS[triple]}")
    result = _run_checked(
        [
            qemu,
            "-L",
            str(sysroot),
            "-E",
            (f"LD_LIBRARY_PATH={library_dir}:/lib:/lib64:/usr/lib:/usr/lib64"),
            str(executable),
        ]
    )
    return result.stdout.strip()


def _run_checked(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
    except subprocess.CalledProcessError as error:
        output = error.stdout or ""
        raise RuntimeError(
            f"命令执行失败 ({error.returncode}): {' '.join(command)}\n{output}"
        ) from error
