package schedule

import (
	"testing"
)

func TestRollbackService_ValidateRollback(t *testing.T) {
	svc := NewRollbackService()

	// Register an operation
	svc.RegisterOperation("op-001", []string{"change-1", "change-2"}, true, "")

	tests := []struct {
		name        string
		req         *RollbackValidationRequest
		wantCan     bool
		wantReason  string
		wantErr     bool
		errExpected error
	}{
		{
			name:        "valid operation can rollback",
			req:         &RollbackValidationRequest{OperationID: "op-001", Synthetic: true},
			wantCan:     true,
			wantReason:  "",
			wantErr:     false,
		},
		{
			name:        "non-existent operation",
			req:         &RollbackValidationRequest{OperationID: "op-999", Synthetic: true},
			wantCan:     false,
			wantReason:  "operation-not-found",
			wantErr:     false,
		},
		{
			name:        "non-synthetic data rejected",
			req:         &RollbackValidationRequest{OperationID: "op-001", Synthetic: false},
			wantCan:     false,
			wantErr:     true,
			errExpected: ErrRollbackNonSynthetic,
		},
		{
			name:        "empty operation ID",
			req:         &RollbackValidationRequest{OperationID: "", Synthetic: true},
			wantErr:     true,
			errExpected: ErrRollbackInvalid,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			resp, err := svc.ValidateRollback(tt.req)
			if tt.wantErr {
				if err == nil {
					t.Errorf("expected error, got nil")
				} else if err != tt.errExpected {
					t.Errorf("expected error %v, got %v", tt.errExpected, err)
				}
				return
			}
			if err != nil {
				t.Errorf("unexpected error: %v", err)
				return
			}
			if resp.CanRollback != tt.wantCan {
				t.Errorf("CanRollback = %v, want %v", resp.CanRollback, tt.wantCan)
			}
			if resp.Reason != tt.wantReason {
				t.Errorf("Reason = %v, want %v", resp.Reason, tt.wantReason)
			}
		})
	}
}

func TestRollbackService_Rollback(t *testing.T) {
	svc := NewRollbackService()
	svc.RegisterOperation("op-100", []string{"schedule-create", "slot-allocate"}, true, "")

	tests := []struct {
		name    string
		req     *RollbackRequest
		wantErr error
	}{
		{
			name: "successful rollback",
			req: &RollbackRequest{
				OperationID: "op-100",
				Reason:      "user-requested",
				ActorRef:    "Practitioner/actor-syn-001",
				Synthetic:   true,
			},
			wantErr: nil,
		},
		{
			name: "non-synthetic rejected",
			req: &RollbackRequest{
				OperationID: "op-100",
				Reason:      "user-requested",
				ActorRef:    "Practitioner/actor-001",
				Synthetic:   false,
			},
			wantErr: ErrRollbackNonSynthetic,
		},
		{
			name: "empty reason rejected",
			req: &RollbackRequest{
				OperationID: "op-100",
				Reason:      "",
				ActorRef:    "Practitioner/actor-syn-002",
				Synthetic:   true,
			},
			wantErr: ErrRollbackInvalid,
		},
		{
			name: "unknown reason rejected",
			req: &RollbackRequest{
				OperationID: "op-100",
				Reason:      "unknown",
				ActorRef:    "Practitioner/actor-syn-003",
				Synthetic:   true,
			},
			wantErr: ErrRollbackInvalid,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			resp, err := svc.Rollback(tt.req)
			if tt.wantErr != nil {
				if err != tt.wantErr {
					t.Errorf("expected error %v, got %v", tt.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Errorf("unexpected error: %v", err)
				return
			}
			if resp.Status != "completed" {
				t.Errorf("Status = %v, want completed", resp.Status)
			}
			if len(resp.RevertedChanges) != 2 {
				t.Errorf("RevertedChanges length = %v, want 2", len(resp.RevertedChanges))
			}
		})
	}
}

func TestRollbackService_IdempotentRollback(t *testing.T) {
	svc := NewRollbackService()
	svc.RegisterOperation("op-200", []string{"change-a"}, true, "")

	req := &RollbackRequest{
		OperationID:    "op-200",
		Reason:         "duplicate-detected",
		ActorRef:       "Practitioner/actor-syn-100",
		Synthetic:      true,
		IdempotencyKey: "idem-key-001",
	}

	resp1, err := svc.Rollback(req)
	if err != nil {
		t.Fatalf("first rollback failed: %v", err)
	}

	resp2, err := svc.Rollback(req)
	if err != nil {
		t.Fatalf("second rollback failed: %v", err)
	}

	if resp1.RollbackID != resp2.RollbackID {
		t.Errorf("idempotent rollback returned different IDs: %v vs %v", resp1.RollbackID, resp2.RollbackID)
	}
}

func TestRollbackService_DependentOperationsBlock(t *testing.T) {
	svc := NewRollbackService()
	svc.RegisterOperation("op-300", []string{"base-change"}, true, "")
	svc.AddDependentOperation("op-300", "op-301")

	req := &RollbackRequest{
		OperationID: "op-300",
		Reason:      "base-invalid",
		ActorRef:    "Practitioner/actor-syn-200",
		Synthetic:   true,
	}

	_, err := svc.Rollback(req)
	if err != ErrRollbackConflict {
		t.Errorf("expected ErrRollbackConflict, got %v", err)
	}
}

func TestRollbackService_StateValidation(t *testing.T) {
	svc := NewRollbackService()

	tests := []struct {
		name        string
		setupOp     func()
		req         *RollbackRequest
		expectedErr error
	}{
		{
			name: "operation not found",
			setupOp: func() {
				// No operation registered
			},
			req: &RollbackRequest{
				OperationID: "op-404",
				Reason:      "test-reason",
				ActorRef:    "Practitioner/actor-syn-300",
				Synthetic:   true,
			},
			expectedErr: ErrRollbackStateInvalid,
		},
		{
			name: "already rolled back",
			setupOp: func() {
				svc.RegisterOperation("op-500", []string{"test-change"}, true, "")
				svc.operations["op-500"].Status = "rolled-back"
			},
			req: &RollbackRequest{
				OperationID: "op-500",
				Reason:      "retry-rollback",
				ActorRef:    "Practitioner/actor-syn-400",
				Synthetic:   true,
			},
			expectedErr: ErrRollbackConflict,
		},
		{
			name: "operation in progress",
			setupOp: func() {
				svc.RegisterOperation("op-600", []string{"pending-change"}, true, "")
				svc.operations["op-600"].Status = "in-progress"
			},
			req: &RollbackRequest{
				OperationID: "op-600",
				Reason:      "cancel-in-progress",
				ActorRef:    "Practitioner/actor-syn-500",
				Synthetic:   true,
			},
			expectedErr: ErrRollbackStateInvalid,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tt.setupOp()
			_, err := svc.Rollback(tt.req)
			if err != tt.expectedErr {
				t.Errorf("expected error %v, got %v", tt.expectedErr, err)
			}
		})
	}
}
