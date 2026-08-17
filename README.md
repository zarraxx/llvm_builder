# LLVM Builder

所有构建脚本都通过 `BuilderRunner` 执行，并按
`configure -> build -> install -> verify -> package` 的顺序调用脚本中存在的阶段。

```bash
# 构建、验证并打包 GCC sysroot
uv run python3 src/BuilderRunner.py packages/sysroot_full.py \
  -DGCC_VERSION=15.2.0

# 整理、验证并打包 GCC/musl sysroot
uv run python3 src/BuilderRunner.py packages/sysroot_musl_full.py \
  -DGCC_VERSION=15.2.0

# 构建 glibc/musl compiler-rt builtins（自动下载对应的 full sysroot）
uv run python3 src/BuilderRunner.py packages/compiler_rt_builtins.py \
  -DLLVM_VERSION=22.1.8

# 从 glibc/musl full release 裁剪、验证并打包 thin sysroot
uv run python3 src/BuilderRunner.py packages/sysroot_thin.py \
  -DGCC_VERSION=15.2.0 -DMUSL_GCC_VERSION=15.2.0 \
  -DLLVM_VERSION=22.1.8

# 构建 wasi-libc（默认使用 compiler-rt 输出）
uv run python3 src/BuilderRunner.py packages/wasi_libc.py \
  -DWASI_VERSION=32 -DLLVM_VERSION=22.1.8
```

`sysroot_thin` 保留动态 glibc；对 musl 同时保留动态 `libc.so`、静态
`libc.a`、musl 兼容静态库和 CRT 文件。两类 sysroot 都会移除 GCC、
libstdc++、sanitizer 和 OpenMP runtime。musl 静态链接使用相同 LLVM 版本、
按 musl target triple 单独构建的 compiler-rt builtins。

可在 package 脚本后使用 `--target <triple>` 只处理指定 target，该参数可重复传入。
`-DKEY=VALUE` 可以出现在脚本路径前后；`-D` 比同名环境变量优先。
