package forms

import (
	"strings"
	"testing"
	"time"
)

func TestValidatePrintRenderRequest(t *testing.T) {
	baseReq := func() *PrintRenderRequest {
		return &PrintRenderRequest{
			FormID:         "FORM-ABC123",
			SubmissionID:   "SUB-DEF456",
			Template:       "default",
			Format:         "pdf",
			RenderedBy:     "USER-001",
			ActorID:        "ACT-001",
			IdempotencyKey: "idem-001",
			Synthetic:      true,
		}
	}
	
	tests := []struct {
		name    string
		req     *PrintRenderRequest
		wantErr string
	}{
		{
			name:    "nil request",
			req:     nil,
			wantErr: "print-render-request-nil",
		},
		{
			name: "missing synthetic flag",
			req: &PrintRenderRequest{
				FormID:         "FORM-ABC123",
				SubmissionID:   "SUB-DEF456",
				Template:       "default",
				Format:         "pdf",
				RenderedBy:     "USER-001",
				ActorID:        "ACT-001",
				IdempotencyKey: "idem-001",
				Synthetic:      false,
			},
			wantErr: "print-render-synthetic-required",
		},
		{
			name: "missing form ID",
			req: func() *PrintRenderRequest {
				r := baseReq()
				r.FormID = ""
				return r
			}(),
			wantErr: "print-render-form-id-empty",
		},
		{
			name: "missing submission ID",
			req: func() *PrintRenderRequest {
				r := baseReq()
				r.SubmissionID = ""
				return r
			}(),
			wantErr: "print-render-submission-id-empty",
		},
		{
			name: "missing template",
			req: func() *PrintRenderRequest {
				r := baseReq()
				r.Template = ""
				return r
			}(),
			wantErr: "print-render-template-empty",
		},
		{
			name: "missing format",
			req: func() *PrintRenderRequest {
				r := baseReq()
				r.Format = ""
				return r
			}(),
			wantErr: "print-render-format-empty",
		},
		{
			name: "invalid format",
			req: &PrintRenderRequest{
				FormID:         "FORM-SYN-001",
				SubmissionID:   "SUB-SYN-001",
				Template:       "TPL-001",
				Format:         "invalid",
				RenderedBy:     "SYS-001",
				ActorID:        "USR-SYN-001",
				IdempotencyKey: "IDEM-001",
				Synthetic:      true,
			},
			wantErr: "print-render-format-invalid",
		},
		{
			name: "missing rendered by",
			req: func() *PrintRenderRequest {
				r := baseReq()
				r.RenderedBy = ""
				return r
			}(),
			wantErr: "print-render-rendered-by-empty",
		},
		{
			name: "missing actor ID",
			req: &PrintRenderRequest{
				FormID:         "FORM-SYN-001",
				SubmissionID:   "SUB-SYN-001",
				Template:       "TPL-001",
				Format:         "pdf",
				RenderedBy:     "SYS-001",
				ActorID:        "",
				IdempotencyKey: "IDEM-001",
				Synthetic:      true,
			},
			wantErr: "print-render-actor-required",
		},
		{
			name: "missing idempotency key",
			req: func() *PrintRenderRequest {
				r := baseReq()
				r.IdempotencyKey = ""
				return r
			}(),
			wantErr: "print-render-idempotency-required",
		},
		{
			name: "valid request",
			req: &PrintRenderRequest{
				FormID:         "FORM-ABC123",
				SubmissionID:   "SUB-DEF456",
				Template:       "default",
				Format:         "pdf",
				RenderedBy:     "USER-001",
				ActorID:        "ACT-001",
				IdempotencyKey: "idem-001",
				Synthetic:      true,
			},
			wantErr: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidatePrintRenderRequest(tt.req)
			if tt.wantErr == "" {
				if err != nil {
					t.Errorf("expected no error, got %v", err)
				}
			} else {
				if err == nil {
					t.Errorf("expected error %s, got nil", tt.wantErr)
				} else if !strings.Contains(err.Error(), tt.wantErr) {
					t.Errorf("expected error %s, got %v", tt.wantErr, err)
				}
			}
		})
	}
}

func TestValidateRenderFormat(t *testing.T) {
	tests := []struct {
		name    string
		format  string
		wantErr string
	}{
		{
			name:    "empty format",
			format:  "",
			wantErr: "print-render-format-empty",
		},
		{
			name:    "invalid format",
			format:  "invalid",
			wantErr: "print-render-format-invalid",
		},
		{
			name:    "valid pdf format",
			format:  "pdf",
			wantErr: "",
		},
		{
			name:    "valid html format",
			format:  "html",
			wantErr: "",
		},
		{
			name:    "valid docx format",
			format:  "docx",
			wantErr: "",
		},
		{
			name:    "case insensitive pdf",
			format:  "PDF",
			wantErr: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateRenderFormat(tt.format)
			if tt.wantErr == "" {
				if err != nil {
					t.Errorf("expected no error, got %v", err)
				}
			} else {
				if err == nil {
					t.Errorf("expected error %s, got nil", tt.wantErr)
				} else if !strings.Contains(err.Error(), tt.wantErr) {
					t.Errorf("expected error %s, got %v", tt.wantErr, err)
				}
			}
		})
	}
}

