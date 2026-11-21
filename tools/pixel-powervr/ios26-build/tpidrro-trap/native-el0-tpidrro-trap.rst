Generic native TPIDRRO read qualification
========================================

``ASOFT_NATIVE_EL0_TPIDRRO_TRAP=1`` selects a separate, opt-in native path for
the existing generic ``el0bench.elf`` guest. It preserves the guest's writable
``TPIDR_EL0`` while deliberately trapping reads of ``TPIDRRO_EL0`` and returning
the value held by QEMU's guest CPU state. Unset, empty or ``0`` leaves the
previous behavior unchanged. Other flag values are errors.

Why this mode exists
--------------------

The pinned benchmark writes ``TPIDRRO_EL0 = 0xabcd0000 | cpu_id`` in EL1. Its
T7 payload writes ``TPIDR_EL0 = 0x1234`` in EL0, makes 1,000 SVC round trips,
and checks both values. On the Pixel's initial native run, both CPUs completed
the guest but reported ``TPIDRRO_EL0 = 0`` and ``MISMATCH``. Direct native reads
returned the host register, so the existing trap emulator was not invoked.

The existing ``ASOFT_NATIVE_EL0_TPIDRRO=1`` mode is specialized for iOS. It
swaps reads of the two thread registers and treats the host's zero read-only
register as a CPU-number hint. It does not preserve the two independent
architectural values used by T7. The new mode is mutually exclusive with that
iOS mode and does not change its implementation or defaults.

Required configuration
----------------------

Use all of these settings::

    ASOFT_NATIVE_EL0=1
    ASOFT_NATIVE_EL0_REQUIRED=1
    ASOFT_NATIVE_EL0_STUBS=2
    ASOFT_NATIVE_EL0_TPIDRRO_TRAP=1

The flag requires between 1 and 32 native stub slots. In-process native
execution is rejected because its instruction lookup reads the modified
mirror rather than the original guest instruction. The executable memfd code
cache must be enabled. ``ASOFT_NATIVE_EL0_CODECACHE=0``, the iOS TPIDRRO swap
mode and ``ASOFT_NATIVE_EL0_PATCH_XO`` are rejected. Configuration failures
terminate even when the required-native flag was omitted. Fatal paths use
``_Exit(1)`` after flushing the diagnostic, including failures encountered
while a native/cache mutex is held.

Instruction and state behavior
------------------------------

