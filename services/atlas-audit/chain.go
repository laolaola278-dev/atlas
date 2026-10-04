// Package audit implements the append-only audit hash chain (ATLAS-P6-0272).
//
// Ported from internal/audit/chain.py. The canonical encoding has a fixed
// field order: a changed actor, purpose, sequence, or previous hash changes
// the event hash and breaks verification. SHA-256 is used for the digest;
// the SM3 production substitution is pending crypto-assessment [待验证]
// per ADR-014/ADR-020.
package audit

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"strings"
)

// Genesis is the previous hash of the first event in every stream: 64 zeros.
const Genesis = "0000000000000000000000000000000000000000000000000000000000000000"

// requiredFields is the canonical fixed field order for the event encoding.
var requiredFields = []string{
	"event_id",
	"stream_id",
	"sequence",
	"tenant_id",
	"campus_id",
	"actor_id",
	"actor_role",
	"operation",
	"resource_type",
	"resource_id",
	"purpose_code",
	"why_code",
	"policy_version",
	"occurred_at",
	"payload_digest",
	"clock_quality",
	"consent_decision",
}

// directIdentifiers are path segments that must never appear in audit data.
var directIdentifiers = []string{
	"name", "identifier", "phone", "address", "birth_date", "patient_id",
}

// Event is one immutable entry in the chain.
type Event struct {
	EventID         string
	StreamID        string
	Sequence        int
	TenantID        string
	CampusID        string
	ActorID         string
	ActorRole       string
	Operation       string
	ResourceType    string
	ResourceID      string
	PurposeCode     string
	WhyCode         string
	PolicyVersion   string
	OccurredAt      string
	PayloadDigest   string
	ClockQuality    string
	ConsentDecision string
	PreviousHash    string
	EventHash       string
}

// Fields is the input map accepted by Append.
type Fields map[string]string

// Log is one append-only audit stream.
type Log struct {
	streamID string
	events   []Event
	sink     func(Event)
}

// NewLog starts one stream. A direct identifier in the stream id is rejected.
func NewLog(streamID string) (*Log, error) {
	if streamID == "" {
		return nil, errors.New("audit-stream-invalid")
	}
	if hasDirectIdentifier(streamID) {
		return nil, errors.New("audit-identifier-forbidden")
	}
	return &Log{streamID: streamID}, nil
}

// SetSink attaches a durable sink called after every successful append.
func (log *Log) SetSink(sink func(Event)) {
	log.sink = sink
}

// canonical encodes fields in fixed order plus the previous hash.
func canonical(values map[string]string, previousHash string) []byte {
	var builder strings.Builder
	for _, name := range requiredFields {
		builder.WriteString(name)
		builder.WriteByte('=')
		builder.WriteString(values[name])
		builder.WriteByte('\n')
	}
	builder.WriteString("previous_hash=")
	builder.WriteString(previousHash)
	return []byte(builder.String())
}

func digest(payload []byte) string {
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}

func hasDirectIdentifier(value string) bool {
	parts := strings.FieldsFunc(value, func(char rune) bool {
		return char == '.' || char == '[' || char == ']'
	})
	for _, part := range parts {
		for _, forbidden := range directIdentifiers {
			if part == forbidden {
				return true
			}
		}
	}
	return false
}

// compatible mirrors internal.contract.version: current 1.x or 1.(x-1).
func compatible(version string) bool {
	parts := strings.Split(version, ".")
	if len(parts) == 3 {
		parts = parts[:2]
	}
	if len(parts) != 2 {
		return false
	}
	if parts[0] != "1" {
		return false
	}
	return parts[1] == "0"
}

