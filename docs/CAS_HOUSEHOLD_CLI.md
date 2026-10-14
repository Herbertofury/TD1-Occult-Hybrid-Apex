# Independent full-household CAS transactions

`game cas --value full` enters the native existing-household editor (mode 0).
It first captures the selected Sim and every hybrid companion independently,
then prepares existing native base/alternate availability pairs. Each capture
retains every stored appearance and the separate active owner. An unresolved
companion prevents entry. Ordinary phone/MCCC entry is a separate unfinished
integration gate; this command's proof cannot certify it.

Use the marked disposable profile and an existing loaded household. Entry,
semantic editing, return and explicit commit produce separate external proofs.

```powershell
python tools/apex_cli.py game cas --value full --state .work/reusable-profile-session.json --sim-id SIM_ID --seconds 60 --output .work/unique-cas-entry.json
python tools/apex_cli.py cas-workbench --state .work/reusable-profile-session.json --sim-id SIM_ID --edit --panel skin_details --panel eyebrows --output .work/unique-cas-edits.json
python tools/apex_cli.py cas return --state .work/reusable-profile-session.json --sim-id SIM_ID --household-id HOUSEHOLD_ID --seconds 120 --output .work/unique-cas-return.json
python tools/apex_cli.py cas-household-commit --state .work/reusable-profile-session.json --entry-proof .work/unique-cas-entry.json --entry-sha256 EXACT_ENTRY_SHA256 --accept SIM_ID:2 --output .work/unique-household-commit.json
```

Replace placeholders with exact fresh native identities and proof hashes.
`--accept SIM_ID:FORM` may repeat for independently intended member/form edits.
Known form values are Human 1, Alien 2, Vampire 4, Mermaid 8, Spellcaster 16,
Werewolf 32 and Fairy 64. Unnamed changed forms restore their fresh entry
originals. An unchanged named form needs no fabricated edit. The command
observes every member before any plan or native commit. The selected member's
already-observed semantic-return journal is reused without replay.

Return deliberately reports explicit decisions required until commit; that
result differs from a native acceptance rejection. Inspect native return,
simulation ticks and transaction evidence rather than command exit code alone.
Commit verifies each appearance owner and restores every independently captured
availability context. It does not alter membership, generate forms or save.

Complete packets remain in the game-owned receiver and private proof files;
the CLI supplies hashes and decisions. Each mutation UUID is recorded before
submission. An uncertain operation stops the sequence. Poll its original UUID
instead of rerunning the command. A partially completed household commit is
not an atomic household transaction and is not automatically replayed.

After commit, capture every member, unpause, verify actual
`services.time_service().sim_now` progress, pause, and compare all stored plus
active appearances. Save and cold-load checks remain separate. Empty or
unavailable panels cannot count as successful edits. The fourteen Alien-panel
V100 test certifies its tested subset; it does not complete the 5,390-cell
household edit matrix. Tattoo acknowledgement currently has a retained native
acceptance rejection and remains uncertified. The direct first-slot prototype
also has a retained native crash. The guarded candidate refuses first-tattoo
insertion before any part/layer mutation; empty tattoo regions are reported
as quarantined rather than counted as edited.
