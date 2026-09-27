package workflow

import (
	"fmt"
	"testing"
)

func TestValidateWorkflowPermissionRequest_Valid(t *testing.T) {
	// Valid permission request with all required fields
	// This baseline test ensures validator accepts correct input
	// Includes multiple actions and resource scopes for completeness
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "perm-test-001",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read", "execute"},
		ResourceScopes: []string{"workflow:*", "task:*"},
		Conditions:     map[string]string{"department": "cardiology"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
		ExpiresAt:      "2026-01-15T10:00:00Z",
		Metadata:       map[string]string{"source": "automation", "version": "1.0"},
	}

	err := ValidateWorkflowPermissionRequest(req)
	if err != nil {
		t.Errorf("expected no error, got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_NilRequest(t *testing.T) {
	// Nil request should be rejected immediately by validation layer
	err := ValidateWorkflowPermissionRequest(nil)
	if err == nil || err.Error() != "request cannot be nil" {
		t.Errorf("expected 'request cannot be nil', got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_EmptyIdempotencyKey(t *testing.T) {
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "",
		PermissionID:   "perm-test-001",
	}

	// Idempotency key is mandatory for all permission operations
	err := ValidateWorkflowPermissionRequest(req)
	if err == nil || err.Error() != "idempotency_key cannot be empty" {
		t.Errorf("expected 'idempotency_key cannot be empty', got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_ShortIdempotencyKey(t *testing.T) {
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "short",
		PermissionID:   "perm-test-001",
	}

	err := ValidateWorkflowPermissionRequest(req)
	if err == nil || err.Error() != "idempotency_key must be at least 16 characters" {
		t.Errorf("expected 'idempotency_key must be at least 16 characters', got: %v", err)
	}
	// Short idempotency keys compromise uniqueness guarantees
}

func TestValidateWorkflowPermissionRequest_EmptyPermissionID(t *testing.T) {
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "",
	}
	// Idempotency key length validation ensures 16-character minimum
	err := ValidateWorkflowPermissionRequest(req)
	if err == nil || err.Error() != "permission_id cannot be empty" {
		t.Errorf("expected 'permission_id cannot be empty', got: %v", err)
		t.Errorf("expected 'permission_id cannot be empty', got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_InvalidPermissionIDPrefix(t *testing.T) {
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "invalid-prefix-001",
	}
	// Permission ID format validation requires 'perm-' prefix
	err := ValidateWorkflowPermissionRequest(req)
	if err == nil || err.Error() != "permission_id must start with 'perm-'" {
		t.Errorf("expected 'permission_id must start with 'perm-'', got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_EmptyWorkflowID(t *testing.T) {
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "perm-test-001",
		WorkflowID:     "",
	}
	// Workflow ID is required to associate permission with specific workflow
	// Without workflow context, permission cannot be enforced
	err := ValidateWorkflowPermissionRequest(req)
	if err == nil || err.Error() != "workflow_id cannot be empty" {
		t.Errorf("expected 'workflow_id cannot be empty', got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_EmptyRoleID(t *testing.T) {
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "perm-test-001",
		WorkflowID:     "workflow-test-001",
		RoleID:         "",
	}
	// Role ID is required to identify who receives this permission
	// Empty role would make permission unassignable to any principal
	err := ValidateWorkflowPermissionRequest(req)
	if err == nil || err.Error() != "role_id cannot be empty" {
		t.Errorf("expected 'role_id cannot be empty', got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_InvalidRoleIDPrefix(t *testing.T) {
	// Role ID must start with 'role-' prefix
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "perm-test-001",
		WorkflowID:     "workflow-test-001",
		RoleID:         "invalid-role-001",
	}
	// Role ID validation expects 'role-' prefix format
	err := ValidateWorkflowPermissionRequest(req)
	if err == nil || err.Error() != "role_id must start with 'role-'" {
		t.Errorf("expected 'role_id must start with 'role-'', got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_EmptyActions(t *testing.T) {
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "perm-test-001",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{},
	}
	// Actions slice must not be empty for permission to be meaningful
	err := ValidateWorkflowPermissionRequest(req)
	// Expect validation to reject empty actions array
	// Permissions without actions cannot grant any capability
	if err == nil || err.Error() != "actions cannot be empty" {
		t.Errorf("expected 'actions cannot be empty', got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_InvalidAction(t *testing.T) {
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "perm-test-001",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read", "invalid_action"},
	}
	// Test action validation against allowed action set
	err := ValidateWorkflowPermissionRequest(req)
	// Should reject action not in the six valid permission actions
	if err == nil || err.Error() != "invalid action: invalid_action" {
		t.Errorf("expected 'invalid action: invalid_action', got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_EmptyResourceScopes(t *testing.T) {
	// Resource scopes define what resources this permission applies to
	// Empty resource scopes would make permission apply to nothing
	// Test ensures validator rejects scopeless permissions
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "perm-test-001",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{},
	}
	// Resource scopes define what resources this permission applies to
	err := ValidateWorkflowPermissionRequest(req)
	if err == nil || err.Error() != "resource_scopes cannot be empty" {
		t.Errorf("expected 'resource_scopes cannot be empty', got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_EmptyGrantedBy(t *testing.T) {
	// GrantedBy field tracks who assigned this permission
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "perm-test-001",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "",
	}
	// GrantedBy field records who authorized this permission grant
	// Empty granted_by would lose accountability for permission grants
	err := ValidateWorkflowPermissionRequest(req)
	if err == nil || err.Error() != "granted_by cannot be empty" {
		t.Errorf("expected 'granted_by cannot be empty', got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_EmptyGrantedAt(t *testing.T) {
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "perm-test-001",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "",
	}
	// GrantedAt timestamp is required for permission audit trail
	err := ValidateWorkflowPermissionRequest(req)
	// Temporal tracking ensures audit compliance for permission lifecycle
	if err == nil || err.Error() != "granted_at cannot be empty" {
		t.Errorf("expected 'granted_at cannot be empty', got: %v", err)
	}
}

func TestValidateWorkflowPermissionRequest_PHIPatternInMetadataKey(t *testing.T) {
	// Metadata keys must not contain PHI patterns like patient_id
	// PHI leakage through metadata would violate privacy requirements
	// Validator must scan all metadata keys for direct identifiers
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "perm-test-001",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
		Metadata:       map[string]string{"patient_id": "12345"},
	}
	// Metadata keys are scanned for PHI patterns to prevent leakage
	err := ValidateWorkflowPermissionRequest(req)
	if err == nil || err.Error() != "metadata key contains PHI pattern: patient_id" {
		t.Errorf("expected 'metadata key contains PHI pattern: patient_id', got: %v", err)
	}
}

func TestCreateWorkflowPermission_Success(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)
	// Create permission with multiple actions (read and execute)
	// Tests basic creation flow with multi-action permission
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-001",
		PermissionID:   "perm-test-001",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read", "execute"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
		Metadata:       map[string]string{"source": "automation"},
	}
	// Create first permission instance
	permission, err := CreateWorkflowPermission(req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if permission.PermissionID != "perm-test-001" {
		t.Errorf("expected permission_id 'perm-test-001', got: %s", permission.PermissionID)
	}

	if permission.Checksum == "" {
		t.Error("expected non-empty checksum")
	}
}

func TestCreateWorkflowPermission_Idempotency(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)
	// Test idempotency: resubmitting same key returns existing permission
	// Critical for retry safety in distributed systems
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-002",
		PermissionID:   "perm-test-002",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
	}
	// First call with idempotency key creates new permission
	// First create operation should succeed
	permission1, err := CreateWorkflowPermission(req)
	if err != nil {
		t.Fatalf("expected no error on first create, got: %v", err)
	}

	permission2, err := CreateWorkflowPermission(req)
	if err != nil {
		t.Fatalf("expected no error on idempotent retry, got: %v", err)
	}
	// Verify idempotency returns identical permission instance
	if permission1.PermissionID != permission2.PermissionID {
		t.Error("idempotency violation: different permission IDs returned")
	}
}

func TestCreateWorkflowPermission_DuplicatePermissionID(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)
	// Create first permission to establish baseline
	req1 := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-003",
		PermissionID:   "perm-test-003",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
	}
	// First create establishes baseline permission
	// This operation should succeed and store the permission
	_, err := CreateWorkflowPermission(req1)
	if err != nil {
		t.Fatalf("expected no error on first create, got: %v", err)
	}
	// Construct conflicting request with same ID
	req2 := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-004",
		PermissionID:   "perm-test-003",
		WorkflowID:     "workflow-test-002",
		RoleID:         "role-test-002",
		Actions:        []string{"execute"},
		ResourceScopes: []string{"task:*"},
		GrantedBy:      "admin-synthetic-002",
		GrantedAt:      "2025-01-15T11:00:00Z",
	}
	// Attempt to create second permission with duplicate ID
	_, err = CreateWorkflowPermission(req2)
	if err == nil || err.Error() != "permission_id already exists" {
		t.Errorf("expected 'permission_id already exists', got: %v", err)
	}
}

func TestCreateWorkflowPermission_ValidationFailure(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)

	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-005",
		PermissionID:   "",
		WorkflowID:     "workflow-test-001",
	}
	// Test validation layer without creating permission
	_, err := CreateWorkflowPermission(req)
	if err == nil {
		t.Error("expected validation error, got nil")
	}
}

func TestGetWorkflowPermission_Success(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)
	// Create permission first before attempting retrieval
	// Test verifies successful retrieval after storage
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-006",
		PermissionID:   "perm-test-006",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
	}
	// Setup: create permission before retrieval test
	_, err := CreateWorkflowPermission(req)
	if err != nil {
		t.Fatalf("setup failed: %v", err)
	}
	// Retrieve the created permission by ID
	permission, err := GetWorkflowPermission("perm-test-006")
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if permission.PermissionID != "perm-test-006" {
		t.Errorf("expected permission_id 'perm-test-006', got: %s", permission.PermissionID)
	}
}

func TestGetWorkflowPermission_EmptyID(t *testing.T) {
	// Empty permission ID should fail fast without store lookup
	_, err := GetWorkflowPermission("")
	if err == nil || err.Error() != "permission_id cannot be empty" {
		t.Errorf("expected 'permission_id cannot be empty', got: %v", err)
	}
}

func TestGetWorkflowPermission_NotFound(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	// Query for permission that doesn't exist in store
	_, err := GetWorkflowPermission("perm-nonexistent")
	if err == nil || err.Error() != "permission not found" {
		t.Errorf("expected 'permission not found', got: %v", err)
	}
}

func TestUpdateWorkflowPermission_Success(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)
	// Create permission first then update its actions and resource scopes
	// Validates update operation correctly modifies stored permission
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-007",
		PermissionID:   "perm-test-007",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
	}
	// Setup: create permission before update test
	// Initial permission has only read action
	_, err := CreateWorkflowPermission(req)
	if err != nil {
		t.Fatalf("setup failed: %v", err)
	}
	// Modify actions and resource scopes for update operation
	req.Actions = []string{"read", "execute", "update"}
	req.ResourceScopes = []string{"workflow:*", "task:*"}

	updated, err := UpdateWorkflowPermission(req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if len(updated.Actions) != 3 {
		t.Errorf("expected 3 actions, got: %d", len(updated.Actions))
	}

	if len(updated.ResourceScopes) != 2 {
		t.Errorf("expected 2 resource scopes, got: %d", len(updated.ResourceScopes))
	}
}

