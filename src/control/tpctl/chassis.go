package main

import (
	"github.com/vipshop/tuplenet/control/logicaldev"
	"gopkg.in/urfave/cli.v1"
	"sort"
)

func showChassis(ctx *cli.Context) error {
	checkArgs(ctx, 0, 1, "require only one name")

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

func delChassis(ctx *cli.Context) error {
	checkArgs(ctx, 1, 1, "require a name")

	name := ctx.Args().Get(0)
	chassis, err := controller.GetChassis(name)
	if err != nil {
		fail(err)
	}

	err = controller.Delete(false, chassis)
	if err != nil {
		failf("failed to delete %s: %v", name, err)
	}

	succeedf("%s deleted", name)
	return nil
}
