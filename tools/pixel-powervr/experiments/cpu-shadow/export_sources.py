#!/usr/bin/env python3
"""Export committed CPU-shadow sources and verify each complete reconstructed Git tree.

All three HEADs are captured before export. Local changes, including reims' Cargo
path overrides, are recorded as excluded paths and never enter the patches.
Verification uses a temporary bare repository, index and object directory; source
objects are read through Git alternates. No source index, checkout or ref is written.
Only this helper's named files under --out are replaced, after all checks succeed.
This is source reconstruction evidence, not Pixel, iOS boot or APK qualification.
"""

from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import tempfile


PROJECTS = {
    "qemu": {
        "repository": "https://github.com/alpersamur3/qemu-sptm",
        "base": "7a900afb62ddf94713e38ac5a4aafe1d42c9efa8",
        "patch": "0001-native-el0-and-cpu-shadow-integration.patch",
    },
    "metal2vulkan": {
        "repository": "https://github.com/alpersamur3/metal2vulkan",
        "base": "7aaf60f105544b70b4cf25f9eb44ace4b00a61fd",
        "base_preparation": "../../producer-adoption",
        "patch": "0001-canonical-paged-cpu-shadow-runtime.patch",
    },
    "reims": {
        "repository": "https://github.com/alpersamur3/reims-vgpu",
        "base": "c3551c742dfa826ea8e4aecf5affc22bf508822b",
        "base_preparation": "../../reims-host-validation",
        "patch": "0001-ordinary-file-cpu-shadow-integration.patch",
    },
}

DIFF_OPTIONS = [
    "--binary", "--full-index", "--no-color", "--no-ext-diff", "--no-textconv",
    "--no-renames", "--diff-algorithm=myers", "--indent-heuristic", "--unified=3",
    "--src-prefix=a/", "--dst-prefix=b/",
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def environment():
    # Inherited Git routing must not redirect either reads or the isolated index.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0",
                "GIT_NO_LAZY_FETCH": "1", "GIT_ATTR_NOSYSTEM": "1"})
    return env


def git(source, *arguments, env=None):
    command = ["git", "--no-pager", "--no-optional-locks",
               "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
               "-c", "gc.auto=0", "-c", "core.attributesFile=" + os.devnull,
               "-C", str(source), *arguments]
    return subprocess.check_output(command, env=env or environment())


def commit(source, ref):
    return git(source, "rev-parse", "--verify", "--end-of-options",
               ref + "^{commit}").decode().strip()


def paths(raw):
    return [name.decode("utf-8", "surrogateescape") for name in raw.split(b"\0") if name]


def source_state(source, head):
    index = Path(git(source, "rev-parse", "--path-format=absolute", "--git-path", "index")
                 .decode().strip())
    changed = paths(git(source, "diff", "--name-only", "--no-renames", "-z", head, "--"))
    untracked = paths(git(source, "ls-files", "--others", "--exclude-standard", "-z"))
    untracked_hashes = {}
    for name in untracked:
        path = source / name
        if path.is_symlink():
            untracked_hashes[name] = sha(os.fsencode(os.readlink(path)))
        elif path.is_file():
            with path.open("rb") as stream:
                untracked_hashes[name] = hashlib.file_digest(stream, "sha256").hexdigest()
        else:
            raise RuntimeError("Unsupported untracked entry: " + str(path))
    return {
        "head": commit(source, "HEAD"),
        "index_sha256": sha(index.read_bytes()) if index.exists() else None,
        "worktree_diff_sha256": sha(git(source, "diff", *DIFF_OPTIONS, head, "--")),
        "excluded_tracked_paths": sorted(changed),
        "untracked_sha256": untracked_hashes,
        "remote_refs_sha256": sha(git(source, "for-each-ref", "refs/remotes/",
                                      "--format=%(refname)%00%(objectname)")),
    }