func TestValidateRenderOptions(t *testing.T) {
	tests := []struct {
		name    string
		options map[string]interface{}
		wantErr string
	}{
		{
			name:    "nil options",
			options: nil,
			wantErr: "",
		},
		{
			name:    "empty options",
			options: map[string]interface{}{},
			wantErr: "",
		},
		{
			name: "valid options",
			options: map[string]interface{}{
				"page_size":   "A4",
				"orientation": "portrait",
			},
			wantErr: "",
		},
		{
			name: "prohibited PHI key rejection",
			options: map[string]interface{}{
				"page_size":  "A4",
				"patient_id": "P12345",
			},
			wantErr: "print-render-prohibited-key",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateRenderOptions(tt.options)
			if tt.wantErr == "" {
				if err != nil {
					t.Errorf("expected no error, got %v", err)
				}
			} else {
				if err == nil {
					t.Errorf("expected error %s, got nil", tt.wantErr)
				} else if !strings.Contains(err.Error(), tt.wantErr) {
					t.Errorf("expected error %s, got %v", tt.wantErr, err)
				}
			}
		})
	}
}

func TestValidateRenderID(t *testing.T) {
	tests := []struct {
		name     string
		renderID string
		wantErr  string
	}{
		{
			name:     "empty render ID",
			renderID: "",
			wantErr:  "print-render-id-empty",
		},
		{
			name:     "invalid prefix",
			renderID: "INVALID-123456789012",
			wantErr:  "print-render-id-invalid-prefix",
		},
		{
			name:     "invalid length",
			renderID: "RND-SHORT",
			wantErr:  "print-render-id-invalid-length",
		},
		{
			name:     "valid render ID",
			renderID: "RND-ABCD1234EFGH5678",
			wantErr:  "",
		},
	}

	for i, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			result := ValidateRenderID(tc.renderID)
			hasError := (result != nil)
			expectError := (tc.wantErr != "")
			if !expectError && hasError {
				t.Errorf("[case %d] expected no error, got %v", i, result)
			} else if expectError && !hasError {
				t.Errorf("[case %d] expected error %s, got nil", i, tc.wantErr)
			} else if expectError && hasError && !strings.Contains(result.Error(), tc.wantErr) {
				t.Errorf("[case %d] expected error %s, got %v", i, tc.wantErr, result)
			}
		})
	}
}

func TestGenerateRenderID(t *testing.T) {
	id1 := GenerateRenderID("FORM-001", "SUB-001")

	if !strings.HasPrefix(id1, "RND-") {
		t.Errorf("expected ID to start with RND-, got %s", id1)
	}
	if len(id1) != 20 {
		t.Errorf("expected ID length 20, got %d", len(id1))
	}
	
	time.Sleep(2 * time.Millisecond)
	id2 := GenerateRenderID("FORM-001", "SUB-001")
	if id1 == id2 {
		t.Error("expected different IDs for same input at different times")
	}
	
	id3 := GenerateRenderID("FORM-002", "SUB-002")
	if id1 == id3 {
		t.Error("expected different IDs for different inputs")
	}
}

func TestCalculateRenderChecksum(t *testing.T) {
	checksum1 := CalculateRenderChecksum("FORM-001", "SUB-001", "default", "pdf")
	checksum2 := CalculateRenderChecksum("FORM-001", "SUB-001", "default", "pdf")
	checksum3 := CalculateRenderChecksum("FORM-002", "SUB-001", "default", "pdf")

	if checksum1 != checksum2 {
		t.Error("expected same checksum for same inputs")
	}
	if checksum1 == checksum3 {
		t.Error("expected different checksums for different inputs")
	}
	if len(checksum1) != 64 {
		t.Errorf("expected checksum length 64, got %d", len(checksum1))
	}
}

func TestRenderForm(t *testing.T) {
	renderStore = make(map[string]*RenderEntry)
	idempotencyStore = make(map[string]string)

	req := &PrintRenderRequest{
		FormID:         "FORM-TEST001",
		SubmissionID:   "SUB-TEST001",
		Template:       "default",
		Format:         "pdf",
		RenderedBy:     "USER-001",
		ActorID:        "ACT-001",
		IdempotencyKey: "idem-render-001",
		Synthetic:      true,
	}

	resp, err := RenderForm(req)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.RenderID == "" {
		t.Error("expected render ID to be set")
	}
	if resp.Status != "rendered" {
		t.Errorf("expected status rendered, got %s", resp.Status)
	}
	if resp.Format != "pdf" {
		t.Errorf("expected format pdf, got %s", resp.Format)
	}
	if !strings.Contains(resp.OutputURL, resp.RenderID) {
		t.Error("expected output URL to contain render ID")
	}
}