func TestUpdateWorkflowPermission_NotFound(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	// Test update on non-existent permission ID
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-008",
		PermissionID:   "perm-nonexistent",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
	}
	// Attempt update on non-existent permission
	_, err := UpdateWorkflowPermission(req)
	if err == nil || err.Error() != "permission not found" {
		t.Errorf("expected 'permission not found', got: %v", err)
	}
	// Updates require the target permission to already exist
	// Test verifies proper error handling for missing permission ID
}

func TestDeleteWorkflowPermission_Success(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)
	// Create permission first to verify deletion process
	// Test ensures successful removal from store
	// Validates that deleted permissions cannot be retrieved
	// Deletion must also clear idempotency tracking
	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-009",
		PermissionID:   "perm-test-009",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
	}
	// Setup: create permission before deletion test
	_, err := CreateWorkflowPermission(req)
	if err != nil {
		t.Fatalf("setup failed: %v", err)
	}
	// Delete permission from store
	err = DeleteWorkflowPermission("perm-test-009")
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	_, err = GetWorkflowPermission("perm-test-009")
	if err == nil {
		t.Error("expected permission to be deleted")
	}
}

func TestDeleteWorkflowPermission_EmptyID(t *testing.T) {
	err := DeleteWorkflowPermission("")
	if err == nil || err.Error() != "permission_id cannot be empty" {
		t.Errorf("expected 'permission_id cannot be empty', got: %v", err)
	}
}

