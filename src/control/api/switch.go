package api

import (
	"net"
	"fmt"
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
	AddPatchPort()
}

func (b *TuplenetAPI) AddSwitch() {
	var (
		m SwitchRequest
	)
	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Switch

	if name == "" {
		logger.Errorf("AddSwitch request switch param  %s", name)
		b.BadResponse("AddSwitch request switch param")
		return
	}
	if err := controller.Save(logicaldev.NewSwitch(name)); err != nil {
		addStr := fmt.Sprintf("AddSwitch %s failed %s", name, err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	logger.Debugf("AddSwitch success switch %s", name)
	b.NormalResponse("AddSwitch success")
}

func (b *TuplenetAPI) ShowSwitch() {
	var (
		m   SwitchRequest
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
			showStr := fmt.Sprintf("ShowSwitch get all switch failed %s", err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}
	} else {
		s, err := controller.GetSwitch(name)
		if err != nil {
			showStr := fmt.Sprintf("ShowSwitch get switch name %s failed %s", name, err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}

		switches = []*logicaldev.Switch{s}
	}

	sort.Slice(switches, func(i, j int) bool { return switches[i].Name < switches[j].Name })
	logger.Debugf("ShowSwitch success swtich %s", name)
	b.NormalResponse(switches)
}

func (b *TuplenetAPI) DelSwitch() {
	var (
		m SwitchRequest
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Switch
	recursive := m.Recursive
	logger.Debugf("DelSwitch request param switch %s recursive %v ", name, recursive)

	if name == "" {
		logger.Errorf("DelSwitch request param failed switch %s recursive %v ", name, recursive)
		b.BadResponse("request switch param")
		return
	}

	swtch, err := controller.GetSwitch(name)
	if err != nil {
		delStr := fmt.Sprintf("DelSwitch get switch %s failed %s", name, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	ports, err := controller.GetSwitchPorts(swtch)
	if err != nil {
		delStr := fmt.Sprintf("DelSwitch get switch %s ports failed %s", name, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	if len(ports) != 0 {
		// for switch with children, it depends

		if recursive {
			err := controller.Delete(true, swtch)
			if err != nil {
				delStr := fmt.Sprintf("DelSwitch remove switch name %s switch %v failed %s", name, swtch, err)
				logger.Errorf(delStr)
				b.InternalServerErrorResponse(delStr)
				return
			}
		} else {
			delStr := fmt.Sprintf("DelSwitch failed switch name %s there are remaining ports, consider use recursive param with true", name)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}
	} else {
		err = controller.Delete(false, swtch)
		if err != nil {
			delStr := fmt.Sprintf("DelSwitch failed switch name %s err %s", name, err)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}
	}

	logger.Debugf("DelSwitch success switch %s ", name)
	b.NormalResponse("DelSwitch success")
}

// operate on logical switch port(lsp)
func (b *TuplenetAPI) AddSwitchPort() {
	var (
		m SwitchPortRequest
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
		b.BadResponse("request switch, portName and ip (mac) (peer) param")
		return
	}

	if net.ParseIP(ip) == nil {
		logger.Errorf("AddSwitchPort parse ip failed switch %s ip %s", switchName, ip)
		b.BadResponse("invalid ip")
		return
	}

	// check mac
	if mac == "" {
		mac = comm.MacFromIP(ip)
	} else {
		if _, err := net.ParseMAC(mac); err != nil {
			logger.Errorf("AddSwitchPort parse mac failed switch %s mac %s err %s", switchName, mac, err)
			b.BadResponse("invalid mac")
			return
		}
	}

	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		addStr := fmt.Sprintf("AddSwitchPort get switch failed switch %s err %s", switchName, err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	if _, err = controller.GetSwitchPort(swtch, portName); err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		addStr := fmt.Sprintf("AddSwitchPort get switch port failed switch %s port name %s ip %s mac %s peer %s err %s", switchName, portName, ip, mac, peer, err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	if mac == "" {
		addStr := fmt.Sprintf("AddSwitchPort switch name %s port name %s ip %s peer %s mac is null", switchName, portName, ip, peer)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	port := swtch.CreatePort(portName, ip, mac)
	port.PeerRouterPortName = peer

	if err = controller.Save(port); err != nil {
		addStr := fmt.Sprintf("AddSwitchPort switch name %s port name %s ip %s mac %s peer %s err %s", switchName, portName, ip, mac, peer, err)
		logger.Errorf(addStr)
		b.InternalServerErrorResponse(addStr)
		return
	}

	logger.Debugf("AddSwitchPort success switch %s portName %s ip %s mac %s peer %s", switchName, portName, ip, mac, peer)
	b.NormalResponse("AddSwitchPort success")

}

func (b *TuplenetAPI) ShowSwitchPort() {
	var (
		m     SwitchPortRequest
		ports []*logicaldev.SwitchPort
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	switchName := m.Switch
	portName := m.PortName
	logger.Debugf("ShowSwitchPort get param switch %s portName %s ", switchName, portName)

	if switchName == "" {
		logger.Errorf("ShowSwitchPort get param failed switch %s ", switchName)
		b.BadResponse("request switch param")
		return
	}
	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		showStr := fmt.Sprintf("ShowSwitchPort get switch %s failed %s", switchName, err)
		logger.Errorf(showStr)
		b.InternalServerErrorResponse(showStr)
		return
	}

	if portName == "" {
		// show all ports
		ports, err = controller.GetSwitchPorts(swtch)
		if err != nil {
			showStr := fmt.Sprintf("ShowSwitchPort switch %s get all switch port failed %s ", switchName, err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}
	} else {
		port, err := controller.GetSwitchPort(swtch, portName)
		if err != nil {
			showStr := fmt.Sprintf("ShowSwitchPort switch %s get switch port %s failed %s ", switchName, portName, err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}

		ports = []*logicaldev.SwitchPort{port}
	}

	sort.Slice(ports, func(i, j int) bool { return ports[i].Name < ports[j].Name })
	logger.Debugf("ShowSwitchPort success switch %s get switch port %s ", switchName, portName)
	b.NormalResponse(ports)
}

func (b *TuplenetAPI) DelSwitchPort() {
	var (
		m SwitchPortRequest
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	switchName := m.Switch
	portName := m.PortName
	logger.Debugf("ShowSwitchPort get param switch %s portName %s", switchName, portName)

	if switchName == "" || portName == "" {
		logger.Errorf("ShowSwitchPort get param failed switch %s portName %s", switchName, portName)
		b.BadResponse("request switch and portName param")
		return
	}
	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		delStr := fmt.Sprintf("DelSwitchPort switch %s failed %s ", switchName, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	port, err := controller.GetSwitchPort(swtch, portName)
	if err != nil {
		delStr := fmt.Sprintf("DelSwitchPort switch %s get switch port %s failed %s ", switchName, portName, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	err = controller.Delete(false, port)
	if err != nil {
		delStr := fmt.Sprintf("DelSwitchPort switch %s delete port %s failed %s ", switchName, portName, err)
		logger.Errorf(delStr)
		b.InternalServerErrorResponse(delStr)
		return
	}

	logger.Debugf("DelSwitchPort switch %s port %s deleted", switchName, portName)
	b.NormalResponse("DelSwitchPort  success")
}

func (b *TuplenetAPI) AddPatchPort()  {
	var (
		m SwitchPatchPortRequest
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	switchName := m.Switch
	portName := m.PortName
	chassis := m.Chassis
	peer := m.Peer
	mac := "ff:ff:ff:ff:ff:ee"
	ip := "255.255.255.255"

	logger.Debugf("AddPatchPort get param switch %s portName %s chassis %s peer %s", switchName, portName, chassis, peer)

	if switchName == "" || portName == "" || chassis == "" || peer == "" {
		logger.Errorf("AddPatchPort get param failed switch %s portName %s chassis %s peer %s", switchName, portName, chassis, peer)
		b.BadResponse("request switch portName chassis and peer param")
		return
	}

	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		patchStr := fmt.Sprintf("AddPatchPort get switch %s failed %s ", switchName, err)
		logger.Errorf(patchStr)
		b.InternalServerErrorResponse(patchStr)
		return
	}

	_, err = controller.GetSwitchPort(swtch, portName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		patchStr := fmt.Sprintf("AddPatchPort get switch %s port %s failed %s ", switchName, portName, err)
		logger.Errorf(patchStr)
		b.InternalServerErrorResponse(patchStr)
		return
	}

	if err == nil {
		patchStr := fmt.Sprintf("AddPatchPort switch %s port %s exists", switchName, portName)
		logger.Warnf(patchStr)
		b.NormalResponse(patchStr)
		return
	}

	port := swtch.CreatePort(portName, ip, mac)
	port.PeerRouterPortName = peer
	port.Chassis = chassis
	err = controller.Save(port)
	if err != nil {
		patchStr := fmt.Sprintf("AddPatchPort switch %s port %s chassis %s peer %s failed %s ", switchName, portName, chassis, peer, err)
		logger.Errorf(patchStr)
		b.InternalServerErrorResponse(patchStr)
		return
	}

	patchStr := fmt.Sprintf("AddPatchPort switch %s port %s chassis %s peer %s success", switchName, portName, chassis, peer)
	logger.Infof(patchStr)
	b.NormalResponse(patchStr)
}