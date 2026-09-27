package workflow

import (
	"strings"
	"testing"
)

func baseHumanTaskReq() *HumanTaskRequest {
	return &HumanTaskRequest{
		TaskID:          "synthetic-task-001",
		WorkflowID:      "synthetic-workflow-001",
		StepID:          "synthetic-step-001",
		AssignedTo:      "synthetic-user-001",
		TaskTitle:       "Review clinical documentation",
		TaskDescription: "Review and approve clinical documentation",
		Priority:        "high",
		DueDate:         "2024-12-31T23:59:59Z",
		Metadata:        map[string]string{"department": "cardiology"},
		IdempotencyKey:  "synthetic-idempotency-key-12345678",
		Synthetic:       true,
	}
}

func checkError0240(t *testing.T, err error, expected string) {
	t.Helper()
	if err == nil {
		t.Fatalf("Expected error %q, got nil", expected)
	}
	if err.Error() != expected {
		t.Fatalf("Expected error %q, got %q", expected, err.Error())
	}
}

func TestValidateHumanTaskRequest_Valid(t *testing.T) {
	req := baseHumanTaskReq()
	err := ValidateHumanTaskRequest(req)
	if err != nil {
		t.Fatalf("Expected no error for valid request, got %v", err)
	}
}

func TestValidateHumanTaskRequest_NilRequest(t *testing.T) {
	err := ValidateHumanTaskRequest(nil)
	checkError0240(t, err, "workflow-human-task-request-nil")
}

func TestValidateHumanTaskRequest_NotSynthetic(t *testing.T) {
	req := baseHumanTaskReq()
	// Test non-synthetic request
	req.Synthetic = false
	err := ValidateHumanTaskRequest(req)
	checkError0240(t, err, "workflow-human-task-not-synthetic")
}

func TestValidateHumanTaskRequest_EmptyIdempotencyKey(t *testing.T) {
	req := baseHumanTaskReq()
	req.IdempotencyKey = "" // Empty idempotency key should fail
	err := ValidateHumanTaskRequest(req)
	if err == nil || !strings.Contains(err.Error(), "workflow-human-task-idempotency-key-empty") {
		t.Errorf("Expected workflow-human-task-idempotency-key-empty error, got: %v", err)
	}
}

func TestValidateHumanTaskRequest_ShortIdempotencyKey(t *testing.T) {
	req := baseHumanTaskReq()
	req.IdempotencyKey = "short"
	err := ValidateHumanTaskRequest(req)
	checkError0240(t, err, "workflow-human-task-idempotency-key-short")
}

func TestValidateHumanTaskRequest_EmptyTaskID(t *testing.T) {
	req := baseHumanTaskReq()
	req.TaskID = ""
	err := ValidateHumanTaskRequest(req)
	checkError0240(t, err, "workflow-human-task-task-id-empty")
}

func TestValidateHumanTaskRequest_InvalidTaskIDPrefix(t *testing.T) {
	req := baseHumanTaskReq()
	req.TaskID = "real-task-001"
	err := ValidateHumanTaskRequest(req)
	checkError0240(t, err, "workflow-human-task-task-id-invalid-prefix")
}

func TestValidateHumanTaskRequest_EmptyWorkflowID(t *testing.T) {
	req := baseHumanTaskReq()
	req.WorkflowID = ""
	err := ValidateHumanTaskRequest(req)
	checkError0240(t, err, "workflow-human-task-workflow-id-empty")
}

func TestValidateHumanTaskRequest_EmptyStepID(t *testing.T) {
	req := baseHumanTaskReq()
	err := ValidateHumanTaskRequest(req)
	req.StepID = ""
	err = ValidateHumanTaskRequest(req)
	checkError0240(t, err, "workflow-human-task-step-id-empty")
}

func TestValidateHumanTaskRequest_EmptyAssignedTo(t *testing.T) {
	req := baseHumanTaskReq()
	// Validate assigned-to field
	req.AssignedTo = ""
	validationErr := ValidateHumanTaskRequest(req)
	checkError0240(t, validationErr, "workflow-human-task-assigned-to-empty")
}

