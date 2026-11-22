#!/usr/bin/env python3
"""Build the opt-in Android runtime and authored qualifier, without creating an APK."""

from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import shlex
import shutil
import subprocess


AIR_SOURCES = {
    "alias": "cpu_shadow_alias/kernel.ll",
    "fixed": "cpu_shadow_fixed/render.ll",
    "arguments": "cpu_shadow_arguments/kernel.ll",
    "dynamic-rebind": "cpu_shadow_dynamic_rebind/kernel.ll",
    "tile-vertex": "cpu_shadow_tile/vertex.ll",
    "tile-fragment": "cpu_shadow_tile/fragment.ll",
}


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def capture(command, *, cwd=None, env=None):
    return subprocess.check_output(command, cwd=cwd, env=env, text=True)


def source_snapshot(source):
    changed = set(capture(["git", "diff", "--name-only", "-z", "HEAD", "--"], cwd=source).split("\0"))
    untracked = set(capture(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=source).split("\0"))
    untracked.discard("")
    if untracked:
        raise RuntimeError("Commit source inputs before the frozen build: " + ", ".join(sorted(untracked)))
    changed.discard("")
    return {
        "commit": capture(["git", "rev-parse", "HEAD"], cwd=source).strip(),
        "tree": capture(["git", "rev-parse", "HEAD^{tree}"], cwd=source).strip(),
        "changed_files_sha256": {
            name: sha(source / name) if (source / name).is_file() else None
            for name in sorted(changed)
        },
        "cargo_lock_sha256": sha(source / "Cargo.lock"),
    }


