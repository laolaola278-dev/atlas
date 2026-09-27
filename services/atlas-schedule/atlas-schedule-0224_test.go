package schedule

import (
	"context"
	"testing"
	"time"
)

func TestScheduleGenerator_GenerateSchedule_Synthetic(t *testing.T) {
	generator := NewScheduleGenerator()

	req := GenerateScheduleRequest{
		TenantID:            "TENANT-SYNTH-001",
		CampusID:            "CAMPUS-SYNTH-001",
		DepartmentID:        "DEPT-SYNTH-CARDIO",
		StartDate:           time.Date(2024, 3, 1, 0, 0, 0, 0, time.UTC),
		EndDate:             time.Date(2024, 3, 3, 0, 0, 0, 0, time.UTC),
		PractitionerCount:   3,
		SlotDurationMinutes: 30,
		Synthetic:           true,
		TraceID:             "trace-synth-001",
		Producer:            "test-generator",
	}

	resp, err := generator.GenerateSchedule(context.Background(), req)
	if err != nil {
		t.Fatalf("GenerateSchedule failed: %v", err)
	}

	if resp.TotalSlots <= 0 {
		t.Errorf("Expected positive total_slots, got %d", resp.TotalSlots)
	}

	if len(resp.Entries) != int(resp.TotalSlots) {
		t.Errorf("Entries count mismatch: got %d, want %d", len(resp.Entries), resp.TotalSlots)
	}

	// Validate all entries are synthetic
	for _, entry := range resp.Entries {
		if !entry.Synthetic {
			t.Errorf("Entry %s not marked synthetic", entry.ScheduleID)
		}
		if entry.PractitionerID == "" {
			t.Errorf("Entry %s missing practitioner_id", entry.ScheduleID)
		}
		if entry.DepartmentID != req.DepartmentID {
			t.Errorf("Entry %s department mismatch: got %s, want %s", entry.ScheduleID, entry.DepartmentID, req.DepartmentID)
		}
		if entry.SlotEnd.Before(entry.SlotStart) || entry.SlotEnd.Equal(entry.SlotStart) {
			t.Errorf("Entry %s invalid slot timing: start=%v, end=%v", entry.ScheduleID, entry.SlotStart, entry.SlotEnd)
		}
	}
}

func TestScheduleGenerator_GenerateSchedule_RejectNonSynthetic(t *testing.T) {
	generator := NewScheduleGenerator()

	req := GenerateScheduleRequest{
		TenantID:            "TENANT-SYNTH-001",
		CampusID:            "CAMPUS-SYNTH-001",
		DepartmentID:        "DEPT-SYNTH-NEURO",
		StartDate:           time.Date(2024, 3, 1, 0, 0, 0, 0, time.UTC),
		EndDate:             time.Date(2024, 3, 1, 0, 0, 0, 0, time.UTC),
		PractitionerCount:   1,
		SlotDurationMinutes: 30,
		Synthetic:           false, // Not synthetic
		TraceID:             "trace-synth-002",
	}

	resp, err := generator.GenerateSchedule(context.Background(), req)
	if err == nil {
		t.Fatal("Expected error for non-synthetic request, got none")
	}
	if resp.ErrorCode != ErrScheduleSyntheticRequired {
		t.Errorf("Expected error code %s, got %s", ErrScheduleSyntheticRequired, resp.ErrorCode)
	}
}

func TestScheduleGenerator_GenerateSchedule_Idempotency(t *testing.T) {
	generator := NewScheduleGenerator()

	req := GenerateScheduleRequest{
		TenantID:            "TENANT-SYNTH-001",
		CampusID:            "CAMPUS-SYNTH-001",
		DepartmentID:        "DEPT-SYNTH-ORTHO",
		StartDate:           time.Date(2024, 3, 1, 0, 0, 0, 0, time.UTC),
		EndDate:             time.Date(2024, 3, 2, 0, 0, 0, 0, time.UTC),
		PractitionerCount:   2,
		SlotDurationMinutes: 60,
		Synthetic:           true,
		TraceID:             "trace-synth-003",
	}

	resp1, err1 := generator.GenerateSchedule(context.Background(), req)
	if err1 != nil {
		t.Fatalf("First GenerateSchedule failed: %v", err1)
	}

	resp2, err2 := generator.GenerateSchedule(context.Background(), req)
	if err2 != nil {
		t.Fatalf("Second GenerateSchedule failed: %v", err2)
	}

	if resp1.GenerationID != resp2.GenerationID {
		t.Errorf("Generation ID mismatch: %s vs %s", resp1.GenerationID, resp2.GenerationID)
	}
	if resp1.TotalSlots != resp2.TotalSlots {
		t.Errorf("Total slots mismatch: %d vs %d", resp1.TotalSlots, resp2.TotalSlots)
	}
}

func TestScheduleGenerator_GenerateSchedule_InvalidPractitionerCount(t *testing.T) {
	generator := NewScheduleGenerator()

	req := GenerateScheduleRequest{
		TenantID:            "TENANT-SYNTH-001",
		CampusID:            "CAMPUS-SYNTH-001",
		DepartmentID:        "DEPT-SYNTH-DERM",
		StartDate:           time.Date(2024, 3, 1, 0, 0, 0, 0, time.UTC),
		EndDate:             time.Date(2024, 3, 1, 0, 0, 0, 0, time.UTC),
		PractitionerCount:   100, // Exceeds limit
		SlotDurationMinutes: 30,
		Synthetic:           true,
		TraceID:             "trace-synth-004",
	}

	resp, err := generator.GenerateSchedule(context.Background(), req)
	if err == nil {
		t.Fatal("Expected error for excessive practitioner count, got none")
	}
	if resp.ErrorCode != ErrScheduleCapacityExceeded {
		t.Errorf("Expected error code %s, got %s", ErrScheduleCapacityExceeded, resp.ErrorCode)
	}
}

