package api

import (
	"encoding/json"
	"github.com/vipshop/tuplenet/control/logger"
	"os/exec"
	"io"
	"bytes"
	"net/http"
	"context"
	"time"
)

/*
   the edge api must run in a tuplenet edge node ; default edge add shell is /apps/svr/vip-tuplenet/src/tuplenet/tools/edge-operate.py use env EDGE_SHELL_PATH to change
*/

func (b *TuplenetAPI) InitEdge() {
	var (
		m              EdgeRequest
		stdout, stderr bytes.Buffer
	)
	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "InitEdge decode get param body failed %s please check param", err)
		return
	}
	logger.Infof("InitEdge get param phyBr %s inner %s virt %s vip %s extGw %s endpoint %s prefix %s", m.PhyBr, m.Inner, m.Virt, m.Vip, m.ExtGw, endPointArg, edgePrefix)

	if CheckNilParam(m.PhyBr, m.Inner, m.Virt, m.Vip, m.ExtGw) {
		b.Response(http.StatusBadRequest, "InitEdge get param failed phyBr %s inner %s virt %s vip %s extGw %s", nil, m.PhyBr, m.Inner, m.Virt, m.Vip, m.ExtGw)
		return
	}

	vipArg := "--vip=" + m.Vip
	phyBrArg := "--phy_br=" + m.PhyBr
	virtArg := "--virt=" + m.Virt
	innerArg := "--inner=" + m.Inner
	extGwArg := "--ext_gw=" + m.ExtGw
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "python", edgeShellPath, endPointArg, edgePrefix, "--op=init", vipArg, phyBrArg, virtArg, innerArg, extGwArg)
	// for test case use specific ovs dir, not use default ovs-vsctl get Open_Vswitch . external_ids:system-id
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err = cmd.Start()
	io.WriteString(stdin, "yes\n")

	if err != nil {
		b.Response(http.StatusInternalServerError, "InitEdge failed phyBr %s inner %s virt %s vip %s extGw %s outErr %s outStr %s err %s", err, m.PhyBr, m.Inner, m.Virt, m.Vip, m.ExtGw, stderr.Bytes(), stdout.Bytes())
		return
	}
	err = cmd.Wait()
	if err != nil {
		b.Response(http.StatusInternalServerError, "InitEdge wait failed phyBr %s inner %s virt %s vip %s extGw %s outErr %s outStr %s err %s", err, m.PhyBr, m.Inner, m.Virt, m.Vip, m.ExtGw, stderr.Bytes(), stdout.Bytes())
		return
	}

	b.Response(http.StatusOK, "InitEdge success phyBr %s inner %s virt %s vip %s extGw %s", nil, m.PhyBr, m.Inner, m.Virt, m.Vip, m.ExtGw)
}

func (b *TuplenetAPI) AddEdge() {
	var (
		m              EdgeRequest
		stdout, stderr bytes.Buffer
	)
	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "AddEdge decode get param body failed %s", err)
		return
	}
	logger.Infof("AddEdge get param vip %s phyBr %s endpoint %s prefix %s", m.Vip, m.PhyBr, endPointArg, edgePrefix)

	if CheckNilParam(m.Vip, m.PhyBr) {
		b.Response(http.StatusBadRequest, "AddEdge get param failed vip %s phyBr %s", nil, m.Vip, m.PhyBr)
		return
	}

	phyBrArg := "--phy_br=" + m.PhyBr
	vipArg := "--vip=" + m.Vip
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "python", edgeShellPath, endPointArg, edgePrefix, "--op=add", vipArg, phyBrArg)
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err = cmd.Start()
	io.WriteString(stdin, "yes\n")
	if err != nil {
		b.Response(http.StatusInternalServerError, "AddEdge failed vip %s outErr %s outStr %s err %s ", err, m.Vip, stderr.Bytes(), stdout.Bytes())
		return
	}
	err = cmd.Wait()
	if err != nil {
		b.Response(http.StatusInternalServerError, "AddEdge wait failed vip %s outErr %s outStr %s err %s ", err, m.Vip, stderr.Bytes(), stdout.Bytes())
		return
	}

	b.Response(http.StatusOK, "AddEdge success vip %s phyBr %s", nil, m.Vip, m.PhyBr)
}

func (b *TuplenetAPI) DelEdge() {
	var (
		m              EdgeRequest
		stdout, stderr bytes.Buffer
	)
	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "DelEdge decode get param body failed %s", err)
		return
	}
	logger.Infof("DelEdge get param vip %s endpoint %s prefix %s", m.Vip, endPointArg, edgePrefix)

	if CheckNilParam(m.Vip) {
		b.Response(http.StatusBadRequest, "DelEdge get param failed vip %s", nil, m.Vip)
		return
	}

	vipArg := "--vip=" + m.Vip
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "python", edgeShellPath, endPointArg, edgePrefix, "--op=remove", vipArg)
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err = cmd.Start()
	io.WriteString(stdin, "yes\n")

	if err != nil {
		b.Response(http.StatusInternalServerError, "DelEdge failed vip %s outErr %s outStr %s err %s", err, m.Vip, stderr.Bytes(), stdout.Bytes())
		return
	}

	err = cmd.Wait()
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelEdge wait failed vip %s outErr %s outStr %s err %s", err, m.Vip, stderr.Bytes(), stdout.Bytes())
		return
	}

	b.Response(http.StatusOK, "DelEdge success vip %s", nil, m.Vip)
}
