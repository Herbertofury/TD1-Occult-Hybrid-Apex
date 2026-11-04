cmake_minimum_required(VERSION 3.20)
project(ApexGfxSnapshotProfileQualification LANGUAGES C CXX)
enable_testing()
set(ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../..")
add_library(GfxProfileMinHook STATIC
  "${ROOT}/NativeOverlay/third_party/minhook/src/buffer.c"
  "${ROOT}/NativeOverlay/third_party/minhook/src/hook.c"
  "${ROOT}/NativeOverlay/third_party/minhook/src/trampoline.c"
  "${ROOT}/NativeOverlay/third_party/minhook/src/hde/hde64.c")
target_include_directories(GfxProfileMinHook PUBLIC "${ROOT}/NativeOverlay/third_party/minhook/include")
add_executable(GfxSnapshotProfileTests "${ROOT}/NativeOverlay/Tests/GfxSnapshotProfileTests.cpp")
target_include_directories(GfxSnapshotProfileTests PRIVATE "${ROOT}/NativeOverlay/Source" "${ROOT}/NativeOverlay/third_party")
target_compile_features(GfxSnapshotProfileTests PRIVATE cxx_std_17)
target_compile_definitions(GfxSnapshotProfileTests PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
target_compile_options(GfxSnapshotProfileTests PRIVATE /W4 /WX /permissive- /EHsc)
target_link_libraries(GfxSnapshotProfileTests PRIVATE GfxProfileMinHook bcrypt ntdll)
add_test(NAME GfxSnapshotProfileTests COMMAND GfxSnapshotProfileTests)