def describe(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def localize(raw, out, work, tools):
    """Use the project's xtask dist recipe, substituting the target LLVM tools."""
    work.mkdir(parents=True, exist_ok=False)
    obj = work / "reims_vgpu.o"
    commands = [[str(tools / "ld.lld"), "-r", "--whole-archive", str(raw),
                 "--no-whole-archive", "-o", str(obj)]]
    subprocess.run(commands[-1], check=True)

    def globals_for(path):
        output = capture([str(tools / "llvm-nm"), "-g", "--defined-only", "-P", str(path)])
        return [line.split()[0] for line in output.splitlines()
                if len(line.split()) >= 2 and len(line.split()[1]) == 1]

    public = sorted(name for name in globals_for(obj) if name.startswith("rvg_"))
    required = {"rvg_device_cpu_shadow_counts", "rvg_cpu_shadow_probe_v1"}
    if not required.issubset(public):
        raise RuntimeError("Runtime archive lacks the actual CPU-shadow C API")
    keep = work / "keep-global-symbols"
    keep.write_text("\n".join(public) + "\n")
    commands.append([str(tools / "llvm-objcopy"), "--keep-global-symbols=" + str(keep), str(obj)])
    subprocess.run(commands[-1], check=True)
    archive = out / "lib/libreims_vgpu.a"
    commands.append([str(tools / "llvm-ar"), "rcsD", str(archive), str(obj)])
    subprocess.run(commands[-1], check=True)
    if sorted(globals_for(archive)) != public:
        raise RuntimeError("Localized archive exposes unexpected symbols")
    result = {"commands": commands, "raw_archive": describe(raw),
              "public_symbols": public, "public_symbol_count": len(public),
              "recipe": "reims xtask/src/dist/linux.rs::localize with target LLVM tools"}
    # Only this invocation's intermediate object is removed. Shared Cargo outputs remain.
    obj.unlink()
    keep.unlink()
    work.rmdir()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Reims checkout with the captured source patches")
    parser.add_argument("--runtime", type=Path, required=True, help="Matching metal2vulkan checkout")
    parser.add_argument("--ndk", type=Path, required=True, help="Android NDK r29")
    parser.add_argument("--target", type=Path, required=True, help="This checkout's reusable Cargo target under ~/.cache")
    parser.add_argument("--out", type=Path, required=True, help="New, nonexistent output directory")
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--cbindgen", default="cbindgen")
    parser.add_argument("--rust-toolchain", default="1.98.1")
    args = parser.parse_args()
    source, runtime, ndk = (path.resolve() for path in (args.source, args.runtime, args.ndk))
    target = args.target.absolute()
    out = args.out.absolute()
    out.mkdir(parents=True, exist_ok=False)
    for directory in ("lib", "include", "bin", "fixtures", "logs", "source"):
        (out / directory).mkdir()
    tools = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    cargo = [args.cargo, "+" + args.rust_toolchain]
    overrides = {
        "CARGO_TARGET_DIR": str(target), "CARGO_BUILD_JOBS": "1", "CARGO_INCREMENTAL": "0",
        "CARGO_NET_OFFLINE": "true", "CARGO": args.cargo,
        "RUSTUP_TOOLCHAIN": args.rust_toolchain,
        "CARGO_PROFILE_RELEASE_DEBUG": "0", "CARGO_PROFILE_RELEASE_LTO": "false",
        "CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER": str(tools / "aarch64-linux-android29-clang"),
        "CC_aarch64_linux_android": str(tools / "aarch64-linux-android29-clang"),
        "AR_aarch64_linux_android": str(tools / "llvm-ar"),
        "RVG_CPU_SHADOW_LLVM_AS": str(tools / "llvm-as"),
        "RVG_METALLIB_DIR": str(source / "crates/reims-vgpu-vulkan/metallibs"),
        "CARGO_ENCODED_RUSTFLAGS": "\x1f".join([
            "-Dwarnings", "-C", "target-feature=+lse,+rcpc",
            "-C", "link-arg=-Wl,-z,max-page-size=16384",
            "--remap-path-prefix", f"{source}=/reims-vgpu",
            "--remap-path-prefix", f"{runtime}=/metal2vulkan",
        ]),
    }
    environment = os.environ.copy()
    compiler_environment = {"RUSTC", "RUSTC_WRAPPER", "RUSTC_WORKSPACE_WRAPPER", "RUSTFLAGS",
                            "CARGO_BUILD_RUSTC", "CARGO_BUILD_RUSTC_WRAPPER",
                            "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER", "CARGO_BUILD_RUSTFLAGS"}
    removed = sorted(key for key in environment
                     if key in compiler_environment or key.startswith("CARGO_PROFILE_"))
    for key in removed:
        environment.pop(key)
    environment.update(overrides)
    report = {
        "result": "RUNNING", "gpu_path_complete": False,
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "build_script_sha256": sha(Path(__file__)), "environment_overrides": overrides,
        "inherited_compiler_variables_removed": removed,
        "source": str(source), "runtime": str(runtime), "ndk": str(ndk),
        "rust_toolchain": args.rust_toolchain,
        "profile": "Release optimization; no debug info, incremental build or LTO; one Cargo job.",
        "warning_policy": "All Rust warnings are denied; desktop-only window helpers are excluded on Android at their source.",
        "cpu_contract": "AArch64 LSE/RCpc host code; ordinary memfd CPU RAM, no CPU atomics on Vulkan shadows. QEMU native EL0 is a separate qualification.",
        "scope": "Build artifacts only. No APK, physical PowerVR execution or Apple guest boot is claimed.",
        "commands": [],
    }
    manifest = out / "build.json"

    def save():
        manifest.write_text(json.dumps(report, indent=2) + "\n")

    def run(command, label):
        log = out / "logs" / (label + ".log")
        with log.open("w") as output:
            result = subprocess.run(command, cwd=source, env=environment,
                                    stdout=output, stderr=subprocess.STDOUT)
        report["commands"].append({"label": label, "command": command,
                                   "exit_code": result.returncode, "log": describe(log)})
        save()
        if result.returncode:
            raise RuntimeError(f"{label} failed with exit {result.returncode}; see {log}")
        return log

    try:
        report["ndk_source_properties"] = (ndk / "source.properties").read_text()
        report["cargo_version"] = capture([*cargo, "-vV"], cwd=source, env=environment)
        report["cbindgen_version"] = capture([args.cbindgen, "--version"],
                                             cwd=source, env=environment).strip()
        if report["cbindgen_version"] != "cbindgen 0.29.4":
            raise RuntimeError("The committed C header requires cbindgen 0.29.4")
        report["rustc_version"] = capture([str(Path(args.cargo).with_name("rustc")),
                                           "+" + args.rust_toolchain, "-vV"],
                                          cwd=source, env=environment)
        report["source_before"] = source_snapshot(source)
        report["runtime_before"] = source_snapshot(runtime)
        for name, tree in (("reims", source), ("metal2vulkan", runtime)):
            (out / "source" / (name + ".patch")).write_bytes(subprocess.check_output(
                ["git", "diff", "--binary", "HEAD", "--"], cwd=tree))
            shutil.copyfile(tree / "Cargo.lock", out / "source" / (name + "-Cargo.lock"))
        save()
        # Refuse an accidental stale dependency tree instead of silently building the wrong runtime.
        metadata = json.loads(capture([
            *cargo, "metadata", "--offline", "--locked", "--format-version", "1",
            "--manifest-path", str(source / "crates/reims-vgpu-c/Cargo.toml"),
            "--no-default-features", "--features", "vulkan,cpu-shadow-probe",
        ], cwd=source, env=environment))
        for name in ("metal2vulkan", "metal2vulkan-runtime", "metal2vulkan-air"):
            found = [Path(package["manifest_path"]).resolve().parent
                     for package in metadata["packages"] if package["name"] == name]
            if found != [runtime / "crates" / name]:
                raise RuntimeError(f"{name} resolves to {found}, not the requested runtime checkout")
        header = out / "include/reims_vgpu.h"
        run([args.cbindgen, "--quiet", "--config", str(source / "crates/reims-vgpu-c/cbindgen.toml"),
             "--output", str(header), str(source / "crates/reims-vgpu-c")], "header")
        if sha(header) != sha(source / "crates/reims-vgpu-c/include/reims_vgpu.h"):
            raise RuntimeError("Generated C header differs from the captured source header")
        examples = source / "crates/reims-vgpu-vulkan/examples"
        for name, relative in AIR_SOURCES.items():
            run([str(tools / "llvm-as"), str(examples / relative),
                 "-o", str(out / "fixtures" / ("cpu-shadow-" + name + ".air"))], "air-" + name)
        common = [*cargo, "rustc", "--offline", "--locked", "--release", "--target", "aarch64-linux-android"]
        log = run([*common, "-p", "reims-vgpu-c", "--lib", "--no-default-features",
                   "--features", "vulkan,cpu-shadow-probe", "--", "--print", "native-static-libs"], "runtime")
        report["native_static_libs"] = [shlex.split(line.split("native-static-libs:", 1)[1])
            for line in log.read_text().splitlines() if "native-static-libs:" in line]
        if not report["native_static_libs"]:
            raise RuntimeError("Rust did not report the static archive's native dependency closure")
        release = target / "aarch64-linux-android/release"
        work = target / ("cpu-shadow-localize-" + hashlib.sha256(str(out).encode()).hexdigest()[:12])
        report["localization"] = localize(release / "libreims_vgpu_c.a", out, work, tools)
        report["source_at_archive"] = source_snapshot(source)
        report["runtime_at_archive"] = source_snapshot(runtime)
        if (report["source_before"] != report["source_at_archive"]
                or report["runtime_before"] != report["runtime_at_archive"]):
            raise RuntimeError("Source changed while building the runtime archive")
        archive_record = {"result": "BUILT_NOT_EXECUTED", "gpu_path_complete": False,
                          "archive": describe(out / "lib/libreims_vgpu.a"),
                          "header": describe(header), "native_static_libs": report["native_static_libs"],
                          "source": report["source_at_archive"], "runtime": report["runtime_at_archive"]}
        (out / "runtime-archive.json").write_text(json.dumps(archive_record, indent=2) + "\n")
        print("RUNTIME_ARCHIVE_READY " + str(out / "lib/libreims_vgpu.a"), flush=True)
        # A separate Cargo graph keeps the example's testkit dev-dependency out of the C library.
        shim = target / ("cpu-shadow-api29-" + hashlib.sha256(str(out).encode()).hexdigest()[:12] + ".o")
        run([str(tools / "aarch64-linux-android29-clang"), "-O2", "-fPIC", "-fvisibility=hidden",
             "-Wall", "-Wextra", "-Werror", "-Wmissing-prototypes", "-c",
             str(examples / "cpu_shadow_qualification/android_compat.c"), "-o", str(shim)], "api29-shim")
        report["standalone_api29_shim"] = describe(shim)
        run([*common, "-p", "reims-vgpu-vulkan", "--features", "cpu-shadow-probe",
             "--example", "cpu_shadow_qualification", "--", "-C", "link-arg=" + str(shim)], "qualifier")
        binary = out / "bin/cpu_shadow_qualification"
        shutil.copyfile(release / "examples/cpu_shadow_qualification", binary)
        run([str(tools / "llvm-strip"), "--strip-unneeded", str(binary)], "strip")
        binary.chmod(0o755)
        headers = capture([str(tools / "llvm-readelf"), "-lW", str(binary)])
        report["elf_program_headers"] = headers
        report["elf_dynamic"] = capture([str(tools / "llvm-readelf"), "-dW", str(binary)])
        loads = [line.split() for line in headers.splitlines() if line.lstrip().startswith("LOAD ")]
        if not loads or any(int(fields[-1], 0) < 16384 for fields in loads):
            raise RuntimeError("Android qualifier LOAD segments do not preserve 16 KiB alignment")
        report["source_after"] = source_snapshot(source)
        report["runtime_after"] = source_snapshot(runtime)
        report["sources_stable"] = (report["source_before"] == report["source_after"]
                                    and report["runtime_before"] == report["runtime_after"])
        if not report["sources_stable"]:
            raise RuntimeError("Source changed during the build; these artifacts are not a frozen checkpoint")
        report["artifacts"] = {str(path.relative_to(out)): describe(path)
            for directory in ("lib", "include", "bin", "fixtures")
            for path in sorted((out / directory).rglob("*")) if path.is_file()}
        report["result"] = "BUILT_NOT_DEVICE_QUALIFIED"
    except Exception as error:
        report["result"] = "FAILED"
        report["error"] = str(error)
        raise
    finally:
        report["ended_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
    print(report["result"], flush=True)


if __name__ == "__main__":
    main()
