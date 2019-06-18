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
	"github.com/vipshop/tuplenet/control/logger"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
)

func (b *TuplenetAPI) AddNAT() {
	var (
		m   NetRequest
		res Response
		err error
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	natName := m.NatName
	cidr := m.Cidr
	xlateType := m.XlateType
	xlateIP := m.XlateIP

	if name == "" || natName == "" || cidr == "" || xlateType == "" || xlateIP == "" {
		logger.Errorf("AddNAT get param failed route %s natName %s cidr %s xlateType %s xlateIP %s", name, natName, cidr, xlateType, xlateIP)
		res.Code = http.StatusBadRequest
		res.Message = "request route natName cidr xlateType and xlateIP param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}
	ip, prefix, err := comm.ParseCIDR(cidr)
	if err != nil {
		logger.Errorf("AddNAT parse cidr failed route %s cider string %s", name, cidr)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("AddNAT parse cidr failed route %s cider string %s", name, cidr)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}
	// if xlateType neither snat or dnat return failed
	if xlateType != "snat" && xlateType != "dnat" {
		logger.Errorf("AddNAT invalid translate type, must be snat/dnat: %s", xlateType)
		res.Code = http.StatusBadRequest
		res.Message = fmt.Sprintf("AddNAT invalid translate type, must be snat/dnat: %s", xlateType)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if net.ParseIP(xlateIP) == nil {
		logger.Errorf("AddNAT invalid translate IP: %s", xlateIP)
		res.Code = http.StatusBadRequest
		res.Message = fmt.Sprintf("AddNAT invalid translate IP: %s", xlateIP)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	router, err := controller.GetRouter(name)
	if err != nil {
		logger.Errorf("AddNAT get route failed %s", err)
		res.Code = http.StatusBadRequest
		res.Message = fmt.Sprintf("AddNAT get route failed %s", err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	_, err = controller.GetRouterNAT(router, natName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		logger.Errorf("AddNAT get route failed %s", err)
		res.Code = http.StatusBadRequest
		res.Message = fmt.Sprintf("AddNAT get route failed %s", err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if err == nil {
		logger.Warnf("AddNAT route %s nat %s exists", name, natName)
		res.Code = http.StatusOK
		res.Message = fmt.Sprintf("AddNAT route %s nat %s exists", name, natName)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	nat := router.CreateNAT(natName, ip, prefix, xlateType, xlateIP)
	err = controller.Save(nat)
	if err != nil {
		logger.Errorf("AddNAT create nat failed %s", err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("AddNAT create nat failed %s", err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	logger.Debugf("AddNAT success route %s natName %s cidr %s xlateType %s xlateIP %s", name, natName, cidr, xlateType, xlateIP)
	res.Code = http.StatusOK
	res.Message = fmt.Sprintf("AddNAT success route %s nat %s ", name, natName)
	b.Data["json"] = res
	b.ServeJSON()

}

func (b *TuplenetAPI) DelNAT() {
	var (
		m   NetRequest
		res Response
		err error
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	natName := m.NatName

	if name == "" || natName == "" {
		logger.Errorf("DelNAT get param failed route %s natName %s", name, natName)
		res.Code = http.StatusBadRequest
		res.Message = "request route and natName param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}
	router, err := controller.GetRouter(name)
	if err != nil {
		logger.Errorf("DelNAT get route failed %s", err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("DelNAT get route failed %s", err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	port, err := controller.GetRouterNAT(router, natName)
	if err != nil {
		logger.Errorf("DelNAT get route nat failed %s", err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("DelNAT get route nat failed %s", err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	err = controller.Delete(false, port)
	if err != nil {
		logger.Errorf("DelNAT delete failed %s", err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("DelNAT delete failed %s", err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	logger.Debugf("DelNAT router %s NAT %s deleted", name, natName)
	res.Code = http.StatusOK
	res.Message = fmt.Sprintf("DelNAT router %s NAT %s deleted", name, natName)
	b.Data["json"] = res
	b.ServeJSON()
}

func (b *TuplenetAPI) ShowNAT() {
	var (
		m    NetRequest
		res  Response
		err  error
		nats []*logicaldev.NAT
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Route
	natName := m.NatName

	if name == "" {
		logger.Errorf("ShowNAT get param failed route %s ", name)
		res.Code = http.StatusBadRequest
		res.Message = "request route param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}
	router, err := controller.GetRouter(name)
	if err != nil {
		logger.Errorf("ShowNAT get route failed %s", err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("ShowNAT get route failed %s", err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if natName == "" { // show all nats
		nats, err = controller.GetRouterNATs(router)
		if err != nil {
			logger.Errorf("ShowNAT get route nats failed %s", err)
			res.Code = http.StatusInternalServerError
			res.Message = fmt.Sprintf("ShowNAT get route nats failed %s", err)
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
	} else {
		nat, err := controller.GetRouterNAT(router, natName)
		if err != nil {
			logger.Errorf("ShowNAT get route nat failed %s", err)
			res.Code = http.StatusInternalServerError
			res.Message = fmt.Sprintf("ShowNAT get route nat failed %s", err)
			b.Data["json"] = res
			b.ServeJSON()
			return
		}

		nats = []*logicaldev.NAT{nat}
	}

	logger.Debugf("ShowNAT success route %s natName %s", name, natName)
	sort.Slice(nats, func(i, j int) bool { return nats[i].Name < nats[j].Name })
	res.Code = http.StatusOK
	res.Message = nats
	b.Data["json"] = res
	b.ServeJSON()
}
