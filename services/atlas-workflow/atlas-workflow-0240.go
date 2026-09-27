// Package workflow provides human task node management with synthetic-only validation.
// This module implements fail-closed human task node gates.
package workflow

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"regexp"
	"strings"
	"sync"
	"time"
)

// HumanTaskRequest represents a human task node creation or assignment request.
type HumanTaskRequest struct {
	TaskID          string            `json:"task_id"`
	WorkflowID      string            `json:"workflow_id"`
	StepID          string            `json:"step_id"`
	AssignedTo      string            `json:"assigned_to"`
	TaskTitle       string            `json:"task_title"`
	TaskDescription string            `json:"task_description"`
	Priority        string            `json:"priority"`
	DueDate         string            `json:"due_date"`
	Metadata        map[string]string `json:"metadata"`
	IdempotencyKey  string            `json:"idempotency_key"`
	Synthetic       bool              `json:"synthetic"`
}

// HumanTaskResponse represents the response after creating a human task node.
type HumanTaskResponse struct {
	TaskID          string            `json:"task_id"`
	WorkflowID      string            `json:"workflow_id"`
	StepID          string            `json:"step_id"`
	AssignedTo      string            `json:"assigned_to"`
	TaskTitle       string            `json:"task_title"`
	Status          string            `json:"status"`
	CreatedAt       string            `json:"created_at"`
	Checksum        string            `json:"checksum"`
	Metadata        map[string]string `json:"metadata"`
}

var (
	phiPatternRegex  = regexp.MustCompile(`(?i)(patient_id|patient id|name|address|phone|birth_date|identifier)`)
	syntheticPattern = regexp.MustCompile(`^synthetic-[a-z0-9-]+$`)
	priorityValues   = map[string]bool{"low": true, "medium": true, "high": true, "critical": true}
	statusValues     = map[string]bool{"pending": true, "in_progress": true, "completed": true, "cancelled": true}
)

var (
	humanTaskStore  = make(map[string]*HumanTaskResponse)
	humanTaskMutex  sync.RWMutex
	taskIdempotency = make(map[string]string)
)

// ValidateHumanTaskRequest validates a human task node request.
func ValidateHumanTaskRequest(req *HumanTaskRequest) error {
	if req == nil {
		return errors.New("workflow-human-task-request-nil")
	}

	if !req.Synthetic {
		return errors.New("workflow-human-task-not-synthetic")
	}

	if req.IdempotencyKey == "" {
		return errors.New("workflow-human-task-idempotency-key-empty")
	}
	if len(req.IdempotencyKey) < 16 {
		return errors.New("workflow-human-task-idempotency-key-short")
	}

	if req.TaskID == "" {
		return errors.New("workflow-human-task-task-id-empty")
	}
	if !strings.HasPrefix(req.TaskID, "synthetic-") {
		return errors.New("workflow-human-task-task-id-invalid-prefix")
	}

	if req.WorkflowID == "" {
		return errors.New("workflow-human-task-workflow-id-empty")
	}

	if req.StepID == "" {
		return errors.New("workflow-human-task-step-id-empty")
	}

	if req.AssignedTo == "" {
		return errors.New("workflow-human-task-assigned-to-empty")
	}

	if strings.TrimSpace(req.TaskTitle) == "" {
		return errors.New("workflow-human-task-title-blank")
	}
	if phiPatternRegex.MatchString(req.TaskTitle) {
		return errors.New("workflow-human-task-title-phi-pattern")
	}

	if req.Priority != "" && !priorityValues[req.Priority] {
		return errors.New("workflow-human-task-priority-invalid")
	}

	for key := range req.Metadata {
		if phiPatternRegex.MatchString(key) {
			return errors.New("workflow-human-task-metadata-key-phi-pattern")
		}
	}

	return nil
}

