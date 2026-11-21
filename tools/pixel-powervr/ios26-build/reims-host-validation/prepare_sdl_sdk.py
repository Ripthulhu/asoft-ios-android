import concurrent.futures
import hashlib
import json
import lzma
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request

CACHE = Path('/home/agent/.cache/reims-host-sdl-debs')
SDK = Path('/home/agent/.cache/reims-host-sdl-root')
BASE = 'https://deb.debian.org/debian/'
INDEX_PATH = 'main/binary-amd64/Packages.xz'
NAMES = '''libx11-dev libx11-6 libx11-xcb1 libxext-dev libxext6
libxrandr-dev libxrandr2 libxcursor-dev libxcursor1 libxfixes-dev libxfixes3
libxi-dev libxi6 libxss-dev libxss1 libxtst-dev libxtst6 libxrender-dev
libxrender1 libxcb1-dev libxcb1 libxau-dev libxau6 libxdmcp-dev libxdmcp6
x11proto-dev xtrans-dev libpthread-stubs0-dev'''.split()

def fetch(url, dest, digest=None, size=None):
    if not dest.exists():
        with urllib.request.urlopen(url, timeout=45) as response:
            data = response.read()
        dest.write_bytes(data)
    data = dest.read_bytes()
    if digest is not None:
        assert hashlib.sha256(data).hexdigest() == digest, dest
    if size is not None:
        assert len(data) == int(size), dest
    return data

CACHE.mkdir(parents=True, exist_ok=True)
SDK.mkdir(parents=True, exist_ok=True)
release = fetch(BASE + 'dists/trixie/InRelease', CACHE / 'InRelease').decode()
checks = [line.split() for line in release.splitlines() if line.strip().endswith(' ' + INDEX_PATH)]
expected = next(x for x in checks if len(x) == 3 and re.fullmatch('[0-9a-f]{64}', x[0]))
compressed = fetch(BASE + 'dists/trixie/' + INDEX_PATH, CACHE / 'Packages.xz', expected[0], expected[1])
packages = {}
for block in lzma.decompress(compressed).decode().split('\n\n'):
    fields = {}
    for line in block.splitlines():
        if line and not line[0].isspace() and ': ' in line:
            key, value = line.split(': ', 1)
            fields[key] = value
    if fields.get('Package') in NAMES:
        packages[fields['Package']] = fields
assert set(NAMES) == set(packages), sorted(set(NAMES) - set(packages))
assert shutil.which('dpkg-deb')

def download(name):
    item = packages[name]
    filename = item['Filename']
    assert filename.startswith('pool/') and '..' not in Path(filename).parts
    path = CACHE / Path(filename).name
    fetch(BASE + filename, path, item['SHA256'], item['Size'])
    return name, path

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    downloaded = list(pool.map(download, NAMES))
for name, path in downloaded:
    subprocess.run(['dpkg-deb', '-x', str(path), str(SDK)], check=True)

# Relocate pkg-config metadata in this private extracted SDK. The verified archives stay intact.
relocated = []
for pc in (SDK / 'usr').rglob('*.pc'):
    before = pc.read_text()
    after = re.sub(r'(?m)^([A-Za-z_][A-Za-z_0-9]*=)/usr(?=/|$)',
                   lambda m: m.group(1) + str(SDK / 'usr'), before)
    if after != before:
        pc.write_text(after)
        relocated.append(str(pc.relative_to(SDK)))
manifest = {
    'source': BASE + 'dists/trixie/InRelease',
    'download_transport': 'HTTPS with certificate verification',
    'release_signature_verified': False,
    'package_index_sha256': expected[0],
    'sdk': str(SDK),
    'system_package_database_modified': False,
    'maintainer_scripts_executed': False,
    'relocated_pkg_config': relocated,
    'packages': [{k: packages[n][k] for k in ['Package', 'Version', 'Filename', 'SHA256', 'Size']} for n in NAMES],
}
(Path(__file__).parent / 'sdl-sdk.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print(json.dumps({'sdk': str(SDK), 'packages': len(packages), 'relocated_pc_files': len(relocated)}, indent=2))
