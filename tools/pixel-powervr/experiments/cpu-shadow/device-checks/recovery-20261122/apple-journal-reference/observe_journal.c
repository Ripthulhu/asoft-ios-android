/* Adapter for the pinned Apple fsck_hfs journal reader. */
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/types.h>

#include "fsck_journal.h"

/* Clang emits only global Blocks for this adapter and the Apple reader. */
void *_NSConcreteGlobalBlock[32];

enum {
    SECTOR_BYTES = 512,
    JOURNAL_BYTES = 8 * 1024 * 1024,
    MAX_CALLBACKS = 4096,
};

static const uint64_t volume_bytes = UINT64_C(16) * 1024 * 1024 * 1024;
static size_t callbacks;
static size_t payload_bytes;
static int callback_failed;

void *__real_malloc(size_t size);

void *__wrap_malloc(size_t size)
{
    if (size > JOURNAL_BYTES) {
        errno = ENOMEM;
        return NULL;
    }
    return __real_malloc(size);
}

static int observe_block(off_t offset, void *buffer, size_t size)
{
    if (offset < 0 || offset % SECTOR_BYTES != 0 || size == 0 ||
        size % SECTOR_BYTES != 0 || size > JOURNAL_BYTES - payload_bytes ||
        (uint64_t)offset > volume_bytes - size || callbacks == MAX_CALLBACKS) {
        callback_failed = 1;
        return -1;
    }

    /* Match the diagnostic's HFS checksum without printing any payload. */
    const uint8_t *bytes = buffer;
    uint32_t checksum = 0;
    for (size_t index = 0; index < size; ++index) {
        checksum = (checksum << 8) ^ (checksum + bytes[index]);
    }
    if (printf("%" PRIu64 " %zu %08" PRIx32 "\n",
               (uint64_t)offset, size, ~checksum) < 0) {
        callback_failed = 1;
        return -1;
    }
    payload_bytes += size;
    ++callbacks;
    return 0;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        return 2;
    }
    char *end;
    errno = 0;
    long number = strtol(argv[1], &end, 10);
    if (errno != 0 || end == argv[1] || *end != '\0' ||
        number < 3 || number > INT32_MAX) {
        return 2;
    }
    int fd = (int)number;
    struct stat status;
    int flags = fcntl(fd, F_GETFL);
    if (flags < 0 || (flags & O_ACCMODE) != O_RDONLY ||
        fstat(fd, &status) != 0 || !S_ISREG(status.st_mode) ||
        status.st_size != JOURNAL_BYTES) {
        return 2;
    }

    /* This subprocess reports failures through its exit status. */
    if (signal(SIGABRT, SIG_DFL) == SIG_ERR ||
        signal(SIGBUS, SIG_DFL) == SIG_ERR ||
        signal(SIGSEGV, SIG_DFL) == SIG_ERR) {
        return 2;
    }
    int result = journal_open(fd, 0, JOURNAL_BYTES, SECTOR_BYTES, 0,
                              "journal extract",
                              ^int(off_t offset, void *bytes, size_t size) {
                                  return observe_block(offset, bytes, size);
                              });
    if (result != 0 || callback_failed || fflush(stdout) == EOF) {
        return 1;
    }
    return 0;
}
