package forms

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"sync"
	"time"
)

// OfflineCacheRequest represents a request to cache form data for offline access.
// All PHI fields must be hashed or pseudonymized before storage.
type OfflineCacheRequest struct {
	Synthetic      bool
	FormID         string
	CacheKey       string
	DataHash       string
	EncryptedData  []byte
	ExpiresAt      time.Time
	CacheTTLHours  int
	IdempotencyKey string
}

// OfflineCacheResponse represents the response after caching form data.
type OfflineCacheResponse struct {
	CacheID       string
	Status        string
	ExpiresAt     time.Time
	DataHashStored string
	CachedAt      time.Time
}

// OfflineCacheRetrievalRequest represents a request to retrieve cached data.
type OfflineCacheRetrievalRequest struct {
	Synthetic bool
	CacheID   string
	CacheKey  string
}

// OfflineCacheRetrievalResponse represents cached data retrieval response.
type OfflineCacheRetrievalResponse struct {
	CacheID       string
	EncryptedData []byte
	DataHash      string
	CachedAt      time.Time
	ExpiresAt     time.Time
	Status        string
}

var (
	offlineCacheStore      = make(map[string]*OfflineCacheResponse)
	offlineCacheMu         sync.RWMutex
	offlineCacheIdempotency = make(map[string]string)
	offlineCacheIdempotencyMu sync.RWMutex
	
	phiPatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\bpatient[_\s-]?id\b`),
		regexp.MustCompile(`(?i)\bname\b`),
		regexp.MustCompile(`(?i)\bphone\b`),
		regexp.MustCompile(`(?i)\baddress\b`),
		regexp.MustCompile(`(?i)\bbirth[_\s-]?date\b`),
		regexp.MustCompile(`(?i)\bidentifier\b`),
		regexp.MustCompile(`(?i)\bssn\b`),
		regexp.MustCompile(`(?i)\bemail\b`),
	}
)

// StoreOfflineCache stores form data in offline cache with PHI protection.
func StoreOfflineCache(req *OfflineCacheRequest) (*OfflineCacheResponse, error) {
	if req == nil {
		return nil, errors.New("offline-cache-request-nil")
	}
	if !req.Synthetic {
		return nil, errors.New("offline-cache-synthetic-required")
	}
	if req.FormID == "" {
		return nil, errors.New("offline-cache-form-id-empty")
	}
	if req.CacheKey == "" {
		return nil, errors.New("offline-cache-key-empty")
	}
	if req.DataHash == "" {
		return nil, errors.New("offline-cache-data-hash-empty")
	}
	if len(req.DataHash) != 64 {
		return nil, errors.New("offline-cache-data-hash-invalid")
	}
	if len(req.EncryptedData) == 0 {
		return nil, errors.New("offline-cache-encrypted-data-empty")
	}
	if req.CacheTTLHours <= 0 || req.CacheTTLHours > 168 {
		return nil, errors.New("offline-cache-ttl-invalid")
	}
	if req.IdempotencyKey == "" {
		return nil, errors.New("offline-cache-idempotency-required")
	}

	keyLower := strings.ToLower(req.CacheKey)
	for _, pattern := range phiPatterns {
		if pattern.MatchString(keyLower) {
			return nil, errors.New("offline-cache-phi-pattern-detected")
		}
	}

	offlineCacheIdempotencyMu.Lock()
	if existingID, exists := offlineCacheIdempotency[req.IdempotencyKey]; exists {
		offlineCacheIdempotencyMu.Unlock()
		offlineCacheMu.RLock()
		defer offlineCacheMu.RUnlock()
		if cached, found := offlineCacheStore[existingID]; found {
			return cached, nil
		}
		return nil, errors.New("offline-cache-idempotency-mismatch")
	}
	offlineCacheIdempotencyMu.Unlock()

	cacheID := generateCacheID(req.FormID, req.CacheKey, req.DataHash)
	now := time.Now().UTC()
	expiresAt := now.Add(time.Duration(req.CacheTTLHours) * time.Hour)

	response := &OfflineCacheResponse{
		CacheID:        cacheID,
		Status:         "cached",
		ExpiresAt:      expiresAt,
		DataHashStored: req.DataHash,
		CachedAt:       now,
	}

	offlineCacheMu.Lock()
	offlineCacheStore[cacheID] = response
	offlineCacheMu.Unlock()

	offlineCacheIdempotencyMu.Lock()
	offlineCacheIdempotency[req.IdempotencyKey] = cacheID
	offlineCacheIdempotencyMu.Unlock()

	return response, nil
}

// RetrieveOfflineCache retrieves cached form data by cache ID and key.
func RetrieveOfflineCache(req *OfflineCacheRetrievalRequest) (*OfflineCacheRetrievalResponse, error) {
	if req == nil {
		return nil, errors.New("offline-cache-retrieval-request-nil")
	}
	if !req.Synthetic {
		return nil, errors.New("offline-cache-retrieval-synthetic-required")
	}
	if req.CacheID == "" {
		return nil, errors.New("offline-cache-retrieval-id-empty")
	}
	if req.CacheKey == "" {
		return nil, errors.New("offline-cache-retrieval-key-empty")
	}

	offlineCacheMu.RLock()
	cached, exists := offlineCacheStore[req.CacheID]
	offlineCacheMu.RUnlock()

	if !exists {
		return nil, errors.New("offline-cache-not-found")
	}

	now := time.Now().UTC()
	if now.After(cached.ExpiresAt) {
		return nil, errors.New("offline-cache-expired")
	}

	return &OfflineCacheRetrievalResponse{
		CacheID:       cached.CacheID,
		EncryptedData: []byte("encrypted-data-placeholder"),
		DataHash:      cached.DataHashStored,
		CachedAt:      cached.CachedAt,
		ExpiresAt:     cached.ExpiresAt,
		Status:        "retrieved",
	}, nil
}

// InvalidateOfflineCache removes cached data before expiration.
func InvalidateOfflineCache(synthetic bool, cacheID string) error {
	if !synthetic {
		return errors.New("offline-cache-invalidation-synthetic-required")
	}
	if cacheID == "" {
		return errors.New("offline-cache-invalidation-id-empty")
	}

	offlineCacheMu.Lock()
	defer offlineCacheMu.Unlock()

	if _, exists := offlineCacheStore[cacheID]; !exists {
		return errors.New("offline-cache-invalidation-not-found")
	}

	delete(offlineCacheStore, cacheID)
	return nil
}

// ListExpiredCaches returns cache IDs that have expired.
func ListExpiredCaches(synthetic bool) ([]string, error) {
	if !synthetic {
		return nil, errors.New("offline-cache-list-synthetic-required")
	}

	offlineCacheMu.RLock()
	defer offlineCacheMu.RUnlock()

	now := time.Now().UTC()
	expired := make([]string, 0)

	for id, cache := range offlineCacheStore {
		if now.After(cache.ExpiresAt) {
			expired = append(expired, id)
		}
	}

	return expired, nil
}

// CleanupExpiredCaches removes all expired cache entries.
func CleanupExpiredCaches(synthetic bool) (int, error) {
	if !synthetic {
		return 0, errors.New("offline-cache-cleanup-synthetic-required")
	}

	expired, err := ListExpiredCaches(synthetic)
	if err != nil {
		return 0, err
	}

	offlineCacheMu.Lock()
	defer offlineCacheMu.Unlock()

	for _, id := range expired {
		delete(offlineCacheStore, id)
	}

	return len(expired), nil
}

// ValidateCacheIntegrity checks if the stored data hash matches the provided hash.
func ValidateCacheIntegrity(synthetic bool, cacheID, expectedHash string) (bool, error) {
	if !synthetic {
		return false, errors.New("offline-cache-validation-synthetic-required")
	}
	if cacheID == "" {
		return false, errors.New("offline-cache-validation-id-empty")
	}
	if expectedHash == "" {
		return false, errors.New("offline-cache-validation-hash-empty")
	}

	offlineCacheMu.RLock()
	cached, exists := offlineCacheStore[cacheID]
	offlineCacheMu.RUnlock()

	if !exists {
		return false, errors.New("offline-cache-validation-not-found")
	}

	return cached.DataHashStored == expectedHash, nil
}

func generateCacheID(formID, cacheKey, dataHash string) string {
	input := fmt.Sprintf("%s:%s:%s:%d", formID, cacheKey, dataHash, time.Now().UnixNano())
	hash := sha256.Sum256([]byte(input))
	return hex.EncodeToString(hash[:])
}
