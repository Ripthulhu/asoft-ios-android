import datetime,json,pathlib,subprocess,sys,time
base=pathlib.Path("/data/local/tmp/pixel-gpu-transfer-sxtv33sh")
command=json.loads((base/"helper-smoke-command-f4d64db.json").read_text())
command.insert(1,"-u")
command.append("--execute")
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
print("\033[2J\033[HNATIVE HELPER SMOKE START",start,flush=True)
print("Bound: 180 seconds; authored input only; native EL0 required.",flush=True)
with (base/"helper-smoke-run-f4d64db.log").open("xb") as log:
    child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    for line in iter(child.stdout.readline,b""):
        log.write(line);log.flush()
        sys.stdout.buffer.write(line);sys.stdout.buffer.flush()
    code=child.wait()
finish=datetime.datetime.now(datetime.timezone.utc).isoformat()
record={"started_utc":start,"finished_utc":finish,"exit_code":code,"command":command}
with (base/"helper-smoke-exit-f4d64db.json").open("x") as f:json.dump(record,f,indent=2);f.write("\n")
print("\033[2J\033[HHELPER SMOKE EXIT",code,flush=True)
result=pathlib.Path("/data/local/tmp/pixel-smoke-e9cc754/result.json")
if result.exists():print(result.read_text())
else:print((base/"helper-smoke-run-f4d64db.log").read_text()[-12000:])
