import base64,hashlib,io,json,os,sys,zipfile
from pathlib import Path,PurePosixPath
os.umask(0o077)
root=Path(sys.argv[1])
spec=json.loads(r'''{
  "archive_bytes": 1970913,
  "archive_sha256": "a1868ef98cf69e83af82033fef89de4ac2209a7433093dc5d0269e4253f3faed",
  "installer_sha256": "444d2dc1276731d0e75b095b99d17e66a12ac9dc4c9fbe2b6d698e17ab546df3",
  "parts": [
    {
      "name": "part-000.b64",
      "bytes": 147504,
      "sha256": "555c95fd58ccff253064401cdca1abca305e70ec36f70fb91528513fe42e9f37"
    },
    {
      "name": "part-001.b64",
      "bytes": 147504,
      "sha256": "4bcbea3796a1f511e944fa8231a3f7f123de75b542acef1a6861447fd644b04f"
    },
    {
      "name": "part-002.b64",
      "bytes": 147504,
      "sha256": "a3e70a262f9eca98e8e7929d6f101880f94711f611053b078ff814d4e84ecf84"
    },
    {
      "name": "part-003.b64",
      "bytes": 147504,
      "sha256": "686b4add52101a1e580f46dfd33db9e30934e7dff39f6388f127cd3f40837590"
    },
    {
      "name": "part-004.b64",
      "bytes": 147504,
      "sha256": "2f2820fa6d85bc84050ac0ea40c9ff08baed8c861c8d0a0c6f8c24689a852fa2"
    },
    {
      "name": "part-005.b64",
      "bytes": 147504,
      "sha256": "1d52b937cab06d01960eed540102b1c10133d4e3f414cc24ae2619ffa9bd2c1b"
    },
    {
      "name": "part-006.b64",
      "bytes": 147504,
      "sha256": "0bdea27510ec319b3aa161359fe7fffad386ac6adbef3bc1b454b635259a8bff"
    },
    {
      "name": "part-007.b64",
      "bytes": 147504,
      "sha256": "34eee0db253f509935674c7fc4fbb6d3b078ab84f1e0621271701f05dd048a11"
    },
    {
      "name": "part-008.b64",
      "bytes": 147504,
      "sha256": "8d872bcef3b5eaa8d875712a3c95e30f88a58b76310681296bb02fa580c7ba78"
    },
    {
      "name": "part-009.b64",
      "bytes": 147504,
      "sha256": "def5d526b144a22f3db1aca0f3ad0e09d4ed8f43e7869050f504edea57355219"
    },
    {
      "name": "part-010.b64",
      "bytes": 147504,
      "sha256": "d8c64ef3604bc161528d12ebcf4279a4d2f3df9626fd9d92b51d8e5b7c888d9d"
    },
    {
      "name": "part-011.b64",
      "bytes": 147504,
      "sha256": "cccce4201fff0e251198ad41c1a05b8a1e66c7142c29412e48f530ecfdef047c"
    },
    {
      "name": "part-012.b64",
      "bytes": 147504,
      "sha256": "e818ad1898d734922f4d5977ae6a80a934abe91a335196bdd4b107c1ea5dbc26"
    },
    {
      "name": "part-013.b64",
      "bytes": 147504,
      "sha256": "3a681ea427a70cb9b6f391d32b2db04f84861f5941fc4bf813e685751586e2d8"
    },
    {
      "name": "part-014.b64",
      "bytes": 147504,
      "sha256": "22229f179d60cdde3375eef1c1c5f8747881c7a1feafe65deb947eecbda3bf63"
    },
    {
      "name": "part-015.b64",
      "bytes": 147504,
      "sha256": "cedcb9c4f1075f2bf383a1f35d5b3f40e08d72cc8e512eeb2707088f945a5a78"
    },
    {
      "name": "part-016.b64",
      "bytes": 147504,
      "sha256": "98f17a808ff0ada7dae4f92ac3a3f8a23352298487e718abc97449a4e3ce2fe9"
    },
    {
      "name": "part-017.b64",
      "bytes": 121172,
      "sha256": "498914f2b053475bdca1fa8589eca4415e2b65203c2031b3dcdea2a9bcf632b8"
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
assert sorted(archive.namelist())==['install-update.py', 'owner-delta.zst', 'payload/README.txt', 'payload/SHA256SUMS', 'payload/owner-build.json', 'payload/reims-build.json', 'payload/reims_vgpu.h', 'payload/run.sh', 'update.json']
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
assert hashlib.sha256((out/'install-update.py').read_bytes()).hexdigest()==spec['installer_sha256']
with (root/'reims-native-update.zip').open('xb') as file:file.write(raw)
print('REIMS_TRANSFER=PASS parts='+str(len(spec['parts']))+' bytes='+str(len(raw))+' archive_sha256='+hashlib.sha256(raw).hexdigest())
print('INSTALLER_READY='+str(out/'install-update.py'))