func TestRenderFormIdempotency(t *testing.T) {
	renderStore = make(map[string]*RenderEntry)
	idempotencyStore = make(map[string]string)

	req := &PrintRenderRequest{
		FormID:         "FORM-TEST002",
		SubmissionID:   "SUB-TEST002",
		Template:       "default",
		Format:         "html",
		RenderedBy:     "USER-002",
		ActorID:        "ACT-002",
		IdempotencyKey: "idem-render-002",
		Synthetic:      true,
	}

	resp1, err1 := RenderForm(req)
	if err1 != nil {
		t.Fatalf("unexpected error on first render: %v", err1)
	}

	resp2, err2 := RenderForm(req)
	if err2 != nil {
		t.Fatalf("unexpected error on second render: %v", err2)
	}

	if resp1.RenderID != resp2.RenderID {
		t.Error("expected same render ID for idempotent requests")
	}
	if resp1.Status != resp2.Status {
		t.Error("expected same status for idempotent requests")
	}
}

func TestGetRender(t *testing.T) {
	renderStore = make(map[string]*RenderEntry)
	idempotencyStore = make(map[string]string)

	req := &PrintRenderRequest{
		FormID:         "FORM-TEST003",
		SubmissionID:   "SUB-TEST003",
		Template:       "default",
		Format:         "docx",
		RenderedBy:     "USER-003",
		ActorID:        "ACT-003",
		IdempotencyKey: "idem-render-003",
		Synthetic:      true,
	}

	createResp, err := RenderForm(req)
	if err != nil {
		t.Fatalf("unexpected error creating render: %v", err)
	}

	getResp, err := GetRender(createResp.RenderID)
	if err != nil {
		t.Fatalf("unexpected error getting render: %v", err)
	}
	if getResp.RenderID != createResp.RenderID {
		t.Error("expected same render ID")
	}
	if getResp.Format != "docx" {
		t.Errorf("expected format docx, got %s", getResp.Format)
	}
}

func TestGetRenderNotFound(t *testing.T) {
	renderStore = make(map[string]*RenderEntry)

	_, err := GetRender("RND-NOTFOUND12345678")
	if err == nil {
		t.Error("expected error for non-existent render")
	}
	if !strings.Contains(err.Error(), "print-render-not-found") {
		t.Errorf("expected not found error, got %v", err)
	}
}

func TestDeleteRender(t *testing.T) {
	renderStore = make(map[string]*RenderEntry)
	idempotencyStore = make(map[string]string)

	req := &PrintRenderRequest{
		FormID:         "FORM-TEST004",
		SubmissionID:   "SUB-TEST004",
		Template:       "default",
		Format:         "pdf",
		RenderedBy:     "USER-004",
		ActorID:        "ACT-004",
		IdempotencyKey: "idem-render-004",
		Synthetic:      true,
	}

	resp, err := RenderForm(req)
	if err != nil {
		t.Fatalf("unexpected error creating render: %v", err)
	}

	err = DeleteRender(resp.RenderID, "ACT-004")
	if err != nil {
		t.Fatalf("unexpected error deleting render: %v", err)
	}

	_, err = GetRender(resp.RenderID)
	if err == nil {
		t.Error("expected error getting deleted render")
	}
}

func TestDeleteRenderUnauthorized(t *testing.T) {
	renderStore = make(map[string]*RenderEntry)
	idempotencyStore = make(map[string]string)

	req := &PrintRenderRequest{
		FormID:         "FORM-TEST005",
		SubmissionID:   "SUB-TEST005",
		Template:       "default",
		Format:         "pdf",
		RenderedBy:     "USER-005",
		ActorID:        "ACT-005",
		IdempotencyKey: "idem-render-005",
		Synthetic:      true,
	}

	resp, err := RenderForm(req)
	if err != nil {
		t.Fatalf("unexpected error creating render: %v", err)
	}

	err = DeleteRender(resp.RenderID, "WRONG-ACTOR")
	if err == nil {
		t.Error("expected unauthorized error")
	}
	if !strings.Contains(err.Error(), "print-render-unauthorized") {
		t.Errorf("expected unauthorized error, got %v", err)
	}
}

func TestProcessPrintRender(t *testing.T) {
	renderStore = make(map[string]*RenderEntry)
	idempotencyStore = make(map[string]string)

	req := &PrintRenderRequest{
		FormID:         "FORM-TEST006",
		SubmissionID:   "SUB-TEST006",
		Template:       "default",
		Format:         "pdf",
		RenderedBy:     "USER-006",
		ActorID:        "ACT-006",
		IdempotencyKey: "idem-render-006",
		Synthetic:      true,
	}

	resp, err := ProcessPrintRender(req)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resp.Status != "rendered" {
		t.Errorf("expected status rendered, got %s", resp.Status)
	}
}