The exact AArch64 word ``0xd53bd060 | Rt`` (``MRS Xt, TPIDRRO_EL0``) becomes
``0x00006000 | Rt`` (``UDF #(0x6000 | Rt)``) in the code copy. The UDF immediate
occupies the low 16 bits; it is not shifted by five. Every other instruction
word is left unchanged by this mode, including reads and writes of
``TPIDR_EL0``. The generic rewrite returns before all existing iOS, TPRO,
SSBS and counter-rewrite logic.

The stub reports the resulting SIGILL using the existing trap path. In stub
mode, ``fetch_insn`` reads the original instruction through QEMU's guest
memory, not the UDF in the copied page. ``emulate_mrs`` returns
``env->cp15.tpidrro_el[0]``, discards the result for ``Rt=31`` and advances the
guest PC by exactly four bytes. The writable guest thread pointer remains in
the stub's reported thread-pointer field and is restored on native resume.
The normal state-transfer path still preserves writes to ``TPIDR_EL0``.

Copied-code constraints
-----------------------

This is a deliberately restricted qualification mode:

* Every executable mapping must be read-only for the guest and must use an
  aligned 16 KiB code-cache page. Larger guest mappings are divided into
  those cache pages; executable mappings smaller than 16 KiB are rejected.
* Executable RAM must be backed by the first registered RAM fd. Other RAM-fd
  executable mappings, missing backing, unaligned offsets and private-copy
  substitutes are rejected. Ordinary non-executable data uses the existing
  RAM mapping path.
* Even a code page containing no TPIDRRO read is copied into the cache. The
  normal ``CC_CLEAN`` direct executable alias cannot bypass this mode.
* Too many rewrite sites for the cache metadata, an out-of-range frame or an
  exhausted cache terminates the qualification. No direct executable RAM
  mapping or TCG substitute is selected for a failed copied-code fill.
* Speculative neighbour filling is disabled. The worker independently checks
  executable fill descriptors before mmap. Any worker fill failure terminates
  the parent qualification instead of falling back to TCG for that failure.

The cache fd is created before the existing factory fork and is inherited by
workers. The ordinary guest RAM fd still reaches the factory through the
existing SCM_RIGHTS handoff. No GPU allocation, imported-memory provider or
new fd ownership/lifetime mechanism is added.

The executable cache reserves a sparse 1 GiB memfd and uses the existing
bounded frame/slot tables. A process file-size limit below that size prevents
initialization; file-size limits also apply to the 512 MiB guest RAM memfd.
Do not use such a limit to bound a diagnostic output file.

This mode retains existing guest translation and eligibility decisions,
including legitimate guest faults and TCG handling of kernel/unsupported
instructions. It does not promise native execution of every EL0 instruction.
It also does not establish correctness for concurrent writable aliases,
self-modifying code or guests that inspect modified instruction bytes as
data. It relies on the existing guest TLB/code-coherency implementation. The
pinned fixture's static read-only payload is the reviewed qualification scope.

Run and pass criteria
---------------------

The unchanged benchmark asset is SHA-256
``0454b4988e32f7476fd19c205343f436a702a70f69b1a5fb4d115c26ab64d98f``. Its
payload is one read-only 16 KiB executable page; its stack and demand memory
are writable and non-executable. No guest instruction or success expectation
is modified.

Run ``scripts/native-el0-tpidrro-trap-smoke.sh`` with the isolated package
directory as its only argument. It verifies all package hashes and performs
negative required-native and mutually-exclusive-mode checks before launching
the guest. The guest uses 512 MiB ordinary memfd RAM, two vCPUs and two stub
slots, with no GPU, disk or network. Stdin is explicitly ``/dev/null``, matching
``EngineService`` and the successful stdin-only phone control. That control
does not establish the underlying cause of the earlier terminal-dependent
stall.

The guest has a 30-second diagnostic bound plus a three-second forced-stop
grace period. A timeout is a failed qualification. A pass requires all of the
previous correctness and native-activity checks, plus:

* Both CPUs report the exact T7 values: writable pointer ``0x1234`` and
  read-only pointer ``0xabcd0000`` / ``0xabcd0001``, each with ``OK``.
* Both CPUs report at least two native TPIDRRO emulations, with last guest PC
  ``0x100000768``. The first read is T0 at ``0x100000154``; T0 alone cannot
  satisfy the native T7 witness.
* The new mode's ready message and positive code-copy/map-request counts
  are present. Map requests count descriptors issued by QEMU, not completed
  worker mappings; the native instruction witnesses establish execution.
* Both CPUs report their own T6/T10 success and ``[cpuN] EXIT 0 faults=...``.
  CPU0's exit alone is insufficient: a secondary CPU's fatal-park path also
  signals the completion counter that CPU0 waits for. Any CPU's nonzero exit,
  any ``MISMATCH``, copy ``check=BAD`` or native-policy failure rejects the run.

The final marker is ``NATIVE_TPIDRRO_TRAP_BENCH_PASS=1``. A shell pass would
qualify only that process identity. Ordinary-app execution, iOS boot, GPU
memory integration and complete descendant quiescence remain separate work.

Validation and limits
---------------------

``tests/unit/test-native-el0-tpidrro-rewrite.py`` compiles the actual rewrite,
emulator and state-transfer functions against small host CPU/frame models,
with undefined-behavior sanitization. It covers all 32 destination registers,
five distinct read-only values, instruction-selection negatives, single PC
advance, writable-pointer preservation and unchanged iOS swap/state behavior.

``tests/unit/test-native-el0-tpidrro-policy.py`` tests the actual option,
producer/worker mapping and cache-policy functions. It covers fatal mode
conflicts, lock-safe termination, copied clean pages, cache reuse/rewrite and
capacity/failure decisions with simulated cache scanning and storage.

``tests/unit/test-native-el0-tpidrro-log.py`` executes the actual shell checker
against CPU-prefixed synthetic logs, including T0-only and wrong-PC witnesses,
wrong T7 values labelled OK, missing evidence and mixed successful/failed exits.

These host tests do not execute AArch64 guest instructions or qualify Android
signal delivery. The Android translation unit and full executable must build
successfully, and the actual phone run must satisfy the strict witness before
the new mode is considered qualified.
