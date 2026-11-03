# External CAS source recovery (in progress)

This branch is a partial source recovery, not a usable CAS release or installer. It preserves recovered code separately from the active Apex development branch. It does not contain game data, creator CC, pose inputs, private catalogs, or credentials. Some files and generated bundles are still being restored; builds and live-game integration are not yet qualified here.

Earlier isolated testing did render real creator CC and play actual pose sequences, but those runtime inputs are not present in this branch. The newly recovered version also passed synthetic browser-to-Rust frame tests. Neither demonstrates complete CAS editing, reliable saves, or native-game acceptance. Do not enable mutation based on this branch alone.
