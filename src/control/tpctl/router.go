package main

import (
	"fmt"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
	"net"
	"sort"
	"strings"

	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"gopkg.in/urfave/cli.v1"
)

func addRouter(ctx *cli.Context) error {
	checkArgs(ctx, 1, 2, "require a name,  an optional chassis")

	name := ctx.Args().Get(0)
	chassis := ctx.Args().Get(1)

	r, err := controller.CreateRouter(name)
	if err != nil {
		fail(err)
	}

	r.Chassis = chassis

	err = controller.Save(r)
	if err != nil {
		fail(err)
	}

	succeedf("router %s created", name)

	return nil
}

func showRouter(ctx *cli.Context) error {
	checkArgs(ctx, 0, 1, "require at most one name")

	var (
		routers []*logicaldev.Router
		err     error
	)

	if len(ctx.Args()) == 0 { // show all ports
		routers, err = controller.GetRouters()
		if err != nil {
			fail(err)
		}
	} else {
		name := ctx.Args().First()
		router, err := controller.GetRouter(name)
		if err != nil {
			fail(err)
		}

		routers = []*logicaldev.Router{router}
	}

	sort.Slice(routers, func(i, j int) bool { return routers[i].Name < routers[j].Name })
	printDevices(routers)
	return nil
}

func delRouter(ctx *cli.Context) error {
	checkArgs(ctx, 1, 1, "require a name")

	name := ctx.Args().Get(0)
	router, err := controller.GetRouter(name)
	if err != nil {
		fail(err)
	}

	ports, err := controller.GetRouterPorts(router)
	if err != nil {
		failf("unable to get router ports, abort unsafe deletion of %s: %v", name, err)
	}

	srs, err := controller.GetRouterStaticRoutes(router)
	if err != nil {
		failf("unable to get router static route, abort unsafe deletion of %s: %v", name, err)
	}

	if len(ports) != 0 || len(srs) != 0 { // for router with ports and static routes, it depends
		recursive := ctx.Bool("recursive")

		if recursive {
			err := controller.Delete(true, router)
			if err != nil {
				failf("failed to remove %s: %v", name, err)
			}
		} else {
			failf(`failed to delete %s: there are remaining ports or static routes, consider using "-r"?`, name)
		}
	} else {
		err := controller.Delete(false, router)
		if err != nil {
			failf("failed to delete %s: %v", name, err)
		}
	}

	succeedf("%s deleted", name)
	return nil
}

func showStaticRoute(ctx *cli.Context) error {
	checkArgs(ctx, 1, 2, "require a router name and a static route name")

	var (
		routerName string
		routeName  string
		srs        []*logicaldev.StaticRoute
		err        error
	)

	routerName = ctx.Args().Get(0)
	router, err := controller.GetRouter(routerName)
	if err != nil {
		fail(err)
	}

	routeName = ctx.Args().Get(1)
	if routeName == "" { // show all ports
		srs, err = controller.GetRouterStaticRoutes(router)
		if err != nil {
			fail(err)
		}
	} else {
		r, err := controller.GetRouterStaticRoute(router, routeName)
		if err != nil {
			fail(err)
		}

		srs = []*logicaldev.StaticRoute{r}
	}

	sort.Slice(srs, func(i, j int) bool { return srs[i].Name < srs[j].Name })
	printDevices(srs)
	return nil
}

