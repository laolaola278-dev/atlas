package schedule

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"time"
)

type RollbackRequest struct {
	OperationID    string
	Reason         string
	ActorRef       string
	Synthetic      bool
	IdempotencyKey string
}

type RollbackResponse struct {
	RollbackID      string
	Status          string
	Timestamp       string
	RevertedChanges []string
}

type RollbackValidationRequest struct {
	OperationID string
	Synthetic   bool
}

type RollbackValidationResponse struct {
	CanRollback         bool
	Reason              string
	DependentOperations []string
}

type RollbackAuditEntry struct {
	RollbackID     string
	OperationID    string
	ActorRef       string
	Timestamp      string
	Reason         string
	Status         string
	Synthetic      bool
	IdempotencyKey string
}

var (
	ErrRollbackInvalid       = errors.New("rollback-invalid")
	ErrRollbackForbidden     = errors.New("rollback-forbidden")
	ErrRollbackConflict      = errors.New("rollback-conflict")
	ErrRollbackStateInvalid  = errors.New("rollback-state-invalid")
	ErrRollbackResultUnknown = errors.New("rollback-result-unknown")
	ErrRollbackNonSynthetic  = errors.New("rollback-non-synthetic")
)

type RollbackService struct {
	operations map[string]*OperationState
	rollbacks  map[string]*RollbackAuditEntry
}

type OperationState struct {
	ID              string
	Status          string
	Changes         []string
	DependentOps    []string
	CanRollback     bool
	RollbackBlocked string
}

func NewRollbackService() *RollbackService {
	return &RollbackService{
		operations: make(map[string]*OperationState),
		rollbacks:  make(map[string]*RollbackAuditEntry),
	}
}

func (s *RollbackService) ValidateRollback(req *RollbackValidationRequest) (*RollbackValidationResponse, error) {
	if !req.Synthetic {
		return nil, ErrRollbackNonSynthetic
	}
	if req.OperationID == "" {
		return nil, ErrRollbackInvalid
	}
	op, exists := s.operations[req.OperationID]
	if !exists {
		return &RollbackValidationResponse{CanRollback: false, Reason: "operation-not-found"}, nil
	}
	if !op.CanRollback {
		return &RollbackValidationResponse{CanRollback: false, Reason: op.RollbackBlocked, DependentOperations: op.DependentOps}, nil
	}
	return &RollbackValidationResponse{CanRollback: true, DependentOperations: op.DependentOps}, nil
}

func (s *RollbackService) Rollback(req *RollbackRequest) (*RollbackResponse, error) {
	if !req.Synthetic {
		return nil, ErrRollbackNonSynthetic
	}
	if req.IdempotencyKey != "" {
		if existing := s.findRollbackByIdempotencyKey(req.IdempotencyKey); existing != nil {
			return &RollbackResponse{RollbackID: existing.RollbackID, Status: existing.Status, Timestamp: existing.Timestamp, RevertedChanges: s.getRevertedChanges(existing.OperationID)}, nil
		}
	}
	if err := s.validateRollbackRequest(req); err != nil {
		return nil, err
	}
	valReq := &RollbackValidationRequest{OperationID: req.OperationID, Synthetic: req.Synthetic}
	valResp, err := s.ValidateRollback(valReq)
	if err != nil {
		return nil, err
	}
	if !valResp.CanRollback {
		if valResp.Reason == "dependent-operations-exist" {
			return nil, ErrRollbackConflict
		}
		return nil, ErrRollbackForbidden
	}
	rollbackID := s.generateRollbackID(req)
	op := s.operations[req.OperationID]
	revertedChanges := op.Changes
	timestamp := time.Now().UTC().Format(time.RFC3339)
	auditEntry := &RollbackAuditEntry{RollbackID: rollbackID, OperationID: req.OperationID, ActorRef: req.ActorRef, Timestamp: timestamp, Reason: req.Reason, Status: "completed", Synthetic: req.Synthetic, IdempotencyKey: req.IdempotencyKey}
	s.rollbacks[rollbackID] = auditEntry
	op.Status = "rolled-back"
	return &RollbackResponse{RollbackID: rollbackID, Status: "completed", Timestamp: timestamp, RevertedChanges: revertedChanges}, nil
}

func (s *RollbackService) validateRollbackRequest(req *RollbackRequest) error {
	if req.OperationID == "" || req.Reason == "" || req.Reason == "unknown" || req.Reason == "unspecified" || req.ActorRef == "" {
		return ErrRollbackInvalid
	}
	op, exists := s.operations[req.OperationID]
	if !exists {
		return ErrRollbackStateInvalid
	}
	if op.Status == "rolled-back" {
		return ErrRollbackConflict
	}
	if op.Status == "in-progress" {
		return ErrRollbackStateInvalid
	}
	return nil
}

func (s *RollbackService) generateRollbackID(req *RollbackRequest) string {
	data := fmt.Sprintf("%s:%s:%s:%d", req.OperationID, req.ActorRef, req.Reason, time.Now().UnixNano())
	hash := sha256.Sum256([]byte(data))
	return "rb-" + hex.EncodeToString(hash[:])[:16]
}

func (s *RollbackService) findRollbackByIdempotencyKey(key string) *RollbackAuditEntry {
	for _, entry := range s.rollbacks {
		if entry.IdempotencyKey == key {
			return entry
		}
	}
	return nil
}

func (s *RollbackService) computeIdempotencyKey(entry *RollbackAuditEntry) string {
	data := fmt.Sprintf("%s:%s:%s", entry.OperationID, entry.ActorRef, entry.Reason)
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])[:32]
}

func (s *RollbackService) getRevertedChanges(operationID string) []string {
	if op, exists := s.operations[operationID]; exists {
		return op.Changes
	}
	return []string{}
}

func (s *RollbackService) RegisterOperation(id string, changes []string, canRollback bool, blockedReason string) {
	s.operations[id] = &OperationState{ID: id, Status: "completed", Changes: changes, DependentOps: []string{}, CanRollback: canRollback, RollbackBlocked: blockedReason}
}

func (s *RollbackService) AddDependentOperation(operationID string, dependentID string) {
	if op, exists := s.operations[operationID]; exists {
		op.DependentOps = append(op.DependentOps, dependentID)
		op.CanRollback = false
		op.RollbackBlocked = "dependent-operations-exist"
	}
}
