package workflow

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
)

// WorkflowPermission represents a permission rule for workflow operations.
type WorkflowPermission struct {
	PermissionID   string            `json:"permission_id"`
	WorkflowID     string            `json:"workflow_id"`
	RoleID         string            `json:"role_id"`
	Actions        []string          `json:"actions"`
	ResourceScopes []string          `json:"resource_scopes"`
	Conditions     map[string]string `json:"conditions"`
	GrantedBy      string            `json:"granted_by"`
	GrantedAt      string            `json:"granted_at"`
	ExpiresAt      string            `json:"expires_at"`
	Metadata       map[string]string `json:"metadata"`
	Checksum       string            `json:"checksum"`
}

// WorkflowPermissionRequest represents a request to create or update a workflow permission.
type WorkflowPermissionRequest struct {
	IdempotencyKey string            `json:"idempotency_key"`
	PermissionID   string            `json:"permission_id"`
	WorkflowID     string            `json:"workflow_id"`
	RoleID         string            `json:"role_id"`
	Actions        []string          `json:"actions"`
	ResourceScopes []string          `json:"resource_scopes"`
	Conditions     map[string]string `json:"conditions"`
	GrantedBy      string            `json:"granted_by"`
	GrantedAt      string            `json:"granted_at"`
	ExpiresAt      string            `json:"expires_at"`
	Metadata       map[string]string `json:"metadata"`
}

var (
	permissionStore           = make(map[string]*WorkflowPermission)
	permissionIdempotencyKeys = make(map[string]string)
)

var validActions = map[string]bool{
	"read":    true,
	"execute": true,
	"update":  true,
	"delete":  true,
	"grant":   true,
	"revoke":  true,
}

// CreateWorkflowPermission creates a new workflow permission with idempotency support.
func CreateWorkflowPermission(req *WorkflowPermissionRequest) (*WorkflowPermission, error) {
	if err := ValidateWorkflowPermissionRequest(req); err != nil {
		return nil, err
	}

	if existingID, found := permissionIdempotencyKeys[req.IdempotencyKey]; found {
		return permissionStore[existingID], nil
	}

	if _, exists := permissionStore[req.PermissionID]; exists {
		return nil, errors.New("permission_id already exists")
	}

	checksum := GeneratePermissionChecksum(req)

	permission := &WorkflowPermission{
		PermissionID:   req.PermissionID,
		WorkflowID:     req.WorkflowID,
		RoleID:         req.RoleID,
		Actions:        req.Actions,
		ResourceScopes: req.ResourceScopes,
		Conditions:     req.Conditions,
		GrantedBy:      req.GrantedBy,
		GrantedAt:      req.GrantedAt,
		ExpiresAt:      req.ExpiresAt,
		Metadata:       req.Metadata,
		Checksum:       checksum,
	}

	// Store permission and register idempotency key
	permissionStore[req.PermissionID] = permission
	permissionIdempotencyKeys[req.IdempotencyKey] = req.PermissionID

	return permission, nil
}

// GetWorkflowPermission retrieves a workflow permission by ID.
func GetWorkflowPermission(permissionID string) (*WorkflowPermission, error) {
	if permissionID == "" {
		return nil, errors.New("permission_id cannot be empty")
	}

	permission, exists := permissionStore[permissionID]
	if !exists {
		return nil, errors.New("permission not found")
	}

	return permission, nil
}

// UpdateWorkflowPermission updates an existing workflow permission.
func UpdateWorkflowPermission(req *WorkflowPermissionRequest) (*WorkflowPermission, error) {
	if err := ValidateWorkflowPermissionRequest(req); err != nil {
		return nil, err
	}

	permission, exists := permissionStore[req.PermissionID]
	if !exists {
		return nil, errors.New("permission not found")
	}

	// Recalculate checksum after permission update
	checksum := GeneratePermissionChecksum(req)

	permission.WorkflowID = req.WorkflowID
	permission.RoleID = req.RoleID
	permission.Actions = req.Actions
	permission.ResourceScopes = req.ResourceScopes
	permission.Conditions = req.Conditions
	permission.GrantedBy = req.GrantedBy
	permission.GrantedAt = req.GrantedAt
	permission.ExpiresAt = req.ExpiresAt
	permission.Metadata = req.Metadata
	permission.Checksum = checksum

	return permission, nil
}

