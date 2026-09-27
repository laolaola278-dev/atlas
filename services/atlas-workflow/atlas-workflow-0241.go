package workflow

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"
)

// TimeoutEscalationRequest represents a request to create or update a timeout escalation rule
type TimeoutEscalationRequest struct {
	RuleID           string            `json:"rule_id"`
	WorkflowID       string            `json:"workflow_id"`
	StepID           string            `json:"step_id"`
	TimeoutDuration  int64             `json:"timeout_duration"` // in seconds
	EscalationAction string            `json:"escalation_action"`
	EscalationTarget string            `json:"escalation_target"`
	NotifyUsers      []string          `json:"notify_users"`
	Metadata         map[string]string `json:"metadata"`
	IdempotencyKey   string            `json:"idempotency_key"`
}

// TimeoutEscalationRule represents a stored timeout escalation rule
type TimeoutEscalationRule struct {
	RuleID           string            `json:"rule_id"`
	WorkflowID       string            `json:"workflow_id"`
	StepID           string            `json:"step_id"`
	TimeoutDuration  int64             `json:"timeout_duration"`
	EscalationAction string            `json:"escalation_action"`
	EscalationTarget string            `json:"escalation_target"`
	NotifyUsers      []string          `json:"notify_users"`
	Metadata         map[string]string `json:"metadata"`
	Checksum         string            `json:"checksum"`
	CreatedAt        time.Time         `json:"created_at"`
}

var (
	timeoutEscalationStore       = make(map[string]*TimeoutEscalationRule)
	timeoutEscalationIdempotency = make(map[string]string)
	escalationPHIPatternRegex    = regexp.MustCompile(`(?i)(patient[_\s-]?(id|name|identifier|mrn)|birth[_\s-]?date|phone|address|ssn|email)`)
)

// ValidateTimeoutEscalationRequest validates the timeout escalation request
func ValidateTimeoutEscalationRequest(req *TimeoutEscalationRequest) error {
	if req == nil {
		return errors.New("workflow-timeout-escalation-request-nil")
	}

	if !strings.HasPrefix(req.RuleID, "synthetic-") {
		return errors.New("workflow-timeout-escalation-rule-id-not-synthetic")
	}

	if req.IdempotencyKey == "" {
		return errors.New("workflow-timeout-escalation-idempotency-key-empty")
	}

	if len(req.IdempotencyKey) < 8 {
		return errors.New("workflow-timeout-escalation-idempotency-key-short")
	}

	if req.RuleID == "" {
		return errors.New("workflow-timeout-escalation-rule-id-empty")
	}

	if !strings.HasPrefix(req.RuleID, "synthetic-rule-") {
		return errors.New("workflow-timeout-escalation-rule-id-invalid-prefix")
	}

	if req.WorkflowID == "" {
		return errors.New("workflow-timeout-escalation-workflow-id-empty")
	}

	if req.StepID == "" {
		return errors.New("workflow-timeout-escalation-step-id-empty")
	}

	if req.TimeoutDuration <= 0 {
		return errors.New("workflow-timeout-escalation-duration-invalid")
	}

	if req.EscalationAction == "" {
		return errors.New("workflow-timeout-escalation-action-empty")
	}

	validActions := map[string]bool{
		"notify":        true,
		"reassign":      true,
		"escalate":      true,
		"cancel":        true,
		"auto-complete": true,
	}
	if !validActions[req.EscalationAction] {
		return errors.New("workflow-timeout-escalation-action-invalid")
	}

	if req.EscalationTarget == "" && (req.EscalationAction == "reassign" || req.EscalationAction == "escalate") {
		return errors.New("workflow-timeout-escalation-target-required")
	}

	if escalationPHIPatternRegex.MatchString(req.EscalationTarget) {
		return errors.New("workflow-timeout-escalation-target-phi-pattern")
	}

	for key := range req.Metadata {
		if escalationPHIPatternRegex.MatchString(key) {
			return errors.New("workflow-timeout-escalation-metadata-key-phi-pattern")
		}
	}

	return nil
}

