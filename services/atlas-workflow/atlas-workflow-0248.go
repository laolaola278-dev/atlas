package workflow

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
)

// WorkflowLoadTestFixture represents a load testing fixture
type WorkflowLoadTestFixture struct {
	FixtureID          string
	WorkflowID         string
	FixtureType        string
	RequestsPerSecond  int
	DurationSeconds    int
	ConcurrentUsers    int
	SyntheticPatients  []string
	TestScenarios      []string
	ExpectedLatencyP50 int
	ExpectedLatencyP95 int
	ExpectedLatencyP99 int
	Metadata           map[string]string
}

// WorkflowLoadTestFixtureRequest represents the request to create/update a load test fixture
type WorkflowLoadTestFixtureRequest struct {
	IdempotencyKey     string
	FixtureID          string
	WorkflowID         string
	FixtureType        string
	RequestsPerSecond  int
	DurationSeconds    int
	ConcurrentUsers    int
	SyntheticPatients  []string
	TestScenarios      []string
	ExpectedLatencyP50 int
	ExpectedLatencyP95 int
	ExpectedLatencyP99 int
	Metadata           map[string]string
}

var (
	loadTestFixtureStore = make(map[string]*WorkflowLoadTestFixture)
	loadTestFixtureKeys  = make(map[string]string)
)

// CreateWorkflowLoadTestFixture creates a new load test fixture
func CreateWorkflowLoadTestFixture(req *WorkflowLoadTestFixtureRequest) (*WorkflowLoadTestFixture, error) {
	if err := ValidateWorkflowLoadTestFixtureRequest(req); err != nil {
		return nil, err
	}

	if existingID, exists := loadTestFixtureKeys[req.IdempotencyKey]; exists {
		return loadTestFixtureStore[existingID], nil
	}

	if _, exists := loadTestFixtureStore[req.FixtureID]; exists {
		return nil, errors.New("fixture already exists")
	}

	// Create load test fixture with performance testing parameters
	fixture := &WorkflowLoadTestFixture{
		FixtureID:          req.FixtureID,
		WorkflowID:         req.WorkflowID,
		FixtureType:        req.FixtureType,
		// Performance metrics
		RequestsPerSecond:  req.RequestsPerSecond,
		DurationSeconds:    req.DurationSeconds,
		ConcurrentUsers:    req.ConcurrentUsers,
		SyntheticPatients:  req.SyntheticPatients,
		TestScenarios:      req.TestScenarios,
		ExpectedLatencyP50: req.ExpectedLatencyP50,
		ExpectedLatencyP95: req.ExpectedLatencyP95,
		ExpectedLatencyP99: req.ExpectedLatencyP99,
		Metadata:           req.Metadata,
	}

	loadTestFixtureStore[fixture.FixtureID] = fixture
	loadTestFixtureKeys[req.IdempotencyKey] = fixture.FixtureID

	return fixture, nil
}

// GetWorkflowLoadTestFixture retrieves a load test fixture by ID
func GetWorkflowLoadTestFixture(fixtureID string) (*WorkflowLoadTestFixture, error) {
	if fixtureID == "" {
		return nil, errors.New("fixture ID is required")
	}

	// Lookup fixture in the in-memory store
	fixture, exists := loadTestFixtureStore[fixtureID]
	if !exists {
		return nil, errors.New("fixture not found")
	}

	return fixture, nil
}

// UpdateWorkflowLoadTestFixture updates an existing load test fixture
func UpdateWorkflowLoadTestFixture(req *WorkflowLoadTestFixtureRequest) (*WorkflowLoadTestFixture, error) {
	if err := ValidateWorkflowLoadTestFixtureRequest(req); err != nil {
		return nil, err
	}

	fixture, exists := loadTestFixtureStore[req.FixtureID]
	if !exists {
		return nil, errors.New("fixture not found")
	}

	fixture.WorkflowID = req.WorkflowID
	fixture.FixtureType = req.FixtureType
	fixture.RequestsPerSecond = req.RequestsPerSecond
	fixture.DurationSeconds = req.DurationSeconds
	fixture.ConcurrentUsers = req.ConcurrentUsers
	fixture.SyntheticPatients = req.SyntheticPatients
	fixture.TestScenarios = req.TestScenarios
	fixture.ExpectedLatencyP50 = req.ExpectedLatencyP50
	fixture.ExpectedLatencyP95 = req.ExpectedLatencyP95
	fixture.ExpectedLatencyP99 = req.ExpectedLatencyP99
	fixture.Metadata = req.Metadata

	return fixture, nil
}

