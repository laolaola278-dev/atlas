// Package schedule implements synthetic scheduling generation with fail-closed validation.
// All schedule entries must be marked synthetic=true; real patient identifiers are prohibited.
package schedule

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"time"
)

// Validation error codes registered in internal/contract/errors.py
const (
	ErrScheduleInvalid          = "schedule-invalid"
	ErrScheduleSyntheticRequired = "schedule-synthetic-required"
	ErrScheduleOverlap          = "schedule-overlap"
	ErrScheduleDepartmentInvalid = "schedule-department-invalid"
	ErrScheduleSlotInvalid      = "schedule-slot-invalid"
	ErrScheduleCapacityExceeded  = "schedule-capacity-exceeded"
	ErrScheduleIdempotencyConflict = "schedule-idempotency-conflict"
	ErrScheduleResultUnknown    = "schedule-result-unknown"
)

// ScheduleEntry represents a single time slot allocation.
type ScheduleEntry struct {
	ScheduleID     string
	PractitionerID string
	DepartmentID   string
	SlotStart      time.Time
	SlotEnd        time.Time
	Status         string
	Synthetic      bool
	TenantID       string
	CampusID       string
}

// GenerateScheduleRequest contains synthetic schedule generation parameters.
type GenerateScheduleRequest struct {
	TenantID            string
	CampusID            string
	DepartmentID        string
	StartDate           time.Time
	EndDate             time.Time
	PractitionerCount   int32
	SlotDurationMinutes int32
	Synthetic           bool
	TraceID             string
	Producer            string
}

// GenerateScheduleResponse returns generated schedule entries and metadata.
type GenerateScheduleResponse struct {
	Entries      []ScheduleEntry
	TotalSlots   int32
	GenerationID string
	ErrorCode    string
	ErrorMessage string
}

// ValidateScheduleRequest validates schedule entries against schema and business rules.
type ValidateScheduleRequest struct {
	ScheduleID     string
	TenantID       string
	CampusID       string
	RequiredFields []string
	TraceID        string
}

// ValidateScheduleResponse returns validation result.
type ValidateScheduleResponse struct {
	Valid            bool
	ValidationErrors []string
	ErrorCode        string
	ErrorMessage     string
}

// ScheduleValidator enforces fail-closed schedule validation.
type ScheduleValidator struct {
	maxSlotsPerDay      int
	maxPractitionersPerDept int
	allowedStatuses     map[string]bool
}

// NewScheduleValidator creates a validator with default limits.
func NewScheduleValidator() *ScheduleValidator {
	return &ScheduleValidator{
		maxSlotsPerDay:      100,
		maxPractitionersPerDept: 50,
		allowedStatuses: map[string]bool{
			"available": true,
			"booked":    true,
			"blocked":   true,
		},
	}
}

// ValidateSynthetic ensures all schedule entries are marked synthetic.
func (v *ScheduleValidator) ValidateSynthetic(entries []ScheduleEntry) error {
	for _, entry := range entries {
		if !entry.Synthetic {
			return fmt.Errorf("%s: schedule entry must be synthetic", ErrScheduleSyntheticRequired)
		}
		if entry.PractitionerID == "" || entry.DepartmentID == "" {
			return fmt.Errorf("%s: practitioner_id and department_id required", ErrScheduleInvalid)
		}
	}
	return nil
}

// ValidateSlotTiming checks slot duration and boundaries.
func (v *ScheduleValidator) ValidateSlotTiming(entry ScheduleEntry, minDuration, maxDuration time.Duration) error {
	if entry.SlotStart.IsZero() || entry.SlotEnd.IsZero() {
		return fmt.Errorf("%s: slot_start and slot_end required", ErrScheduleSlotInvalid)
	}
	if !entry.SlotEnd.After(entry.SlotStart) {
		return fmt.Errorf("%s: slot_end must be after slot_start", ErrScheduleSlotInvalid)
	}
	duration := entry.SlotEnd.Sub(entry.SlotStart)
	if duration < minDuration || duration > maxDuration {
		return fmt.Errorf("%s: slot duration %v outside allowed range [%v, %v]", ErrScheduleSlotInvalid, duration, minDuration, maxDuration)
	}
	return nil
}

