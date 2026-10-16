# Native CAS existing-owner selection

The native CAS importer for game 1.128.90.1030 constructs one primary and one
alternate from the saved occult tracker. The native change-kind implementation
then runs an appearance generator. Merely advertising all memberships does not
make that converter select the independently stored appearances.

`ApexNativeCasEngineWin.h` implements a different native path for an explicitly
captured development household. It intercepts the native Sim importer, reads
each existing occult record with the game's field deserializer, and owns
separate native allocations for those records. The V151 runtime observed a
narrowed client packet for all five household members, so V152 also supplies
each complete pre-entry native save-model message from the Live game thread.
EA's native protobuf parser and field deserializer construct the missing
client owners in memory. No disk export or live-owner replacement is involved.
A narrowed client packet cannot overwrite this complete import.
Missing, repeated or unexpected
owners prevent activation. Importing does not overwrite the game's current
appearance.

After complete capture, the selection hook replaces the native generator for
owned targets. The normal CAS operation records current edits first. The hook
keeps those edited records, adds the imported owners absent from that cache,
and constructs independent before/after native history records. The selected
record supplies the requested appearance. Every captured membership remains
in both the history headers and cached appearance headers. Unscoped Sims and
new-kind generation retain the existing game implementation.

The DLL checks the exact executable SHA-256 and runtime function fingerprints
before installing the six hooks. One hook replaces a composite
alternate-kind result with the selected single family for a scoped hybrid's
Human appearance. The other prevents the legacy Vampire/Witch-priority
normalizer from replacing an already selected kind in a known hybrid genus.
V153 captures the active entry owner separately from the seven stored owners
and imports both the correct primary and actual alternate before the native
client is ready. The actual socket handshake closes that initialization
lifetime; later CAS edits cannot be overwritten by the entry capture.
V153 imported all forty owners in the actual household, but the primary kind
still read Vampire and an Alien request did not reach the controller at all.
The game's `SetSimOccult` callback compares the request with the first set
membership bit, rather than the displayed kind. For an all-occult Sim that
comparison treats Alien as already selected. V154 replaces that decision for
captured existing owners, calls the original complete controller transaction,
and sends the same native avatar notification. Unscoped selections retain the
original callback. The active capture also takes its kind from the tracker's
explicit current field after appearance deserialization, which can otherwise
apply a legacy priority classification.
It uses native construction, deep copying
and destruction on the native calling thread. There is no frame-loop polling,
executable-file rewrite, CAS exit/re-entry substitution or shared appearance
allocation between history records. The permanent Source guard remains enabled.

Development CLI, with a new external proof file for each call:

```
apex_cli.py game native-cas-engine --state SESSION --value ARM_JSON --output NEW_JSON
apex_cli.py game native-cas-engine --state SESSION --output NEW_JSON
apex_cli.py game native-cas-engine --state SESSION --value ACTIVATE_JSON --output NEW_JSON
```

`ARM_JSON` has `operation: "arm"`, a fresh hexadecimal `scope_id`, and a
`members` array containing exact decimal `sim_id` strings and `owned_mask`
integers. `ACTIVATE_JSON` contains `operation: "activate"` and that same scope.
Activation requires every scoped member's complete native capture. Reusing a
scope with changed members is refused.

The native fixture exercises complete and incomplete imports, duplicate kinds,
edited-record precedence, target-owner selection, independent history copies
and matching allocation/destruction. Private Python 3.7 checks the exported ABI
and rejection of a foreign host executable. These checks do not prove in-game
appearance retention. Actual cross-kind edits, native return serialization,
undo/redo, all household members, cold loading and Tray/Gallery round trips
remain release gates until corresponding runtime evidence is recorded. The
candidate reports `production_ready: false` throughout this qualification.

V154's eight native CTests pass, including the Vampire-displayed/Alien-requested
regression, numeric argument forms, unscoped/invalid request handling and
explicit active-kind restoration after the field loader. These fixture checks
are not an in-game cross-kind edit or serialization result.
