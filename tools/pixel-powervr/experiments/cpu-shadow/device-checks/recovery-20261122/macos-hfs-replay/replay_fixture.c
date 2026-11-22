/* Exercise Apple's replay-only ABI on the generated 96 MiB fixture. */
#include <TargetConditionals.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/sysctl.h>
#include <unistd.h>

#if TARGET_OS_IPHONE
/* The iPhoneOS SDK omits sys/disk.h. These are XNU's read-only geometry ioctls. */
#define DKIOCGETBLOCKSIZE _IOR('d', 24, uint32_t)
#define DKIOCGETBLOCKCOUNT _IOR('d', 25, uint64_t)
#else
#include <sys/disk.h>
#endif

enum {
    replay_selector = 0x6a6e6c72, /* HFS_REPLAY_JOURNAL in hfs_mount.h */
    volume_header_offset = 1024,
    fixture_bytes = 96 * 1024 * 1024,
};

static int fixture_descriptor(const char *path)
{
    const char prefix[] = "/dev/rdisk";
    if (strncmp(path, prefix, sizeof(prefix) - 1) != 0) {
        return -1;
    }
    const char *digits = path + sizeof(prefix) - 1;
    if (*digits == '\0' || digits[strspn(digits, "0123456789")] != '\0') {
        return -1;
    }
    return open(path, O_RDWR | O_NOFOLLOW | O_CLOEXEC);
}

static int is_disposable_fixture(int fd)
{
    struct stat info;
    uint32_t sector = 0;
    uint64_t sectors = 0;
    if (fstat(fd, &info) != 0 || !S_ISCHR(info.st_mode) ||
        ioctl(fd, DKIOCGETBLOCKSIZE, &sector) != 0 ||
        ioctl(fd, DKIOCGETBLOCKCOUNT, &sectors) != 0 ||
        (sector != 512 && sector != 4096) || sectors != fixture_bytes / sector) {
        return 0;
    }

    /* Raw character-device I/O must use device-aligned reads. */
    unsigned char first_blocks[4096];
    if (pread(fd, first_blocks, sizeof(first_blocks), 0) != sizeof(first_blocks)) {
        return 0;
    }
    const unsigned char *header = first_blocks + volume_header_offset;
    return memcmp(header, "HX\0\5", 4) == 0 && memcmp(header + 8, "HFSJ", 4) == 0;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        return 2;
    }
    int fd = fixture_descriptor(argv[1]);
    if (fd < 0) {
        fprintf(stderr, "replay helper could not open the disposable raw disk\n");
        return 2;
    }
    if (!is_disposable_fixture(fd)) {
        fprintf(stderr, "replay helper refused unexpected disk geometry or signature\n");
        close(fd);
        return 2;
    }

    struct vfsconf hfs;
    if (getvfsbyname("hfs", &hfs) == -1) {
        perror("getvfsbyname hfs");
        close(fd);
        return 1;
    }

    int mib[] = {CTL_VFS, hfs.vfc_typenum, replay_selector, fd};
    int result = sysctl(mib, sizeof(mib) / sizeof(mib[0]), NULL, NULL, NULL, 0);
    if (result == -1) {
        perror("HFS_REPLAY_JOURNAL");
        close(fd);
        return 1;
    }
    if (close(fd) != 0) {
        perror("close disposable disk");
        return 1;
    }
    puts("HFS_REPLAY_JOURNAL returned success");
    return 0;
}
