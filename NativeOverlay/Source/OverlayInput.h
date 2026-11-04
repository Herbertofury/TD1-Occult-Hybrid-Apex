#pragma once
namespace td1 {
// Use the high key-state bit and our own edge; Windows' low bit can be
// consumed by another application. Observe releases even outside our window.
class ToggleInput {
    bool down_ = false;
public:
    bool sample(bool foreground, bool down) noexcept {
        const bool toggle = foreground && down && !down_;
        down_ = down;
        return toggle;
    }
};
}