func addStaticRoute(ctx *cli.Context) error {
	checkArgs(ctx, 5, 5, "require router name, static route name, CIDR, next_hop and outport")

	routerName := ctx.Args().Get(0)
	rName := ctx.Args().Get(1)
	cidrStr := ctx.Args().Get(2)
	nextHop := ctx.Args().Get(3)
	outport := ctx.Args().Get(4)

	// perform some early checking, avoid reading db if any error
	ip, prefix := parseCIDR(cidrStr)

	if net.ParseIP(nextHop) == nil {
		failf("invalid next_hop: %s", nextHop)
	}

	router, err := controller.GetRouter(routerName)
	if err != nil {
		fail(err)
	}

	_, err = controller.GetRouterStaticRoute(router, rName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		fail(err)
	}

	if err == nil {
		failf("router %s static route %s exists", routerName, rName)
	}

	r := router.CreateStaticRoute(rName, ip, prefix, nextHop, outport)

	err = controller.Save(r)
	if err != nil {
		fail(err)
	}

	succeedf("router %s static router %s created", routerName, rName)

	return nil
}

func delStaticRoute(ctx *cli.Context) error {
	checkArgs(ctx, 2, 2, "require router name and a static route name")

	routerName := ctx.Args().Get(0)
	rName := ctx.Args().Get(1)

	router, err := controller.GetRouter(routerName)
	if err != nil {
		fail(err)
	}

	r, err := controller.GetRouterStaticRoute(router, rName)
	if err != nil {
		fail(err)
	}

	err = controller.Delete(false, r)
	if err != nil {
		fail(err)
	}

	succeedf("router %s static router %s deleted", routerName, rName)

	return nil
}

func showRouterPort(ctx *cli.Context) error {
	checkArgs(ctx, 1, 2, "require at least router name and optionally a port name")

	var (
		routerName string
		portName   string
		ports      []*logicaldev.RouterPort
		err        error
	)

	routerName = ctx.Args().Get(0)
	router, err := controller.GetRouter(routerName)
	if err != nil {
		fail(err)
	}

	portName = ctx.Args().Get(1)
	if portName == "" { // show all ports
		ports, err = controller.GetRouterPorts(router)
		if err != nil {
			fail(err)
		}
	} else {
		port, err := controller.GetRouterPort(router, portName)
		if err != nil {
			fail(err)
		}

		ports = []*logicaldev.RouterPort{port}
	}

	sort.Slice(ports, func(i, j int) bool { return ports[i].Name < ports[j].Name })
	printDevices(ports)
	return nil
}

func addRouterPort(ctx *cli.Context) error {
	checkArgs(ctx, 3, 5, "require a router name, a port name, an CIDR and optionally a MAC, a peer port")

	routerName := ctx.Args().Get(0)
	portName := ctx.Args().Get(1)
	cidr := ctx.Args().Get(2)
	mac := ctx.Args().Get(3)
	peer := ctx.Args().Get(4)

	ip, prefix := parseCIDR(cidr)
	if mac == "" {
		mac = macFromIP(ip)
	} else {
		validateMAC(mac)
	}

	router, err := controller.GetRouter(routerName)
	if err != nil {
		fail(err)
	}

	_, err = controller.GetRouterPort(router, portName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		fail(err)
	}

	if err == nil {
		failf("router port %s exists", portName)
	}

	port := router.CreatePort(portName, ip, prefix, mac)
	port.PeerSwitchPortName = peer

	err = controller.Save(port)
	if err != nil {
		fail(err)
	}

	succeedf("router %s port %s created", routerName, portName)

	return nil
}

func delRouterPort(ctx *cli.Context) error {
	checkArgs(ctx, 2, 2, "require router name and a port name")

	routerName := ctx.Args().Get(0)
	portName := ctx.Args().Get(1)

	router, err := controller.GetRouter(routerName)
	if err != nil {
		fail(err)
	}

	port, err := controller.GetRouterPort(router, portName)
	if err != nil {
		fail(err)
	}

	err = controller.Delete(false, port)
	if err != nil {
		fail(err)
	}

	succeedf("router %s port %s deleted", routerName, portName)

	return nil
}

