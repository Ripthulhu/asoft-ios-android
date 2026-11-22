import hashlib,json,os,pathlib,secrets,struct,subprocess
base=pathlib.Path("/data/local/tmp/pixel-gpu-transfer-sxtv33sh")
tools=pathlib.Path("/data/local/tmp/pixel-tools-1528a782")
root=base/"tools-probe-1528a782"
root.mkdir(mode=0o700)
env={"PATH":"/system/bin:/system/xbin:/data/data/com.termux/files/usr/bin","LD_LIBRARY_PATH":str(tools/"lib")}
with (root/"qemu-img.log").open("xb") as f:
    q=subprocess.run([str(tools/"tools/qemu-img"),"--version"],env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=20)
assert q.returncode==0,(root/"qemu-img.log").read_text()
plain=b"ASOFT authored JNI decoder probe "+secrets.token_hex(16).encode()+b"\n"
compressed=b"bvx-"+struct.pack("<I",len(plain))+plain+b"bvx$"
def der(tag,data):
    n=len(data)
    length=bytes([n]) if n<128 else bytes([128+(n.bit_length()+7)//8])+n.to_bytes((n.bit_length()+7)//8,"big")
    return bytes([tag])+length+data
body=der(0x16,b"IM4P")+der(0x16,b"test")+der(0x16,b"ASOFT authored fixture")+der(4,compressed)+der(0x30,der(2,b"\x01")+der(2,len(plain).to_bytes(2,"big")))
source=root/"authored.im4p"
source.write_bytes(der(0x30,body))
request={"schema":1,"op":"im4p","output_root":str(root),"input":str(source),"input_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"output":str(root/"decoded.bin"),"result_file":str(root/"result.json")}
(root/"request.json").write_text(json.dumps(request))
for key in ("ANDROID_ROOT","ANDROID_DATA","ANDROID_ART_ROOT","ANDROID_I18N_ROOT","ANDROID_RUNTIME_ROOT","ANDROID_TZDATA_ROOT","BOOTCLASSPATH","DEX2OATBOOTCLASSPATH","SYSTEMSERVERCLASSPATH"):
    if key in os.environ: env[key]=os.environ[key]
env["CLASSPATH"]=str(tools/"java/classes.dex")
cmd=["/system/bin/app_process","-Djava.library.path="+str(tools/"lib"),"/system/bin","com.asoft.ios.PrepareInputs",str(root/"request.json")]
with (root/"java.log").open("xb") as f:
    j=subprocess.run(cmd,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=30)
print("\033[2J\033[H",end="")
print("QEMU IMAGE TOOL EXIT",q.returncode)
print((root/"qemu-img.log").read_text())
print("CURRENT JAVA JNI EXIT",j.returncode)
print((root/"java.log").read_text())
assert j.returncode==0
result=json.loads((root/"result.json").read_text())
assert result["status"]=="COMPLETE"
decoded=(root/"decoded.bin").read_bytes()
assert decoded==plain
assert result["file"]["sha256"]==hashlib.sha256(plain).hexdigest()
record={"status":"PASS","qemu_img_exit":q.returncode,"java_exit":j.returncode,"jni_fixture":"authored IM4P containing an LZFSE uncompressed block","decoded_bytes":len(decoded),"decoded_sha256":hashlib.sha256(decoded).hexdigest(),"explicit_result":result,"apple_inputs":False,"apk_installed":False}
(root/"probe.json").write_text(json.dumps(record,indent=2)+"\n")
print(json.dumps(record,indent=2))
