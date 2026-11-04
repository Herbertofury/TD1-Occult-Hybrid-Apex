# Read-only mod provenance prototype

This experimental tool supplies filesystem/module observations around a future
offline ETW capture. It has not been run
against Sims or a user profile, and must not be presented as a qualified game
test. Its tests use temporary synthetic files and stub game/window identities;
one additional test enumerates only its own synthetic Python test process.

It requires the current token-marked, active disposable test journal and exact
profile path, PID, creation FILETIME, executable path/hash, and visible Canvas
identity. It does not touch saves, Tray, or the protected original. It hashes
every file under `Mods` (including Resource.cfg and generated settings) twice,
records the complete sorted relative paths and SHA-256 digests, and refuses a
change in the set or digest during that scan. It checks loaded-module paths,
bases and sizes through a Windows Toolhelp snapshot, hashes each on-disk module
twice, and rechecks process/window/module identities after the scans. A denied,
empty, incomplete or truncated module enumeration refuses the observation.

File reads use a Windows `CreateFileW` handle with final reparse-point following
disabled; handle attributes, final resolved path, file identity, size and time
are checked around hashing. Profile paths and traversed directories reject
symlinks/reparse points. Profile evidence files with multiple hard links are
refused. System modules may be hardlinked because Windows commonly installs
them that way; only their opened path and on-disk contents are observed.
Checking paths and files is not an atomic filesystem snapshot: a directory can
be replaced between enumeration and access, and a file can change and return
to the same contents between observations. Handle checks, repeated scans and
reparse rejection reduce that risk; they do not prove continuous stability.

The two observations must have the same journal and marker digests, exact
process lifetime, window/viewport/DPI/foreground identity, loaded module
identity and on-disk file digests, and complete mod file inventory. A matching
pair must surround the offline adapter's QPC ready/end interval; duplicate,
overlapping, wrong-PID, wrong-profile, mismatched-clock and explicitly synthetic
records are refused. The saved comparison pins both prior-observation and
capture-metadata hashes. This binds the declared capture metadata; it does not
independently revalidate its ETL, collector, loss or action evidence. Use the
existing offline adapter/comparator for those checks.

Do **not** treat matching snapshots as proof that the running process opened
the declared profile, that Sims loaded a particular package or script, that
the bytes in memory match the module files on disk, or that nothing changed
between scans. The report sets all of those proof flags to false. In particular,
declarations in a journal or mod-state JSON are not independent proof of load.
Additional separately observed, PID/creation-time-bound game evidence is still
required before claiming any real baseline or stage identity.

The full inventories are not silently truncated; directory entries are bounded
as they stream, and a known oversized file is rejected before reading it. The tool fails if more than
200,000 filesystem entries, 1 TiB of mod bytes, 4,096 modules, 128 MiB of
snapshot JSON, or 4 MiB of capture metadata would be exceeded. These conservative
bounds may need a reviewed change for unusually large setups. Hashing the full
mod set and every loaded module twice per observation can be expensive. Both
scans occur **outside** the timed capture; their durations are recorded. Hashing
can warm filesystem caches, so document and apply the same cache preparation in
both comparison orders. The tool makes no claim about capture overhead or speed.

From a matching checkout, an authorized operator can take a new first observation under its existing
`.work` directory:

```powershell
python tools/mod_provenance.py --state <disposable-journal> --profile <test-profile> --token <exact-token> --pid <pid> --creation <creation-filetime> --exe <game-exe> --exe-sha256 <game-sha256> --output .work/<new-before>.json --run
```

After a separately coordinated, completed offline ETW capture, take a second
observation with all the same identity arguments and a different new output:

```powershell
python tools/mod_provenance.py --state <disposable-journal> --profile <test-profile> --token <exact-token> --pid <pid> --creation <creation-filetime> --exe <game-exe> --exe-sha256 <game-sha256> --output .work/<new-after>.json --compare-to .work/<new-before>.json --capture-metadata .work/<capture>.json --run
```

All output paths must be new and remain in that checkout's private `.work`.
The tool requests no writes to the game, trace session, saves, settings or
profile; filesystem reads may update access-time metadata. Actual game
qualification must coordinate with the owner of the single live game and use
a safely backed-up isolated profile; this prototype does not do that setup.
