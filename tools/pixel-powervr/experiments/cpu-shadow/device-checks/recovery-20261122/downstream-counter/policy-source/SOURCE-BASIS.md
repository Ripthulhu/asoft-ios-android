# Counter guard correction: qualified QEMU source basis

The firstboot guard rejected attempt `07-0002` because its `query-blockstats` response contained a named default `floppy0` backend in addition to `root`. The qualified QEMU implementation can create and report that empty backend even when the machine has no attached floppy device. The corrected guard accepts only the two reviewed inventories—`root` alone, or `root` plus this exact empty default backend—and requires a new post-stop `query-block` response to prove the latter has no inserted medium. It retains the typed zero-counter checks for every returned top-level, parent, and backing row.

This source analysis does not turn the old attempt into a pass. The saved `07-0002` event contains no `query-block` response. A new execution must collect that proof and satisfy all existing supervision, sync, native-witness, cleanup, source, session, and checkpoint gates.

## Immutable source identity

Repository: `https://github.com/alpersamur3/qemu-sptm`.

| Identity | Value |
| --- | --- |
| Base commit used for these source snapshots | `7a900afb62ddf94713e38ac5a4aafe1d42c9efa8` |
| Qualified CPU-shadow source head | `755b88fad8a2771a8e3e207133a54898b740cd7f` |
| Qualified source tree | `d1def5a49eaec302e46d8fa28aeaf5a227d02ecb` |
| Durable integration patch SHA-256 | `69276e34359da92baff5584a45e5da26d0a3f8d8d8f9196ede0d339f0b88ffab` |

The integration patch recorded in `asoft-ios-android/tools/pixel-powervr/patches/cpu-shadow/qemu/source.json` does not modify any of the seven source files below. The recorded Android build patch at `tools/pixel-powervr/ios26-build/reconstruction/provenance/qemu-android-build.patch` changes only `meson.build`. These base bytes therefore apply to the recorded qualified source tree. This correction rebuilds and executes no QEMU binary.

Every retrieved file is retained under the absolute directory:

`/workspace/scratch/abcabc3f01ae/firstboot-counter-recovery/guard-fix/source-basis/7a900afb62ddf94713e38ac5a4aafe1d42c9efa8/`

`source-basis.json` records each complete local path, immutable raw source URL, byte length, and SHA-256. The code excerpts below are copied verbatim from those retained sources; locations are within this exact commit, not a moving upstream branch.

| Source file | Relevant definitions |
| --- | --- |
| `system/vl.c` | `default_floppy`, `FD_OPTS`, `default_drive`, `configure_blockdev`, default-device disabling |
| `hw/arm/vresearch.c` | VResearch machine-class defaults |
| `blockdev.c` | `IF_FLOPPY` naming, `drive_new`, empty-drive `blk_new`, monitor backend registration |
| `block/block-backend.c` | `blk_new`, attached-device identity, removable/tray/lock/I/O-status predicates |
| `block/qapi.c` | `bdrv_query_info`, `qmp_query_block`, `qmp_query_blockstats`, `bdrv_query_bds_stats` |
| `block/accounting.c` | `block_account_one_io` failure counting and timing policy |
| `qapi/block-core.json` | `BlockInfo` field optionality and `account_failed` contract |

## Why an empty `floppy0` backend exists

`system/vl.c` initializes `default_floppy` to 1. It disables that default when defaults are disabled or the machine class sets `no_floppy`. The frozen firstboot launch does not pass `-nodefaults`, and the qualified VResearch machine class sets `no_cdrom` but does not set `no_floppy`.

The relevant call in `configure_blockdev` is:

```c
    default_drive(default_floppy, snapshot, IF_FLOPPY, 0, FD_OPTS);
```

`FD_OPTS` is the empty string. `default_drive` calls `drive_add(type, index, NULL, optstr)`, then `drive_new`, and marks the result as default. In `blockdev.c`, `IF_FLOPPY` maps to `"floppy"`; the no-explicit-ID branch constructs the name `floppy0` for this index.

The empty-drive branch in `blockdev.c` constructs a backend without opening a `BlockDriverState`:

