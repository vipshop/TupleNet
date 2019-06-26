package api

import (
	"encoding/json"
	"github.com/vipshop/tuplenet/control/logger"
	"os/exec"
	"fmt"
	"io"
	"bytes"
	"os"
)

type Edge interface {
	AddEdge()
	DelEdge()
	InitEdge()
}

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
		logger.Infof("InitEdge decode body failed %s", err)
		b.BadResponse("InitEdge decode body failed please check param")
		return
	}
	logger.Infof("InitEdge get param phyBr %s inner %s virt %s vip %s extGw %s endpoint %s prefix %s", m.PhyBr, m.Inner, m.Virt, m.Vip, m.ExtGw, endPointArg, edgePrefix)

	if m.PhyBr == "" || m.Inner == "" || m.Virt == "" || m.Vip == "" || m.ExtGw == "" {
		logger.Infof("InitEdge get param failed phyBr %s inner %s virt %s vip %s extGw %s", m.PhyBr, m.Inner, m.Virt, m.Vip, m.ExtGw)
		b.BadResponse("request phyBr inner virt vip and extGw param")
		return
	}

	vipArg := "--vip=" + m.Vip
	phyBrArg := "--phy_br=" + m.PhyBr
	virtArg := "--virt=" + m.Virt
	innerArg := "--inner=" + m.Inner
	extGwArg := "--ext_gw=" + m.ExtGw
	cmd := exec.Command("python", edgeShellPath, endPointArg, edgePrefix, "--op=init", vipArg, phyBrArg, virtArg, innerArg, extGwArg)
	// for test case use specific ovs dir, not use default ovs-vsctl get Open_Vswitch . external_ids:system-id
	if ovsTmpDir != "" {
		cmd.Env = append(os.Environ(), ovsDir, ovsLog, ovsDbdir, ovsSysConfDir, ovsPkgDatadir)
	}
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err = cmd.Start()
	io.WriteString(stdin, "yes\n")

	if err != nil {
		initStr := fmt.Sprintf("InitEdge failed phyBr %s inner %s virt %s vip %s extGw %s err %s outErr %s outStr %s", m.PhyBr, m.Inner, m.Virt, m.Vip, m.ExtGw, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(initStr)
		b.InternalServerErrorResponse(initStr)
		return
	}
	err = cmd.Wait()
	if err != nil {
		initStr := fmt.Sprintf("InitEdge failed phyBr %s inner %s virt %s vip %s extGw %s err %s outErr %s outStr %s", m.PhyBr, m.Inner, m.Virt, m.Vip, m.ExtGw, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(initStr)
		b.InternalServerErrorResponse(initStr)
		return
	}

	logger.Infof("InitEdge success phyBr %s inner %s virt %s vip %s extGw %s", m.PhyBr, m.Inner, m.Virt, m.Vip, m.ExtGw)
	b.NormalResponse("InitEdge success")
}

func (b *TuplenetAPI) AddEdge() {
	var (
		m              EdgeRequest
		stdout, stderr bytes.Buffer
	)
	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		logger.Infof("AddEdge decode body failed %s", err)
		b.BadResponse("AddEdge decode body failed please check param")
		return
	}
	logger.Infof("AddEdge get param vip %s phyBr %s endpoint %s prefix %s", m.Vip, m.PhyBr, endPointArg, edgePrefix)

	if m.Vip == "" || m.PhyBr == "" {
		logger.Infof("AddEdge get param failed vip %s phyBr %s", m.Vip, m.PhyBr)
		b.BadResponse("request vip and phyBr param")
		return
	}

	phyBrArg := "--phy_br=" + m.PhyBr
	vipArg := "--vip=" + m.Vip
	cmd := exec.Command("python", edgeShellPath, endPointArg, edgePrefix, "--op=add", vipArg, phyBrArg)
	if ovsTmpDir != "" {
		cmd.Env = append(os.Environ(), ovsDir, ovsLog, ovsDbdir, ovsSysConfDir, ovsPkgDatadir)
	}
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err = cmd.Start()
	io.WriteString(stdin, "yes\n")
	if err != nil {
		addStr := fmt.Sprintf("AddEdge failed vip %s err %s outErr %s outStr %s", m.Vip, err, stderr.Bytes(), stdout.Bytes())
		b.InternalServerErrorResponse(addStr)
		return
	}
	err = cmd.Wait()
	if err != nil {
		addStr := fmt.Sprintf("AddEdge wait response failed vip %s err %s outErr %s outStr %s", m.Vip, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	logger.Infof("AddEdge success vip %s phyBr %s", m.Vip, m.PhyBr)
	b.NormalResponse("AddEdge success")
}

func (b *TuplenetAPI) DelEdge() {
	var (
		m              EdgeRequest
		stdout, stderr bytes.Buffer
	)
	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		logger.Infof("DelEdge decode body failed %s", err)
		b.BadResponse("DelEdge decode body failed please check param")
		return
	}
	logger.Infof("DelEdge get param vip %s endpoint %s prefix %s", m.Vip, endPointArg, edgePrefix)

	if m.Vip == "" {
		logger.Infof("DelEdge get param failed vip %s", m.Vip)
		b.BadResponse("request vip param")
		return
	}

	vipArg := "--vip=" + m.Vip
	cmd := exec.Command("python", edgeShellPath, endPointArg, edgePrefix, "--op=remove", vipArg)
	if ovsTmpDir != "" {
		cmd.Env = append(os.Environ(), ovsDir, ovsLog, ovsDbdir, ovsSysConfDir, ovsPkgDatadir)
	}
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err = cmd.Start()
	io.WriteString(stdin, "yes\n")

	if err != nil {
		delStr := fmt.Sprintf("DelEdge exec command failed vip %s err %s outErr %s outStr %s", m.Vip, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	err = cmd.Wait()
	if err != nil {
		delStr := fmt.Sprintf("DelEdge wait response failed vip %s err %s outErr %s outStr %s", m.Vip, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	logger.Infof("DelEdge success vip %s", m.Vip)
	b.NormalResponse("DelEdge success")
}
