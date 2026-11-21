import base64,hashlib,io,json,os,sys,zipfile
from pathlib import Path,PurePosixPath
os.umask(0o077)
root=Path(sys.argv[1])
spec=json.loads(r'''{
  "archive_bytes": 26669,
  "archive_sha256": "5f2aff48eeb4a7033152513cc442c8a597e2535fa31c1c149949ef1d333830d7",
  "installer_sha256": "89ca2d55f13ab3674440e8befe1ab85f20e2a8655950e490f930f00f99a3adae",
  "reused_file": {
    "name": "owner-delta.zst",
    "bytes": 1943786,
    "sha256": "2f3b14b8a19fee65eef7adcf1ea87193cccd5bde659bbc7c27d845ecc4f6d6d1"
  },
  "parts": [
    {
      "name": "part-000.b64",
      "bytes": 35572,
      "sha256": "df314c3d874150eb139b68e0be1fd7908408e074a7244a3bf563594a783dcc57"
    }
  ]
}''')
encoded=[]
for item in spec['parts']:
 p=root/item['name']
 assert p.is_file() and not p.is_symlink()
 data=p.read_bytes()
 assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],item['name']
 encoded.append(data)
raw=base64.b64decode(b''.join(encoded).replace(b'\n',b''),validate=True)
assert len(raw)==spec['archive_bytes'] and hashlib.sha256(raw).hexdigest()==spec['archive_sha256']
archive=zipfile.ZipFile(io.BytesIO(raw))
assert sorted(archive.namelist())==['install-update.py', 'payload/README.txt', 'payload/SHA256SUMS', 'payload/owner-build.json', 'payload/reims-build.json', 'payload/reims_vgpu.h', 'payload/run.sh', 'update.json']
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