```c
    if ((!file || !*file) && !qdict_size(bs_opts)) {
        BlockBackendRootState *blk_rs;

        blk = blk_new(qemu_get_aio_context(), 0, BLK_PERM_ALL);
        blk_rs = blk_get_root_state(blk);
        blk_rs->open_flags    = bdrv_flags | (read_only ? 0 : BDRV_O_RDWR);
        blk_rs->detect_zeroes = detect_zeroes;

        qobject_unref(bs_opts);
```

The common path subsequently registers the named backend with `monitor_add_blk`. `blk_new` in `block/block-backend.c` uses `g_new0(BlockBackend, 1)`: there is initially no attached device, device-operations table, or enabled I/O-status facility. The empty-drive construction path does not attach a device or enable I/O status. The existence of this backend alone does not imply a floppy medium or extra guest disk.

## Why the complete `query-block` shape is exactly four fields

The qualified `blk_dev_has_removable_media` implementation is explicit that an unattached backend is removable:

```c
/*
 * Does @blk's attached device model have removable media?
 * %true if no device model is attached.
 */
bool blk_dev_has_removable_media(BlockBackend *blk)
{
    GLOBAL_STATE_CODE();
    return !blk->dev || (blk->dev_ops && blk->dev_ops->change_media_cb);
}
```

This is why the corrected predicate requires `removable is True`. The earlier, uninstalled candidate incorrectly required false; its historical test receipts are retained but are not the final validation receipt.

The complete construction in `block/qapi.c:bdrv_query_info` is:

```c
static void GRAPH_RDLOCK
bdrv_query_info(BlockBackend *blk, bool flat, BlockInfo **p_info, Error **errp)
{
    BlockInfo *info = g_malloc0(sizeof(*info));
    BlockDriverState *bs = blk_bs(blk);
    char *qdev;

    /* Skip automatically inserted nodes that the user isn't aware of */
    bs = bdrv_skip_implicit_filters(bs);

    info->device = g_strdup(blk_name(blk));
    info->type = g_strdup("unknown");
    info->locked = blk_dev_is_medium_locked(blk);
    info->removable = blk_dev_has_removable_media(blk);

    qdev = blk_get_attached_dev_id(blk);
    if (qdev && *qdev) {
        info->qdev = qdev;
    } else {
        g_free(qdev);
    }

    if (blk_dev_has_tray(blk)) {
        info->has_tray_open = true;
        info->tray_open = blk_dev_is_tray_open(blk);
    }

    if (blk_iostatus_is_enabled(blk)) {
        info->has_io_status = true;
        info->io_status = blk_iostatus(blk);
    }

    if (bs && bs->drv) {
        info->inserted = bdrv_block_device_info(blk, bs, flat, errp);
        if (info->inserted == NULL) {
            goto err;
        }
    }

    *p_info = info;
    return;

 err:
    qapi_free_BlockInfo(info);
}
```

The associated schema in `qapi/block-core.json` confirms which fields are optional:

```python
{ 'struct': 'BlockInfo',
  'data': {'device': 'str', '*qdev': 'str', 'type': 'str', 'removable': 'bool',
           'locked': 'bool', '*inserted': 'BlockDeviceInfo',
           '*tray_open': 'bool', '*io-status': 'BlockDeviceIoStatus' } }
```

| Field | Qualified empty-backend behavior |
| --- | --- |
| `device` | Always emitted, from the registered name `floppy0`. |
| `type` | Always emitted as the compatibility value `unknown`. It is not conditional. |
| `locked` | Always emitted; `blk_dev_is_medium_locked` returns false without a device lock callback. |
| `removable` | Always emitted; `blk_dev_has_removable_media` returns true when no device is attached. |
| `qdev` | Omitted: `blk_get_attached_dev_id_or_path` returns an empty string without a device. |
| `tray_open` | Omitted: `blk_dev_has_tray` requires a non-null device-operations table with a tray callback. |
| `io-status` | Omitted: `blk_iostatus_is_enabled` requires the explicitly enabled flag as well as an applicable error policy; the zero-initialized flag remains false. |
| `inserted` | Omitted: the empty backend has no `BlockDriverState`. |

Thus the only accepted default-floppy `query-block` object is:

```json
{"device":"floppy0","type":"unknown","locked":false,"removable":true}
```

Object key order is immaterial. The guard requires the exact key set and actual boolean identities, so inserted media, qdev/node metadata, extra status fields, and integer substitutes for booleans are refused. This is a qualified implementation policy, not a generic allowance for arbitrary empty-looking backends.

