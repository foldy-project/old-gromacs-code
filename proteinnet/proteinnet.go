package proteinnet

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"strconv"
	"strings"
)

// Record a ProteinNet record
type Record struct {
	StructureID string
	ModelID     int
	ChainID     string
	Primary     string
	Mask        string
}

// ErrSuccessfullyStopped returned by ReadRecords when
// the reader thread was successfully stopped.
var ErrSuccessfullyStopped = errors.New("stopped successfully")

// ReadRecords ...
func ReadRecords(
	r io.Reader,
	results chan<- *Record,
	stop <-chan int,
) error {
	defer close(results)
	scanner := bufio.NewScanner(r)
	var next *Record
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
				next = &Record{
					StructureID: pdbID,
					ModelID:     int(modelID),
					ChainID:     chainID,
				}
			} else if len(parts) == 2 {
				//log.Printf("Skipping ASTRAL %v", id)
			} else {
				return fmt.Errorf("malformed ID format '%v'", id)
			}
		case "[PRIMARY]":
			if next != nil {
				if !scanner.Scan() {
					return fmt.Errorf("expected primary sequence")
				}
				next.Primary = scanner.Text()
			}
		case "[MASK]":
			if next != nil {
				if !scanner.Scan() {
					return fmt.Errorf("expected mask")
				}
				next.Mask = scanner.Text()
			}
		case "":
			if next != nil {
				if got, expected := len(next.Mask), len(next.Primary); got != expected {
					return fmt.Errorf("mask length (got %v, expected %v)", got, expected)
				}
				select {
				case results <- next:
					next = nil
					continue
				case <-stop:
					return ErrSuccessfullyStopped
				}
			}
			continue
		default:
			// Skip the line
			continue
		}
	}
	return nil
}
