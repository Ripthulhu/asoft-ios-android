# Local build prerequisites; does not choose a target cache or test command.
export PATH=/home/agent/.cargo/bin:/workspace/scratch/abcabc3f01ae/host-tooling/bin:/workspace/scratch/abcabc3f01ae/host-tooling/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64/bin:/workspace/scratch/abcabc3f01ae/host-tooling/cmake-pinned/cmake/data/bin:/workspace/scratch/abcabc3f01ae/host-tooling/ninja-pinned/ninja/data/bin:/workspace/scratch/abcabc3f01ae/host-tooling/sysroot/usr/bin:/usr/local/bin:/usr/bin:/bin
export CMAKE_PREFIX_PATH=/workspace/scratch/abcabc3f01ae/host-tooling/sysroot/usr
export PKG_CONFIG_PATH=/workspace/scratch/abcabc3f01ae/host-tooling/sysroot/usr/lib/x86_64-linux-gnu/pkgconfig:/workspace/scratch/abcabc3f01ae/host-tooling/sysroot/usr/share/pkgconfig
export LD_LIBRARY_PATH=/workspace/scratch/abcabc3f01ae/host-tooling/sysroot/usr/lib/x86_64-linux-gnu
export RVG_CPU_SHADOW_LLVM_AS=/workspace/scratch/abcabc3f01ae/host-tooling/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-as
export RUSTUP_TOOLCHAIN=1.98.1
export VK_ICD_FILENAMES=/workspace/scratch/abcabc3f01ae/host-tooling/lvp-local.json
export VK_LAYER_PATH=/workspace/scratch/abcabc3f01ae/host-tooling/sysroot/usr/share/vulkan/explicit_layer.d
export VK_INSTANCE_LAYERS=VK_LAYER_KHRONOS_validation
export VK_LAYER_ENABLES=VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT
export VK_LOADER_DEBUG=error,warn,layer
export MESA_SHADER_CACHE_DISABLE=true
export XDG_RUNTIME_DIR=/workspace/scratch/abcabc3f01ae/host-tooling/xdg-run
