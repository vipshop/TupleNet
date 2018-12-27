package main

import (
	"fmt"
	"github.com/vipshop/tuplenet/control/controllers/bookkeeping"
	"gopkg.in/urfave/cli.v1"
	"strings"
)

func syncDeviceID(ctx *cli.Context) (err error) {
	checkArgsThenConnect(ctx, 0, 0,"no parameters required")
	err = controller.SyncDeviceID(true)
	if err != nil {
		fail(err)
	}
	fmt.Println("done")
	return
}

func findIPConflict(ctx *cli.Context) {
	checkArgsThenConnect(ctx, 0, 0,"no parameters required")

	var errMsgs []string
	if routers, err := controller.GetRouters(); err != nil {
		errMsgs = append(errMsgs, err.Error())
	} else {
		for _, router := range routers {
			if ports, err := controller.GetRouterPorts(router); err != nil {
				errMsgs = append(errMsgs, err.Error())
			} else {
				ips := make(map[string]string)
				for _, port := range ports {
					if name, found := ips[port.IP]; found {
						errMsgs = append(errMsgs, fmt.Sprintf("in %s, %s use the same IP as %s: %s",
							router.Name, name, port.Name, port.IP))
					} else {
						ips[port.IP] = port.Name
					}
				}
			}
		}
	}

	if switches, err := controller.GetSwitches(); err != nil {
		errMsgs = append(errMsgs, err.Error())
	} else {
		for _, swtch := range switches {
			if ports, err := controller.GetSwitchPorts(swtch); err != nil {
				errMsgs = append(errMsgs, err.Error())
			} else {
				ips := make(map[string]string)
				for _, port := range ports {
					if name, found := ips[port.IP]; found {
						errMsgs = append(errMsgs, fmt.Sprintf("in %s, %s use the same IP as %s: %s",
							swtch.Name, name, port.Name, port.IP))
					} else {
						ips[port.IP] = port.Name
					}
				}
			}
		}
	}

	if len(errMsgs) != 0 {
		fail(strings.Join(errMsgs, "\n"))
	}

	fmt.Println("looks good!")
}

func findIDConflict(ctx *cli.Context) {
	checkArgsThenConnect(ctx, 0, 0,"no parameters required")

	var (
		errMsgs   []string
		deviceIds map[uint32]string
	)

	routers, err := controller.GetRouters()
	if err != nil {
		fail(errMsgs, err.Error())
	}

	switches, err := controller.GetSwitches()
	if err != nil {
		fail(errMsgs, err.Error())
	}

	deviceIds = make(map[uint32]string, len(routers)+len(switches))

	for _, r := range routers {
		if name, found := deviceIds[r.ID]; found {
			errMsgs = append(errMsgs, fmt.Sprintf("%s has the same id of %s: %d\n",
				r.Name, name, r.ID))
		} else {
			deviceIds[r.ID] = r.Name
		}
	}

	for _, s := range switches {
		if name, found := deviceIds[s.ID]; found {
			errMsgs = append(errMsgs, fmt.Sprintf("%s has the same id of %s: %d\n",
				s.Name, name, s.ID))
		} else {
			deviceIds[s.ID] = s.Name
		}
	}

	if len(errMsgs) != 0 {
		fail(strings.Join(errMsgs, "\n"))
	}

	fmt.Println("looks good!")
}

func rebuildIPBooks(ctx *cli.Context) (err error) {
	checkArgsThenConnect(ctx, 0, 0,"no parameters required")
	err = controller.RebuildIPBooks()
	if err != nil {
		fail(err)
	}
	fmt.Println("done")
	return
}

func decodeIDString(ctx *cli.Context) {
	input := ctx.Args().Get(0)

	u32ToIP := func(i uint32) string {
		return fmt.Sprintf("%d.%d.%d.%d",
			0xFF & i >> 24,0xFF & (i >> 16),0xFF & (i >> 8),0xFF & i)
	}

	for iter := bookkeeping.NewIDMap(input).Iterator();iter.HasNext(); {
		i := iter.Next()
		fmt.Printf("%d => %s\n", i, u32ToIP(i))
	}
}
