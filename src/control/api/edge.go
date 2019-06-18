package api

import (
	"net/http"
	"io/ioutil"
	"encoding/json"
	"github.com/vipshop/tuplenet/control/logger"
	"os/exec"
	"fmt"
	"os"
	"io"
)

/*
   the api must run in a tuplenet edge node ; default edge add shell is /apps/svr/vip-tuplenet/src/tuplenet/tools/edge-operate.py use env EDGE_SHELL_PATH to change
*/

func (b *TuplenetAPI) InitEdge() {
	var (
		m   EdgeRequest
		res Response
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	phyBr := m.PhyBr
	inner := m.Inner //  the inner network(connect  virt to phy), default is 100.64.88.100/24
	virt := m.Virt   //  the whole virtual network(like:5.5.5.5/16)
	vip := m.Vip     //  the virtual ip(like:2.2.2.2/24) of edge node
	extGw := m.ExtGw // extGw the physical gateway ip address

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
	opArg := "--op=init"
	vipArg := "--vip=" + vip
	phyBrArg := "--phy_br=" + phyBr
	virtArg := "--virt=" + virt
	innerArg := "--inner=" + inner
	extGwArg := "--ext_gw=" + extGw

	cmd := exec.Command(edgeShellPath, endPointArg, preFixArg, opArg, vipArg, phyBrArg, virtArg, innerArg, extGwArg)

	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err := cmd.Start()
	io.WriteString(stdin, "yes\n")

	if err != nil {
		logger.Errorf("InitEdge failed phyBr %s inner %s virt %s vip %s extGw %s err %s out %s", phyBr, inner, virt, vip, extGw, cmd.Stderr, cmd.Stdout)
		res.Code = http.StatusBadRequest
		res.Message = fmt.Sprintf("InitAdge failed phyBr %s inner %s virt %s vip %s extGw %s err %s out %s", phyBr, inner, virt, vip, extGw, cmd.Stderr, cmd.Stdout)
		b.Data["json"] = res
		b.ServeJSON()
		return

	}
	err = cmd.Wait()
	if err != nil {
		logger.Errorf("InitEdge failed phyBr %s inner %s virt %s vip %s extGw %s err %s out %s", phyBr, inner, virt, vip, extGw, cmd.Stderr, cmd.Stdout)
		res.Code = http.StatusBadRequest
		res.Message = fmt.Sprintf("InitAdge failed phyBr %s inner %s virt %s vip %s extGw %s err %s out %s", phyBr, inner, virt, vip, extGw, cmd.Stderr, cmd.Stdout)
		b.Data["json"] = res
		b.ServeJSON()
		return

	}

	logger.Debugf("InitEdge success phyBr %s inner %s virt %s vip %s extGw %s", phyBr, inner, virt, vip, extGw)
	res.Code = http.StatusOK
	res.Message = "InitEdge success "
	b.Data["json"] = res
	b.ServeJSON()

}

func (b *TuplenetAPI) AddEdge() {
	var (
		m   EdgeRequest
		res Response
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	vip := m.Vip //  the virtual ip(like:2.2.2.2/24) of edge node
	phyBr := m.PhyBr

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
	opArg := "--op=add"
	phyBrArg := "--phy_br=" + phyBr
	vipArg := "--vip=" + vip
	cmd := exec.Command(edgeShellPath, endPointArg, preFixArg, opArg, vipArg, phyBrArg)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err := cmd.Start()
	io.WriteString(stdin, "yes\n")
	if err != nil {
		logger.Errorf("AddEdge failed vip %s err %s out %s", vip, cmd.Stderr, cmd.Stdout)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("AddEdge failed vip %s err %s", vip, cmd.Stderr)
		b.Data["json"] = res
		b.ServeJSON()
		return

	}
	err = cmd.Wait()
	if err != nil {
		logger.Errorf("AddEdge failed vip %s err %s out %s", vip, cmd.Stderr, cmd.Stdout)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("AddEdge failed vip %s err %s", vip, cmd.Stderr)
		b.Data["json"] = res
		b.ServeJSON()
		return

	}
	logger.Debugf("AddEdge success vip %s phyBr %s", vip, phyBr)
	res.Code = http.StatusOK
	res.Message = "AddEdge success "
	b.Data["json"] = res
	b.ServeJSON()

}

func (b *TuplenetAPI) DelEdge() {
	var (
		m   EdgeRequest
		res Response
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	vip := m.Vip //  the virtual ip(like:2.2.2.2/24) of edge node

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
	opArg := "--op=remove"
	vipArg := "--vip=" + vip
	cmd := exec.Command(edgeShellPath, endPointArg, preFixArg, opArg, vipArg)

	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	stdin, _ := cmd.StdinPipe()
	defer stdin.Close()
	err := cmd.Start()
	io.WriteString(stdin, "yes\n")

	if err != nil {
		logger.Errorf("DelEdge failed vip %s err %s out %s", vip, cmd.Stderr, cmd.Stdout)
		res.Code = http.StatusBadRequest
		res.Message = fmt.Sprintf("DelEdge failed vip %s err %s", vip, cmd.Stderr)
		b.Data["json"] = res
		b.ServeJSON()
		return

	}

	err = cmd.Wait()
	if err != nil {
		logger.Errorf("DelEdge failed vip %s err %s out %s", vip, cmd.Stderr, cmd.Stdout)
		res.Code = http.StatusBadRequest
		res.Message = fmt.Sprintf("DelEdge failed vip %s err %s", vip, cmd.Stderr)
		b.Data["json"] = res
		b.ServeJSON()
		return

	}
	logger.Debugf("DelEdge success vip %s", vip)
	res.Code = http.StatusOK
	res.Message = "DelEdge success "
	b.Data["json"] = res
	b.ServeJSON()

}
