# Exact native snapshot-page measurement

This adds a default-disabled diagnostic, not an allocator optimization. No page
is retained, replaced, cached, copied by Apex, or freed by Apex. Every original
native allocation, free, Capture and snapshot destructor executes with its
original arguments, return and exception behavior.

The source is in `NativeOverlay/Source/ApexGfxSnapshotProfile.h` and
`ApexGfxSnapshotProfileWin.h`; the standalone test target is
`NativeOverlay/Tests/GfxSnapshotProfileTests.cpp`. Production dispatch/build
integration belongs to the parent task. Nothing here launches or edits a game
or profile. Actual-game qualification and performance measurements are separate
from the standalone evidence below.

## Public diagnostic API

```cpp
td1::nativecas::gfxprofile::win::Configure(scope_id, milliseconds, detail_timing);
td1::nativecas::gfxprofile::win::Snapshot(); // ui::Json
td1::nativecas::gfxprofile::win::Stop();
```

The existing game-owner dispatcher must validate its selected/bound context and
accept only the four fields `method`, `scope_id`, `milliseconds`, and
`detail_timing` for method `profile-gfx-snapshot-pages`. Duration is 0–30000 ms;
zero stops. `detail_timing` is a Boolean. The header does not expose arbitrary
addresses or callback injection through this API.

Default startup installs no allocator hook, clock callback, worker or timer.
An explicit bounded window fingerprints the real executable, complete native
functions, original unwind entries/codes, native heap vtable and exact caller
instructions before creating or enabling its own hooks.

Four function-entry detours provide authentic synchronous attribution:

- Context Capture `0x1006A20(Context*) -> AL` for the reviewed Movie Capture
  return sites `0xFF7E88` and `0xFF7929`.
- Snapshot destructor `0x10063D0(Snapshot*, unsigned flags) -> RAX` copies its
  still-live owner at `Snapshot+0x10` only while a Capture is being measured.
- Aligned native allocation `0x10026E0(Heap*, size, alignment, info) -> RAX`
  counts only the direct return address `0x1006B8A`.
- Native free `0x1002DA0(Heap*, page) -> void` counts only the direct return
  address `0x10064B7`.

An unrelated heap call immediately forwards. It does not inspect arguments,
read a clock, update a metric, or dereference a game object. During explicit
measurement, it still incurs the temporary detour/filter overhead; this is not
described as free overhead. Matched calls outside an authenticated root-heap
Capture are counted, but are not reported as qualified owner-specific calls.

Owner-specific counters require the current synchronous Capture, matching
Context/Snapshot owner, matching heap and the pinned global root heap/vtable.
Context heap fields `+0x0` and `+0x18` must agree with global `0x29640D0`;
the heap vtable must be image `+0x201EDE0`. The native frame id at Context
`+0xE8` is copied on entry. No game object is dereferenced after its original
native call returns. JSON contains copied primitives and a window-scoped address
fingerprint, not a persistent Sim/form/lifetime identity or a reusable handle.

## Timing and lifecycle

Count-only mode has no per-page QPC reads. Its page timing fields are `null` and
`timed:false`; they are not zero-cost claims. Capture/destructor timing remains
available. Detail mode measures each matched allocation/free with QPC. Those
values include observer/call overhead and scheduler time, and are not exclusive
CPU time. Use matched ETW sampling/CPU data and an uninstrumented frame baseline
to determine responsibility for a hitch.

An atomic generation/inflight gate prevents resetting counters while accepted
native calls remain in flight. Native hooks allocate no profiling memory, use no
mutex, and never wait for a metrics reader. The Capture record ring contains at
most 64 copied records; sort by `scope_serial` because the returned ring uses
physical storage order. A contended record write is reported as dropped rather
than blocking the game.

Native wrappers preserve `GetLastError` around observations. Compiler-generated
`__try/__finally` blocks restore thread-local scopes and complete observations
for normal return, C++ exceptions and SEH. They do not catch or replace a native
exception, convert a failure into success, or change the native AL/RAX result.

Only the explicit window starts a one-off timeout thread. It waits without
polling, disables measurement, restores owned native entries and exits. Stop
also restores owned entries. A conflicting third-party entry is reported and
is never overwritten by cleanup. Activation uses individual owned enable calls,
so a failure cannot leave queued enable operations for another component's
future `MH_ApplyQueued`.

Disabled trampolines and their registered unwind data remain together until
process exit. Removing a trampoline immediately after disabling can race with
a callback already dispatched before an inflight counter; this diagnostic never
does that. It pins its own DLL lifetime at first preparation. There is no active
heap hook after successful timeout/stop, and no persistent timeout service.

## Trampoline unwind proof

MinHook uses 64-byte owned slots. The exact four relocated layouts occupy at
most 47 bytes including their separate entry relay, leaving `+56..+63` for
eight bytes of unwind data. A nonzero foreign tail or a different instruction,
jump-back, relay, target or layout rejects preparation. `RtlAddFunctionTable`
ranges cover the relocated body plus jump-back and **exclude the entry relay**,
which executes before the copied prologue.

Real Windows tests found that MinHook's ordinary RIP-relative absolute jump-back
is classified as a tail epilogue by `RtlVirtualUnwind`, which incorrectly skips
the copied Capture stack adjustment. Metadata alone did not pass qualification.
This diagnostic replaces only that owned 14-byte trampoline jump-back with a
same-length `MOVABS R11; JMP R11; NOP`. Authenticated disassembly finds no R11
references anywhere in the four complete native bodies. R11 is volatile, no
formal argument is changed, and the original native body remains unchanged.
The conditional Free early-return branch has no preceding stack adjustment and
retains its original equivalent layout.

Registered unwind data describes each actual copied prefix: Capture pushes RBP
and allocates `0x40`; allocation saves RBP at entry RSP `+0x10`; snapshot
destruction saves RBX at entry RSP `+8`; Free's copied test/branch changes neither
RSP nor a nonvolatile. Native prefix unwind records cannot simply be copied,
because their saved-register offsets include later original stack adjustments.

The tests use actual `RtlLookupFunctionEntry` and `RtlVirtualUnwind` at every
relocated instruction boundary, after MOVABS, at JMP-register, and at the
separate relay boundary. Caller RIP, RSP, RBP and RBX must restore exactly.
Metadata registration failure and conflicting-tail gates run before activation;
only never-activated fixture hooks are removed in these private tests.

## Standalone evidence

```powershell
cmake -S Experiments/GfxSnapshotProfile -B .work/gfx-snapshot-profile-build -G "Visual Studio 17 2022" -A x64
cmake --build .work/gfx-snapshot-profile-build --config Release -j 2
ctest --test-dir .work/gfx-snapshot-profile-build -C Release --output-on-failure
```

Thirteen scenarios pass under MSVC `/W4 /WX /EHsc`: atomic windows and clock
gates; exact deadline/record bounds; 16-thread counting; all registered unwind
boundaries and relay exclusion; failed registration/foreign tail; actual
MinHook-created layouts before activation; arguments, AL/RAX, LastError and
unchanged page pointers; native C++ exception propagation; raised SEH through
nested observer scopes; successful stop and every partial-enable rollback;
foreign activation/stop byte preservation; one-off timeout restoration; and
refusal to arm the profiler in the standalone executable.

These tests use owned executable fixtures and test callbacks, never the Sims
process. They prove the inspected plumbing, not a game performance gain.
