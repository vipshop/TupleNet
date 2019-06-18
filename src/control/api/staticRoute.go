package api

import (
	"net"
	"fmt"
	"sort"
	"net/http"
	"io/ioutil"
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
		res Response
		m   RouteStaticRequest
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	routerName := m.Route
	rName := m.RName
	cidrString := m.Cidr
	nextHop := m.NextHop
	outPort := m.OutPort
	logger.Debugf("AddStaticRoute get param route %s rName %s cider %s nexthop %s outport %s", routerName, rName, cidrString, nextHop, outPort)

	if routerName == "" || rName == "" || cidrString == "" || nextHop == "" || outPort == "" {
		logger.Errorf("AddStaticRoute get param failed route %s rName %s cider %s nexthop %s outport %s", routerName, rName, cidrString, nextHop, outPort)
		res.Code = http.StatusBadRequest
		res.Message = "request route rName cidr nextHop and outPort param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	// perform some early checking, avoid reading db if any error
	ip, prefix, err := comm.ParseCIDR(cidrString)
	if err != nil {
		addStr := fmt.Sprintf("AddStaticRoute parse cidr failed route %s cider %s", routerName, cidrString)
		logger.Errorf(addStr)
		res.Code = http.StatusInternalServerError
		res.Message = addStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if net.ParseIP(nextHop) == nil {
		logger.Errorf("AddStaticRoute parse next hop ip failed route %s nexthop %s ", routerName, nextHop)
		res.Code = http.StatusInternalServerError
		res.Message = "parse nexthop ip failed"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	router, err := controller.GetRouter(routerName)
	if err != nil {
		logger.Errorf("AddStaticRoute get router failed %s route %s", err, routerName)
		res.Code = http.StatusInternalServerError
		res.Message = "get router failed"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if _, err = controller.GetRouterStaticRoute(router, rName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		logger.Errorf("AddStaticRoute get static route failed %s route %s rName %s ", err, routerName, rName)
		res.Code = http.StatusInternalServerError
		res.Message = "get static route failed"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	r := router.CreateStaticRoute(rName, ip, prefix, nextHop, outPort)
	if err = controller.Save(r); err != nil {
		addStr := fmt.Sprintf("AddStaticRoute failed %s route %s rName %s cider %s nexthop %s outport %s", err, routerName, rName, cidrString, nextHop, outPort)
		logger.Errorf(addStr)
		res.Code = http.StatusInternalServerError
		res.Message = addStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	logger.Infof("AddStaticRoute success route %s rName %s cider %s nexthop %s outport %s", routerName, rName, cidrString, nextHop, outPort)
	res.Code = http.StatusOK
	res.Message = "add static route success"
	b.Data["json"] = res
	b.ServeJSON()

}

func (b *TuplenetAPI) ShowStaticRoute() {
	var (
		res Response
		m   RouteStaticRequest
		srs []*logicaldev.StaticRoute
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	rName := m.RName
	logger.Debugf("ShowStaticRoute get param route name %s rName %s", name, rName)

	if name == "" {
		logger.Errorf("ShowStaticRoute get param failed route name %s rName %s", name, rName)
		res.Code = http.StatusBadRequest
		res.Message = "request route param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		showStr := fmt.Sprintf("get route failed route name %s rName %s err %s", name, rName, err)
		logger.Errorf(showStr)
		res.Code = http.StatusInternalServerError
		res.Message = showStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if rName == "" {
		// show all ports
		srs, err = controller.GetRouterStaticRoutes(router)
		if err != nil {
			showStr := fmt.Sprintf("get static route failed route name %s rName %s err %s", name, rName, err)
			logger.Errorf(showStr)
			res.Code = http.StatusInternalServerError
			res.Message = showStr
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
	} else {
		r, err := controller.GetRouterStaticRoute(router, rName)
		if err != nil {
			showStr := fmt.Sprintf("get static route failed route name %s rName %s err %s", name, rName, err)
			logger.Errorf(showStr)
			res.Code = http.StatusInternalServerError
			res.Message = showStr
			b.Data["json"] = res
			b.ServeJSON()
			return
		}

		srs = []*logicaldev.StaticRoute{r}
	}

	sort.Slice(srs, func(i, j int) bool { return srs[i].Name < srs[j].Name })
	logger.Debugf("ShowStaticRoute success route %s rName %s ", name, rName)
	res.Code = http.StatusOK
	res.Message = srs
	b.Data["json"] = res
	b.ServeJSON()
}

func (b *TuplenetAPI) DelStaticRoute() {
	var (
		res Response
		m   RouteStaticRequest
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	rName := m.RName
	logger.Debugf("DelStaticRoute get param route %s rName %s", name, rName)

	if name == "" || rName == "" {
		logger.Errorf("DelStaticRoute get param failed route %s rName %s", name, rName)
		res.Code = http.StatusBadRequest
		res.Message = "request route and rName param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		delStr := fmt.Sprintf("DelStaticRoute get route failed route %s rName %s error %s", name, rName, err)
		logger.Errorf(delStr)
		res.Code = http.StatusInternalServerError
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	r, err := controller.GetRouterStaticRoute(router, rName)
	if err != nil {
		delStr := fmt.Sprintf("DelStaticRoute get static route failed route %s rName %s error %s", name, rName, err)
		logger.Errorf(delStr)
		res.Code = http.StatusInternalServerError
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	err = controller.Delete(false, r)
	if err != nil {
		delStr := fmt.Sprintf("DelStaticRoute delete failed route %s rName %s error %s", name, rName, err)
		logger.Errorf(delStr)
		res.Code = http.StatusInternalServerError
		res.Message = delStr
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	logger.Infof("DelStaticRoute delete success route %s rName %s", name, rName)
	res.Code = http.StatusOK
	res.Message = "DelStaticRoute success"
	b.Data["json"] = res
	b.ServeJSON()
}