// CreateTimeoutEscalation creates a new timeout escalation rule
func CreateTimeoutEscalation(req *TimeoutEscalationRequest) (*TimeoutEscalationRule, error) {
	if err := ValidateTimeoutEscalationRequest(req); err != nil {
		return nil, err
	}

	if existingID, found := timeoutEscalationIdempotency[req.IdempotencyKey]; found {
		if rule, ok := timeoutEscalationStore[existingID]; ok {
			return rule, nil
		}
	}

	checksum := GenerateTimeoutEscalationChecksum(req)

	rule := &TimeoutEscalationRule{
		RuleID:           req.RuleID,
		WorkflowID:       req.WorkflowID,
		StepID:           req.StepID,
		TimeoutDuration:  req.TimeoutDuration,
		EscalationAction: req.EscalationAction,
		EscalationTarget: req.EscalationTarget,
		NotifyUsers:      req.NotifyUsers,
		Metadata:         req.Metadata,
		Checksum:         checksum,
		CreatedAt:        time.Now().UTC(),
	}

	timeoutEscalationStore[req.RuleID] = rule
	timeoutEscalationIdempotency[req.IdempotencyKey] = req.RuleID

	return rule, nil
}

// GetTimeoutEscalation retrieves a timeout escalation rule by ID
func GetTimeoutEscalation(ruleID string) (*TimeoutEscalationRule, error) {
	if ruleID == "" {
		return nil, errors.New("workflow-timeout-escalation-rule-id-empty")
	}

	rule, found := timeoutEscalationStore[ruleID]
	if !found {
		return nil, errors.New("workflow-timeout-escalation-rule-not-found")
	}

	return rule, nil
}

// UpdateTimeoutEscalation updates an existing timeout escalation rule
func UpdateTimeoutEscalation(ruleID string, req *TimeoutEscalationRequest) (*TimeoutEscalationRule, error) {
	if ruleID == "" {
		return nil, errors.New("workflow-timeout-escalation-rule-id-empty")
	}

	if err := ValidateTimeoutEscalationRequest(req); err != nil {
		return nil, err
	}

	rule, found := timeoutEscalationStore[ruleID]
	if !found {
		return nil, errors.New("workflow-timeout-escalation-rule-not-found")
	}

	rule.WorkflowID = req.WorkflowID
	rule.StepID = req.StepID
	rule.TimeoutDuration = req.TimeoutDuration
	rule.EscalationAction = req.EscalationAction
	rule.EscalationTarget = req.EscalationTarget
	rule.NotifyUsers = req.NotifyUsers
	rule.Metadata = req.Metadata
	rule.Checksum = GenerateTimeoutEscalationChecksum(req)

	timeoutEscalationStore[ruleID] = rule

	return rule, nil
}

// ListTimeoutEscalations lists all timeout escalation rules
func ListTimeoutEscalations() []*TimeoutEscalationRule {
	rules := make([]*TimeoutEscalationRule, 0, len(timeoutEscalationStore))
	for _, rule := range timeoutEscalationStore {
		rules = append(rules, rule)
	}
	return rules
}

// ListTimeoutEscalationsByWorkflow lists timeout escalation rules by workflow ID
func ListTimeoutEscalationsByWorkflow(workflowID string) []*TimeoutEscalationRule {
	var rules []*TimeoutEscalationRule
	for _, rule := range timeoutEscalationStore {
		if rule.WorkflowID == workflowID {
			rules = append(rules, rule)
		}
	}
	return rules
}

// DeleteTimeoutEscalation deletes a timeout escalation rule
func DeleteTimeoutEscalation(ruleID string) error {
	if ruleID == "" {
		return errors.New("workflow-timeout-escalation-rule-id-empty")
	}

	if _, found := timeoutEscalationStore[ruleID]; !found {
		return errors.New("workflow-timeout-escalation-rule-not-found")
	}

	delete(timeoutEscalationStore, ruleID)
	return nil
}

// ClearTimeoutEscalations clears all timeout escalation rules (for testing)
func ClearTimeoutEscalations() {
	timeoutEscalationStore = make(map[string]*TimeoutEscalationRule)
	timeoutEscalationIdempotency = make(map[string]string)
}

// GenerateTimeoutEscalationChecksum generates a SHA256 checksum for the request
func GenerateTimeoutEscalationChecksum(req *TimeoutEscalationRequest) string {
	data := fmt.Sprintf("%s|%s|%s|%d|%s|%s",
		req.RuleID,
		req.WorkflowID,
		req.StepID,
		req.TimeoutDuration,
		req.EscalationAction,
		req.EscalationTarget,
	)

	if len(req.NotifyUsers) > 0 {
		notifyJSON, _ := json.Marshal(req.NotifyUsers)
		data += "|" + string(notifyJSON)
	}

	if len(req.Metadata) > 0 {
		metadataJSON, _ := json.Marshal(req.Metadata)
		data += "|" + string(metadataJSON)
	}

	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}
