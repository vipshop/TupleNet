package main

import (
	"github.com/pkg/errors"
	"os/exec"
)

const (
	tuplenetBridge = "br-int"
)

func vethPairNamesFrom(src string) (sandbox string, bridge string) {
	// linux network interface limitation is 15 bytes + \0
	var maxSize = 13
	if len(src) < maxSize {
		maxSize = len(src)
	}

	// rarely collide?
	sandbox, bridge = src[:maxSize]+"s", src[:maxSize]+"b"
	return
}

func createVethPair(endpointID, sandboxVeth, bridgeVeth, sandboxMAC string) error {
	var (
		cmd        *exec.Cmd
		err        error
		revertCmds []*exec.Cmd
		output     []byte
	)

	defer func() {
		if err != nil {
			for i := len(revertCmds) - 1; i > 0; i-- {
				revertCmds[i].CombinedOutput()
			}
		}
	}()

	cmd = exec.Command("ip",
		[]string{"link", "add", sandboxVeth, "type", "veth", "peer", "name", bridgeVeth}...)
	output, err = cmd.CombinedOutput()
	if err != nil {
		goto Done
	}
	// TODO: test if need ip link down before removal
	revertCmds = append(revertCmds, exec.Command("ip",
		[]string{"link", "del", "dev", sandboxVeth, "type", "veth"}...))
	revertCmds = append(revertCmds, exec.Command("ip",
		[]string{"link", "del", "dev", bridgeVeth, "type", "veth"}...))

	cmd = exec.Command("ip", []string{"link", "set", "dev", sandboxVeth, "address", sandboxMAC}...)
	output, err = cmd.CombinedOutput()
	if err != nil {
		goto Done
	}

	cmd = exec.Command("ip", []string{"link", "set", bridgeVeth, "up"}...)
	output, err = cmd.CombinedOutput()
	if err != nil {
		goto Done
	}

	cmd = exec.Command("ovs-vsctl", []string{"add-port", tuplenetBridge, bridgeVeth}...)
	output, err = cmd.CombinedOutput()
	if err != nil {
		goto Done
	}

	cmd = exec.Command("ovs-vsctl", []string{"set", "interface", bridgeVeth, "external_ids:iface-id=" + endpointID}...)
	output, err = cmd.CombinedOutput()
	if err != nil {
		goto Done
	}

	return nil

Done:
	return errors.Errorf("unable to create veth pair: sandbox %s, bridge %s: %s",
		sandboxVeth, bridgeVeth, string(output))
}

func deleteVethPair(sandboxVeth, bridgeVeth string) error {
	var (
		cmd    *exec.Cmd
		err    error
		output []byte
	)

	cmd = exec.Command("ip", []string{"link", "del", "dev", bridgeVeth, "type", "veth"}...)
	output, err = cmd.CombinedOutput()
	if err != nil {
		log.Warnf("unable to remove %s: %s", bridgeVeth, string(output))
	}

	cmd = exec.Command("ovs-vsctl", []string{"del-port", tuplenetBridge, bridgeVeth}...)
	output, err = cmd.CombinedOutput()
	if err != nil {
		log.Warnf("unable to remove %s from ovs: %s", bridgeVeth, string(output))
	}

	return nil
}
