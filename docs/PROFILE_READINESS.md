# Isolated profile readiness

Reusable profile status now requires an existing `Mods` directory and a readable
regular `Resource.cfg`. Previously an empty walk could report ready when Mods
was absent, and Resource.cfg was skipped without checking it existed. Directory
walk errors now propagate instead of silently omitting inaccessible entries.

An optional schema-2 journal field, `resource_cfg_sha256`, binds the exact
configuration bytes. Invalid or mismatched pins refuse readiness. Without that
field, legacy configurations retain their existing behavior and report
`present_unpinned_unverified` with the observed digest. Presence and hashing do
not validate EA configuration grammar or prove a historical baseline match.
This change neither modifies configurations nor adds pins to existing journals.

When `verify_original=True` is requested without the journal's `previous_state`,
status now returns not-ready with `original_inventory_baseline_unavailable` and
an unknown inventory result. It previously raised an incidental KeyError. No
original-profile verification is inferred from a missing baseline.

Validation on the integrated source: nine new temporary-profile tests, the 13
existing reusable-profile tests and two legacy profile-status tests pass. The
new cases exercise actual status dispatch and the launch-plan path with mocked
EA account identity, without launching a game. They cover missing files, read
and walk errors, optional pins and preserved legacy configuration behavior.

These are CLI readiness tests. They do not prove which profile a running game
opened, which packages loaded, complete filesystem stability or game performance.
Controlled runs still need independently recorded isolation, settings and actual
game observations.
