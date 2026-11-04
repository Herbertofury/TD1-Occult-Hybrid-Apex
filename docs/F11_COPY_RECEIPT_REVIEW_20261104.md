# F11 package-copy identity review

The live catalog's explicit Studio-open path verifies a package against its
pinned index during resolution, then prepares a sealed copy. A synthetic DBPF
test reproduced a change between those two steps: non-CASP package bytes could
change while the CASP bytes remained identical, and the previous flow launched
the different package copy. The open path now carries the originally inspected
package SHA-256 into preparation and compares the fresh TGI, CASP hash, body
type, resource ID and package hash before requesting a launch. An unchanged
package remains openable; the reproduced changed package is refused before the
launcher. The original source package is not edited by the operation.

The broker's existing open receipt now includes the cached TGI, CASP hash and
verified copied-package hash, plus explicit fields indicating that Studio's
GUI acceptance, individual CASP selection and current-equipped identity have
not been verified. The overlay compares a present extension with the requested
row. Older receipts without the extension remain accepted for compatibility and
provide no new evidence. Because the broker calls the launcher before returning
its receipt, a mismatched receipt can only report uncertainty after that call;
it cannot prevent or undo a launch. This is not a current-owner lease, a proof
of the game's loaded package source, or confirmation that Studio opened or
selected an individual resource. The copied file or current selection could
change after the observed checks.

Validation: a reconciled full sidecar compiled as Debug in an isolated build
using a previously built, hash-verified Rust archive; no DLL was loaded or
installed. The current native resource test passed 135 checks. Twenty-four
selected Python 3.7 tests passed using test-only SQLite/Path compatibility
shims and mocked image decoding; they include an unchanged open and a synthetic
same-CASP/different-package change after resolution. Full unshimmed broker
tests, real image decoding, Studio GUI behavior, current owner/resource
freshness and game behavior remain unverified. No package or game files were
installed, and recovery/epoch compatibility still needs review before use.