// Append validates, links, and records one event. It fails closed.
func (log *Log) Append(fields Fields) (Event, error) {
	values := make(map[string]string, len(requiredFields))
	for _, name := range requiredFields {
		values[name] = fields[name]
	}
	if values["why_code"] == "" || values["why_code"] == "unknown" {
		return Event{}, errors.New("audit-why-missing")
	}
	for _, name := range requiredFields {
		if name == "sequence" || name == "why_code" || name == "consent_decision" {
			continue
		}
		if values[name] == "" {
			return Event{}, errors.New("audit-context-incomplete")
		}
	}
	if values["consent_decision"] == "" {
		values["consent_decision"] = "unspecified"
	}
	if !compatible(values["policy_version"]) {
		return Event{}, errors.New("audit-version-incompatible")
	}
	for _, value := range values {
		if hasDirectIdentifier(value) {
			return Event{}, errors.New("audit-identifier-forbidden")
		}
	}
	sequence := len(log.events) + 1
	if fields["sequence"] != "" && fields["sequence"] != itoa(sequence) {
		return Event{}, errors.New("audit-sequence-invalid")
	}
	if values["stream_id"] != log.streamID {
		return Event{}, errors.New("audit-stream-mismatch")
	}
	previous := Genesis
	if len(log.events) > 0 {
		previous = log.events[len(log.events)-1].EventHash
	}
	encoded := canonical(values, previous)
	event := Event{
		EventID:         values["event_id"],
		StreamID:        values["stream_id"],
		Sequence:        sequence,
		TenantID:        values["tenant_id"],
		CampusID:        values["campus_id"],
		ActorID:         values["actor_id"],
		ActorRole:       values["actor_role"],
		Operation:       values["operation"],
		ResourceType:    values["resource_type"],
		ResourceID:      values["resource_id"],
		PurposeCode:     values["purpose_code"],
		WhyCode:         values["why_code"],
		PolicyVersion:   values["policy_version"],
		OccurredAt:      values["occurred_at"],
		PayloadDigest:   values["payload_digest"],
		ClockQuality:    values["clock_quality"],
		ConsentDecision: values["consent_decision"],
		PreviousHash:    previous,
		EventHash:       digest(encoded),
	}
	log.events = append(log.events, event)
	if log.sink != nil {
		log.sink(event)
	}
	return event, nil
}

func itoa(value int) string {
	if value == 0 {
		return "0"
	}
	var digits [20]byte
	index := len(digits)
	for value > 0 {
		index--
		digits[index] = byte('0' + value%10)
		value /= 10
	}
	return string(digits[index:])
}

// eventValues rebuilds the canonical input map from a stored event.
func eventValues(event Event) map[string]string {
	return map[string]string{
		"event_id":         event.EventID,
		"stream_id":        event.StreamID,
		"sequence":         itoa(event.Sequence),
		"tenant_id":        event.TenantID,
		"campus_id":        event.CampusID,
		"actor_id":         event.ActorID,
		"actor_role":       event.ActorRole,
		"operation":        event.Operation,
		"resource_type":    event.ResourceType,
		"resource_id":      event.ResourceID,
		"purpose_code":     event.PurposeCode,
		"why_code":         event.WhyCode,
		"policy_version":   event.PolicyVersion,
		"occurred_at":      event.OccurredAt,
		"payload_digest":   event.PayloadDigest,
		"clock_quality":    event.ClockQuality,
		"consent_decision": event.ConsentDecision,
	}
}

// Verify replays the whole chain. Any gap, reorder, or edit fails closed.
func (log *Log) Verify() error {
	previous := Genesis
	for index, event := range log.events {
		if event.Sequence != index+1 || event.PreviousHash != previous {
			return errors.New("audit-chain-broken")
		}
		encoded := canonical(eventValues(event), previous)
		if digest(encoded) != event.EventHash {
			return errors.New("audit-hash-mismatch")
		}
		previous = event.EventHash
	}
	return nil
}

// Events returns a copy of the stored events.
func (log *Log) Events() []Event {
	result := make([]Event, len(log.events))
	copy(result, log.events)
	return result
}

// ToFhirAuditEvent maps one chain event to a FHIR-shaped map without free
// text. A digest that is not 64 hex chars fails closed.
func ToFhirAuditEvent(event Event) (map[string]string, error) {
	mapped := map[string]string{
		"action":       event.Operation,
		"agentRole":    event.ActorRole,
		"entityDigest": event.PayloadDigest,
		"id":           event.EventID,
		"occurredAt":   event.OccurredAt,
		"outcome":      event.ConsentDecision,
		"purposeCode":  event.PurposeCode,
		"resourceType": "AuditEvent",
		"subtype":      event.ResourceType,
	}
	for _, value := range mapped {
		if hasDirectIdentifier(value) {
			return nil, errors.New("audit-fhir-identifier-forbidden")
		}
	}
	if len(event.PayloadDigest) != 64 || len(event.EventHash) != 64 {
		return nil, errors.New("audit-fhir-digest-invalid")
	}
	mapped["eventHash"] = event.EventHash
	return mapped, nil
}
