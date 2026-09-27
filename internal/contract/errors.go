// Package contract keeps stable fail-closed error codes.
//
// Codes are safe for logs. They never include a patient identifier, clinical
// text, or a secret. This file is a source skeleton; this workspace has no Go
// toolchain, so it has not been compiled here.
package contract

import "errors"

// Error is one stable contract violation.
type Error struct {
	Code       string
	Retryable  bool
	HTTPStatus int
}

func (err Error) Error() string {
	return err.Code
}

// Lookup returns a known code or fails closed for an unknown one.
func Lookup(code string) (Error, error) {
	item, ok := codes[code]
	if !ok || item.Code == "" || item.HTTPStatus < 400 || item.HTTPStatus > 599 {
		return Error{}, errors.New("error-code-unknown")
	}
	return item, nil
}

var codes = map[string]Error{
	"approval-missing":             {Code: "approval-missing", Retryable: false, HTTPStatus: 403},
	"campus-missing":               {Code: "campus-missing", Retryable: false, HTTPStatus: 403},
	"context-incomplete":           {Code: "context-incomplete", Retryable: false, HTTPStatus: 400},
	"dependency-unavailable":       {Code: "dependency-unavailable", Retryable: true, HTTPStatus: 503},
	"emergency-grant-not-approval": {Code: "emergency-grant-not-approval", Retryable: false, HTTPStatus: 403},
	"idempotency-conflict":         {Code: "idempotency-conflict", Retryable: false, HTTPStatus: 409},
	"purpose-missing":              {Code: "purpose-missing", Retryable: false, HTTPStatus: 403},
	"result-unknown":               {Code: "result-unknown", Retryable: true, HTTPStatus: 503},
	"tenant-missing":               {Code: "tenant-missing", Retryable: false, HTTPStatus: 403},
	"version-conflict":             {Code: "version-conflict", Retryable: false, HTTPStatus: 409},
}
