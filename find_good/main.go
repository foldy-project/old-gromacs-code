package main

import (
	"bufio"
	"fmt"
	"io"
	"log"
	"os"
	"strconv"
	"strings"
)

func main() {
	f, err := os.Open("/mnt/d/casp11/training_30")
	if err != nil {
		log.Fatal(err)
	}
	results := make(chan *record)
	go func() {
		if err := ReadProteinNet(f, results); err != nil {
			log.Fatal(err)
		}
	}()
	for r := range results {
		log.Printf("PDB=%v ModelID=%v ChainID=%v PrimaryLen=%d", r.pdbID, r.modelID, r.chainID, len(r.primary))
	}
}

type record struct {
	pdbID   string
	modelID int
	chainID string
	primary string
	mask    string
}

// ReadProteinNet ...
func ReadProteinNet(r io.Reader, results chan<- *record) error {
	defer close(results)
	scanner := bufio.NewScanner(r)
	var next *record
	for scanner.Scan() {
		line := scanner.Text()
		switch line {
		case "[ID]":
			if !scanner.Scan() {
				return fmt.Errorf("expected ID")
			}
			id := scanner.Text()
			parts := strings.Split(id, "_")
			if len(parts) == 3 {
				pdbID := parts[0]
				modelIDStr := parts[1]
				modelID, err := strconv.ParseInt(modelIDStr, 10, 64)
				if err != nil {
					return fmt.Errorf("failed to parse model ID '%v': %v", modelIDStr, err)
				}
				chainID := parts[2]
				next = &record{
					pdbID:   pdbID,
					modelID: int(modelID),
					chainID: chainID,
				}
			} else if len(parts) == 2 {
				//log.Printf("Skipping ASTRAL %v", id)
			} else {
				log.Printf("Unknown ID format '%v'", id)
				continue
			}
		case "[PRIMARY]":
			if next != nil {
				if !scanner.Scan() {
					return fmt.Errorf("expected primary sequence")
				}
				next.primary = scanner.Text()
			}
		case "[MASK]":
			if next != nil {
				if !scanner.Scan() {
					return fmt.Errorf("expected mask")
				}
				next.mask = scanner.Text()
			}
		case "":
			if next != nil {
				if got, expected := len(next.mask), len(next.primary); got != expected {
					panic(fmt.Sprintf("mask length (got %v, expected %v)", got, expected))
				}
				results <- next
				next = nil
			}
			continue
		default:
			// Skip the line
			continue
		}
	}
	log.Printf("Success")
	return nil
}
