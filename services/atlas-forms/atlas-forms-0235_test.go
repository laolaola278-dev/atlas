package forms

import (
	"crypto/sha256"
	"encoding/hex"
	"strings"
	"testing"
	"time"
)

// Helper function to check error matches expected message
func checkError(t *testing.T, err error, expected string) {
	t.Helper()
	if err == nil {
		t.Errorf("Expected error %s, got nil", expected)
		return
	}
	if err.Error() != expected {
		t.Errorf("Expected error %s, got %v", expected, err)
	}
}

// Helper function to create a base OfflineCacheRequest for tests
func baseStoreReq() *OfflineCacheRequest {
	hash := sha256.Sum256([]byte("test-data"))
	return &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-id",
		CacheKey:       "cache-key",
		DataHash:       hex.EncodeToString(hash[:]),
		EncryptedData:  []byte("encrypted"),
		CacheTTLHours:  24,
		IdempotencyKey: "idem-key",
	}
}

func TestStoreOfflineCache_Success(t *testing.T) {
	hash := sha256.Sum256([]byte("test-data"))
	hashStr := hex.EncodeToString(hash[:])

	req := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-synthetic-001",
		CacheKey:       "cache-key-synthetic-001",
		DataHash:       hashStr,
		EncryptedData:  []byte("encrypted-payload"),
		CacheTTLHours:  24,
		IdempotencyKey: "idem-cache-001",
	}

	resp, err := StoreOfflineCache(req)
	if err != nil {
		t.Fatalf("StoreOfflineCache failed: %v", err)
	}
	if resp.CacheID == "" {
		t.Error("Expected non-empty CacheID")
	}
	if resp.Status != "cached" {
		t.Errorf("Expected status 'cached', got %s", resp.Status)
	}
	if resp.DataHashStored != hashStr {
		t.Errorf("Expected hash %s, got %s", hashStr, resp.DataHashStored)
	}
}

func TestStoreOfflineCache_NilRequest(t *testing.T) {
	_, err := StoreOfflineCache(nil)
	checkError(t, err, "offline-cache-request-nil")
}

func TestStoreOfflineCache_SyntheticRequired(t *testing.T) {
	hash := sha256.Sum256([]byte("test"))
	request := &OfflineCacheRequest{
		Synthetic:      false,
		FormID:         "form-001",
		CacheKey:       "key-001",
		DataHash:       hex.EncodeToString(hash[:]),
		EncryptedData:  []byte("data"),
		CacheTTLHours:  24,
		IdempotencyKey: "idem-001",
	}

	_, err := StoreOfflineCache(request)
	checkError(t, err, "offline-cache-synthetic-required")
}

func TestStoreOfflineCache_FormIDEmpty(t *testing.T) {
	request := baseStoreReq()
	request.FormID = ""
	request.IdempotencyKey = "idem-002"

	_, err := StoreOfflineCache(request)
	checkError(t, err, "offline-cache-form-id-empty")
}

func TestStoreOfflineCache_CacheKeyEmpty(t *testing.T) {
	hash := sha256.Sum256([]byte("test"))
	request := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-002",
		CacheKey:       "",
		DataHash:       hex.EncodeToString(hash[:]),
		EncryptedData:  []byte("data"),
		CacheTTLHours:  24,
		IdempotencyKey: "idem-003",
	}

	_, err := StoreOfflineCache(request)
	checkError(t, err, "offline-cache-key-empty")
}

func TestStoreOfflineCache_DataHashEmpty(t *testing.T) {
	request := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-003",
		CacheKey:       "key-003",
		DataHash:       "",
		EncryptedData:  []byte("data"),
		CacheTTLHours:  24,
		IdempotencyKey: "idem-004",
	}

	_, err := StoreOfflineCache(request)
	checkError(t, err, "offline-cache-data-hash-empty")
}

