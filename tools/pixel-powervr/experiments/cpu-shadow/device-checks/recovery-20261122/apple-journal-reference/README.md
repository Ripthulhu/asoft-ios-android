# Apple HFS journal reader on Pixel

Apple's pinned **fsck_hfs** journal reader matched the Resume5 diagnostic's
49 callback records in order, covering all six active lists and 318,976
payload bytes. For each callback the target byte offset, length and HFS
payload checksum matched. The reader emitted zero further callbacks beyond
the advertised journal end. The Android run used the retained 8 MiB extract
and verified its SHA-256 and the diagnostic receipt before and after testing.

| Synthetic fixture | Apple reader observation |
| --- | --- |
| Empty at the advertised end | One callback from the active list |
| Consecutive sequence after the advertised end | One active and one additional callback |
| Stale sequence after the advertised end | One callback from the active list |

The adapter reads a sealed memory copy through a read-only descriptor. The
callback records numeric comparisons in a child pipe. The published summary
contains counts only. The process ran as the Android shell UID. No guest VM,
image attachment, filesystem replay or fsck took place during these tests.

The first test build capped the whole Android address space. That prevented
Scudo from reserving virtual memory and triggered a nested Android crash
reporter chain. The chain was stopped after verifying its process ancestry.
The successful build limits journal-reader allocations through a linker
wrapper. A final device check found zero live reader, crash reporter, QEMU
or fsck processes.

| Retained evidence | SHA-256 |
| --- | --- |
| Resume5 journal extract | `0b33a53eac6f0b19b5f74a0b8e7f6109f5877a4778ce0827f37e92197d7a73db` |
| Resume5 diagnostic receipt | `6d1829c3a1a4982e4cdcf11a6854fb862f93a12d5025a783331d4a578de28efc` |
| Reference executable | `58dcd10bffe9303405a1492d2d60ba7592302845b352e4e91809205a3a4540c8` |
| Reference comparison script | `1882d5960aaf234278d082e20db4184813ced8a82f5ab68a77e69b5d43fc0374` |
| Reference result | `fb76b271a562721d571b6dfdc91eef784db91ca9ae57cfec97180c00556279ca` |

The successful run is retained on the Pixel at
`/data/local/tmp/asoft-rd-journal-reference-02/reference-result.json`.

## Build and run

Download Apple's unchanged
[fsck_journal.c](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/lib_fsck_hfs/fsck_journal.c)
and
[fsck_journal.h](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/lib_fsck_hfs/fsck_journal.h)
from commit `d1bac2f062e6e9c0dfcce302d9aacb10173d0eea`. Verify the hashes
before building. The Apple sources and device binary are kept off this branch.

| Apple source | SHA-256 |
| --- | --- |
| `fsck_journal.c` | `3c70c6a87a7bca185c7ba9b7ef6b16bbb365dbc5a1c443ac5496ed41926bc722` |
| `fsck_journal.h` | `3392e5d15c875fa09957cc04be650a3a26b25cf25e5ba830367e00d5b5711654` |

With the Android NDK ARM64 API 29 compiler, the adapter and the two downloaded
files in the same build directory, build the two translation units and link
the allocation bound.

~~~sh
"$CC" -std=c11 -fblocks -O2 -I compat -c fsck_journal.c -o fsck_journal.o
"$CC" -std=c11 -fblocks -O2 -I compat -c observe_journal.c -o observe_journal.o
"$CC" fsck_journal.o observe_journal.o -Wl,-z,defs -Wl,--wrap=malloc \
  -Wl,--strip-all -o observe-journal
~~~

The tested compiler was NDK `30.0.14904198`. Run
`compare_journal.py BINARY DIAGNOSTIC_DIRECTORY` with Android Python 3 in
a fresh work directory. Keep the binary executable by the shell UID. The
script binds the diagnostic and extract to the recorded hashes and sends
only a sealed 8 MiB memory copy or a built-in synthetic fixture to the
executable.

## Recovery still required

This reader is the cache simulation used by Apple's read-only checker. A
recovery route needs to commit the journal on a disposable volume, prove a
clean unmount and empty journal, then pass a separate read-only fsck before
using a fresh saved Data descendant.

Apple's published
[LiveFiles HFS implementation](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/livefiles_hfs_plugin/lf_hfs_vfsops.c#L104)
has a user-space mount-and-replay routine. A read-only scan of all 203 leaf
nodes and 3,024 catalog records of the pinned prepared ramdisk found
`fsck_hfs`, `mount_hfs`, and `hfs.util`. The exact filenames
`livefiles_hfs`, `livefiles_hfs.dylib`, and `livefiles_hfs_tester` had
zero catalog matches. The stock mount previously received a
[System Policy denial](../ramdisk-capability-probe/RESULT-06.md).
Durable replay still needs a supported HFS-capable Darwin environment.
