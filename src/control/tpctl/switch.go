package main

import (
	"fmt"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"gopkg.in/urfave/cli.v1"
	"sort"
)

func addSwitch(ctx *cli.Context) error {
	checkArgsThenConnect(ctx, 1, 1, "require a name")

	name := validateAndTrimSpace(ctx.Args().Get(0))

	err := controller.Save(logicaldev.NewSwitch(name))
	if err != nil {
		fail(err)
	}

	fmt.Printf("switch %s created\n", name)

	return nil
}

func showSwitch(ctx *cli.Context) error {
	checkArgsThenConnect(ctx, 0, 1, "require at most one name")

	var (
		switches []*logicaldev.Switch
		err      error
	)

	if len(ctx.Args()) == 0 {
		switches, err = controller.GetSwitches()
		if err != nil {
			fail(err)
		}
	} else {
		name := ctx.Args().First()
		s, err := controller.GetSwitch(name)
		if err != nil {
			fail(err)
		}

		switches = []*logicaldev.Switch{s}
	}

	sort.Slice(switches, func(i, j int) bool { return switches[i].Name < switches[j].Name })
	printDevices(switches)
	return nil
}

func delSwitch(ctx *cli.Context) error {
	checkArgsThenConnect(ctx, 1, 1, "require a name")

	name := ctx.Args().Get(0)
	swtch, err := controller.GetSwitch(name)
	if err != nil {
		fail(err)
	}

	ports, err := controller.GetSwitchPorts(swtch)
	if err != nil {
		failf("unable to get switch ports, abort unsafe deletion of %s: %v", name, err)
	}

	if len(ports) != 0 { // for switch with children, it depends
		recursive := ctx.Bool("recursive")

		if recursive {
			err := controller.Delete(true, swtch)
			if err != nil {
				failf("failed to remove %s: %v", name, err)
			}
		} else {
			failf(`failed to delete %s: there are remaining ports, consider using "-r"?`, name)
		}
	} else {
		err = controller.Delete(false, swtch)
		if err != nil {
			failf("failed to delete %s: %v", name, err)
		}
	}

	fmt.Printf("%s deleted\n", name)
	return nil
}

func showSwitchPort(ctx *cli.Context) error {
	checkArgsThenConnect(ctx, 1, 2, "require at least switch name and optionally a port name")

	var (
		switchName string
		portName   string
		ports      []*logicaldev.SwitchPort
		err        error
	)

	switchName = ctx.Args().Get(0)
	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		fail(err)
	}

	portName = ctx.Args().Get(1)
	if portName == "" { // show all ports
		ports, err = controller.GetSwitchPorts(swtch)
		if err != nil {
			fail(err)
		}
	} else {
		port, err := controller.GetSwitchPort(swtch, portName)
		if err != nil {
			fail(err)
		}

		ports = []*logicaldev.SwitchPort{port}
	}

	sort.Slice(ports, func(i, j int) bool { return ports[i].Name < ports[j].Name })
	printDevices(ports)
	return nil
}

func addPatchPort(ctx *cli.Context) error {
	checkArgsThenConnect(ctx, 4, 4, "require a switch name, a port name, chassis and peer ovs-bridge name")

	switchName := ctx.Args().Get(0)
	portName := validateAndTrimSpace(ctx.Args().Get(1))
	chassis := ctx.Args().Get(2)
	peer := ctx.Args().Get(3)

	mac := "ff:ff:ff:ff:ff:ee"
	ip := "255.255.255.255"
	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		fail(err)
	}

	_, err = controller.GetSwitchPort(swtch, portName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		fail(err)
	}

	if err == nil {
		failf("switch %s port %s exists", switchName, portName)
	}

	port := swtch.CreatePort(portName, ip, mac)
	port.PeerRouterPortName = peer
	port.Chassis = chassis
	err = controller.Save(port)
	if err != nil {
		fail(err)
	}

	fmt.Printf("switch %s patchport %s created\n", switchName, portName)

	return nil
}

func addSwitchPort(ctx *cli.Context) error {
	checkArgsThenConnect(ctx, 3, 5, "require a switch name, a port name, an IP and optionally a MAC, a peer port")

	switchName := ctx.Args().Get(0)
	portName := validateAndTrimSpace(ctx.Args().Get(1))
	ip := ctx.Args().Get(2)
	mac := ctx.Args().Get(3)
	peer := ctx.Args().Get(4)

	validateIP(ip)

	if mac == "" {
		mac = etcd3.MacFromIP(ip)
	} else {
		validateMAC(mac)
	}

	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		fail(err)
	}

	_, err = controller.GetSwitchPort(swtch, portName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		fail(err)
	}

	if err == nil {
		failf("switch %s port %s exists", switchName, portName)
	}

	port := swtch.CreatePort(portName, ip, mac)
	port.PeerRouterPortName = peer

	err = controller.Save(port)
	if err != nil {
		fail(err)
	}

	fmt.Printf("switch %s port %s created\n", switchName, portName)

	return nil
}

func delSwitchPort(ctx *cli.Context) error {
	checkArgsThenConnect(ctx, 2, 2, "require switch name and a port name")

	switchName := ctx.Args().Get(0)
	portName := ctx.Args().Get(1)

	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		fail(err)
	}

	port, err := controller.GetSwitchPort(swtch, portName)
	if err != nil {
		fail(err)
	}

	err = controller.Delete(false, port)
	if err != nil {
		fail(err)
	}

	fmt.Printf("switch %s port %s deleted\n", switchName, portName)

	return nil
}