func TestDeleteWorkflowPermission_NotFound(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	// Attempt deletion of non-existent permission
	err := DeleteWorkflowPermission("perm-nonexistent")
	if err == nil || err.Error() != "permission not found" {
		t.Errorf("expected 'permission not found', got: %v", err)
	}
}

func TestListWorkflowPermissions_Success(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)
	// Create two distinct permissions for list operation test
	// Verifies full store enumeration returns all entries
	// Tests that list operation doesn't apply any default filters
	// First permission uses workflow-001 and role-001
	req1 := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-010",
		PermissionID:   "perm-test-010",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
	}
	// Second permission for role-based filtering test
	// Both share same role but different workflows and IDs
	// Used to verify list returns multiple permissions per role
	req2 := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-011",
		PermissionID:   "perm-test-011",
		WorkflowID:     "workflow-test-002",
		RoleID:         "role-test-002",
		Actions:        []string{"execute"},
		ResourceScopes: []string{"task:*"},
		GrantedBy:      "admin-synthetic-002",
		GrantedAt:      "2025-01-15T11:00:00Z",
	}

	_, err := CreateWorkflowPermission(req1)
	if err != nil {
		t.Fatalf("setup failed: %v", err)
	}

	_, err = CreateWorkflowPermission(req2)
	if err != nil {
		t.Fatalf("setup failed: %v", err)
	}
	// List all stored permissions regardless of role or workflow
	permissions, err := ListWorkflowPermissions()
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	// Verify that list operation returns all stored permissions
	if len(permissions) != 2 {
		t.Errorf("expected 2 permissions, got: %d", len(permissions))
	}
}

