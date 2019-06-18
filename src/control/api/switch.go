package api

import (
	"net"
	"fmt"
	"net/http"
	"io/ioutil"
	"encoding/json"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/comm"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"

	"github.com/vipshop/tuplenet/control/logger"
	"sort"
)

type Switch interface {
	AddSwitch()
	ShowSwitch()
	DelSwitch()
	AddSwitchPort()
	ShowSwitchPort()
	DelSwitchPort()
}

func (b *TuplenetAPI) AddSwitch() {
	var (
		m   SwitchRequest
		res Response
	)
	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Switch

	if name == "" {
		logger.Errorf("AddSwitch request switch param  %s", name)
		res.Code = http.StatusBadRequest
		res.Message = "AddSwitch request switch param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}
	if err := controller.Save(logicaldev.NewSwitch(name)); err != nil {
		logger.Errorf("AddSwitch %s failed %s", name, err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("AddSwitch %s failed %s", name, err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	logger.Debugf("AddSwitch success switch %s", name)
	res.Code = http.StatusOK
	res.Message = fmt.Sprintf("AddSwitch success switch %s", name)
	b.Data["json"] = res
	b.ServeJSON()
}

func (b *TuplenetAPI) ShowSwitch() {
	var (
		m   SwitchRequest
		res Response
		err error
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Switch

	var (
		switches []*logicaldev.Switch
	)
	if name == "" {
		switches, err = controller.GetSwitches()
		if err != nil {
			logger.Errorf("ShowSwitch get all switch failed %s", err)
			res.Code = http.StatusInternalServerError
			res.Message = fmt.Sprintf("ShowSwitch get all switch failed %s", err)
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
	} else {
		s, err := controller.GetSwitch(name)
		if err != nil {
			logger.Errorf("ShowSwitch get switch name %s failed %s", name, err)
			res.Code = http.StatusInternalServerError
			res.Message = fmt.Sprintf("ShowSwitch get switch name %s failed %s", name, err)
			b.Data["json"] = res
			b.ServeJSON()
			return
		}

		switches = []*logicaldev.Switch{s}
	}

	sort.Slice(switches, func(i, j int) bool { return switches[i].Name < switches[j].Name })
	logger.Debugf("ShowSwitch success swtich %s", name)
	res.Code = http.StatusOK
	res.Message = switches
	b.Data["json"] = res
	b.ServeJSON()
}

func (b *TuplenetAPI) DelSwitch() {
	var (
		m   SwitchRequest
		res Response
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Switch
	recursive := m.Recursive
	logger.Debugf("DelSwitch request param switch %s recursive %v ", name, recursive)

	if name == "" {
		logger.Errorf("DelSwitch request param failed switch %s recursive %v ", name, recursive)
		res.Code = http.StatusBadRequest
		res.Message = "request switch param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	swtch, err := controller.GetSwitch(name)
	if err != nil {
		logger.Errorf("DelSwitch get switch %s failed %s", name, err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("DelSwitch get switch %s failed %s", name, err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	ports, err := controller.GetSwitchPorts(swtch)
	if err != nil {
		logger.Errorf("DelSwitch get switch %s ports failed %s", name, err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("DelSwitch get switch %s ports failed %s", name, err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if len(ports) != 0 {
		// for switch with children, it depends

		if recursive {
			err := controller.Delete(true, swtch)
			if err != nil {
				logger.Errorf("DelSwitch remove switch name %s switch %v failed %s", name, swtch, err)
				res.Code = http.StatusInternalServerError
				res.Message = fmt.Sprintf("DelSwitch remove switch name %s switch %v failed %s", name, swtch, err)
				b.Data["json"] = res
				b.ServeJSON()
				return
			}
		} else {
			logger.Errorf("DelSwitch failed switch name %s there are remaining ports, consider use recursive param with true", name)
			res.Code = http.StatusInternalServerError
			res.Message = fmt.Sprintf("DelSwitch failed switch name %s there are remaining ports, consider use recursive param with true", name)
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
	} else {
		err = controller.Delete(false, swtch)
		if err != nil {
			logger.Errorf("DelSwitch failed switch name %s err %s", name, err)
			res.Code = http.StatusInternalServerError
			res.Message = fmt.Sprintf("DelSwitch failed switch name %s err %s", name, err)
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
	}

	logger.Debugf("DelSwitch success switch %s ", name)
	res.Code = http.StatusOK
	res.Message = fmt.Sprintf("DelSwitch success switch %s ", name)
	b.Data["json"] = res
	b.ServeJSON()
}

// operate on logical switch port(lsp)
func (b *TuplenetAPI) AddSwitchPort() {
	var (
		m   SwitchRequest
		res Response
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	switchName := m.Switch
	portName := m.PortName
	ip := m.IP
	peer := m.Peer
	mac := m.Mac
	logger.Debugf("AddSwitchPort get param switch %s portName %s ip %s mac %s peer %s", switchName, portName, ip, mac, peer)

	if switchName == "" || ip == "" || portName == "" {
		logger.Errorf("AddSwitchPort get param failed switch %s portName %s ip %s mac %s peer %s", switchName, portName, ip, mac, peer)
		res.Code = http.StatusBadRequest
		res.Message = "request switch, portName and ip (mac) (peer) param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if net.ParseIP(ip) == nil {
		logger.Errorf("AddSwitchPort parse ip failed switch %s ip %s", switchName, ip)
		res.Code = http.StatusBadRequest
		res.Message = "invalid ip"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	// check mac
	if mac == "" {
		mac = comm.MacFromIP(ip)
	} else {
		if _, err := net.ParseMAC(mac); err != nil {
			logger.Errorf("AddSwitchPort parse mac failed switch %s mac %s err %s", switchName, mac, err)
			res.Code = http.StatusBadRequest
			res.Message = "invalid mac"
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
	}

	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		logger.Errorf("AddSwitchPort get switch failed switch %s err %s", switchName, err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("AddSwitchPort get switch failed switch %s err %s", switchName, err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if _, err = controller.GetSwitchPort(swtch, portName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		logger.Errorf("AddSwitchPort get switch port failed switch %s porrName ip %s mac %s peer %s err %s", switchName, portName, ip, mac, peer, err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("AddSwitchPort get switch port failed switch %s port name %s ip %s mac %s peer %s err %s", switchName, portName, ip, mac, peer, err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if mac == "" {
		logger.Errorf("AddSwitchPort switch name %s port name %s ip %s peer %s mac is null", switchName, portName, ip, peer)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("AddSwitchPort switch name %s port name %s ip %s peer %s mac is null", switchName, portName, ip, peer)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	port := swtch.CreatePort(portName, ip, mac)
	port.PeerRouterPortName = peer

	if err = controller.Save(port); err != nil {
		logger.Errorf("AddSwitchPort switch name %s port name %s ip %s mac %s peer %s", switchName, portName, ip, mac, peer)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("AddSwitchPort switch name %s port name %s ip %s mac %s peer %s err %s", switchName, portName, ip, mac, peer, err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	logger.Debugf("AddSwitchPort success switch %s portName %s ip %s mac %s peer %s", switchName, portName, ip, mac, peer)
	res.Code = http.StatusOK
	res.Message = fmt.Sprintf("AddSwitchPort success switch %s portName %s ip %s mac %s peer %s", switchName, portName, ip, mac, peer)
	b.Data["json"] = res
	b.ServeJSON()

}

func (b *TuplenetAPI) ShowSwitchPort() {
	var (
		m     SwitchRequest
		res   Response
		ports []*logicaldev.SwitchPort
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	switchName := m.Switch
	portName := m.PortName
	logger.Debugf("ShowSwitchPort get param switch %s portName %s ", switchName, portName)

	if switchName == "" {
		logger.Errorf("ShowSwitchPort get param failed switch %s ", switchName)
		res.Code = http.StatusBadRequest
		res.Message = "request switch param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}
	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		logger.Errorf("ShowSwitchPort get switch %s failed %s", switchName, err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("ShowSwitchPort get switch %s failed %s", switchName, err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	if portName == "" {
		// show all ports
		ports, err = controller.GetSwitchPorts(swtch)
		if err != nil {
			logger.Errorf("ShowSwitchPort switch %s get all switch port failed %s ", switchName, err)
			res.Code = http.StatusInternalServerError
			res.Message = fmt.Sprintf("ShowSwitchPort switch %s get all switch port failed %s ", switchName, err)
			b.Data["json"] = res
			b.ServeJSON()
			return
		}
	} else {
		port, err := controller.GetSwitchPort(swtch, portName)
		if err != nil {
			logger.Errorf("ShowSwitchPort switch %s get switch port %s failed %s ", switchName, portName, err)
			res.Code = http.StatusInternalServerError
			res.Message = fmt.Sprintf("ShowSwitchPort switch %s get switch port %s failed %s ", switchName, portName, err)
			b.Data["json"] = res
			b.ServeJSON()
			return
		}

		ports = []*logicaldev.SwitchPort{port}
	}

	sort.Slice(ports, func(i, j int) bool { return ports[i].Name < ports[j].Name })
	logger.Debugf("ShowSwitchPort success switch %s get switch port %s ", switchName, portName)
	res.Code = http.StatusOK
	res.Message = ports
	b.Data["json"] = res
	b.ServeJSON()
}

func (b *TuplenetAPI) DelSwitchPort() {
	var (
		m   SwitchRequest
		res Response
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	switchName := m.Switch
	portName := m.PortName
	logger.Debugf("ShowSwitchPort get param switch %s portName %s", switchName, portName)

	if switchName == "" || portName == "" {
		logger.Errorf("ShowSwitchPort get param failed switch %s portName %s", switchName, portName)
		res.Code = http.StatusBadRequest
		res.Message = "request switch and portName param"
		b.Data["json"] = res
		b.ServeJSON()
		return
	}
	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		logger.Errorf("DelSwitchPort switch %s failed %s ", switchName, err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("DelSwitchPort switch %s failed %s ", switchName, err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	port, err := controller.GetSwitchPort(swtch, portName)
	if err != nil {
		logger.Errorf("DelSwitchPort switch %s get switch port %s failed %s ", switchName, portName, err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("DelSwitchPort switch %s get switch port %s failed %s ", switchName, portName, err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	err = controller.Delete(false, port)
	if err != nil {
		logger.Errorf("DelSwitchPort switch %s delete port %s failed %s ", switchName, portName, err)
		res.Code = http.StatusInternalServerError
		res.Message = fmt.Sprintf("DelSwitchPort switch %s delete port %s failed %s ", switchName, portName, err)
		b.Data["json"] = res
		b.ServeJSON()
		return
	}

	logger.Debugf("DelSwitchPort switch %s port %s deleted", switchName, portName)
	res.Code = http.StatusOK
	res.Message = fmt.Sprintf("DelSwitchPort switch %s port %s deleted", switchName, portName)
	b.Data["json"] = res
	b.ServeJSON()
}