// DeleteWorkflowPermission removes a workflow permission by ID.
func DeleteWorkflowPermission(permissionID string) error {
	if permissionID == "" {
		return errors.New("permission_id cannot be empty")
	}

	if _, exists := permissionStore[permissionID]; !exists {
		return errors.New("permission not found")
	}

	delete(permissionStore, permissionID)
	return nil
}

// ListWorkflowPermissions returns all workflow permissions.
func ListWorkflowPermissions() ([]*WorkflowPermission, error) {
	permissions := make([]*WorkflowPermission, 0, len(permissionStore))
	for _, permission := range permissionStore {
		permissions = append(permissions, permission)
	}
	return permissions, nil
}

// ListWorkflowPermissionsByRole returns permissions for a specific role.
func ListWorkflowPermissionsByRole(roleID string) ([]*WorkflowPermission, error) {
	permissions := make([]*WorkflowPermission, 0)
	for _, permission := range permissionStore {
		if permission.RoleID == roleID {
			permissions = append(permissions, permission)
		}
	}
	return permissions, nil
}

// ListWorkflowPermissionsByWorkflow returns permissions for a specific workflow.
func ListWorkflowPermissionsByWorkflow(workflowID string) ([]*WorkflowPermission, error) {
	permissions := make([]*WorkflowPermission, 0)
	for _, permission := range permissionStore {
		if permission.WorkflowID == workflowID {
			permissions = append(permissions, permission)
		}
	}
	return permissions, nil
}

// ValidateWorkflowPermissionRequest validates the workflow permission request.
func ValidateWorkflowPermissionRequest(req *WorkflowPermissionRequest) error {
	if req == nil {
		return errors.New("request cannot be nil")
	}

	if req.IdempotencyKey == "" {
		return errors.New("idempotency_key cannot be empty")
	}

	if len(req.IdempotencyKey) < 16 {
		return errors.New("idempotency_key must be at least 16 characters")
	}

	if req.PermissionID == "" {
		return errors.New("permission_id cannot be empty")
	}

	if !strings.HasPrefix(req.PermissionID, "perm-") {
		return errors.New("permission_id must start with 'perm-'")
	}

	if req.WorkflowID == "" {
		return errors.New("workflow_id cannot be empty")
	}

	if req.RoleID == "" {
		return errors.New("role_id cannot be empty")
	}

	if !strings.HasPrefix(req.RoleID, "role-") {
		return errors.New("role_id must start with 'role-'")
	}

	if len(req.Actions) == 0 {
		return errors.New("actions cannot be empty")
	}

	for _, action := range req.Actions {
		if !validActions[action] {
			return fmt.Errorf("invalid action: %s", action)
		}
	}

	if len(req.ResourceScopes) == 0 {
		return errors.New("resource_scopes cannot be empty")
	}

	if req.GrantedBy == "" {
		return errors.New("granted_by cannot be empty")
	}

	if req.GrantedAt == "" {
		return errors.New("granted_at cannot be empty")
	}

	for key := range req.Metadata {
		lowerKey := strings.ToLower(key)
		if strings.Contains(lowerKey, "name") || strings.Contains(lowerKey, "patient") ||
			strings.Contains(lowerKey, "phone") || strings.Contains(lowerKey, "address") {
			return fmt.Errorf("metadata key contains PHI pattern: %s", key)
		}
	}

	return nil
}

// GeneratePermissionChecksum generates a SHA256 checksum for the permission.
func GeneratePermissionChecksum(req *WorkflowPermissionRequest) string {
	data := fmt.Sprintf("%s|%s|%s|%s|%s|%s|%s|%s",
		req.PermissionID,
		req.WorkflowID,
		req.RoleID,
		strings.Join(req.Actions, ","),
		strings.Join(req.ResourceScopes, ","),
		req.GrantedBy,
		req.GrantedAt,
		req.ExpiresAt,
	)
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}
