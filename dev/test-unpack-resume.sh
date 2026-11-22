#!/usr/bin/env bash
# Host-only synthetic AEA resume regression. Needs a JDK, C compiler and Android SDK android.jar.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
android_jar=${1:?usage: test-unpack-resume.sh /path/to/android.jar}
test_dir=$(mktemp -d)
trap 'rm -rf "$test_dir"' EXIT
jdk=$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")
jni_include=$jdk/include
# A stripped JDK may still have the compiler module but no headers. The NDK's standalone jni.h is VM-neutral.
if [ -n "${ASOFT_JNI_HEADER:-}" ]; then
    cp "$ASOFT_JNI_HEADER" "$test_dir/jni.h"
    jni_include=$test_dir
fi
src=$here/app/src/main
cc -shared -fPIC -O2 -I"$jni_include" -I"$jdk/include/linux" \
    "$src/cpp/unpack.c" "$src/cpp/lzfse/lzfse_decode.c" "$src/cpp/lzfse/lzfse_decode_base.c" \
    "$src/cpp/lzfse/lzfse_fse.c" "$src/cpp/lzfse/lzvn_decode_base.c" -o "$test_dir/libunpack.so"
java com.sun.tools.javac.Main -cp "$android_jar" -d "$test_dir" "$src/java/com/asoft/ios/Unpack.java" \
    "$src/java/com/asoft/ios/Io.java" "$here/dev/tools/unpack/UnpackResumeTest.java"
java -Djava.library.path="$test_dir" -cp "$test_dir:$android_jar" com.asoft.ios.UnpackResumeTest "$test_dir"