def export_one(source, head, base, info):
    tree = git(source, "rev-parse", head + "^{tree}").decode().strip()
    base_tree = git(source, "rev-parse", base + "^{tree}").decode().strip()
    object_format = git(source, "rev-parse", "--show-object-format").decode().strip()
    objects = git(source, "rev-parse", "--path-format=absolute", "--git-path", "objects")
    objects = objects.decode().strip()
    with tempfile.TemporaryDirectory(prefix="cpu-shadow-source-export-") as temporary:
        temp = Path(temporary)
        private = temp / "verify.git"
        subprocess.run(["git", "init", "--quiet", "--bare",
                        "--object-format=" + object_format, str(private)],
                       env=environment(), check=True)
        env = environment()
        env["GIT_INDEX_FILE"] = str(temp / "index")
        # JSON quoting is Git's supported C-style quoting for an alternate path. It also
        # handles spaces, colons and backslashes without turning them into extra alternates.
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = json.dumps(objects, ensure_ascii=False)
        git(private, "read-tree", base, env=env)
        patch = git(private, "diff", *DIFF_OPTIONS, base, head, "--", env=env)
        changes = paths(git(private, "diff", "--name-only", "--no-renames", "-z",
                            base, head, "--", env=env))
        if patch:
            patch_file = temp / "source.patch"
            patch_file.write_bytes(patch)
            git(private, "apply", "--cached", "--binary", "--whitespace=nowarn",
                str(patch_file), env=env)
        rebuilt = git(private, "write-tree", env=env).decode().strip()
        if rebuilt != tree:
            raise RuntimeError(f"{source}: reconstructed tree {rebuilt} != {tree}")
    manifest = {
        "repository": info["repository"],
        "base_commit": base,
        "base_tree": base_tree,
    }
    if "base_preparation" in info:
        manifest["base_preparation"] = info["base_preparation"]
    manifest.update({
        "source_head": head,
        "source_tree": tree,
        "patch": {"path": info["patch"], "bytes": len(patch), "sha256": sha(patch)},
        "changes": changes,
        "verification": {
            "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "method": "isolated git index: read-tree base, apply --cached patch, write-tree",
            "object_database": "temporary bare repository; source objects read-only",
            "reconstructed_tree": rebuilt,
            "matches_source_tree": True,
        },
        "execution_status": "NOT_QUALIFIED_ON_PIXEL",
        "gpu_path_complete": False,
        "android_apk_built": False,
    })
    return patch, manifest


def readme(manifests):
    rows = "\n".join(
        f"| {name} | `{m['base_commit']}` | `{m['source_head']}` | `{m['source_tree']}` |"
        for name, m in manifests.items())
    expectations = " \\\n  ".join(f"--expect-{name}-head {m['source_head']}" for name, m in manifests.items())
    return f"""# CPU-authoritative GPU source exports

These binary-capable Git patches reproduce the committed QEMU, metal2vulkan and
reims source trees below. Reconstruction is verified; these exports are
**not Pixel-qualified**. They establish no iOS boot, complete GPU path or APK
result. Execution evidence belongs to the separate qualification records.

| Component | Required base commit | Exported source commit | Complete source tree |
| --- | --- | --- | --- |
{rows}

Each component's `source.json` preserves its patch name, size, SHA-256, changed
paths and exact reconstruction result. The metal2vulkan base is prepared by
`../producer-adoption`; the reims base by `../reims-host-validation`. These
increments do not replace or alter those earlier patch series or their licenses.

## Verify and apply

Run `sha256sum -c SHA256SUMS` in this directory. In a separate clean checkout at
the component's recorded base, apply its patch with `git apply --index` and check
`git write-tree` against `source_tree` in its manifest. These are raw Git diffs,
not mail patches; `git am` is not the application method. The resulting commit
ID may differ, but the complete Git tree must match exactly.

## Repeat the export

The helper takes explicit source and output paths and captures all three HEADs
before generating any patch. Optional expected heads make a pinned rerun fail
if a checkout has advanced. Omit or update those checks intentionally when
exporting a later committed capability change. Base commits also have explicit
`--qemu-base`, `--metal2vulkan-base` and `--reims-base` overrides; their defaults
are the required bases above.

```sh
python3 ../../experiments/cpu-shadow/export_sources.py \\
  --qemu-source /absolute/qemu-cpu-shadow \\
  --metal2vulkan-source /absolute/metal2vulkan-paged-shadow \\
  --reims-source /absolute/reims-pixel-apk-runtime \\
  --out /absolute/asoft-ios-android/tools/pixel-powervr/patches/cpu-shadow \\
  {expectations}
```

Only committed differences enter the patches. Local reims `Cargo.toml` path
overrides, staged/uncommitted edits and untracked files are excluded and their
paths recorded. Configure the three local metal2vulkan Cargo paths separately
for a build, as described by `../../experiments/cpu-shadow/README.md`.

The helper reconstructs each full tree in a temporary bare repository with its
own index and object directory. Source objects are read through Git alternates;
the original checkouts, indexes and remote refs are not written. It checks HEAD,
main-index bytes, tracked working differences, untracked contents and remote
refs again before publishing. Ignored build outputs are not part of that check.
All reconstruction and stability checks must pass before existing export files
are replaced. `SHA256SUMS` is written last, so an interrupted update cannot pass
the checksum check with mismatched files. Unrelated output files are left alone.
"""


