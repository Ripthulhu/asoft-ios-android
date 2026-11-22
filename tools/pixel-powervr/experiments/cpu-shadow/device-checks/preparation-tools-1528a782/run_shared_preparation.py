import datetime,json,os,pathlib,signal,subprocess
base=pathlib.Path("/data/local/tmp/pixel-gpu-transfer-sxtv33sh")
command=json.loads((base/"shared-prep-command-f4d64db.json").read_text())
command.insert(1,"-u")
command.append("--execute")
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
def identity(pid):
    p=pathlib.Path("/proc")/str(pid)/"stat"
    text=p.read_text()
    return {"pid":pid,"starttime":int(text[text.rfind(")")+2:].split()[19])}
with (base/"shared-prep-run-f4d64db.log").open("xb") as log:
    child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
    owner={"started_utc":start,"wrapper":identity(os.getpid()),"runner":identity(child.pid),"command":command}
    with (base/"shared-prep-owner-f4d64db.json").open("x") as f:json.dump(owner,f,indent=2);f.write("\n")
    try:
        code=child.wait()
    except BaseException:
        if child.poll() is None:
            child.send_signal(signal.SIGTERM)
            try:child.wait(timeout=60)
            except subprocess.TimeoutExpired:
                child.kill();child.wait()
        raise
record={"started_utc":start,"finished_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"exit_code":code,"command":command}
with (base/"shared-prep-exit-f4d64db.json").open("x") as f:json.dump(record,f,indent=2);f.write("\n")
