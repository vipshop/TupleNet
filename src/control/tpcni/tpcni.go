package main

import (
	"encoding/json"
	"fmt"
	"github.com/containernetworking/cni/pkg/skel"
	"github.com/containernetworking/cni/pkg/types"
	"github.com/containernetworking/cni/pkg/types/current"
	"github.com/containernetworking/cni/pkg/version"
	"github.com/containernetworking/plugins/pkg/ip"
	"github.com/containernetworking/plugins/pkg/ns"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"github.com/vishvananda/netlink"
	"net"
	"os/exec"
	"strings"
)

var ErrOVSPortNotFound = errors.New("ovsport not found")

const defaultBrName = "br-int"
const defaultPrefixPath = "/tuplenet"

type pluginConf struct {
	types.NetConf
	MTU             int    `json:"mtu"`
	SwitchName      string `json:"switchname"`
	SubNet          string `json:"subnet"`
	EtcdCluster     string `json:"etcd_cluster"`
	DataStorePrefix string `json:"data_store_prefix"`
}

func lspName(cid, ifName string) string {
	return fmt.Sprintf("lsp-%s-%s", ifName, cid)
}

func parseConfig(bytes []byte) (*pluginConf, string, error) {
	cfg := &pluginConf{
		DataStorePrefix: defaultPrefixPath,
	}
	if err := json.Unmarshal(bytes, cfg); err != nil {
		return nil, "", fmt.Errorf("failed to parse pluginConfig: %v", err)
	}
	return cfg, cfg.CNIVersion, nil
}

func sanityCheck(cfg *pluginConf, args *skel.CmdArgs) error {
	if cfg.EtcdCluster == "" || cfg.DataStorePrefix == "" {
		return fmt.Errorf("etcd3 cluster or data store prefix is empty")
	}

	if _, _, err := net.ParseCIDR(cfg.SubNet); err != nil {
		return err
	}

	return nil
}

func ovsvsctl(args ...string) (string, error) {
	args = append([]string{"--timeout=5"}, args...)
	output, err := exec.Command("ovs-vsctl", args...).CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to run 'ovs-vsctl %s': %v\n  %s", strings.Join(args, " "), err, string(output))
	}

	return string(output), nil
}

func addOvsPort(portName, ifaceID string) error {
	_, err := ovsvsctl("add-port", defaultBrName, portName, "--", "set",
		"interface", portName, fmt.Sprintf("external_ids:iface-id=%s", ifaceID))
	if err != nil {
		return fmt.Errorf("failed to add port %s in %s: %v",
			portName, defaultBrName, err)
	}
	return nil
}

func findOvsportByIfaceID(ifaceID string) (string, error) {
	output, err := ovsvsctl("--no-heading", "--columns=name", "find", "interface",
		fmt.Sprintf("external_ids:iface-id=%s", ifaceID))
	if err != nil {
		return "", fmt.Errorf("failed to get ovsport by iface-id:%s: %v", ifaceID, err)
	}
	name := strings.Replace(output, "\"", "", -1)
	if name == "" {
		return "", errors.Wrap(ErrOVSPortNotFound,
			fmt.Sprintf("no iface record has iface-id:%s", ifaceID))
	}
	return strings.TrimSpace(name), nil
}

func delOvsPortByIfaceID(ifaceID string) error {
	portName, err := findOvsportByIfaceID(ifaceID)
	if err != nil {
		return errors.Wrap(err, fmt.Sprintf("failed to delete ovsport by iface-id:%s", ifaceID))
	}
	return delOvsPort(portName)
}

func delOvsPort(portName string) error {
	_, err := ovsvsctl("del-port", portName)
	if err != nil {
		return fmt.Errorf("failed to del port %s in %s: %v",
			portName, defaultBrName, err)
	}
	return nil
}

func setupVeth(netns ns.NetNS, ifaceID string,
	ifName string, ipAddr string,
	mac string, gw net.IP,
	mtu int) (*current.Interface, *current.Interface, error) {

	cIface := &current.Interface{}
	peerIface := &current.Interface{}
	hwAddr, err := net.ParseMAC(mac)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to parse mac:%s", mac)
	}

	addr, err := netlink.ParseAddr(ipAddr)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to parse ip:%s: %v", ipAddr, err)
	}

	err = netns.Do(func(hostNS ns.NetNS) error {
		peerVeth, cVeth, err := ip.SetupVeth(ifName, mtu, hostNS)
		if err != nil {
			return err
		}
		cIface.Name = cVeth.Name
		cIface.Sandbox = netns.Path()
		peerIface.Name = peerVeth.Name
		peerIface.Mac = peerVeth.HardwareAddr.String()

		clink, err := netlink.LinkByName(cIface.Name)
		if err != nil {
			err = fmt.Errorf("failed to lookup container veth %q: %v",
				cIface.Name, err)
			goto DELETE_VETH
		}

		err = netlink.AddrAdd(clink, addr)
		if err != nil {
			err = fmt.Errorf("failed to add ip %s to %s: %v",
				ipAddr, cIface.Name, err)
			goto DELETE_VETH
		}

		err = netlink.LinkSetHardwareAddr(clink, hwAddr)
		if err != nil {
			err = fmt.Errorf("failed to set mac %s for %s: %v",
				hwAddr.String(), cIface.Name, err)
			goto DELETE_VETH
		}
		cIface.Mac = hwAddr.String()

		// set default gateway
		err = ip.AddRoute(nil, gw, clink)
		if err != nil {
			err = fmt.Errorf("failed to set gw for %s: %v", cIface.Name, err)
			goto DELETE_VETH
		}

		// connect host veth end to the ovs port
		err = addOvsPort(peerIface.Name, ifaceID)
		if err != nil {
			err = fmt.Errorf("failed to add %s in ovs bridge: %v",
				peerIface.Name, err)
			goto DELETE_VETH
		}

		return nil
	DELETE_VETH:
		ip.DelLinkByName(cIface.Name)
		return err

	})
	if err != nil {
		return nil, nil, err
	}

	return peerIface, cIface, nil
}

