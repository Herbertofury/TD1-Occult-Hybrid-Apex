# Outfit row rollback review

`dresser_parts.write_rows` updates five parallel outfit arrays. The previous
exception handler stopped restoring arrays if a restoration itself raised,
which could leave later arrays unrestored and mask the original write error.
The source-only change now attempts each restoration. It re-raises the original
write error if all restorations succeed; otherwise it raises a distinct
`OutfitRollbackError` naming the failed fields and chains the original write
error. It cannot repair a container that refuses restoration or guarantee an
atomic rollback. Individual restoration exceptions are not retained.

Host-side fault injection reproduces the previous double-failure behavior and
checks normal writes, failures in each array, subsequent restoration attempts,
multiple failed fields and preservation of the original error. Separate tests
exercise the appearance merge and hair-reconciliation callers with synthetic
parser and container objects; those paths do not serialize or return the
partial message after the injected failure. The hair event test checks that an
error is recorded. These tests do not execute in game or prove live data was
damaged by the old behavior.

The failed array can remain damaged in a retained parser object. A custom
snapshot parser can supply an object whose ownership and reuse are not yet
proved, and the top-level generic error boundary reduces exception details to
a message. Native protobuf failures, parser ownership, guarded Studio Apply,
CAS preparation and form-switch recovery need further qualification. This
source branch is not an approved game build. A script archive containing the
change requires an independently audited recovery/epoch review and isolated
in-game validation; do not silently repin or deploy it.

Validation used Python 3.7 and 118 selected helper, caller, appearance, hair
and Studio tests. The host-only `protobuf` 4.24.4 wheel was obtained from
[PyPI](https://pypi.org/project/protobuf/4.24.4/), checked against the published
SHA-256 `80797ce7424f8c8d2f2547e2d42bfbb6c08230ce5832d6c099a37335c9c90a92`,
and extracted to a separate task directory for testing only. It was not added
to the mod, the user environment, or the source branch.