func linkSwitch(ctx *cli.Context) error {
	checkArgs(ctx, 3, 3, "require a router, a switch name and a CIDR string of: 10.0.0.1/24")

	// perform some early checking, avoid reading db if any error
	cidr, mac := ctx.Args().Get(2), ctx.Args().Get(3)

	ip, prefix := parseCIDR(cidr)
	if mac == "" {
		mac = macFromIP(ip)
	} else {
		validateMAC(mac)
	}

	routerName := ctx.Args().Get(0)
	router, err := controller.GetRouter(routerName)
	if err != nil {
		fail(err)
	}

	switchName := ctx.Args().Get(1)
	swtch, err := controller.GetSwitch(switchName)
	if err != nil {
		fail(err)
	}

	spName := switchName + "_to_" + routerName
	_, err = controller.GetSwitchPort(swtch, spName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		fail(err)
	}
	if err == nil {
		failf("switch port %s exists", spName)
	}

	rpName := routerName + "_to_" + switchName
	_, err = controller.GetRouterPort(router, rpName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		fail(err)
	}
	if err == nil {
		failf("router port %s exists", rpName)
	}

	sp := swtch.CreatePort(spName, ip, mac)
	rp := router.CreatePort(rpName, ip, prefix, mac)
	rp.Link(sp)

	err = controller.Save(sp, rp)
	if err != nil {
		fail(err)
	}

	fmt.Printf("%s linked to %s\n", router.Name, swtch.Name)
	return nil
}

func addNAT(ctx *cli.Context) error {
	checkArgs(ctx, 5, 5, "require router, NAT name, CIDR TRANSLATE_TYPE and TRANSLATE_IP")

	routerName := ctx.Args().Get(0)
	natName := ctx.Args().Get(1)
	cidr := ctx.Args().Get(2)
	xlateType := strings.ToLower(ctx.Args().Get(3))
	xlateIP := strings.ToLower(ctx.Args().Get(4))

	ip, prefix := parseCIDR(cidr)

	if xlateType != "snat" && xlateType != "dnat" {
		failf("invalid translate type, must be snat/dnat: %s", xlateType)
	}

	if net.ParseIP(xlateIP) == nil {
		failf("invalid translate IP: %s", xlateIP)
	}

	router, err := controller.GetRouter(routerName)
	if err != nil {
		fail(err)
	}

	_, err = controller.GetRouterNAT(router, natName)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		fail(err)
	}

	if err == nil {
		failf("router NAT %s exists", natName)
	}

	nat := router.CreateNAT(natName, ip, prefix, xlateType, xlateIP)
	err = controller.Save(nat)
	if err != nil {
		fail(err)
	}

	succeedf("router %s NAT %s created", routerName, natName)

	return nil
}

func delNAT(ctx *cli.Context) error {
	checkArgs(ctx, 2, 2, "require router, NAT name")

	routerName := ctx.Args().Get(0)
	natName := ctx.Args().Get(1)

	router, err := controller.GetRouter(routerName)
	if err != nil {
		fail(err)
	}

	port, err := controller.GetRouterNAT(router, natName)
	if err != nil {
		fail(err)
	}

	err = controller.Delete(false, port)
	if err != nil {
		fail(err)
	}

	succeedf("router %s NAT %s deleted", routerName, natName)

	return nil
}

func showNAT(ctx *cli.Context) error {
	checkArgs(ctx, 1, 2, "require router and optionally NAT name")

	var (
		routerName string
		natName    string
		nats       []*logicaldev.NAT
		err        error
	)

	routerName = ctx.Args().Get(0)
	router, err := controller.GetRouter(routerName)
	if err != nil {
		fail(err)
	}

	natName = ctx.Args().Get(1)
	if natName == "" { // show all nats
		nats, err = controller.GetRouterNATs(router)
		if err != nil {
			fail(err)
		}
	} else {
		nat, err := controller.GetRouterNAT(router, natName)
		if err != nil {
			fail(err)
		}

		nats = []*logicaldev.NAT{nat}
	}

	sort.Slice(nats, func(i, j int) bool { return nats[i].Name < nats[j].Name })
	printDevices(nats)
	return nil
}
