# F11 equipped-category lookup

The equipped-items draw previously scanned every category for every equipped
part, then scanned every equipped part for each possible empty slot. It now
builds a local index once per draw. This changes lookup work without retaining
category or outfit state across draws.

The key remains the existing `ui::Scalar(body_type)` value. The first category
with that key wins, including duplicates and empty values. Copied group strings
avoid pointers into mutable catalog JSON. Original equipped and empty-category
row order, labels, item indices, sorting, search and action dispatch remain in
the production draw function. The index neither filters content nor changes
resource selection, owner identity, recovery state or native CAS.

`ApexEquippedCategoryIndexTests` compares the header against the former loops.
The integrated source passed 1,208 differential checks covering absent and
empty data, duplicate categories, unknown values, maximum uint64 identities,
both empty-slot modes, catalog/outfit changes between draws, and 600 generated
arrangements in both modes. CTest registers `native-equipped-category-index`.
The optional `--benchmark` argument emits paired, order-alternating synthetic
host timings. No timing threshold is part of the acceptance test.

A private complete Debug overlay build with the same production proxy/header
change linked successfully. The existing 148 native resource checks passed
against that source. That private build used a previously built, hash-verified
Rust archive in place of invoking Cargo; it was not loaded or installed.

These results establish offline row-projection equivalence and compilation.
They do not establish game frame-time improvement, input latency, visual
acceptance or resolution of a reported hitch. Keep actual F11 behavior and the
matched game-performance cases open until measured on the qualified profile.
