#pragma once
#include <cstdint>
#include <string_view>

namespace td1 {
// Renderer selection follows the actual process-owned Sims Canvas. Desktop
// foreground ownership is only relevant to physical hotkeys, never attachment.
inline bool GameCanvas(std::uint32_t owner, std::uint32_t process,
        bool visible, bool minimized, bool topLevel, int width, int height,
        std::wstring_view windowClass) {
    return owner != 0 && owner == process && visible && !minimized && topLevel &&
        width > 0 && height > 0 && windowClass.size() > 7 &&
        windowClass.substr(0,7) == L"Canvas-";
}
inline bool UniqueGameCanvas(bool candidate, unsigned matchingWindows) {
    return candidate && matchingWindows == 1;
}
inline bool CaptureReady(bool hooked, int nativeStatus, bool overlay, bool visible) {
    return hooked && nativeStatus >= 2 && nativeStatus <= 3 &&
        (!overlay || (nativeStatus == 3 && visible));
}
}
