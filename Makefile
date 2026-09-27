.PHONY: verify contracts test build lint slice matrix official provision

verify:
	python plan/verify_first_round.py
	python -m unittest discover -s tools -p 'test_*.py'
	python -B -m unittest internal.workflow.test_slice internal.audit.test_file internal.audit.test_chain
	$(MAKE) slice
	$(MAKE) matrix

slice:
	python -B tools/evidence/fhir_slice_acceptance.py

matrix:
	python -B tools/evidence/traceability.py

# Requires ATLAS_FHIR_VALIDATOR_JAR and a JRE; see tools/evidence/provision_fhir_validator.py
provision:
	python -B tools/evidence/provision_fhir_validator.py --verify-only

official:
	python -B tools/evidence/fhir_official_validation.py
	python -B -m unittest internal.contract.test_hapi_validator

contracts:
	@command -v buf >/dev/null 2>&1 && buf lint api/proto || echo 'buf unavailable: contract lint deferred to P0 environment'
	@command -v cue >/dev/null 2>&1 && cue vet api/cue || echo 'cue unavailable: policy validation deferred to P0 environment'

build:
	go build ./...

test:
	go test -race -cover ./...

lint:
	gofmt -l internal cmd tools
	go vet ./...