func TestStoreOfflineCache_DataHashInvalid(t *testing.T) {
	request := baseStoreReq()
	request.DataHash = "short-hash"
	request.IdempotencyKey = "idem-005"

	_, err := StoreOfflineCache(request)
	checkError(t, err, "offline-cache-data-hash-invalid")
}

func TestStoreOfflineCache_EncryptedDataEmpty(t *testing.T) {
	hash := sha256.Sum256([]byte("test"))
	request := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-005",
		CacheKey:       "key-005",
		DataHash:       hex.EncodeToString(hash[:]),
		EncryptedData:  []byte{},
		CacheTTLHours:  24,
		IdempotencyKey: "idem-006",
	}

	_, err := StoreOfflineCache(request)
	checkError(t, err, "offline-cache-encrypted-data-empty")
}

func TestStoreOfflineCache_TTLInvalid(t *testing.T) {
	hash := sha256.Sum256([]byte("test"))
	
	testCases := []struct {
		name string
		ttl  int
	}{
		{"zero TTL", 0},
		{"negative TTL", -1},
		{"exceeds maximum", 200},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			request := &OfflineCacheRequest{
				Synthetic:      true,
				FormID:         "form-ttl",
				CacheKey:       "key-ttl",
				DataHash:       hex.EncodeToString(hash[:]),
				EncryptedData:  []byte("data"),
				CacheTTLHours:  tc.ttl,
				IdempotencyKey: "idem-ttl-" + tc.name,
			}

			_, err := StoreOfflineCache(request)
			checkError(t, err, "offline-cache-ttl-invalid")
		})
	}
}

func TestStoreOfflineCache_IdempotencyRequired(t *testing.T) {
	hash := sha256.Sum256([]byte("test"))
	request := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-006",
		CacheKey:       "key-006",
		DataHash:       hex.EncodeToString(hash[:]),
		EncryptedData:  []byte("data"),
		CacheTTLHours:  24,
		IdempotencyKey: "",
	}

	_, err := StoreOfflineCache(request)
	checkError(t, err, "offline-cache-idempotency-required")
}

func TestStoreOfflineCache_PHIPatternDetected(t *testing.T) {
	hash := sha256.Sum256([]byte("test"))
	
	phiKeys := []string{
		"patient-id-key",
		"cache-name-field",
		"user-phone-cache",
		"address-cache-key",
		"birth-date-field",
		"ssn-identifier",
		"email-field",
	}

	for idx, key := range phiKeys {
		t.Run(key, func(t *testing.T) {
			request := &OfflineCacheRequest{
				Synthetic:      true,
				FormID:         "form-phi",
				CacheKey:       key,
				DataHash:       hex.EncodeToString(hash[:]),
				EncryptedData:  []byte("data"),
				CacheTTLHours:  24,
				IdempotencyKey: "idem-phi-" + string(rune(idx)),
			}

		_, err := StoreOfflineCache(request)
		if err == nil || err.Error() != "offline-cache-phi-pattern-detected" {
			t.Errorf("Key %s: expected offline-cache-phi-pattern-detected, got %v", key, err)
		}
	})
}
}

func TestStoreOfflineCache_Idempotency(t *testing.T) {
	hash := sha256.Sum256([]byte("idempotent-test"))
	hashStr := hex.EncodeToString(hash[:])

	request := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-idem",
		CacheKey:       "key-idem",
		DataHash:       hashStr,
		EncryptedData:  []byte("idempotent-data"),
		CacheTTLHours:  48,
		IdempotencyKey: "idem-repeat-key",
	}

	resp1, err1 := StoreOfflineCache(request)
	if err1 != nil {
		t.Fatalf("First call failed: %v", err1)
	}

	resp2, err2 := StoreOfflineCache(request)
	if err2 != nil {
		t.Fatalf("Second call failed: %v", err2)
	}

	if resp1.CacheID != resp2.CacheID {
		t.Errorf("Idempotency violated: %s != %s", resp1.CacheID, resp2.CacheID)
	}
}

