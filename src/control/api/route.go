package api

import (
	"fmt"
	"sort"
	"encoding/json"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/comm"
	"github.com/vipshop/tuplenet/control/logger"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
)

type Route interface {
	AddRoute()
	LinkSwitch()
	ShowRouter()
	DelRouter()
	ShowRouterPort()
	AddRouterPort()
	DelRouterPort()
	AddStaticRoute()
	ShowStaticRoute()
	DelStaticRoute()
	AddNAT()
	DelNAT()
	ShowNAT()
}

// add a logical router (lr)
func (b *TuplenetAPI) AddRoute() {
	var (
		m   RouteRequest
		err error
	)

	err = json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		logger.Infof("AddRoute decode body failed %s", err)
		b.BadResponse("AddRoute decode body failed please check param")
		return
	}
	logger.Infof("AddRoute get param route %s chassis %s", m.Route, m.Chassis)

	if m.Route == "" {
		logger.Infof("AddRoute get param failed route %s", m.Route)
		b.BadResponse("request route param")
		return
	}

	r := logicaldev.NewRouter(m.Route, m.Chassis)
	if err = controller.Save(r); err != nil {
		addStr := fmt.Sprintf("AddRoute %s create route failed %s ", m.Route, err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	logger.Infof("AddRoute %s created", m.Route)
	b.NormalResponse("add route success")
}

// link a logical router to a logical switch (lr link)
func (b *TuplenetAPI) LinkSwitch() {
	var (
		m RouteRequest
	)

	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		logger.Infof("LinkSwitch decode body failed %s", err)
		b.BadResponse("LinkSwitch decode body failed please check param")
		return
	}
	logger.Infof("LinkSwitch get param route %s switch %s cider %s", m.Route, m.Switch, m.Cidr)

	if m.Route == "" || m.Switch == "" || m.Cidr == "" {
		logger.Infof("LinkSwitch get param failed route %s switch %s cider %s", m.Route, m.Switch, m.Cidr)
		b.BadResponse("request route switch and cidr param")
		return
	}

	ip, prefix, err := comm.ParseCIDR(m.Cidr)
	if err != nil {
		linkStr := fmt.Sprintf("LinkSwitch parse cidr failed route %s switch %s cider %s", m.Route, m.Switch, m.Cidr)
		logger.Errorf(linkStr)
		b.InternalServerErrorResponse(linkStr)
		return
	}
	mac := comm.MacFromIP(ip)

	router, err := controller.GetRouter(m.Route)
	if err != nil {
		linkStr := fmt.Sprintf("LinkSwitch get route failed  %s route name %s switch name %s cider %s", err, m.Route, m.Switch, m.Cidr)
		logger.Errorf(linkStr)
		b.InternalServerErrorResponse(linkStr)
		return
	}

	swtch, err := controller.GetSwitch(m.Switch)
	if err != nil {
		linkStr := fmt.Sprintf("LinkSwitch get switch failed  %s route name %s switch name %s cider %s", err, m.Route, m.Switch, m.Cidr)
		logger.Errorf(linkStr)
		b.InternalServerErrorResponse(linkStr)
		return
	}

	spName := m.Switch + "_to_" + m.Route
	if _, err = controller.GetSwitchPort(swtch, spName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		linkStr := fmt.Sprintf("LinkSwitch get switch port failed  %s route name %s switch name %s cider string %s", err, m.Route, m.Switch, m.Cidr)
		logger.Errorf(linkStr)
		b.InternalServerErrorResponse(linkStr)
		return
	}

	rpName := m.Route + "_to_" + m.Switch
	if _, err = controller.GetRouterPort(router, rpName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		linkStr := fmt.Sprintf("LinkSwitch get route port failed  %s route name %s switch name %s cider string %s", err, m.Route, m.Switch, m.Cidr)
		logger.Errorf(linkStr)
		b.InternalServerErrorResponse(linkStr)
		return
	}

	sp := swtch.CreatePort(spName, ip, mac)
	rp := router.CreatePort(rpName, ip, prefix, mac)
	rp.Link(sp)

	if err = controller.Save(sp, rp); err != nil {
		linkStr := fmt.Sprintf("LinkSwitch failed %s route name %s switch name %s cider string %s", err, m.Route, m.Switch, m.Cidr)
		logger.Errorf(linkStr)
		b.InternalServerErrorResponse(linkStr)
		return
	}

	logger.Infof("LinkSwitch link success route name %s switch name %s cider string %s", m.Route, m.Switch, m.Cidr)
	b.NormalResponse("link switch success")
}

