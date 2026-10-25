# Isolated renderer snapshot pointer-page recycling experiment

This is **not installed in the game**. It contains a bounded C++ ownership core,
an allocator fixture, and an authenticated native ABI receipt. It does not hook
the game, change a production builder, skip a capture, or claim a measured gain.

The V336 UI-thread CPU samples lead through Movie Advance, Movie Capture,
Context Capture, snapshot retirement, and the native allocator. The hot
`0x1002CF0` address-to-allocation-owner lookup is reached by the native free at
`0x10064B4`; the aligned allocation at `0x1006B87` reaches the other sampled
allocator range. These are renderer pointer pages. They are not Sim appearance
records. CPU sample weights do not establish how many allocations occur.

The allocator calls concern a `0x268` byte page: a `0x28` byte header and 72
pointer slots (`0x240` bytes). Context Capture copies the pointer slots into a
new page and initializes every header byte. Finalized snapshots release native
node data and finalize dead entries before the snapshot destructor unlinks page
neighbors and frees the old page. The separate entry pages use 4KB alignment
and 56-byte entry slots. The experiment never reads or changes a retained
page's contents; the unchanged native initializer must overwrite all 616 bytes.

## Ownership policy

`SnapshotPointerPagePool.h` starts disabled. An adapter may enable it only after
all native authentication and lifetime gates pass. Each registered context has
a fresh nonzero nonce, native heap identity and Advance thread. An authenticated
Capture receives a unique scope. Nested captures on that thread do not acquire
a second pooling scope.

`try_take` can substitute a retained page only at the exact native Capture
allocation site, with the original 616-byte size, 16-byte alignment, null
allocation-info argument, same context, heap, thread, live nonce and active
scope. `nullptr` means the original allocator must execute with its original
arguments. An allocation from another call site, including initial entry-page
creation, always executes normally.

`try_retain` can consume only the exact final pointer-page free after native
finalization and neighbor unlink have completed. Every other free runs normally.
The actual adapter must derive the owner from the still-live Snapshot at
offset `+0x10`, and independently verify the native root heap and absence of a
ReleaseOnFree marker. A foreign or duplicate free revokes any cached claim first
and suspends that context, preventing a later use of a freed retained pointer.

Bounds are compile-time fixed arrays plus lower runtime page limits. The
prototype's ordinary limits are 64 pages per context and 256 in total. These
are experimental limits, not measured production choices. `retained_bytes`
counts requested 616-byte pages; native heap rounding, metadata and segment
footprint remain accounted by the native heap. There is no separate page
allocator, virtual memory allocation, worker, hidden service or game-object
access in the core.

Before the real Context destructor, `begin_close` marks the lifetime closing,
revokes its active scope, detaches its retained pages, unlocks, and invokes the
**original native free** for each. The closing tombstone remains until
`finish_close`, which is called only after the original destructor returns. A
later context at the same address receives a new nonce. Stale keys cannot take
or drain the new context's pages.

Global heap teardown is a second mandatory seam. Terminal disable and drain
must finish before native `0x1003930` begins its leak check and heap release.
The core waits for any concurrent drain already invoking original frees. Native
callbacks always run outside the pool mutex, and a thread-local guard prevents
their reentry from enabling or consuming the pool. No capture, renderer ACK,
shutdown callback or snapshot generation is replaced or suppressed.

The core currently uses a no-throw native-free fixture callback. **Actual native
Free exception/unwind compatibility remains unqualified**; that callback type
must not be used in a game adapter without completing that gate. Allocation
decisions do not invoke the allocator, so native null returns and exceptions
remain the adapter's original path. No C++ destructor guesses whether the game
heap is still alive: explicit verified drains are required.

## Exact adapter contract still to implement

`native_pin_manifest.json` records the authenticated runtime text hash, executable
hash, complete relevant function spans and exact short call-site bytes. It is
generated read-only by `build_native_pin_manifest.py` from the existing private
runtime text dump. It cannot arm hooks and cannot bless a different game build.

The narrow hot sites are the original virtual calls, rather than a global heap
detour affecting every game allocation:

- Allocation span `0x1006B80..0x1006B8A`: original heap in RCX, size in RDX,
  alignment in R8, allocation-info in R9, result in RAX. Context belongs to the
  authenticated active Capture scope. Its native header/copy instructions stay.
- Free span `0x10064B1..0x10064B7`: original native heap in RCX and page in RDX;
  the containing snapshot is the original nonvolatile RDI, with owner at `+0x10`.
  The native neighbor unlink and earlier node-data finalization stay.
- Context Capture `0x1006A20` supplies a bounded same-thread scope only for the
  reviewed Movie Capture callers. Context destructor `0x1005EE0` closes/drains
  before the original shutdown. Global heap teardown `0x1003930` terminally
  drains before its original leak check/release.

No thunk or function detour is provided. Future code must qualify instruction
relocation, stack alignment, shadow space, every preserved register, return AL
from Context Capture, exceptions, partial installation rollback, conflicting
patches, concurrent teardown, module unload and native heap lifetime. The
original shutdown waits for the render thread to release its snapshot and cache;
that ACK/finalization behavior must remain intact.

Before considering a native adapter, collect opt-in per-Capture counters for
actual page allocation/free calls and duration. Count at those narrow calls,
not by walking the entire render tree or interpreting ETW samples as calls.
Qualify matched category clicks and settled idle periods separately, and measure
real frame spikes with the unchanged guard and complete appearance checks.

## Standalone tests

```powershell
cmake -S Experiments/GfxSnapshotPool -B .work/gfx-snapshot-pool-build -G "Visual Studio 17 2022" -A x64
cmake --build .work/gfx-snapshot-pool-build --config Release -j 2
ctest --test-dir .work/gfx-snapshot-pool-build -C Release --output-on-failure
python -B Experiments/GfxSnapshotPool/build_native_pin_manifest.py
```

Nine MSVC `/W4 /WX` contract scenarios pass: native outstanding allocation
accounting and untouched page bytes; every evidence gate; context/page/global
limits; nonce, scope and address reuse; callback reentry; nested/cross-thread
rejection; duplicate ownership revocation; concurrent global drain waiting for
native frees; and 16 independently owned concurrent contexts. The fixture
allocator is a test double, not the game's allocator or a game performance test.

Scaleform's primary documentation describes the underlying ownership model:
[Context](https://help.autodesk.com/cloudhelp/ENU/Scaleform-Help/cpp_ref/03124.html),
[Shutdown](https://help.autodesk.com/cloudhelp/ENU/Scaleform-Help/cpp_ref/03146.html),
[MemoryHeap](https://help.autodesk.com/cloudhelp/ENU/Scaleform-Help/cpp_ref/02315.html).
The actual native caller does not perform the documented inefficient pattern of
calling Capture twice after Advance: its four internal Capture sites are on
mutually exclusive branches. Existing native HasChanges and viewport equality
guards also remain untouched.