// CreateHumanTask creates a new human task node.
func CreateHumanTask(req *HumanTaskRequest) (*HumanTaskResponse, error) {
	if err := ValidateHumanTaskRequest(req); err != nil {
		return nil, err
	}

	humanTaskMutex.Lock()
	defer humanTaskMutex.Unlock()

	if existingID, found := taskIdempotency[req.IdempotencyKey]; found {
		return humanTaskStore[existingID], nil
	}

	checksum := GenerateHumanTaskChecksum(req)
	resp := &HumanTaskResponse{
		TaskID:     req.TaskID,
		WorkflowID: req.WorkflowID,
		StepID:     req.StepID,
		AssignedTo: req.AssignedTo,
		TaskTitle:  req.TaskTitle,
		Status:     "pending",
		CreatedAt:  time.Now().UTC().Format(time.RFC3339),
		Checksum:   checksum,
		Metadata:   req.Metadata,
	}

	humanTaskStore[req.TaskID] = resp
	taskIdempotency[req.IdempotencyKey] = req.TaskID

	return resp, nil
}

// GetHumanTask retrieves a human task by ID.
func GetHumanTask(taskID string) (*HumanTaskResponse, error) {
	if taskID == "" {
		return nil, errors.New("workflow-human-task-get-id-empty")
	}

	humanTaskMutex.RLock()
	defer humanTaskMutex.RUnlock()

	task, found := humanTaskStore[taskID]
	if !found {
		return nil, errors.New("workflow-human-task-not-found")
	}

	return task, nil
}

// UpdateHumanTaskStatus updates the status of a human task.
func UpdateHumanTaskStatus(taskID string, status string) error {
	if taskID == "" {
		return errors.New("workflow-human-task-update-id-empty")
	}
	if status == "" {
		return errors.New("workflow-human-task-status-empty")
	}
	if !statusValues[status] {
		return errors.New("workflow-human-task-status-invalid")
	}

	humanTaskMutex.Lock()
	defer humanTaskMutex.Unlock()

	task, found := humanTaskStore[taskID]
	if !found {
		return errors.New("workflow-human-task-not-found")
	}

	task.Status = status
	return nil
}

// ListHumanTasks retrieves all human tasks.
func ListHumanTasks() []*HumanTaskResponse {
	humanTaskMutex.RLock()
	defer humanTaskMutex.RUnlock()

	tasks := make([]*HumanTaskResponse, 0, len(humanTaskStore))
	for _, task := range humanTaskStore {
		tasks = append(tasks, task)
	}

	return tasks
}

// ListHumanTasksByWorkflow retrieves all human tasks for a specific workflow.
func ListHumanTasksByWorkflow(workflowID string) []*HumanTaskResponse {
	humanTaskMutex.RLock()
	defer humanTaskMutex.RUnlock()

	tasks := make([]*HumanTaskResponse, 0)
	for _, task := range humanTaskStore {
		if task.WorkflowID == workflowID {
			tasks = append(tasks, task)
		}
	}

	return tasks
}

// ListHumanTasksByAssignee retrieves all human tasks assigned to a specific user.
func ListHumanTasksByAssignee(assignedTo string) []*HumanTaskResponse {
	humanTaskMutex.RLock()
	defer humanTaskMutex.RUnlock()

	tasks := make([]*HumanTaskResponse, 0)
	for _, task := range humanTaskStore {
		if task.AssignedTo == assignedTo {
			tasks = append(tasks, task)
		}
	}

	return tasks
}

// DeleteHumanTask deletes a human task by ID.
func DeleteHumanTask(taskID string) error {
	if taskID == "" {
		return errors.New("workflow-human-task-delete-id-empty")
	}

	humanTaskMutex.Lock()
	defer humanTaskMutex.Unlock()

	if _, found := humanTaskStore[taskID]; !found {
		return errors.New("workflow-human-task-not-found")
	}

	delete(humanTaskStore, taskID)
	return nil
}

// ClearHumanTasks clears all human tasks from the store.
func ClearHumanTasks() {
	humanTaskMutex.Lock()
	defer humanTaskMutex.Unlock()
	humanTaskStore = make(map[string]*HumanTaskResponse)
	taskIdempotency = make(map[string]string)
}

// GenerateHumanTaskChecksum generates a SHA256 checksum for a human task request.
func GenerateHumanTaskChecksum(req *HumanTaskRequest) string {
	h := sha256.New()
	h.Write([]byte(req.TaskID))
	h.Write([]byte(req.WorkflowID))
	h.Write([]byte(req.StepID))
	h.Write([]byte(req.AssignedTo))
	h.Write([]byte(req.TaskTitle))
	return hex.EncodeToString(h.Sum(nil))
}
