# Independent F11 appearance assembler

This directory contains Apex's adapters for the separately licensed
[CmarNYC-Tools/TS4SimRipper](https://github.com/CmarNYC-Tools/TS4SimRipper)
appearance assembler, pinned at `862a32949e5156b371e2d2f83de4e37e0bb1afcc`.
It runs without showing a window and supplies actual meshes, textures, rig
and animation data to Apex's native D3D11 preview. The Live Sim and game camera
are independent of this preview.

Build from the repository root with an installed .NET 8 Windows SDK:

```powershell
python -B tools/build_preview_worker.py
.work/preview-worker/bin/ApexPreviewWorker.exe --self-test
```

The recipe verifies the upstream source/dependency hashes before extracting,
applies the adapters, builds the worker, and writes `provenance.json` plus the
complete upstream/adapters/recipe `corresponding-source.zip` beside it. Preserve
that source archive and `SimRipper-LICENSE.txt` when distributing the helper.
The adapters are covered by this directory's GPL-3.0 license; the native
renderer communicates with the helper through bounded process/loopback data.

`tools/sim_preview_service.py` reads installed package resources in place. It
retains scenes in a bounded 128 MiB memory cache and does not export a package,
mesh or texture for each Sim. The assembler's managed heap is capped at 2 GiB.
Thumbnails share a content-addressed asset cache; opening a package in Studio
deliberately makes a separate editable copy, retaining the original untouched.

Current development use requires building this helper and starting the
catalog/preview services from the repository. The mod candidate ZIP alone
does not contain a portable auto-starting helper installation. Complete EA
shader/material matching, all poses, swatch families and full CAS parity
remain open; a successfully rendered scene does not establish those claims.
