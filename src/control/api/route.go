package api

import (
	"sort"
	"encoding/json"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/comm"
	"github.com/vipshop/tuplenet/control/logger"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
	"net/http"
)

// add a logical router (lr)
func (b *TuplenetAPI) AddRoute() {
	var (
		m   RouteRequest
		err error
	)

	err = json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "AddRoute decode get param body failed %s", err)
		return
	}
	logger.Infof("AddRoute get param route %s chassis %s", m.Route, m.Chassis)

	if CheckNilParam(m.Route) {
		b.Response(http.StatusBadRequest, "AddRoute get param failed route %s", nil, m.Route)
		return
	}

	r := logicaldev.NewRouter(m.Route, m.Chassis)
	if err = controller.Save(r); err != nil {
		b.Response(http.StatusInternalServerError, "AddRoute %s create route failed %s ", err, m.Route)
		return
	}
	b.Response(http.StatusOK, "AddRoute %s success", nil, m.Route)
}

// link a logical router to a logical switch (lr link)
func (b *TuplenetAPI) LinkSwitch() {
	var (
		m RouteRequest
	)

	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "LinkSwitch decode get param body failed %s", err)
		return
	}
	logger.Infof("LinkSwitch get param route %s switch %s cider %s", m.Route, m.Switch, m.Cidr)

	if CheckNilParam(m.Route, m.Switch, m.Cidr) {
		b.Response(http.StatusBadRequest, "LinkSwitch get param failed route %s switch %s cider %s", nil, m.Route, m.Switch, m.Cidr)
		return
	}

	ip, prefix, err := comm.ParseCIDR(m.Cidr)
	if err != nil {
		b.Response(http.StatusInternalServerError, "LinkSwitch parse cidr route %s switch %s cider %s failed %s", err, m.Route, m.Switch, m.Cidr)
		return
	}
	mac := comm.MacFromIP(ip)

	router, err := controller.GetRouter(m.Route)
	if err != nil {
		b.Response(http.StatusInternalServerError, "LinkSwitch route name %s switch name %s cider %s get route failed  %s", err, m.Route, m.Switch, m.Cidr)
		return
	}

	swtch, err := controller.GetSwitch(m.Switch)
	if err != nil {
		b.Response(http.StatusInternalServerError, "LinkSwitch route name %s switch name %s cider %s get switch failed %s", err, m.Route, m.Switch, m.Cidr)
		return
	}

	spName := m.Switch + "_to_" + m.Route
	if _, err = controller.GetSwitchPort(swtch, spName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		b.Response(http.StatusInternalServerError, "LinkSwitch route name %s switch name %s cider string %s get switch port failed %s", err, m.Route, m.Switch, m.Cidr)
		return
	}

	rpName := m.Route + "_to_" + m.Switch
	if _, err = controller.GetRouterPort(router, rpName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		b.Response(http.StatusInternalServerError, "LinkSwitch route name %s switch name %s cider string %s get route port failed %s", err, m.Route, m.Switch, m.Cidr)
		return
	}

	sp := swtch.CreatePort(spName, ip, mac)
	rp := router.CreatePort(rpName, ip, prefix, mac)
	rp.Link(sp)

	if err = controller.Save(sp, rp); err != nil {
		b.Response(http.StatusInternalServerError, "LinkSwitch route name %s switch name %s cider string %s failed %s", err, m.Route, m.Switch, m.Cidr)
		return
	}

	b.Response(http.StatusOK, "LinkSwitch link success route name %s switch name %s cider string %s", nil, m.Route, m.Switch, m.Cidr)
}

func (b *TuplenetAPI) ShowRouter() {
	var (
		err     error
		routers []*logicaldev.Router
	)

	route := b.GetString("route")
	logger.Infof("ShowRouter get param route %s", route)

	if CheckNilParam(route) {
		// show all ports
		routers, err = controller.GetRouters()
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowRouter get all routes failed %s", err)
			return
		}
	} else {
		router, err := controller.GetRouter(route)
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowRouter get routes %s failed %s", err, route)
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
		b.Response(http.StatusBadRequest, "DelRouter decode get param body failed %s", err)
		return
	}
	logger.Infof("DelRouter get param name %s recursive %v", m.Route, m.Recursive)

	if CheckNilParam(m.Route) {
		b.Response(http.StatusBadRequest, "DelRouter get param failed route is null", nil)
		return
	}
	router, err := controller.GetRouter(m.Route)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelRouter get %s route failed %s", err, m.Route)
		return
	}

	ports, err := controller.GetRouterPorts(router)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelRouter get %s route port failed %s", err, m.Route)
		return
	}

	srs, err := controller.GetRouterStaticRoutes(router)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelRouter get %s static route failed %s", err, m.Route)
		return
	}

	if len(ports) != 0 || len(srs) != 0 { // for router with ports and static routes, it depends
		if m.Recursive {
			err := controller.Delete(true, router)
			if err != nil {
				b.Response(http.StatusInternalServerError, "DelRouter use recursive delete route %s failed %s", err, m.Route)
				return
			}
		} else {
			b.Response(http.StatusInternalServerError, "DelRouter failed route %s there are remaining ports or static routes, consider recursive?", nil, m.Route)
			return
		}
	} else {
		err := controller.Delete(false, router)
		if err != nil {
			b.Response(http.StatusInternalServerError, "DelRouter failed route %s %s", err, m.Route)
			return
		}
	}

	b.Response(http.StatusOK, "DelRouter success route %s recursive %v", nil, m.Route, m.Recursive)
}