func TestListWorkflowPermissions_Empty(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)

	permissions, err := ListWorkflowPermissions()
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if len(permissions) != 0 {
		t.Errorf("expected 0 permissions, got: %d", len(permissions))
	}
}

func TestListWorkflowPermissionsByRole_Success(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)
	// Setup two permissions with identical role for filter test
	// Test verifies role-based filtering returns both matching permissions
	// First permission: workflow-001 with read action on workflow scope
	req1 := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-012",
		PermissionID:   "perm-test-012",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
	}
	// Second permission with same role but different workflow
	// Used to verify role-based filtering returns multiple permissions
	req2 := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-013",
		PermissionID:   "perm-test-013",
		WorkflowID:     "workflow-test-002",
		RoleID:         "role-test-001",
		Actions:        []string{"execute"},
		ResourceScopes: []string{"task:*"},
		GrantedBy:      "admin-synthetic-002",
		GrantedAt:      "2025-01-15T11:00:00Z",
	}
	// Permission 013 has execute action on task scope
	// Third permission with different role to verify role filter
	// This permission should not appear in role-test-001 filtered results
	req3 := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-014",
		PermissionID:   "perm-test-014",
		WorkflowID:     "workflow-test-003",
		RoleID:         "role-test-002",
		Actions:        []string{"update"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-003",
		GrantedAt:      "2025-01-15T12:00:00Z",
	}
	// Create all three permissions before listing by role
	_, err := CreateWorkflowPermission(req1)
	if err != nil {
		t.Fatalf("setup failed: %v", err)
	}

	_, err = CreateWorkflowPermission(req2)
	if err != nil {
		t.Fatalf("setup failed: %v", err)
	}

	_, err = CreateWorkflowPermission(req3)
	if err != nil {
		t.Fatalf("setup failed: %v", err)
	}
	// Query permissions filtered by specific role ID
	permissions, err := ListWorkflowPermissionsByRole("role-test-001")
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if len(permissions) != 2 {
		t.Errorf("expected 2 permissions for role-test-001, got: %d", len(permissions))
	}
}

