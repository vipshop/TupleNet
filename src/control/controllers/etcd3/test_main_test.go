package etcd3

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"testing"
)

const etcdDataDir = "/tmp/tuplenet_pkg_test/"

func TestMain(m *testing.M) {
	ctx, cancel := context.WithCancel(context.Background())
	var cmd *exec.Cmd

	go func() {
		os.RemoveAll(etcdDataDir)
		cmd = exec.CommandContext(ctx, "etcd", "--data-dir", etcdDataDir)
		if data, err := cmd.CombinedOutput(); err != nil && ctx.Err() == nil {
			log.Fatal(string(data))
		}
	}()

	code := m.Run()

	// clean up
	if code != 0 {
		c := exec.Command("etcdctl", "get", "--prefix", "")
		c.Env = []string{"ETCDCTL_API=3"}
		data, _ := c.CombinedOutput()
		fmt.Printf("---------- etcd3 data dumpped below ----------\n%s\n", string(data))
	}

	cancel()
	log.Print("waiting for etcd3 to exit")
	if cmd != nil {
		cmd.Wait()
	}
	os.RemoveAll(etcdDataDir)

	os.Exit(code)
}
