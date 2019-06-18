package api

import (
	"net/http"
	"io/ioutil"
	"encoding/json"
	"github.com/vipshop/tuplenet/control/logger"
	"os/exec"
	"fmt"
	"io"
	"bytes"
)

type Edge interface {
	AddEdge()
	DelEdge()
	InitEdge()
}

/*
   the api must run in a tuplenet edge node ; default edge add shell is /apps/svr/vip-tuplenet/src/tuplenet/tools/edge-operate.py use env EDGE_SHELL_PATH to change
*/

func (b *TuplenetAPI) InitEdge() {
	var (
		m              EdgeRequest
		res            Response
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
		res.Code = http.StatusBadRequest
		res.Message = "request phyBr inner virt vip and extGw param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	endPointArg := "--endpoint=" + etcdHost
	preFixArg := EdgeEtcdPrefix(etcdPrefix)
	vipArg := "--vip=" + vip
	phyBrArg := "--phy_br=" + phyBr
	virtArg := "--virt=" + virt
	innerArg := "--inner=" + inner
	extGwArg := "--ext_gw=" + extGw

	cmd := exec.Command(edgeShellPath, endPointArg, preFixArg, "--op=init", vipArg, phyBrArg, virtArg, innerArg, extGwArg)
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err := cmd.Start()
	io.WriteString(stdin, "yes\n")

	if err != nil {
		initStr := fmt.Sprintf("InitEdge failed phyBr %s inner %s virt %s vip %s extGw %s err %s outErr %s outStr %s", phyBr, inner, virt, vip, extGw, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(initStr)
		res.Code = http.StatusBadRequest
		res.Message = initStr
		b.Data["json"] = res
		b.ServeJSON()
		return

	}
	err = cmd.Wait()
	if err != nil {
		initStr := fmt.Sprintf("InitEdge failed phyBr %s inner %s virt %s vip %s extGw %s err %s outErr %s outStr %s", phyBr, inner, virt, vip, extGw, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(initStr)
		res.Code = http.StatusBadRequest
		res.Message = initStr
		b.Data["json"] = res
		b.ServeJSON()
		return

	}

	logger.Infof("InitEdge success phyBr %s inner %s virt %s vip %s extGw %s", phyBr, inner, virt, vip, extGw)
	res.Code = http.StatusOK
	res.Message = "InitEdge success "
	b.Data["json"] = res
	b.ServeJSON()

}

func (b *TuplenetAPI) AddEdge() {
	var (
		m              EdgeRequest
		res            Response
		stdout, stderr bytes.Buffer
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	vip := m.Vip //  the virtual ip(like:2.2.2.2/24) of edge node
	phyBr := m.PhyBr
	logger.Debugf("AddEdge get param vip %s phyBr %s", vip, phyBr)

	if vip == "" || phyBr == "" {
		logger.Errorf("AddEdge get param failed vip %s phyBr %s", vip, phyBr)
		res.Code = http.StatusBadRequest
		res.Message = "request vip and phyBr param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	endPointArg := "--endpoint=" + etcdHost
	preFixArg := EdgeEtcdPrefix(etcdPrefix)
	phyBrArg := "--phy_br=" + phyBr
	vipArg := "--vip=" + vip
	cmd := exec.Command(edgeShellPath, endPointArg, preFixArg, "--op=add", vipArg, phyBrArg)
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err := cmd.Start()
	io.WriteString(stdin, "yes\n")
	if err != nil {
		addStr := fmt.Sprintf("AddEdge failed vip %s err %s outErr %s outStr %s", vip, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(addStr)
		res.Code = http.StatusInternalServerError
		res.Message = addStr
		b.Data["json"] = res
		b.ServeJSON()
		return

	}
	err = cmd.Wait()
	if err != nil {
		addStr := fmt.Sprintf("AddEdge wait response failed vip %s err %s outErr %s outStr %s", vip, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(addStr)
		res.Code = http.StatusInternalServerError
		res.Message = addStr
		b.Data["json"] = res
		b.ServeJSON()
		return

	}
	logger.Infof("AddEdge success vip %s phyBr %s", vip, phyBr)
	res.Code = http.StatusOK
	res.Message = "AddEdge success "
	b.Data["json"] = res
	b.ServeJSON()

}

func (b *TuplenetAPI) DelEdge() {
	var (
		m              EdgeRequest
		res            Response
		stdout, stderr bytes.Buffer
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	vip := m.Vip //  the virtual ip(like:2.2.2.2/24) of edge node
	logger.Debugf("DelEdge get param vip %s", vip)

	if vip == "" {
		logger.Errorf("DelEdge get param failed vip %s", vip)
		res.Code = http.StatusBadRequest
		res.Message = "request vip param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	endPointArg := "--endpoint=" + etcdHost
	preFixArg := EdgeEtcdPrefix(etcdPrefix)
	vipArg := "--vip=" + vip
	cmd := exec.Command(edgeShellPath, endPointArg, preFixArg, "--op=remove", vipArg)
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err := cmd.Start()
	io.WriteString(stdin, "yes\n")

	if err != nil {
		delStr := fmt.Sprintf("DelEdge exec command failed vip %s err %s outErr %s outStr %s", vip, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(delStr)
		res.Code = http.StatusBadRequest
		res.Message = fmt.Sprintf(delStr)
		b.Data["json"] = res
		b.ServeJSON()
		return

	}

	err = cmd.Wait()
	if err != nil {
		delStr := fmt.Sprintf("DelEdge wait response failed vip %s err %s outErr %s outStr %s", vip, err, stderr.Bytes(), stdout.Bytes())
		logger.Errorf(delStr)
		res.Code = http.StatusBadRequest
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return

	}
	logger.Infof("DelEdge success vip %s", vip)
	res.Code = http.StatusOK
	res.Message = "DelEdge success "
	b.Data["json"] = res
	b.ServeJSON()

}