## Why both QMP commands report that backend

`block/qapi.c:qmp_query_block` iterates the backend inventory and skips only an unnamed backend with no attached device:

```c
    for (blk = blk_all_next(NULL); blk; blk = blk_all_next(blk)) {
        BlockInfoList *info;

        if (!*blk_name(blk) && !blk_get_attached_dev(blk)) {
            continue;
        }

        info = g_malloc0(sizeof(*info));
        bdrv_query_info(blk, flat, &info->value, &local_err);
```

`qmp_query_blockstats` without `query-nodes=true` uses the same backend iteration and skip condition. It obtains `bdrv_query_bds_stats(blk_bs(blk), true)`, adds the backend name and optional attached-device identifier, and fills top-level backend counters through `bdrv_query_blk_stats`.

The no-node branch in `bdrv_query_bds_stats` is:

```c
    s = g_malloc0(sizeof(*s));
    s->stats = g_malloc0(sizeof(*s->stats));

    if (!bs) {
        return s;
    }
```

For named, unattached, empty `floppy0`, the resulting top-level statistics object therefore contains exactly `device` and `stats`, without `node-name`, `qdev`, `parent`, or `backing`. The corrected guard demands that exact top-level shape as well as the independent no-medium `query-block` witness. The two inventories must contain the same unique names. The `root` rows must agree on a nonempty node name and attached qdev identifier, with an inserted writable root node.

## Counter semantics and evidence limits

`block/qapi.c:bdrv_query_blk_stats` copies `failed_ops[BLOCK_ACCT_WRITE]` and `failed_ops[BLOCK_ACCT_FLUSH]` into the reported failure counters. In `block/accounting.c:block_account_one_io`, the failed count increments independently of `account_failed`:

```c
        if (failed) {
            stats->failed_ops[cookie->type]++;
        } else {
            stats->nr_bytes[cookie->type] += cookie->bytes;
            stats->nr_ops[cookie->type]++;
        }
```

The later `if (!failed || stats->account_failed)` controls total-time, last-access, and timed-average updates. The histogram update occurs before that conditional. Therefore `account_failed=false` does not disable `failed_*` counting, and the guard must not invent a requirement that it be true to validate the returned failure counters.

The nested `parent` and `backing` rows come from recursively zero-initialized node-statistics objects. They receive node-specific offset/driver data; they are not separately populated top-level backend failure accounts. The validator still checks every returned write/flush failure field for exact integer zero and preserves graph depth, size, and cycle limits. The evidence supports zero recorded failures in these returned fields; it does not create independent per-storage-layer failure coverage, prove the internal return value of QEMU's stop flush, or replace the subsequent raw journal and full read-only filesystem checks.

## Observed evidence and final validation

The parent-owned saved projection at `asoft-ios-android/tools/pixel-powervr/experiments/cpu-shadow/device-checks/recovery-20261122/firstboot-memfd/saved-counter-projection-123428.json` is explicitly a selected visual transcription, not a raw phone receipt export. It identifies the raw on-phone observations by SHA-256 `75bcf49437cba79303d019dbd3cdedba63cf269b93cdc5ba9384d47773923a9a`. The projection contains the `root` node `#block121`, parent `#block043`, backing `#block328`, backing parent `#block252`, and the separate `floppy0` row. All five reported failure-counter pairs are integer zero. There is no saved `query-block` witness in that attempt.

`focused-tests-reviewed.json` is the final offline receipt for the corrected guard and matching inspector. It records all imported local source hashes, the exact command, source stability, log hash, and successful exit. All 57 tests passed. The tests use authored metadata and mocked I/O; the new no-medium `query-block` objects are source-grounded synthetic fixtures, not recovered phone observations. The copied local `prepare_ios26.py` is the recorded current checkout support source, not the byte-identical frozen phone runner; `baseline.json` records that distinction.

The saved-firstboot inspector variant pins this new guard, recalculates the same two-response predicate, and requires the exact successful QMP sequence `stop`, `query-blockstats`, `query-block`, `quit`, with both recorded responses equal to the guard event. Its guest helper is unchanged. Later app/wallpaper/cold-boot validators have their own old pins and protocol assumptions; they remain outside this correction and require a separate explicit review before any later gate uses the new variant.
