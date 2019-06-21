package api

import (
	"io/ioutil"
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

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	phyBr := m.PhyBr
	inner := m.Inner //  the inner network(connect  virt to phy), default is 100.64.88.100/24
	virt := m.Virt   //  the whole virtual network(like:5.5.5.5/16)
	vip := m.Vip     //  the virtual ip(like:2.2.2.2/24) of edge node
	extGw := m.ExtGw // extGw the physical gateway ip address
	logger.Debugf("InitEdge get param phyBr %s inner %s virt %s vip %s extGw %s", phyBr, inner, virt, vip, extGw)

	if phyBr == "" || inner == "" || virt == "" || vip == "" || extGw == "" {
		logger.Errorf("InitEdge get param failed phyBr %s inner %s virt %s vip %s extGw %s", phyBr, inner, virt, vip, extGw)
		b.BadResponse("request phyBr inner virt vip and extGw param")
		return
	}

	vipArg := "--vip=" + vip
	phyBrArg := "--phy_br=" + phyBr
	virtArg := "--virt=" + virt
	innerArg := "--inner=" + inner
	extGwArg := "--ext_gw=" + extGw
	cmd := exec.Command("python", edgeShellPath, endPointArg, edgePrefix, "--op=init", vipArg, phyBrArg, virtArg, innerArg, extGwArg)
	// for test case use specific ovs dir, not use default ovs-vsctl get Open_Vswitch . external_ids:system-id
	if ovsTmpDir != "" {
		cmd.Env = append(os.Environ(), ovsDir, ovsLog, ovsDbdir, ovsSysConfDir, ovsPkgDatadir)
	}
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err := cmd.Start()
	io.WriteString(stdin, "yes\n")

	if err != nil {
		initStr := fmt.Sprintf("InitEdge failed phyBr %s inner %s virt %s vip %s extGw %s err %s outErr %s outStr %s", phyBr, inner, virt, vip, extGw, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(initStr)
		b.InternalServerErrorResponse(initStr)
		return
	}
	err = cmd.Wait()
	if err != nil {
		initStr := fmt.Sprintf("InitEdge failed phyBr %s inner %s virt %s vip %s extGw %s err %s outErr %s outStr %s", phyBr, inner, virt, vip, extGw, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(initStr)
		b.InternalServerErrorResponse(initStr)
		return
	}

	logger.Infof("InitEdge success phyBr %s inner %s virt %s vip %s extGw %s", phyBr, inner, virt, vip, extGw)
	b.NormalResponse("InitEdge success")
}

func (b *TuplenetAPI) AddEdge() {
	var (
		m              EdgeRequest
		stdout, stderr bytes.Buffer
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	vip := m.Vip //  the virtual ip(like:2.2.2.2/24) of edge node
	phyBr := m.PhyBr
	logger.Debugf("AddEdge get param vip %s phyBr %s", vip, phyBr)

	if vip == "" || phyBr == "" {
		logger.Errorf("AddEdge get param failed vip %s phyBr %s", vip, phyBr)
		b.BadResponse("request vip and phyBr param")
		return
	}

	phyBrArg := "--phy_br=" + phyBr
	vipArg := "--vip=" + vip
	cmd := exec.Command("python", edgeShellPath, endPointArg, etcdPrefix, "--op=add", vipArg, phyBrArg)
	if ovsTmpDir != "" {
		cmd.Env = append(os.Environ(), ovsDir, ovsLog, ovsDbdir, ovsSysConfDir, ovsPkgDatadir)
	}
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err := cmd.Start()
	io.WriteString(stdin, "yes\n")
	if err != nil {
		addStr := fmt.Sprintf("AddEdge failed vip %s err %s outErr %s outStr %s", vip, err, stderr.Bytes(), stdout.Bytes())
		b.InternalServerErrorResponse(addStr)
		return
	}
	err = cmd.Wait()
	if err != nil {
		addStr := fmt.Sprintf("AddEdge wait response failed vip %s err %s outErr %s outStr %s", vip, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	logger.Infof("AddEdge success vip %s phyBr %s", vip, phyBr)
	b.NormalResponse("AddEdge success")
}

func (b *TuplenetAPI) DelEdge() {
	var (
		m              EdgeRequest
		stdout, stderr bytes.Buffer
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	vip := m.Vip //  the virtual ip(like:2.2.2.2/24) of edge node

	logger.Debugf("DelEdge get param vip %s", vip)

	if vip == "" {
		logger.Errorf("DelEdge get param failed vip %s", vip)
		b.BadResponse("request vip param")
		return
	}

	vipArg := "--vip=" + vip
	cmd := exec.Command("python", edgeShellPath, endPointArg, edgePrefix, "--op=remove", vipArg)
	if ovsTmpDir != "" {
		cmd.Env = append(os.Environ(), ovsDir, ovsLog, ovsDbdir, ovsSysConfDir, ovsPkgDatadir)
	}
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err := cmd.Start()
	io.WriteString(stdin, "yes\n")

	if err != nil {
		delStr := fmt.Sprintf("DelEdge exec command failed vip %s err %s outErr %s outStr %s", vip, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	err = cmd.Wait()
	if err != nil {
		delStr := fmt.Sprintf("DelEdge wait response failed vip %s err %s outErr %s outStr %s", vip, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	logger.Infof("DelEdge success vip %s", vip)
	b.NormalResponse("DelEdge success")
}
