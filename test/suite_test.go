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
	"runtime"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/fogleman/fauxgl"
	"github.com/nfnt/resize"

	"github.com/fogleman/ribbon/pdb"
	"github.com/fogleman/ribbon/ribbon"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

const (
	size  = 2048
	scale = 4
)

func TestErrBrokenPDB(t *testing.T) {
	foldyOperator, ok := os.LookupEnv("FOLDY_OPERATOR")
	require.Truef(t, ok, "missing FOLDY_OPERATOR")
	config, _ := json.Marshal(map[string]interface{}{
		"pdb_id":   "broken", // s3://pdb/pdbbroken.ent.gz contains random junk text for this test
		"model_id": 1,
		"chain_id": "B",
		"steps":    100,
	})
	url := fmt.Sprintf("http://%s/run", foldyOperator)
	req, err := http.NewRequest("POST", url, bytes.NewReader(config))
	require.NoError(t, err)
	cl := http.Client{Timeout: time.Minute * 3}
	resp, err := cl.Do(req)
	require.NoError(t, err)
	defer resp.Body.Close()
	require.Equal(t, 500, resp.StatusCode)
	body, err := ioutil.ReadAll(resp.Body)
	require.NoError(t, err)
	require.Equal(t, "model \"1\" not found in \"broken\", options are []", string(body))
}

