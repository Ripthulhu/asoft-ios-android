#!/usr/bin/env python3
"""Compile actual engine guard functions into an ordinary-host test harness.

This checks strict rejection predicates, not AArch64 execution, QEMU integration,
signals, a GPU mapping, or an Android memory contract.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def definition(source, name):
    match = re.search(r'static bool ' + name + r'\(', source)
    if not match:
        raise RuntimeError('Missing production guard ' + name)
    opening = source.index('{', match.start())
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    src = a.source / 'target/arm/tcg/native-el0.c'
    s = src.read_text()
    defs = ['native_gpu_overlap', 'native_gpu_code_valid', 'native_gpu_fill_valid',
            'native_gpu_fault_allowed', 'native_gpu_completion_allowed']
    constants = re.findall(r'^#define (?:GPU_\w+|FD_INDEX_CC)\s+[^\n]+', s, re.M)
    structs = '\n'.join(re.search(r'typedef struct ' + n + r' \{.*?\} ' + n + ';', s, re.S)[0]
                        for n in ('StubFill', 'NativeGpuShared'))
    enum_fill = re.search(r'enum \{ STUB_FILL_RAM.*?\};', s, re.S)[0]
    code = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <signal.h>
#include <sys/mman.h>
#include "native_gpu_protocol.h"
typedef enum { MMU_DATA_LOAD, MMU_DATA_STORE, MMU_INST_FETCH } MMUAccessType;
'''
    code += '\n'.join(constants) + '\n' + structs + '\n' + enum_fill + '\n'
    code += '\n\n'.join(definition(s, n) for n in defs)
    code += r'''
int main(void) {
    assert(!native_gpu_overlap(9, 0, 9, 1));
    assert(!native_gpu_overlap(0x1000, 0x4000, 0x5000, 0x4000));
    assert(native_gpu_overlap(0x1000, 0x4001, 0x5000, 0x4000));
    assert(native_gpu_overlap(0x5000, 0x4000, 0x1000, 0x4001));
    assert(native_gpu_overlap(UINT64_MAX-4, 4, UINT64_MAX-3, 1));
    uint8_t code[NGP_VIEW_BYTES] = {0};
    memcpy(code, ngp_payload_words, sizeof(ngp_payload_words));
    assert(native_gpu_code_valid(code, sizeof(code)));
    assert(!native_gpu_code_valid(code, sizeof(code)-1));
    unsigned code_cases=0;
    for (unsigned bit=0; bit<NGP_PAYLOAD_BYTES*8; bit++) {
        code[bit/8] ^= 1u << (bit%8);
        assert(!native_gpu_code_valid(code, sizeof(code)));
        code[bit/8] ^= 1u << (bit%8); code_cases++;
    }
    for (unsigned i=NGP_PAYLOAD_BYTES; i<sizeof(code); i+=257) {
        code[i]=1; assert(!native_gpu_code_valid(code,sizeof(code))); code[i]=0; code_cases++;
    }
    code[sizeof(code)-1]=1; assert(!native_gpu_code_valid(code,sizeof(code))); code[sizeof(code)-1]=0;
    NativeGpuShared g={.ready=1,.generation=73,.gpa=NGP_GPA,.va=NGP_DATA_VA,.len=NGP_VIEW_BYTES,
        .backing_len=NGP_ALLOCATION_BYTES,.backing_off=NGP_VIEW_OFFSET,.fd_index=1};
    StubFill code_fill={.va=NGP_CODE_VA,.len=NGP_VIEW_BYTES,.off=0,.gen=17,
        .provider_generation=73,.prot=PROT_READ|PROT_EXEC,.fd_index=FD_INDEX_CC,.kind=STUB_FILL_RAM};
    StubFill data_fill={.va=NGP_DATA_VA,.len=NGP_VIEW_BYTES,.off=NGP_VIEW_OFFSET,.gen=17,
        .provider_generation=73,.prot=PROT_READ|PROT_WRITE,.fd_index=1,.kind=STUB_FILL_GPU};
    assert(native_gpu_fill_valid(&code_fill,&g,17,0,false));
    assert(native_gpu_fill_valid(&data_fill,&g,17,1,false));
    unsigned fill_cases=0;
    for(unsigned ack=0;ack<4;ack++) for(unsigned installed=0;installed<2;installed++) {
        assert(native_gpu_fill_valid(&code_fill,&g,17,ack,installed)==(!installed&&ack==0));
        assert(native_gpu_fill_valid(&data_fill,&g,17,ack,installed)==(!installed&&ack==1)); fill_cases+=2;
    }
    /* Every data-fill byte belongs to an exact field; reject every bit flip. */
    for(size_t bit=0;bit<sizeof(data_fill)*8;bit++) {
        StubFill bad=data_fill; ((uint8_t*)&bad)[bit/8]^=1u<<(bit%8);
        assert(!native_gpu_fill_valid(&bad,&g,17,1,false)); fill_cases++;
    }
    NativeGpuShared badg=g; badg.ready=0;
    assert(!native_gpu_fill_valid(&data_fill,&badg,17,1,false));
    badg=g; badg.generation++;
    assert(!native_gpu_fill_valid(&data_fill,&badg,17,1,false));
    assert(!native_gpu_fill_valid(&data_fill,&g,18,1,false));
    StubFill bad=code_fill; bad.prot|=PROT_WRITE;
    assert(!native_gpu_fill_valid(&bad,&g,17,0,false));
    bad=code_fill; bad.fd_index=0; assert(!native_gpu_fill_valid(&bad,&g,17,0,false));
    bad=code_fill; bad.off=1; assert(!native_gpu_fill_valid(&bad,&g,17,0,false));
    int sigs[]={SIGSEGV,SIGBUS,SIGILL,SIGTRAP,SIGSYS};
    int codes[]={SEGV_ACCERR,SEGV_MAPERR,0};
    uint64_t pcs[]={NGP_CODE_VA,NGP_LOAD_PC,NGP_STORE_PC,NGP_SVC_PC,NGP_COMPLETE_PC};
    uint64_t addresses[]={NGP_CODE_VA,NGP_DATA_VA,NGP_DATA_VA+8,NGP_STACK_VA,0};
    unsigned ecs[]={0x20,0x21,0x24,0x25,0};
    unsigned fault_cases=0,accepted=0;
    for(unsigned phase=0;phase<=7;phase++) for(unsigned i=0;i<5;i++)
    for(unsigned j=0;j<3;j++) for(unsigned k=0;k<5;k++) for(unsigned m=0;m<5;m++)
    for(unsigned n=0;n<5;n++) for(unsigned access=0;access<3;access++) {
        bool expected=sigs[i]==SIGSEGV&&codes[j]==SEGV_ACCERR&&
            ((phase==NGP_ENTRY&&pcs[k]==NGP_CODE_VA&&addresses[m]==NGP_CODE_VA&&ecs[n]==0x20&&access==MMU_INST_FETCH)||
             (phase==NGP_CODE_MAP&&pcs[k]==NGP_LOAD_PC&&addresses[m]==NGP_DATA_VA&&ecs[n]==0x24&&access==MMU_DATA_LOAD));
        bool actual=native_gpu_fault_allowed(phase,sigs[i],codes[j],pcs[k],addresses[m],ecs[n],access);
        assert(actual==expected); fault_cases++; accepted+=actual;
    }
    assert(accepted==2);
    uint64_t input=UINT64_C(0x6a1b2c346a1b2c34),output=UINT64_C(0x615c5026615c515d);
    assert(native_gpu_completion_allowed(NGP_DATA_MAP,NGP_COMPLETE_PC,input,output,NGP_DATA_VA,NGP_SVC_TAG,0xd4001001));
    unsigned completion_cases=0;
    for(unsigned field=0;field<7;field++) for(unsigned bit=0;bit<32;bit++) {
        uint64_t fields[]={NGP_DATA_MAP,NGP_COMPLETE_PC,input,output,NGP_DATA_VA,NGP_SVC_TAG,0xd4001001};
        fields[field]^=UINT64_C(1)<<bit;
        assert(!native_gpu_completion_allowed(fields[0],fields[1],fields[2],fields[3],fields[4],fields[5],fields[6]));
        completion_cases++;
    }
    printf("ENGINE_GUARD_FIXTURE=PASS code_corruptions=%u fill_cases=%u fault_cases=%u accepted_fault_shapes=%u completion_corruptions=%u GPU_tested=0 AArch64_executed=0\n",
        code_cases+1,fill_cases+6,fault_cases,accepted,completion_cases);
}
'''
    harness = a.out / 'engine-guards-generated.c'
    harness.write_text(code)
    binary = a.out / 'engine-guard-fixture'
    subprocess.run(['gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-I', str(a.source / 'target/arm/tcg'), str(harness), '-o', str(binary)], check=True)
    log = subprocess.check_output([str(binary)], text=True, timeout=15)
    (a.out / 'engine-guard-fixture.log').write_text(log)
    record = {'source_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
              'extracted_production_functions': defs, 'result': 'PASS',
              'GPU_tested': False, 'AArch64_executed': False,
              'generated_harness_sha256': hashlib.sha256(harness.read_bytes()).hexdigest()}
    (a.out / 'engine-guard-checks.json').write_text(json.dumps(record, indent=2) + '\n')
    print(log, end='')


if __name__ == '__main__':
    main()
