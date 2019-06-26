package api

import (
	"net"
	"fmt"
	"sort"
	"encoding/json"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/comm"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
	"github.com/vipshop/tuplenet/control/logger"
)

// operate on logical static route(lsr)
func (b *TuplenetAPI) AddStaticRoute() {
	var (
		m RouteStaticRequest
	)

	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		logger.Infof("AddStaticRoute decode body failed %s", err)
		b.BadResponse("AddStaticRoute decode body failed please check param")
		return
	}
	routerName := m.Route
	rName := m.RName
	cidrString := m.Cidr
	nextHop := m.NextHop
	outPort := m.OutPort
	logger.Infof("AddStaticRoute get param route %s rName %s cider %s nexthop %s outport %s", routerName, rName, cidrString, nextHop, outPort)

	if routerName == "" || rName == "" || cidrString == "" || nextHop == "" || outPort == "" {
		logger.Infof("AddStaticRoute get param failed route %s rName %s cider %s nexthop %s outport %s", routerName, rName, cidrString, nextHop, outPort)
		b.BadResponse("request route rName cidr nextHop and outPort param")
		return
	}

	// perform some early checking, avoid reading db if any error
	ip, prefix, err := comm.ParseCIDR(cidrString)
	if err != nil {
		addStr := fmt.Sprintf("AddStaticRoute parse cidr failed route %s cider %s", routerName, cidrString)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	if net.ParseIP(nextHop) == nil {
		logger.Errorf("AddStaticRoute parse next hop ip failed route %s nexthop %s ", routerName, nextHop)
		b.InternalServerErrorResponse("parse nexthop ip failed")
		return
	}

	router, err := controller.GetRouter(routerName)
	if err != nil {
		logger.Errorf("AddStaticRoute get router failed %s route %s", err, routerName)
		b.InternalServerErrorResponse("get router failed")
		return
	}

	if _, err = controller.GetRouterStaticRoute(router, rName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		logger.Errorf("AddStaticRoute get static route failed %s route %s rName %s ", err, routerName, rName)
		b.InternalServerErrorResponse("get static route failed")
		return
	}

	r := router.CreateStaticRoute(rName, ip, prefix, nextHop, outPort)
	if err = controller.Save(r); err != nil {
		addStr := fmt.Sprintf("AddStaticRoute failed %s route %s rName %s cider %s nexthop %s outport %s", err, routerName, rName, cidrString, nextHop, outPort)
		b.InternalServerErrorResponse(addStr)
		return
	}

	logger.Infof("AddStaticRoute success route %s rName %s cider %s nexthop %s outport %s", routerName, rName, cidrString, nextHop, outPort)
	b.NormalResponse("add static route success")
}

func (b *TuplenetAPI) ShowStaticRoute() {
	var (
		srs []*logicaldev.StaticRoute
	)
	name := b.GetString("route")
	rName := b.GetString("rName")
	logger.Infof("ShowStaticRoute get param route name %s rName %s", name, rName)

	if name == "" {
		logger.Infof("ShowStaticRoute get param failed route name %s rName %s", name, rName)
		b.BadResponse("request route param")
		return
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		showStr := fmt.Sprintf("get route failed route name %s rName %s err %s", name, rName, err)
		logger.Errorf(showStr)
		b.InternalServerErrorResponse(showStr)
		return
	}

	if rName == "" {
		// show all ports
		srs, err = controller.GetRouterStaticRoutes(router)
		if err != nil {
			showStr := fmt.Sprintf("get static route failed route name %s rName %s err %s", name, rName, err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}
	} else {
		r, err := controller.GetRouterStaticRoute(router, rName)
		if err != nil {
			showStr := fmt.Sprintf("get static route failed route name %s rName %s err %s", name, rName, err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
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
		logger.Infof("DelStaticRoute decode body failed %s", err)
		b.BadResponse("DelStaticRoute decode body failed please check param")
		return
	}
	name := m.Route
	rName := m.RName
	logger.Infof("DelStaticRoute get param route %s rName %s", name, rName)

	if name == "" || rName == "" {
		logger.Infof("DelStaticRoute get param failed route %s rName %s", name, rName)
		b.BadResponse("request route and rName param")
		return
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		delStr := fmt.Sprintf("DelStaticRoute get route failed route %s rName %s error %s", name, rName, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	r, err := controller.GetRouterStaticRoute(router, rName)
	if err != nil {
		delStr := fmt.Sprintf("DelStaticRoute get static route failed route %s rName %s error %s", name, rName, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	err = controller.Delete(false, r)
	if err != nil {
		delStr := fmt.Sprintf("DelStaticRoute delete failed route %s rName %s error %s", name, rName, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	logger.Infof("DelStaticRoute delete success route %s rName %s", name, rName)
	b.NormalResponse("DelStaticRoute success")
}
