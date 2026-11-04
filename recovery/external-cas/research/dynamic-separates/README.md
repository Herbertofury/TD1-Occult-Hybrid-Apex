# On-demand separate-clothing preview candidate

This cumulative research patch applies to the recovered post-v138 `rig-recovery` source (it includes the earlier prebuilt-separates patch, so do not apply both). It extends pinned catalog admission for tops and bottoms, constructs a combined private preview from two separately authorized packages, retains each source's CASP, package, mesh and material hashes and shared rig identity, verifies the staged frame, and binds the result into the existing explicit preparation/activation workflow. The active scene is not replaced until verification succeeds. It is not an installer or native game integration.

For an active separate-clothing scene, each selected part is rebased against a validated snapshot of all six slots. Package paths come only from a trusted, hash-pinned owner source map, never from a catalog row or browser request. Reused sources are rebound to the pinned catalog, and top and bottom packages are separately reopened and pinned. Provenance checks the individual component records and the combined mesh, material and descriptor before registration. Stale and duplicate activations are refused; failure retains the last good scene. Existing dress-mode handling remains in place. Mixed dress/separates transitions remain unsupported.

The first on-demand path intentionally allows only an identical combined clothing mesh, head, shoes and hair against the prepared pose cache. A changed mesh is refused rather than triggering an unverified rebuild. The pair builder rejects different projection rigs, overlapping nonzero-alpha atlas texels and missing resources. There is no claim that a common projection rig proves native game compatibility. The separate pipeline has a 16-scene/16-part limit; when the part limit is reached before the scene limit it can refuse a new variation. The background owner is a Linux research lifecycle, not a hardened OS sandbox or power-loss guarantee.

## Evidence

- In an isolated private real-source fixture, an owner-built manifest selected top, bottom, top, then a previously prepared top. Each result was frame-verified. Hair, shoes, eyes and tattoo identities were retained; the reused combination produced the same frame. Stale preparation and activation generations, plus duplicate activation, were rejected. No game files were touched.
- This used two swatches each of one top and one bottom with matching respective meshes and nonoverlapping atlases. It does not establish arbitrary CC compatibility or game rendering fidelity.
- The candidate passed 59 Python checks and 7 synthetic JavaScript checks. A clean isolated application of this cumulative patch independently passed 58 selected Python checks and the 7 JavaScript checks. Private fixture scripts and logs demonstrate only the scoped local run.
- A real-browser attempt did not run because Chromium aborted when the environment denied socket creation. No browser acceptance is claimed.

## Still needed

Real game and installed-version validation, native CAS shader/material and body appearance parity, arbitrary asset support, general pose-cache rebuild and rig verification, dress↔separates transitions, durable session restore, complete editing and the UI-to-native-record save path remain unverified. The candidate does not yet implement all CAS functions, native Tray authoring, live-game synchronization or full-room parity. Creator/game assets and private catalog/configuration files are excluded.