func prepare(args *skel.CmdArgs) (
	*pluginConf, *etcd3.Controller, *logicaldev.Switch, error) {
	cfg, _, err := parseConfig(args.StdinData)
	if err != nil {
		err = fmt.Errorf("failed to parse config: %v", err)
		return nil, nil, nil, err
	}

	if err := sanityCheck(cfg, args); err != nil {
		err = fmt.Errorf("failed to pass sanity-check: %v", err)
		return nil, nil, nil, err
	}

	controller, err := etcd3.NewController(
		strings.Split(cfg.EtcdCluster, ","),
		cfg.DataStorePrefix,
		true)
	if err != nil {
		err = fmt.Errorf("failed to link to remote etcd:%s: %v",
			cfg.EtcdCluster, err)
		return nil, nil, nil, err
	}

	swtch, err := controller.GetSwitch(cfg.SwitchName)
	if err != nil {
		err = fmt.Errorf("failed to get logical switch %s: %v",
			cfg.SwitchName, err)
		return nil, nil, nil, err
	}
	return cfg, controller, swtch, nil
}

func cmdAdd(args *skel.CmdArgs) error {
	cfg, controller, swtch, err := prepare(args)
	if err != nil {
		return nil
	}

	portName := lspName(args.ContainerID, args.IfName)
	sport, err := controller.GetSwitchPort(swtch, portName)
	if err != nil {
		if errors.Cause(err) == etcd3.ErrKeyNotFound {
			sport = swtch.CreatePort(portName, "0.0.0.0", "00:00:00:00:00:00")
		} else {
			return fmt.Errorf("failed to get remote switch port info: %v", err)
		}
	} else {
		return fmt.Errorf("remote side already get port %s", portName)
	}

	_, ipv4Net, _ := net.ParseCIDR(cfg.SubNet) // sanity func had checked it
	gwIP := ipv4Net.IP.To4()
	gwIP[3]++ // 192.168.10.0 --> 192.168.10.1
	prefix, _ := ipv4Net.Mask.Size()
	err = controller.SaveSwitchPort(sport, ipv4Net.IP.String(), uint8(prefix))
	if err != nil {
		return fmt.Errorf("failed to update lsp %s [ip:%s] to remote: %v",
			portName, sport.IP, err)
	}

	netns, err := ns.GetNS(args.Netns)
	if err != nil {
		return fmt.Errorf("failed to open netns %q: %v", args.Netns, err)
	}
	defer netns.Close()

	cVethIP := fmt.Sprintf("%s/%d", sport.IP, prefix)
	peerIface, cIface, err := setupVeth(netns, portName, args.IfName,
		cVethIP, sport.MAC, gwIP, cfg.MTU)
	if err != nil {
		// delete the switch port we had created in above code
		_ = controller.Delete(true, sport)
		return fmt.Errorf("failed to setup veth pair for container %s: %v",
			args.ContainerID, err)
	}

	result := &current.Result{
		CNIVersion: cfg.CNIVersion,
		Interfaces: []*current.Interface{peerIface, cIface},
		IPs: []*current.IPConfig{
			{
				Version:   "4",
				Interface: current.Int(1),
				Address: net.IPNet{
					IP:   net.ParseIP(sport.IP),
					Mask: ipv4Net.Mask,
				},
				Gateway: gwIP,
			},
		},
	}

	return types.PrintResult(result, cfg.CNIVersion)
}

func cmdDel(args *skel.CmdArgs) error {
	_, controller, swtch, err := prepare(args)
	if err != nil {
		return err
	}

	portName := lspName(args.ContainerID, args.IfName)
	sport, err := controller.GetSwitchPort(swtch, portName)
	if err != nil {
		if errors.Cause(err) != etcd3.ErrKeyNotFound {
			return err
		} else {
			goto DELETE_VETH
		}
	}

	if err = controller.Delete(false, sport); err != nil {
		return fmt.Errorf("failed to delete %s's lsp %s: %v",
			swtch.Name, sport.Name, err)
	}
DELETE_VETH:
	// NOTE: should NOT consume sport, sport maybe nil here
	err = ns.WithNetNSPath(args.Netns, func(_ ns.NetNS) error {
		err := ip.DelLinkByName(args.IfName)
		if err != nil && err == ip.ErrLinkNotFound {
			// don't return an error if the device is already removed.
			return nil
		}
		return err
	})
	if err != nil {
		return fmt.Errorf("failed to delete %s:%s veth pair: %v",
			args.Netns, args.IfName, err)
	}

	err = delOvsPortByIfaceID(portName)
	if err != nil && errors.Cause(err) != ErrOVSPortNotFound {
		return fmt.Errorf("failed to delete logical port %s peer ovs-port: %v", portName, err)
	}
	return nil
}

func main() {
	skel.PluginMain(cmdAdd, cmdDel, version.All)
}
