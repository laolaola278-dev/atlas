// Package contract checks suggestion drafts before review.
//
// A draft with a short digest, a direct identifier, or an incompatible
// version stays closed. This workspace has no Go toolchain, so this file
// has not been compiled here.
package contract

import "strings"

// Draft is the minimum suggestion context required before review.
type Draft struct {
	SuggestionID    string
	PatientRef      string
	Action          string
	ContentDigest   string
	ContractVersion string
}

var directIdentifiers = []string{"name", "identifier", "phone", "address", "birth_date", "patient_id"}

// Ready reports whether one draft may enter review.
func Ready(draft Draft) error {
	if draft.SuggestionID == "" || draft.PatientRef == "" || draft.Action == "" || draft.ContentDigest == "" {
		return Error{Code: "suggestion-incomplete", HTTPStatus: 400}
	}
	if hasDirectIdentifier(draft.PatientRef) || hasDirectIdentifier(draft.Action) {
		return Error{Code: "suggestion-identifier-forbidden", HTTPStatus: 403}
	}
	if len(draft.ContentDigest) != 64 {
		return Error{Code: "suggestion-digest-invalid", HTTPStatus: 400}
	}
	if draft.ContractVersion != "1.0" && draft.ContractVersion != "1.1" {
		return Error{Code: "contract-version-incompatible", HTTPStatus: 400}
	}
	return nil
}

func hasDirectIdentifier(value string) bool {
	for _, part := range strings.FieldsFunc(value, func(char rune) bool {
		return char == '.' || char == '[' || char == ']'
	}) {
		for _, forbidden := range directIdentifiers {
			if part == forbidden {
				return true
			}
		}
	}
	return false
}
