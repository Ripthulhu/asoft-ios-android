/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include "cpu_exec_control.h"

int main(int argc, char **argv)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc == 2 && !strcmp(argv[1], "--cpu-exec-anon")) return ec_run(0);
    if (argc == 2 && !strcmp(argv[1], "--cpu-exec-memfd")) return ec_run(1);
    fprintf(stderr, "Usage: %s --cpu-exec-anon | --cpu-exec-memfd\n", argv[0]);
    return 2;
}
