import argparse
import hashlib
import importlib.util
import os
import sys
from os import PathLike
from pathlib import Path
from types import ModuleType
from typing import Any

from python_shell import Shell

from PackageBuilder import PackageBuilder, PackageBuilderWithPreparedClang


class _CommandProxy:
    def __init__(
        self,
        command: Any,
        defaults: dict[str, Any],
    ) -> None:
        self._command = command
        self._defaults = defaults

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # 调用时显式传入的参数优先级更高
        options = self._defaults.copy()
        options.update(kwargs)

        return self._command(*args, **options)

    def __getattr__(self, name: str) -> Any:
        # 保留原 Command 对象的属性访问
        # 例如 command.output、command.errors、command.return_code
        return getattr(self._command, name)

    def __repr__(self) -> str:
        return repr(self._command)


class ShellWithDefaults:
    def __init__(
        self,
        shell: Any,
        **defaults: Any,
    ) -> None:
        self._shell = shell
        self._defaults = defaults

    def __getattr__(self, command_name: str) -> Any:
        if command_name == "last_command":
            return self._shell.last_command

        command = getattr(self._shell, command_name)

        return _CommandProxy(
            command=command,
            defaults=self._defaults,
        )

    def __call__(self, command_name: str) -> Any:
        # 支持 MyShell("2to3") 这种命令名
        return getattr(self, command_name)

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(dir(self._shell)))


MyShell = ShellWithDefaults(
    Shell,
    stdout=None,
    stderr=None,
)


class BuilderRunner:
    def __init__(
        self,
        workspace: PathLike,
        package_file: PathLike | str,
        builder_type: type[PackageBuilder] = PackageBuilderWithPreparedClang,
        builder_kwargs: dict[str, Any] | None = None,
    ):
        self.workspace = Path(workspace).resolve()
        self.package_file = Path(package_file).resolve()

        if not self.package_file.is_file():
            raise FileNotFoundError(f"Python 文件不存在：{self.package_file}")

        if self.package_file.suffix != ".py":
            raise ValueError(f"不是 Python 源文件：{self.package_file}")

        self.package_builder = builder_type(
            self.workspace,
            **(builder_kwargs or {}),
        )
        name = self.package_file.stem
        self.package_builder.name = name
        self.path_hash = hashlib.sha256(
            str(self.package_file).encode("utf-8")
        ).hexdigest()[:12]
        self.module_name = f"_dynamic_{self.package_file.stem}_{self.path_hash}"
        self.module = None

    def load_package_script(self, custom_dict: dict | None = None) -> ModuleType:
        self.package_builder.prepare_builder()

        spec = importlib.util.spec_from_file_location(
            self.module_name,
            self.package_file,
        )

        if spec is None or spec.loader is None:
            raise ImportError(f"无法创建模块加载器：{self.package_file}")

        self.module = importlib.util.module_from_spec(spec)

        injected_values = {
            "builder": self.package_builder,
            "Shell": MyShell,
            "source": self.package_builder.add_source_dependence,
            "tool": self.package_builder.add_tool_dependence,
            "prebuild": self.package_builder.add_prebuild_dependence,
        }
        custom_values = custom_dict or {}
        # Runner 注入的 DSL 名称不允许被 -D 参数覆盖。
        module_dict = {**custom_values, **injected_values}

        def func_env(key: str, default_value: Any = None) -> Any:
            if key in custom_values:
                return custom_values[key]
            return os.environ.get(key, default_value)

        self.module.__dict__.update(module_dict)
        self.module.__dict__["env"] = func_env

        # 提前注册，使模块加载期间可以正常进行部分导入操作
        sys.modules[self.module_name] = self.module

        try:
            spec.loader.exec_module(self.module)
        except Exception:
            # 加载失败时避免留下半初始化模块
            sys.modules.pop(self.module_name, None)
            raise

        name = getattr(self.module, "__PACKAGE_NAME__", self.package_builder.name)
        version = getattr(
            self.module, "__PACKAGE_VERSION__", self.package_builder.version
        )
        self.package_builder.name = name
        self.package_builder.version = version
        return self.module

    def execute(self) -> None:
        package_builder = self.package_builder
        module = self.module

        if module is None:
            raise RuntimeError("必须先加载 package 脚本才能执行")

        package_builder.extract_tools_dependencies()
        package_builder.extract_prebuild_dependencies()
        package_builder.extract_source_dependencies()

        for stage in ("configure", "build", "install", "verify", "package"):
            stage_func = getattr(module, stage, None)
            if stage_func is None:
                print(f"Skip {stage}")
                continue

            print(f"{stage.capitalize()}:")
            stage_func()


def parse_define(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"-D 参数必须是 key=value 格式：{value!r}")

    key, value = value.split("=", 1)

    if not key:
        raise argparse.ArgumentTypeError("-D 参数的 key 不能为空")

    return key, value


def main():

    if os.environ.get("WORKSPACE"):
        workspace = Path(os.environ["WORKSPACE"]).resolve()
    else:
        workspace = Path.cwd()

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-D",
        dest="defines",
        action="append",
        type=parse_define,
        default=[],
        metavar="KEY=VALUE",
        help="定义变量，可以重复指定",
    )

    args, package_args = parser.parse_known_args()

    if not package_args:
        parser.error("必须指定 package Python 文件")

    defines = dict(args.defines)

    # 第一个非 -D 参数是 package 脚本，其余参数传给该脚本。
    package_file, *package_argv = package_args
    builder_kwargs = {}
    if llvm_version := defines.get("LLVM_VERSION"):
        builder_kwargs["llvm_version"] = llvm_version

    runner = BuilderRunner(
        workspace=workspace,
        package_file=package_file,
        builder_kwargs=builder_kwargs,
    )
    custom_dict = dict(defines)
    custom_dict["__sys_argv__"] = package_argv

    runner.load_package_script(custom_dict)
    runner.execute()


if __name__ == "__main__":
    main()
