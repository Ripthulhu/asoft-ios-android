#!/usr/bin/env python3
"""Split a frozen update into checked terminal-safe parts; execute nothing."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import textwrap
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package_output', type=Path)
    parser.add_argument('--reuse-update', type=Path,
                        help='Reuse an identical owner delta from an earlier verified update directory')
    args = parser.parse_args()
    root = args.package_output.resolve()
    package = json.loads((root / 'package.json').read_text())
    raw = Path(package['update_zip']['path']).read_bytes()
    assert len(raw) == package['update_zip']['bytes']
    assert digest(raw) == package['update_zip']['sha256']
    reused = None
    if args.reuse_update:
        name = 'owner-delta.zst'
        old = args.reuse_update.resolve() / name
        new = root / 'update-package' / name
        assert old.is_file() and not old.is_symlink()
        assert old.read_bytes() == new.read_bytes()
        reused = {'name': name, 'bytes': new.stat().st_size, 'sha256': digest(new.read_bytes())}
        payload = root / 'transfer-payload.zip'
        with zipfile.ZipFile(Path(package['update_zip']['path'])) as original:
            with zipfile.ZipFile(payload, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for entry in original.infolist():
                    if entry.filename != name:
                        archive.writestr(entry, original.read(entry))
        raw = payload.read_bytes()
    parts = root / 'transfer-parts'
    parts.mkdir()
    encoded = base64.b64encode(raw).decode('ascii')
    spec = {'archive_bytes': len(raw), 'archive_sha256': digest(raw),
            'installer_sha256': package['installer_sha256'], 'reused_file': reused, 'parts': []}
    for number, start in enumerate(range(0, len(encoded), 147456)):
        name = f'part-{number:03d}.b64'
        data = ('\n'.join(textwrap.wrap(encoded[start:start + 147456], 3072)) + '\n').encode()
        (parts / name).write_bytes(data)
        spec['parts'].append({'name': name, 'bytes': len(data), 'sha256': digest(data)})
    (root / 'transfer.json').write_text(json.dumps(spec, indent=2) + '\n')
    with zipfile.ZipFile(root / 'transfer-payload.zip' if reused else Path(package['update_zip']['path'])) as archive:
        names = sorted(archive.namelist())
    source = '''import base64,hashlib,io,json,os,sys,zipfile
from pathlib import Path,PurePosixPath
os.umask(0o077)
root=Path(sys.argv[1])
spec=json.loads(r\'\'\'MANIFEST\'\'\')
encoded=[]
for item in spec['parts']:
 p=root/item['name']
 assert p.is_file() and not p.is_symlink()
 data=p.read_bytes()
 assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],item['name']
 encoded.append(data)
raw=base64.b64decode(b''.join(encoded).replace(b'\\n',b''),validate=True)
assert len(raw)==spec['archive_bytes'] and hashlib.sha256(raw).hexdigest()==spec['archive_sha256']
archive=zipfile.ZipFile(io.BytesIO(raw))
assert sorted(archive.namelist())==ZIP_NAMES
assert archive.testzip() is None
out=root/'unpacked'
out.mkdir(mode=0o700)
for item in archive.infolist():
 p=PurePosixPath(item.filename)
 assert not p.is_absolute() and '..' not in p.parts and not item.is_dir()
 assert (item.external_attr>>16)&0o170000==0o100000
 dest=out/p
 dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 with dest.open('xb') as file:file.write(archive.read(item))
 dest.chmod(0o600)
if spec['reused_file']:
 item=spec['reused_file']
 assert item['name']=='owner-delta.zst' and len(sys.argv)==3
 previous=Path(sys.argv[2])/item['name']
 assert previous.is_file() and not previous.is_symlink()
 data=previous.read_bytes()
 assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
 dest=out/item['name']
 with dest.open('xb') as file:file.write(data)
 dest.chmod(0o600)
 assert hashlib.sha256(dest.read_bytes()).hexdigest()==item['sha256']
assert hashlib.sha256((out/'install-update.py').read_bytes()).hexdigest()==spec['installer_sha256']
with (root/'transfer-payload.zip').open('xb') as file:file.write(raw)
print('REIMS_TRANSFER=PASS parts='+str(len(spec['parts']))+' bytes='+str(len(raw))+' archive_sha256='+hashlib.sha256(raw).hexdigest())
print('REUSED_DELTA='+str(bool(spec['reused_file'])))
print('INSTALLER_READY='+str(out/'install-update.py'))
'''
    source = source.replace('MANIFEST', json.dumps(spec, indent=2)).replace('ZIP_NAMES', repr(names))
    compile(source, 'assemble-transfer.py', 'exec')
    assert max(map(len, source.splitlines())) < 3072
    (root / 'assemble-transfer.py').write_text(source)
    print(json.dumps({'parts': len(spec['parts']), 'archive_bytes': len(raw),
                      'archive_sha256': spec['archive_sha256']}))


if __name__ == '__main__':
    main()
