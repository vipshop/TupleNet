package api

import (
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

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	chassis := m.Chassis
	logger.Debugf("AddRoute get param route %s chassis %s", name, chassis)

	if name == "" {
		logger.Errorf("AddRoute get param failed route %s chassis %s", name, chassis)
		b.BadResponse("request route param")
		return
	}

	r := logicaldev.NewRouter(name, chassis)
	if err = controller.Save(r); err != nil {
		addStr := fmt.Sprintf("AddRoute %s create route failed %s ", name, err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	logger.Infof("AddRoute %s created", name)
	b.NormalResponse("add route success")
}

// link a logical router to a logical switch (lr link)
func (b *TuplenetAPI) LinkSwitch() {
	var (
		m RouteRequest
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	routerName := m.Route
	switchName := m.Switch
	cidrString := m.Cidr
	logger.Debugf("LinkSwitch get param route %s switch %s cider string %s", routerName, switchName, cidrString)

	if routerName == "" || switchName == "" || cidrString == "" {
		logger.Errorf("LinkSwitch get param failed route %s switch %s cider string %s", routerName, switchName, cidrString)
		b.BadResponse("request route, switch, cidr param")
		return
	}

	ip, prefix, err := comm.ParseCIDR(cidrString)
	if err != nil {
		linkStr := fmt.Sprintf("LinkSwitch parse cidr failed route %s switch %s cider string %s", routerName, switchName, cidrString)
		logger.Errorf(linkStr)
		b.InternalServerErrorResponse(linkStr)
		return
	}
	mac := comm.MacFromIP(ip)

	router, err := controller.GetRouter(routerName)
	if err != nil {
		linkStr := fmt.Sprintf("LinkSwitch get route failed  %s route name %s switch name %s cider string %s", err, routerName, switchName, cidrString)
		logger.Errorf(linkStr)
		b.InternalServerErrorResponse(linkStr)
		return
	}

	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		linkStr := fmt.Sprintf("LinkSwitch get switch failed  %s route name %s switch name %s cider string %s", err, routerName, switchName, cidrString)
		logger.Errorf(linkStr)
		b.InternalServerErrorResponse(linkStr)
		return
	}

	spName := switchName + "_to_" + routerName
	if _, err = controller.GetSwitchPort(swtch, spName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		linkStr := fmt.Sprintf("LinkSwitch get switch port failed  %s route name %s switch name %s cider string %s", err, routerName, switchName, cidrString)
		logger.Errorf(linkStr)
		b.InternalServerErrorResponse(linkStr)
		return
	}

	rpName := routerName + "_to_" + switchName
	if _, err = controller.GetRouterPort(router, rpName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		linkStr := fmt.Sprintf("LinkSwitch get route port failed  %s route name %s switch name %s cider string %s", err, routerName, switchName, cidrString)
		logger.Errorf(linkStr)
		b.InternalServerErrorResponse(linkStr)
		return
	}

	sp := swtch.CreatePort(spName, ip, mac)
	rp := router.CreatePort(rpName, ip, prefix, mac)
	rp.Link(sp)

	if err = controller.Save(sp, rp); err != nil {
		linkStr := fmt.Sprintf("LinkSwitch failed %s route name %s switch name %s cider string %s", err, routerName, switchName, cidrString)
		logger.Errorf(linkStr)
		b.InternalServerErrorResponse(linkStr)
		return
	}

	logger.Infof("LinkSwitch link success route name %s switch name %s cider string %s", routerName, switchName, cidrString)
	b.NormalResponse("link switch success")
}

func (b *TuplenetAPI) ShowRouter() {
	var (
		m       RouteRequest
		err     error
		routers []*logicaldev.Router
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	all := m.All
	logger.Debugf("ShowRouter get param all %v route %s", all, name)

	if name == "" && all == false {
		logger.Errorf("ShowRouter get param failed all %v route %s", all, name)
		b.BadResponse("request route or all param")
		return
	}

	if all {
		// show all ports
		routers, err = controller.GetRouters()
		if err != nil {
			showStr := fmt.Sprintf("get routes failed %s", err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}
	} else {
		router, err := controller.GetRouter(name)
		if err != nil {
			showStr := fmt.Sprintf("get routes failed %s", err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}

		routers = []*logicaldev.Router{router}
	}

	sort.Slice(routers, func(i, j int) bool { return routers[i].Name < routers[j].Name })
	logger.Debugf("ShowRouter success all %v route name %s", all, name)
	b.NormalResponse(routers)
}

func (b *TuplenetAPI) DelRouter() {
	var (
		m RouteRequest
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	recursive := m.Recursive
	logger.Debugf("DelRouter get param name %s recursive %v", name, recursive)

	if name == "" {
		logger.Errorf("DelRouter get param failed route is null")
		b.BadResponse("request route param")
		return
	}
	router, err := controller.GetRouter(name)
	if err != nil {
		delStr := fmt.Sprintf("DelRouter get route failed %s", err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	ports, err := controller.GetRouterPorts(router)
	if err != nil {
		delStr := fmt.Sprintf("DelRouter get route port failed %s", err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	srs, err := controller.GetRouterStaticRoutes(router)
	if err != nil {
		delStr := fmt.Sprintf("DelRouter get static route failed %s", err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	if len(ports) != 0 || len(srs) != 0 { // for router with ports and static routes, it depends
		if recursive {
			err := controller.Delete(true, router)
			if err != nil {
				delStr := fmt.Sprintf("DelRouter use recursive failed route %s %v", name, err)
				logger.Errorf(delStr)
				b.InternalServerErrorResponse(delStr)
				return
			}
		} else {
			delStr := fmt.Sprintf("DelRouter failed route %s there are remaining ports or static routes, consider recursive?", name)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}
	} else {
		err := controller.Delete(false, router)
		if err != nil {
			delStr := fmt.Sprintf("DelRouter failed route %s %v", name, err)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}
	}

	logger.Infof("DelRouter success route %s recursive %v", name, recursive)
	b.NormalResponse("DelRouter success")
}

func (b *TuplenetAPI) ShowRouterPort() {
	var (
		m     RouteRequest
		ports []*logicaldev.RouterPort
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	portName := m.PortName
	logger.Debugf("ShowRouterPort get param name %s portName %s", name, portName)

	if name == "" {
		logger.Errorf("ShowRouterPort get param failed route %s portName %s", name, portName)
		b.BadResponse("request route param")
		return
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		showStr := fmt.Sprintf("ShowRouterPort get route failed %s route %s portName %s", err, name, portName)
		logger.Errorf(showStr)
		b.InternalServerErrorResponse(showStr)
		return
	}

	if portName == "" {
		// show all ports
		ports, err = controller.GetRouterPorts(router)
		if err != nil {
			showStr := fmt.Sprintf("ShowRouterPort get route port failed %s route %s portName %s", err, name, portName)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}
	} else {
		port, err := controller.GetRouterPort(router, portName)
		if err != nil {
			showStr := fmt.Sprintf("ShowRouterPort get route port failed %s route %s portName %s", err, name, portName)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}
		ports = []*logicaldev.RouterPort{port}
	}

	sort.Slice(ports, func(i, j int) bool { return ports[i].Name < ports[j].Name })
	logger.Debugf("ShowRouterPort success router %s portName %s", name, portName)
	b.NormalResponse(ports)
}

func (b *TuplenetAPI) AddRouterPort() {
	var (
		m RouteRequest
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	portName := m.PortName
	cidr := m.Cidr
	mac := m.Mac
	peer := m.Peer
	logger.Debugf("AddRouterPort get param route %s portName %s cidr %s mac %s peer %s", name, portName, cidr, mac, peer)

	if name == "" || cidr == "" || portName == "" || peer == "" {
		logger.Errorf("AddRouterPort get param failed route %s cidr %s portName %s peer %s ", name, cidr, portName, peer)
		b.BadResponse("request route and cidr and portName and peer param")
		return
	}
	ip, prefix, err := comm.ParseCIDR(cidr)
	if err != nil {
		addStr := fmt.Sprintf("AddRouterPort parse cidr failed route %s cider string %s", name, cidr)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}
	if mac == "" {
		mac = comm.MacFromIP(ip)
	} else {
		err := comm.ValidateMAC(mac)
		if err != nil {
			addStr := fmt.Sprintf("AddRouterPort mac invalid route %s mac %s", name, mac)
			logger.Errorf(addStr)
			b.InternalServerErrorResponse(addStr)
			return
		}
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		addStr := fmt.Sprintf("AddRouterPort get route %s failed %s", name, err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	_, err = controller.GetRouterPort(router, portName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		addStr := fmt.Sprintf("AddRouterPort get route %s port %s failed %s", name, portName, err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	port := router.CreatePort(portName, ip, prefix, mac)
	port.PeerSwitchPortName = peer

	err = controller.Save(port)
	if err != nil {
		addStr := fmt.Sprintf("AddRouterPort save route %s port %s ip %s prefix %d mac %s failed %s", name, portName, ip, prefix, mac, err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	logger.Infof("AddRouterPort success route %s port %s ip %s prefix %d mac %s", name, portName, ip, prefix, mac)
	b.NormalResponse("AddRouterPort success")
}

func (b *TuplenetAPI) DelRouterPort() {
	var (
		m RouteRequest
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	portName := m.PortName
	logger.Debugf("DelRouterPort get param route %s portName %s ", name, portName)

	if name == "" || portName == "" {
		logger.Errorf("DelRouterPort get param failed route %s portName %s", name, portName)
		b.BadResponse("request route and portName param")
		return
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		delStr := fmt.Sprintf("DelRouterPort get route %s failed %s", name, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	port, err := controller.GetRouterPort(router, portName)
	if err != nil {
		delStr := fmt.Sprintf("DelRouterPort get route %s portName %s failed %s", name, portName, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	err = controller.Delete(false, port)
	if err != nil {
		delStr := fmt.Sprintf("DelRouterPort delete route %s portName %s failed %s", name, portName, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	logger.Infof("DelRouterPort success router %s portName %s ", name, portName)
	b.NormalResponse("DelRouterPort success")
}