func TestErrPDBNotFound(t *testing.T) {
	foldyOperator, ok := os.LookupEnv("FOLDY_OPERATOR")
	require.Truef(t, ok, "missing FOLDY_OPERATOR")
	pdbID := "abcd"
	config, _ := json.Marshal(map[string]interface{}{
		"pdb_id":   pdbID,
		"model_id": 0,
		"chain_id": "A",
		"steps":    100,
	})
	url := fmt.Sprintf("http://%s/run", foldyOperator)
	req, err := http.NewRequest("POST", url, bytes.NewReader(config))
	require.NoError(t, err)
	cl := http.Client{Timeout: time.Minute * 3}
	resp, err := cl.Do(req)
	require.NoError(t, err)
	defer resp.Body.Close()
	require.Equal(t, 500, resp.StatusCode)
	body, err := ioutil.ReadAll(resp.Body)
	require.NoError(t, err)
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

func TestErrZeroSteps(t *testing.T) {
	foldyOperator, ok := os.LookupEnv("FOLDY_OPERATOR")
	require.Truef(t, ok, "missing FOLDY_OPERATOR")
	config, _ := json.Marshal(map[string]interface{}{
		"pdb_id":   "1aki",
		"model_id": 0,
		"chain_id": "A",
	})
	url := fmt.Sprintf("http://%s/run", foldyOperator)
	req, err := http.NewRequest("POST", url, bytes.NewReader(config))
	require.NoError(t, err)
	cl := http.Client{Timeout: time.Minute * 3}
	resp, err := cl.Do(req)
	require.NoError(t, err)
	defer resp.Body.Close()
	body, err := ioutil.ReadAll(resp.Body)
	require.NoError(t, err)
	assert.Equal(t, http.StatusBadRequest, resp.StatusCode)
	assert.Equal(t, "expected >1 steps, got 0", string(body))
}

func TestErrInvalidSeed(t *testing.T) {
	foldyOperator, ok := os.LookupEnv("FOLDY_OPERATOR")
	require.Truef(t, ok, "missing FOLDY_OPERATOR")
	config, _ := json.Marshal(map[string]interface{}{
		"pdb_id":   "1aki",
		"model_id": 0,
		"chain_id": "A",
		"steps":    10,
		"seed":     -2,
	})
	url := fmt.Sprintf("http://%s/run", foldyOperator)
	req, err := http.NewRequest("POST", url, bytes.NewReader(config))
	require.NoError(t, err)
	cl := http.Client{Timeout: time.Minute * 3}
	resp, err := cl.Do(req)
	require.NoError(t, err)
	defer resp.Body.Close()
	body, err := ioutil.ReadAll(resp.Body)
	require.NoError(t, err)
	assert.Equal(t, http.StatusBadRequest, resp.StatusCode)
	assert.Equal(t, "invalid seed", string(body))
}

func TestErrMissingChainID(t *testing.T) {
	foldyOperator, ok := os.LookupEnv("FOLDY_OPERATOR")
	require.Truef(t, ok, "missing FOLDY_OPERATOR")
	config, _ := json.Marshal(map[string]interface{}{
		"pdb_id":   "1aki",
		"model_id": 0,
		"steps":    100,
	})
	url := fmt.Sprintf("http://%s/run", foldyOperator)
	req, err := http.NewRequest("POST", url, bytes.NewReader(config))
	require.NoError(t, err)
	cl := http.Client{Timeout: time.Minute * 3}
	resp, err := cl.Do(req)
	require.NoError(t, err)
	defer resp.Body.Close()
	body, err := ioutil.ReadAll(resp.Body)
	require.NoError(t, err)
	assert.Equal(t, http.StatusBadRequest, resp.StatusCode)
	assert.Equal(t, "missing chain_id", string(body))
}

func untar(t *testing.T, fileName string) {
	cmd := exec.Command("tar", "-xzvf", fileName)
	cmd.Dir = filepath.Dir(fileName)
	cmd.Stderr = os.Stderr
	require.Nil(t, cmd.Run())
}

func TestBasicMinim(t *testing.T) {
	foldyOperator, ok := os.LookupEnv("FOLDY_OPERATOR")
	require.Truef(t, ok, "missing FOLDY_OPERATOR")
	pdbID, ok := os.LookupEnv("PDB_ID")
	if !ok {
		pdbID = "1aki"
	}
	pdbID = strings.ToLower(pdbID)
	t.Run(pdbID, func(t *testing.T) {
		steps := 10
		config, _ := json.Marshal(map[string]interface{}{
			"pdb_id":   pdbID,
			"model_id": 0,
			"chain_id": "A",
			"steps":    steps,
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
		files, err := listFiles(fmt.Sprintf("%s_minim/", pdbID))
		require.NoError(t, err)
		require.Equal(t, len(files), steps)
	})
}

type testSuite struct {
	pdbID   string
	modelID int
	chainID string
	primary string
	mask    string
}

func TestCreateVideo(t *testing.T) {
	foldyOperator, ok := os.LookupEnv("FOLDY_OPERATOR")
	require.Truef(t, ok, "missing FOLDY_OPERATOR")
	//suite := &testSuite{
	//	pdbID:   "4jrn",
	//	modelID: 1,
	//	chainID: "A",
	//	primary: "GAHMSELVFEKADSGCVIGKRILAHMQEQIGQPQALENSERLDRILTVAAWPPDVPKRFVSVTTGETRTLVRGAPLGSGGFATVYEATDVETNEELAVKVFMSEKEPTDETMLDLQRESSCYRNFSLAKTAKDAQESCRFMVPSDVVMLEGQPASTEVVIGLTTRWVPNYFLLMMRAEADMSKVISWVFGDASVNKSEFGLVVRMYLSSQAIKLVANVQAQGIVHTDIKPANFLLLKDGRLFLGDFGTYRINNSVGRAIGTPGYEPPERPFQATGITYTFPTDAWQLGITLYCIWCKERPTPADGIWDYLHFADCPSTPELVQDLIRSLLNRDPQKRMLPLQALETAAFKEMDSVVKGAAQNFEQQEHLHTE",
	//	mask:    "----++++++++++++++++++++++++-------++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++--+++++++++++----++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++------",
	//}
	//suite := &testSuite{
	//	pdbID:   "2yo0",
	//	modelID: 1,
	//	chainID: "A",
	//	primary: "MKQIEDKIEEILSKIYHIENEIARIKKLIQNAIGAVTTTPTKYYHANSTEEDSLAVGTDSLAMGAKTIVNADAGIGIGLNTLVMADAINGIAIGSNARANHANSIAMGNGSQTTRGAQTDYTAYNMDTPQNSVGEFSVGSEDGQRQITNVAAGSADTDAVNVGQLKVTDAQVSRNTQSITNLNTQVSNLDTRVTNIENGIGDIVTTGSTKYFKTNTDGADANAQGADSVAIGSGSIAAAENSVALGTNSVADEANTVSVGSSTQQRRITNVAAGVNNTDAVNVAQMKQIEDKIEEILSKIYHIENEIARIKKLIKLHHHHHH",
	//	mask:    "-----------------------------------------++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++-----",
	//}

	var primary, chainID, mask string
	var modelID int
	pdbID, ok := os.LookupEnv("PDB_ID")
	if ok {
		// Specify overrides using environment variables
		pdbID = strings.ToLower(pdbID)
		modelIDStr, ok := os.LookupEnv("MODEL_ID")
		require.True(t, ok)
		modelIDV, err := strconv.ParseInt(modelIDStr, 10, 64)
		require.NoError(t, err)
		modelID = int(modelIDV)
		chainID, ok = os.LookupEnv("CHAIN_ID")
		require.True(t, ok)
		primary, ok = os.LookupEnv("PRIMARY")
		require.True(t, ok)
		mask, ok = os.LookupEnv("MASK")
		require.True(t, ok)
		log.Printf("Using custom PDB %v_%v_%v", pdbID, modelID, chainID)
	} else {
		// Default is 2l0e - a short chain with residues
		// missing only at the ends
		pdbID = "2l0e"
		chainID = "A"
		modelID = 1
		primary = "AKKKDNLLFGSIISAVDPVAVLAVFEEIHKKKA"
		mask = "-+++++++++++++++++++++++++++++++-"
	}

	suite := &testSuite{
		pdbID:   "2l0e",
		modelID: modelID,
		chainID: chainID,
		primary: primary,
		mask:    mask,
	}
	require.NoError(t, os.RemoveAll("/data/tmp"))
	require.NoError(t, os.Mkdir("/data/tmp", 0644))
	require.NoError(t, os.RemoveAll("/data/png"))
	require.NoError(t, os.Mkdir("/data/png", 0644))

	nsteps := 100
	stepsStr, ok := os.LookupEnv("NSTEPS")
	if ok {
		stepsV, err := strconv.ParseInt(stepsStr, 10, 64)
		require.NoError(t, err)
		nsteps = int(stepsV)
	}
	log.Printf("Simulating for %v steps", nsteps)

	t.Run("should be deterministic", func(t *testing.T) {
		require.NoError(t, os.Mkdir(fmt.Sprintf("/data/png/%s", suite.pdbID), 0644))
		var context *fauxgl.Context
		var camera *ribbon.Camera
		config, _ := json.Marshal(map[string]interface{}{
			"pdb_id":   suite.pdbID,
			"model_id": suite.modelID,
			"chain_id": suite.chainID,
			"primary":  suite.primary,
			"mask":     suite.mask,
			"steps":    nsteps,
			"seed":     1,
		})
		url := fmt.Sprintf("http://%s/run", foldyOperator)
		req, err := http.NewRequest("POST", url, bytes.NewReader(config))
		require.NoError(t, err)
		cl := http.Client{Timeout: time.Minute * 10000}
		resp, err := cl.Do(req)
		require.NoError(t, err)
		if resp.StatusCode != 200 {
			msg, _ := ioutil.ReadAll(resp.Body)
			log.Printf("%v", string(msg))
		}
		require.Equal(t, resp.StatusCode, 200)
		defer resp.Body.Close()
		f, err := ioutil.TempFile("/data/tmp", "result-*.tar.gz")
		require.NoError(t, err)
		_, err = io.Copy(f, resp.Body)
		require.NoError(t, err)
		require.Nil(t, f.Close())
		info, err := os.Stat(f.Name())
		require.NoError(t, err)
		require.Greater(t, info.Size(), int64(0))
		untar(t, f.Name())
		require.Nil(t, os.Remove(f.Name()))
		files, err := listFiles(fmt.Sprintf("/data/tmp/%s_minim/", suite.pdbID))
		require.NoError(t, err)
		require.Equal(t, len(files), nsteps)
		for i := 0; i < nsteps; i++ {
			runtime.GC()
			path := fmt.Sprintf("/data/tmp/%s_minim/%s_minim_%d.pdb", suite.pdbID, suite.pdbID, i)
			f, err := os.Open(path)
			require.NoError(t, err)
			r := pdb.NewReader(f)
			models, err := r.ReadAll()
			require.NoError(t, err)
			require.NoError(t, f.Close())
			require.Nil(t, os.Remove(path))
			//for modelID, model := range models {
			//	log.Printf("modelID=%v", modelID)
			//	for _, chain := range model.Chains {
			//		log.Printf("\tchain %v", chain.ChainID)
			//		for _, residue := range chain.Residues[:10] {
			//			atomNames := make([]string, len(residue.Atoms), len(residue.Atoms))
			//			for j, atom := range residue.Atoms {
			//				atomNames[j] = atom.Name
			//			}
			//			log.Printf("\t%v %v", residue.ResName, atomNames)
			//		}
			//	}
			//}
			assert.Equal(t, 1, len(models))
			model := models[0]
			assert.Equal(t, 1, len(model.Chains))
			chain := model.Chains[0]
			numKnownResidues := 0
			for c := 0; c < len(suite.mask); c++ {
				if suite.mask[c] == '+' {
					numKnownResidues++
				}
			}
			numActual := 0
			for _, residue := range chain.Residues {
				if residue.ResName == "SOL" {
					break
				}
				numActual++
			}
			assert.Equal(t, numKnownResidues, numActual)
			mesh := ribbon.ModelMesh(model)
			if camera == nil {
				m := mesh.BiUnitCube()
				cam := ribbon.PositionCamera(model, m)
				camera = &cam
			} else {
				mesh.BiUnitCube()
			}
			context = fauxgl.NewContext(int(size*scale*camera.Aspect), size*scale)
			matrix := fauxgl.LookAt(camera.Eye, camera.Center, camera.Up).Perspective(camera.Fovy, camera.Aspect, 1, 100)
			light := camera.Eye.Sub(camera.Center).Normalize()
			shader := fauxgl.NewPhongShader(matrix, light, camera.Eye)
			shader.AmbientColor = fauxgl.Gray(0.3)
			shader.DiffuseColor = fauxgl.Gray(0.9)
			context.Shader = shader
			context.ClearColorBufferWith(fauxgl.HexColor("1D181F"))
			context.DrawTriangles(mesh.Triangles)
			image := context.Image()
			image = resize.Resize(uint(size*camera.Aspect), size, image, resize.Bilinear)
			require.NoError(t, fauxgl.SavePNG(fmt.Sprintf("/data/png/%s/%s_%d.png", suite.pdbID, suite.pdbID, i), image))
		}
	})
}

/*func TestConfiguredMinim(t *testing.T) {
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
			})
		}()
		<-doneOuter
		return nil
	})
	defer pool.Close()

	//"2gd3"
	//"2KAM",
	//"2KXI",
	//"2LI5",
	//"1X6B",

	pdbIDs := []string{
		"2L0E",
		"2K0M",
		"2KKP",
		"1TRL",
		"2LOJ",
		"1UJV",
		"2L9Y",
		"1NXI",
		"2KC6",
		"1NR3",
		"1V7F",
		"2K3O",
		"1QEY",
		"1E0N",
		"2LS2",
	}
	numPDBs := len(pdbIDs)
	dones := make([]chan int, numPDBs, numPDBs)
	for i, pdbID := range pdbIDs {
		done := make(chan int, 1)
		dones[i] = done
		go func(pdbID string, done chan<- int) {
			pool.Process(pdbID)
			done <- 0
			close(done)
		}(pdbID, done)
	}
	for _, done := range dones {
		<-done
	}
}

func TestErrBrokenRTP(t *testing.T) {
	foldyOperator, ok := os.LookupEnv("FOLDY_OPERATOR")
	require.Truef(t, ok, "missing FOLDY_OPERATOR")
	pdbID := "1jlo"
	t.Run(pdbID, func(t *testing.T) {
		steps := 10
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
		require.Equal(t, resp.StatusCode, 500)
		defer resp.Body.Close()
		body, err := ioutil.ReadAll(resp.Body)
		require.NoError(t, err)
		require.True(t, strings.Contains(string(body), " was not found in rtp entry "))
	})
}*/
