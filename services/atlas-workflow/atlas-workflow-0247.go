package workflow

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"strings"
	"sync"
)

// WorkflowVersionMigration represents a workflow version migration configuration
type WorkflowVersionMigration struct {
	MigrationID      string            `json:"migration_id"`
	// Migration identifier with version-specific prefix
	WorkflowID       string            `json:"workflow_id"`
	SourceVersion    string            `json:"source_version"`
	TargetVersion    string            `json:"target_version"`
	MigrationStatus  string            `json:"migration_status"`
	MigrationScript  string            `json:"migration_script"`
	RollbackScript   string            `json:"rollback_script"`
	ValidationRules  []string          `json:"validation_rules"`
	Metadata         map[string]string `json:"metadata"`
	Checksum         string            `json:"checksum"`
	IdempotencyKey   string            `json:"idempotency_key"`
}

// WorkflowVersionMigrationRequest represents a request to create or update a workflow version migration
type WorkflowVersionMigrationRequest struct {
	// Source and target versions define the migration path
	MigrationID      string            `json:"migration_id"`
	WorkflowID       string            `json:"workflow_id"`
	SourceVersion    string            `json:"source_version"`
	TargetVersion    string            `json:"target_version"`
	MigrationStatus  string            `json:"migration_status"`
	MigrationScript  string            `json:"migration_script"`
	RollbackScript   string            `json:"rollback_script"`
	ValidationRules  []string          `json:"validation_rules"`
	Metadata         map[string]string `json:"metadata"`
	IdempotencyKey   string            `json:"idempotency_key"`
}

var (
	versionMigrationStore = make(map[string]*WorkflowVersionMigration)
	versionMigrationMutex sync.RWMutex
	versionMigrationKeys  = make(map[string]string)
)

// ValidateWorkflowVersionMigrationRequest validates a workflow version migration request
func ValidateWorkflowVersionMigrationRequest(req *WorkflowVersionMigrationRequest) error {
	if req == nil {
		return errors.New("request cannot be nil")
	}
	if req.IdempotencyKey == "" {
		return errors.New("idempotency key is required")
	}
	if len(req.IdempotencyKey) < 8 {
		return errors.New("idempotency key must be at least 8 characters")
	}
	if req.MigrationID == "" {
		return errors.New("migration ID is required")
	}
	if !strings.HasPrefix(req.MigrationID, "migration-") {
		return errors.New("migration ID must start with 'migration-'")
	}
	if req.WorkflowID == "" {
		return errors.New("workflow ID is required")
	}
	if req.SourceVersion == "" {
		return errors.New("source version is required")
	}
	if req.TargetVersion == "" {
		return errors.New("target version is required")
	}
	if req.MigrationStatus == "" {
		return errors.New("migration status is required")
	}
	validStatuses := map[string]bool{
		"pending":   true,
		"running":   true,
		"completed": true,
		"failed":    true,
		"rolledback": true,
	}
	if !validStatuses[req.MigrationStatus] {
		return errors.New("invalid migration status")
	}
	if req.MigrationScript == "" {
		return errors.New("migration script is required")
	}
	if len(req.ValidationRules) == 0 {
		return errors.New("validation rules are required")
	}
	// Reject direct PHI patterns in metadata keys
	for key := range req.Metadata {
		lowerKey := strings.ToLower(key)
		if strings.Contains(lowerKey, "patient_id") || strings.Contains(lowerKey, "ssn") ||
			strings.Contains(lowerKey, "birth_date") || strings.Contains(lowerKey, "phone") {
			return errors.New("metadata keys must not contain direct PHI patterns")
		}
	}
	return nil
}