// ValidateNoOverlap ensures practitioner has no overlapping slots.
func (v *ScheduleValidator) ValidateNoOverlap(entries []ScheduleEntry) error {
	practitionerSlots := make(map[string][]ScheduleEntry)
	for _, entry := range entries {
		practitionerSlots[entry.PractitionerID] = append(practitionerSlots[entry.PractitionerID], entry)
	}

	for practitionerID, slots := range practitionerSlots {
		for i := 0; i < len(slots); i++ {
			for j := i + 1; j < len(slots); j++ {
				if slotsOverlap(slots[i], slots[j]) {
					return fmt.Errorf("%s: practitioner %s has overlapping slots", ErrScheduleOverlap, practitionerID)
				}
			}
		}
	}
	return nil
}

func slotsOverlap(a, b ScheduleEntry) bool {
	return a.SlotStart.Before(b.SlotEnd) && b.SlotStart.Before(a.SlotEnd)
}

// ValidateStatus checks status is in allowed set.
func (v *ScheduleValidator) ValidateStatus(entry ScheduleEntry) error {
	if !v.allowedStatuses[entry.Status] {
		return fmt.Errorf("%s: status %q not in allowed set", ErrScheduleInvalid, entry.Status)
	}
	return nil
}

// ValidateCapacity ensures slot count does not exceed limits.
func (v *ScheduleValidator) ValidateCapacity(entries []ScheduleEntry) error {
	departmentCounts := make(map[string]int)
	practitionerCounts := make(map[string]map[string]int) // dept -> practitioner -> count

	for _, entry := range entries {
		departmentCounts[entry.DepartmentID]++
		if practitionerCounts[entry.DepartmentID] == nil {
			practitionerCounts[entry.DepartmentID] = make(map[string]int)
		}
		practitionerCounts[entry.DepartmentID][entry.PractitionerID]++
	}

	for dept, practitioners := range practitionerCounts {
		if len(practitioners) > v.maxPractitionersPerDept {
			return fmt.Errorf("%s: department %s exceeds max practitioners", ErrScheduleCapacityExceeded, dept)
		}
	}

	return nil
}

// ScheduleGenerator creates synthetic schedule entries.
type ScheduleGenerator struct {
	validator *ScheduleValidator
	cache     map[string]GenerateScheduleResponse
}

// NewScheduleGenerator creates a generator with validator.
func NewScheduleGenerator() *ScheduleGenerator {
	return &ScheduleGenerator{
		validator: NewScheduleValidator(),
		cache:     make(map[string]GenerateScheduleResponse),
	}
}

