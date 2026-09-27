// Command atlas-skeleton is the fail-closed process entry.
//
// It refuses to start without a tenant, campus, and policy version. It does
// not serve clinical traffic. This workspace has no Go toolchain, so this
// command has not been built here.
package main

import (
	"errors"
	"fmt"
	"os"

	"atlas/internal/contract"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
		os.Exit(1)
	}
}

func run(args []string) error {
	if len(args) != 3 || args[0] == "" || args[1] == "" || args[2] == "" {
		item, err := contract.Lookup("context-incomplete")
		if err != nil {
			return err
		}
		return errors.New(item.Code)
	}
	fmt.Println("atlas-skeleton-ready")
	return nil
}