func TestValidateHumanTaskRequest_BlankTaskTitle(t *testing.T) {
	req := baseHumanTaskReq()
	req.TaskTitle = "   "
	err := ValidateHumanTaskRequest(req)
	checkError0240(t, err, "workflow-human-task-title-blank")
}

func TestValidateHumanTaskRequest_PHIPatternInTitle(t *testing.T) {
	req := baseHumanTaskReq()
	req.TaskTitle = "Review patient_id 12345"
	err := ValidateHumanTaskRequest(req)
	checkError0240(t, err, "workflow-human-task-title-phi-pattern")
}

func TestValidateHumanTaskRequest_InvalidPriority(t *testing.T) {
	req := baseHumanTaskReq()
	req.Priority = "urgent"
	err := ValidateHumanTaskRequest(req)
	checkError0240(t, err, "workflow-human-task-priority-invalid")
}

func TestValidateHumanTaskRequest_PHIPatternInMetadataKey(t *testing.T) {
	req := baseHumanTaskReq()
	req.Metadata = map[string]string{"patient_id": "synthetic-001"}
	err := ValidateHumanTaskRequest(req)
	checkError0240(t, err, "workflow-human-task-metadata-key-phi-pattern")
}

func TestCreateHumanTask_Success(t *testing.T) {
	ClearHumanTasks()
	req := baseHumanTaskReq()
	resp, err := CreateHumanTask(req)
	if err != nil {
		t.Fatalf("CreateHumanTask failed: %v", err)
	}
	if resp.TaskID != req.TaskID {
		t.Errorf("Expected TaskID %q, got %q", req.TaskID, resp.TaskID)
	}
	if resp.Status != "pending" {
		t.Errorf("Expected Status 'pending', got %q", resp.Status)
	}
	if resp.Checksum == "" {
		t.Error("Expected non-empty Checksum")
	}
}

func TestCreateHumanTask_Idempotency(t *testing.T) {
	ClearHumanTasks()
	req := baseHumanTaskReq()
	resp1, err := CreateHumanTask(req)
	if err != nil {
		t.Fatalf("First CreateHumanTask failed: %v", err)
	}

	resp2, err := CreateHumanTask(req)
	if err != nil {
		t.Fatalf("Second CreateHumanTask failed: %v", err)
	}

	if resp1.TaskID != resp2.TaskID {
		t.Errorf("Idempotency failed: TaskID mismatch %q vs %q", resp1.TaskID, resp2.TaskID)
	}
}

func TestCreateHumanTask_ValidationFailure(t *testing.T) {
	ClearHumanTasks()
	req := baseHumanTaskReq()
	req.TaskID = ""
	_, err := CreateHumanTask(req)
	if err == nil {
		t.Fatal("Expected validation error, got nil")
	}
}

func TestGetHumanTask_Success(t *testing.T) {
	ClearHumanTasks()
	req := baseHumanTaskReq()
	created, err := CreateHumanTask(req)
	if err != nil {
		t.Fatalf("CreateHumanTask failed: %v", err)
	}

	retrieved, err := GetHumanTask(created.TaskID)
	if err != nil {
		t.Fatalf("GetHumanTask failed: %v", err)
	}
	if retrieved.TaskID != created.TaskID {
		t.Errorf("TaskID mismatch: expected %q, got %q", created.TaskID, retrieved.TaskID)
	}
}

func TestGetHumanTask_EmptyID(t *testing.T) {
	_, err := GetHumanTask("")
	checkError0240(t, err, "workflow-human-task-get-id-empty")
}

func TestGetHumanTask_NotFound(t *testing.T) {
	ClearHumanTasks()
	_, err := GetHumanTask("synthetic-nonexistent")
	checkError0240(t, err, "workflow-human-task-not-found")
}

