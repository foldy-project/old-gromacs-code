package main

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestRunExperiment(t *testing.T) {
	s, err := newServer()
	assert.Nil(t, err)

	req, _ := http.NewRequest("GET", "localhost:8090/?pdb_id=1aki", nil)
	w := httptest.NewRecorder()
	s.handleRun()(w, req)
	body := w.Body.Bytes()
	assert.Greater(t, len(body), 0)
}
