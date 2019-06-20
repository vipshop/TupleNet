package main

import (
	"fmt"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"gopkg.in/urfave/cli.v1"
	"net"
	"sort"
)

func showChassis(ctx *cli.Context) error {
	checkArgsThenConnect(ctx, 0, 1, "require only one name")

	var (
		chs []*logicaldev.Chassis
		err error
	)
	if len(ctx.Args()) == 0 { // no name provided show all chassises
		chs, err = controller.GetChassises()
		if err != nil {
			fail(err)
		}
	} else { // chassis name provided
		name := ctx.Args().First()
		chassis, err := controller.GetChassis(name)
		if err != nil {
			fail(err)
		}

		chs = []*logicaldev.Chassis{chassis}
	}

	sort.Slice(chs, func(i, j int) bool { return chs[i].Name < chs[j].Name })
	printDevices(chs)

	return nil
}

func delChassisByIP(ip string) error {
	chs, err := controller.GetChassises()
	if err != nil {
		failf("failed to get chassis by ip %s: %v", ip, err)
	}

	cnt := 0
	for _, ch := range chs {
		if ch.IP == ip {
			cnt++
			delChassisByName(ch.Name)
		}
	}
	if cnt == 0 {
		failf("failed to get chassis by ip %s", ip)
	}
	return nil
}

func delChassisByName(name string) error {
	chassis, err := controller.GetChassis(name)
	if err != nil {
		fail(err)
	}

	err = controller.Delete(false, chassis)
	if err != nil {
		failf("failed to delete %s: %v", name, err)
	}

	fmt.Printf("%s deleted\n", name)
	return nil
}

func delChassis(ctx *cli.Context) error {
	checkArgsThenConnect(ctx, 1, 1, "require a name or ip")
	name := ctx.Args().Get(0)
	if net.ParseIP(name) != nil {
		delChassisByIP(name)
	} else {
		delChassisByName(name)
	}
	return nil
}
