package main

import "testing"

func TestRunRejectsMissingScope(t *testing.T) {
	err := run([]string{"tenant-synthetic", "campus-synthetic"})
	if err == nil || err.Error() != "context-incomplete" {
		t.Fatalf("short startup accepted: %v", err)
	}
}

func TestRunAcceptsSyntheticScope(t *testing.T) {
	err := run([]string{"tenant-synthetic", "campus-synthetic", "1.0.0"})
	if err != nil {
		t.Fatalf("synthetic startup rejected: %v", err)
	}
}

func TestRunRejectsBlankPolicy(t *testing.T) {
	err := run([]string{"tenant-synthetic", "campus-synthetic", ""})
	if err == nil || err.Error() != "context-incomplete" {
		t.Fatalf("blank policy accepted: %v", err)
	}
}