func TestRetrieveOfflineCache_Success(t *testing.T) {
	hash := sha256.Sum256([]byte("retrieve-test"))
	hashStr := hex.EncodeToString(hash[:])

	storeReq := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-retrieve",
		CacheKey:       "key-retrieve",
		DataHash:       hashStr,
		EncryptedData:  []byte("stored-data"),
		CacheTTLHours:  24,
		IdempotencyKey: "idem-retrieve",
	}

	storeResp, err := StoreOfflineCache(storeReq)
	if err != nil {
		t.Fatalf("StoreOfflineCache failed: %v", err)
	}

	retrieveReq := &OfflineCacheRetrievalRequest{
		Synthetic: true,
		CacheID:   storeResp.CacheID,
		CacheKey:  "key-retrieve",
	}

	retrieveResp, err := RetrieveOfflineCache(retrieveReq)
	if err != nil {
		t.Fatalf("RetrieveOfflineCache failed: %v", err)
	}
	if retrieveResp.CacheID != storeResp.CacheID {
		t.Errorf("Expected CacheID %s, got %s", storeResp.CacheID, retrieveResp.CacheID)
	}
	if retrieveResp.DataHash != hashStr {
		t.Errorf("Expected hash %s, got %s", hashStr, retrieveResp.DataHash)
	}
	if retrieveResp.Status != "retrieved" {
		t.Errorf("Expected status 'retrieved', got %s", retrieveResp.Status)
	}
}

func TestRetrieveOfflineCache_NilRequest(t *testing.T) {
	_, err := RetrieveOfflineCache(nil)
	checkError(t, err, "offline-cache-retrieval-request-nil")
}

func TestRetrieveOfflineCache_SyntheticRequired(t *testing.T) {
	retrieveReq := &OfflineCacheRetrievalRequest{
		Synthetic: false,
		CacheID:   "cache-001",
		CacheKey:  "key-001",
	}

	_, err := RetrieveOfflineCache(retrieveReq)
	checkError(t, err, "offline-cache-retrieval-synthetic-required")
}

func TestRetrieveOfflineCache_IDEmpty(t *testing.T) {
	retrieveReq := &OfflineCacheRetrievalRequest{
		Synthetic: true,
		CacheID:   "",
		CacheKey:  "key-002",
	}

	_, err := RetrieveOfflineCache(retrieveReq)
	checkError(t, err, "offline-cache-retrieval-id-empty")
}

func TestRetrieveOfflineCache_KeyEmpty(t *testing.T) {
	retrieveReq := &OfflineCacheRetrievalRequest{
		Synthetic: true,
		CacheID:   "cache-002",
		CacheKey:  "",
	}

	_, err := RetrieveOfflineCache(retrieveReq)
	checkError(t, err, "offline-cache-retrieval-key-empty")
}

func TestRetrieveOfflineCache_NotFound(t *testing.T) {
	retrieveReq := &OfflineCacheRetrievalRequest{
		Synthetic: true,
		CacheID:   "nonexistent-cache-id",
		CacheKey:  "key-003",
	}

	_, err := RetrieveOfflineCache(retrieveReq)
	checkError(t, err, "offline-cache-not-found")
}

func TestRetrieveOfflineCache_Expired(t *testing.T) {
	hash := sha256.Sum256([]byte("expired-test"))
	hashStr := hex.EncodeToString(hash[:])

	storeReq := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-expired",
		CacheKey:       "key-expired",
		DataHash:       hashStr,
		EncryptedData:  []byte("expired-data"),
		CacheTTLHours:  1,
		IdempotencyKey: "idem-expired",
	}

	storeResp, err := StoreOfflineCache(storeReq)
	if err != nil {
		t.Fatalf("StoreOfflineCache failed: %v", err)
	}

	offlineCacheMu.Lock()
	if cached, exists := offlineCacheStore[storeResp.CacheID]; exists {
		cached.ExpiresAt = time.Now().UTC().Add(-1 * time.Hour)
	}
	offlineCacheMu.Unlock()

	retrieveReq := &OfflineCacheRetrievalRequest{
		Synthetic: true,
		CacheID:   storeResp.CacheID,
		CacheKey:  "key-expired",
	}

	_, err = RetrieveOfflineCache(retrieveReq)
	checkError(t, err, "offline-cache-expired")
}

