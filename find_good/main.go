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
	if err := ReadProteinNet(f); err != nil {
		log.Fatal(err)
	}
}

// ReadProteinNet ...
func ReadProteinNet(r io.Reader) error {
	scanner := bufio.NewScanner(r)
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
				log.Printf("PDB=%v ModelID=%v ChainID=%v", pdbID, modelID, chainID)
			} else if len(parts) == 2 {
				//log.Printf("Skipping ASTRAL %v", id)
			} else {
				log.Printf("Unknown ID format '%v'", id)
				continue
			}
		//case "": // new record
		default:
			// Skip the line
			continue
		}
	}
	return nil
}
