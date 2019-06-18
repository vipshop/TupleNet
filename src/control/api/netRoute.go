package api

import (
	"net"
	"fmt"
	"sort"
	"io/ioutil"
	"encoding/json"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/comm"
	"github.com/vipshop/tuplenet/control/logger"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
)

func (b *TuplenetAPI) AddNAT() {
	var (
		m   NetRequest
		err error
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	natName := m.NatName
	cidr := m.Cidr
	xlateType := m.XlateType
	xlateIP := m.XlateIP
	logger.Debugf("AddNAT get param route %s natName %s cidr %s xlateType %s xlateIP %s", name, natName, cidr, xlateType, xlateIP)

	if name == "" || natName == "" || cidr == "" || xlateType == "" || xlateIP == "" {
		logger.Errorf("AddNAT get param failed route %s natName %s cidr %s xlateType %s xlateIP %s", name, natName, cidr, xlateType, xlateIP)
		b.BadResponse("request route natName cidr xlateType and xlateIP param")
		return
	}
	ip, prefix, err := comm.ParseCIDR(cidr)
	if err != nil {
		addStr := fmt.Sprintf("AddNAT parse cidr failed route %s cider string %s", name, cidr)
		b.InternalServerErrorResponse(addStr)
		return
	}
	// if xlateType neither snat or dnat return failed
	if xlateType != "snat" && xlateType != "dnat" {
		addStr := fmt.Sprintf("AddNAT invalid translate type, must be snat/dnat: %s", xlateType)
		logger.Errorf(addStr)
		b.BadResponse(addStr)
		return
	}

	if net.ParseIP(xlateIP) == nil {
		addStr := fmt.Sprintf("AddNAT invalid translate IP: %s", xlateIP)
		logger.Errorf(addStr)
		b.BadResponse(addStr)
		return
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		addStr := fmt.Sprintf("AddNAT get route failed %s", err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	_, err = controller.GetRouterNAT(router, natName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		addStr := fmt.Sprintf("AddNAT get route failed %s", err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	if err == nil {
		addStr := fmt.Sprintf("AddNAT route %s nat %s exists", name, natName)
		logger.Infof(addStr)
		b.NormalResponse(addStr)
		return
	}

	nat := router.CreateNAT(natName, ip, prefix, xlateType, xlateIP)
	err = controller.Save(nat)
	if err != nil {
		addStr := fmt.Sprintf("AddNAT create nat failed %s", err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	logger.Infof("AddNAT success route %s natName %s cidr %s xlateType %s xlateIP %s", name, natName, cidr, xlateType, xlateIP)
	b.NormalResponse("AddNAT success")
}

func (b *TuplenetAPI) DelNAT() {
	var (
		m   NetRequest
		err error
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	natName := m.NatName
	logger.Debugf("DelNAT get param route %s natName %s", name, natName)

	if name == "" || natName == "" {
		logger.Errorf("DelNAT get param failed route %s natName %s", name, natName)
		b.BadResponse("request route and natName param")
		return
	}
	router, err := controller.GetRouter(name)
	if err != nil {
		delStr := fmt.Sprintf("DelNAT get route failed %s", err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	port, err := controller.GetRouterNAT(router, natName)
	if err != nil {
		delStr := fmt.Sprintf("DelNAT get route nat failed %s", err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	err = controller.Delete(false, port)
	if err != nil {
		delStr := fmt.Sprintf("DelNAT delete failed %s", err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	logger.Infof("DelNAT router %s NAT %s deleted", name, natName)
	b.NormalResponse("DelNAT success")
}

func (b *TuplenetAPI) ShowNAT() {
	var (
		m    NetRequest
		err  error
		nats []*logicaldev.NAT
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	natName := m.NatName
	logger.Debugf("ShowNAT get param route %s natName %s", name, natName)

	if name == "" {
		logger.Errorf("ShowNAT get param failed route %s ", name)
		b.BadResponse("request route param")
		return
	}
	router, err := controller.GetRouter(name)
	if err != nil {
		showStr := fmt.Sprintf("ShowNAT get route failed %s", err)
		logger.Errorf(showStr)
		b.InternalServerErrorResponse(showStr)
		return
	}

	if natName == "" { // show all nats
		nats, err = controller.GetRouterNATs(router)
		if err != nil {
			showStr := fmt.Sprintf("ShowNAT get route nats failed %s", err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}
	} else {
		nat, err := controller.GetRouterNAT(router, natName)
		if err != nil {
			showStr := fmt.Sprintf("ShowNAT get route nat failed %s", err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}

		nats = []*logicaldev.NAT{nat}
	}

	logger.Debugf("ShowNAT success route %s natName %s", name, natName)
	sort.Slice(nats, func(i, j int) bool { return nats[i].Name < nats[j].Name })
	b.NormalResponse(nats)
}