func TestInvalidateOfflineCache_Success(t *testing.T) {
	hash := sha256.Sum256([]byte("invalidate-test"))
	hashStr := hex.EncodeToString(hash[:])

	storeReq := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-invalidate",
		CacheKey:       "key-invalidate",
		DataHash:       hashStr,
		EncryptedData:  []byte("invalidate-data"),
		CacheTTLHours:  24,
		IdempotencyKey: "idem-invalidate",
	}

	storeResp, err := StoreOfflineCache(storeReq)
	if err != nil {
		t.Fatalf("StoreOfflineCache failed: %v", err)
	}

	err = InvalidateOfflineCache(true, storeResp.CacheID)
	if err != nil {
		t.Fatalf("InvalidateOfflineCache failed: %v", err)
	}

	retrieveReq := &OfflineCacheRetrievalRequest{
		Synthetic: true,
		CacheID:   storeResp.CacheID,
		CacheKey:  "key-invalidate",
	}

	_, err = RetrieveOfflineCache(retrieveReq)
	if err == nil || err.Error() != "offline-cache-not-found" {
		t.Errorf("Expected cache to be invalidated, got %v", err)
	}
}

func TestInvalidateOfflineCache_SyntheticRequired(t *testing.T) {
	err := InvalidateOfflineCache(false, "cache-id")
	checkError(t, err, "offline-cache-invalidation-synthetic-required")
}

func TestInvalidateOfflineCache_IDEmpty(t *testing.T) {
	err := InvalidateOfflineCache(true, "")
	checkError(t, err, "offline-cache-invalidation-id-empty")
}

func TestInvalidateOfflineCache_NotFound(t *testing.T) {
	err := InvalidateOfflineCache(true, "nonexistent-id")
	checkError(t, err, "offline-cache-invalidation-not-found")
}

func TestListExpiredCaches_Success(t *testing.T) {
	hash1 := sha256.Sum256([]byte("list-test-1"))
	hash2 := sha256.Sum256([]byte("list-test-2"))

	req1 := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-list-1",
		CacheKey:       "key-list-1",
		DataHash:       hex.EncodeToString(hash1[:]),
		EncryptedData:  []byte("data-1"),
		CacheTTLHours:  24,
		IdempotencyKey: "idem-list-1",
	}

	resp1, _ := StoreOfflineCache(req1)

	req2 := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-list-2",
		CacheKey:       "key-list-2",
		DataHash:       hex.EncodeToString(hash2[:]),
		EncryptedData:  []byte("data-2"),
		CacheTTLHours:  1,
		IdempotencyKey: "idem-list-2",
	}

	resp2, _ := StoreOfflineCache(req2)

	offlineCacheMu.Lock()
	if cached, exists := offlineCacheStore[resp2.CacheID]; exists {
		cached.ExpiresAt = time.Now().UTC().Add(-1 * time.Hour)
	}
	offlineCacheMu.Unlock()

	expired, err := ListExpiredCaches(true)
	if err != nil {
		t.Fatalf("ListExpiredCaches failed: %v", err)
	}

	found := false
	for _, id := range expired {
		if id == resp2.CacheID {
			found = true
		}
		if id == resp1.CacheID {
			t.Errorf("Unexpired cache %s should not be in list", resp1.CacheID)
		}
	}

	if !found {
		t.Errorf("Expected to find expired cache %s", resp2.CacheID)
	}
}

