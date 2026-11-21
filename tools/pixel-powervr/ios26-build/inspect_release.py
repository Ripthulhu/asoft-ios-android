#!/usr/bin/env python3
"""Inspect, hash, and selectively extract an official APK without running it."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import urllib.request
import zipfile

BASE = Path(__file__).resolve().parent
REPO = BASE.parent / 'asoft-ios-android'
APK = BASE / 'ASoftware-iOS-Android-0.1.6.apk'
EXPECTED_SHA256 = 'befbcc1b31d83f166870010300a2a302e3570a7d3622d8de9c02fd896eeaa0cf'
EXPECTED_SIZE = 109357759
READELF = BASE.parent / 'tooling/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf'
BUILD_TOOLS = BASE.parent / 'pixel-android-probe/toolchain/sdk/android-16'
RELEASE_API = 'https://api.github.com/repos/alpersamur3/asoft-ios-android/releases/tags/v0.1.6'
EXTRACT = BASE / 'extracted'
REPORTS = BASE / 'reports'
REPORTS.mkdir(exist_ok=True)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(args):
    result = subprocess.run([str(a) for a in args], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout


apk_raw = APK.read_bytes()
assert len(apk_raw) == EXPECTED_SIZE, 'APK size mismatch'
assert sha(apk_raw) == EXPECTED_SHA256, 'APK SHA-256 mismatch'
del apk_raw
request = urllib.request.Request(RELEASE_API, headers={'User-Agent': 'ASoftware-Pixel-runtime-inventory'})
with urllib.request.urlopen(request, timeout=30) as response:
    release_raw = response.read()
release = json.loads(release_raw)
asset = next(a for a in release['assets'] if a['name'] == APK.name)
assert asset['size'] == EXPECTED_SIZE
assert asset['digest'] == 'sha256:' + EXPECTED_SHA256
(REPORTS / 'github-release-v0.1.6.json').write_bytes(release_raw)
tag_url = 'https://api.github.com/repos/alpersamur3/asoft-ios-android/git/ref/tags/v0.1.6'
tag_chain = []
for tag_depth in range(4):
    request = urllib.request.Request(tag_url, headers={'User-Agent': 'ASoftware-Pixel-runtime-inventory'})
    with urllib.request.urlopen(request, timeout=30) as response:
        tag_raw = response.read()
    tag_object = json.loads(tag_raw)
    (REPORTS / ('github-tag-v0.1.6-' + str(tag_depth) + '.json')).write_bytes(tag_raw)
    tag_chain.append({'url': tag_url, 'object': tag_object['object']})
    if tag_object['object']['type'] == 'commit':
        tag_commit = tag_object['object']['sha']
        break
    assert tag_object['object']['type'] == 'tag', 'Unexpected tag object type'
    tag_url = tag_object['object']['url']
else:
    raise RuntimeError('GitHub tag did not resolve to a commit')
signature = run([BUILD_TOOLS / 'apksigner', 'verify', '--verbose', '--print-certs', APK])
(REPORTS / 'apk-signature.txt').write_text(signature)
badging = run([BUILD_TOOLS / 'aapt', 'dump', 'badging', APK])
(REPORTS / 'apk-badging.txt').write_text(badging)

entries = []
comparisons = []
native_reports = []
normalized_comparisons = []
skip_native = {'libconscrypt_jni.so', 'librender.so', 'libgpucheck.so', 'libunpack.so'}
with zipfile.ZipFile(APK) as archive:
    for item in archive.infolist():
        name = item.filename
        if item.is_dir() or not name.startswith(('lib/arm64-v8a/', 'assets/')):
            continue
        path = PurePosixPath(name)
        assert not path.is_absolute() and '..' not in path.parts
        raw = archive.read(item)
        selected = name.startswith(('assets/helper/', 'assets/setup/')) or (
            name.startswith('lib/arm64-v8a/') and path.name not in skip_native)
        entry = dict(path=name, size=item.file_size, compressed_size=item.compress_size,
                     compression_method=item.compress_type, sha256=sha(raw), extracted=selected)
        if path.name in skip_native and name.startswith('lib/'):
            entry['reuse'] = 'Do not copy: build from app source or resolve Conscrypt through Maven.'
        elif path.name == 'libqemu26.so':
            entry['reuse'] = 'Reference only: rebuild and relink patched reims/metal2vulkan plus QEMU producer-RAM path.'
        elif path.name in {'lib_libvulkan.so.so', 'lib_libvulkan_freedreno.so.so'}:
            entry['reuse'] = 'Retain only for the existing Adreno path; do not select these for PowerVR.'
        elif name.startswith('lib/'):
            entry['reuse'] = 'Candidate unchanged dependency/helper binary; not executed by this inspection.'
        elif name.startswith('assets/helper/'):
            entry['reuse'] = 'Candidate unchanged helper asset; preserve .bin no-compress packaging.'
        elif name.startswith('assets/setup/'):
            entry['reuse'] = 'Compare text to matching app/installer source before staging.'
        else:
            entry['reuse'] = 'Not extracted: iOS 16 kernel or existing benchmark outside this iOS 26 inventory scope.'
        entries.append(entry)
        if selected:
            target = EXTRACT / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            # No extracted object is marked executable or invoked.
            target.chmod(0o644)
        if name == 'assets/setup/asoft-setup.json' or name.startswith('assets/setup/phone/'):
            local = REPO / name.removeprefix('assets/')
            local_raw = local.read_bytes() if local.exists() else None
            comparisons.append(dict(apk_path=name, local_path=str(local.relative_to(REPO)),
                                    comparison='missing' if local_raw is None else ('identical' if local_raw == raw else 'different'),
                                    apk_sha256=sha(raw), local_sha256=None if local_raw is None else sha(local_raw)))
            if local_raw is not None and local_raw != raw:
                normalized_comparisons.append(dict(path=str(local.relative_to(REPO)),
                    difference_kind='line-endings-only' if local_raw.replace(b'\r\n', b'\n') == raw.replace(b'\r\n', b'\n') else 'text-content'))
        if name == 'assets/el0bench.elf':
            local = REPO / 'app/src/main/assets/el0bench.elf'
            local_raw = local.read_bytes()
            comparisons.append(dict(apk_path=name, local_path=str(local.relative_to(REPO)),
                                    comparison='identical' if local_raw == raw else 'different',
                                    apk_sha256=sha(raw), local_sha256=sha(local_raw)))

for entry in entries:
    if not entry['extracted'] or not entry['path'].startswith('lib/'):
        continue
    file = EXTRACT / entry['path']
    report = run([READELF, '-h', '-l', '-d', '-n', file])
    (REPORTS / (file.name + '.readelf.txt')).write_text(report)
    needed = re.findall(r'\(NEEDED\)\s+Shared library: \[([^]]+)\]', report)
    soname_match = re.search(r'\(SONAME\)\s+Library soname: \[([^]]+)\]', report)
    runpath = re.findall(r'\((?:RUNPATH|RPATH)\)\s+Library (?:runpath|rpath): \[([^]]*)\]', report)
    interpreter = re.findall(r'Requesting program interpreter: ([^]]+)\]', report)
    native_reports.append(dict(path=entry['path'], sha256=entry['sha256'], needed=needed,
                               soname=soname_match.group(1) if soname_match else None,
                               runpath=runpath, interpreter=interpreter))

aliases = {Path(v['path']).name[4:-3] for v in native_reports if Path(v['path']).name.startswith('lib_')}
needed = {name for v in native_reports for name in v['needed']}
closure = dict(packaged_soname_aliases=sorted(aliases), android_system_needed=sorted(needed - aliases),
               unresolved_non_system=sorted(needed - aliases - {'libc.so', 'libdl.so', 'libm.so', 'libz.so'}))
assert not closure['unresolved_non_system'], 'Missing non-system dynamic dependency'
for entry in entries:
    if entry['extracted']:
        assert sha((EXTRACT / entry['path']).read_bytes()) == entry['sha256'], 'Written extraction hash mismatch'

metadata = dict(
    inspected_at_utc=datetime.now(timezone.utc).isoformat(),
    policy='Static inspection only. No APK installation or execution of extracted binaries/scripts.',
    source=dict(repository='alpersamur3/asoft-ios-android', tag='v0.1.6',
                release_url=release['html_url'], release_api=RELEASE_API,
                published_at=release['published_at'], target_commitish=release['target_commitish'],
                tag_commit=tag_commit, tag_resolution_chain=tag_chain,
                asset_id=asset['id'], asset_url=asset['browser_download_url'],
                github_digest=asset['digest'], size=EXPECTED_SIZE, sha256=EXPECTED_SHA256,
                signature_certificate_sha256='d412a33bde757a6b36524e09c215b1e2a2a21285b0fd38e8e30a8c5f23672ef2'),
    local_repo=dict(path=str(REPO), head=run(['git', '-C', REPO, 'rev-parse', 'HEAD']).strip()),
    entries=entries, local_comparisons=comparisons, setup_normalized_comparisons=normalized_comparisons,
    native_dependencies=native_reports, dependency_closure=closure,
)
(BASE / 'inventory.json').write_text(json.dumps(metadata, indent=2) + '\n')
(BASE / 'SHA256SUMS-extracted.txt').write_text(''.join(e['sha256'] + '  extracted/' + e['path'] + '\n' for e in entries if e['extracted']))
print(json.dumps(dict(apk_sha256=EXPECTED_SHA256, apk_size=EXPECTED_SIZE,
    extracted_files=sum(e['extracted'] for e in entries),
    extracted_bytes=sum(e['size'] for e in entries if e['extracted']),
    native_files=len(native_reports),
    setup_differences=[c['local_path'] for c in comparisons if c['comparison'] != 'identical']), indent=2))
