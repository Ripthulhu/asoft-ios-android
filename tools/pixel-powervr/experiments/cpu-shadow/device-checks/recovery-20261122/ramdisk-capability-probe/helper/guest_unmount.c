#include <stddef.h>
#include <stdint.h>

// iPhoneOS uses the 64-bit statfs layout in XNU bsd/sys/mount.h.
// Only these three strings are consumed. Keep the ABI storage size and alignment.
struct darwin_statfs {
    _Alignas(uint64_t) unsigned char header[72];
    char filesystem[16];
    char mountpoint[1024];
    char source[1024];
    unsigned char reserved[32];
};

_Static_assert(sizeof(struct darwin_statfs) == 2168, "Darwin statfs ABI size");
_Static_assert(offsetof(struct darwin_statfs, mountpoint) == 88, "Darwin statfs mountpoint offset");
_Static_assert(offsetof(struct darwin_statfs, source) == 1112, "Darwin statfs source offset");

extern uint32_t geteuid(void);
extern int statfs(const char *path, struct darwin_statfs *result);
extern int unmount(const char *path, int flags);
extern int strcmp(const char *first, const char *second);
extern int strncmp(const char *first, const char *second, size_t count);
extern int printf(const char *format, ...);
extern int puts(const char *value);
extern void perror(const char *label);

static const char recovery_mount[] = "/mnt/asoft-recovery";

static const char *skip_digits(const char *text)
{
    while (*text >= '0' && *text <= '9')
        ++text;
    return text;
}

static int is_disk_device(const char *path)
{
    static const char prefix[] = "/dev/disk";
    if (strncmp(path, prefix, sizeof(prefix) - 1) != 0)
        return 0;
    const char *number = path + sizeof(prefix) - 1;
    const char *end = skip_digits(number);
    if (end == number)
        return 0;
    if (*end == 's') {
        number = end + 1;
        end = skip_digits(number);
        if (end == number)
            return 0;
    }
    return *end == '\0';
}

int main(int argc, char **argv)
{
    if (geteuid() != 0) {
        puts("ASOFT_UMOUNT_REQUIRES_ROOT");
        return 77;
    }

    struct darwin_statfs observation;
    if (argc == 2 && strcmp(argv[1], "--inspect-root") == 0) {
        if (statfs("/", &observation) != 0) {
            perror("statfs root");
            return 1;
        }
        if (strcmp(observation.mountpoint, "/") != 0) {
            puts("ASOFT_ROOT_MOUNTPOINT_UNEXPECTED");
            return 1;
        }
        printf("ASOFT_ROOT_MOUNT %.*s %.*s\n", 48, observation.source, 16, observation.filesystem);
        return 0;
    }

    if (argc != 3 || strcmp(argv[1], "--unmount") != 0 || !is_disk_device(argv[2])) {
        puts("usage: asoft-unmount --inspect-root | --unmount /dev/diskN[sM]");
        return 64;
    }

    if (statfs(recovery_mount, &observation) != 0) {
        perror("statfs before unmount");
        return 1;
    }
    if (strcmp(observation.mountpoint, recovery_mount) != 0 ||
        strcmp(observation.filesystem, "hfs") != 0 ||
        strcmp(observation.source, argv[2]) != 0) {
        puts("ASOFT_UMOUNT_TARGET_MISMATCH");
        return 1;
    }
    if (unmount(recovery_mount, 0) != 0) {
        perror("unmount");
        return 1;
    }
    if (statfs(recovery_mount, &observation) != 0) {
        perror("statfs after unmount");
        return 1;
    }
    if (strcmp(observation.mountpoint, "/") != 0) {
        puts("ASOFT_UMOUNT_POSTCHECK_FAILED");
        return 1;
    }

    puts("ASOFT_UMOUNT_CLEAN");
    return 0;
}
