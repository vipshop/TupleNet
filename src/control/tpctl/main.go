package main

import (
	"fmt"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
	"gopkg.in/urfave/cli.v1"
	"os"
)

var (
	controller *etcd3.Controller
	version    = "untagged"
	commit     = "undefined"

	// global control param
	endpoints, keyPrefix string
	outputFormat         = "plain"
)

func main() {
	app := cli.NewApp()
	app.Version = version + "@" + commit
	app.Flags = []cli.Flag{
		cli.StringFlag{
			Name:        "endpoints, e",
			Usage:       "a list of etcd3 server urls separated by ,",
			Value:       "localhost:2379",
			Destination: &endpoints,
		},
		cli.StringFlag{
			Name:        "prefix, p",
			Usage:       "the prefix used in data store",
			Value:       "/tuplenet",
			Destination: &keyPrefix,
		},
		cli.BoolFlag{
			Name:  "json, j",
			Usage: "output as json",
		},
	}

	app.Commands = []cli.Command{
		// logical router command
		{
			Name:  "lr",
			Usage: "operate on logical router",
			Subcommands: []cli.Command{
				{
					Name:      "add",
					Aliases:   []string{"a"},
					Usage:     "add a new logical router",
					ArgsUsage: "ROUTER [CHASSIS]",
					Action:    addRouter,
				},
				{
					Name:    "del",
					Aliases: []string{"d"},
					Usage:   "delete a logical router",
					Flags: []cli.Flag{
						cli.BoolFlag{
							Name:  "recursive, r",
							Usage: "delete everything tied to a logical router",
						},
					},
					Action: delRouter,
					Before: confirmDelete,
				},
				{
					Name:      "link",
					Usage:     "link a logical router to a logical switch",
					Action:    linkSwitch,
					ArgsUsage: "ROUTER SWITCH CIDR",
				},
				{
					Name:    "show",
					Aliases: []string{"s"},
					Usage:   "show logical router",
					Action:  showRouter,
				},
			},
		},
		// logical router port command
		{
			Name:  "lrp",
			Usage: "operate on logical router port",
			Subcommands: []cli.Command{
				{
					Name:      "add",
					Aliases:   []string{"a"},
					Usage:     "add a new logical router port",
					ArgsUsage: "ROUTER PORT CIDR [MAC] [PEER_PORT]",
					Action:    addRouterPort,
				},
				{
					Name:    "del",
					Aliases: []string{"d"},
					Usage:   "delete a logical router port",
					Action:  delRouterPort,
				},
				{
					Name:    "show",
					Aliases: []string{"s"},
					Usage:   "list one or all logical router ports",
					Action:  showRouterPort,
				},
			},
		},
		// logical static route command
		{
			Name:  "lsr",
			Usage: "operate on logical static route",
			Subcommands: []cli.Command{
				{
					Name:      "add",
					Aliases:   []string{"a"},
					Usage:     "add a new logical static route",
					ArgsUsage: "ROUTER STATIC_ROUTE CIDR NEXT_HOP OUT_PORT",
					Action:    addStaticRoute,
				},
				{
					Name:    "del",
					Aliases: []string{"d"},
					Usage:   "delete a logical static route",
					Action:  delStaticRoute,
				},
				{
					Name:    "show",
					Aliases: []string{"s"},
					Usage:   "list a logical static route",
					Action:  showStaticRoute,
				},
			},
		},
		{
			Name:  "lnat",
			Usage: "operate on logical nat",
			Subcommands: []cli.Command{
				{
					Name:      "add",
					Aliases:   []string{"a"},
					Usage:     "add a new logical NAT",
					ArgsUsage: "ROUTER NAT_NAME CIDR TRANSLATE_TYPE TRANSLATE_IP",
					Action:    addNAT,
				},
				{
					Name:    "del",
					Aliases: []string{"d"},
					Usage:   "delete a logical NAT",
					Action:  delNAT,
				},
				{
					Name:    "show",
					Aliases: []string{"s"},
					Usage:   "list a logical static route",
					Action:  showNAT,
				},
			},
		},
		// logical switch command
		{
			Name:  "ls",
			Usage: "operate on logical switch",
			Subcommands: []cli.Command{
				{
					Name:    "add",
					Aliases: []string{"a"},
					Usage:   "add a new logical switch",
					Action:  addSwitch,
				},
				{
					Name:    "del",
					Aliases: []string{"d"},
					Usage:   "delete a logical switch",
					Flags: []cli.Flag{
						cli.BoolFlag{
							Name:  "recursive, r",
							Usage: "delete logical switch and associated ports",
						},
					},
					Action: delSwitch,
					Before: confirmDelete,
				},
				{
					Name:    "show",
					Aliases: []string{"s"},
					Usage:   "list a logical switch config",
					Action:  showSwitch,
				},
			},
		},
		// logical switch port command
		{
			Name:  "lsp",
			Usage: "operate on logical switch port",
			Subcommands: []cli.Command{
				{
					Name:      "add",
					Aliases:   []string{"a"},
					Usage:     "add a new logical switch port",
					ArgsUsage: "SWITCH PORT IP [MAC] [PEER_PORT]",
					Action:    addSwitchPort,
				},
				{
					Name:    "del",
					Aliases: []string{"d"},
					Usage:   "delete a logical switch port",
					Action:  delSwitchPort,
				},
				{
					Name:    "show",
					Aliases: []string{"s"},
					Usage:   "list a logical switch port",
					Action:  showSwitchPort,
				},
			},
		},
		{
			Name:  "ch",
			Usage: "operate on chassis",
			Subcommands: []cli.Command{
				{
					Name:    "del",
					Aliases: []string{"d"},
					Usage:   "delete a chassis",
					Action:  delChassis,
				},
				{
					Name:    "show",
					Aliases: []string{"s"},
					Usage:   "list a chassis",
					Action:  showChassis,
				},
			},
		},
		{
			Name:  "toolbox",
			Usage: "misc tools",
			Subcommands: []cli.Command{
				{
					Name:  "sync-device-map",
					Usage: "sync device id map within tuplenet",
					Action: func(ctx *cli.Context) (err error) {
						err = controller.SyncDeviceID(true)
						if err != nil {
							fail(err)
						}
						return
					},
				},
				{
					Name:   "find-ip-conflict",
					Usage:  "find ip conflict within a logical router/switch",
					Action: findIPConflict,
				},
				{
					Name:   "find-id-conflict",
					Usage:  "find device id conflict within tuplenet",
					Action: findIDConflict,
				},
			},
		},
	}

	// any error will just panic and we capture it and close the connection before exit
	defer func() {
		if controller != nil {
			controller.Close()
		}
		if r := recover(); r != nil {
			fmt.Println(r)
			os.Exit(1)
		}
	}()

	app.Run(os.Args)
}