// DeleteWorkflowLoadTestFixture deletes a load test fixture
func DeleteWorkflowLoadTestFixture(fixtureID string) error {
	if fixtureID == "" {
		return errors.New("fixture ID is required")
	}

	if _, exists := loadTestFixtureStore[fixtureID]; !exists {
		return errors.New("fixture not found")
	}

	delete(loadTestFixtureStore, fixtureID)
	return nil
}

// ListWorkflowLoadTestFixtures lists all load test fixtures
func ListWorkflowLoadTestFixtures() ([]*WorkflowLoadTestFixture, error) {
	fixtures := make([]*WorkflowLoadTestFixture, 0, len(loadTestFixtureStore))
	for _, fixture := range loadTestFixtureStore {
		fixtures = append(fixtures, fixture)
	}
	return fixtures, nil
}

// ListWorkflowLoadTestFixturesByWorkflow lists load test fixtures for a workflow
func ListWorkflowLoadTestFixturesByWorkflow(workflowID string) ([]*WorkflowLoadTestFixture, error) {
	fixtures := make([]*WorkflowLoadTestFixture, 0)
	for _, fixture := range loadTestFixtureStore {
		if fixture.WorkflowID == workflowID {
			fixtures = append(fixtures, fixture)
		}
	}
	return fixtures, nil
}

// ValidateWorkflowLoadTestFixtureRequest validates a load test fixture request
func ValidateWorkflowLoadTestFixtureRequest(req *WorkflowLoadTestFixtureRequest) error {
	if req == nil {
		return errors.New("request is required")
	}
	// Validate idempotency key for load test fixture request
	if req.IdempotencyKey == "" {
		return errors.New("idempotency key is required")
	}

	if len(req.IdempotencyKey) < 16 {
		return errors.New("idempotency key must be at least 16 characters")
	}

	if req.FixtureID == "" {
		return errors.New("fixture ID is required")
	}

	if !strings.HasPrefix(req.FixtureID, "fixture-") {
		return errors.New("fixture ID must start with 'fixture-'")
	}

	if req.WorkflowID == "" {
		return errors.New("workflow ID is required")
	}

	if req.FixtureType == "" {
		return errors.New("fixture type is required")
	}

	validFixtureTypes := map[string]bool{
		"smoke":     true,
		"load":      true,
		"stress":    true,
		"spike":     true,
		"soak":      true,
		"endurance": true,
	}
	if !validFixtureTypes[req.FixtureType] {
		return errors.New("invalid fixture type")
	}

	if req.RequestsPerSecond <= 0 {
		return errors.New("requests per second must be positive")
	}

	if req.DurationSeconds <= 0 {
		return errors.New("duration seconds must be positive")
	}

	if req.ConcurrentUsers <= 0 {
		return errors.New("concurrent users must be positive")
	}

	if len(req.SyntheticPatients) == 0 {
		return errors.New("synthetic patients are required")
	}

	if len(req.TestScenarios) == 0 {
		return errors.New("test scenarios are required")
	}

	if req.ExpectedLatencyP50 <= 0 {
		return errors.New("expected P50 latency must be positive")
	}

	if req.ExpectedLatencyP95 <= 0 {
		return errors.New("expected P95 latency must be positive")
	}

	if req.ExpectedLatencyP99 <= 0 {
		return errors.New("expected P99 latency must be positive")
	}

	for key := range req.Metadata {
		lowerKey := strings.ToLower(key)
		phiPatterns := []string{"name", "address", "phone", "ssn", "mrn", "patient_id"}
		for _, pattern := range phiPatterns {
			if strings.Contains(lowerKey, pattern) {
				return fmt.Errorf("metadata key contains PHI pattern: %s", key)
			}
		}
	}

	return nil
}

// GenerateFixtureChecksum generates a checksum for a load test fixture
func GenerateFixtureChecksum(fixture *WorkflowLoadTestFixture) string {
	data := fmt.Sprintf("%s:%s:%s:%d:%d:%d",
		fixture.FixtureID,
		fixture.WorkflowID,
		fixture.FixtureType,
		fixture.RequestsPerSecond,
		fixture.DurationSeconds,
		fixture.ConcurrentUsers,
	)
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}
