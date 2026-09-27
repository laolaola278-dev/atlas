package terminology

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

type releaseRecord struct {
	SystemURL     string `json:"system_url"`
	ReleaseID     string `json:"release_id"`
	EffectiveFrom string `json:"effective_from"`
	EffectiveTo   string `json:"effective_to"`
}

type manifestFile struct {
	Synthetic bool            `json:"synthetic"`
	Releases  []releaseRecord `json:"releases"`
}

func TestManifestIsSyntheticAndDated(t *testing.T) {
	path := filepath.Join("..", "..", "api", "terminology", "manifest.json")
	body, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("manifest unreadable: %v", err)
	}
	var parsed manifestFile
	if err = json.Unmarshal(body, &parsed); err != nil {
		t.Fatalf("manifest corrupt: %v", err)
	}
	if !parsed.Synthetic || len(parsed.Releases) == 0 {
		t.Fatal("manifest is not a synthetic release list")
	}
	first := parsed.Releases[0]
	if first.SystemURL == "" || first.ReleaseID == "" || first.EffectiveFrom == "" || first.EffectiveTo == "" {
		t.Fatal("release window is incomplete")
	}
	if first.EffectiveFrom >= first.EffectiveTo {
		t.Fatal("release window is inverted")
	}
}
