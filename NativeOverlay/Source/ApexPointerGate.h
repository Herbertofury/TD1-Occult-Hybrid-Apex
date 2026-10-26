#pragma once
#include <cstdint>
namespace td1 {
// First-click ownership uses the last rendered window bounds. ImGui's
// WantCaptureMouse describes the preceding frame and can lag a posted burst.
struct PointerGate {
    int left=0, top=0, right=0, bottom=0;
    uint32_t held=0;
    bool Owns(int x, int y, uint32_t down, uint32_t up, bool wanted) {
        const bool inside = x >= left && x < right && y >= top && y < bottom;
        const bool owns = wanted || inside || held != 0;
        if (down && owns) held |= down;
        if (up) held &= ~up;
        return owns;
    }
};
}
