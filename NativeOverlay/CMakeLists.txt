cmake_minimum_required(VERSION 3.20)
project(TD1ApexD3D11Overlay LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_library(TD1ApexD3D11Proxy SHARED
    Source/TD1ApexD3D11Proxy.cpp
    third_party/imgui/imgui.cpp
    third_party/imgui/imgui_draw.cpp
    third_party/imgui/imgui_tables.cpp
    third_party/imgui/imgui_widgets.cpp
    third_party/imgui/backends/imgui_impl_win32.cpp
    third_party/imgui/backends/imgui_impl_dx11.cpp
)
target_include_directories(TD1ApexD3D11Proxy PRIVATE
    third_party/imgui
    third_party/imgui/backends
    third_party
)
target_compile_definitions(TD1ApexD3D11Proxy PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
target_compile_options(TD1ApexD3D11Proxy PRIVATE /W4 /permissive- /EHsc /O2)
target_link_libraries(TD1ApexD3D11Proxy PRIVATE d3d11 dxgi user32 ws2_32)
set_target_properties(TD1ApexD3D11Proxy PROPERTIES OUTPUT_NAME "d3d11")

include(CTest)
if(BUILD_TESTING)
    add_executable(ApexUiDataTests Tests/UiDataTests.cpp)
    target_include_directories(ApexUiDataTests PRIVATE Source third_party)
    target_compile_options(ApexUiDataTests PRIVATE /W4 /permissive- /EHsc /utf-8)
    add_test(NAME native-ui-data COMMAND ApexUiDataTests)
endif()
