# LLVM Builder

所有构建脚本都通过 `BuilderRunner` 执行，并按
`configure -> build -> install -> verify -> package` 的顺序调用脚本中存在的阶段。

```bash
# 构建、验证并打包 GCC sysroot
uv run python3 src/BuilderRunner.py packages/sysroot_full.py \
  -DGCC_VERSION=15.2.0

# 构建 compiler-rt builtins（默认使用上面的 sysroot 输出）
uv run python3 src/BuilderRunner.py packages/compiler_rt.py \
  -DGCC_VERSION=15.2.0 -DLLVM_VERSION=22.1.8

# 构建 wasi-libc（默认使用 compiler-rt 输出）
uv run python3 src/BuilderRunner.py packages/wasi_libc.py \
  -DWASI_VERSION=32 -DLLVM_VERSION=22.1.8
```

可在 package 脚本后使用 `--target <triple>` 只处理指定 target，该参数可重复传入。
`-DKEY=VALUE` 可以出现在脚本路径前后；`-D` 比同名环境变量优先。
