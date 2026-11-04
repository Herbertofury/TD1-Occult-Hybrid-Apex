# Source-bound separate-clothing preview candidate

This isolated source patch extends the existing prepared-scene binding model to accept complete top-and-bottom pairs, in addition to dresses. A selected top or bottom changes only that slot within already-prepared pair scenes. It refuses missing/conflicting clothing modes, inconsistent prior transitions, and mismatched catalog body types. It binds both clothing identities to the pinned runtime descriptor and catalog, checks descriptor mesh/material identities, and presents explicit preview actions for top and bottom. Source, config, launcher and catalog remain trusted local inputs. No game data is written.

## Verified scope

Four privately staged real-source combinations (two tops × two bottoms, with identical respective meshes and disjoint texture atlases) yielded eight bound catalog parts and 32 prepared transitions. A local HTTP replay switched top, bottom, then top, retained hair, shoes, eyes and tattoo, and produced three distinct 512×512 preview frames. Stale and unknown scene requests were rejected while retaining the last good scene. This is a single source set with four prebuilt combinations, not arbitrary or on-demand CC support. The pose cache was reused only after the pair mesh hashes matched. Game and creator assets, catalog, scene configurations and frames remain private and are not part of this checkpoint.

The isolated patch passes 23 Python tests and 7 synthetic JavaScript DOM tests. Chromium was installed but actual browser acceptance was not completed: its process aborted because the environment denied socket creation. The optional browser test is retained as an unverified test harness, not evidence of a pass.

## Boundaries and next gates

The existing preparation owner still does not build arbitrary top/bottom combinations on demand. The candidate does not transition between a full-body dress and separates; it refuses an incomplete or mixed clothing mode rather than inventing a counterpart. Texture-atlas overlap is still rejected by the pair builder. Native shader fidelity, broader CC and pose compatibility, real-browser acceptance, durability across restart, game-visible changes, and native Tray authoring are unverified. This patch is research code, not an installer or production release.

The patch is relative to the recovered post-v138 `rig-recovery` source. Review and apply in an isolated copy. `test_private_separates_http.py` requires a separately prepared private config and bindings, which are intentionally not supplied here. No permissions are implied for redistributing creator assets.
