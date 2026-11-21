Required native EL0 initialization
==================================

Source patch base
-----------------

The native-required patch applies to QEMU source commit
``7a900afb62ddf94713e38ac5a4aafe1d42c9efa8``. It contains the native engine
change, this document, the phone script and their host tests. It does not
include ``meson.build`` or replace the separate Android Meson configuration
patch. Apply that Android patch as part of reconstructing the Android build;
the two patches touch separate files and can be applied together in either
order. The candidate relink reuses the frozen Android baseline's unchanged
objects and replaces only the native engine object.

Startup contract
----------------

Set both ``ASOFT_NATIVE_EL0=1`` and ``ASOFT_NATIVE_EL0_REQUIRED=1`` when a
native-disabled startup must fail. The new flag is opt-in: exactly ``1``
enables it; an absent flag, an empty value or ``0`` retains the existing
behavior. This is an initialization contract, not a guest performance or
GPU-compatibility claim.
Other values are configuration errors and exit with status 1; a misspelled
value such as ``true`` cannot silently disable the requirement.

With the requirement enabled, QEMU exits with status 1 and an actionable
``native-el0: required initialization failed:`` diagnostic for these cases:

* Native EL0 was not enabled with ``ASOFT_NATIVE_EL0``.
* The build does not contain the AArch64 Linux system-emulation native engine.
* The fixed native mirror or its guard cannot be reserved at the required
  address, including a kernel returning a different address.
* The mirror extent table cannot be allocated.
* A requested stub factory cannot be created.
* The executable code cache selected by the TPIDRRO stub mode cannot be created.
* Deferred per-vCPU native-context initialization returns failure. This covers
  the context limit, alternate-stack setup and seccomp setup paths.
* The factory stops answering a command, cannot receive the RAM fd, fails to
  spawn a worker, or a worker exits or fails to become ready within its bound.
  Required mode waits for every selected vCPU thread's signal-frame readiness
  within the same five-second worker-startup deadline.

After constructor initialization it prints
``required initialization ready mode=stubs`` or ``mode=in-process``, followed
by ``guest execution not yet observed``. The requirement also enables the
existing exit statistics, even if ``ASOFT_NATIVE_EL0_STATS`` is unset or zero.
It does not add a successful-execution claim or a new guest progress counter.
Fatal initialization paths flush their diagnostic and call ``_Exit(1)``.
They deliberately bypass exit handlers because deferred startup can fail while
the stub-pool mutex is held. Successful normal exits still print statistics.

The surrounding mechanism is deliberately unchanged when the new flag is
absent. In particular, normal non-required builds retain their existing
fallback and optional-code-cache behavior.

Call chain and limits
---------------------

The constructor reserves the mirror and initializes the selected mode before
QEMU processes its machine/accelerator arguments. The ARM CPU installs
``native_el0_try`` in ``arm_tcg_ops.try_native``. The TCG execution loop calls
that hook before translating another block. Eligible AArch64 EL0 code enters
the native mirror; EL1 and above continue to use the existing TCG kernel path.
Therefore a native benchmark still uses ``-accel tcg,thread=multi``. Selecting
KVM bypasses this hook; constructor success does not verify the accelerator
chosen later from the command line.

Context setup is partly deferred until the first eligible EL0 code. Stub RAM
fd transfer and worker readiness are checked when requested later, rather than
being established by the constructor. Page mapping, guest MMU state, vCPU
count, signal handling, later failures during guest execution and instruction
eligibility are not all established by startup. A normal guest can
also return to TCG for unsupported instructions or transient scheduling
conditions. Those cases are not changed into unconditional failures by this
startup flag. There is no active-progress watchdog in this patch.

The ``enters`` counter is incremented around an entry attempt, so a positive
count alone is not conclusive proof of useful native execution. Qualify it
with positive native SVC counts, nonzero native time and a completed guest
whose correctness checks pass. A timeout, absent counters or an incomplete
guest result remains a failed or unqualified run even after a ready message.

Ordinary memfd benchmark
-----------------------

``scripts/native-el0-memfd-smoke.sh`` is a bounded recipe using the existing
``asoft-ios-android`` ``EngineService.java`` invocation. It uses the ``virt``
machine with 512 MiB of ordinary ``memory-backend-memfd`` RAM, two vCPUs and
two native stub slots. It does not configure a GPU, guest disk or network, and
does not require iOS images. Its ``el0bench.elf`` input is the existing app
asset, SHA-256
``0454b4988e32f7476fd19c205343f436a702a70f69b1a5fb4d115c26ab64d98f``.

Use an isolated package directory containing the candidate executable named
``qemu-system-aarch64``, its exact matched libraries under ``lib/``, that
``el0bench.elf`` and a ``SHA256SUMS`` file. Invoke the script with this directory
as its only argument. It first verifies hashes, then makes a negative
``-version`` check with native disabled and required enabled. If that does not
exit 1 with the expected message, it refuses to start the guest. This catches
accidental use of an older engine that ignores the required flag.

The guest run has a 30-second outer timeout with a 3-second forced-stop grace
period. This is a diagnostic limit, stricter than the app's default 120-second
limit; it is not a claim that every supported device completes within 30 seconds.
A pass requires exit status zero, the requested stub-mode ready
message, positive native entry/SVC counts, positive native time, a spawned
stub, ``[cpu0] EXIT 0 faults=...`` from the guest, successful floating-point and copy checks,
and no mismatch or native-fallback diagnostics. All outputs go into a new
directory below the package's ``results/``. No timeout is treated as a pass.
The existing guest's ``kprintf`` prefixes its lines with ``[cpuN] ``. CPU0 waits
for the other CPUs before reporting completion. The checker requires CPU0's
zero exit and rejects any CPU's nonzero signed exit code, even if another
line reports success. Unprefixed or secondary-only completion cannot pass.
The guest's T10 copy result is lowercase ``check=ok`` on success and uppercase
``check=BAD`` on failure. These exact strings were verified in the existing
guest binary's payload; T6 uses uppercase ``OK`` independently.

A successful shell run qualifies only the identity and permissions under
which it ran. It does not replace an ordinary-app-UID test or establish GPU
shared-memory behavior. The Pixel PowerVR producer/adoption backend is not
part of this patch or this benchmark.

Host validation
---------------

``python3 tests/unit/test-native-el0-required.py`` compiles the production
``native-el0.c`` unsupported-build branch with minimal type/header glue. It
checks constructor exit behavior across 12 required/enabled combinations.
It also compiles the verbatim production option checks and ``stub_spawn``
function with simulated factory, clock and readiness dependencies. The further
31 cases cover enabled-option conflicts, factory/child/thread failures,
successful and delayed readiness, invalid flag values, and a locking exit
handler that must be bypassed on fatal failure. Every fixture process has a
two-second host timeout. These verify initialization decisions, not real
AArch64 mappings, process primitives or guest code.
The supported Android branch must also be compiled and linked using the
actual QEMU configuration before any device test.

``python3 tests/unit/test-native-el0-memfd-log.py`` exercises the phone script's
actual shell result-checking function with fifteen synthetic log cases. The
guest lines model the existing ELF's CPU prefixes and exact success/failure
spelling; their counts and timings are synthetic. It accepts CPU0 completion
with lowercase T10 success, and rejects a BAD result even when another line
reports success. It rejects unprefixed or secondary-only completion and any
CPU's nonzero signed exit, including mixed successful/failed exit lines. It
also rejects uppercase T10 ``OK``, zero native SVC/time evidence, an incomplete
guest and a floating-point mismatch.
