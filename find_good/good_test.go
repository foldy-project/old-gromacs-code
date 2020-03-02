package main

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
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/Jeffail/tunny"
	"github.com/stretchr/testify/require"
)

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

	timeoutStr, ok := os.LookupEnv("TIMEOUT")
	if !ok {
		timeoutStr = "240s"
	}
	timeout, err := time.ParseDuration(timeoutStr)
	require.NoError(t, err)

	concurrency := 1
	if concStr, ok := os.LookupEnv("CONCURRENCY"); ok {
		conc, err := strconv.ParseInt(concStr, 10, 64)
		require.NoError(t, err)
		concurrency = int(conc)
	}

	log.Printf("Running minimization experiments with concurrency of %d", concurrency)

	data, err := ioutil.ReadFile("good.txt")
	require.NoError(t, err)
	good := strings.Split(string(data), "\n")

	definitelyGood, err := os.Create("/data/definitely-good.txt")
	require.NoError(t, err)
	defer func() {
		require.NoError(t, definitelyGood.Close())
	}()
	definitelyGoodL := sync.Mutex{}

	pool := tunny.NewFunc(concurrency, func(payload interface{}) interface{} {
		pdbID := payload.(string)
		pdbID = strings.ToLower(pdbID)
		doneOuter := make(chan int, 1)
		go func() {
			t.Run(pdbID, func(t *testing.T) {
				defer func() {
					// Notify the tunny func that this test is done
					doneOuter <- 0
					close(doneOuter)
				}()
				doneInner := make(chan int, 1)
				go func() {
					defer func() {
						// Escape the timeout; experiment has finished
						doneInner <- 0
						close(doneInner)
					}()
					steps := 5
					config, _ := json.Marshal(map[string]interface{}{
						"pdb_id": pdbID,
						"steps":  steps,
					})
					url := fmt.Sprintf("http://%s/run", foldyOperator)
					req, err := http.NewRequest("POST", url, bytes.NewReader(config))
					require.NoError(t, err)
					cl := http.Client{Timeout: time.Minute * 3}
					resp, err := cl.Do(req)
					require.NoError(t, err)
					if resp.StatusCode != 200 {
						msg, _ := ioutil.ReadAll(resp.Body)
						log.Printf("%v", string(msg))
					}
					require.Equal(t, resp.StatusCode, 200)
					defer resp.Body.Close()
					f, err := ioutil.TempFile("/tmp", "result-*.tar.gz")
					require.NoError(t, err)
					defer func() {
						require.Nil(t, os.Remove(f.Name()))
					}()
					_, err = io.Copy(f, resp.Body)
					require.NoError(t, err)
					require.Nil(t, f.Close())
					info, err := os.Stat(f.Name())
					require.NoError(t, err)
					require.Greater(t, info.Size(), int64(0))
					untar(t, f.Name())
					dirPath := fmt.Sprintf("%s_minim/", pdbID)
					defer func() {
						require.Nil(t, os.RemoveAll(dirPath))
					}()
					files, err := listFiles(dirPath)
					require.NoError(t, err)
					require.Equal(t, len(files), steps)
				}()
				select {
				case <-doneInner:
				case <-time.After(timeout):
					t.Fatalf("timed out after %v", timeout)
				}
				definitelyGoodL.Lock()
				defer definitelyGoodL.Unlock()
				_, err = definitelyGood.Write([]byte(fmt.Sprintf("%s\n", pdbID)))
				require.NoError(t, err)
			})
		}()
		<-doneOuter
		return nil
	})
	defer pool.Close()

	numPDBs := len(good)
	dones := make([]chan int, numPDBs, numPDBs)
	for i, pdbID := range good {
		pdbID = strings.ToLower(strings.TrimSpace(pdbID))
		require.Equalf(t, 4, len(pdbID), "malformed pdb ID '%v'", pdbID)
		done := make(chan int, 1)
		dones[i] = done
		//go func(pdbID string, done chan<- int) {
		pool.Process(pdbID)
		done <- 0
		close(done)
		//}(pdbID, done)
	}
	for _, done := range dones {
		<-done
	}
}
