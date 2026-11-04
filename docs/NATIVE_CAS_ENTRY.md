# Protected native CAS entry

V116 intercepts the game's `_commands.client_cheat` boundary for the exact
`sims.exit2cas` and `sims.exit2caswithhouseholdid` commands. The installed game
and MCCC 2026.5.0 both use this boundary, including MCCC's previously imported
Python `client_cheat` alias. No MCCC private implementation is patched.

Before the native call, Apex verifies the game thread, Live zone, connection,
selected native Sim and the complete loaded household roster. Every hybrid
member receives a durable raw appearance checkpoint and original navigation
identity. Native CAS availability preparation follows those captures. The
explicit CLI entry uses the same boundary and a synchronous prepared scope;
it cannot create a second checkpoint or replay an entry.

An earlier phone capture is reusable only while its receiver-owned native Sim,
complete raw appearances and native context remain exact. An observed return,
stale capture, unresolved companion or consumed entry blocks another entry.
Each member's native submission intent is durable before the command is sent.
A native exception retains that intent and never authorizes automatic replay.

Return uses the existing all-owner receiver and explicit phone/F11/CLI review.
Raw differences alone do not identify user intent: native CAS can propagate an
edit to other owners. Every changed form needs an independent decision before
commit. Unchanged owners can be committed without invented edit decisions.
Permanent transition, save and transaction protection remains enabled alongside
the direct native cross-form copy prevention patch.

The hook runs only at command submission, with no periodic scan or per-frame
appearance serialization. Unrelated commands delegate directly. Coverage is
limited to Python-to-native entry through these two commands; direct native
UI routes require separate evidence. This does not establish every MCCC menu,
every special form or every CAS panel as production qualified.

Fourteen focused tests cover cached aliases, full-household and career routes,
fresh phone capture reuse, stale/observed captures, companion preservation,
explicit return commit, native exceptions, duplicate submission, foreign
identity, wrong thread and idempotent installation. Actual game results are
recorded separately in the household validation report.

V117 also retains the complete household roster in the ordinary-route receipt,
so the real host household-return validator can consume it. A contract test
passes the receiver's ordinary-route result through that host validator.

An actual V116 Alien eyebrow-color test exposed a separate transport fault:
a complete but mismatched swatch result became a terminal failed operation,
but its rejected success acknowledgement also closed the socket. V117 consumes
that exact retained failed packet as transport traffic while keeping the edit
failed. Malformed, foreign or incomplete packets remain unresolved. Three
tests cover failed-value retention, continued status, identical duplicates and
changed/invalid acknowledgements. This repairs failure handling; it does not
establish that the requested eyebrow color itself now applies correctly.
