package api

import (
	"net"
	"fmt"
	"sort"
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

	err = json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		logger.Infof("AddNAT decode body failed %s", err)
		b.BadResponse("AddNAT decode body failed please check param")
		return
	}
	logger.Infof("AddNAT get param route %s natName %s cidr %s xlateType %s xlateIP %s", m.Route, m.NatName, m.Cidr, m.XlateType, m.XlateIP)

	if m.Route == "" || m.NatName == "" || m.Cidr == "" || m.XlateType == "" || m.XlateIP == "" {
		logger.Infof("AddNAT get param failed route %s natName %s cidr %s xlateType %s xlateIP %s", m.Route, m.NatName, m.Cidr, m.XlateType, m.XlateIP)
		b.BadResponse("request route natName cidr xlateType and xlateIP param")
		return
	}
	ip, prefix, err := comm.ParseCIDR(m.Cidr)
	if err != nil {
		addStr := fmt.Sprintf("AddNAT parse cidr failed route %s cider string %s", m.Route, m.Cidr)
		logger.Infof(addStr)
		b.BadResponse(addStr)
		return
	}
	// if xlateType neither snat or dnat return failed
	if m.XlateType != "snat" && m.XlateType != "dnat" {
		addStr := fmt.Sprintf("AddNAT invalid translate type, must be snat/dnat: %s", m.XlateType)
		logger.Infof(addStr)
		b.BadResponse(addStr)
		return
	}

	if net.ParseIP(m.XlateIP) == nil {
		addStr := fmt.Sprintf("AddNAT invalid translate IP: %s", m.XlateIP)
		logger.Infof(addStr)
		b.BadResponse(addStr)
		return
	}

	router, err := controller.GetRouter(m.Route)
	if err != nil {
		addStr := fmt.Sprintf("AddNAT get route failed %s", err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	_, err = controller.GetRouterNAT(router, m.NatName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		addStr := fmt.Sprintf("AddNAT get route failed %s", err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	if err == nil {
		addStr := fmt.Sprintf("AddNAT route %s nat %s exists", m.Route, m.NatName)
		logger.Infof(addStr)
		b.NormalResponse(addStr)
		return
	}

	nat := router.CreateNAT(m.NatName, ip, prefix, m.XlateType, m.XlateIP)
	err = controller.Save(nat)
	if err != nil {
		addStr := fmt.Sprintf("AddNAT create nat failed %s", err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	logger.Infof("AddNAT success route %s natName %s cidr %s xlateType %s xlateIP %s", m.Route, m.NatName, m.Cidr, m.XlateType, m.XlateIP)
	b.NormalResponse("AddNAT success")
}

func (b *TuplenetAPI) DelNAT() {
	var (
		m   NetRequest
		err error
	)

	err = json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		logger.Infof("DelNAT decode body failed %s", err)
		b.BadResponse("DelNAT decode body failed please check param")
		return
	}
	logger.Infof("DelNAT get param route %s natName %s", m.Route, m.NatName)

	if m.Route == "" || m.NatName == "" {
		logger.Infof("DelNAT get param failed route %s natName %s", m.Route, m.NatName)
		b.BadResponse("request route and natName param")
		return
	}
	router, err := controller.GetRouter(m.Route)
	if err != nil {
		delStr := fmt.Sprintf("DelNAT get route failed %s", err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	port, err := controller.GetRouterNAT(router, m.NatName)
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

	logger.Infof("DelNAT router %s NAT %s deleted", m.Route, m.NatName)
	b.NormalResponse("DelNAT success")
}

func (b *TuplenetAPI) ShowNAT() {
	var (
		err  error
		nats []*logicaldev.NAT
	)

	route := b.GetString("route")
	natName := b.GetString("natName")
	logger.Infof("ShowNAT get param route %s natName %s", route, natName)

	if route == "" {
		logger.Infof("ShowNAT get param failed route %s ", route)
		b.BadResponse("request route param")
		return
	}
	router, err := controller.GetRouter(route)
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

	logger.Infof("ShowNAT success route %s natName %s", router, natName)
	sort.Slice(nats, func(i, j int) bool { return nats[i].Name < nats[j].Name })
	b.NormalResponse(nats)
}
