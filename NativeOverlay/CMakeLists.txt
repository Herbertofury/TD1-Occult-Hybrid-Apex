cmake_minimum_required(VERSION 3.20)
project(TD1ApexD3D11Overlay LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "Apex requires the x64 game and x64 native build")
endif()
add_library(ApexMinHook STATIC
    third_party/minhook/src/buffer.c
    third_party/minhook/src/hook.c
    third_party/minhook/src/trampoline.c
    third_party/minhook/src/hde/hde64.c)
target_include_directories(ApexMinHook PUBLIC third_party/minhook/include)
set(APEX_OVERLAY_SOURCES
    Source/TD1ApexD3D11Proxy.cpp
    third_party/imgui/imgui.cpp
    third_party/imgui/imgui_draw.cpp
    third_party/imgui/imgui_tables.cpp
    third_party/imgui/imgui_widgets.cpp
    third_party/imgui/backends/imgui_impl_win32.cpp
    third_party/imgui/backends/imgui_impl_dx11.cpp
)
function(apex_overlay_target name)
    target_include_directories(${name} PRIVATE Source third_party/imgui third_party/imgui/backends third_party)
    target_compile_definitions(${name} PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
    target_compile_options(${name} PRIVATE /W4 /permissive- /EHsc /O2 /utf-8)
    target_link_libraries(${name} PRIVATE ApexMinHook d3d11 d3dcompiler dxgi user32 ws2_32 windowscodecs ole32 bcrypt)
endfunction()
# The mod-folder sidecar is the default distribution. Keep the older proxy
# build available for independently verified import surfaces, never required.
add_library(ApexOverlay SHARED ${APEX_OVERLAY_SOURCES})
target_compile_definitions(ApexOverlay PRIVATE APEX_SIDECAR)
apex_overlay_target(ApexOverlay)
add_library(TD1ApexD3D11Proxy SHARED ${APEX_OVERLAY_SOURCES})
apex_overlay_target(TD1ApexD3D11Proxy)
set_target_properties(TD1ApexD3D11Proxy PROPERTIES OUTPUT_NAME "d3d11")

include(CTest)
add_executable(ApexPermissionCapture Source/ApexPermissionCapture.cpp)
target_compile_features(ApexPermissionCapture PRIVATE cxx_std_20)
# Keep executable lookup away from the optional d3d11 proxy in Release.
set_target_properties(ApexPermissionCapture PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/permission-capture/$<CONFIG>")
target_compile_definitions(ApexPermissionCapture PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
target_compile_options(ApexPermissionCapture PRIVATE /W4 /permissive- /EHsc /utf-8)
target_link_libraries(ApexPermissionCapture PRIVATE windowsapp d3d11 dxgi dwmapi user32)
if(BUILD_TESTING)
    add_executable(ApexCasOwnerGraphTests Tests/CasOwnerGraphTests.cpp)
    target_include_directories(ApexCasOwnerGraphTests PRIVATE Source third_party)
    target_compile_options(ApexCasOwnerGraphTests PRIVATE /W4 /permissive- /EHsc /utf-8)
    add_test(NAME native-separate-cas-owners COMMAND ApexCasOwnerGraphTests)
    add_executable(ApexNativeCasEngineTests Tests/NativeCasEngineTests.cpp)
    apex_overlay_target(ApexNativeCasEngineTests)
    add_test(NAME native-cas-owner-engine COMMAND ApexNativeCasEngineTests)
    add_executable(ApexNativeCasProbeTests Tests/NativeCasProbeTests.cpp)
    target_include_directories(ApexNativeCasProbeTests PRIVATE Source)
    target_link_libraries(ApexNativeCasProbeTests PRIVATE ApexMinHook)
    target_compile_options(ApexNativeCasProbeTests PRIVATE /W4 /permissive- /EHsc /utf-8)
    add_test(NAME native-cas-code-probe COMMAND ApexNativeCasProbeTests)
    add_test(NAME native-ea-capture-empty-owner COMMAND ApexPermissionCapture 0 0 200 150 unused-invalid-ea.bmp)
    set_tests_properties(native-ea-capture-empty-owner PROPERTIES WILL_FAIL TRUE TIMEOUT 10)
    add_executable(ApexSimPreviewTests Tests/SimPreviewTests.cpp)
    target_include_directories(ApexSimPreviewTests PRIVATE Source third_party)
    target_compile_definitions(ApexSimPreviewTests PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
    target_compile_options(ApexSimPreviewTests PRIVATE /W4 /permissive- /EHsc /utf-8)
    target_link_libraries(ApexSimPreviewTests PRIVATE d3d11 d3dcompiler windowscodecs ole32 bcrypt)
    add_test(NAME native-sim-preview COMMAND ApexSimPreviewTests)
    add_executable(ApexUiDataTests Tests/UiDataTests.cpp)
    target_include_directories(ApexUiDataTests PRIVATE Source third_party)
    target_compile_options(ApexUiDataTests PRIVATE /W4 /permissive- /EHsc /utf-8)
    add_test(NAME native-ui-data COMMAND ApexUiDataTests)
    add_executable(ApexCasBankTests Tests/CasBankTests.cpp)
    target_include_directories(ApexCasBankTests PRIVATE Source third_party)
    target_compile_options(ApexCasBankTests PRIVATE /W4 /permissive- /EHsc /utf-8)
    add_test(NAME native-cas-bank COMMAND ApexCasBankTests)
    add_executable(ApexResourceTests Tests/ResourceTests.cpp)
    target_include_directories(ApexResourceTests PRIVATE Source third_party)
    target_compile_definitions(ApexResourceTests PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
    target_compile_options(ApexResourceTests PRIVATE /W4 /permissive- /EHsc /utf-8)
    target_link_libraries(ApexResourceTests PRIVATE windowscodecs ole32 bcrypt)
    add_test(NAME native-resource-data COMMAND ApexResourceTests)
    add_executable(ApexNativeSmoke ${APEX_OVERLAY_SOURCES} Tests/NativeSmoke.cpp)
    target_compile_definitions(ApexNativeSmoke PRIVATE APEX_SIDECAR APEX_NATIVE_SMOKE)
    apex_overlay_target(ApexNativeSmoke)
    add_test(NAME native-dx11-smoke COMMAND ApexNativeSmoke)
    set_tests_properties(native-dx11-smoke PROPERTIES TIMEOUT 30)
endif()
