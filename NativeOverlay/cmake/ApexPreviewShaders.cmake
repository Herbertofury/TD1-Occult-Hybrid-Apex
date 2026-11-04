# DX11 consumes DXBC, so use the SDK compiler at build time. Do not introduce
# a runtime compiler, a downloaded driver cache, or a GPU-specific disk cache.
get_filename_component(APEX_WINDOWS_KITS
    "[HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows Kits\\Installed Roots;KitsRoot10]" ABSOLUTE)
file(GLOB APEX_FXC_CANDIDATES "${APEX_WINDOWS_KITS}/bin/*/x64/fxc.exe")
list(SORT APEX_FXC_CANDIDATES COMPARE NATURAL ORDER DESCENDING)
find_program(APEX_FXC NAMES fxc.exe)
if(NOT APEX_FXC AND APEX_FXC_CANDIDATES)
    list(GET APEX_FXC_CANDIDATES 0 APEX_FXC)
endif()
if(NOT APEX_FXC)
    message(FATAL_ERROR "Windows SDK fxc is required to precompile Apex preview shaders")
endif()
set(APEX_PREVIEW_GENERATED "${CMAKE_CURRENT_BINARY_DIR}/generated-preview")
file(MAKE_DIRECTORY "${APEX_PREVIEW_GENERATED}")
foreach(STAGE IN ITEMS VS PS)
    string(TOLOWER "${STAGE}" PROFILE)
    add_custom_command(OUTPUT "${APEX_PREVIEW_GENERATED}/ApexPreview${STAGE}.h"
        COMMAND "${APEX_FXC}" /nologo /Ges /O3 /T "${PROFILE}_4_0" /E "${STAGE}"
            /Fh "${APEX_PREVIEW_GENERATED}/ApexPreview${STAGE}.h" /Vn "apex_preview_${PROFILE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/Shaders/SimPreview.hlsl"
        DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/Shaders/SimPreview.hlsl"
        COMMENT "Precompile Apex preview ${STAGE}; no in-game HLSL compilation" VERBATIM)
endforeach()
add_custom_target(ApexPreviewShaders DEPENDS
    "${APEX_PREVIEW_GENERATED}/ApexPreviewVS.h" "${APEX_PREVIEW_GENERATED}/ApexPreviewPS.h")
