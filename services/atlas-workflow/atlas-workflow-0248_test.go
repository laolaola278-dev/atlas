package workflow

import (
	"fmt"
	"testing"
)

func baseLoadTestFixtureReq() *WorkflowLoadTestFixtureRequest {
	return &WorkflowLoadTestFixtureRequest{
		IdempotencyKey:     "test-key-0248-load-fixture-abc",
		FixtureID:          "fixture-load-test-001",
		WorkflowID:         "workflow-synthetic-001",
		FixtureType:        "load",
		RequestsPerSecond:  100,
		DurationSeconds:    300,
		ConcurrentUsers:    50,
		SyntheticPatients:  []string{"synthetic-patient-001", "synthetic-patient-002"},
		TestScenarios:      []string{"scenario-create", "scenario-update"},
		ExpectedLatencyP50: 100,
		ExpectedLatencyP95: 250,
		ExpectedLatencyP99: 500,
		Metadata:           map[string]string{"synthetic": "true", "test_env": "staging"},
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_Valid(t *testing.T) {
	// Valid load test fixture request validation
	req := baseLoadTestFixtureReq()
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err != nil {
		t.Fatalf("expected no error for valid request, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_NilRequest(t *testing.T) {
	// Nil request validation
	err := ValidateWorkflowLoadTestFixtureRequest(nil)
	if err == nil || err.Error() != "request is required" {
		t.Fatalf("expected request required error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_EmptyIdempotencyKey(t *testing.T) {
	req := baseLoadTestFixtureReq()
	req.IdempotencyKey = ""
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "idempotency key is required" {
		t.Fatalf("expected idempotency key required error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_ShortIdempotencyKey(t *testing.T) {
	req := baseLoadTestFixtureReq()
	req.IdempotencyKey = "short"
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "idempotency key must be at least 16 characters" {
		t.Fatalf("expected idempotency key length error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_EmptyFixtureID(t *testing.T) {
	req := baseLoadTestFixtureReq()
	req.FixtureID = ""
	// Fixture ID is required for load test fixture
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "fixture ID is required" {
		t.Fatalf("expected fixture ID required error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_InvalidFixtureIDPrefix(t *testing.T) {
	req := baseLoadTestFixtureReq()
	req.FixtureID = "invalid-prefix-001"
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "fixture ID must start with 'fixture-'" {
		t.Fatalf("expected fixture ID prefix error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_EmptyWorkflowID(t *testing.T) {
	req := baseLoadTestFixtureReq()
	// Clear workflow identifier
	req.WorkflowID = ""
	// Workflow ID validation for load test fixture
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "workflow ID is required" {
		t.Fatalf("expected workflow ID required error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_EmptyFixtureType(t *testing.T) {
	req := baseLoadTestFixtureReq()
	// Fixture type must not be empty string
	req.FixtureType = ""
	// Request validation must reject empty fixture type
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil {
		t.Fatalf("expected fixture type required error, got: %v", err)
	}
	if err.Error() != "fixture type is required" {
		t.Fatalf("expected fixture type required error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_InvalidFixtureType(t *testing.T) {
	req := baseLoadTestFixtureReq()
	// Test invalid fixture type outside the allowed set
	req.FixtureType = "invalid-type"
	// Fixture type must be one of: smoke, load, stress, spike, soak, endurance
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "invalid fixture type" {
		t.Fatalf("expected invalid fixture type error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_NegativeRequestsPerSecond(t *testing.T) {
	req := baseLoadTestFixtureReq()
	// RequestsPerSecond must be >= 0 for load testing
	req.RequestsPerSecond = -1
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "requests per second must be positive" {
		t.Fatalf("expected requests per second positive error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_NegativeDurationSeconds(t *testing.T) {
	req := baseLoadTestFixtureReq()
	req.DurationSeconds = -1
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "duration seconds must be positive" {
		t.Fatalf("expected duration seconds positive error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_NegativeConcurrentUsers(t *testing.T) {
	req := baseLoadTestFixtureReq()
	// Negative concurrent users count is invalid for load testing
	req.ConcurrentUsers = -1
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "concurrent users must be positive" {
		t.Fatalf("expected concurrent users positive error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_EmptySyntheticSubjects(t *testing.T) {
	req := baseLoadTestFixtureReq()
	// SyntheticPatients slice must contain at least one entry
	req.SyntheticPatients = []string{}
	// Validation should catch the empty synthetic patients array
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil {
		t.Fatalf("expected synthetic patients required error, got: %v", err)
	}
	// Verify exact error message matches requirement
	if err.Error() != "synthetic patients are required" {
		t.Fatalf("expected synthetic patients required error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_EmptyTestScenarios(t *testing.T) {
	req := baseLoadTestFixtureReq()
	// TestScenarios array must have at least one entry
	req.TestScenarios = []string{}
	// Test scenarios validation for load test fixture
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "test scenarios are required" {
		t.Fatalf("expected test scenarios required error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_NegativeExpectedLatencyP50(t *testing.T) {
	req := baseLoadTestFixtureReq()
	// P50 latency must be non-negative for load testing
	req.ExpectedLatencyP50 = -1
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "expected P50 latency must be positive" {
		t.Fatalf("expected P50 latency positive error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_NegativeExpectedLatencyP95(t *testing.T) {
	req := baseLoadTestFixtureReq()
	// P95 latency threshold must be positive value
	req.ExpectedLatencyP95 = -1
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "expected P95 latency must be positive" {
		t.Fatalf("expected P95 latency positive error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_NegativeExpectedLatencyP99(t *testing.T) {
	req := baseLoadTestFixtureReq()
	// P99 latency expectation must be a positive value
	req.ExpectedLatencyP99 = -1
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil || err.Error() != "expected P99 latency must be positive" {
		t.Fatalf("expected P99 latency positive error, got: %v", err)
	}
}

func TestValidateWorkflowLoadTestFixtureRequest_PHIPatternInMetadataKey(t *testing.T) {
	req := baseLoadTestFixtureReq()
	req.Metadata = map[string]string{"patient_name": "test"}
	err := ValidateWorkflowLoadTestFixtureRequest(req)
	if err == nil {
		t.Fatalf("expected PHI pattern error, got nil")
	}
}

func TestCreateWorkflowLoadTestFixture_Success(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	req := baseLoadTestFixtureReq()
	fixture, err := CreateWorkflowLoadTestFixture(req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if fixture.FixtureID != req.FixtureID {
		t.Errorf("expected fixture ID %s, got %s", req.FixtureID, fixture.FixtureID)
	}
}

func TestCreateWorkflowLoadTestFixture_Idempotency(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	req := baseLoadTestFixtureReq()
	fixture1, err := CreateWorkflowLoadTestFixture(req)
	if err != nil {
		t.Fatalf("expected no error on first create, got: %v", err)
	}

	fixture2, err := CreateWorkflowLoadTestFixture(req)
	if err != nil {
		t.Fatalf("expected no error on idempotent create, got: %v", err)
	}

	if fixture1.FixtureID != fixture2.FixtureID {
		t.Errorf("expected same fixture ID on idempotent create")
	}
}

func TestCreateWorkflowLoadTestFixture_DuplicateFixtureID(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	// First creation with base request
	req1 := baseLoadTestFixtureReq()
	_, err := CreateWorkflowLoadTestFixture(req1)
	if err != nil {
		t.Fatalf("expected no error on first create, got: %v", err)
	}

	// Second creation with different idempotency key but same fixture ID
	req2 := baseLoadTestFixtureReq()
	req2.IdempotencyKey = "different-key-0248-duplicate-test"
	_, err = CreateWorkflowLoadTestFixture(req2)
	if err == nil {
		t.Fatalf("expected fixture already exists error, got: %v", err)
	}
	// Verify the exact error message for duplicate fixture ID
	if err.Error() != "fixture already exists" {
		t.Fatalf("expected fixture already exists error, got: %v", err)
	}
}

func TestCreateWorkflowLoadTestFixture_ValidationFailure(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	// Create request with missing fixture ID to trigger validation
	req := baseLoadTestFixtureReq()
	req.FixtureID = ""
	_, err := CreateWorkflowLoadTestFixture(req)
	if err == nil {
		t.Fatalf("expected validation error, got nil")
	}
}

func TestGetWorkflowLoadTestFixture_Success(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	// Create a fixture to retrieve in this test
	req := baseLoadTestFixtureReq()
	created, err := CreateWorkflowLoadTestFixture(req)
	if err != nil {
		t.Fatalf("expected no error on create, got: %v", err)
	}
	// Retrieve the load test fixture by its generated ID
	retrieved, err := GetWorkflowLoadTestFixture(created.FixtureID)
	if err != nil {
		t.Fatalf("expected no error on get, got: %v", err)
	}

	if retrieved.FixtureID != created.FixtureID {
		t.Errorf("expected fixture ID %s, got %s", created.FixtureID, retrieved.FixtureID)
	}
}

func TestGetWorkflowLoadTestFixture_EmptyID(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	// Empty ID retrieval attempt
	_, err := GetWorkflowLoadTestFixture("")
	if err == nil {
		t.Fatalf("expected fixture ID required error, got: %v", err)
	}
	// Empty ID check: retrieval must fail with validation error
	if err.Error() != "fixture ID is required" {
		t.Fatalf("expected fixture ID required error, got: %v", err)
	}
}

func TestGetWorkflowLoadTestFixture_NotFound(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	// Query for fixture that doesn't exist in store
	_, err := GetWorkflowLoadTestFixture("fixture-nonexistent")
	if err == nil {
		t.Fatalf("expected fixture not found error, got: %v", err)
	}
	if err.Error() != "fixture not found" {
		t.Fatalf("expected fixture not found error, got: %v", err)
	}
}

func TestUpdateWorkflowLoadTestFixture_Success(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	req := baseLoadTestFixtureReq()
	created, err := CreateWorkflowLoadTestFixture(req)
	if err != nil {
		t.Fatalf("expected no error on create, got: %v", err)
	}

	req.RequestsPerSecond = 200
	updated, err := UpdateWorkflowLoadTestFixture(req)
	if err != nil {
		t.Fatalf("expected no error on update, got: %v", err)
	}

	if updated.RequestsPerSecond != 200 {
		t.Errorf("expected requests per second 200, got %d", updated.RequestsPerSecond)
	}

	if updated.FixtureID != created.FixtureID {
		t.Errorf("expected fixture ID to remain %s, got %s", created.FixtureID, updated.FixtureID)
	}
}

func TestUpdateWorkflowLoadTestFixture_NotFound(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	// Attempt update on fixture that was never created
	req := baseLoadTestFixtureReq()
	req.FixtureID = "fixture-nonexistent"
	_, err := UpdateWorkflowLoadTestFixture(req)
	if err == nil {
		t.Fatalf("expected fixture not found error, got: %v", err)
	}
	// Load test fixture update requires existing fixture
	if err.Error() != "fixture not found" {
		t.Fatalf("expected fixture not found error, got: %v", err)
	}
}

func TestDeleteWorkflowLoadTestFixture_Success(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	// Create a fixture first for successful deletion
	req := baseLoadTestFixtureReq()
	created, err := CreateWorkflowLoadTestFixture(req)
	if err != nil {
		t.Fatalf("expected no error on create, got: %v", err)
	}

	err = DeleteWorkflowLoadTestFixture(created.FixtureID)
	if err != nil {
		t.Fatalf("expected no error on delete, got: %v", err)
	}

	// Verify deletion by attempting retrieval
	_, err = GetWorkflowLoadTestFixture(created.FixtureID)
	if err == nil {
		t.Fatalf("expected fixture not found after delete")
	}
}

func TestDeleteWorkflowLoadTestFixture_EmptyID(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	// Empty fixture ID should be rejected at validation
	err := DeleteWorkflowLoadTestFixture("")
	if err == nil {
		t.Fatalf("expected fixture ID required error, got: %v", err)
	}
	// Deletion operation requires non-empty fixture ID parameter
	if err.Error() != "fixture ID is required" {
		t.Fatalf("expected fixture ID required error, got: %v", err)
	}
}

func TestDeleteWorkflowLoadTestFixture_NotFound(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	// Attempt to delete non-existent load test fixture
	err := DeleteWorkflowLoadTestFixture("fixture-nonexistent")
	if err == nil {
		t.Fatalf("expected fixture not found error, got: %v", err)
	}
	// NotFound test: deletion must fail for non-existent fixture
	if err.Error() != "fixture not found" {
		t.Fatalf("expected fixture not found error, got: %v", err)
	}
}

func TestListWorkflowLoadTestFixtures_Success(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	req1 := baseLoadTestFixtureReq()
	req1.FixtureID = "fixture-load-test-001"
	req1.IdempotencyKey = "test-key-0248-list-001-abcdef"
	_, err := CreateWorkflowLoadTestFixture(req1)
	if err != nil {
		t.Fatalf("expected no error on create 1, got: %v", err)
	}

	req2 := baseLoadTestFixtureReq()
	req2.FixtureID = "fixture-load-test-002"
	req2.IdempotencyKey = "test-key-0248-list-002-ghijkl"
	_, err = CreateWorkflowLoadTestFixture(req2)
	if err != nil {
		t.Fatalf("expected no error on create 2, got: %v", err)
	}

	fixtures, err := ListWorkflowLoadTestFixtures()
	if err != nil {
		t.Fatalf("expected no error on list, got: %v", err)
	}
	// Verify that list operation returns exactly two fixtures from store
	if len(fixtures) != 2 {
		t.Errorf("expected 2 fixtures, got %d", len(fixtures))
	}
}

func TestListWorkflowLoadTestFixtures_Empty(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	fixtures, err := ListWorkflowLoadTestFixtures()
	if err != nil {
		t.Fatalf("expected no error on empty list, got: %v", err)
	}

	if len(fixtures) != 0 {
		t.Errorf("expected 0 fixtures, got %d", len(fixtures))
	}
}

func TestListWorkflowLoadTestFixturesByWorkflow_Success(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	req := baseLoadTestFixtureReq()
	req.WorkflowID = "workflow-synthetic-filter"
	_, err := CreateWorkflowLoadTestFixture(req)
	if err != nil {
		t.Fatalf("expected no error on create, got: %v", err)
	}

	fixtures, err := ListWorkflowLoadTestFixturesByWorkflow("workflow-synthetic-filter")
	if err != nil {
		t.Fatalf("expected no error on list by workflow, got: %v", err)
	}

	if len(fixtures) != 1 {
		t.Errorf("expected 1 fixture, got %d", len(fixtures))
	}
}

func TestGenerateFixtureChecksum_Deterministic(t *testing.T) {
	fixture := &WorkflowLoadTestFixture{
		FixtureID:         "fixture-load-test-001",
		WorkflowID:        "workflow-synthetic-001",
		FixtureType:       "load",
		RequestsPerSecond: 100,
		DurationSeconds:   300,
		ConcurrentUsers:   50,
	}

	// Generate checksums for deterministic fixture
	checksum1 := GenerateFixtureChecksum(fixture)
	checksum2 := GenerateFixtureChecksum(fixture)

	// Checksums must be identical for same input
	if checksum1 != checksum2 {
		t.Fatalf("expected identical checksums for same fixture")
	}
}

func TestGenerateFixtureChecksum_DifferentInputs(t *testing.T) {
	fixture1 := &WorkflowLoadTestFixture{
		FixtureID:         "fixture-load-test-001",
		WorkflowID:        "workflow-synthetic-001",
		FixtureType:       "load",
		RequestsPerSecond: 100,
		DurationSeconds:   300,
		ConcurrentUsers:   50,
	}

	fixture2 := &WorkflowLoadTestFixture{
		FixtureID:         "fixture-load-test-002",
		WorkflowID:        "workflow-synthetic-002",
		FixtureType:       "stress",
		RequestsPerSecond: 200,
		DurationSeconds:   600,
		ConcurrentUsers:   100,
	}

	// Generate checksums for different fixture configurations
	checksum1 := GenerateFixtureChecksum(fixture1)
	checksum2 := GenerateFixtureChecksum(fixture2)

	// Checksums must differ when inputs differ
	if checksum1 == checksum2 {
		t.Fatalf("expected different checksums for different fixtures")
	}
	// Checksums must be deterministic but unique per input
}

func TestCreateWorkflowLoadTestFixture_AllFixtureTypes(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	fixtureTypes := []string{"smoke", "load", "stress", "spike", "soak", "endurance"}

	for i, fixtureType := range fixtureTypes {
		req := baseLoadTestFixtureReq()
		req.FixtureID = fmt.Sprintf("fixture-%s-%03d", fixtureType, i)
		req.IdempotencyKey = fmt.Sprintf("test-key-0248-%s-%03d-xyz", fixtureType, i)
		req.FixtureType = fixtureType

		fixture, err := CreateWorkflowLoadTestFixture(req)
		if err != nil {
			t.Fatalf("expected no error for fixture type %s, got: %v", fixtureType, err)
		}

		if fixture.FixtureType != fixtureType {
			t.Errorf("expected fixture type %s, got %s", fixtureType, fixture.FixtureType)
		}
	}
}

func TestListWorkflowLoadTestFixturesByWorkflow_MultipleMatches(t *testing.T) {
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys = make(map[string]string)

	workflowID := "workflow-synthetic-multi"

	for i := 0; i < 3; i++ {
		req := baseLoadTestFixtureReq()
		req.FixtureID = fmt.Sprintf("fixture-multi-%03d", i)
		req.IdempotencyKey = fmt.Sprintf("multi-key-%d-abcdefgh", i)
		req.WorkflowID = workflowID
		_, err := CreateWorkflowLoadTestFixture(req)
		if err != nil {
			t.Fatalf("expected no error on create %d, got: %v", i, err)
		}
	}

	fixtures, err := ListWorkflowLoadTestFixturesByWorkflow(workflowID)
	if err != nil {
		t.Fatalf("expected no error on list by workflow, got: %v", err)
	}

	if len(fixtures) != 3 {
		t.Errorf("expected 3 fixtures for workflow, got %d", len(fixtures))
	}
}
