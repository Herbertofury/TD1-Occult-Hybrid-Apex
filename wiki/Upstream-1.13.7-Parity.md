# 1.13.7 Behavioral Reference

Apex uses the latest verified Occult Hybrid release only as a behavioral/regression reference. The production Apex hybrid engine is first-party and must work with no TD1/IcedCream/LordPercival files installed.

Required verified parity items:

- missing STBL fix;
- TMex PhoneSearch / PlantSim Pie Menu compatibility;
- werewolf tuning injections;
- fairy tuning injections;
- fairy bloodline tuning injections;
- selected-Sim occult-cache diagnostics;
- global occult-cache diagnostics;
- CAS-session cache diagnostics.

The public upstream GitHub tree should not be assumed to contain every distributed 1.13.7 change. Compare package/release evidence and preserve provenance.


## Standalone rule

The behavior here is implemented independently in `ApexOccultHybrid.package` + `ApexOccultHybrid.ts4script`. Historical packages/scripts are not runtime dependencies and are excluded from clean-profile release proof.
