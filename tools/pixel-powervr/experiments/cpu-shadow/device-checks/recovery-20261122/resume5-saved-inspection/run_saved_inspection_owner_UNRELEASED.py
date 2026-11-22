#!/usr/bin/env python3
"""Two-phase owner for a fresh resume5 saved-firstboot inspection.

The accepted firstboot, both failed inspections and completed diagnostic records
remain pinned and preserved. The revised inspector is installed only in a fresh
source directory after independent review. Actual fresh preflight pins and a
separately owned ready process observer remain necessary for execution release.
Native runtime, own-child cleanup, resource floors and read-only/fsck acceptance
remain unchanged. Revised inspector source pins are deliberately unbound in this draft.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import types

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OWNER = BASE / 'ios26-saved-inspection-resume5-owner'
FIRSTBOOT_OWNER = BASE / 'ios26-firstboot-owner-resume1'
FIRSTBOOT_ADAPTER = BASE / 'run-ios26-firstboot-memfd-adapter-resume1.py'
FIRSTBOOT_SOURCE = BASE / 'run-ios26-firstboot-owner-resume1.py'
GUARD_WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1')
GUARD_SOURCE = Path('/data/local/tmp/pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py')
PREP = Path('/data/local/tmp/pixel-prep-e9cc754')
RUNNER = Path('/data/local/tmp/pixel-prep-runner-f4d64db')
INSPECTOR = Path('/data/local/tmp/pixel-saved-checks-resume5')
PREVIOUS_INSPECTOR = Path('/data/local/tmp/pixel-saved-checks-counter1')
INSPECTOR_SOURCE_PINS = None
WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume5')
PREVIOUS_OWNER = BASE / 'ios26-saved-inspection-resume1-owner'
PREVIOUS_WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume1')
PREVIOUS_SOURCE = BASE / 'run-ios26-saved-inspection-resume1.py'
PREVIOUS_FAILURE_PINS = {'/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume1-execute-launch.json': {'bytes': 2751,
                                                                                                    'sha256': '04a6815565e27a75bb5d9aa4331feb67dcf5c327ac873664f939f45fa73398df'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume1-owner/command.json': {'bytes': 302,
                                                                                                   'sha256': '7328cd41a8ae9c03c20972c17ff140ef11abbead9c0661466c4d708cbf800142'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume1-owner/exit.json': {'bytes': 906,
                                                                                                'sha256': '88ecd2bcd09ab476ba5c75b465851628aab71f97f6ca492c75769c364afab5ea'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume1-owner/owner.json': {'bytes': 532,
                                                                                                 'sha256': '166482948c3c74375d879beab92dafe40bd2f9f483b75b01c1fba1350d3ec642'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume1-owner/preflight-command.json': {'bytes': 287,
                                                                                                             'sha256': '02f58851d6fdb4de2de7b9d5a5211b332fdefdd3b50daf65ba609e910ef68688'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume1-owner/preflight-exit.json': {'bytes': 920,
                                                                                                          'sha256': 'ebdd1946b8f6f13781452ebb5c90e1dfb1eb3e153fc0b820b3c1e1b1ada4e748'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume1-owner/preflight-owner.json': {'bytes': 513,
                                                                                                           'sha256': '65de64bcba4a9a35cc6a7cdcd4b06ee31341c76ea009bcc95e20e7aaf560867b'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume1-owner/preflight.json': {'bytes': 9070,
                                                                                                     'sha256': '84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume1-owner/prerequisites.json': {'bytes': 6423,
                                                                                                         'sha256': '8d9414aec789323d98367fbb38a21e3b5b341b2275b2a87faebe1628c313893d'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume1-preflight-launch.json': {'bytes': 1170,
                                                                                                      'sha256': 'e9c5aa498bf2c8eca622e8d1ff22a2f19c79ed0ab72ff8dc4e58e61ca4051349'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume1.py': {'bytes': 25168,
                                                                                       'sha256': '87526ee42417108f46a8ca03b3fece1cd154f2c439a9c6492f20c97fd6981bb9'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/saved-inspection-resume1-install.json': {'bytes': 621,
                                                                                       'sha256': 'a696005d00f1fdc1ebb1f5e7d4b80a24de76c6c00cbbe7ec21b05d184aaa266e'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume1/a1/expected-policy.json': {'bytes': 271,
                                                                               'sha256': '30ea96f4531f6e24ffd4b47042e578dbbbc6392477a37844e88b48febc77de26'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume1/a1/inspection-result.json': {'bytes': 828,
                                                                                 'sha256': 'ca8cc61e13e16b92d8287d7732e3f14606b2d85d9ad260c7446520aff5b4fde5'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume1/a1/launch.json': {'bytes': 2359,
                                                                      'sha256': 'bfae6ba75761a5c3f8b2d919107d4227c48393b19fa010943acfaef944189893'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume1/a1/vm-result.json': {'bytes': 1269,
                                                                         'sha256': '7f69c932974a98adf001d2011e2b5af0880d9fbd9cfdf6fefd89eb0aa6943cbb'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume1/a1/vm.child.json': {'bytes': 45,
                                                                        'sha256': '29da0c05a5f5132cd06bb41a34bd5621f0456e66d680ff096ed9dc16ebe9eabf'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume1/inspection-session.json': {'bytes': 8625,
                                                                               'sha256': 'ae080326f88f92960381a4e368f5afe52ae710ca1af74064675692d079ce2457'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume1/result.json': {'bytes': 828,
                                                                   'sha256': 'ca8cc61e13e16b92d8287d7732e3f14606b2d85d9ad260c7446520aff5b4fde5'}}
RESUME2_OWNER = BASE / 'ios26-saved-inspection-resume2-owner'
RESUME2_WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume2')
HEADER_SOURCE = BASE / 'run-ios26-hfs-header-diagnostic-resume2.py'
HEADER_WORK = BASE / 'ios26-hfs-header-diagnostic-resume2'
PREVIOUS_MONITOR = BASE / 'ios26-saved-inspection-resume2-observer-procstat1'
RESUME2_PRESERVATION_PINS = {'/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-hfs-header-capability-resume2/result.json': {'bytes': 1467,
                                                                                                 'sha256': 'ad6584a12fd72b421932dadb93bec6c95548142f677767f7737a8d34c9310061'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-hfs-header-capability-resume3/result.json': {'bytes': 1481,
                                                                                                 'sha256': 'fd9f444caae344caf9bf6b3058e3d377c28c60c4b486132bac96323fa35dd1e0'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-hfs-header-capability-resume4/result.json': {'bytes': 2659,
                                                                                                 'sha256': '897cb1faaab342ff576fcc8a3e8d958282f0d44fd0162c445457853cf1d8c11c'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-hfs-header-diagnostic-resume2/result.json': {'bytes': 14542,
                                                                                                 'sha256': 'd768516e7cc9846e35aefa5f7583797b4cc0c129402a16994965501c69882ba6'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume2-observer-procstat1/events.jsonl': {'bytes': 19750,
                                                                                                                'sha256': 'b26c38a1b51b415a1a185f42ccc031973a84508ab45b5a782314a56aa2922d10'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume2-observer-procstat1/exit.json': {'bytes': 478,
                                                                                                             'sha256': '4af8f8a2feeb3e8103bfaf61c8393aa58f94c9ea01e32f06e51bbaee3cdbb920'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume2-observer-procstat1/ready.json': {'bytes': 3839,
                                                                                                              'sha256': '4c3abfebaeee33ce4c1c59f5195292116b016bc869d27ff5f0e38a5047981a3d'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume2-observer-procstat1/summary.json': {'bytes': 12455,
                                                                                                                'sha256': '5544a60116e34a99d44c58b103e51139cd0502bac95c3b543b58fdfac7e44e9d'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume2-owner/exit.json': {'bytes': 906,
                                                                                                'sha256': '83a9f8f145d78b64b2cb555576f0de73f22a9658d118ce034e8db813ed4e81bd'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-hfs-header-diagnostic-resume2.py': {'bytes': 22740,
                                                                                            'sha256': 'e79c0fbc472ae2a875164565802feffc4fad0a630571970f6e68d7251801bdcd'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume2-observer-procstat1.py': {'bytes': 37878,
                                                                                                          'sha256': 'a49ec9b11ba0fefda03e2a688e86422df53851c9ec146f21591961da20104bd2'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume2.py': {'bytes': 35799,
                                                                                       'sha256': '445f16736ff3f0c4aca2f9d825f4b71b9264bc24b177fe3a8281ca9c6e0f1e0b'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume2/a1/expected-policy.json': {'bytes': 271,
                                                                               'sha256': '62b374f2088e8eb92f7aa8b32b899c09cac0e0dd2cbcc55a1e0e5bbfb5f9455a'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume2/a1/files/inspection/result.json': {'bytes': 1972,
                                                                                       'sha256': '4548dc39a1c014152ab090d57a1c9ceabde4d94afb67a5d54feec4fae9454de2'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume2/a1/vm-result.json': {'bytes': 1266,
                                                                         'sha256': '05d3c3f5ebc3cb658c4283fd5412fdac32a8caf49e291188bdf8eee2a0377ee5'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume2/result.json': {'bytes': 3705,
                                                                   'sha256': 'b7c788a7581db8c4061d2e97f6600c20ac9a0cdd3f47816e92c6c7276d54dfb1'}}


RESUME4_OWNER = BASE / 'ios26-saved-inspection-resume4-owner'
RESUME4_WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume4')
RESUME4_MONITOR = BASE / 'ios26-saved-inspection-resume4-observer-procstat1'
JIB_SOURCE = BASE / 'run-ios26-root-jib-diagnostic-resume4.py'
JIB_WORK = BASE / 'ios26-root-jib-diagnostic-resume4'
RESUME4_PRESERVATION_PINS = {'/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-root-jib-diagnostic-resume4/result.json': {'bytes': 14246,
                                                                                               'sha256': '5d39c9a0fb16c794577abaf4ab7155ee5f352d46cb7027e03b571055f10d5061'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-observer-procstat1/events.jsonl': {'bytes': 48601,
                                                                                                                'sha256': '81d8df8425d3be6df9bed237fead205ee27f15aec40078742eabc029bd63409a'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-observer-procstat1/exit.json': {'bytes': 478,
                                                                                                             'sha256': '149820613afba9b5b1ba4279198efe7e7ffc5e8cc202b89b46997c292421b903'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-observer-procstat1/ready.json': {'bytes': 3839,
                                                                                                              'sha256': '98bd34d1c290027db202ce1ea94c57029fe2c520d5c88c601eecd32ca1c9c215'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-observer-procstat1/summary.json': {'bytes': 12457,
                                                                                                                'sha256': '998a6c55622a953eaaf3151d69a97b8cbfdb505b4b1f0422b208d0f7d371c5cd'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-owner/exit.json': {'bytes': 905,
                                                                                                'sha256': '42d8672e28ee85245517dada0d016299bf4a22d833cd5cfae968585755cb1d49'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-root-jib-diagnostic-resume4.py': {'bytes': 41544,
                                                                                          'sha256': 'cf31bf3489bed645dbd59f8e024f6759150f9262f1480e6d9d4ff53f855b9480'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume4/a1/expected-policy.json': {'bytes': 271,
                                                                               'sha256': '2592a62d9f9169d015a8822221dae848bc3b346b8f81e4c69ec1ebe531796a3d'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume4/a1/files/inspection/result.json': {'bytes': 1948,
                                                                                       'sha256': '72f505c0407a145575408d09a0817d808358a7a7149fe7a13c0290b756f2ce8e'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume4/a1/vm-result.json': {'bytes': 1264,
                                                                         'sha256': 'b34b5f2195732900b4710116e70db9c0daa2a7b1c0533c8c397d18f12b611cb2'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume4/result.json': {'bytes': 3681,
                                                                   'sha256': '39516c6f49bab5114dd612780f8e6113e869bcac44dea90127f20901710ff51c'}}

PYTHON = '/data/data/com.termux/files/usr/bin/python'
COMMAND = [PYTHON, '-I', '-B', str(INSPECTOR / 'inspect_ios26_firstboot.py'),
           '--guard-work', str(GUARD_WORK), '--work', str(WORK)]
FIRSTBOOT_COMMAND = [PYTHON, '-I', '-B', str(FIRSTBOOT_ADAPTER), '--execute']
STAGES = ['shared-fetch', 'shared-unpack', 'shared-build', 'ios26-fetch',
          'ios26-decrypt', 'ios26-rootfs', 'ios26-partition', 'ios26-firstboot']
SESSION_DIGEST = '9ce5f5b8e4953ac54fddd854c5b4a606c2b9866814af6b1d520c2b590e987a6b'
FIRSTBOOT_SUCCESS_PINS = {'/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1/guard-observations.json': {'bytes': 13249, 'sha256': 'c6b967916eee233f8d6bfe4efbd13dee002caf2fc1af1b61dc5bb0ff9027703a'}, '/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1/guard-session.json': {'bytes': 20936, 'sha256': 'dbb13619f92e0349036a71088511db4eeb978aaae6a22428976761ef54b2873e'}, '/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1/result.json': {'bytes': 33910, 'sha256': '8d2731493b0ccdad2056677e56774f11718d9d01fb35e895023963d98847f8e3'}, '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-resume1/command.json': {'bytes': 176, 'sha256': 'b1fa143253a989f64c347d792324897bbebeb6ae3197c4824a69dff7dbb608f2'}, '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-resume1/exit.json': {'bytes': 4104, 'sha256': 'd7efc91338833952c35637bdbb0f53260d35a5a9c3a9bba60979240a7d3abc53'}, '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-resume1/owner.json': {'bytes': 667, 'sha256': 'b37b5d9e806689e93be5bcf41a82ac0d86c15e116c37919fe3109ba3c5e26545'}, '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-firstboot-memfd-adapter-resume1.py': {'bytes': 9101, 'sha256': 'ede70023bc1e05b08730b48fab1016c3e665c0e83469509e5b8b74c6f2364ec7'}, '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-firstboot-owner-resume1.py': {'bytes': 42490, 'sha256': '862af55267f7ecd1273faf8f161e4065161f1bf49a5df6614cfb2571fc95d473'}, '/data/local/tmp/pixel-prep-e9cc754/checkpoints/ios26-firstboot.json': {'bytes': 803, 'sha256': '0c3418d053477d73d210eb8a22dd28e49cff61ff5140f77b6c97d4c96c8c079e'}}  # Physically observed accepted 07-0004.
SOURCE_HASHES = {
    GUARD_SOURCE: 'ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674',
    INSPECTOR / 'inspect_ios26_firstboot.py': None if INSPECTOR_SOURCE_PINS is None else INSPECTOR_SOURCE_PINS['inspect_ios26_firstboot.py']['sha256'],
    INSPECTOR / 'inspect_ios26_firstboot_guest.py': None if INSPECTOR_SOURCE_PINS is None else INSPECTOR_SOURCE_PINS['inspect_ios26_firstboot_guest.py']['sha256'],
    RUNNER / 'prepare_ios26.py': 'c77bc990e56dcb47d651f9c054c41313a6671498a5b2494e96bb522ae868fb1a',
    RUNNER / 'prepare_ios26_stages.py': '89e242b0c98dd994a04cabaeadc52f8d566ff3fd33fae37e1979ab81fd32b952',
    RUNNER / 'cold_boot_ios26.py': '6a57ed164864eef20aeffd34b14b675a8ac597c20583c9f179414a36b4ccbdeb',
    RUNNER / 'cold_boot_dt.py': '6931310e1318a6397ee2d7eead966bd0fcdeaae9c10038ca2f2aa01de1a45f7e',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def canonical(path):
    require(path.is_absolute() and path.resolve(strict=True) == path, 'noncanonical path: ' + str(path))
    return path


def read_bytes(path, limit=4 << 20):
    canonical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit,
                'not bounded ordinary metadata: ' + str(path))
        body = stream.read(limit + 1)
        require(len(body) <= limit, 'metadata grew beyond bound: ' + str(path))
        return body


def read_json(path):
    return json.loads(read_bytes(path))


def create(name, value):
    canonical(OWNER)
    fd = os.open(OWNER / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(OWNER, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def identity(pid):
    require(type(pid) is int and pid > 0, 'invalid process identity')
    try:
        raw = (Path('/proc') / str(pid) / 'stat').read_text()
    except FileNotFoundError:
        return None
    return {'pid': pid, 'starttime': int(raw[raw.rfind(')') + 2:].split()[19])}


def absent(record, label, start_key='starttime'):
    require(set(record) == {'pid', start_key} and type(record[start_key]) is int,
            'invalid recorded identity: ' + label)
    require(identity(record['pid']) != {'pid': record['pid'], 'starttime': record[start_key]},
            'recorded process is still present: ' + label)


def refuse_live_children():
    for path in (PREP / 'attempts').glob('*/*.child.json'):
        absent(read_json(path), str(path), 'start_ticks')
    marker = (str(PREP) + '/attempts/').encode()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / 'cmdline').read_bytes()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        require(not (marker in command and
                     (b'qemu-system-aarch64' in command or b'com.asoft.ios.PrepareInputs' in command)),
                'unreaped preparation process: PID ' + entry.name)


def expected_success_paths():
    return {str(p) for p in (FIRSTBOOT_SOURCE, FIRSTBOOT_ADAPTER,
            *(FIRSTBOOT_OWNER / name for name in ('owner.json', 'command.json', 'exit.json')),
            *(GUARD_WORK / name for name in ('guard-session.json', 'guard-observations.json', 'result.json')),
            PREP / 'checkpoints/ios26-firstboot.json')}


def require_finalized():
    require(type(INSPECTOR_SOURCE_PINS) is dict and set(INSPECTOR_SOURCE_PINS) ==
            {'inspect_ios26_firstboot.py', 'inspect_ios26_firstboot_guest.py'},
            'unreleased owner: independently reviewed revised inspector pins required')
    for name, pin in INSPECTOR_SOURCE_PINS.items():
        require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
                type(pin['bytes']) is int and 0 < pin['bytes'] <= 256 << 10 and
                type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']),
                'malformed revised inspector source pin: ' + name)
    require(type(FIRSTBOOT_SUCCESS_PINS) is dict and set(FIRSTBOOT_SUCCESS_PINS) == expected_success_paths(),
            'unreleased owner: actual accepted firstboot pins must be finalized')
    for path, pin in FIRSTBOOT_SUCCESS_PINS.items():
        require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
                type(pin['bytes']) is int and 0 < pin['bytes'] <= 2 << 20 and
                type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']),
                'malformed firstboot pin: ' + path)


def expected_previous_paths():
    return {str(path) for path in (
        PREVIOUS_SOURCE,
        *(BASE / name for name in ('saved-inspection-resume1-install.json',
            'ios26-saved-inspection-resume1-preflight-launch.json',
            'ios26-saved-inspection-resume1-execute-launch.json')),
        *(PREVIOUS_OWNER / name for name in ('prerequisites.json', 'preflight-command.json',
            'preflight-owner.json', 'preflight-exit.json', 'preflight.json', 'command.json', 'owner.json', 'exit.json')),
        *(PREVIOUS_WORK / name for name in ('inspection-session.json', 'result.json')),
        *(PREVIOUS_WORK / 'a1' / name for name in ('inspection-result.json', 'expected-policy.json',
            'launch.json', 'vm-result.json', 'vm.child.json')))}


def previous_failure_inputs():
    """Read and preserve the exact failed predecessor; change no old artifact."""
    require(type(PREVIOUS_FAILURE_PINS) is dict and set(PREVIOUS_FAILURE_PINS) == expected_previous_paths(),
            'previous failed inspection bindings are incomplete')
    canonical(PREVIOUS_OWNER)
    canonical(PREVIOUS_WORK)
    require(not WORK.is_relative_to(PREVIOUS_WORK) and not PREVIOUS_WORK.is_relative_to(WORK) and
            not OWNER.is_relative_to(PREVIOUS_OWNER) and not PREVIOUS_OWNER.is_relative_to(OWNER),
            'new inspection paths overlap the preserved failure')
    fd = os.open(canonical(PREVIOUS_WORK / 'owner.lock'), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'preserved inspection lock is not ordinary')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        inputs = {}
        for path, pin in PREVIOUS_FAILURE_PINS.items():
            require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
                    type(pin['bytes']) is int and 0 < pin['bytes'] <= 4 << 20 and
                    type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']),
                    'malformed previous inspection pin')
            body = read_bytes(Path(path))
            require(len(body) == pin['bytes'] and sha(body) == pin['sha256'],
                    'preserved inspection input changed: ' + path)
            inputs[path] = sha(body)
        started = read_json(PREVIOUS_OWNER / 'owner.json')
        exited = read_json(PREVIOUS_OWNER / 'exit.json')
        command = [PYTHON, '-I', '-B', str(PREVIOUS_INSPECTOR / 'inspect_ios26_firstboot.py'),
                   '--guard-work', str(GUARD_WORK), '--work', str(PREVIOUS_WORK), '--execute']
        require(started.get('schema') == exited.get('schema') == 1 and
                started.get('command') == exited.get('command') == read_json(PREVIOUS_OWNER / 'command.json') == command and
                all(started.get(key) == exited.get(key) for key in ('started_utc', 'wrapper', 'runner')) and
                exited.get('exit_code') == exited.get('owner_exit_code') == 2 and exited.get('accepted') is False and
                exited.get('runner_started') is True and exited.get('runner_reaped') is True and
                exited.get('forced_runner') is False and exited.get('cleanup_errors') == [] and
                exited.get('wrapper_error') == 'ValueError: inspector exited 2' and exited.get('finished_utc'),
                'previous inspection is not the preserved cleanly reaped failure')
        absent(started['wrapper'], 'previous inspection wrapper')
        absent(started['runner'], 'previous inspector')
        absent(read_json(PREVIOUS_WORK / 'a1/vm.child.json'), 'previous inspection VM', 'start_ticks')
        result = read_json(PREVIOUS_WORK / 'result.json')
        require(result == read_json(PREVIOUS_WORK / 'a1/inspection-result.json') and
                result.get('schema') == 1 and result.get('status') == 'INCOMPLETE' and
                result.get('error') == 'RuntimeError: VM stage incomplete; see ' + str(PREVIOUS_WORK / 'a1/vm-result.json') and
                result.get('full_backing_chain_unchanged') is True and result.get('preparation_and_guard_unchanged') is True and
                result.get('identity_error') is None and
                all(result.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')),
                'previous failed inspection result changed')
        vm = read_json(PREVIOUS_WORK / 'a1/vm-result.json')
        cleanup, witness = vm.get('cleanup', {}), vm.get('witnesses', {})
        require(vm.get('stage') == 'saved-firstboot-inspection' and vm.get('status') == 'INCOMPLETE' and
                vm.get('natural_exit') is True and vm.get('error') is None and vm.get('done_codes') == [0] and
                vm.get('out_sizes') == [10240] and cleanup.get('exit_code') == 0 and cleanup.get('echild') is True and
                cleanup.get('forced_qemu') is False and cleanup.get('forced_descendants') == [13344] and
                cleanup.get('errors') == [] and
                all(witness.get(k) is True for k in ('native_initialization', 'native_execution', 'native_svc_final')) and
                witness.get('fatal_markers') == [], 'previous native cleanup failure differs')
        return inputs
    finally:
        os.close(fd)


def resume2_failure_inputs():
    """Preserve actual failed native inspection and its read-only diagnosis."""
    for old_work, old_owner in ((PREVIOUS_WORK, PREVIOUS_OWNER), (RESUME2_WORK, RESUME2_OWNER)):
        require(not WORK.is_relative_to(old_work) and not old_work.is_relative_to(WORK) and
                not OWNER.is_relative_to(old_owner) and not old_owner.is_relative_to(OWNER),
                'new inspection overlaps preserved work')
    inputs, pinned_bodies = {}, {}
    for name, pin in RESUME2_PRESERVATION_PINS.items():
        require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
                type(pin['bytes']) is int and 0 < pin['bytes'] <= 4 << 20 and
                type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']),
                'malformed completed diagnostic pin')
        body = read_bytes(Path(name))
        require({'bytes': len(body), 'sha256': sha(body)} == pin, 'preserved resume2 evidence changed: ' + name)
        inputs[name] = sha(body)
        pinned_bodies[name] = body
    # Reuse the exact reviewed diagnostic's metadata validator without running
    # its main, opening images, creating files, or spawning any tool/guest.
    diagnostic = types.ModuleType('preserved_header_metadata_validator')
    diagnostic.__file__ = str(HEADER_SOURCE)
    exec(compile(pinned_bodies[str(HEADER_SOURCE)], str(HEADER_SOURCE), 'exec'), diagnostic.__dict__)
    old = diagnostic.load_bound_owner()
    require(old.OWNER == RESUME2_OWNER and old.WORK == RESUME2_WORK and old.INSPECTOR == PREVIOUS_INSPECTOR and
            diagnostic.OUT == HEADER_WORK and diagnostic.DIAGNOSTIC_SOURCE == HEADER_SOURCE,
            'preserved validator scope differs')
    lock = os.open(canonical(RESUME2_WORK / 'owner.lock'), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(lock).st_mode), 'preserved resume2 lock is not ordinary')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _, _, bound = diagnostic.check_metadata(old)
        for name, pin in bound.items():
            require(name not in inputs or inputs[name] == pin, 'preserved metadata validators disagree')
            inputs[name] = pin
        headers = json.loads(pinned_bodies[str(HEADER_WORK / 'result.json')])
        require(headers.get('schema') == 1 and headers.get('kind') == 'readonly_hfs_header_diagnostic' and
                headers.get('status') == 'READONLY_HFS_HEADERS_OBSERVED' and
                headers.get('source') == {'path': str(HEADER_SOURCE), **RESUME2_PRESERVATION_PINS[str(HEADER_SOURCE)]} and
                headers.get('diagnostic_only') is True and headers.get('inspection_success_claimed') is False and
                headers.get('error') is None and headers.get('preservation_error') is None and
                all(headers.get(k) is True for k in ('disk_identities_unchanged', 'bound_metadata_unchanged', 'bound_tooling_unchanged')) and
                all(headers.get(k) is False for k in ('guest_vm_started', 'mounted', 'replayed', 'repaired', 'fsck_run', 'full_disk_hashes_recomputed')),
                'completed header diagnosis differs')
        absent(headers['owner'], 'completed header diagnostic')
        require(len(headers.get('headers', [])) == len(headers.get('tool_commands', [])) == 8 and
                all(row.get('reaped') is True and row.get('forced') is False and row.get('exit_code') == 0 and
                    not row.get('cleanup_error') for row in headers['tool_commands']), 'header diagnostic cleanup differs')
        for index, row in enumerate(headers['headers']):
            path = HEADER_WORK / ('h' + str(index) + '.bin')
            body = read_bytes(path, 512)
            require(len(body) == row.get('bytes') == 512 and sha(body) == row.get('sha256'), 'retained header bytes changed')
            inputs[str(path)] = sha(body)
        for number, expected_source, status in (
            (2, 'fef35cf4c2921c95e1fb9be3000408f4484498fb6bf019dc3ce0f346fe097928', 'INCOMPLETE'),
            (3, '7029bc14ad7ae5a056caadfd1932d8f4b4eec738ad68fef2bdac67e961c607e8', 'INCOMPLETE'),
            (4, '4264533ff68a0a116aeecbe140de041b1f02b5036f9bf83783d2f4958f1ece8f', 'QEMU_IMG_READ_CAPABILITY_PASSED')):
            probe = json.loads(pinned_bodies[str(BASE / ('ios26-hfs-header-capability-resume' + str(number)) / 'result.json')])
            require(probe.get('kind') == 'native_qemu_img_read_capability_probe' and probe.get('status') == status and
                    probe.get('source_sha256') == expected_source and probe.get('diagnostic_only') is True and
                    probe.get('existing_disk_images_opened') is False and probe.get('guest_vm_started') is False and
                    probe.get('bound_tooling_and_session_unchanged') is True and
                    all(row.get('reaped') is True and row.get('forced') is False and row.get('exit_code') == 0 and
                        not row.get('cleanup_error') for row in probe.get('tool_commands', [])),
                    'preserved capability result differs')
            absent(probe['owner'], 'completed capability probe')
        monitor = json.loads(pinned_bodies[str(PREVIOUS_MONITOR / 'exit.json')])
        summary = json.loads(pinned_bodies[str(PREVIOUS_MONITOR / 'summary.json')])
        expected_observer = {'pid': 11031, 'start_ticks': 8803490}
        require(monitor.get('schema') == summary.get('schema') == 1 and
                monitor.get('status') == summary.get('status') == 'OBSERVATION_FINISHED' and
                monitor.get('exit_code') == 0 and monitor.get('observer') == summary.get('observer') == expected_observer and
                monitor.get('errors') == summary.get('errors') == [] and summary.get('remaining_observed_identities') == [] and
                monitor.get('diagnostic_only') is True and summary.get('diagnostic_only') is True and
                monitor.get('summary') == {'path': str(PREVIOUS_MONITOR / 'summary.json'),
                    **RESUME2_PRESERVATION_PINS[str(PREVIOUS_MONITOR / 'summary.json')]},
                'completed independent observer differs')
        absent(expected_observer, 'completed independent observer', 'start_ticks')
        return inputs
    finally:
        os.close(lock)


def resume4_failure_inputs():
    """Preserve the exact failed inspection, completed observer and JIB diagnosis.

    Reuse the pinned diagnostic's metadata and pure retained-payload validators.
    This function never calls its main/extraction routines or starts a tool/VM.
    """
    require(not WORK.is_relative_to(RESUME4_WORK) and not RESUME4_WORK.is_relative_to(WORK) and
            not OWNER.is_relative_to(RESUME4_OWNER) and not RESUME4_OWNER.is_relative_to(OWNER),
            'new inspection overlaps preserved resume4 work')
    expected = {str(RESUME4_OWNER / 'exit.json'), str(RESUME4_WORK / 'result.json'),
                str(RESUME4_WORK / 'a1/vm-result.json'), str(RESUME4_WORK / 'a1/expected-policy.json'),
                str(RESUME4_WORK / 'a1/files/inspection/result.json'),
                *(str(RESUME4_MONITOR / name) for name in ('ready.json', 'exit.json', 'summary.json', 'events.jsonl')),
                str(JIB_SOURCE), str(JIB_WORK / 'result.json')}
    require(set(RESUME4_PRESERVATION_PINS) == expected, 'exact resume4/JIB preservation paths required')
    inputs, cached = {}, {}
    for name, pin in RESUME4_PRESERVATION_PINS.items():
        require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
                type(pin['bytes']) is int and 0 < pin['bytes'] <= 4 << 20 and
                type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']),
                'malformed resume4/JIB preservation pin')
        body = read_bytes(Path(name), pin['bytes'])
        require({'bytes': len(body), 'sha256': sha(body)} == pin, 'preserved resume4/JIB evidence changed: ' + name)
        inputs[name], cached[name] = sha(body), body

    d = types.ModuleType('preserved_root_jib_metadata_validator')
    d.__file__ = str(JIB_SOURCE)
    exec(compile(cached[str(JIB_SOURCE)], str(JIB_SOURCE), 'exec'), d.__dict__)
    old = d.load_bound_owner()
    require(old.OWNER == RESUME4_OWNER and old.WORK == RESUME4_WORK and
            old.INSPECTOR == Path('/data/local/tmp/pixel-saved-checks-resume3') and
            d.OUT == JIB_WORK and d.DIAGNOSTIC_SOURCE == JIB_SOURCE and d.MONITOR == RESUME4_MONITOR and
            d.RECEIPT_PINS == {name: pin for name, pin in RESUME4_PRESERVATION_PINS.items()
                               if name not in (str(JIB_SOURCE), str(JIB_WORK / 'result.json'))},
            'preserved JIB validator scope differs')
    lock = os.open(canonical(RESUME4_WORK / 'owner.lock'), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(lock).st_mode), 'preserved resume4 lock is not ordinary')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _, inspected, bound = d.check_metadata(old)
        layouts = d.load_header_layouts(old, bound)
        for name, expected_sha in bound.items():
            require(name not in inputs or inputs[name] == expected_sha, 'preserved metadata validators disagree')
            inputs[name] = expected_sha
        result = json.loads(cached[str(JIB_WORK / 'result.json')])
        require(result.get('schema') == 1 and result.get('kind') == 'readonly_root_jib_diagnostic' and
                result.get('status') == 'READONLY_ROOT_JIB_COMPARISON_OBSERVED' and
                result.get('source') == {'path': str(JIB_SOURCE), **RESUME4_PRESERVATION_PINS[str(JIB_SOURCE)]} and
                result.get('root_layouts') == layouts and result.get('limits') == d.LIMITS and
                result.get('actual_failed_inspection_pins') == 9 and
                result.get('previous_full_hash_records') == [row['record'] for row in inspected['backing_chain']],
                'completed JIB diagnostic scope differs')
        require(all(result.get(key) is True for key in
                    ('diagnostic_only', 'disk_identities_unchanged', 'bound_metadata_unchanged',
                     'bound_tooling_unchanged', 'recorded_inspection_processes_absent')) and
                all(result.get(key) is False for key in
                    ('inspection_success_claimed', 'difference_classified_as_safe', 'guest_vm_started', 'fsck_run',
                     'mounted', 'replayed', 'repaired', 'journal_pointer_followed', 'raw_bytes_exported',
                     'full_disk_hashes_recomputed')) and
                result.get('error') is None and result.get('preservation_error') is None,
                'completed JIB diagnostic preservation or scope differs')
        absent(result['owner'], 'completed root JIB diagnostic')
        images = [canonical(Path(row['identity']['path'])) for row in inspected['backing_chain']]
        require(len(images) == 2 and images[0] != images[1] and all(path.is_relative_to(PREP) for path in images),
                'preserved JIB image pair differs')
        session = read_json(PREP / 'session.json')
        tool = canonical(Path(session['tooling']) / 'tools/qemu-img')
        require(result.get('tool') == {'path': str(tool), **d.TOOL_PIN} and
                result.get('capability') == {'path': str(d.CAPABILITY_RESULT), **d.CAPABILITY_PIN, 'passed': True},
                'completed JIB tooling or capability differs')
        plan = d.read_plan(images, layouts, tool)
        rows = result.get('tool_commands')
        require(type(rows) is list and len(rows) == len(plan) == 16, 'fixed JIB extraction inventory differs')
        sectors = []
        for expected_row, row in zip(plan, rows):
            require(row.get('label') == expected_row['label'] and row.get('command') == expected_row['command'] and
                    row.get('exit_code') == 0 and row.get('reaped') is True and row.get('forced') is False and
                    not row.get('cleanup_error'), 'preserved JIB extraction was not clean')
            path = Path(expected_row['output'])
            body = read_bytes(path, 512)
            require(len(body) == 512, 'retained JIB sector has changed size')
            sectors.append(body)
            inputs[str(path)] = sha(body)
            for suffix in ('command.json', 'exit.json', 'stdout'):
                retained = JIB_WORK / (row['label'] + '.' + suffix)
                retained_body = read_bytes(retained, d.LIMITS['tool_output_bytes'])
                inputs[str(retained)] = sha(retained_body)
                if suffix == 'exit.json':
                    require(json.loads(retained_body) == row, 'retained JIB child exit differs')
                elif suffix == 'stdout':
                    require(len(retained_body) == row.get('output_bytes') and sha(retained_body) == row.get('output_sha256'),
                            'retained JIB child output differs')
                else:
                    require(json.loads(retained_body) == {'label': row['label'], 'command': row['command'],
                            'pid': None, 'exit_code': None, 'reaped': False, 'forced': False},
                            'retained JIB child command differs')
        blocks = []
        for name, selected_sectors in (('saved', sectors[:8]), ('baseline', sectors[8:])):
            path = JIB_WORK / (name + '-jib.bin')
            body = read_bytes(path, 4096)
            require(body == d.assemble_jib(selected_sectors), 'retained complete JIB differs from its sectors')
            blocks.append(body)
            inputs[str(path)] = sha(body)
        projected = [d.decode_jib(body, layout) for body, layout in zip(blocks, layouts)]
        comparison = d.compare_jibs(blocks[0], blocks[1], d.LIMITS['difference_ranges'])
        require(result.get('jibs') == projected and result.get('comparison') == comparison and
                [row['flags'] for row in projected] == [1, 5] and comparison['equal'] is False and
                comparison['differing_bytes'] == comparison['range_count'] == 1 and
                comparison['ranges'] == [{'start': 3, 'end': 4}] and comparison['omitted_ranges'] == 0 and
                comparison['ranges_truncated'] is False,
                'retained JIB comparison differs from the actual observed transition')
        # The diagnostic observed a flag difference. The new immutable guest
        # must independently prove the authored baseline and initialized-empty
        # journal and pass both read-only fscks; this metadata check grants none
        # of those conclusions.
        path = JIB_WORK / 'session.json'
        inputs[str(path)] = sha(read_bytes(path))
        absent(result['owner'], 'completed root JIB diagnostic after preservation')
        return inputs
    finally:
        os.close(lock)


def prerequisites():
    """Metadata/identity/lock checks. The immutable inspector validates disks."""
    require_finalized()
    require(os.geteuid() == 0, 'root phone owner required')
    for folder in (BASE, FIRSTBOOT_OWNER, GUARD_WORK, PREP, RUNNER, INSPECTOR, WORK.parent):
        canonical(folder)
    require(not os.path.lexists(WORK), 'inspection output already exists; preserve it')
    require(len(str(WORK)) <= 55, 'inspection work path exceeds inspector bound')
    inputs = previous_failure_inputs()
    for name, pin in resume2_failure_inputs().items():
        require(name not in inputs or inputs[name] == pin, 'preserved predecessor bindings disagree')
        inputs[name] = pin
    for name, pin in resume4_failure_inputs().items():
        require(name not in inputs or inputs[name] == pin, 'preserved resume4/JIB bindings disagree')
        inputs[name] = pin

    def checked(path, expected=None, size=None):
        body = read_bytes(path)
        inputs[str(path)] = actual = sha(body)
        require(expected is None or actual == expected, 'changed bound input: ' + str(path))
        require(size is None or len(body) == size, 'changed bound input size: ' + str(path))
        return body

    for path, pin in FIRSTBOOT_SUCCESS_PINS.items():
        checked(Path(path), pin['sha256'], pin['bytes'])
    for path, pin in SOURCE_HASHES.items():
        checked(path, pin, INSPECTOR_SOURCE_PINS[path.name]['bytes'] if path.parent == INSPECTOR else None)
    checked(Path(__file__).resolve(strict=True))
    first = read_json(FIRSTBOOT_OWNER / 'owner.json')
    exited = read_json(FIRSTBOOT_OWNER / 'exit.json')
    require(first.get('schema') == exited.get('schema') == 1 and
            first.get('command') == read_json(FIRSTBOOT_OWNER / 'command.json') == FIRSTBOOT_COMMAND and
            all(exited.get(k) == first.get(k) for k in ('command', 'wrapper', 'guard', 'started_utc')) and
            exited.get('exit_code') == exited.get('owner_exit_code') == 0 and
            exited.get('accepted') is True and exited.get('guard_started') is True and
            exited.get('guard_reaped') is True and exited.get('forced_guard') is False and
            exited.get('wrapper_error') is None and exited.get('cleanup_errors') == [] and
            exited.get('finished_utc'), 'resume1 firstboot owner has not accepted and cleanly reaped')
    for key in ('wrapper', 'guard'):
        absent(first[key], 'firstboot ' + key)
    guard = read_json(GUARD_WORK / 'result.json')
    require(guard.get('schema') == 1 and guard.get('status') == 'GUARDED_FIRSTBOOT_COMPLETE' and
            guard.get('checkpoint_accepted_by_guard') is True and guard.get('bound_inputs_unchanged') is True and
            guard.get('original_firstboot_checkpoint_present') is True and
            guard.get('actual_attempt', {}).get('attempt') == str(PREP / 'attempts/07-0004') and
            all(not guard.get(k) for k in ('error', 'identity_error', 'attempt_error')),
            'resume1 guard has not accepted the actual 07-0004 checkpoint')
    acceptance = exited.get('acceptance', {})
    require(acceptance.get('result_sha256') == inputs[str(GUARD_WORK / 'result.json')] and
            acceptance.get('checkpoint_sha256') == inputs[str(PREP / 'checkpoints/ios26-firstboot.json')] and
            acceptance.get('guard_session_file_sha256') == inputs[str(GUARD_WORK / 'guard-session.json')] and
            acceptance.get('guard_observations_sha256') == inputs[str(GUARD_WORK / 'guard-observations.json')] and
            acceptance.get('attempt') == str(PREP / 'attempts/07-0004'), 'outer firstboot acceptance differs')
    require(all(guard.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')),
            'unexpected firstboot completion claims')
    session = json.loads(checked(PREP / 'session.json'))
    require(digest(session) == SESSION_DIGEST, 'preparation session differs')
    folder = canonical(PREP / 'checkpoints')
    require({p.name for p in folder.iterdir()} == {s + '.json' for s in STAGES},
            'exact eight-checkpoint firstboot boundary required')
    previous, checkpoints = None, {}
    for stage in STAGES:
        path = folder / (stage + '.json')
        body = checked(path)
        record = json.loads(body)
        require(record.get('schema') == 1 and record.get('status') == 'STAGE_COMPLETE' and
                record.get('stage') == stage and record.get('session_sha256') == SESSION_DIGEST and
                record.get('previous_sha256') == previous, 'disconnected/incomplete checkpoint: ' + stage)
        previous = checkpoints[str(path)] = sha(body)
        if stage == 'ios26-firstboot':
            require(record.get('attempt') == str(PREP / 'attempts/07-0004'), 'wrong accepted firstboot attempt')
    require(guard.get('checkpoint') == {'path': str(PREP / 'checkpoints/ios26-firstboot.json'),
            'sha256': checkpoints[str(PREP / 'checkpoints/ios26-firstboot.json')]}, 'guard checkpoint binding differs')
    guard_files = {str(GUARD_WORK / name): inputs[str(GUARD_WORK / name)]
                   for name in ('guard-session.json', 'guard-observations.json', 'result.json')}
    require(set(guard['actual_attempt'].get('files', {})) ==
            {'stage-inputs.json', 'launch.json', 'vm-result.json', 'stage-result.json'}, 'incomplete firstboot attempt metadata')
    for name, pin in guard['actual_attempt']['files'].items():
        path = PREP / 'attempts/07-0004' / name
        body = checked(path, pin['sha256'], pin['bytes'])
        guard_files[str(path)] = sha(body)
    fd = os.open(canonical(PREP / 'owner.lock'), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'preparation lock is not ordinary')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        refuse_live_children()
    finally:
        os.close(fd)
    return {'inputs': inputs, 'checkpoints': checkpoints, 'guard_files': guard_files}


def validate_preflight(public, current):
    session = public.get('inspection_session', {})
    require(public.get('schema') == 1 and public.get('status') == 'PREFLIGHT_READY' and
            all(public.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')) and
            session.get('schema') == 1 and session.get('kind') == 'ios26_saved_firstboot_inspection' and
            session.get('prep_work') == str(PREP) and session.get('runner_dir') == str(RUNNER) and
            session.get('prep_session_sha256') == current['inputs'][str(PREP / 'session.json')] and
            session.get('checkpoints') == current['checkpoints'] and session.get('guard_files') == current['guard_files'] and
            session.get('guard_work') == str(GUARD_WORK) and session.get('guard_source') == str(GUARD_SOURCE) and
            session.get('guard_source_sha256') == SOURCE_HASHES[GUARD_SOURCE] and
            session.get('source_directory') == str(INSPECTOR) and
            session.get('inspector_sources') == {p.name: h for p, h in SOURCE_HASHES.items() if p.parent == INSPECTOR} and
            session.get('frozen_sources') == {p.name: h for p, h in SOURCE_HASHES.items() if p.parent == RUNNER} and
            session.get('readonly') is True and session.get('native_required') is True and session.get('tcg_retry') is False and
            all(session.get(k) is False for k in ('mounts_allowed', 'replay_allowed', 'repair_allowed',
                                               'boot_complete', 'gpu_path_complete', 'app_gate_changed')) and
            session.get('helper_ram_mib') == 2048 and
            session.get('bounds') == {'helper_seconds': 7200, 'max_log_mib': 64, 'min_free_mib': 1536, 'min_available_mib': 512} and
            type(session.get('backing_chain')) is list and len(session['backing_chain']) == 2,
            'inspector preflight did not accept the exact saved firstboot boundary')


def resources():
    match = re.search(rb'^MemAvailable:\s+(\d+) kB$', Path('/proc/meminfo').read_bytes(), re.M)
    require(match is not None and int(match[1]) * 1024 >= 2816 << 20, 'inspection needs 2816 MiB MemAvailable')
    free = os.statvfs(PREP)
    require(free.f_bavail * free.f_frsize >= 1536 << 20, 'inspection needs 1536 MiB free storage')


def accept_result(current):
    value = read_json(WORK / 'result.json')
    expected = read_json(OWNER / 'preflight.json')['inspection_session']
    actual = read_json(WORK / 'inspection-session.json')
    witness, cleanup = value.get('native_witnesses', {}), value.get('cleanup', {})
    require(value.get('schema') == 1 and value.get('status') == 'SAVED_FIRSTBOOT_INSPECTION_PASSED' and
            actual == expected and value.get('inspection_session_sha256') == digest(expected) and
            value.get('full_backing_chain_unchanged') is True and value.get('preparation_and_guard_unchanged') is True and
            value.get('natural_exit') is True and not value.get('error') and not value.get('identity_error') and
            witness.get('native_initialization') is True and witness.get('native_execution') is True and
            witness.get('fatal_markers') == [] and cleanup.get('exit_code') == 0 and cleanup.get('echild') is True and
            cleanup.get('forced_qemu') is False and cleanup.get('forced_descendants') == [] and cleanup.get('errors') == [] and
            all(value.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')),
            'inspector did not produce a complete unchanged native inspection')
    outputs = value.get('outputs', {})
    require(set(outputs) == {'inspection/result.json', 'inspection/fsck-system.txt', 'inspection/fsck-data.txt'},
            'inspection output inventory incomplete')
    for name, pin in outputs.items():
        path = WORK / 'a1/files' / name
        require(pin.get('path') == str(path.relative_to(WORK)) and pin.get('bytes') == path.stat().st_size and
                pin.get('sha256') == sha(read_bytes(path)), 'inspection returned file differs: ' + name)
    guest = read_json(WORK / 'a1/files/inspection/result.json')
    require(guest == value.get('guest_result') and guest.get('status') == 'SAVED_FIRSTBOOT_INSPECTION_PASSED' and
            guest.get('errors') == [] and guest.get('cleanup_errors') == [] and guest.get('raw_metadata_unchanged') is True and
            guest.get('readonly_attachments') is True and all(guest.get(k) is False for k in ('mounted', 'replayed', 'repaired')),
            'raw inspection result disagrees with host acceptance')
    for path, pin in current['inputs'].items():
        require(sha(read_bytes(Path(path))) == pin, 'bound firstboot/source/checkpoint changed during inspection')
    refuse_live_children()
    absent(read_json(WORK / 'a1/vm.child.json'), 'inspection VM', 'start_ticks')
    return sha(read_bytes(WORK / 'result.json'))


def run_phase(execute, current):
    prefix, output = ('', 'run.log') if execute else ('preflight-', 'preflight.json')
    command = COMMAND + (['--execute'] if execute else [])
    # Exclusive command receipt reserves this phase before any child can start.
    create(prefix + 'command.json', command)
    started, child, child_identity = utc(), None, None
    forced, error, returncode, accepted, result_sha = False, None, None, False, None
    cleanup_errors = []
    wrapper = identity(os.getpid())

    def interrupted(number, _frame):
        raise InterruptedError('outer owner signal ' + str(number))

    old = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        fd = os.open(OWNER / output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
            child_identity = identity(child.pid)
            require(child_identity is not None, 'spawned inspector has no process identity')
            create(prefix + 'owner.json', {'schema': 1, 'started_utc': started,
                   'wrapper': wrapper, 'runner': child_identity, 'command': command})
            returncode = child.wait(timeout=7800 if execute else 1800)
            stream.flush()
            os.fsync(stream.fileno())
        require(returncode == 0, 'inspector exited ' + str(returncode))
        if execute:
            result_sha = accept_result(current)
        else:
            validate_preflight(read_json(OWNER / output), current)
            require(prerequisites() == current, 'prerequisites changed during read-only preflight')
        accepted = True
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        for number in old:
            signal.signal(number, signal.SIG_IGN)
        try:
            if child is not None and child.poll() is None:
                # Only this unreaped direct child is signalled. Its own native
                # supervisor retains QMP shutdown, subreaping and PDEATHSIG.
                child.send_signal(signal.SIGTERM)
                try:
                    child.wait(timeout=180)
                except subprocess.TimeoutExpired:
                    forced = True
                    child.kill()
                    child.wait(timeout=30)
        except BaseException as exc:
            cleanup_errors.append(type(exc).__name__ + ': ' + str(exc))
        if child is not None:
            returncode = child.returncode
    finally:
        owner_exit_code = 0 if accepted and not error and not forced and not cleanup_errors and returncode == 0 else 2
        try:
            for number in old:
                signal.signal(number, signal.SIG_IGN)
            stdout_sha = None
            if not execute and (OWNER / output).exists():
                try:
                    stdout_sha = sha(read_bytes(OWNER / output))
                except Exception as exc:
                    cleanup_errors.append('preflight output hash: ' + str(exc))
                    owner_exit_code = 2
            create(prefix + 'exit.json', {'schema': 1, 'started_utc': started, 'finished_utc': utc(),
                   'wrapper': wrapper, 'runner': child_identity, 'exit_code': returncode,
                   'owner_exit_code': owner_exit_code, 'command': command, 'wrapper_error': error,
                   'forced_runner': forced, 'cleanup_errors': cleanup_errors, 'runner_started': child is not None,
                   'runner_reaped': child is not None and returncode is not None, 'accepted': accepted,
                   'stdout_sha256': stdout_sha, 'inspection_result_sha256': result_sha,
                   'requires_owned_process_recheck': True})
        finally:
            for number, handler in old.items():
                signal.signal(number, handler)
    return owner_exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight', action='store_true')
    modes.add_argument('--execute', action='store_true')
    parser.add_argument('--preflight-sha256')
    parser.add_argument('--preflight-bytes', type=int)
    args = parser.parse_args(argv)
    try:
        current = prerequisites()
        if args.preflight:
            require(args.preflight_sha256 is None and args.preflight_bytes is None, 'preflight cannot consume execution pins')
            OWNER.mkdir(mode=0o700)
            create('prerequisites.json', current)
        else:
            require(type(args.preflight_sha256) is str and re.fullmatch('[0-9a-f]{64}', args.preflight_sha256) and
                    type(args.preflight_bytes) is int and 0 < args.preflight_bytes <= 2 << 20,
                    'actual observed preflight SHA-256 and bytes required')
            canonical(OWNER)
            require(read_json(OWNER / 'prerequisites.json') == current, 'preflight inputs changed')
            receipt = read_json(OWNER / 'preflight-exit.json')
            startup = read_json(OWNER / 'preflight-owner.json')
            body = read_bytes(OWNER / 'preflight.json')
            require(sha(body) == args.preflight_sha256 and len(body) == args.preflight_bytes, 'observed preflight pin differs')
            require(receipt.get('schema') == 1 and receipt.get('command') == COMMAND and
                    read_json(OWNER / 'preflight-command.json') == COMMAND and
                    receipt.get('exit_code') == receipt.get('owner_exit_code') == 0 and
                    receipt.get('accepted') is True and receipt.get('runner_started') is True and receipt.get('runner_reaped') is True and
                    receipt.get('forced_runner') is False and receipt.get('wrapper_error') is None and
                    receipt.get('cleanup_errors') == [] and receipt.get('finished_utc') and
                    startup.get('command') == COMMAND and startup.get('started_utc') == receipt.get('started_utc') and
                    all(startup.get(k) == receipt.get(k) for k in ('wrapper', 'runner')) and
                    sha(body) == receipt.get('stdout_sha256'), 'missing, failed or mismatched read-only preflight receipt')
            absent(startup['wrapper'], 'preflight wrapper')
            absent(startup['runner'], 'preflight inspector')
            validate_preflight(json.loads(body), current)
            resources()
        return run_phase(args.execute, current)
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'OWNER_REFUSED', 'error': type(exc).__name__ + ': ' + str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