def write_atomic(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".export-", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(contents)
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
        except BaseException:
            temporary.unlink()
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, info in PROJECTS.items():
        parser.add_argument(f"--{name}-source", type=Path, required=True)
        parser.add_argument(f"--{name}-base", default=info["base"])
        parser.add_argument(f"--expect-{name}-head", help="Refuse a different captured HEAD")
    parser.add_argument("--out", type=Path, required=True,
                        help="Export directory; replace only the named patches/manifests")
    args = parser.parse_args()
    sources = {name: getattr(args, name + "_source").resolve() for name in PROJECTS}
    out = args.out.resolve()
    for source in sources.values():
        if out.is_relative_to(source) or source.is_relative_to(out):
            raise RuntimeError("Output must be separate from each source checkout: " + str(source))
    heads = {name: commit(source, "HEAD") for name, source in sources.items()}
    before = {}
    bases = {}
    for name, source in sources.items():
        expected = getattr(args, "expect_" + name + "_head")
        if expected and commit(source, expected) != heads[name]:
            raise RuntimeError(f"{name}: captured HEAD {heads[name]} differs from {expected}")
        bases[name] = commit(source, getattr(args, name + "_base"))
        before[name] = source_state(source, heads[name])
        if before[name]["head"] != heads[name]:
            raise RuntimeError(name + ": HEAD changed while capturing source state")
    files = {}
    manifests = {}
    exporter_hash = sha(Path(__file__).read_bytes())
    for name, info in PROJECTS.items():
        patch, manifest = export_one(sources[name], heads[name], bases[name], info)
        manifest["exporter_sha256"] = exporter_hash
        manifest["excluded_local_changes"] = {
            "tracked_paths": before[name]["excluded_tracked_paths"],
            "untracked_paths": sorted(before[name]["untracked_sha256"]),
            "policy": "Committed objects only; no working-tree or staged diff is exported",
        }
        files[f"{name}/{info['patch']}"] = patch
        manifests[name] = manifest
    for name, source in sources.items():
        if source_state(source, heads[name]) != before[name]:
            raise RuntimeError(name + ": source/index/remote refs changed during export; retry")
        manifests[name]["verification"].update({
            "working_tree_unchanged": True,
            "main_index_unchanged": True,
            "remote_refs_unchanged": True,
            "worktree_check": "Tracked diff and untracked contents; ignored build outputs excluded",
        })
        files[f"{name}/source.json"] = (json.dumps(manifests[name], indent=2) + "\n").encode()
    files["README.md"] = readme(manifests).encode()
    sums = "".join(f"{sha(data)}  {name}\n" for name, data in sorted(files.items()))
    files["SHA256SUMS"] = sums.encode()
    for name in files:
        path = out / name
        if path.is_symlink() or (path.parent != out and path.parent.is_symlink()):
            raise RuntimeError("Refusing a symlinked export path: " + str(path))
    for name, data in files.items():
        write_atomic(out / name, data)
    print(json.dumps({"result": "SOURCE_TREES_RECONSTRUCTED", "output": str(out),
                      "heads": heads, "execution_status": "NOT_QUALIFIED_ON_PIXEL",
                      "gpu_path_complete": False, "android_apk_built": False}, indent=2))


if __name__ == "__main__":
    main()