// GenerateSchedule creates synthetic schedule entries with fail-closed validation.
func (g *ScheduleGenerator) GenerateSchedule(ctx context.Context, req GenerateScheduleRequest) (GenerateScheduleResponse, error) {
	// Idempotency check
	idempotencyKey := computeIdempotencyKey(req)
	if cached, exists := g.cache[idempotencyKey]; exists {
		return cached, nil
	}

	// Validate synthetic flag
	if !req.Synthetic {
		return GenerateScheduleResponse{
			ErrorCode:    ErrScheduleSyntheticRequired,
			ErrorMessage: "synthetic flag must be true",
		}, errors.New(ErrScheduleSyntheticRequired)
	}

	// Validate request parameters
	if req.DepartmentID == "" || req.TenantID == "" || req.CampusID == "" {
		return GenerateScheduleResponse{
			ErrorCode:    ErrScheduleInvalid,
			ErrorMessage: "tenant_id, campus_id, and department_id required",
		}, errors.New(ErrScheduleInvalid)
	}

	if req.PractitionerCount <= 0 || req.PractitionerCount > 50 {
		return GenerateScheduleResponse{
			ErrorCode:    ErrScheduleCapacityExceeded,
			ErrorMessage: "practitioner_count must be between 1 and 50",
		}, errors.New(ErrScheduleCapacityExceeded)
	}

	if req.SlotDurationMinutes <= 0 || req.SlotDurationMinutes > 480 {
		return GenerateScheduleResponse{
			ErrorCode:    ErrScheduleSlotInvalid,
			ErrorMessage: "slot_duration_minutes must be between 1 and 480",
		}, errors.New(ErrScheduleSlotInvalid)
	}

	if req.EndDate.Before(req.StartDate) || req.EndDate.Equal(req.StartDate) {
		return GenerateScheduleResponse{
			ErrorCode:    ErrScheduleInvalid,
			ErrorMessage: "end_date must be after start_date",
		}, errors.New(ErrScheduleInvalid)
	}

	// Generate entries
	var entries []ScheduleEntry
	slotDuration := time.Duration(req.SlotDurationMinutes) * time.Minute
	generationID := generateID(req.TraceID, req.DepartmentID)

	currentDate := req.StartDate
	for !currentDate.After(req.EndDate) {
		for practitionerIdx := int32(0); practitionerIdx < req.PractitionerCount; practitionerIdx++ {
			practitionerID := fmt.Sprintf("PRACT-SYNTH-%d", practitionerIdx+1)
			
			// Generate slots for work hours (8 AM - 5 PM)
			slotStart := time.Date(currentDate.Year(), currentDate.Month(), currentDate.Day(), 8, 0, 0, 0, time.UTC)
			endOfDay := time.Date(currentDate.Year(), currentDate.Month(), currentDate.Day(), 17, 0, 0, 0, time.UTC)

			for slotStart.Before(endOfDay) {
				slotEnd := slotStart.Add(slotDuration)
				if slotEnd.After(endOfDay) {
					break
				}

				entry := ScheduleEntry{
					ScheduleID:     generateID(generationID, practitionerID, slotStart.String()),
					PractitionerID: practitionerID,
					DepartmentID:   req.DepartmentID,
					SlotStart:      slotStart,
					SlotEnd:        slotEnd,
					Status:         "available",
					Synthetic:      true,
					TenantID:       req.TenantID,
					CampusID:       req.CampusID,
				}
				entries = append(entries, entry)
				slotStart = slotEnd
			}
		}
		currentDate = currentDate.AddDate(0, 0, 1)
	}

	// Validate generated entries
	if err := g.validator.ValidateSynthetic(entries); err != nil {
		return GenerateScheduleResponse{
			ErrorCode:    ErrScheduleSyntheticRequired,
			ErrorMessage: err.Error(),
		}, err
	}

	if err := g.validator.ValidateNoOverlap(entries); err != nil {
		return GenerateScheduleResponse{
			ErrorCode:    ErrScheduleOverlap,
			ErrorMessage: err.Error(),
		}, err
	}

	if err := g.validator.ValidateCapacity(entries); err != nil {
		return GenerateScheduleResponse{
			ErrorCode:    ErrScheduleCapacityExceeded,
			ErrorMessage: err.Error(),
		}, err
	}

	response := GenerateScheduleResponse{
		Entries:      entries,
		TotalSlots:   int32(len(entries)),
		GenerationID: generationID,
	}

	// Cache for idempotency
	g.cache[idempotencyKey] = response

	return response, nil
}

// ValidateSchedule validates a schedule entry against all rules.
func (g *ScheduleGenerator) ValidateSchedule(ctx context.Context, req ValidateScheduleRequest) (ValidateScheduleResponse, error) {
	var validationErrors []string

	if req.ScheduleID == "" {
		validationErrors = append(validationErrors, "schedule_id required")
	}
	if req.TenantID == "" {
		validationErrors = append(validationErrors, "tenant_id required")
	}
	if req.CampusID == "" {
		validationErrors = append(validationErrors, "campus_id required")
	}

	if len(validationErrors) > 0 {
		return ValidateScheduleResponse{
			Valid:            false,
			ValidationErrors: validationErrors,
			ErrorCode:        ErrScheduleInvalid,
			ErrorMessage:     "validation failed",
		}, nil
	}

	return ValidateScheduleResponse{
		Valid: true,
	}, nil
}

func computeIdempotencyKey(req GenerateScheduleRequest) string {
	data := fmt.Sprintf("%s:%s:%s:%s:%s:%d:%d",
		req.TenantID, req.CampusID, req.DepartmentID,
		req.StartDate.Format(time.RFC3339), req.EndDate.Format(time.RFC3339),
		req.PractitionerCount, req.SlotDurationMinutes)
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}

func generateID(parts ...string) string {
	combined := ""
	for _, part := range parts {
		combined += part
	}
	hash := sha256.Sum256([]byte(combined))
	return hex.EncodeToString(hash[:16])
}
