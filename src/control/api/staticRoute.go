package api

import (
	"net"
	"sort"
	"encoding/json"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/comm"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
	"github.com/vipshop/tuplenet/control/logger"
	"net/http"
)

// operate on logical static route(lsr)
func (b *TuplenetAPI) AddStaticRoute() {
	var (
		m RouteStaticRequest
	)

	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "AddStaticRoute decode get param body failed %s", err)
		return
	}
	routerName := m.Route
	rName := m.RName
	cidrString := m.Cidr
	nextHop := m.NextHop
	outPort := m.OutPort
	logger.Infof("AddStaticRoute get param route %s rName %s cider %s nexthop %s outport %s", routerName, rName, cidrString, nextHop, outPort)

	if CheckNilParam(routerName, rName, cidrString, nextHop, outPort) {
		b.Response(http.StatusBadRequest, "AddStaticRoute get param failed route %s rName %s cider %s nexthop %s outport %s", nil, routerName, rName, cidrString, nextHop, outPort)
		return
	}

	// perform some early checking, avoid reading db if any error
	ip, prefix, err := comm.ParseCIDR(cidrString)
	if err != nil {
		b.Response(http.StatusBadRequest, "AddStaticRoute invalid cidr route %s cider %s failed %s", err, routerName, cidrString)
		return
	}

	if net.ParseIP(nextHop) == nil {
		b.Response(http.StatusBadRequest, "AddStaticRoute invalid nexthop  route %s nexthop %s ", nil, routerName, nextHop)
		return
	}

	router, err := controller.GetRouter(routerName)
	if err != nil {
		b.Response(http.StatusInternalServerError, "AddStaticRoute get router route %s failed %s", err, routerName)
		return
	}

	if _, err = controller.GetRouterStaticRoute(router, rName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		b.Response(http.StatusInternalServerError, "AddStaticRoute route %s rName %s get static route failed %s", err, routerName, rName)
		return
	}

	r := router.CreateStaticRoute(rName, ip, prefix, nextHop, outPort)
	if err = controller.Save(r); err != nil {
		b.Response(http.StatusInternalServerError, "AddStaticRoute route %s rName %s cider %s nexthop %s outport %s failed %s ", err, routerName, rName, cidrString, nextHop, outPort)
		return
	}

	b.Response(http.StatusOK, "AddStaticRoute success route %s rName %s cider %s nexthop %s outport %s", nil, routerName, rName, cidrString, nextHop, outPort)
}

func (b *TuplenetAPI) ShowStaticRoute() {
	var (
		srs []*logicaldev.StaticRoute
	)
	name := b.GetString("route")
	rName := b.GetString("rName")
	logger.Infof("ShowStaticRoute get param route name %s rName %s", name, rName)

	if CheckNilParam(name) {
		b.Response(http.StatusBadRequest, "ShowStaticRoute get param failed route name %s rName %s", nil, name, rName)
		return
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		b.Response(http.StatusInternalServerError, "ShowStaticRoute get route name %s rName %s route failed %s", err, name, rName)
		return
	}

	if CheckNilParam(rName) {
		// show all ports
		srs, err = controller.GetRouterStaticRoutes(router)
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowStaticRoute get all route name %s static route failed %s", err, name)
			return
		}
	} else {
		r, err := controller.GetRouterStaticRoute(router, rName)
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowStaticRoute get route name %s rName %s static route failed %s", err, name, rName)
			return
		}

		srs = []*logicaldev.StaticRoute{r}
	}

	sort.Slice(srs, func(i, j int) bool { return srs[i].Name < srs[j].Name })
	logger.Infof("ShowStaticRoute success route %s rName %s ", name, rName)
	b.NormalResponse(srs)
}

func (b *TuplenetAPI) DelStaticRoute() {
	var (
		m RouteStaticRequest
	)

	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "DelStaticRoute decode get param body failed %s", err)
		return
	}
	name := m.Route
	rName := m.RName
	logger.Infof("DelStaticRoute get param route %s rName %s", name, rName)

	if CheckNilParam(name, rName) {
		b.Response(http.StatusBadRequest, "DelStaticRoute get param failed route %s rName %s", nil, name, rName)
		return
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelStaticRoute get route failed route %s rName %s error %s", err, name, rName)
		return
	}

	r, err := controller.GetRouterStaticRoute(router, rName)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelStaticRoute get static route failed route %s rName %s error %s", err, name, rName)
		return
	}

	err = controller.Delete(false, r)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelStaticRoute delete failed route %s rName %s error %s", err, name, rName)
		return
	}

	b.Response(http.StatusOK, "DelStaticRoute success route %s rName %s", nil, name, rName)
}