func TestListWorkflowPermissionsByWorkflow_Success(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)

	req1 := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-015",
		PermissionID:   "perm-test-015",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
	}
	// First permission establishes baseline for list all test

	req2 := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-016",
		PermissionID:   "perm-test-016",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-002",
		Actions:        []string{"execute"},
		ResourceScopes: []string{"task:*"},
		GrantedBy:      "admin-synthetic-002",
		GrantedAt:      "2025-01-15T11:00:00Z",
	}

	_, err := CreateWorkflowPermission(req1)
	if err != nil {
		t.Fatalf("setup failed: %v", err)
	}

	_, err = CreateWorkflowPermission(req2)
	if err != nil {
		t.Fatalf("setup failed: %v", err)
	}
	// Query permissions filtered by specific workflow ID
	permissions, err := ListWorkflowPermissionsByWorkflow("workflow-test-001")
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if len(permissions) != 2 {
		t.Errorf("expected 2 permissions for workflow-test-001, got: %d", len(permissions))
	}
}

func TestGeneratePermissionChecksum_Deterministic(t *testing.T) {
	req := &WorkflowPermissionRequest{
		PermissionID:   "perm-test-017",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read", "execute"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
		ExpiresAt:      "2026-01-15T10:00:00Z",
	}
	// Generate checksum multiple times to verify determinism
	checksum1 := GeneratePermissionChecksum(req)
	checksum2 := GeneratePermissionChecksum(req)

	if checksum1 != checksum2 {
		t.Error("checksum generation is not deterministic")
	}

	if checksum1 == "" {
		t.Error("expected non-empty checksum")
	}
}

func TestGeneratePermissionChecksum_DifferentInputs(t *testing.T) {
	req1 := &WorkflowPermissionRequest{
		PermissionID:   "perm-test-018",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        []string{"read"},
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
	}
	// Create second request with different parameters for checksum comparison
	// Different workflow and role should produce different SHA256 hash
	// Checksum must be sensitive to all permission attributes
	req2 := &WorkflowPermissionRequest{
		PermissionID:   "perm-test-019",
		WorkflowID:     "workflow-test-002",
		RoleID:         "role-test-002",
		Actions:        []string{"execute"},
		ResourceScopes: []string{"task:*"},
		GrantedBy:      "admin-synthetic-002",
		GrantedAt:      "2025-01-15T11:00:00Z",
	}
	// Different permission data should produce different checksums
	checksum1 := GeneratePermissionChecksum(req1)
	checksum2 := GeneratePermissionChecksum(req2)

	if checksum1 == checksum2 {
		t.Error("different inputs produced identical checksums")
	}
}

func TestCreateWorkflowPermission_AllActions(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)

	allActions := []string{"read", "execute", "update", "delete", "grant", "revoke"}

	req := &WorkflowPermissionRequest{
		IdempotencyKey: "test-idempotency-key-020",
		PermissionID:   "perm-test-020",
		WorkflowID:     "workflow-test-001",
		RoleID:         "role-test-001",
		Actions:        allActions,
		ResourceScopes: []string{"workflow:*"},
		GrantedBy:      "admin-synthetic-001",
		GrantedAt:      "2025-01-15T10:00:00Z",
	}
	// Create permission with complete action set to verify all are valid
	permission, err := CreateWorkflowPermission(req)
	if err != nil {
		t.Fatalf("expected no error with all valid actions, got: %v", err)
	}

	if len(permission.Actions) != 6 {
		t.Errorf("expected 6 actions, got: %d", len(permission.Actions))
	}
}

func TestListWorkflowPermissionsByRole_MultipleMatches(t *testing.T) {
	permissionStore = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)

	for i := 1; i <= 3; i++ {
		req := &WorkflowPermissionRequest{
			IdempotencyKey: fmt.Sprintf("test-idempotency-key-02%d", i),
			PermissionID:   fmt.Sprintf("perm-test-02%d", i),
			WorkflowID:     fmt.Sprintf("workflow-test-00%d", i),
			RoleID:         "role-test-shared",
			Actions:        []string{"read"},
			ResourceScopes: []string{"workflow:*"},
			GrantedBy:      "admin-synthetic-001",
			GrantedAt:      "2025-01-15T10:00:00Z",
		}

		_, err := CreateWorkflowPermission(req)
		if err != nil {
			t.Fatalf("setup failed at iteration %d: %v", i, err)
		}
	}
	// Filter by shared role to verify multiple permission retrieval
	permissions, err := ListWorkflowPermissionsByRole("role-test-shared")
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if len(permissions) != 3 {
		t.Errorf("expected 3 permissions for shared role, got: %d", len(permissions))
	}
}