func (b *TuplenetAPI) ShowRouter() {
	var (
		err     error
		routers []*logicaldev.Router
	)

	route := b.GetString("route")
	logger.Infof("ShowRouter get param route %s", route)

	if route == "" {
		// show all ports
		routers, err = controller.GetRouters()
		if err != nil {
			showStr := fmt.Sprintf("ShowRouter get all routes failed %s", err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}
	} else {
		router, err := controller.GetRouter(route)
		if err != nil {
			showStr := fmt.Sprintf("ShowRouter get routes %s failed %s", route, err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}

		routers = []*logicaldev.Router{router}
	}

	sort.Slice(routers, func(i, j int) bool { return routers[i].Name < routers[j].Name })
	logger.Infof("ShowRouter success route name %s", route)
	b.NormalResponse(routers)
}

func (b *TuplenetAPI) DelRouter() {
	var (
		m RouteRequest
	)

	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		logger.Infof("DelRouter decode body failed %s", err)
		b.BadResponse("DelRouter decode body failed please check param")
		return
	}
	logger.Infof("DelRouter get param name %s recursive %v", m.Route, m.Recursive)

	if m.Route == "" {
		logger.Infof("DelRouter get param failed route is null")
		b.BadResponse("request route param")
		return
	}
	router, err := controller.GetRouter(m.Route)
	if err != nil {
		delStr := fmt.Sprintf("DelRouter get %s route failed %s", m.Route, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	ports, err := controller.GetRouterPorts(router)
	if err != nil {
		delStr := fmt.Sprintf("DelRouter get %s route port failed %s", m.Route, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	srs, err := controller.GetRouterStaticRoutes(router)
	if err != nil {
		delStr := fmt.Sprintf("DelRouter get %s static route failed %s", m.Route, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	if len(ports) != 0 || len(srs) != 0 { // for router with ports and static routes, it depends
		if m.Recursive {
			err := controller.Delete(true, router)
			if err != nil {
				delStr := fmt.Sprintf("DelRouter use recursive failed route %s %v", m.Route, err)
				logger.Errorf(delStr)
				b.InternalServerErrorResponse(delStr)
				return
			}
		} else {
			delStr := fmt.Sprintf("DelRouter failed route %s there are remaining ports or static routes, consider recursive?", m.Route)
			logger.Warnf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}
	} else {
		err := controller.Delete(false, router)
		if err != nil {
			delStr := fmt.Sprintf("DelRouter failed route %s %v", m.Route, err)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}
	}

	logger.Infof("DelRouter success route %s recursive %v", m.Route, m.Recursive)
	b.NormalResponse("DelRouter success")
}

func (b *TuplenetAPI) ShowRouterPort() {
	var (
		ports []*logicaldev.RouterPort
	)

	route := b.GetString("route")
	portName := b.GetString("portName")
	logger.Infof("ShowRouterPort get param name %s portName %s", route, portName)

	if route == "" {
		logger.Infof("ShowRouterPort get param failed route %s ", route)
		b.BadResponse("request route param")
		return
	}

	router, err := controller.GetRouter(route)
	if err != nil {
		showStr := fmt.Sprintf("ShowRouterPort get route failed %s route %s portName %s", err, route, portName)
		logger.Errorf(showStr)
		b.InternalServerErrorResponse(showStr)
		return
	}

	if portName == "" {
		// show all ports
		ports, err = controller.GetRouterPorts(router)
		if err != nil {
			showStr := fmt.Sprintf("ShowRouterPort get all route port failed %s route %s ", err, route)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}
	} else {
		port, err := controller.GetRouterPort(router, portName)
		if err != nil {
			showStr := fmt.Sprintf("ShowRouterPort get route port failed %s route %s portName %s", err, route, portName)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}
		ports = []*logicaldev.RouterPort{port}
	}

	sort.Slice(ports, func(i, j int) bool { return ports[i].Name < ports[j].Name })
	logger.Infof("ShowRouterPort success router %s portName %s", route, portName)
	b.NormalResponse(ports)
}

func (b *TuplenetAPI) AddRouterPort() {
	var (
		m RouteRequest
	)
	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		logger.Infof("AddRouterPort decode body failed %s", err)
		b.BadResponse("AddRouterPort decode body failed please check param")
		return
	}
	logger.Infof("AddRouterPort get param route %s portName %s cidr %s mac %s peer %s", m.Route, m.PortName, m.Cidr, m.Mac, m.Peer)

	if m.Route == "" || m.Cidr == "" || m.PortName == "" || m.Peer == "" {
		logger.Infof("AddRouterPort get param failed route %s cidr %s portName %s peer %s ", m.Route, m.Cidr, m.PortName, m.Peer)
		b.BadResponse("request route and cidr and portName and peer param")
		return
	}
	ip, prefix, err := comm.ParseCIDR(m.Cidr)
	if err != nil {
		addStr := fmt.Sprintf("AddRouterPort invalid cidr route %s cider %s", m.Route, m.Cidr)
		logger.Infof(addStr)
		b.BadResponse(addStr)
		return
	}
	mac := m.Mac
	if mac == "" {
		mac = comm.MacFromIP(ip)
	} else {
		err := comm.ValidateMAC(mac)
		if err != nil {
			addStr := fmt.Sprintf("AddRouterPort mac invalid route %s mac %s", m.Route, mac)
			logger.Infof(addStr)
			b.BadResponse(addStr)
			return
		}
	}

	router, err := controller.GetRouter(m.Route)
	if err != nil {
		addStr := fmt.Sprintf("AddRouterPort get route %s failed %s", m.Route, err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	_, err = controller.GetRouterPort(router, m.PortName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		addStr := fmt.Sprintf("AddRouterPort get route %s port %s failed %s", m.Route, m.PortName, err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	port := router.CreatePort(m.PortName, ip, prefix, mac)
	port.PeerSwitchPortName = m.Peer

	err = controller.Save(port)
	if err != nil {
		addStr := fmt.Sprintf("AddRouterPort save route %s port %s ip %s prefix %d mac %s failed %s", m.Route, m.PortName, ip, prefix, mac, err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	logger.Infof("AddRouterPort success route %s port %s ip %s prefix %d mac %s", m.Route, m.PortName, ip, prefix, mac)
	b.NormalResponse("AddRouterPort success")
}

func (b *TuplenetAPI) DelRouterPort() {
	var (
		m RouteRequest
	)

	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		logger.Infof("AddRouterPort decode body failed %s", err)
		b.BadResponse("AddRouterPort decode body failed please check param")
		return
	}
	logger.Infof("DelRouterPort get param route %s portName %s ", m.Route, m.PortName)

	if m.Route == "" || m.PortName == "" {
		logger.Infof("DelRouterPort get param failed route %s portName %s", m.Route, m.PortName)
		b.BadResponse("request route and portName param")
		return
	}

	router, err := controller.GetRouter(m.Route)
	if err != nil {
		delStr := fmt.Sprintf("DelRouterPort get route %s failed %s", m.Route, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	port, err := controller.GetRouterPort(router, m.PortName)
	if err != nil {
		delStr := fmt.Sprintf("DelRouterPort get route %s portName %s failed %s", m.Route, m.PortName, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	err = controller.Delete(false, port)
	if err != nil {
		delStr := fmt.Sprintf("DelRouterPort delete route %s portName %s failed %s", m.Route, m.PortName, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	logger.Infof("DelRouterPort success router %s portName %s ", m.Route, m.PortName)
	b.NormalResponse("DelRouterPort success")
}
