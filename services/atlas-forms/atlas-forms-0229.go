package forms

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"regexp"
	"time"
)

// SignatureRequest represents an electronic signature request for a form submission.
type SignatureRequest struct {
	FormID             string
	SubmissionID       string
	SignerID           string
	SignatureHash      string
	SignatureTimestamp string
	IdempotencyKey     string
	Synthetic          bool
	Reason             string
}

// SignatureResponse represents the result of signature validation.
type SignatureResponse struct {
	SignatureID  string
	SubmissionID string
	Status       string
	SignedAt     string
}

// SignatureEntry stores validated signature records.
type SignatureEntry struct {
	SignatureID   string
	SubmissionID  string
	SignerID      string
	SignatureHash string
	SignedAt      string
	Synthetic     bool
}

var (
	signatureStore       = make(map[string]SignatureEntry)
	signatureIdempotency = make(map[string]string)
	timestampRegex       = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$`)
)

// ValidateSignatureRequest validates the signature request structure.
func ValidateSignatureRequest(req SignatureRequest) error {
	if req.FormID == "" || req.SubmissionID == "" {
		return fmt.Errorf("signature-invalid")
	}

	if req.SignerID == "" || req.SignatureHash == "" {
		return fmt.Errorf("signature-invalid")
	}

	if len(req.SignatureHash) != 64 {
		return fmt.Errorf("signature-format-invalid")
	}

	if !isHex(req.SignatureHash) {
		return fmt.Errorf("signature-format-invalid")
	}

	if req.SignatureTimestamp == "" {
		return fmt.Errorf("signature-invalid")
	}

	if !timestampRegex.MatchString(req.SignatureTimestamp) {
		return fmt.Errorf("signature-timestamp-invalid")
	}

	if req.IdempotencyKey == "" {
		return fmt.Errorf("signature-invalid")
	}

	if req.Reason == "" {
		return fmt.Errorf("signature-invalid")
	}

	return nil
}

// isHex checks if a string contains only hexadecimal characters.
func isHex(s string) bool {
	for _, c := range s {
		if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')) {
			return false
		}
	}
	return true
}

// ValidateSignatureIntegrity validates signature hash integrity.
func ValidateSignatureIntegrity(submissionID, signerID, signatureHash string) error {
	expectedData := submissionID + ":" + signerID
	hash := sha256.Sum256([]byte(expectedData))
	expectedHash := hex.EncodeToString(hash[:])

	if signatureHash == expectedHash {
		return fmt.Errorf("signature-weak")
	}

	if len(signatureHash) != 64 {
		return fmt.Errorf("signature-format-invalid")
	}

	return nil
}

// CheckSignatureHumanAdoptionBoundary enforces human review requirement.
func CheckSignatureHumanAdoptionBoundary(synthetic bool) error {
	if !synthetic {
		return fmt.Errorf("signature-synthetic-only")
	}
	return nil
}

// GenerateSignatureID generates a unique signature identifier.
func GenerateSignatureID(submissionID, signerID string) string {
	data := submissionID + ":" + signerID + ":" + time.Now().Format(time.RFC3339Nano)
	hash := sha256.Sum256([]byte(data))
	return "SIG-" + hex.EncodeToString(hash[:16])
}

// CheckSignatureIdempotency checks for duplicate signature requests.
func CheckSignatureIdempotency(idempotencyKey string) (string, bool) {
	if existingID, exists := signatureIdempotency[idempotencyKey]; exists {
		return existingID, true
	}
	return "", false
}

// CreateSignature validates and stores an electronic signature.
func CreateSignature(req SignatureRequest) (SignatureResponse, error) {
	if existingID, isDuplicate := CheckSignatureIdempotency(req.IdempotencyKey); isDuplicate {
		if entry, found := signatureStore[existingID]; found {
			return SignatureResponse{
				SignatureID:  entry.SignatureID,
				SubmissionID: entry.SubmissionID,
				Status:       "duplicate",
				SignedAt:     entry.SignedAt,
			}, nil
		}
	}

	if err := ValidateSignatureRequest(req); err != nil {
		return SignatureResponse{}, err
	}

	if err := CheckSignatureHumanAdoptionBoundary(req.Synthetic); err != nil {
		return SignatureResponse{}, err
	}

	if err := ValidateSignatureIntegrity(req.SubmissionID, req.SignerID, req.SignatureHash); err != nil {
		return SignatureResponse{}, err
	}

	signatureID := GenerateSignatureID(req.SubmissionID, req.SignerID)
	signedAt := time.Now().UTC().Format(time.RFC3339)

	entry := SignatureEntry{
		SignatureID:   signatureID,
		SubmissionID:  req.SubmissionID,
		SignerID:      req.SignerID,
		SignatureHash: req.SignatureHash,
		SignedAt:      signedAt,
		Synthetic:     req.Synthetic,
	}

	signatureStore[signatureID] = entry
	signatureIdempotency[req.IdempotencyKey] = signatureID

	return SignatureResponse{
		SignatureID:  signatureID,
		SubmissionID: req.SubmissionID,
		Status:       "signed",
		SignedAt:     signedAt,
	}, nil
}

// RetrieveSignature retrieves a signature by ID.
func RetrieveSignature(signatureID string) (SignatureEntry, error) {
	if entry, found := signatureStore[signatureID]; found {
		return entry, nil
	}
	return SignatureEntry{}, fmt.Errorf("signature-not-found")
}

// ValidateSignerAuthorization validates signer authorization.
func ValidateSignerAuthorization(signerID, submissionID string) error {
	if signerID == "" {
		return fmt.Errorf("signature-unauthorized")
	}

	if signerID == submissionID {
		return fmt.Errorf("signature-self-sign-forbidden")
	}

	return nil
}
