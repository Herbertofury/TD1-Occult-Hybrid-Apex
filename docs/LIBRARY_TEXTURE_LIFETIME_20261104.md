# Library thumbnail view ownership

The library can render an already displayed item again. Previously, replacing
its shader-resource view overwrote the old raw pointer without releasing it.
At the 60-image capacity, the same replacement was refused along with new keys.

The render-thread installer now releases the prior view after a successful
replacement, permits replacing an existing key at capacity, and retains the
old image when creation or installation fails. New keys still respect the
existing 60-image limit. Temporary D3D objects use `ComPtr`; a failed new-key
map insertion rolls back instead of retaining a partial pair of entries.

The standalone `LibraryTextureLifetimeTests.cpp` exercises repeated
replacement, exact release counts, capacity and injected allocation failure
using the real helper, WRL `ComPtr` and `ImVec2`. The standalone
`LibraryTextureWarpTests.cpp` uses a software D3D11 WARP device to test a
replacement at capacity and read back its exact RGBA pixels. Both passed in
an MSVC x64 Debug-style build with assertions enabled. They are standalone
tests and are not yet registered in CTest.

From an x64 Visual Studio developer prompt at the repository root, set
`APEX_TEST_OUT` to an existing writable directory, then compile and run the
standalone tests:

```bat
cl /nologo /std:c++17 /EHsc /W4 /WX /UNDEBUG /INativeOverlay\Source /INativeOverlay\third_party\imgui /Fo"%APEX_TEST_OUT%\lifetime.obj" /Fe"%APEX_TEST_OUT%\lifetime.exe" NativeOverlay\Tests\LibraryTextureLifetimeTests.cpp
"%APEX_TEST_OUT%\lifetime.exe"
cl /nologo /std:c++17 /EHsc /W4 /WX /UNDEBUG /INativeOverlay\Source /INativeOverlay\third_party\imgui /Fo"%APEX_TEST_OUT%\warp.obj" /Fe"%APEX_TEST_OUT%\warp.exe" NativeOverlay\Tests\LibraryTextureWarpTests.cpp /link d3d11.lib
"%APEX_TEST_OUT%\warp.exe"
```

An isolated full Debug overlay built with the previously verified Rust
archive, and the existing 148 native resource checks passed. Existing compiler
warnings remain. The normal source ordering synchronizes library images before
their draw references, but the actual mod's full frame lifetime, device reset,
repeated use and in-game performance remain unverified. No improvement in
hitching or FPS is claimed, and no game, save, package or installation was
changed. This does not address resource freshness, retained broker generations
or Studio's individual-resource selection.
