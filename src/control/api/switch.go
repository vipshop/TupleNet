package api

import (
	"net"
	"encoding/json"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/comm"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"

	"github.com/vipshop/tuplenet/control/logger"
	"sort"
	"net/http"
)

type Switch interface {
	AddSwitch()
	ShowSwitch()
	DelSwitch()
	AddSwitchPort()
	ShowSwitchPort()
	DelSwitchPort()
	AddPatchPort()
}

func (b *TuplenetAPI) AddSwitch() {
	var (
		m SwitchRequest
	)
	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "AddSwitch decode get param body failed %s", err)
		return
	}
	name := m.Switch
	logger.Infof("AddSwitch get param switch %s", name)

	if CheckNilParam(name) {
		b.Response(http.StatusBadRequest, "AddSwitch request switch param %s", nil, name)
		return
	}
	if err := controller.Save(logicaldev.NewSwitch(name)); err != nil {
		b.Response(http.StatusInternalServerError, "AddSwitch %s failed %s", err, name)
		return
	}

	b.Response(http.StatusOK, "AddSwitch success switch %s", nil, name)
}

func (b *TuplenetAPI) ShowSwitch() {
	var (
		err      error
		switches []*logicaldev.Switch
	)
	name := b.GetString("switch")
	logger.Infof("ShowSwitch get param switch %s ", name)

	if CheckNilParam(name) {
		switches, err = controller.GetSwitches()
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowSwitch get all switch failed %s", err)
			return
		}
	} else {
		s, err := controller.GetSwitch(name)
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowSwitch get switch name %s failed %s", err, name)
			return
		}

		switches = []*logicaldev.Switch{s}
	}

	sort.Slice(switches, func(i, j int) bool { return switches[i].Name < switches[j].Name })
	logger.Infof("ShowSwitch success swtich %s", name)
	b.NormalResponse(switches)
}

func (b *TuplenetAPI) DelSwitch() {
	var (
		m SwitchRequest
	)

	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "DelSwitch decode get param body failed %s", err)
		return
	}
	name := m.Switch
	recursive := m.Recursive
	logger.Infof("DelSwitch get param switch %s recursive %v ", name, recursive)

	if CheckNilParam(name) {
		b.Response(http.StatusBadRequest, "DelSwitch request param failed switch %s recursive %v ", nil, name, recursive)
		return
	}

	swtch, err := controller.GetSwitch(name)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelSwitch get switch %s failed %s", err, name)
		return
	}

	ports, err := controller.GetSwitchPorts(swtch)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelSwitch get switch %s ports failed %s", err, name)
		return
	}

	if len(ports) != 0 {
		// for switch with children, it depends

		if recursive {
			err := controller.Delete(true, swtch)
			if err != nil {
				b.Response(http.StatusInternalServerError, "DelSwitch remove switch name %s switch %v failed %s", err, name, swtch)
				return
			}
		} else {
			b.Response(http.StatusInternalServerError, "DelSwitch failed switch name %s there are remaining ports, consider use recursive param with true", nil, name)
			return
		}
	} else {
		err = controller.Delete(false, swtch)
		if err != nil {
			b.Response(http.StatusInternalServerError, "DelSwitch failed switch name %s err %s", err, name)
			return
		}
	}

	b.Response(http.StatusOK, "DelSwitch success switch %s ", nil, name)
}

// operate on logical switch port(lsp)
func (b *TuplenetAPI) AddSwitchPort() {
	var (
		m SwitchPortRequest
	)

	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "AddSwitchPort decode get param body failed %s", err)
		return
	}
	switchName := m.Switch
	portName := m.PortName
	ip := m.IP
	peer := m.Peer
	mac := m.Mac
	logger.Infof("AddSwitchPort get param switch %s portName %s ip %s mac %s peer %s", switchName, portName, ip, mac, peer)

	if CheckNilParam(switchName, ip, portName) {
		b.Response(http.StatusBadRequest, "AddSwitchPort get param failed switch %s portName %s ip %s mac %s peer %s", nil, switchName, portName, ip, mac, peer)
		return
	}

	if net.ParseIP(ip) == nil {
		b.Response(http.StatusBadRequest, "AddSwitchPort get invalid ip switch %s ip %s", nil, switchName, ip)
		return
	}

	// check mac
	if CheckNilParam(mac) {
		mac = comm.MacFromIP(ip)
	} else {
		if _, err := net.ParseMAC(mac); err != nil {
			b.Response(http.StatusBadRequest, "AddSwitchPort get invalid mac switch %s mac %s err %s", err, switchName, mac)
			return
		}
	}

	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		b.Response(http.StatusInternalServerError, "AddSwitchPort get switch failed switch %s err %s", err, switchName)
		return
	}

	if _, err = controller.GetSwitchPort(swtch, portName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		b.Response(http.StatusInternalServerError, "AddSwitchPort switch %s port name %s ip %s mac %s peer %s get switch port failed %s", err, switchName, portName, ip, mac, peer)
		return
	}

	if CheckNilParam(mac) {
		b.Response(http.StatusInternalServerError, "AddSwitchPort switch name %s port name %s ip %s peer %s mac is null", nil, switchName, portName, ip, peer)
		return
	}

	port := swtch.CreatePort(portName, ip, mac)
	port.PeerRouterPortName = peer

	if err = controller.Save(port); err != nil {
		b.Response(http.StatusInternalServerError, "AddSwitchPort switch name %s port name %s ip %s mac %s peer %s err %s", err, switchName, portName, ip, mac, peer)
		return
	}

	b.Response(http.StatusOK, "AddSwitchPort success switch %s portName %s ip %s mac %s peer %s", nil, switchName, portName, ip, mac, peer)
}

