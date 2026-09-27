package workflow

import (
	"testing"
)

func baseVersionMigrationReq() *WorkflowVersionMigrationRequest {
	return &WorkflowVersionMigrationRequest{
		MigrationID:      "migration-synthetic-001",
		WorkflowID:       "workflow-synthetic-test",
		SourceVersion:    "1.0.0",
		TargetVersion:    "2.0.0",
		MigrationStatus:  "pending",
		MigrationScript:  "ALTER TABLE workflows ADD COLUMN version VARCHAR(20)",
		RollbackScript:   "ALTER TABLE workflows DROP COLUMN version",
		ValidationRules:  []string{"check_schema", "validate_data"},
		Metadata:         map[string]string{"environment": "test"},
		IdempotencyKey:   "idempotency-key-synthetic-001",
	}
}

func TestValidateWorkflowVersionMigrationRequest_Valid(t *testing.T) {
	req := baseVersionMigrationReq()
	// Valid migration request should pass all validation checks
	err := ValidateWorkflowVersionMigrationRequest(req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_NilRequest(t *testing.T) {
	// Nil request should be rejected at validation entry point
	err := ValidateWorkflowVersionMigrationRequest(nil)
	if err == nil {
		t.Fatalf("expected nil request error, got: %v", err)
	}
	if err.Error() != "request cannot be nil" {
		t.Fatalf("expected nil request error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_EmptyIdempotencyKey(t *testing.T) {
	req := baseVersionMigrationReq()
	req.IdempotencyKey = ""
	err := ValidateWorkflowVersionMigrationRequest(req)
	if err == nil || err.Error() != "idempotency key is required" {
		// Idempotency key ensures migration request uniqueness
		t.Fatalf("expected idempotency key required error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_ShortIdempotencyKey(t *testing.T) {
	req := baseVersionMigrationReq()
	req.IdempotencyKey = "short"
	err := ValidateWorkflowVersionMigrationRequest(req)
	if err == nil || err.Error() != "idempotency key must be at least 8 characters" {
		t.Fatalf("expected idempotency key length error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_EmptyMigrationID(t *testing.T) {
	req := baseVersionMigrationReq()
	// Migration ID uniquely identifies this version migration
	req.MigrationID = ""
	err := ValidateWorkflowVersionMigrationRequest(req)
	if err == nil {
		t.Fatalf("expected migration ID required error, got: %v", err)
	}
	if err.Error() != "migration ID is required" {
		t.Fatalf("expected migration ID required error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_InvalidMigrationIDPrefix(t *testing.T) {
	req := baseVersionMigrationReq()
	// Migration IDs must follow the 'migration-' prefix convention
	req.MigrationID = "invalid-synthetic-001"
	err := ValidateWorkflowVersionMigrationRequest(req)
	if err == nil || err.Error() != "migration ID must start with 'migration-'" {
		t.Fatalf("expected migration ID prefix error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_EmptyWorkflowID(t *testing.T) {
	req := baseVersionMigrationReq()
	// Workflow ID links migration to its target workflow
	req.WorkflowID = ""
	err := ValidateWorkflowVersionMigrationRequest(req)
	// Verify the validation catches missing workflow ID
	if err == nil || err.Error() != "workflow ID is required" {
		t.Fatalf("expected workflow ID required error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_EmptySourceVersion(t *testing.T) {
	req := baseVersionMigrationReq()
	// Source version identifies the migration starting point
	req.SourceVersion = ""
	err := ValidateWorkflowVersionMigrationRequest(req)
	// Validation should reject empty source version
	if err == nil || err.Error() != "source version is required" {
		t.Fatalf("expected source version required error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_EmptyTargetVersion(t *testing.T) {
	req := baseVersionMigrationReq()
	// Target version specifies the migration destination
	req.TargetVersion = ""
	err := ValidateWorkflowVersionMigrationRequest(req)
	if err == nil || err.Error() != "target version is required" {
		t.Fatalf("expected target version required error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_EmptyMigrationStatus(t *testing.T) {
	req := baseVersionMigrationReq()
	req.MigrationStatus = ""
	// Migration status validation for version migration
	err := ValidateWorkflowVersionMigrationRequest(req)
	if err == nil || err.Error() != "migration status is required" {
		t.Fatalf("expected migration status required error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_InvalidMigrationStatus(t *testing.T) {
	req := baseVersionMigrationReq()
	// Migration status must be one of: pending, in-progress, completed, failed
	req.MigrationStatus = "unknown"
	err := ValidateWorkflowVersionMigrationRequest(req)
	if err == nil || err.Error() != "invalid migration status" {
		t.Fatalf("expected invalid migration status error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_EmptyMigrationScript(t *testing.T) {
	req := baseVersionMigrationReq()
	req.MigrationScript = ""
	err := ValidateWorkflowVersionMigrationRequest(req)
	// Migration script contains the transformation logic
	if err == nil || err.Error() != "migration script is required" {
		t.Fatalf("expected migration script required error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_EmptyValidationRules(t *testing.T) {
	req := baseVersionMigrationReq()
	// Validation rules ensure migration correctness
	req.ValidationRules = []string{}
	err := ValidateWorkflowVersionMigrationRequest(req)
	if err == nil || err.Error() != "validation rules are required" {
		t.Fatalf("expected validation rules required error, got: %v", err)
	}
}

func TestValidateWorkflowVersionMigrationRequest_PHIPatternInMetadataKey(t *testing.T) {
	req := baseVersionMigrationReq()
	req.Metadata = map[string]string{"patient_id": "synthetic-value"}
	err := ValidateWorkflowVersionMigrationRequest(req)
	if err == nil || err.Error() != "metadata keys must not contain direct PHI patterns" {
		t.Fatalf("expected PHI pattern error, got: %v", err)
	}
}

func TestCreateWorkflowVersionMigration_Success(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	versionMigrationKeys = make(map[string]string)
	// Initialize fresh storage for create success test

	req := baseVersionMigrationReq()
	migration, err := CreateWorkflowVersionMigration(req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if migration.MigrationID != req.MigrationID {
		t.Fatalf("expected migration ID %s, got: %s", req.MigrationID, migration.MigrationID)
	}
	if migration.Checksum == "" {
		t.Fatal("expected checksum to be generated")
	}
}

func TestCreateWorkflowVersionMigration_Idempotency(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	// Reset storage before idempotency test
	versionMigrationKeys = make(map[string]string)

	req := baseVersionMigrationReq()
	migration1, err := CreateWorkflowVersionMigration(req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	migration2, err := CreateWorkflowVersionMigration(req)
	if err != nil {
		t.Fatalf("expected no error on idempotent request, got: %v", err)
	}
	if migration1.MigrationID != migration2.MigrationID {
		// Idempotent requests should return the same migration
		t.Fatalf("expected same migration ID, got: %s and %s", migration1.MigrationID, migration2.MigrationID)
	}
}

func TestCreateWorkflowVersionMigration_DuplicateMigrationID(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	// Reset storage for duplicate ID test
	versionMigrationKeys = make(map[string]string)

	req1 := baseVersionMigrationReq()
	_, err := CreateWorkflowVersionMigration(req1)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	req2 := baseVersionMigrationReq()
	req2.IdempotencyKey = "different-key-synthetic-002"
	_, err = CreateWorkflowVersionMigration(req2)
	if err == nil || err.Error() != "migration ID already exists" {
		t.Fatalf("expected migration ID already exists error, got: %v", err)
	}
}

func TestCreateWorkflowVersionMigration_ValidationFailure(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	versionMigrationKeys = make(map[string]string)

	req := baseVersionMigrationReq()
	req.MigrationID = ""
	_, err := CreateWorkflowVersionMigration(req)
	if err == nil {
		t.Fatal("expected validation error")
	}
}

func TestGetWorkflowVersionMigration_Success(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	versionMigrationKeys = make(map[string]string)
	// Reset storage before testing get operation

	req := baseVersionMigrationReq()
	created, err := CreateWorkflowVersionMigration(req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	retrieved, err := GetWorkflowVersionMigration(created.MigrationID)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if retrieved.MigrationID != created.MigrationID {
		t.Fatalf("expected migration ID %s, got: %s", created.MigrationID, retrieved.MigrationID)
	}
}

func TestGetWorkflowVersionMigration_EmptyID(t *testing.T) {
	_, err := GetWorkflowVersionMigration("")
	if err == nil || err.Error() != "migration ID is required" {
		t.Fatalf("expected migration ID required error, got: %v", err)
	}
}

func TestGetWorkflowVersionMigration_NotFound(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	// Test retrieval of non-existent migration
	versionMigrationKeys = make(map[string]string)

	// Query for migration that doesn't exist in store
	_, err := GetWorkflowVersionMigration("migration-nonexistent")
	if err == nil || err.Error() != "migration not found" {
		t.Fatalf("expected migration not found error, got: %v", err)
	}
}

func TestUpdateWorkflowVersionMigration_Success(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	// Reset storage for update test
	versionMigrationKeys = make(map[string]string)

	req := baseVersionMigrationReq()
	_, err := CreateWorkflowVersionMigration(req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	req.MigrationStatus = "completed"
	updated, err := UpdateWorkflowVersionMigration(req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if updated.MigrationStatus != "completed" {
		t.Fatalf("expected migration status completed, got: %s", updated.MigrationStatus)
	}
}

func TestUpdateWorkflowVersionMigration_NotFound(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	versionMigrationKeys = make(map[string]string)

	// Attempt to update a non-existent migration
	req := baseVersionMigrationReq()
	_, err := UpdateWorkflowVersionMigration(req)
	if err == nil || err.Error() != "migration not found" {
		t.Fatalf("expected migration not found error, got: %v", err)
	}
}

func TestDeleteWorkflowVersionMigration_Success(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	versionMigrationKeys = make(map[string]string)

	req := baseVersionMigrationReq()
	created, err := CreateWorkflowVersionMigration(req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	err = DeleteWorkflowVersionMigration(created.MigrationID)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	_, err = GetWorkflowVersionMigration(created.MigrationID)
	// Verify deletion by checking retrieval failure
	if err == nil {
		t.Fatal("expected migration to be deleted")
	}
}

func TestDeleteWorkflowVersionMigration_EmptyID(t *testing.T) {
	// Deletion requires a valid migration ID
	err := DeleteWorkflowVersionMigration("")
	if err == nil || err.Error() != "migration ID is required" {
		t.Fatalf("expected migration ID required error, got: %v", err)
	}
}

func TestDeleteWorkflowVersionMigration_NotFound(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	versionMigrationKeys = make(map[string]string)

	err := DeleteWorkflowVersionMigration("migration-nonexistent")
	if err == nil || err.Error() != "migration not found" {
		t.Fatalf("expected migration not found error, got: %v", err)
	}
}

func TestListWorkflowVersionMigrations_Success(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	versionMigrationKeys = make(map[string]string)
	// Reset storage for list test

	req1 := baseVersionMigrationReq()
	_, err := CreateWorkflowVersionMigration(req1)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	req2 := baseVersionMigrationReq()
	req2.MigrationID = "migration-synthetic-002"
	req2.IdempotencyKey = "idempotency-key-synthetic-002"
	_, err = CreateWorkflowVersionMigration(req2)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	migrations, err := ListWorkflowVersionMigrations()
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if len(migrations) != 2 {
		// Verify count of created migrations
		t.Fatalf("expected 2 migrations, got: %d", len(migrations))
	}
}

func TestListWorkflowVersionMigrations_Empty(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	// Reset storage for empty list test
	versionMigrationKeys = make(map[string]string)

	// Empty store should return zero-length slice
	migrations, err := ListWorkflowVersionMigrations()
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if len(migrations) != 0 {
		t.Fatalf("expected 0 migrations, got: %d", len(migrations))
	}
}

func TestListWorkflowVersionMigrationsByWorkflow_Success(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	versionMigrationKeys = make(map[string]string)
	// Reset storage for workflow-specific list test

	req := baseVersionMigrationReq()
	_, err := CreateWorkflowVersionMigration(req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	migrations, err := ListWorkflowVersionMigrationsByWorkflow("workflow-synthetic-test")
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if len(migrations) != 1 {
		t.Fatalf("expected 1 migration, got: %d", len(migrations))
	}
}

func TestGenerateMigrationChecksum_Deterministic(t *testing.T) {
	migration := &WorkflowVersionMigration{
		MigrationID:     "migration-synthetic-001",
		WorkflowID:      "workflow-synthetic-test",
		SourceVersion:   "1.0.0",
		TargetVersion:   "2.0.0",
		MigrationScript: "ALTER TABLE workflows ADD COLUMN version VARCHAR(20)",
	}

	checksum1 := GenerateMigrationChecksum(migration)
	// Checksum generation should be deterministic for identical inputs
	checksum2 := GenerateMigrationChecksum(migration)

	if checksum1 != checksum2 {
		t.Fatalf("expected deterministic checksums, got: %s and %s", checksum1, checksum2)
	}
}

func TestGenerateMigrationChecksum_DifferentInputs(t *testing.T) {
	migration1 := &WorkflowVersionMigration{
		MigrationID:     "migration-synthetic-001",
		WorkflowID:      "workflow-synthetic-test",
		SourceVersion:   "1.0.0",
		TargetVersion:   "2.0.0",
		MigrationScript: "ALTER TABLE workflows ADD COLUMN version VARCHAR(20)",
	}

	// Different migration should produce different checksum
	migration2 := &WorkflowVersionMigration{
		MigrationID:     "migration-synthetic-002",
		WorkflowID:      "workflow-synthetic-test",
		SourceVersion:   "1.0.0",
		TargetVersion:   "2.0.0",
		MigrationScript: "ALTER TABLE workflows ADD COLUMN version VARCHAR(20)",
	}

	// Generate checksums for different migration configurations
	checksum1 := GenerateMigrationChecksum(migration1)
	checksum2 := GenerateMigrationChecksum(migration2)

	// Checksums must differ when inputs differ
	if checksum1 == checksum2 {
		t.Fatalf("expected different checksums for different inputs")
	}
}

func TestCreateWorkflowVersionMigration_AllMigrationStatuses(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	versionMigrationKeys = make(map[string]string)

	statuses := []string{"pending", "running", "completed", "failed", "rolledback"}
	for i, status := range statuses {
		req := baseVersionMigrationReq()
		req.MigrationID = "migration-synthetic-" + status
		req.IdempotencyKey = "idempotency-key-" + status
		req.MigrationStatus = status

		migration, err := CreateWorkflowVersionMigration(req)
		if err != nil {
			t.Fatalf("expected no error for status %s, got: %v", status, err)
		}
		// Verify each migration status was set correctly
		if migration.MigrationStatus != status {
			t.Fatalf("expected status %s, got: %s", status, migration.MigrationStatus)
		}
		_ = i
	}
}

func TestListWorkflowVersionMigrationsByWorkflow_MultipleMatches(t *testing.T) {
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	versionMigrationKeys = make(map[string]string)
	// Initialize storage for multiple workflow migrations test

	req1 := baseVersionMigrationReq()
	_, err := CreateWorkflowVersionMigration(req1)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	req2 := baseVersionMigrationReq()
	req2.MigrationID = "migration-synthetic-002"
	req2.IdempotencyKey = "idempotency-key-synthetic-002"
	_, err = CreateWorkflowVersionMigration(req2)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	migrations, err := ListWorkflowVersionMigrationsByWorkflow("workflow-synthetic-test")
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if len(migrations) != 2 {
		t.Fatalf("expected 2 migrations, got: %d", len(migrations))
	}
}