func TestScheduleGenerator_GenerateSchedule_InvalidSlotDuration(t *testing.T) {
	generator := NewScheduleGenerator()

	req := GenerateScheduleRequest{
		TenantID:            "TENANT-SYNTH-001",
		CampusID:            "CAMPUS-SYNTH-001",
		DepartmentID:        "DEPT-SYNTH-PSYCH",
		StartDate:           time.Date(2024, 3, 1, 0, 0, 0, 0, time.UTC),
		EndDate:             time.Date(2024, 3, 1, 0, 0, 0, 0, time.UTC),
		PractitionerCount:   1,
		SlotDurationMinutes: 0, // Invalid
		Synthetic:           true,
		TraceID:             "trace-synth-005",
	}

	resp, err := generator.GenerateSchedule(context.Background(), req)
	if err == nil {
		t.Fatal("Expected error for invalid slot duration, got none")
	}
	if resp.ErrorCode != ErrScheduleSlotInvalid {
		t.Errorf("Expected error code %s, got %s", ErrScheduleSlotInvalid, resp.ErrorCode)
	}
}

func TestScheduleGenerator_GenerateSchedule_InvalidDateRange(t *testing.T) {
	generator := NewScheduleGenerator()

	req := GenerateScheduleRequest{
		TenantID:            "TENANT-SYNTH-001",
		CampusID:            "CAMPUS-SYNTH-001",
		DepartmentID:        "DEPT-SYNTH-RADIO",
		StartDate:           time.Date(2024, 3, 5, 0, 0, 0, 0, time.UTC),
		EndDate:             time.Date(2024, 3, 1, 0, 0, 0, 0, time.UTC), // Before start
		PractitionerCount:   1,
		SlotDurationMinutes: 30,
		Synthetic:           true,
		TraceID:             "trace-synth-006",
	}

	resp, err := generator.GenerateSchedule(context.Background(), req)
	if err == nil {
		t.Fatal("Expected error for invalid date range, got none")
	}
	if resp.ErrorCode != ErrScheduleInvalid {
		t.Errorf("Expected error code %s, got %s", ErrScheduleInvalid, resp.ErrorCode)
	}
}

func TestScheduleValidator_ValidateSynthetic(t *testing.T) {
	validator := NewScheduleValidator()

	entries := []ScheduleEntry{
		{
			ScheduleID:     "SCHED-001",
			PractitionerID: "PRACT-SYNTH-001",
			DepartmentID:   "DEPT-SYNTH-001",
			Synthetic:      true,
		},
		{
			ScheduleID:     "SCHED-002",
			PractitionerID: "PRACT-SYNTH-002",
			DepartmentID:   "DEPT-SYNTH-001",
			Synthetic:      false, // Not synthetic
		},
	}

	err := validator.ValidateSynthetic(entries)
	if err == nil {
		t.Fatal("Expected error for non-synthetic entry, got none")
	}
}

func TestScheduleValidator_ValidateNoOverlap(t *testing.T) {
	validator := NewScheduleValidator()

	entries := []ScheduleEntry{
		{
			ScheduleID:     "SCHED-001",
			PractitionerID: "PRACT-SYNTH-001",
			DepartmentID:   "DEPT-SYNTH-001",
			SlotStart:      time.Date(2024, 3, 1, 9, 0, 0, 0, time.UTC),
			SlotEnd:        time.Date(2024, 3, 1, 10, 0, 0, 0, time.UTC),
			Synthetic:      true,
		},
		{
			ScheduleID:     "SCHED-002",
			PractitionerID: "PRACT-SYNTH-001", // Same practitioner
			DepartmentID:   "DEPT-SYNTH-001",
			SlotStart:      time.Date(2024, 3, 1, 9, 30, 0, 0, time.UTC), // Overlaps
			SlotEnd:        time.Date(2024, 3, 1, 10, 30, 0, 0, time.UTC),
			Synthetic:      true,
		},
	}

	err := validator.ValidateNoOverlap(entries)
	if err == nil {
		t.Fatal("Expected error for overlapping slots, got none")
	}
}

func TestScheduleGenerator_ValidateSchedule(t *testing.T) {
	generator := NewScheduleGenerator()

	req := ValidateScheduleRequest{
		ScheduleID: "SCHED-SYNTH-001",
		TenantID:   "TENANT-SYNTH-001",
		CampusID:   "CAMPUS-SYNTH-001",
		TraceID:    "trace-validate-001",
	}

	resp, err := generator.ValidateSchedule(context.Background(), req)
	if err != nil {
		t.Fatalf("ValidateSchedule failed: %v", err)
	}

	if !resp.Valid {
		t.Errorf("Expected valid=true, got valid=false with errors: %v", resp.ValidationErrors)
	}
}

func TestScheduleGenerator_ValidateSchedule_MissingFields(t *testing.T) {
	generator := NewScheduleGenerator()

	req := ValidateScheduleRequest{
		ScheduleID: "", // Missing
		TenantID:   "TENANT-SYNTH-001",
		CampusID:   "", // Missing
		TraceID:    "trace-validate-002",
	}

	resp, err := generator.ValidateSchedule(context.Background(), req)
	if err != nil {
		t.Fatalf("ValidateSchedule failed: %v", err)
	}

	if resp.Valid {
		t.Error("Expected valid=false for missing fields")
	}
	if len(resp.ValidationErrors) == 0 {
		t.Error("Expected validation errors, got none")
	}
}