func (b *TuplenetAPI) ShowSwitchPort() {
	var (
		ports []*logicaldev.SwitchPort
	)
	switchName := b.GetString("switch")
	portName := b.GetString("portName")
	logger.Infof("ShowSwitchPort get param switch %s portName %s ", switchName, portName)

	if CheckNilParam(switchName) {
		b.Response(http.StatusBadRequest, "ShowSwitchPort get param failed switch %s ", nil, switchName)
		return
	}
	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		b.Response(http.StatusInternalServerError, "ShowSwitchPort get switch %s failed %s", err, switchName)
		return
	}

	if CheckNilParam(portName) {
		// show all ports
		ports, err = controller.GetSwitchPorts(swtch)
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowSwitchPort switch %s get all switch port failed %s ", err, switchName)
			return
		}
	} else {
		port, err := controller.GetSwitchPort(swtch, portName)
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowSwitchPort switch %s get switch port %s failed %s ", err, switchName, portName)
			return
		}

		ports = []*logicaldev.SwitchPort{port}
	}

	sort.Slice(ports, func(i, j int) bool { return ports[i].Name < ports[j].Name })
	logger.Infof("ShowSwitchPort success switch %s get switch port %s ", switchName, portName)
	b.NormalResponse(ports)
}

func (b *TuplenetAPI) DelSwitchPort() {
	var (
		m SwitchPortRequest
	)

	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "DelSwitchPort decode get param body failed %s", err)
		return
	}
	switchName := m.Switch
	portName := m.PortName
	logger.Infof("ShowSwitchPort get param switch %s portName %s", switchName, portName)

	if CheckNilParam(switchName, portName) {
		b.Response(http.StatusBadRequest, "ShowSwitchPort get param failed switch %s portName %s", nil, switchName, portName)
		return
	}
	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelSwitchPort switch %s failed %s", err, switchName)
		return
	}

	port, err := controller.GetSwitchPort(swtch, portName)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelSwitchPort switch %s get switch port %s failed %s ", err, switchName, portName)
		return
	}

	err = controller.Delete(false, port)
	if err != nil {
		b.Response(http.StatusInternalServerError, "DelSwitchPort switch %s delete port %s failed %s ", err, switchName, portName)
		return
	}

	b.Response(http.StatusOK, "DelSwitchPort success switch %s port %s", nil, switchName, portName)
}

func (b *TuplenetAPI) AddPatchPort() {
	var (
		m SwitchPatchPortRequest
	)

	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "AddPatchPort decode get param body failed %s", err)
		return
	}
	switchName := m.Switch
	portName := m.PortName
	chassis := m.Chassis
	peer := m.Peer
	mac := "ff:ff:ff:ff:ff:ee"
	ip := "255.255.255.255"
	logger.Infof("AddPatchPort get param switch %s portName %s chassis %s peer %s", switchName, portName, chassis, peer)

	if CheckNilParam(switchName, portName, chassis, peer) {
		b.Response(http.StatusBadRequest, "AddPatchPort get param failed switch %s portName %s chassis %s peer %s", nil, switchName, portName, chassis, peer)
		return
	}

	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		b.Response(http.StatusInternalServerError, "AddPatchPort get switch %s failed %s", err, switchName)
		return
	}

	_, err = controller.GetSwitchPort(swtch, portName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		b.Response(http.StatusInternalServerError, "AddPatchPort get switch %s port %s failed %s", err, switchName, portName)
		return
	}

	if err == nil {
		b.Response(http.StatusOK, "AddPatchPort switch %s port %s exists", nil, switchName, portName)
		return
	}

	port := swtch.CreatePort(portName, ip, mac)
	port.PeerRouterPortName = peer
	port.Chassis = chassis
	err = controller.Save(port)
	if err != nil {
		b.Response(http.StatusInternalServerError, "AddPatchPort switch %s port %s chassis %s peer %s failed %s", err, switchName, portName, chassis, peer)
		return
	}

	b.Response(http.StatusOK, "AddPatchPort switch %s port %s chassis %s peer %s success", nil, switchName, portName, chassis, peer)
}