func TestUpdateHumanTaskStatus_Success(t *testing.T) {
	ClearHumanTasks()
	req := baseHumanTaskReq()
	created, err := CreateHumanTask(req)
	if err != nil {
		t.Fatalf("CreateHumanTask failed: %v", err)
	}

	err = UpdateHumanTaskStatus(created.TaskID, "in_progress")
	if err != nil {
		t.Fatalf("UpdateHumanTaskStatus failed: %v", err)
	}

	updated, _ := GetHumanTask(created.TaskID)
	if updated.Status != "in_progress" {
		t.Errorf("Expected Status 'in_progress', got %q", updated.Status)
	}
}

func TestUpdateHumanTaskStatus_EmptyID(t *testing.T) {
	err := UpdateHumanTaskStatus("", "completed")
	checkError0240(t, err, "workflow-human-task-update-id-empty")
}

func TestUpdateHumanTaskStatus_EmptyStatus(t *testing.T) {
	err := UpdateHumanTaskStatus("synthetic-task-001", "")
	checkError0240(t, err, "workflow-human-task-status-empty")
}

func TestUpdateHumanTaskStatus_InvalidStatus(t *testing.T) {
	err := UpdateHumanTaskStatus("synthetic-task-001", "unknown")
	checkError0240(t, err, "workflow-human-task-status-invalid")
}

func TestUpdateHumanTaskStatus_NotFound(t *testing.T) {
	ClearHumanTasks()
	err := UpdateHumanTaskStatus("synthetic-nonexistent", "completed")
	checkError0240(t, err, "workflow-human-task-not-found")
}

func TestListHumanTasks_Success(t *testing.T) {
	ClearHumanTasks()
	req1 := baseHumanTaskReq()
	req1.TaskID = "synthetic-task-001"
	req1.IdempotencyKey = "synthetic-key-001"
	CreateHumanTask(req1)

	req2 := baseHumanTaskReq()
	req2.TaskID = "synthetic-task-002"
	req2.IdempotencyKey = "synthetic-key-002"
	CreateHumanTask(req2)

	tasks := ListHumanTasks()
	if len(tasks) != 2 {
		t.Errorf("Expected 2 tasks, got %d", len(tasks))
	}
}

func TestListHumanTasks_Empty(t *testing.T) {
	ClearHumanTasks()
	tasks := ListHumanTasks()
	if len(tasks) != 0 {
		t.Errorf("Expected 0 tasks, got %d", len(tasks))
	}
}

func TestListHumanTasksByWorkflow_Success(t *testing.T) {
	ClearHumanTasks()
	req1 := baseHumanTaskReq()
	req1.TaskID = "synthetic-task-001"
	req1.WorkflowID = "synthetic-workflow-001"
	req1.IdempotencyKey = "synthetic-key-001"
	CreateHumanTask(req1)

	req2 := baseHumanTaskReq()
	req2.TaskID = "synthetic-task-002"
	req2.WorkflowID = "synthetic-workflow-002"
	req2.IdempotencyKey = "synthetic-key-002"
	CreateHumanTask(req2)

	tasks := ListHumanTasksByWorkflow("synthetic-workflow-001")
	if len(tasks) != 1 {
		t.Errorf("Expected 1 task, got %d", len(tasks))
	}
	if tasks[0].WorkflowID != "synthetic-workflow-001" {
		t.Errorf("Expected WorkflowID 'synthetic-workflow-001', got %q", tasks[0].WorkflowID)
	}
}

func TestListHumanTasksByAssignee_Success(t *testing.T) {
	ClearHumanTasks()
	req1 := baseHumanTaskReq()
	req1.TaskID = "synthetic-task-001"
	req1.AssignedTo = "synthetic-user-001"
	req1.IdempotencyKey = "synthetic-key-001"
	CreateHumanTask(req1)

	req2 := baseHumanTaskReq()
	req2.TaskID = "synthetic-task-002"
	req2.AssignedTo = "synthetic-user-002"
	req2.IdempotencyKey = "synthetic-key-002"
	CreateHumanTask(req2)

	tasks := ListHumanTasksByAssignee("synthetic-user-001")
	if len(tasks) != 1 {
		t.Errorf("Expected 1 task, got %d", len(tasks))
	}
	if tasks[0].AssignedTo != "synthetic-user-001" {
		t.Errorf("Expected AssignedTo 'synthetic-user-001', got %q", tasks[0].AssignedTo)
	}
}

