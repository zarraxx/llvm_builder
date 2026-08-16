from pathlib import Path
from types import SimpleNamespace

import pytest

from BuilderRunner import BuilderRunner


class FakeDependency:
    def __init__(self, name: str, version: str, filename: str, url: str):
        self.name = name
        self.version = version
        self.filename = filename
        self.url = url
        self.extract_dir: list[str] = []


class FakeBuilder:
    def __init__(self, workspace: Path, llvm_version: str = "22.1.8"):
        self.workspace = Path(workspace).resolve()
        self.llvm_version = llvm_version
        self.llvm_major_version = llvm_version.split(".")[0]
        self.name = None
        self.version = "unknown"
        self.build_dir = self.workspace / ".build"
        self.output_dir = self.workspace / "dist"
        self.source_dir = self.workspace / ".source"
        self.prebuild_dir = self.workspace / ".prebuild"
        self.toolchain_dir = self.build_dir / f"LLVM-{llvm_version}-Linux-X64"
        self.clang = self.toolchain_dir / "bin" / "clang"
        self.clangxx = self.toolchain_dir / "bin" / "clang++"
        self.ar = self.toolchain_dir / "bin" / "llvm-ar"
        self.ranlib = self.toolchain_dir / "bin" / "llvm-ranlib"
        self.nm = self.toolchain_dir / "bin" / "llvm-nm"
        self.events: list[object] = []

        for directory in (
            self.build_dir,
            self.output_dir,
            self.source_dir,
            self.prebuild_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def prepare_builder(self) -> None:
        self.events.append("prepare")

    def _dependency(self, name: str, version: str, filename_fmt: str, **kwargs):
        url_fmt = kwargs.pop("url_fmt", "https://example.test/{{filename}}")
        filename = filename_fmt.replace("{{name}}", name).replace(
            "{{version}}", version
        )
        for key, value in kwargs.items():
            filename = filename.replace(f"{{{{{key}}}}}", str(value))
        url = (
            url_fmt.replace("{{name}}", name)
            .replace("{{version}}", version)
            .replace("{{filename}}", filename)
        )
        for key, value in kwargs.items():
            url = url.replace(f"{{{{{key}}}}}", str(value))
        return FakeDependency(name, version, filename, url)

    add_source_dependence = _dependency
    add_tool_dependence = _dependency
    add_prebuild_dependence = _dependency

    def extract_tools_dependencies(self) -> None:
        self.events.append("extract_tools")

    def extract_prebuild_dependencies(self) -> None:
        self.events.append("extract_prebuild")

    def extract_source_dependencies(self) -> None:
        self.events.append("extract_source")

    def cmake_configure(
        self,
        cmake_args: list[str],
        *,
        source_dir: Path,
        build_dir: Path,
        output_dir: Path,
    ) -> None:
        self.events.append(
            ("cmake_configure", cmake_args, source_dir, build_dir, output_dir)
        )

    def cmake_build(self, cmake_args: list[str], *, build_dir: Path) -> None:
        self.events.append(("cmake_build", cmake_args, build_dir))

    def cmake_install(self, cmake_args: list[str], *, build_dir: Path) -> None:
        self.events.append(("cmake_install", cmake_args, build_dir))


@pytest.mark.parametrize(
    "package_name",
    [
        "sysroot_full.py",
        "sysroot_thin.py",
        "compiler_rt_builtins.py",
        "wasi_libc.py",
    ],
)
def test_package_scripts_load_with_runner_injection(
    package_name: str,
    tmp_path: Path,
):
    project_root = Path(__file__).resolve().parents[1]
    runner = BuilderRunner(
        workspace=tmp_path,
        package_file=project_root / "packages" / package_name,
        builder_type=FakeBuilder,
        builder_kwargs={"llvm_version": "23.0.0"},
    )

    module = runner.load_package_script(
        {
            "LLVM_VERSION": "23.0.0",
            "GCC_VERSION": "15.2.0",
            "__sys_argv__": [],
        }
    )

    assert runner.package_builder.events == ["prepare"]
    assert module.builder is runner.package_builder
    assert module.env("LLVM_VERSION") == "23.0.0"
    assert callable(module.configure)
    assert callable(module.build)


def test_runner_executes_available_lifecycle_stages(tmp_path: Path):
    package_file = tmp_path / "lifecycle.py"
    package_file.write_text(
        """events = []
def configure(): events.append('configure')
def build(): events.append('build')
def verify(): events.append('verify')
""",
        encoding="utf-8",
    )
    runner = BuilderRunner(
        workspace=tmp_path,
        package_file=package_file,
        builder_type=FakeBuilder,
    )
    module = runner.load_package_script({"__sys_argv__": []})

    runner.execute()

    assert runner.package_builder.events == [
        "prepare",
        "extract_tools",
        "extract_prebuild",
        "extract_source",
    ]
    assert module.events == ["configure", "build", "verify"]


def test_compiler_rt_builtins_downloads_sysroot_full_release(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    runner = BuilderRunner(
        workspace=tmp_path,
        package_file=project_root / "packages" / "compiler_rt_builtins.py",
        builder_type=FakeBuilder,
    )
    module = runner.load_package_script({"GCC_VERSION": "15.2.0", "__sys_argv__": []})

    assert module.SYSROOT_DIR == (
        runner.package_builder.prebuild_dir / "sysroot_full-gcc15.2.0"
    )
    assert module.sysroot_full.filename == "sysroot_full-gcc15.2.0.tar.xz"
    assert module.sysroot_full.url == (
        "https://github.com/zarraxx/llvm_builder/releases/download/"
        "sysroot_full-gcc15.2.0/sysroot_full-gcc15.2.0.tar.xz"
    )

    triple = "x86_64-unknown-linux-gnu"
    legacy_sysroot = runner.package_builder.prebuild_dir / triple / "sysroot"
    legacy_sysroot.mkdir(parents=True)
    assert module._sysroot_dir(triple) == runner.package_builder.prebuild_dir

    rooted_sysroot = module.SYSROOT_DIR / triple / "sysroot"
    rooted_sysroot.mkdir(parents=True)
    assert module._sysroot_dir(triple) == module.SYSROOT_DIR


def test_compiler_rt_builtins_packages_versioned_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    project_root = Path(__file__).resolve().parents[1]
    runner = BuilderRunner(
        workspace=tmp_path,
        package_file=project_root / "packages" / "compiler_rt_builtins.py",
        builder_type=FakeBuilder,
        builder_kwargs={"llvm_version": "22.1.8"},
    )
    module = runner.load_package_script({"LLVM_VERSION": "22.1.8", "__sys_argv__": []})
    tar_calls = []
    monkeypatch.setattr(module.Shell, "tar", lambda *args: tar_calls.append(args))

    module.package()

    archive = (
        runner.package_builder.output_dir / "compiler_rt_builtins-llvm22.1.8.tar.xz"
    )
    assert module.OUTPUT_DIR.name == "compiler_rt_builtins-llvm22.1.8"
    assert tar_calls == [
        (
            "caf",
            archive,
            "-C",
            runner.package_builder.output_dir,
            "compiler_rt_builtins-llvm22.1.8",
        )
    ]


def test_riscv64_is_supported_by_all_sysroot_packages(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    triple = "riscv64-unknown-linux-gnu"

    def load(package_name: str):
        runner = BuilderRunner(
            workspace=tmp_path / package_name.removesuffix(".py"),
            package_file=project_root / "packages" / package_name,
            builder_type=FakeBuilder,
        )
        return runner.load_package_script(
            {"GCC_VERSION": "15.2.0", "__sys_argv__": []}
        )

    full = load("sysroot_full.py")
    thin = load("sysroot_thin.py")
    builtins = load("compiler_rt_builtins.py")

    assert triple in full.TARGETS
    assert full.TARGET_SHORT_NAMES[triple] == "riscv64-linux"
    assert full.QEMU_COMMANDS[triple] == "qemu-riscv64"
    assert thin.TARGET_LAYOUTS[triple] == ("lib", "usr/lib")
    assert thin.DYNAMIC_LINKERS[triple] == "/lib/ld-linux-riscv64-lp64d.so.1"
    assert thin.QEMU_COMMANDS[triple] == "qemu-riscv64"
    assert triple in builtins.SYSROOT_TARGETS


def test_sysroot_thin_riscv64_keeps_default_abi_without_multilib(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    triple = "riscv64-unknown-linux-gnu"
    full_root = tmp_path / "sysroot-full"
    source_sysroot = full_root / triple / "sysroot"
    include_dir = source_sysroot / "usr" / "include"
    runtime_dir = source_sysroot / "lib"
    link_dir = source_sysroot / "usr" / "lib"

    include_dir.mkdir(parents=True)
    (include_dir / "stdio.h").write_text("", encoding="utf-8")
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "ld-linux-riscv64-lp64d.so.1").write_text(
        "loader", encoding="utf-8"
    )
    (runtime_dir / "libc.so.6").write_text("glibc", encoding="utf-8")
    link_dir.mkdir(parents=True)
    for name in ("crt1.o", "Scrt1.o", "crti.o", "crtn.o", "libc_nonshared.a"):
        (link_dir / name).write_text(name, encoding="utf-8")
    (link_dir / "libc.so").write_text(
        "GROUP ( /lib/libc.so.6 )", encoding="utf-8"
    )

    alternate_runtime = runtime_dir / "rv32imac" / "ilp32"
    alternate_runtime.mkdir(parents=True)
    (alternate_runtime / "libc.so.6").write_text("rv32", encoding="utf-8")
    alternate_link = link_dir / "rv64imac" / "lp64"
    alternate_link.mkdir(parents=True)
    (alternate_link / "libc.so").write_text("lp64", encoding="utf-8")
    (source_sysroot / "lib64" / "lp64").mkdir(parents=True)
    (source_sysroot / "lib64" / "lp64" / "libc.so.6").write_text(
        "lp64", encoding="utf-8"
    )

    runner = BuilderRunner(
        workspace=tmp_path,
        package_file=project_root / "packages" / "sysroot_thin.py",
        builder_type=FakeBuilder,
    )
    module = runner.load_package_script(
        {
            "GCC_VERSION": "15.2.0",
            "SYSROOT_FULL_DIR": str(full_root),
            "__sys_argv__": ["--target", triple],
        }
    )

    module.configure()
    module.build()
    module._verify_structure(triple)

    thin_sysroot = module.DEST_DIR / triple / "sysroot"
    assert (thin_sysroot / "lib" / "ld-linux-riscv64-lp64d.so.1").is_file()
    assert (thin_sysroot / "lib" / "libc.so.6").is_file()
    assert (thin_sysroot / "usr" / "lib" / "libc.so").is_file()
    assert not (thin_sysroot / "lib" / "rv32imac").exists()
    assert not (thin_sysroot / "usr" / "lib" / "rv64imac").exists()
    assert not (thin_sysroot / "lib64").exists()


@pytest.mark.parametrize(
    ("workflow_name", "required_snippets"),
    [
        (
            "sysroot-release.yml",
            (
                'manifest="${archive}.contents"',
                "riscv64-unknown-linux-gnu/sysroot/usr/lib/libc.so",
                "lib/gcc/riscv64-unknown-linux-gnu/${GCC_VERSION}/libgcc.a",
            ),
        ),
        (
            "compiler-rt-builtins-release.yml",
            (
                'manifest="${archive}.contents"',
                'llvm_major="${LLVM_VERSION%%.*}"',
                "lib/riscv64-unknown-linux-gnu/libclang_rt.builtins.a",
            ),
        ),
        (
            "sysroot-thin-release.yml",
            (
                'manifest="${archive}.contents"',
                "riscv64-unknown-linux-gnu/sysroot/lib/ld-linux-riscv64-lp64d.so.1",
                "riscv64-unknown-linux-gnu/sysroot/usr/lib/libc.so",
                "RISC-V multilib path leaked into thin sysroot",
            ),
        ),
    ],
)
def test_riscv64_workflow_archive_contracts(
    workflow_name: str, required_snippets: tuple[str, ...]
):
    project_root = Path(__file__).resolve().parents[1]
    workflow = (project_root / ".github" / "workflows" / workflow_name).read_text(
        encoding="utf-8"
    )

    for snippet in required_snippets:
        assert snippet in workflow


@pytest.mark.parametrize(
    ("package_name", "target"),
    [
        ("compiler_rt_builtins.py", "x86_64-unknown-linux-gnu"),
        ("wasi_libc.py", "wasm32-wasip1"),
    ],
)
def test_cmake_packages_delegate_lifecycle_to_builder(
    package_name: str,
    target: str,
    tmp_path: Path,
):
    project_root = Path(__file__).resolve().parents[1]
    runner = BuilderRunner(
        workspace=tmp_path,
        package_file=project_root / "packages" / package_name,
        builder_type=FakeBuilder,
    )
    module = runner.load_package_script({"__sys_argv__": []})
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    module._selected_targets = lambda: [target]
    module._cmake_args = lambda *_args: ["-DTEST_OPTION=ON"]
    if package_name == "compiler_rt_builtins.py":
        module._llvm_source_dir = lambda: source_dir
        configure_source = source_dir / "compiler-rt" / "lib" / "builtins"
        output_dir = module.OUTPUT_DIR
    else:
        module._source_dir = lambda: source_dir
        configure_source = source_dir
        output_dir = module.OUTPUT_ROOT / target

    module.configure()
    module.build()
    module.install()

    assert runner.package_builder.events[1] == (
        "cmake_configure",
        ["-DTEST_OPTION=ON"],
        configure_source,
        module.BUILD_ROOT / target,
        output_dir,
    )
    assert runner.package_builder.events[2] == (
        "cmake_build",
        [],
        module.BUILD_ROOT / target,
    )
    if package_name == "compiler_rt_builtins.py":
        assert runner.package_builder.events[3] == (
            "cmake_build",
            ["--target", "install-builtins"],
            module.BUILD_ROOT / target,
        )
    else:
        assert runner.package_builder.events[3] == (
            "cmake_install",
            [],
            module.BUILD_ROOT / target,
        )


def test_sysroot_package_builds_unified_layout(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    runner = BuilderRunner(
        workspace=tmp_path,
        package_file=project_root / "packages" / "sysroot_full.py",
        builder_type=FakeBuilder,
    )
    module = runner.load_package_script({"GCC_VERSION": "15.2.0", "__sys_argv__": []})

    for triple in module.TARGETS:
        origin_root = runner.package_builder.prebuild_dir / f"{triple}-gcc15.2.0"
        source_prefix = origin_root / triple
        gcc_runtime = origin_root / "lib" / "gcc" / triple / "15.2.0"

        if triple == module.MINGW_TRIPLE:
            for source_dir in (
                source_prefix / "sysroot" / "usr" / triple / "include",
                source_prefix / "sysroot" / "usr" / triple / "bin",
                source_prefix / "sysroot" / "usr" / triple / "lib",
                source_prefix / "sysroot" / "usr" / triple / "lib32",
                source_prefix / "sysroot" / "lib",
                source_prefix / "sysroot" / "lib32",
                source_prefix / "include" / "c++" / "15.2.0",
                gcc_runtime / "32",
            ):
                source_dir.mkdir(parents=True, exist_ok=True)
            (
                source_prefix / "sysroot" / "usr" / triple / "include" / "stdio.h"
            ).write_text("", encoding="utf-8")
            (
                source_prefix
                / "sysroot"
                / "usr"
                / triple
                / "bin"
                / "libwinpthread-1.dll"
            ).write_text("", encoding="utf-8")
            (source_prefix / "sysroot" / "lib" / "runtime64.dll").write_text(
                "", encoding="utf-8"
            )
            (source_prefix / "sysroot" / "lib32" / "runtime32.dll").write_text(
                "", encoding="utf-8"
            )
            (gcc_runtime / "libgcc.a").write_text("", encoding="utf-8")
        else:
            (source_prefix / "sysroot").mkdir(parents=True, exist_ok=True)
            (source_prefix / "sysroot" / "marker").write_text("", encoding="utf-8")
            gcc_runtime.mkdir(parents=True, exist_ok=True)
            (gcc_runtime / "libgcc.a").write_text("", encoding="utf-8")

    module.configure()
    module.build()

    assert (module.DEST_DIR / module.TARGETS[0] / "sysroot" / "marker").is_file()
    assert (
        module.DEST_DIR / "lib" / "gcc" / module.TARGETS[0] / "15.2.0" / "libgcc.a"
    ).is_file()
    assert (
        module.DEST_DIR
        / module.MINGW_TRIPLE
        / "sysroot"
        / module.MINGW_TRIPLE
        / "include"
        / "stdio.h"
    ).is_file()
    assert module.SAMPLE_SOURCE_DIR == project_root / "packages" / "samples"

    mingw_prefix = (
        module.DEST_DIR / module.MINGW_TRIPLE / "sysroot" / module.MINGW_TRIPLE
    )
    assert (mingw_prefix / "bin" / "libwinpthread-1.dll").is_file()
    assert (mingw_prefix / "bin" / "runtime64.dll").is_file()
    assert (mingw_prefix / "bin32" / "runtime32.dll").is_file()
    assert not list((mingw_prefix / "lib").rglob("*.dll"))
    assert not list((mingw_prefix / "lib32").rglob("*.dll"))

    subprocess_calls = []

    def fake_run(command, **kwargs):
        subprocess_calls.append((command, kwargs))
        if command[0] == "winepath":
            return SimpleNamespace(stdout=f"WIN:{command[-1]}")
        return SimpleNamespace(stdout="hello x86_64-mingw32\n")

    module.subprocess.run = fake_run
    mingw_output = module._run_output(
        module.MINGW_TRIPLE,
        Path("sample.exe"),
        module.DEST_DIR / module.MINGW_TRIPLE / "sysroot",
    )
    assert mingw_output == "hello x86_64-mingw32"
    assert subprocess_calls[-1][1]["env"]["WINEPATH"] == (
        f"WIN:{mingw_prefix / 'bin'};WIN:{mingw_prefix / 'bin32'}"
    )

    target = module.TARGETS[0]
    short_name = module.TARGET_SHORT_NAMES[target]
    module.VERIFY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def fake_cmake_build(cmake_args: list[str], *, build_dir: Path) -> None:
        runner.package_builder.events.append(("cmake_build", cmake_args, build_dir))
        for filename in (f"main.{short_name}", f"maincxx.{short_name}"):
            (module.VERIFY_OUTPUT_DIR / filename).write_text("", encoding="utf-8")

    runner.package_builder.cmake_build = fake_cmake_build
    module._run_output = lambda *_args: f"hello {short_name}"
    module._verify_target(target)

    assert runner.package_builder.events[-2][0] == "cmake_configure"
    assert runner.package_builder.events[-1] == (
        "cmake_build",
        [],
        module.VERIFY_BUILD_DIR / target,
    )


def test_sysroot_package_uses_package_name_and_gcc_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    project_root = Path(__file__).resolve().parents[1]
    runner = BuilderRunner(
        workspace=tmp_path,
        package_file=project_root / "packages" / "sysroot_full.py",
        builder_type=FakeBuilder,
    )
    module = runner.load_package_script({"GCC_VERSION": "15.2.0", "__sys_argv__": []})
    tar_calls = []
    monkeypatch.setattr(module.Shell, "tar", lambda *args: tar_calls.append(args))

    module.package()

    archive = runner.package_builder.output_dir / "sysroot_full-gcc15.2.0.tar.xz"
    assert module.DEST_DIR.name == "sysroot_full-gcc15.2.0"
    assert tar_calls == [
        (
            "caf",
            archive,
            "-C",
            runner.package_builder.output_dir,
            "sysroot_full-gcc15.2.0",
        )
    ]


def test_sysroot_thin_keeps_only_dynamic_glibc_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    project_root = Path(__file__).resolve().parents[1]
    triple = "x86_64-unknown-linux-gnu"
    full_root = tmp_path / "sysroot-full"
    source_sysroot = full_root / triple / "sysroot"
    include_dir = source_sysroot / "usr" / "include"
    runtime_dir = source_sysroot / "lib64"
    link_dir = source_sysroot / "usr" / "lib64"

    (include_dir / "c++").mkdir(parents=True)
    (include_dir / "stdio.h").write_text("", encoding="utf-8")
    (include_dir / "c++" / "vector").write_text("", encoding="utf-8")
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "ld-2.17.so").write_text("loader", encoding="utf-8")
    (runtime_dir / "ld-linux-x86-64.so.2").symlink_to("ld-2.17.so")
    (runtime_dir / "libc-2.17.so").write_text("glibc", encoding="utf-8")
    (runtime_dir / "libc.so.6").symlink_to("libc-2.17.so")
    (runtime_dir / "libm-2.17.so").write_text("libm", encoding="utf-8")
    (runtime_dir / "libm.so.6").symlink_to("libm-2.17.so")
    for forbidden in ("libatomic.so.1", "libgcc_s.so.1", "libstdc++.so.6"):
        (runtime_dir / forbidden).write_text("gcc", encoding="utf-8")

    link_dir.mkdir(parents=True)
    for name in (*("crt1.o", "Scrt1.o", "crti.o", "crtn.o"), "libc_nonshared.a"):
        (link_dir / name).write_text(name, encoding="utf-8")
    (link_dir / "libc.so").write_text("GROUP ( /lib64/libc.so.6 )", encoding="utf-8")
    (link_dir / "libm.so").symlink_to("../../lib64/libm.so.6")
    (link_dir / "libc.a").write_text("static libc", encoding="utf-8")
    (link_dir / "libm.a").write_text("static libm", encoding="utf-8")
    (link_dir / "crtbeginS.o").write_text("gcc crt", encoding="utf-8")

    runner = BuilderRunner(
        workspace=tmp_path,
        package_file=project_root / "packages" / "sysroot_thin.py",
        builder_type=FakeBuilder,
    )
    module = runner.load_package_script(
        {
            "GCC_VERSION": "15.2.0",
            "SYSROOT_FULL_DIR": str(full_root),
            "__sys_argv__": ["--target", triple],
        }
    )

    module.configure()
    module.build()
    module._verify_structure(triple)

    thin_sysroot = module.DEST_DIR / triple / "sysroot"
    assert {path.name for path in (module.DEST_DIR / triple).iterdir()} == {"sysroot"}
    assert (thin_sysroot / "usr" / "include" / "stdio.h").is_file()
    assert not (thin_sysroot / "usr" / "include" / "c++").exists()
    assert (thin_sysroot / "lib64" / "libc.so.6").is_symlink()
    assert (thin_sysroot / "usr" / "lib64" / "libc_nonshared.a").is_file()
    assert not list(thin_sysroot.rglob("libc.a"))
    assert not list(thin_sysroot.rglob("libm.a"))
    assert not list(thin_sysroot.rglob("libgcc*"))
    assert not list(thin_sysroot.rglob("libatomic*"))
    assert not list(thin_sysroot.rglob("libstdc++*"))
    assert not list(thin_sysroot.rglob("crtbegin*"))

    tar_calls = []
    monkeypatch.setattr(module.Shell, "tar", lambda *args: tar_calls.append(args))
    module.package()
    archive = runner.package_builder.output_dir / "sysroot_thin-gcc15.2.0.tar.xz"
    assert module.DEST_DIR.name == "sysroot_thin-gcc15.2.0"
    assert tar_calls == [
        (
            "caf",
            archive,
            "-C",
            runner.package_builder.output_dir,
            "sysroot_thin-gcc15.2.0",
        )
    ]


def test_sysroot_thin_keeps_mingw_winsdk_without_gcc_or_cxx(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    triple = "x86_64-w64-mingw32"
    full_root = tmp_path / "sysroot-full"
    source_prefix = full_root / triple / "sysroot" / triple
    include_dir = source_prefix / "include"
    lib_dir = source_prefix / "lib"
    bin_dir = source_prefix / "bin"

    (include_dir / "c++").mkdir(parents=True)
    (include_dir / "windows.h").write_text("", encoding="utf-8")
    (include_dir / "d3d12.h").write_text("", encoding="utf-8")
    (include_dir / "c++" / "vector").write_text("", encoding="utf-8")
    lib_dir.mkdir(parents=True)
    for name in (
        "crt2.o",
        "dllcrt2.o",
        "libmingw32.a",
        "libmsvcrt.a",
        "libkernel32.a",
        "libgdi32.a",
        "libole32.a",
        "libd3d12.a",
        "libwinpthread.dll.a",
    ):
        (lib_dir / name).write_text(name, encoding="utf-8")
    for name in (
        "crtbegin.o",
        "crtfastmath.o",
        "libatomic.a",
        "libgcc.a",
        "libstdc++.a",
    ):
        (lib_dir / name).write_text(name, encoding="utf-8")
    (lib_dir / "libwinpthread-1.dll").write_text("runtime", encoding="utf-8")
    bin_dir.mkdir(parents=True)
    (bin_dir / "winsdk-runtime.dll").write_text("runtime", encoding="utf-8")
    (bin_dir / "libgcc_s_seh-1.dll").write_text("gcc", encoding="utf-8")
    (source_prefix / "lib32").mkdir()
    (source_prefix / "bin32").mkdir()

    runner = BuilderRunner(
        workspace=tmp_path,
        package_file=project_root / "packages" / "sysroot_thin.py",
        builder_type=FakeBuilder,
    )
    module = runner.load_package_script(
        {
            "GCC_VERSION": "15.2.0",
            "SYSROOT_FULL_DIR": str(full_root),
            "__sys_argv__": ["--target", triple],
        }
    )

    module.configure()
    module.build()
    module._verify_structure(triple)

    thin_prefix = module.DEST_DIR / triple / "sysroot" / triple
    assert (thin_prefix / "include" / "windows.h").is_file()
    assert (thin_prefix / "include" / "d3d12.h").is_file()
    assert not (thin_prefix / "include" / "c++").exists()
    assert (thin_prefix / "lib" / "libole32.a").is_file()
    assert (thin_prefix / "lib" / "libd3d12.a").is_file()
    assert (thin_prefix / "lib" / "libwinpthread.dll.a").is_file()
    assert (thin_prefix / "bin" / "winsdk-runtime.dll").is_file()
    assert (thin_prefix / "bin" / "libwinpthread-1.dll").is_file()
    assert not list((thin_prefix / "lib").glob("*.dll"))
    assert not list(thin_prefix.rglob("libgcc*"))
    assert not list(thin_prefix.rglob("libatomic*"))
    assert not list(thin_prefix.rglob("libstdc++*"))
    assert not list(thin_prefix.rglob("crtbegin*"))
    assert not list(thin_prefix.rglob("crtfastmath*"))
    assert not (thin_prefix / "lib32").exists()
    assert not (thin_prefix / "bin32").exists()

    def fake_cmake_build(cmake_args: list[str], *, build_dir: Path) -> None:
        runner.package_builder.events.append(("cmake_build", cmake_args, build_dir))
        output_dir = module.VERIFY_OUTPUT_DIR / triple
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("thin_a.dll", "thin_b.dll", "thin_verify.exe"):
            (output_dir / filename).write_text("", encoding="utf-8")

    runner.package_builder.cmake_build = fake_cmake_build
    module._run_verify_executable = lambda *_args: module.VERIFY_EXPECTED_OUTPUT
    builtins_lib = (
        module.COMPILER_RT_LIB_DIR / "x86_64-w64-windows-gnu" / "libclang_rt.builtins.a"
    )
    builtins_lib.parent.mkdir(parents=True)
    builtins_lib.write_text("builtins", encoding="utf-8")
    module._verify_target(triple)

    configure_event = runner.package_builder.events[-2]
    assert configure_event[0] == "cmake_configure"
    assert "-DTHIN_SYSTEM_NAME=Windows" in configure_event[1]
    assert f"-DTHIN_BUILTINS_LIB={builtins_lib}" in configure_event[1]
    assert runner.package_builder.events[-1] == (
        "cmake_build",
        [],
        module.VERIFY_BUILD_DIR / triple,
    )
