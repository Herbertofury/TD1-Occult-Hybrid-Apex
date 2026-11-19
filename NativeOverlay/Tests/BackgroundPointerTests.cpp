#include "ApexBackgroundPointer.h"
#include "ApexBackgroundKeyboard.h"
#include <vector>
#include <stdexcept>
#include <iostream>

using td1::BackgroundPointerEvent;
struct Driver {
    bool viewport = true, owner = true;
    int failPost = -1, resizeAt = -1, replaceAt = -1, held = 0;
    std::vector<int> messages, waits, states;
    int run() {
        return td1::RunBackgroundPointer([&] { return viewport && owner; }, [&] { return owner; },
            [&](BackgroundPointerEvent event) {
                int value = static_cast<int>(event); messages.push_back(value);
                if (value == failPost) return false;
                if (value == 1) held = 1;
                if (value == 2) held = 0;
                return true;
            }, [&](int ms) {
                waits.push_back(ms);
                if (static_cast<int>(waits.size()) == resizeAt) viewport = false;
                if (static_cast<int>(waits.size()) == replaceAt) owner = false;
            }, [&](int state) { states.push_back(state); });
    }
};
void require(bool value) { if (!value) throw std::runtime_error("background pointer contract failed"); }
int main() {
    Driver good; require(good.run() == 4); require(good.messages == std::vector<int>({0,1,2}));
    require(good.waits == std::vector<int>({120,100})); require(good.states == std::vector<int>({3})); require(!good.held);
    Driver invalid; invalid.viewport = false; require(invalid.run() == -8); require(invalid.messages.empty());
    Driver resized; resized.resizeAt = 1; require(resized.run() == -8); require(resized.messages == std::vector<int>({0}));
    Driver resizedHeld; resizedHeld.resizeAt = 2; require(resizedHeld.run() == -8);
    require(resizedHeld.messages == std::vector<int>({0,1,2})); require(!resizedHeld.held);
    Driver replaced; replaced.replaceAt = 2; require(replaced.run() == -5); require(replaced.messages == std::vector<int>({0,1}));
    for (int event = 0; event < 3; ++event) {
        Driver failed; failed.failPost = event; require(failed.run() == -5);
        require(failed.messages.size() == static_cast<size_t>(event + 1));
    }
    std::vector<int> keys;bool viewport=true;
    const auto post=[&](int key,bool down){keys.push_back(down?key:-key);return true;};
    require(td1::RunBackgroundKey(39,[]{return true;},[]{return true;},post,[](int){})==4);
    require(keys==std::vector<int>({39,-39}));keys.clear();
    require(td1::RunBackgroundKey(40,[&]{return viewport;},[]{return true;},post,[&](int){viewport=false;})==-8);
    require(keys==std::vector<int>({40,-40}));keys.clear();
    require(td1::RunBackgroundKey(38,[]{return false;},[]{return false;},post,[](int){})==-8);
    require(keys.empty());
    require(td1::RunBackgroundKey(65,[]{return true;},[]{return true;},post,[](int){})==-4);
    require(keys.empty());
    std::cout << "Background pointer delivery, frame settling, refusal and release checks passed\n";
}