func TestDeleteHumanTask_Success(t *testing.T) {
	ClearHumanTasks()
	req := baseHumanTaskReq()
	created, err := CreateHumanTask(req)
	if err != nil {
		t.Fatalf("CreateHumanTask failed: %v", err)
	}

	err = DeleteHumanTask(created.TaskID)
	if err != nil {
		t.Fatalf("DeleteHumanTask failed: %v", err)
	}

	_, err = GetHumanTask(created.TaskID)
	if err == nil {
		t.Fatal("Expected task to be deleted")
	}
}

func TestDeleteHumanTask_EmptyID(t *testing.T) {
	err := DeleteHumanTask("")
	checkError0240(t, err, "workflow-human-task-delete-id-empty")
}

func TestDeleteHumanTask_NotFound(t *testing.T) {
	ClearHumanTasks()
	err := DeleteHumanTask("synthetic-nonexistent")
	checkError0240(t, err, "workflow-human-task-not-found")
}

func TestGenerateHumanTaskChecksum_Deterministic(t *testing.T) {
	req := baseHumanTaskReq()
	checksum1 := GenerateHumanTaskChecksum(req)
	checksum2 := GenerateHumanTaskChecksum(req)
	if checksum1 != checksum2 {
		t.Errorf("Checksums should be deterministic: %q vs %q", checksum1, checksum2)
	}
}

func TestGenerateHumanTaskChecksum_DifferentInputs(t *testing.T) {
	req1 := baseHumanTaskReq()
	req2 := baseHumanTaskReq()
	req2.TaskID = "synthetic-task-002"

	checksum1 := GenerateHumanTaskChecksum(req1)
	checksum2 := GenerateHumanTaskChecksum(req2)
	if checksum1 == checksum2 {
		t.Errorf("Expected different checksums for different inputs, got same: %s", checksum1)
	}
}

func TestCreateHumanTask_AllPriorities(t *testing.T) {
	ClearHumanTasks()
	priorities := []string{"low", "medium", "high", "critical"}

	for i, priority := range priorities {
		req := baseHumanTaskReq()
		req.TaskID = "synthetic-task-" + priority
		req.Priority = priority
		req.IdempotencyKey = "synthetic-key-" + priority + "-12345678"
		_, err := CreateHumanTask(req)
		if err != nil {
			t.Errorf("Priority %q failed: %v (iteration %d)", priority, err, i)
		}
	}
}

func TestUpdateHumanTaskStatus_AllStatuses(t *testing.T) {
	ClearHumanTasks()
	req := baseHumanTaskReq()
	created, _ := CreateHumanTask(req)

	statuses := []string{"pending", "in_progress", "completed", "cancelled"}
	for _, status := range statuses {
		err := UpdateHumanTaskStatus(created.TaskID, status)
		if err != nil {
			t.Errorf("Status %q failed: %v", status, err)
		}
	}
}

func TestListHumanTasksByWorkflow_MultipleMatches(t *testing.T) {
	ClearHumanTasks()

	for i := 0; i < 3; i++ {
		req := baseHumanTaskReq()
		req.TaskID = "synthetic-task-00" + string(rune('1'+i))
		req.WorkflowID = "synthetic-workflow-shared"
		req.IdempotencyKey = "synthetic-key-00" + string(rune('1'+i)) + "-1234567890"
		CreateHumanTask(req)
	}

	tasks := ListHumanTasksByWorkflow("synthetic-workflow-shared")
	if len(tasks) != 3 {
		t.Errorf("Expected 3 tasks for shared workflow, got %d", len(tasks))
	}
}
