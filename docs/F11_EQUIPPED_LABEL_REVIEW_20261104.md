# F11 equipped-item label review

The preferred-name list previously displayed a CC package-filename fallback
without identifying it as a filename. It now appends `(package filename)` to
that fallback. Localized titles, explicit package/code modes, unavailable-name
messages and the existing internal-code marker retain their prior behavior.
This is a labeling correction; it does not make a filename an item title.

An isolated MSVC 19.51 build of the modified ApexOverlay sidecar completed
with offline Cargo and emitted warnings but no errors. The existing native
resource test target passed 124 checks, including six label checks. A separate
synthetic host test covered inspected skin-detail, repeated and unknown body
types, full 64-bit identity, ambiguous resources, stale appearance and mocked
image/package-copy routing. It did not decode images or launch Sims 4 Studio.
No DLL was loaded or installed.

Full user-requested F11 coverage remains open. Native CAS catalog IDs do not
yet have verified CASP mapping; image and package-open data require an
individually inspected, matching cache entry; unavailable localized names can
still fall back to a filename or internal code. The current Studio action opens
a verified copy of the containing package and does not select the individual
CASP resource. All categories, exact titles and images need real-source and
coordinated in-game verification. This source-only branch is not a release;
reconcile it with newer preserved work and review recovery/epoch compatibility
before any build is considered for use.
