package config

import "testing"

func TestLoadAcceptsExternalSecret(t *testing.T) {
	loaded, err := Load(map[string]string{
		"audit_stream":   "review-service",
		"campus_id":      "campus-synthetic",
		"policy_version": "1.0.0",
		"secret_ref":     "secret://atlas/signing-key",
		"tenant_id":      "tenant-synthetic",
	})
	if err != nil || loaded.TenantID != "tenant-synthetic" {
		t.Fatalf("scoped config rejected: %+v %v", loaded, err)
	}
}

func TestLoadRejectsInlineToken(t *testing.T) {
	_, err := Load(map[string]string{
		"api_token":      "sk-synthetic",
		"audit_stream":   "review-service",
		"campus_id":      "campus-synthetic",
		"policy_version": "1.0.0",
		"secret_ref":     "secret://atlas/signing-key",
		"tenant_id":      "tenant-synthetic",
	})
	if err == nil || err.Error() != "config-secret-inline" {
		t.Fatalf("inline token accepted: %v", err)
	}
}

func TestLoadRejectsMissingScope(t *testing.T) {
	_, err := Load(map[string]string{
		"audit_stream":   "review-service",
		"policy_version": "1.0.0",
		"secret_ref":     "secret://atlas/signing-key",
		"tenant_id":      "tenant-synthetic",
	})
	if err == nil || err.Error() != "config-incomplete" {
		t.Fatalf("missing campus accepted: %v", err)
	}
}