func (b *TuplenetAPI) ShowRouterPort() {
	var (
		ports []*logicaldev.RouterPort
	)

	route := b.GetString("route")
	portName := b.GetString("portName")
	logger.Infof("ShowRouterPort get param name %s portName %s", route, portName)

	if CheckNilParam(route) {
		b.Response(http.StatusBadRequest, "ShowRouterPort get param failed route %s", nil, route)
		return
	}

	router, err := controller.GetRouter(route)
	if err != nil {
		b.Response(http.StatusInternalServerError, "ShowRouterPort route %s portName %s get route failed %s", err, route, portName)
		return
	}

	if CheckNilParam(portName) {
		// show all ports
		ports, err = controller.GetRouterPorts(router)
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowRouterPort get all route port route %s failed %s", err, route)
			return
		}
	} else {
		port, err := controller.GetRouterPort(router, portName)
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowRouterPort get route port route %s portName %s failed %s ", err, route, portName)
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
		b.Response(http.StatusBadRequest, "AddRouterPort decode get param body failed %s", err)
		return
	}
	logger.Infof("AddRouterPort get param route %s portName %s cidr %s mac %s peer %s", m.Route, m.PortName, m.Cidr, m.Mac, m.Peer)

	if CheckNilParam(m.Route, m.Cidr, m.PortName, m.Peer) {
		b.Response(http.StatusBadRequest, "AddRouterPort get param failed route %s cidr %s portName %s peer %s ", nil, m.Route, m.Cidr, m.PortName, m.Peer)
		return
	}
	ip, prefix, err := comm.ParseCIDR(m.Cidr)
	if err != nil {
		b.Response(http.StatusBadRequest, "AddRouterPort get invalid cidr route %s cider %s", nil, m.Route, m.Cidr)
		return
	}
	mac := m.Mac
	if CheckNilParam(mac) {
		mac = comm.MacFromIP(ip)
	} else {
		err := comm.ValidateMAC(mac)
		if err != nil {
			b.Response(http.StatusBadRequest, "AddRouterPort get invalid mac route %s mac %s", nil, m.Route, mac)
			return
		}
	}

	router, err := controller.GetRouter(m.Route)
	if err != nil {
		b.Response(http.StatusInternalServerError, "AddRouterPort get route %s failed %s", err, m.Route)
		return
	}

	_, err = controller.GetRouterPort(router, m.PortName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		b.Response(http.StatusInternalServerError, "AddRouterPort get route %s port %s failed %s", err, m.Route, m.PortName)
		return
	}

	port := router.CreatePort(m.PortName, ip, prefix, mac)
	port.PeerSwitchPortName = m.Peer

	err = controller.Save(port)
	if err != nil {
		b.Response(http.StatusInternalServerError, "AddRouterPort save route %s port %s ip %s prefix %d mac %s failed %s", err, m.Route, m.PortName, ip, prefix, mac)
		return
	}

	b.Response(http.StatusOK, "AddRouterPort success route %s port %s ip %s prefix %d mac %s", nil, m.Route, m.PortName, ip, prefix, mac)
}

func (b *TuplenetAPI) DelRouterPort() {
	var (
		m RouteRequest
	)

	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "AddRouterPort decode get param body failed %s", err)
		return
	}
	logger.Infof("DelRouterPort get param route %s portName %s ", m.Route, m.PortName)

	if CheckNilParam(m.Route, m.PortName) {
		b.Response(http.StatusBadRequest, "DelRouterPort get param failed route %s portName %s", nil, m.Route, m.PortName)
		return
	}

	router, err := controller.GetRouter(m.Route)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelRouterPort get route %s failed %s", err, m.Route)
		return
	}

	port, err := controller.GetRouterPort(router, m.PortName)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelRouterPort get route %s portName %s failed %s", err, m.Route, m.PortName)
		return
	}

	err = controller.Delete(false, port)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelRouterPort delete route %s portName %s failed %s", err, m.Route, m.PortName)
		return
	}

	b.Response(http.StatusOK, "DelRouterPort success router %s portName %s ", nil, m.Route, m.PortName)
}
