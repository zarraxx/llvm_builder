import argparse
from pathlib import Path

from python_shell import Shell

from sysroot_creator import MINGW_TRIPLE, triple_list, triple_short_name


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_SOURCE_DIR = Path(__file__).resolve().parent / "samples"
TOOLCHAIN_FILE = SAMPLE_SOURCE_DIR / "toolchain.cmake"
DEFAULT_SYSROOT_DIR = PROJECT_ROOT / "dist" / "sysroot"
DEFAULT_BUILD_DIR = PROJECT_ROOT / ".build" / "samples"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "dist" / "samples"

QEMU_COMMANDS = {
    "aarch64-unknown-linux-gnu": "qemu-aarch64",
    "armv7-unknown-linux-gnueabihf": "qemu-arm",
    "loongarch64-unknown-linux-gnu": "qemu-loongarch64",
    "mips64el-unknown-linux-gnu": "qemu-mips64el",
    "powerpc64le-unknown-linux-gnu": "qemu-ppc64le",
    "s390x-ibm-linux-gnu": "qemu-s390x",
    "x86_64-unknown-linux-gnu": "qemu-x86_64",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="使用 Clang 和 sysroot 构建全部架构的 C/C++ 示例",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=triple_list,
        help="只构建指定 target；可以重复传入，默认构建全部 target",
    )
    parser.add_argument(
        "--sysroot-dir",
        type=Path,
        default=DEFAULT_SYSROOT_DIR,
        help=f"sysroot bundle 路径，默认：{DEFAULT_SYSROOT_DIR}",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=DEFAULT_BUILD_DIR,
        help=f"CMake 构建目录，默认：{DEFAULT_BUILD_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"示例输出目录，默认：{DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument("--clang", default="clang", help="Clang C 编译器")
    parser.add_argument("--clangxx", default="clang++", help="Clang C++ 编译器")
    return parser.parse_args()


def run_output(triple: str, executable: Path, target_sysroot: Path) -> str:
    if triple == MINGW_TRIPLE:
        runtime_dir = target_sysroot / triple / "lib"
        winepath = Shell.winepath("-w", str(runtime_dir))
        windows_runtime_dir = (
            b"".join(winepath.output).decode("utf-8").strip()
        )

        # python-shell 1.1.0 does not forward an env= keyword to Popen, so use
        # the env command through python-shell to provide Wine's DLL path.
        command = Shell.env(
            "WINEDEBUG=-all",
            f"WINEPATH={windows_runtime_dir}",
            "wine",
            str(executable),
        )
    else:
        qemu = QEMU_COMMANDS[triple]
        command = getattr(Shell, qemu)(
            "-L",
            str(target_sysroot),
            "-E",
            "LD_LIBRARY_PATH=/lib:/lib64:/usr/lib:/usr/lib64",
            str(executable),
        )

    return b"".join(command.output).decode("utf-8").strip()


def build_target(
    triple: str,
    *,
    sysroot_dir: Path,
    build_dir: Path,
    output_dir: Path,
    clang: str,
    clangxx: str,
):
    arch = triple_short_name[triple]
    target_sysroot = sysroot_dir / triple / "sysroot"
    target_build_dir = build_dir / triple

    if not target_sysroot.is_dir():
        raise FileNotFoundError(f"Target sysroot 不存在：{target_sysroot}")

    print(f"\nConfiguring {triple} ({arch})", flush=True)
    Shell.cmake(
        "-S",
        str(SAMPLE_SOURCE_DIR),
        "-B",
        str(target_build_dir),
        "-G",
        "Ninja",
        f"-DCMAKE_TOOLCHAIN_FILE={TOOLCHAIN_FILE}",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DTARGET_TRIPLE={triple}",
        f"-DTARGET_SYSROOT={target_sysroot}",
        f"-DSYSROOT_BUNDLE={sysroot_dir}",
        f"-DSAMPLE_ARCH={arch}",
        f"-DSAMPLE_OUTPUT_DIR={output_dir}",
        f"-DSAMPLE_C_COMPILER={clang}",
        f"-DSAMPLE_CXX_COMPILER={clangxx}",
        stdout=None,
        stderr=None,
    )
    Shell.cmake(
        "--build",
        str(target_build_dir),
        "--parallel",
        stdout=None,
        stderr=None,
    )

    c_output = output_dir / f"main.{arch}"
    cxx_output = output_dir / f"maincxx.{arch}"
    if not c_output.is_file() or not cxx_output.is_file():
        raise RuntimeError(f"缺少构建产物：{c_output} 或 {cxx_output}")

    print(f"Built {c_output}")
    print(f"Built {cxx_output}")

    expected_output = f"hello {arch}"
    for executable in (c_output, cxx_output):
        actual_output = run_output(triple, executable, target_sysroot)
        if actual_output != expected_output:
            raise RuntimeError(
                f"{executable} 输出不匹配："
                f"expected={expected_output!r}, actual={actual_output!r}"
            )
        print(f"Ran {executable}: {actual_output}")


def build_all(
    targets: list[str],
    *,
    sysroot_dir: Path,
    build_dir: Path,
    output_dir: Path,
    clang: str,
    clangxx: str,
):
    sysroot_dir = sysroot_dir.resolve()
    build_dir = build_dir.resolve()
    output_dir = output_dir.resolve()

    Shell.rm("-rf", str(build_dir), stdout=None, stderr=None)
    Shell.rm("-rf", str(output_dir), stdout=None, stderr=None)
    Shell.mkdir("-p", str(build_dir), str(output_dir), stdout=None, stderr=None)

    for triple in targets:
        build_target(
            triple,
            sysroot_dir=sysroot_dir,
            build_dir=build_dir,
            output_dir=output_dir,
            clang=clang,
            clangxx=clangxx,
        )


def main():
    args = parse_args()
    targets = args.target or triple_list
    build_all(
        targets,
        sysroot_dir=args.sysroot_dir,
        build_dir=args.build_dir,
        output_dir=args.output_dir,
        clang=args.clang,
        clangxx=args.clangxx,
    )


if __name__ == "__main__":
    main()
