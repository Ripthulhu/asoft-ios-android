# v3: move one verified CPU page

This isolated follow-up addresses one measured limitation. On the Pixel, v2
passed the legal Vulkan opaque-FD allocation/import round trip and the full
native offset-zero mapping. Its first offset-map check requested source page 5
but read page 0's pattern. It returned 4 before scatter writes. This observation
does not establish the behavior of every offset or identify the exporter's
implementation. The exact phone driver source revision has not been matched.

## Invocation and interpretation

```sh
timeout 30 ./opaque_fd_probe --move-page
```

The option retains the v2 Vulkan and full native-mapping phases, then selects
the new one-page move instead of v2's four-page offset-mapping experiment.
Without an option the v3 source still follows v2's original sequence.
`--no-fd-mmap` retains the Vulkan-only option.

The existing exit codes retain their meaning. Exit **5** adds
`RESULT=VULKAN_FD_MMAP_PASS_CPU_MOVE_UNSUPPORTED`: the preceding phases passed,
but the disposable full mapping, move syscall, or moved-page initial read did
not establish the needed CPU view. Mismatches after moved-page writes start
are failures (exit 1). Exit 0 with `--move-page` requires all its checks to pass.

## Exact scope

The probe uses the same eight-page allocation. It requires the allocation size
to equal the buffer size, so every word of the disposable full mapping can be
verified. It keeps both Vulkan mappings and the previously verified full FD
mapping intact throughout the experiment.

1. Create a separate full-allocation `MAP_SHARED` mapping at FD offset zero and
   a fresh one-page `PROT_NONE` anonymous destination reservation.
2. Read and verify every source word against the completed GPU's page-distinct
   fill. This also populates the source mapping before the move.
3. Move source page 5 with exactly
   `mremap(source + 5 * page, page, page, MREMAP_MAYMOVE | MREMAP_FIXED, slot)`.
   The destination belongs to this probe and cannot overlap the live source.
4. Verify every moved-page word before writing. Then write a page/word-specific
   pattern, check all eight pages through both Vulkan mappings and the retained
   full native mapping, and copy the canonical GPU buffer into an independent
   readback allocation. All seven unselected pages remain guards.
5. Fill the canonical buffer with new per-page GPU values, wait for its fence,
   then check all canonical CPU views and the moved page.

All GPU waits are bounded at five seconds. Only the imported, canonical
contiguous buffer is used by GPU commands. No GPU page gather, sparse binding,
repeated CPU mapping, forced page refault, driver-private operation, or mapping
of the Vulkan-provided pointers is part of this experiment. A pass establishes
only the checked CPU page movement and visibility for this retained allocation.

## Why this syscall is a plausible next test

The Linux man-pages project documents equal-size `MREMAP_FIXED` moves and
requires `MREMAP_MAYMOVE` with the fixed flag. It separately describes
`old_size == 0` shared-map cloning and `MREMAP_DONTUNMAP`; those are not this
experiment. See [mremap(2)](https://man7.org/linux/man-pages/man2/mremap.2.html).

In [Android common 6.12 mremap.c, tag android16-6.12-2025-06_r3](https://android.googlesource.com/kernel/common/+/refs/tags/android16-6.12-2025-06_r3/mm/mremap.c),
`vma_to_resize` accepts equal lengths before its expansion refusal for
`VM_DONTEXPAND`/`VM_PFNMAP`. `move_vma` moves page tables, checks `may_split`, and
honors an optional driver `mremap` callback. `mremap_to` still passes the adjusted
page offset to `get_unmapped_area`. Thus existing populated translations may
survive the move, but driver constraints can reject it. This source tag was
reviewed as a primary implementation reference, not identified as the phone's
exact kernel revision.

The Vulkan [opaque-FD handle contract](https://docs.vulkan.org/refpages/latest/refpages/source/VkExternalMemoryHandleTypeFlagBits.html)
does not guarantee POSIX mapping or page-remapping behavior. These phases are
explicitly native observations beyond the portable Vulkan import/export proof.

## Address ownership and failure cleanup

On success, the helper records only three intervals: the five-page source
prefix, the two-page source suffix, and the moved destination page. It never
unmaps across the vacated source page, which another thread could reuse.
Successful interval cleanup clears that interval's ownership immediately.

Android's `mremap_to` can unmap a fixed destination before later checks or
callbacks reject the operation. After **any attempted move failure**, the
helper marks its layout uncertain and refuses cleanup. The probe prints the
unsupported outcome and calls `_Exit(5)` immediately, after all previous GPU
work is fenced. It does not infer which destination or source intervals still
exist. Process teardown owns that exceptional cleanup.

## Host validation

`cpu_move_fixture.c` uses the exact `cpu_move.h` helper with an ordinary Linux
memfd. It checks full-source verification, page-5 identity, writes in both CPU
directions and all eight canonical pages/guards. It then safely claims the
vacated source hole using `MAP_FIXED_NOREPLACE`, writes a guard into it and
verifies that helper cleanup removes the owned prefix/suffix/destination while
preserving that separate mapping. A child process forces a real failed move,
checks cleanup refusal, and exits without repairing uncertain ranges.

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror cpu_move_fixture.c -o cpu_move_fixture
./cpu_move_fixture
python3 build.py --ndk /path/to/android-ndk-r29
```

The memfd fixture proves the helper's CPU mapping/ownership behavior only. It
does not establish opaque-FD semantics, GPU operation or Pixel compatibility.
The software Vulkan driver used for earlier host checks maps opaque-FD metadata
at offset zero, so its initial native payload check stops before this new phase.

## Architectural alternatives

Separate page-sized Vulkan allocations could avoid nonzero FD offsets by
exporting each allocation separately. That is a larger design change: 1 GiB
split into 4 KiB allocations would require 262,144 allocations before counting
imports, FDs or CPU VMAs. Vulkan exposes a finite
[`maxMemoryAllocationCount`](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceLimits.html).
Combining allocations into one GPU buffer requires a separately qualified
[sparse-resource design](https://docs.vulkan.org/spec/latest/chapters/sparsemem.html),
including its actual block granularity and external-buffer flags. The phone's
flags-zero capability queries and CPU mapping results do not supply that proof;
its reported `sparseResidencyAliased == false` remains a separate constraint.

The one-page move answers the immediate CPU-view question with the existing
small allocation. Runtime backing ownership, arbitrary gathers, shader BDA
access, guest-sized memory and iOS boot remain separate work.
