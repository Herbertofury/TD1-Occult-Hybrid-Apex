# Installation metadata inventory and integration gaps

This is a read-only discovery aid, not a CAS asset loader. It enumerates direct
`.package` files under `Data/{Client,Shared,Simulation}`, top-level pack
directories named `EPnn`, `GPnn`, `SPnn`, or `FPnn`, and corresponding
`Delta` pack directories. It uses directory entries and file sizes only; it
does not open package content, inspect a Sims user profile, follow discovered
links, extract assets, or write results to disk. It emits aggregate counts to
stdout, without filenames or paths. Errors are counted and result in a nonzero
exit status. It is deliberately nonrecursive; files outside these locations
are not counted. The input must be a trusted installation directory. This is
not a security sandbox against paths being changed concurrently.

```powershell
node inventory.mjs 'C:\path\to\The Sims 4'
node --test inventory.test.mjs
```

## Observed on GoldenOreo, 2026-11-04

The registered installation reports `gameversion = 1.129.39.1030` in its
`Game/Bin/Default.ini`. The probe returned zero errors and zero discovered
links: three base directories, 116 pack directories, 117 delta pack directories,
132 client-full and 133 client-delta package files, plus 178 clip-header,
413 simulation, 4,041 strings, 120 thumbnail and one UI package. These are
filesystem counts, not a list of owned/enabled packs, loaded resources, valid
CAS items, or evidence of usable renderer coverage. The running game and user
profile were not accessed by the probe. It does not establish completeness of
the installation or resource ownership.

On this Windows host, all three inventory tests passed. Separately, the
recovered dependency-free Rust core was compiled directly with
`rustc --edition 2024 --test src/lib.rs` and all 114 core tests passed. The
normal `cargo test --lib --offline` could not resolve its pinned dev dependency
`libc = 0.2.191` from the local cache. The direct core test is not a substitute
for the full Cargo test suite, renderer acceptance, or game validation.

`Data/Client/Resource.cfg` declares client delta packages at priority -20 and
client full packages at -30, with separate priorities for clip headers,
thumbnails, and UI. This establishes that looking only in base full builds
would miss declared inputs; it does not by itself prove complete cross-pack,
mod, duplicate-key or conditional-selection precedence. The loader must read
the relevant configuration and validate actual game behavior; never infer the
winner solely from filenames or directory counts.

## Required integration and validation

1. Implement a bounded, read-only package index that retains source identity,
   full resource keys, offsets, compression metadata, and all candidates for
   collisions. Resolve configured load order only when supported by evidence;
   report ambiguity instead of silently picking a source. Validate against
   independent readers and actual current-version packages. Cache derived data
   privately and invalidate on source/config changes.
2. Resolve CAS part dependencies across base, pack, delta and explicitly
   authorized custom content: geometry, textures, swatches, rigs, morphs,
   materials, pose/animation data, thumbnails and localization as applicable.
   Missing, unsupported, overridden or incompatible resources must be visible
   as such; an indexed package does not mean an item renders correctly.
3. Reconstruct geometry, deformers, layered textures, alpha/depth behavior,
   material/shader behavior, camera, lighting, animation and the room. Compare
   representative ages, frames, occult forms, CC combinations and poses with
   the running game only after coordinated access is available. Existing
   source-bound prepared previews and isolated diagnostics are limited evidence,
   not general rendering or native parity.
4. Define one canonical Sim/form/outfit model and bounded editing transactions.
   Establish authoritative identity, conflict detection, undo, and verified
   readback before any live mutation. Favorites/outfits and Live/CAS state need
   validated game-side ownership and persistence, not independent lookalikes.
5. Integrate and independently review the existing native Tray validation
   candidate against its actual recovered baseline. Native household creation,
   Windows durable group publication, isolated Library load and save/reload
   validation remain required. Synthetic protobuf success is not game acceptance.

No creator or game assets are included in this directory. The probe does not
access the original profile, nor should it be pointed at it during the Apex
baseline. Game/profile testing must be coordinated separately.
