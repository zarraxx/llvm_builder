from pathlib import Path
from types import SimpleNamespace

import pytest

from BuilderRunner import BuilderRunner


class FakeDependency:
    def __init__(self, name: str, version: str, filename: str):
        self.name = name
        self.version = version
        self.filename = filename
        self.url = f"https://example.test/{filename}"
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
        filename = filename_fmt.replace("{{name}}", name).replace(
            "{{version}}", version
        )
        for key, value in kwargs.items():
            filename = filename.replace(f"{{{{{key}}}}}", str(value))
        return FakeDependency(name, version, filename)

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
    ["sysroot_full.py", "compiler_rt.py", "wasi_libc.py"],
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


@pytest.mark.parametrize(
    ("package_name", "target"),
    [
        ("compiler_rt.py", "x86_64-unknown-linux-gnu"),
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
    if package_name == "compiler_rt.py":
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
    if package_name == "compiler_rt.py":
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
    assert tar_calls == [("caf", archive, "-C", module.DEST_DIR, ".")]
