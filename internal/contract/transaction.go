// Package contract tracks one write stream and fails closed.
//
// A committed result may advance the watermark. An unknown result stays below
// it and cannot be replayed as a new write. This workspace has no Go
// toolchain, so this file has not been compiled here.
package contract

import "errors"

// Mark is one accepted, unknown, or committed write.
type Mark struct {
	Sequence int
	Key      string
	Digest   string
	State    string
	ActorID  string
	WhyCode  string
}

// Watermark is one ordered write stream.
type Watermark struct {
	next      int
	committed int
	records   map[string]Mark
}

// NewWatermark starts one empty stream.
func NewWatermark() *Watermark {
	return &Watermark{next: 1, records: map[string]Mark{}}
}

// Begin accepts one new write or returns the original committed result.
func (mark *Watermark) Begin(key string, digest string, actorID string, whyCode string) (Mark, error) {
	if key == "" || len(digest) != 64 || actorID == "" {
		return Mark{}, errors.New("transaction-key-invalid")
	}
	if whyCode == "" || whyCode == "unknown" || whyCode == "unspecified" {
		return Mark{}, errors.New("transaction-why-missing")
	}
	current, found := mark.records[key]
	if !found {
		current = Mark{Sequence: mark.next, Key: key, Digest: digest, State: "accepted", ActorID: actorID, WhyCode: whyCode}
		mark.records[key] = current
		mark.next++
		return current, nil
	}
	if current.Digest != digest {
		return Mark{}, errors.New("transaction-conflict")
	}
	if current.ActorID != actorID || current.WhyCode != whyCode {
		return Mark{}, errors.New("transaction-responsibility-mismatch")
	}
	if current.State == "unknown" {
		return Mark{}, errors.New("transaction-result-unknown")
	}
	return current, nil
}

// Commit advances the watermark only when the result is known.
func (mark *Watermark) Commit(key string) (Mark, error) {
	current, found := mark.records[key]
	if !found {
		return Mark{}, errors.New("transaction-key-unknown")
	}
	if current.State == "unknown" {
		return Mark{}, errors.New("transaction-result-unknown")
	}
	if current.State == "committed" {
		return current, nil
	}
	current.State = "committed"
	mark.records[key] = current
	if current.Sequence > mark.committed {
		mark.committed = current.Sequence
	}
	return current, nil
}

// Freeze keeps one result unknown and does not move the watermark.
func (mark *Watermark) Freeze(key string) (Mark, error) {
	current, found := mark.records[key]
	if !found {
		return Mark{}, errors.New("transaction-key-unknown")
	}
	if current.State == "committed" {
		return Mark{}, errors.New("transaction-already-committed")
	}
	current.State = "unknown"
	mark.records[key] = current
	return current, nil
}

// Committed returns the highest committed sequence.
func (mark *Watermark) Committed() int {
	return mark.committed
}
