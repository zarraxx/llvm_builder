# RISC-V 64 Sysroot Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish full sysroot, thin default-ABI sysroot, and compiler-rt builtins artifacts for `riscv64-unknown-linux-gnu`.

**Architecture:** Extend the existing explicit target tables rather than introducing shared target metadata. The full package retains the upstream GCC multilib tree, while the thin package selects only direct files from the default `lib` and `usr/lib` directories, which retains `rv64gc/lp64d` and drops nested alternate ABI directories.

**Tech Stack:** Python 3.13, pytest, GitHub Actions YAML, GCC/glibc sysroots, LLVM/Clang, compiler-rt, QEMU user-mode emulation.

---

### Task 1: Add Failing RISC-V Package Contract Tests

**Files:**
- Modify: `test/test_builder_runner.py`

- [x] **Step 1: Add a target-matrix test**

Load `sysroot_full.py`, `sysroot_thin.py`, and `compiler_rt_builtins.py` through `BuilderRunner`, then assert:

```python
triple = "riscv64-unknown-linux-gnu"
assert triple in full.TARGETS
assert full.TARGET_SHORT_NAMES[triple] == "riscv64-linux"
assert full.QEMU_COMMANDS[triple] == "qemu-riscv64"
assert thin.TARGET_LAYOUTS[triple] == ("lib", "usr/lib")
assert thin.DYNAMIC_LINKERS[triple] == "/lib/ld-linux-riscv64-lp64d.so.1"
assert thin.QEMU_COMMANDS[triple] == "qemu-riscv64"
assert triple in builtins.SYSROOT_TARGETS
```

- [x] **Step 2: Add a thin-layout test**

Create a synthetic RISC-V full sysroot with default runtime files in `lib`, default link files in `usr/lib`, and alternate ABI files in nested multilib directories. Build the thin target and assert the default loader/libc are retained and all nested multilib directories are absent.

- [x] **Step 3: Run the focused tests and verify RED**

Run:

```bash
PYTHONPATH=src uv run --with pytest pytest test/test_builder_runner.py -k riscv64 -vv
```

Expected: failures because all three production target tables currently omit `riscv64-unknown-linux-gnu`.

### Task 2: Extend Full, Thin, and Compiler-RT Packages

**Files:**
- Modify: `packages/sysroot_full.py`
- Modify: `packages/sysroot_thin.py`
- Modify: `packages/compiler_rt_builtins.py`

- [x] **Step 1: Extend the full target mappings**

Add:

```python
"riscv64-unknown-linux-gnu"
"riscv64-unknown-linux-gnu": "riscv64-linux"
"riscv64-unknown-linux-gnu": "qemu-riscv64"
```

to `TARGETS`, `TARGET_SHORT_NAMES`, and `QEMU_COMMANDS` respectively.

- [x] **Step 2: Extend the thin target mappings**

Add:

```python
"riscv64-unknown-linux-gnu": ("lib", "usr/lib")
"riscv64-unknown-linux-gnu": "/lib/ld-linux-riscv64-lp64d.so.1"
"riscv64-unknown-linux-gnu": "qemu-riscv64"
```

to `TARGET_LAYOUTS`, `DYNAMIC_LINKERS`, and `QEMU_COMMANDS`. Keep the existing non-recursive runtime whitelist and explicit link-file copy logic so alternate multilib directories are excluded.

- [x] **Step 3: Extend compiler-rt target membership**

Add `riscv64-unknown-linux-gnu` to `SYSROOT_TARGETS` so the default all-target build produces its builtins archive.

- [x] **Step 4: Run the focused tests and verify GREEN**

Run:

```bash
PYTHONPATH=src uv run --with pytest pytest test/test_builder_runner.py -k riscv64 -vv
```

Expected: all RISC-V target and thin-layout tests pass.

### Task 3: Add Release Archive Assertions

**Files:**
- Modify: `.github/workflows/sysroot-release.yml`
- Modify: `.github/workflows/compiler-rt-builtins-release.yml`
- Modify: `.github/workflows/sysroot-thin-release.yml`
- Modify: `test/test_builder_runner.py`

- [x] **Step 1: Add failing workflow contract tests**

Read each workflow as text and assert it checks the exact RISC-V release path:

```text
sysroot_full-gcc${GCC_VERSION}/riscv64-unknown-linux-gnu/sysroot/usr/lib/libc.so
compiler_rt_builtins-llvm${LLVM_VERSION}/lib/clang/${LLVM_VERSION%%.*}/lib/riscv64-unknown-linux-gnu/libclang_rt.builtins.a
sysroot_thin-gcc${GCC_VERSION}/riscv64-unknown-linux-gnu/sysroot/lib/ld-linux-riscv64-lp64d.so.1
```

- [x] **Step 2: Run the workflow contract test and verify RED**

Run:

```bash
PYTHONPATH=src uv run --with pytest pytest test/test_builder_runner.py -k riscv64_workflow -vv
```

Expected: failures because the workflows currently validate only the archive root.

- [x] **Step 3: Update archive checks**

In each workflow, write `tar -tf` output to a manifest and use `grep -Fqx` to verify the RISC-V path. The full workflow also checks `lib/gcc/riscv64-unknown-linux-gnu/${GCC_VERSION}/libgcc.a`; the thin workflow checks `usr/lib/libc.so` and rejects nested entries below its default `lib` and `usr/lib` directories.

- [x] **Step 4: Run the workflow contract test and verify GREEN**

Run:

```bash
PYTHONPATH=src uv run --with pytest pytest test/test_builder_runner.py -k riscv64_workflow -vv
```

Expected: all workflow assertions pass.

### Task 4: Verify, Commit, Push, and Publish

**Files:**
- Verify all modified files

- [x] **Step 1: Run local verification**

Run:

```bash
PYTHONPATH=src uv run --with pytest pytest -vv
uv run --with ruff ruff check .
git diff --check
```

Expected: all tests pass, Ruff reports no errors, and Git reports no whitespace errors.

- [ ] **Step 2: Commit implementation**

```bash
git add packages test .github/workflows docs/superpowers/plans/2026-08-16-riscv64-sysroot-support.md
git commit -m "Add riscv64 sysroot releases"
```

- [ ] **Step 3: Push main**

```bash
git push origin main
```

- [ ] **Step 4: Run full sysroot release and wait for success**

```bash
gh workflow run sysroot-release.yml -f gcc_version=15.2.0 -f llvm_version=22.1.8
run_id="$(gh run list --workflow sysroot-release.yml --commit "$(git rev-parse HEAD)" --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "$run_id" --exit-status
```

- [ ] **Step 5: Run compiler-rt release and wait for success**

```bash
gh workflow run compiler-rt-builtins-release.yml -f llvm_version=22.1.8
run_id="$(gh run list --workflow compiler-rt-builtins-release.yml --commit "$(git rev-parse HEAD)" --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "$run_id" --exit-status
```

- [ ] **Step 6: Run thin sysroot release and wait for success**

```bash
gh workflow run sysroot-thin-release.yml -f sysroot_full_gcc_version=15.2.0 -f llvm_version=22.1.8
run_id="$(gh run list --workflow sysroot-thin-release.yml --commit "$(git rev-parse HEAD)" --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "$run_id" --exit-status
```

- [ ] **Step 7: Verify release assets**

Use `gh release view` and the published checksum files to confirm all three release tags point at the new commit and expose non-empty archives containing the required RISC-V paths.