// CreateWorkflowVersionMigration creates a new workflow version migration
func CreateWorkflowVersionMigration(req *WorkflowVersionMigrationRequest) (*WorkflowVersionMigration, error) {
	if err := ValidateWorkflowVersionMigrationRequest(req); err != nil {
		return nil, err
	}

	versionMigrationMutex.Lock()
	defer versionMigrationMutex.Unlock()

	// Check idempotency
	if existingID, exists := versionMigrationKeys[req.IdempotencyKey]; exists {
		return versionMigrationStore[existingID], nil
	}

	// Check for duplicate migration ID
	if _, exists := versionMigrationStore[req.MigrationID]; exists {
		return nil, errors.New("migration ID already exists")
	}

	migration := &WorkflowVersionMigration{
		MigrationID:      req.MigrationID,
		WorkflowID:       req.WorkflowID,
		SourceVersion:    req.SourceVersion,
		TargetVersion:    req.TargetVersion,
		MigrationStatus:  req.MigrationStatus,
		MigrationScript:  req.MigrationScript,
		RollbackScript:   req.RollbackScript,
		ValidationRules:  req.ValidationRules,
		Metadata:         req.Metadata,
		IdempotencyKey:   req.IdempotencyKey,
	}

	migration.Checksum = GenerateMigrationChecksum(migration)
	versionMigrationStore[migration.MigrationID] = migration
	versionMigrationKeys[req.IdempotencyKey] = migration.MigrationID

	return migration, nil
}

// GetWorkflowVersionMigration retrieves a workflow version migration by ID
func GetWorkflowVersionMigration(migrationID string) (*WorkflowVersionMigration, error) {
	if migrationID == "" {
		return nil, errors.New("migration ID is required")
	}

	versionMigrationMutex.RLock()
	defer versionMigrationMutex.RUnlock()

	migration, exists := versionMigrationStore[migrationID]
	if !exists {
		return nil, errors.New("migration not found")
	}

	return migration, nil
}

// UpdateWorkflowVersionMigration updates an existing workflow version migration
func UpdateWorkflowVersionMigration(req *WorkflowVersionMigrationRequest) (*WorkflowVersionMigration, error) {
	if err := ValidateWorkflowVersionMigrationRequest(req); err != nil {
		return nil, err
	}

	versionMigrationMutex.Lock()
	defer versionMigrationMutex.Unlock()

	if _, exists := versionMigrationStore[req.MigrationID]; !exists {
		return nil, errors.New("migration not found")
	}

	migration := &WorkflowVersionMigration{
		MigrationID:      req.MigrationID,
		WorkflowID:       req.WorkflowID,
		SourceVersion:    req.SourceVersion,
		TargetVersion:    req.TargetVersion,
		MigrationStatus:  req.MigrationStatus,
		MigrationScript:  req.MigrationScript,
		RollbackScript:   req.RollbackScript,
		ValidationRules:  req.ValidationRules,
		Metadata:         req.Metadata,
		IdempotencyKey:   req.IdempotencyKey,
	}

	migration.Checksum = GenerateMigrationChecksum(migration)
	versionMigrationStore[migration.MigrationID] = migration

	return migration, nil
}

// DeleteWorkflowVersionMigration deletes a workflow version migration
func DeleteWorkflowVersionMigration(migrationID string) error {
	if migrationID == "" {
		return errors.New("migration ID is required")
	}

	versionMigrationMutex.Lock()
	defer versionMigrationMutex.Unlock()

	migration, exists := versionMigrationStore[migrationID]
	if !exists {
		return errors.New("migration not found")
	}

	delete(versionMigrationKeys, migration.IdempotencyKey)
	delete(versionMigrationStore, migrationID)

	return nil
}

// ListWorkflowVersionMigrations lists all workflow version migrations
func ListWorkflowVersionMigrations() ([]*WorkflowVersionMigration, error) {
	versionMigrationMutex.RLock()
	defer versionMigrationMutex.RUnlock()

	migrations := make([]*WorkflowVersionMigration, 0, len(versionMigrationStore))
	for _, migration := range versionMigrationStore {
		migrations = append(migrations, migration)
	}

	return migrations, nil
}

// ListWorkflowVersionMigrationsByWorkflow lists workflow version migrations by workflow ID
func ListWorkflowVersionMigrationsByWorkflow(workflowID string) ([]*WorkflowVersionMigration, error) {
	versionMigrationMutex.RLock()
	defer versionMigrationMutex.RUnlock()

	migrations := make([]*WorkflowVersionMigration, 0)
	for _, migration := range versionMigrationStore {
		if migration.WorkflowID == workflowID {
			migrations = append(migrations, migration)
		}
	}

	return migrations, nil
}

// GenerateMigrationChecksum generates a SHA256 checksum for a workflow version migration
func GenerateMigrationChecksum(migration *WorkflowVersionMigration) string {
	data := migration.MigrationID + migration.WorkflowID + migration.SourceVersion + migration.TargetVersion + migration.MigrationScript
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}
