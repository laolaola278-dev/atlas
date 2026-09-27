// Package config loads startup settings and rejects inline secrets.
//
// A service without a tenant, campus, policy version, audit stream, or
// secret reference does not start. This workspace has no Go toolchain, so
// this file has not been compiled here.
package config

import (
	"errors"
	"strings"
)

// Runtime is the non-secret scope required at startup.
type Runtime struct {
	TenantID      string
	CampusID      string
	PolicyVersion string
	AuditStream   string
	SecretRef     string
}

var secretMarkers = []string{"secret", "password", "private_key", "token"}
var acceptedVersions = map[string]struct{}{"1.0": {}, "1.0.0": {}, "1.1": {}, "1.1.0": {}}

// Load accepts only a scoped configuration with an external secret reference.
func Load(payload map[string]string) (Runtime, error) {
	for key, value := range payload {
		lowered := strings.ToLower(key)
		if strings.HasPrefix(strings.ToLower(value), "sk-") || strings.HasPrefix(strings.ToLower(value), "bearer ") {
			return Runtime{}, errors.New("config-secret-inline")
		}
		if !strings.HasSuffix(lowered, "_ref") && markerPresent(lowered) {
			return Runtime{}, errors.New("config-secret-inline")
		}
	}
	loaded := Runtime{
		TenantID:      strings.TrimSpace(payload["tenant_id"]),
		CampusID:      strings.TrimSpace(payload["campus_id"]),
		PolicyVersion: strings.TrimSpace(payload["policy_version"]),
		AuditStream:   strings.TrimSpace(payload["audit_stream"]),
		SecretRef:     strings.TrimSpace(payload["secret_ref"]),
	}
	if loaded.TenantID == "" || loaded.CampusID == "" || loaded.PolicyVersion == "" || loaded.AuditStream == "" || loaded.SecretRef == "" {
		return Runtime{}, errors.New("config-incomplete")
	}
	if !strings.HasPrefix(loaded.SecretRef, "secret://") {
		return Runtime{}, errors.New("config-secret-ref-invalid")
	}
	if _, ok := acceptedVersions[loaded.PolicyVersion]; !ok {
		return Runtime{}, errors.New("config-version-incompatible")
	}
	return loaded, nil
}

func markerPresent(key string) bool {
	for _, marker := range secretMarkers {
		if strings.Contains(key, marker) {
			return true
		}
	}
	return false
}
