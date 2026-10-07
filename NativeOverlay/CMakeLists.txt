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
    target_link_libraries(${name} PRIVATE ApexMinHook d3d11 dxgi user32 ws2_32)
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
if(BUILD_TESTING)
    add_executable(ApexUiDataTests Tests/UiDataTests.cpp)
    target_include_directories(ApexUiDataTests PRIVATE Source third_party)
    target_compile_options(ApexUiDataTests PRIVATE /W4 /permissive- /EHsc /utf-8)
    add_test(NAME native-ui-data COMMAND ApexUiDataTests)
    add_executable(ApexNativeSmoke ${APEX_OVERLAY_SOURCES} Tests/NativeSmoke.cpp)
    target_compile_definitions(ApexNativeSmoke PRIVATE APEX_SIDECAR APEX_NATIVE_SMOKE)
    apex_overlay_target(ApexNativeSmoke)
    add_test(NAME native-dx11-smoke COMMAND ApexNativeSmoke)
    set_tests_properties(native-dx11-smoke PROPERTIES TIMEOUT 30)
endif()
