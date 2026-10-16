#include <cstdio>
extern "C" int ApexRunNativeSmoke();
int main() {
    const int result = ApexRunNativeSmoke();
    if (result) std::fprintf(stderr, "DX11 smoke failed at stage %d\n", result);
    return result;
}
