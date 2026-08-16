# RISC-V 64 Sysroot Support Design

## Goal

Add `riscv64-unknown-linux-gnu` to the full sysroot, thin sysroot, and
compiler-rt builtins releases. The thin sysroot keeps only the normal
`rv64gc/lp64d` runtime and removes alternate RISC-V multilib ABIs.

## Scope

The change covers:

- `packages/sysroot_full.py`
- `packages/sysroot_thin.py`
- `packages/compiler_rt_builtins.py`
- the full, thin, and compiler-rt release workflows
- focused automated tests for the target matrices and RISC-V thin layout

It does not change the GCC/crosstool-ng toolchain build, add another RISC-V
ABI, or refactor all target metadata into a new shared module.

## Full Sysroot

The full package treats `riscv64-unknown-linux-gnu` like the existing Linux
targets. It copies the complete GCC target prefix, sysroot, GCC runtime, and
multilib content from the upstream GCC bundle. Verification builds C and C++
samples with Clang and runs them through `qemu-riscv64`.

The full package therefore remains the complete source from which the thin
package can select one ABI.

## Thin Sysroot

The selected RISC-V ABI is the upstream toolchain default:

- ISA: `rv64gc`
- ABI: `lp64d`
- dynamic linker: `/lib/ld-linux-riscv64-lp64d.so.1`

The thin package copies only the default runtime directory and default linker
directory used by an unqualified `riscv64-unknown-linux-gnu` link. Existing
copy helpers operate on direct children and an explicit library whitelist, so
alternate multilib subdirectories are not copied. Structural verification
must additionally reject RISC-V library subdirectories that contain alternate
ABI runtime or link files.

The thin verification sample is compiled for the RISC-V triple and executed
with `qemu-riscv64` using the packaged sysroot.

## Compiler-RT Builtins

`riscv64-unknown-linux-gnu` is added to the normal sysroot target set. Its
builtins are compiled against the refreshed full sysroot and installed under
the existing per-target compiler-rt layout. No RISC-V-specific compiler-rt
flags are introduced unless the existing generic configuration fails in CI.

## Release Workflows

Each workflow gains an archive-content assertion for its RISC-V output:

- full: the RISC-V sysroot root, libc link file, and GCC runtime are present
- compiler-rt: the RISC-V builtins archive is present
- thin: the default RISC-V loader and libc link file are present, while known
  alternate multilib library paths are absent

The release sequence is strictly ordered:

1. Publish `sysroot_full-gcc15.2.0`.
2. Build and publish `compiler_rt_builtins-llvm22.1.8` from that full sysroot.
3. Build and publish `sysroot_thin-gcc15.2.0` from the refreshed full sysroot.

Each workflow must finish successfully before the next is triggered.

## Testing

Focused tests first assert that the current target tables and workflows do not
satisfy the RISC-V contract. Production changes then make those tests pass.
The tests cover target membership, dynamic linker and QEMU mappings, the full
and thin layouts, compiler-rt membership, and workflow archive assertions.

After unit tests pass, repository-wide tests and formatting/lint checks run.
The GitHub workflows provide the final cross-compile, QEMU execution, archive
layout, and release verification using the actual upstream toolchain bundle.

## Failure Handling

If the upstream default RISC-V library directories differ from `lib` and
`usr/lib`, the full workflow evidence is used to correct the explicit thin
layout before triggering the remaining workflows. A failed workflow does not
permit triggering the next release, and existing release assets are only
replaced by each workflow after build and archive checks succeed.