func TestListExpiredCaches_SyntheticRequired(t *testing.T) {
	_, err := ListExpiredCaches(false)
	checkError(t, err, "offline-cache-list-synthetic-required")
}

func TestCleanupExpiredCaches_Success(t *testing.T) {
	hash := sha256.Sum256([]byte("cleanup-test"))

	cleanupReq := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-cleanup",
		CacheKey:       "key-cleanup",
		DataHash:       hex.EncodeToString(hash[:]),
		EncryptedData:  []byte("cleanup-data"),
		CacheTTLHours:  1,
		IdempotencyKey: "idem-cleanup",
	}

	cleanupResp, _ := StoreOfflineCache(cleanupReq)

	offlineCacheMu.Lock()
	if cached, exists := offlineCacheStore[cleanupResp.CacheID]; exists {
		cached.ExpiresAt = time.Now().UTC().Add(-2 * time.Hour)
	}
	offlineCacheMu.Unlock()

	count, err := CleanupExpiredCaches(true)
	if err != nil {
		t.Fatalf("CleanupExpiredCaches failed: %v", err)
	}
	if count < 1 {
		t.Errorf("Expected at least 1 cleaned up cache, got %d", count)
	}

	offlineCacheMu.RLock()
	_, exists := offlineCacheStore[cleanupResp.CacheID]
	offlineCacheMu.RUnlock()

	if exists {
		t.Errorf("Expected cache %s to be cleaned up", cleanupResp.CacheID)
	}
}

func TestCleanupExpiredCaches_SyntheticRequired(t *testing.T) {
	_, err := CleanupExpiredCaches(false)
	checkError(t, err, "offline-cache-cleanup-synthetic-required")
}

func TestValidateCacheIntegrity_Success(t *testing.T) {
	hash := sha256.Sum256([]byte("integrity-test"))
	hashStr := hex.EncodeToString(hash[:])

	integrityReq := &OfflineCacheRequest{
		Synthetic:      true,
		FormID:         "form-integrity",
		CacheKey:       "key-integrity",
		DataHash:       hashStr,
		EncryptedData:  []byte("integrity-data"),
		CacheTTLHours:  24,
		IdempotencyKey: "idem-integrity",
	}

	integrityResp, err := StoreOfflineCache(integrityReq)
	if err != nil {
		t.Fatalf("StoreOfflineCache failed: %v", err)
	}

	valid, err := ValidateCacheIntegrity(true, integrityResp.CacheID, hashStr)
	if err != nil {
		t.Fatalf("ValidateCacheIntegrity failed: %v", err)
	}
	if !valid {
		t.Error("Expected integrity validation to pass")
	}

	wrongHash := strings.Repeat("a", 64)
	valid, err = ValidateCacheIntegrity(true, integrityResp.CacheID, wrongHash)
	if err != nil {
		t.Fatalf("ValidateCacheIntegrity failed: %v", err)
	}
	if valid {
		t.Error("Expected integrity validation to fail with wrong hash")
	}
}

func TestValidateCacheIntegrity_SyntheticRequired(t *testing.T) {
	_, err := ValidateCacheIntegrity(false, "cache-id", "hash")
	checkError(t, err, "offline-cache-validation-synthetic-required")
}

func TestValidateCacheIntegrity_IDEmpty(t *testing.T) {
	_, err := ValidateCacheIntegrity(true, "", "hash")
	checkError(t, err, "offline-cache-validation-id-empty")
}

func TestValidateCacheIntegrity_HashEmpty(t *testing.T) {
	_, err := ValidateCacheIntegrity(true, "cache-id", "")
	checkError(t, err, "offline-cache-validation-hash-empty")
}

func TestValidateCacheIntegrity_NotFound(t *testing.T) {
	_, err := ValidateCacheIntegrity(true, "nonexistent-id", strings.Repeat("a", 64))
	checkError(t, err, "offline-cache-validation-not-found")
}
