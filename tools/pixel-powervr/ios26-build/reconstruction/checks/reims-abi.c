#include "reims_vgpu.h"
_Static_assert(sizeof(RvgDeviceConfig) == 64, "device config ABI");
_Static_assert(sizeof(RvgHostCallbacks) == 88, "host callback ABI");
_Static_assert(sizeof(RvgMemoryRangeFile) == 16, "memory file ABI");
int main(void) { return 0; }
