#pragma once

namespace td1 {
enum class BackgroundPointerEvent { Move, Down, Up };

// A CAS grid updates its hovered cell on a later UI frame. Same-batch move,
// down and up can acknowledge delivery while leaving the selection unchanged.
// This sequence never requests foreground ownership or moves the OS cursor.
template<class Valid, class Owned, class Post, class Pause, class State>
int RunBackgroundPointer(Valid valid, Owned owned, Post post, Pause pause, State state) {
    if (!valid()) return -8;
    if (!post(BackgroundPointerEvent::Move)) return -5;
    pause(120);
    if (!valid()) return -8;
    if (!post(BackgroundPointerEvent::Down)) return -5;
    state(3);
    pause(100);
    // A resize after Down must not leave a held game button. Release to the
    // same process-owned window even if its old viewport is no longer valid.
    if (!owned() || !post(BackgroundPointerEvent::Up)) return -5;
    return valid() ? 4 : -8;
}
}
