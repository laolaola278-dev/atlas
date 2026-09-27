# Synthetic FHIR Fixture Plan

Planned regression fixtures for P1 FHIR vertical slice:

- valid-patient-bundle.json
- invalid-profile.json
- invalid-reference.json
- validator-missing.json
- terminology-expired.json

Acceptance goals:
- synthetic-only data
- Profile Catalog validation
- fail-closed validator behaviour
- audit_event_id propagation
- Bundle transaction validation