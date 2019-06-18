package api

import (
	"fmt"
	"sort"
	"net/http"
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
		res Response
		err error
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	chassis := m.Chassis
	logger.Debugf("AddRoute get param route %s chassis %s", name, chassis)

	if name == "" {
		logger.Errorf("AddRoute get param failed route %s chassis %s", name, chassis)
		res.Code = http.StatusBadRequest
		res.Message = "request route param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	r := logicaldev.NewRouter(name, chassis)
	if err = controller.Save(r); err != nil {
		addStr := fmt.Sprintf("AddRoute %s create route failed %s ", name, err)
		logger.Errorf(addStr)
		res.Code = http.StatusInternalServerError
		res.Message = addStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	logger.Infof("AddRoute %s created", name)
	res.Code = http.StatusOK
	res.Message = "add route success"
	b.Data["json"] = res
	b.ServeJSON()
}

// link a logical router to a logical switch (lr link)
func (b *TuplenetAPI) LinkSwitch() {
	var (
		m   RouteRequest
		res Response
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	routerName := m.Route
	switchName := m.Switch
	cidrString := m.Cidr
	logger.Debugf("LinkSwitch get param route %s switch %s cider string %s", routerName, switchName, cidrString)

	if routerName == "" || switchName == "" || cidrString == "" {
		logger.Errorf("LinkSwitch get param failed route %s switch %s cider string %s", routerName, switchName, cidrString)
		res.Code = http.StatusBadRequest
		res.Message = "request route, switch, cidr param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	ip, prefix, err := comm.ParseCIDR(cidrString)
	if err != nil {
		linkStr := fmt.Sprintf("LinkSwitch parse cidr failed route %s switch %s cider string %s", routerName, switchName, cidrString)
		logger.Errorf(linkStr)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf(linkStr)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}
	mac := comm.MacFromIP(ip)

	router, err := controller.GetRouter(routerName)
	if err != nil {
		linkStr := fmt.Sprintf("LinkSwitch get route failed  %s route name %s switch name %s cider string %s", err, routerName, switchName, cidrString)
		logger.Errorf(linkStr)
		res.Code = http.StatusInternalServerError
		res.Message = linkStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		linkStr := fmt.Sprintf("LinkSwitch get switch failed  %s route name %s switch name %s cider string %s", err, routerName, switchName, cidrString)
		logger.Errorf(linkStr)
		res.Code = http.StatusInternalServerError
		res.Message = linkStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	spName := switchName + "_to_" + routerName
	if _, err = controller.GetSwitchPort(swtch, spName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		linkStr := fmt.Sprintf("LinkSwitch get switch port failed  %s route name %s switch name %s cider string %s", err, routerName, switchName, cidrString)
		logger.Errorf(linkStr)
		res.Code = http.StatusInternalServerError
		res.Message = linkStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	rpName := routerName + "_to_" + switchName
	if _, err = controller.GetRouterPort(router, rpName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		linkStr := fmt.Sprintf("LinkSwitch get route port failed  %s route name %s switch name %s cider string %s", err, routerName, switchName, cidrString)
		logger.Errorf(linkStr)
		res.Code = http.StatusInternalServerError
		res.Message = linkStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	sp := swtch.CreatePort(spName, ip, mac)
	rp := router.CreatePort(rpName, ip, prefix, mac)
	rp.Link(sp)

	if err = controller.Save(sp, rp); err != nil {
		linkStr := fmt.Sprintf("LinkSwitch failed %s route name %s switch name %s cider string %s", err, routerName, switchName, cidrString)
		logger.Errorf(linkStr)
		res.Code = http.StatusInternalServerError
		res.Message = linkStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	logger.Infof("LinkSwitch link success route name %s switch name %s cider string %s", routerName, switchName, cidrString)
	res.Code = http.StatusOK
	res.Message = "link switch success"
	b.Data["json"] = res
	b.ServeJSON()
}

func (b *TuplenetAPI) ShowRouter() {
	var (
		m       RouteRequest
		res     Response
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
		res.Code = http.StatusBadRequest
		res.Message = "request route or all param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if all {
		// show all ports
		routers, err = controller.GetRouters()
		if err != nil {
			showStr := fmt.Sprintf("get routes failed %s", err)
			logger.Errorf(showStr)
			res.Code = http.StatusInternalServerError
			res.Message = showStr
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
	} else {
		router, err := controller.GetRouter(name)
		if err != nil {
			showStr := fmt.Sprintf("get routes failed %s", err)
			logger.Errorf(showStr)
			res.Code = http.StatusInternalServerError
			res.Message = showStr
			b.Data["json"] = res
			b.ServeJSON()
			return
		}

		routers = []*logicaldev.Router{router}
	}

	sort.Slice(routers, func(i, j int) bool { return routers[i].Name < routers[j].Name })
	logger.Debugf("ShowRouter success all %v route name %s", all, name)
	res.Message = routers
	res.Code = http.StatusOK
	b.Data["json"] = res
	b.ServeJSON()
}

func (b *TuplenetAPI) DelRouter() {
	var (
		m   RouteRequest
		res Response
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	recursive := m.Recursive
	logger.Debugf("DelRouter get param name %s recursive %v", name, recursive)

	if name == "" {
		logger.Errorf("DelRouter get param failed route is null")
		res.Code = http.StatusBadRequest
		res.Message = "request route param "
		b.Data["json"] = res
		b.ServeJSON()
		return
	}
	router, err := controller.GetRouter(name)
	if err != nil {
		delStr := fmt.Sprintf("DelRouter get route failed %s", err)
		logger.Errorf(delStr)
		res.Code = http.StatusInternalServerError
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	ports, err := controller.GetRouterPorts(router)
	if err != nil {
		delStr := fmt.Sprintf("DelRouter get route port failed %s", err)
		logger.Errorf(delStr)
		res.Code = http.StatusInternalServerError
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	srs, err := controller.GetRouterStaticRoutes(router)
	if err != nil {
		delStr := fmt.Sprintf("DelRouter get static route failed %s", err)
		logger.Errorf(delStr)
		res.Code = http.StatusInternalServerError
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if len(ports) != 0 || len(srs) != 0 { // for router with ports and static routes, it depends
		if recursive {
			err := controller.Delete(true, router)
			if err != nil {
				delStr := fmt.Sprintf("DelRouter failed route %s %v", name, err)
				logger.Errorf(delStr)
				res.Code = http.StatusInternalServerError
				res.Message = delStr
				b.Data["json"] = res
				b.ServeJSON()
				return
			}
		} else {
			delStr := fmt.Sprintf("DelRouter failed route %s there are remaining ports or static routes, consider recursive?", name)
			logger.Errorf(delStr)
			res.Code = http.StatusInternalServerError
			res.Message = delStr
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
	} else {
		err := controller.Delete(false, router)
		if err != nil {
			delStr := fmt.Sprintf("DelRouter failed route %s %v", name, err)
			logger.Errorf(delStr)
			res.Code = http.StatusInternalServerError
			res.Message = delStr
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
	}

	logger.Infof("DelRouter success route %s recursive %v", name, recursive)
	res.Message = fmt.Sprintf("route %s deleted", name)
	res.Code = http.StatusOK
	b.Data["json"] = res
	b.ServeJSON()
}

func (b *TuplenetAPI) ShowRouterPort() {
	var (
		m     RouteRequest
		res   Response
		ports []*logicaldev.RouterPort
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	portName := m.PortName
	logger.Debugf("ShowRouterPort get param name %s portName %s", name, portName)

	if name == "" {
		logger.Errorf("ShowRouterPort get param failed route %s portName %s", name, portName)
		res.Code = http.StatusBadRequest
		res.Message = "request route param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		showStr := fmt.Sprintf("ShowRouterPort get route failed %s route %s portName %s", err, name, portName)
		logger.Errorf(showStr)
		res.Code = http.StatusInternalServerError
		res.Message = showStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if portName == "" {
		// show all ports
		ports, err = controller.GetRouterPorts(router)
		if err != nil {
			showStr := fmt.Sprintf("ShowRouterPort get route port failed %s route %s portName %s", err, name, portName)
			logger.Errorf(showStr)
			res.Code = http.StatusInternalServerError
			res.Message = showStr
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
	} else {
		port, err := controller.GetRouterPort(router, portName)
		if err != nil {
			showStr := fmt.Sprintf("ShowRouterPort get route port failed %s route %s portName %s", err, name, portName)
			logger.Errorf(showStr)
			res.Code = http.StatusInternalServerError
			res.Message = showStr
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
		ports = []*logicaldev.RouterPort{port}
	}

	sort.Slice(ports, func(i, j int) bool { return ports[i].Name < ports[j].Name })
	logger.Debugf("ShowRouterPort success router %s portName %s", name, portName)
	res.Code = http.StatusOK
	res.Message = ports
	b.Data["json"] = res
	b.ServeJSON()
	return
}

func (b *TuplenetAPI) AddRouterPort() {
	var (
		m   RouteRequest
		res Response
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
		res.Code = http.StatusBadRequest
		res.Message = "request route and cidr and portName and peer param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}
	ip, prefix, err := comm.ParseCIDR(cidr)
	if err != nil {
		delStr := fmt.Sprintf("AddRouterPort parse cidr failed route %s cider string %s", name, cidr)
		logger.Errorf(delStr)
		res.Code = http.StatusInternalServerError
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}
	if mac == "" {
		mac = comm.MacFromIP(ip)
	} else {
		err := comm.ValidateMAC(mac)
		if err != nil {
			delStr := fmt.Sprintf("AddRouterPort mac invalid route %s mac %s", name, mac)
			logger.Errorf(delStr)
			res.Code = http.StatusInternalServerError
			res.Message = delStr
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		delStr := fmt.Sprintf("AddRouterPort get route %s failed %s", name, err)
		logger.Errorf(delStr)
		res.Code = http.StatusInternalServerError
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	_, err = controller.GetRouterPort(router, portName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		delStr := fmt.Sprintf("AddRouterPort get route %s port %s failed %s", name, portName, err)
		logger.Errorf(delStr)
		res.Code = http.StatusInternalServerError
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	port := router.CreatePort(portName, ip, prefix, mac)
	port.PeerSwitchPortName = peer

	err = controller.Save(port)
	if err != nil {
		addStr := fmt.Sprintf("AddRouterPort save route %s port %s ip %s prefix %d mac %s failed %s", name, portName, ip, prefix, mac, err)
		logger.Errorf(addStr)
		res.Code = http.StatusInternalServerError
		res.Message = addStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	logger.Infof("AddRouterPort success route %s port %s ip %s prefix %d mac %s", name, portName, ip, prefix, mac)
	res.Code = http.StatusOK
	res.Message = "AddRouterPort success"
	b.Data["json"] = res
	b.ServeJSON()
}

func (b *TuplenetAPI) DelRouterPort() {
	var (
		m   RouteRequest
		res Response
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	portName := m.PortName
	logger.Debugf("DelRouterPort get param route %s portName %s ", name, portName)

	if name == "" || portName == "" {
		logger.Errorf("DelRouterPort get param failed route %s portName %s", name, portName)
		res.Code = http.StatusBadRequest
		res.Message = "request route and portName param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		delStr := fmt.Sprintf("DelRouterPort get route %s failed %s", name, err)
		logger.Errorf(delStr)
		res.Code = http.StatusInternalServerError
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	port, err := controller.GetRouterPort(router, portName)
	if err != nil {
		delStr := fmt.Sprintf("DelRouterPort get route %s portName %s failed %s", name, portName, err)
		logger.Errorf(delStr)
		res.Code = http.StatusInternalServerError
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	err = controller.Delete(false, port)
	if err != nil {
		delStr := fmt.Sprintf("DelRouterPort delete route %s portName %s failed %s", name, portName, err)
		logger.Errorf(delStr)
		res.Code = http.StatusInternalServerError
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	logger.Infof("DelRouterPort success router %s portName %s ", name, portName)
	res.Code = http.StatusOK
	res.Message = "DelRouterPort success"
	b.Data["json"] = res
	b.ServeJSON()
}
