#!/usr/bin/env python3
"""Preserve already completed phone logs; never launches a diagnostic.

Arguments: PACKAGE CONTROL_RESULTS GPU_RESULTS TRANSFER_DIRECTORY.
The shared output parent is the existing project evidence directory on this phone.
"""
import hashlib,json,os,pathlib,re,shutil,sys,tempfile
root,control,gpu,transfer=map(pathlib.Path,sys.argv[1:5])
shared=pathlib.Path(tempfile.mkdtemp(prefix="native-gpu-one-region-",dir="/sdcard/Download/pixel-native-resume-mdPitH"))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
record={"package":str(root),"runs":{},"raw_logs_exported_to_assistant":False}
proof=[]
for label,case in (("control",control),("gpu",gpu)):
 text=(case/"diagnostic.txt").read_text()
 events=[dict(token.split("=",1) for token in line.split()[1:]) for line in text.splitlines() if line.startswith("OWNER_EVENT ")]
 result=[line for line in text.splitlines() if line.startswith("RESULT=")]
 selected=[line for line in text.splitlines() if line.startswith(("device=","host_page=","cached_producer_memory","producer_memory","independent_readback_memory","OWNER_GPU_GEOMETRY","OWNER_ENGINE_STOP","OWNER_TREE_CLOSED","OWNER_NATIVE_PROTOCOL","NATIVE_GPU_INDEPENDENT_READBACK_ALL_WORDS","NATIVE_GPU_GUARDS","native-el0: enters","native-el0: tpidrro-trap code-copies","RESULT="))]
 record["runs"][label]={"directory":str(case),"context":(case/"context.txt").read_text(),"events":events,"selected":selected,"diagnostic_sha256":sha(case/"diagnostic.txt")}
 for name in ("diagnostic.txt","context.txt","integrity.txt","summary.txt"):
  shutil.copyfile(case/name,shared/(label+"-"+name))
 shutil.copyfile(root/(label+"-runner.txt"),shared/(label+"-runner.txt"))
 proof.extend([label.upper()+" "+result[-1], "directory="+case.name, "raw_log_sha256="+sha(case/"diagnostic.txt")])
 if label=="gpu":
  proof.extend((case/"context.txt").read_text().splitlines()[:4])
  proof.extend(selected)
  for e in events:
   proof.append("EVENT "+e["phase"]+" pc="+e["pc"]+" inval="+e["invalidation"])
  for key in ("generation","owner","qemu","factory","stub","tid","input","output"):
   proof.append(key+"="+events[-1][key])
reg=(root/"tpidrro-regression-runner.txt").read_text()
regdir=pathlib.Path(re.findall(r"^RESULTS=(.+)$",reg,re.M)[-1])
record["regression"]={"directory":str(regdir),"runner_sha256":sha(root/"tpidrro-regression-runner.txt"),"selected":[line for line in reg.splitlines() if (line.startswith(("BENCHMARK_EXIT=","NATIVE_TPIDRRO_TRAP_BENCH_PASS=","native-el0: enters","native-el0: tpidrro-trap cpu")) or re.match(r"\[cpu[01]\] (T7 |EXIT )",line))]}
proof.extend(["REGRESSION"]+record["regression"]["selected"])
for name in ("benchmark.txt","disabled-native.txt","conflicting-modes.txt","hashes.txt"):
 shutil.copyfile(regdir/name,shared/("regression-"+name))
shutil.copyfile(root/"tpidrro-regression-runner.txt",shared/"regression-runner.txt")
for name in ("installation.json","transfer-result.json"):
 shutil.copyfile(transfer/name,shared/name)
for name,value in (("device-record.json",json.dumps(record,indent=2)+"\n"),("proof.txt","\n".join(proof)+"\n")):
 with (shared/name).open("w") as f:
  f.write(value);f.flush();os.fsync(f.fileno())
for p in shared.iterdir():
 with p.open("rb") as f: os.fsync(f.fileno())
print("SHARED_EVIDENCE="+str(shared))
print((shared/"proof.txt").read_text())
