# External CAS recovery checkpoint — 2026-11-04

This branch holds recovery and experimental work, not a finished external Create-a-Sim product. Do not replace game files or ship these experiments as a working game integration.

## Current evidence

- A local private diagnostic preview rendered nine prepared combinations spanning two dress designs, two hair designs and selected color variants. The source-bound selection prototype was then exercised with a newly selected hair item followed by a dress item; the latter preserved the chosen hair source. These were local preview tests, not verification inside The Sims 4 or an actual browser acceptance test.
- A bounded catalog prototype registered 64 explicitly selected items from hash-pinned source packages. One item was prepared and frame-verified through an explicit local action. Unknown formats, missing resources and incompatible rigs are not generally solved.
- The experimental pose path rendered prepared static pose frames. Different geometry can trigger a separately pinned pose-cache rebuild. Native pose fidelity, general animation support and all age/species compatibility remain unverified.
- An isolated Tray grouping candidate matched the prior algorithm on generated fixtures. Whole-group atomic publication, Windows durability and game-native authoring remain unresolved. The candidate is not installed in game.

## Recovery artifacts

The files in `examples/` are research checkpoints. They are incremental patches or diagnostic sources, not a supported installer and not a complete runnable release. Some depend on earlier candidate snapshots; review their paths and prerequisites before applying them. Do not blindly apply them to main.

Recent checkpoints include:

- `catalog-preflight-candidate.patch` and `catalog-preparation-candidate.patch`: exact source identity checks and private source preparation.
- `combinatorial-preview-candidate.patch`, `nine-scene-capability-candidate.patch`, `dynamic-source-bound-preview-candidate.patch` and `dynamic-geometry-preview-candidate.patch`: bounded, source-bound preview selection experiments.
- `opt-in-preparation-gateway-candidate.patch`, `register-verified-variation-candidate.patch`, `batch-preparation-manifest-candidate.patch` and `rebased-source-selection-candidate.patch`: explicit local preparation, frame verification and active-scene selection research.
- `tray-grouping-scale-candidate.patch`: isolated grouping optimization and generated-fixture checks.

Creator packages, private asset derivatives, account data, runtime configurations and rendered frames are not included. The local test results do not imply rights to redistribute source content.

## Still required

A usable external CAS needs an integrated distributable application, real browser/desktop acceptance, safe access to the user's actual installed content, broad CC/mesh/material coverage, faithful skin and body/face editing, reliable poses, shared in-game favorites and outfits, and verified native Tray/save workflows. The current local registrations are not durable across restart, and many choices remain unsupported. Windows/game-side validation requires access to an authorized environment. Keep original game data safe and make no claim of completion until those gates are actually met.
