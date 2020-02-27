package test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

func TestBasicMinim(t *testing.T) {
	foldyOperator, ok := os.LookupEnv("FOLDY_OPERATOR")
	require.Truef(t, ok, "missing FOLDY_OPERATOR")
	pdbID, ok := os.LookupEnv("PDB_ID")
	if !ok {
		pdbID = "1aki"
	}
	config, _ := json.Marshal(map[string]interface{}{
		"pdb_id": pdbID,
	})
	url := fmt.Sprintf("http://%s/run", foldyOperator)
	req, err := http.NewRequest("POST", url, bytes.NewReader(config))
	require.Nil(t, err)
	cl := http.Client{Timeout: time.Minute * 3}
	resp, err := cl.Do(req)
	require.Nil(t, err)
	defer resp.Body.Close()
	f, err := ioutil.TempFile("/tmp", "result-*.tar.gz")
	require.Nil(t, err)
	defer f.Close()
	defer func() {
		require.Nil(t, os.Remove(f.Name()))
	}()
	io.Copy(f, resp.Body)
	require.Nil(t, err)
	info, err := os.Stat(f.Name())
	require.Nil(t, err)
	require.Greater(t, info.Size(), int64(0))
}

func TestBrokenPDB(t *testing.T) {
	foldyOperator, ok := os.LookupEnv("FOLDY_OPERATOR")
	require.Truef(t, ok, "missing FOLDY_OPERATOR")
	config, _ := json.Marshal(map[string]interface{}{
		"pdb_id": "broken", // s3://pdb/pdbbroken.ent.gz
	})
	url := fmt.Sprintf("http://%s/run", foldyOperator)
	req, err := http.NewRequest("POST", url, bytes.NewReader(config))
	require.Nil(t, err)
	cl := http.Client{Timeout: time.Minute * 3}
	resp, err := cl.Do(req)
	require.Nil(t, err)
	defer resp.Body.Close()
	require.Equal(t, 500, resp.StatusCode)
	body, err := ioutil.ReadAll(resp.Body)
	require.Nil(t, err)
	// GROMACS error message output
	require.True(t, strings.Contains(string(body), "Trying to deduce atomnumbers when no pdb information is present"))
}

func TestPDBNotFound(t *testing.T) {
	foldyOperator, ok := os.LookupEnv("FOLDY_OPERATOR")
	require.Truef(t, ok, "missing FOLDY_OPERATOR")
	pdbID := "abcd"
	config, _ := json.Marshal(map[string]interface{}{
		"pdb_id": pdbID,
	})
	url := fmt.Sprintf("http://%s/run", foldyOperator)
	req, err := http.NewRequest("POST", url, bytes.NewReader(config))
	require.Nil(t, err)
	cl := http.Client{Timeout: time.Minute * 3}
	resp, err := cl.Do(req)
	require.Nil(t, err)
	defer resp.Body.Close()
	require.Equal(t, 500, resp.StatusCode)
	body, err := ioutil.ReadAll(resp.Body)
	require.Nil(t, err)
	require.Equal(t, fmt.Sprintf("pdb '%s' not found", pdbID), string(body))
}

func listFiles(path string) ([]string, error) {
	var files []string
	err := filepath.Walk(path,
		func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return err
			}
			if info.IsDir() {
				return nil
			}
			files = append(files, path)
			return nil
		})
	return files, err
}

func untar(t *testing.T, fileName string) {
	cmd := exec.Command("tar", "-xzvf", fileName)
	cmd.Stderr = os.Stderr
	require.Nil(t, cmd.Run())
}

func TestConfiguredMinim(t *testing.T) {
	foldyOperator, ok := os.LookupEnv("FOLDY_OPERATOR")
	require.Truef(t, ok, "missing FOLDY_OPERATOR")
	pdbID, ok := os.LookupEnv("PDB_ID")
	if !ok {
		pdbID = "1aki"
	}
	steps := 10
	config, _ := json.Marshal(map[string]interface{}{
		"pdb_id": pdbID,
		"steps":  steps,
	})
	url := fmt.Sprintf("http://%s/run", foldyOperator)
	req, err := http.NewRequest("POST", url, bytes.NewReader(config))
	require.Nil(t, err)
	cl := http.Client{Timeout: time.Minute * 3}
	resp, err := cl.Do(req)
	require.Nil(t, err)
	if resp.StatusCode != 200 {
		msg, _ := ioutil.ReadAll(resp.Body)
		log.Printf("%v", string(msg))
	}
	require.Equal(t, resp.StatusCode, 200)
	defer resp.Body.Close()
	f, err := ioutil.TempFile("/tmp", "result-*.tar.gz")
	require.Nil(t, err)
	defer func() {
		require.Nil(t, os.Remove(f.Name()))
	}()
	_, err = io.Copy(f, resp.Body)
	require.Nil(t, err)
	require.Nil(t, f.Close())
	info, err := os.Stat(f.Name())
	require.Nil(t, err)
	require.Greater(t, info.Size(), int64(0))
	untar(t, f.Name())
	files, err := listFiles(fmt.Sprintf("%s_minim/", pdbID))
	require.Nil(t, err)
	require.Equal(t, len(files), steps)
}
