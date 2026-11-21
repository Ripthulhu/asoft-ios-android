import ctypes as c
import json
import os
from pathlib import Path
import resource

lib = c.CDLL(None, use_errno=True)
class Iovec(c.Structure):
    _fields_ = [('base', c.c_void_p), ('length', c.c_size_t)]
source = c.create_string_buffer(b'R')
target = c.create_string_buffer(1)
local = Iovec(c.addressof(target), 1)
remote = Iovec(c.addressof(source), 1)
lib.process_vm_readv.argtypes = [c.c_int, c.POINTER(Iovec), c.c_ulong, c.POINTER(Iovec), c.c_ulong, c.c_ulong]
lib.process_vm_readv.restype = c.c_ssize_t
c.set_errno(0)
result = lib.process_vm_readv(os.getpid(), c.byref(local), 1, c.byref(remote), 1, 0)
error = c.get_errno()
record = {
    'self_process_vm_readv': {'return': result, 'errno': error, 'error': os.strerror(error), 'correct_byte': result == 1 and target.raw == b'R'},
    'rlimit_as': resource.getrlimit(resource.RLIMIT_AS),
    'rlimit_data': resource.getrlimit(resource.RLIMIT_DATA),
    'host_page_bytes': os.sysconf('SC_PAGE_SIZE'),
    'large_allocation': 'Not retried here; full-gate logs record two 34359738368-byte allocation failures.',
    'policy_changed': False,
}
Path(__file__).with_suffix('.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
print(json.dumps(record, indent=2))
