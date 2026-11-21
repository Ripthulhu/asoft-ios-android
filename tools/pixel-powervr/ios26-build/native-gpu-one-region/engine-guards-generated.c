
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
#define GPU_BACKING_LEN NGP_ALLOCATION_BYTES
#define GPU_VIEW_LEN    NGP_VIEW_BYTES
#define GPU_BACKING_OFF NGP_VIEW_OFFSET
#define GPU_REGION_GPA  NGP_GPA
#define GPU_CODE_VA     NGP_CODE_VA
#define GPU_DATA_VA     NGP_DATA_VA
#define GPU_LOAD_PC     NGP_LOAD_PC
#define GPU_STORE_PC    NGP_STORE_PC
#define GPU_SVC_PC      NGP_SVC_PC
#define GPU_SVC_NEXT_PC NGP_COMPLETE_PC
#define GPU_READY       NGP_READY
#define GPU_ENTRY       NGP_ENTRY
#define GPU_CODE_MAP    NGP_CODE_MAP
#define GPU_DATA_FAULT  NGP_DATA_FAULT
#define GPU_DATA_MAP    NGP_DATA_MAP
#define GPU_COMPLETE   NGP_COMPLETE
#define FD_INDEX_CC     (-2)            /* StubFill.fd_index: the code cache */
typedef struct StubFill {
    uint64_t va, len, off, gen;
    uint64_t provider_generation; /* independent of the invalidation sequence */
    int32_t prot;               /* PROT_* */
    int32_t fd_index;           /* into StubShm.ram_fd */
    int32_t patch;              /* private copy with the code-page rewrite */
    uint32_t kind;              /* never infer a producer mapping from an fd */
} StubFill;
typedef struct NativeGpuShared {
    uint64_t generation, device, inode;
    uint64_t gpa, va, len, backing_len, backing_off;
    int32_t fd_index;
    uint32_t ready;             /* both factory fd handoffs acknowledged */
} NativeGpuShared;
enum { STUB_FILL_RAM = 0, STUB_FILL_GPU = 0x47505531 };
static bool native_gpu_overlap(uint64_t va, uint64_t len,
                               uint64_t other, uint64_t other_len)
{
    return len && other_len &&
           (va <= other ? other - va < len : va - other < other_len);
}

static bool native_gpu_code_valid(const void *page, size_t len)
{
    const uint8_t *bytes = page;

    if (len != NGP_VIEW_BYTES ||
        memcmp(bytes, ngp_payload_words, sizeof(ngp_payload_words))) {
        return false;
    }
    for (size_t i = sizeof(ngp_payload_words); i < len; i++) {
        if (bytes[i]) {
            return false;
        }
    }
    return true;
}

static bool native_gpu_fill_valid(const StubFill *f, const NativeGpuShared *g,
                                 uint64_t invalidation, uint32_t acknowledgments,
                                 bool installed)
{
    if (!g->ready || !g->generation || g->gpa != GPU_REGION_GPA ||
        g->va != GPU_DATA_VA || g->len != GPU_VIEW_LEN ||
        g->backing_len != GPU_BACKING_LEN || g->backing_off != GPU_BACKING_OFF ||
        g->fd_index != 1 || f->provider_generation != g->generation ||
        f->gen != invalidation || f->patch || installed) {
        return false;
    }
    if (f->kind == STUB_FILL_RAM) {
        return acknowledgments == 0 && f->va == GPU_CODE_VA &&
               f->len == GPU_VIEW_LEN && !(f->off & (GPU_VIEW_LEN - 1)) &&
               f->fd_index == FD_INDEX_CC && f->prot == (PROT_READ | PROT_EXEC);
    }
    return f->kind == STUB_FILL_GPU && acknowledgments == 1 &&
           f->va == GPU_DATA_VA && f->len == GPU_VIEW_LEN &&
           f->off == GPU_BACKING_OFF && f->fd_index == 1 &&
           f->prot == (PROT_READ | PROT_WRITE);
}

static bool native_gpu_fault_allowed(uint32_t phase, int sig, int si_code,
                                    uint64_t pc, uint64_t address,
                                    unsigned eclass, MMUAccessType access)
{
    if (sig != SIGSEGV || si_code != SEGV_ACCERR) {
        return false;
    }
    if (phase == GPU_ENTRY) {
        return pc == GPU_CODE_VA && address == GPU_CODE_VA &&
               eclass == 0x20 && access == MMU_INST_FETCH;
    }
    return phase == GPU_CODE_MAP && pc == GPU_LOAD_PC &&
           address == GPU_DATA_VA && eclass == 0x24 && access == MMU_DATA_LOAD;
}

static bool native_gpu_completion_allowed(uint32_t phase, uint64_t pc,
                                         uint64_t x0, uint64_t x1,
                                         uint64_t x2, uint64_t x16,
                                         uint32_t instruction)
{
    return phase == GPU_DATA_MAP && pc == GPU_SVC_NEXT_PC &&
           x0 == ngp_input() && x1 == ngp_output(x0) &&
           x2 == GPU_DATA_VA && x16 == NGP_SVC_TAG &&
           instruction == ngp_payload_words[8];
}
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
