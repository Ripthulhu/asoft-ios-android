/* The API-29 NDK libc stub predates the public memfd_create wrapper. QEMU
 * supplies its own syscall fallback; standalone diagnostics need one too.
 * This stays local to the authored diagnostic and does not alter libc or
 * the runtime's API floor. */
#define _GNU_SOURCE
#include <sys/syscall.h>
#include <unistd.h>

#if !defined(__ANDROID__) || __ANDROID_API__ >= 30
#error "This diagnostic shim is only for an Android API below 30"
#endif

int memfd_create(const char *name, unsigned int flags);

int memfd_create(const char *name, unsigned int flags)
{
    return (int)syscall(SYS_memfd_create, name, flags);
}
