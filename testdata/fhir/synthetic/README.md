# Synthetic FHIR fixtures

Regression fixtures for the P1 FHIR vertical slice. All data is synthetic; none
of it is derived from a real patient.

## Envelope convention

Atlas provenance never travels inside the FHIR payload. `internal/workflow/slice.py`
declares `ATLAS_ENVELOPE_FIELDS` (`synthetic`, `purposeCode`, `actorId`, `whyCode`,
`consentState`, `codeSystem`, `reviewedAt`); `pure_resource()` strips them and the
official validator only ever sees the projection. The gate still consumes the
envelope, so both halves are needed and both are asserted.

## Fixtures

| File | Shape | Used for |
|---|---|---|
| `valid-patient-bundle.json` | real FHIR transaction Bundle: `entry[].fullUrl` + `entry[].resource` + `entry[].request` | stage one; judged as a whole by the official validator including nested resources |
| `observation.json` | Atlas envelope around a base-R4 valid Observation | stages two to seven; the projection is what the official validator judges |
| `invalid-profile.json` | profile not in the catalog | `profile-not-declared` |
| `invalid-reference.json` | missing or malformed subject reference | `patient-reference-missing` |
| `validator-missing.json` | no official outcome record supplied | `validator-result-unknown` |
| `terminology-expired.json` | code system release past its review date | `terminology-release-expired` |
| `r4-observation-invalid-status.json` | official R4 observation example with `status` broken | negative control: the official engine must reject it |

The nested Observation inside the bundle is byte-identical to the projection of
`observation.json`, so the two official runs judge the same clinical content.

## Why these fixtures pass the official validator

LOINC `29463-7` makes validator 6.10.4 apply the bodyweight profile (4.0.1), which
requires `category` with the VSCat slice and `effective[x]`. Both are present here;
removing either produces structure errors. That was measured, not assumed.

## PHI scanning

`valid-patient-bundle.json` carries a digest-bound allow entry in
`tools/phi-scan/rules-atlas.json`: its file name contains `patient`, which makes
every long token sensitive-context, so standards URLs and kebab-case resource ids
trip the scanner. The entry pins the file digest, names an owner and expires.
