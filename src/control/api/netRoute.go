package api

import (
	"net"
	"sort"
	"encoding/json"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/comm"
	"github.com/vipshop/tuplenet/control/logger"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
	"net/http"
)

func (b *TuplenetAPI) AddNAT() {
	var (
		m   NetRequest
		err error
	)

	err = json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "AddNAT decode get param body failed %s", err)
		return
	}
	logger.Infof("AddNAT get param route %s natName %s cidr %s xlateType %s xlateIP %s", m.Route, m.NatName, m.Cidr, m.XlateType, m.XlateIP)

	if CheckNilParam(m.Route, m.NatName, m.Cidr, m.XlateType, m.XlateIP) {
		b.Response(http.StatusBadRequest, "AddNAT get param failed route %s natName %s cidr %s xlateType %s xlateIP %s", nil, m.Route, m.NatName, m.Cidr, m.XlateType, m.XlateIP)
		return
	}
	ip, prefix, err := comm.ParseCIDR(m.Cidr)
	if err != nil {
		b.Response(http.StatusBadRequest, "AddNAT get invalid cidr route %s cider string %s", nil, m.Route, m.Cidr)
		return
	}
	// if xlateType neither snat or dnat return failed
	if m.XlateType != "snat" && m.XlateType != "dnat" {
		b.Response(http.StatusBadRequest, "AddNAT invalid xlateType, must be snat/dnat: %s", nil, m.XlateType)
		return
	}

	if net.ParseIP(m.XlateIP) == nil {
		b.Response(http.StatusBadRequest, "AddNAT invalid xlateIP: %s", nil, m.XlateIP)
		return
	}

	router, err := controller.GetRouter(m.Route)
	if err != nil {
		b.Response(http.StatusInternalServerError, "AddNAT get route failed %s", err)
		return
	}

	_, err = controller.GetRouterNAT(router, m.NatName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		b.Response(http.StatusInternalServerError, "AddNAT get route failed %s", err)
		return
	}

	if err == nil {
		b.Response(http.StatusOK, "AddNAT route %s nat %s exists", nil, m.Route, m.NatName)
		return
	}

	nat := router.CreateNAT(m.NatName, ip, prefix, m.XlateType, m.XlateIP)
	err = controller.Save(nat)
	if err != nil {
		b.Response(http.StatusInternalServerError, "AddNAT create nat failed %s", err)
		return
	}

	b.Response(http.StatusOK, "AddNAT success route %s natName %s cidr %s xlateType %s xlateIP %s", nil, m.Route, m.NatName, m.Cidr, m.XlateType, m.XlateIP)
}

func (b *TuplenetAPI) DelNAT() {
	var (
		m   NetRequest
		err error
	)

	err = json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "DelNAT decode get param body failed %s", err)
		return
	}
	logger.Infof("DelNAT get param route %s natName %s", m.Route, m.NatName)

	if CheckNilParam(m.Route, m.NatName) {
		b.Response(http.StatusBadRequest, "DelNAT get param failed route %s natName %s", nil, m.Route, m.NatName)
		return
	}
	router, err := controller.GetRouter(m.Route)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelNAT get route failed %s", err)
		return
	}

	port, err := controller.GetRouterNAT(router, m.NatName)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelNAT get route nat failed %s", err)
		return
	}

	err = controller.Delete(false, port)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelNAT delete failed %s", err)
		return
	}
	b.Response(http.StatusOK, "DelNAT router %s NAT %s deleted", nil, m.Route, m.NatName)
}

func (b *TuplenetAPI) ShowNAT() {
	var (
		err  error
		nats []*logicaldev.NAT
	)

	route := b.GetString("route")
	natName := b.GetString("natName")
	logger.Infof("ShowNAT get param route %s natName %s", route, natName)

	if CheckNilParam(route) {
		b.Response(http.StatusBadRequest, "ShowNAT get param failed route %s ", nil, route)
		return
	}
	router, err := controller.GetRouter(route)
	if err != nil {
		b.Response(http.StatusInternalServerError, "ShowNAT get route failed %s", err)
		return
	}

	if CheckNilParam(natName) { // show all nats
		nats, err = controller.GetRouterNATs(router)
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowNAT get route nats failed %s", err)
			return
		}
	} else {
		nat, err := controller.GetRouterNAT(router, natName)
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowNAT get route nat failed %s", err)
			return
		}

		nats = []*logicaldev.NAT{nat}
	}

	logger.Infof("ShowNAT success route %s natName %s", router, natName)
	sort.Slice(nats, func(i, j int) bool { return nats[i].Name < nats[j].Name })
	b.NormalResponse(nats)
}
