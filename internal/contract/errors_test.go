package contract

import "testing"

func TestLookupKnownCode(t *testing.T) {
	item, err := Lookup("approval-missing")
	if err != nil {
		t.Fatalf("lookup failed: %v", err)
	}
	if item.Code != "approval-missing" || item.Retryable || item.HTTPStatus != 403 {
		t.Fatalf("unexpected code: %+v", item)
	}
}

func TestLookupUnknownCodeFailsClosed(t *testing.T) {
	if _, err := Lookup("not-a-code"); err == nil || err.Error() != "error-code-unknown" {
		t.Fatalf("unknown code was accepted: %v", err)
	}
}

func TestLookupRejectsMalformedStatus(t *testing.T) {
	codes["status-broken"] = Error{Code: "status-broken", HTTPStatus: 200}
	t.Cleanup(func() { delete(codes, "status-broken") })
	if _, err := Lookup("status-broken"); err == nil {
		t.Fatal("non-error status was accepted")
	}
}
