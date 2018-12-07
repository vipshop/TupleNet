package main

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"io/ioutil"
	"net"
	"net/http"
	"regexp"
	"strings"
)

const (
	interfaceAddress = "Address"
	interfaceMac     = "MacAddress"
)

type createEndpointReq struct {
	NetworkID, EndpointID string
	Interface             map[string]string
	Options               map[string]interface{} `json:",omitempty"`
}

type createEndpointResp struct {
	Interface map[string]string `json:",omitempty"`
	Err       string            `json:",omitempty"`
}

type endpointOperInfoReq struct {
	NetworkID, EndpointID string
}

type endpointOperInfoResp struct {
	Value map[string]interface{} `json:",omitempty"`
	Err   string                 `json:",omitempty"`
}

type deleteEndpointReq struct {
	NetworkID, EndpointID string
}

type deleteEndpointResp struct {
	Err string `json:",omitempty"`
}

type joinReq struct {
	NetworkID, EndpointID, SandboxKey string
	Options                           map[string]interface{} `json:",omitempty"`
}

type staticRouteSpec struct {
	Destination string
	RouteType   int
	NextHop     string
}

type joinResp struct {
	InterfaceName struct {
		SrcName, DstPrefix string
	}
	Gateway, GatewayIPv6 string
	StaticRoutes         []staticRouteSpec `json:",omitempty"`
	Err                  string            `json:",omitempty"`
}

type leaveReq struct {
	NetworkID, EndpointID string
}

type leaveResp struct {
	Err string `json:",omitempty"`
}

var (
	gatewaySearcher     = regexp.MustCompile(`"Gateway"\s*:\s*"([\d.]+)"`)
	dockerSockTransport = &http.Transport{
		DialContext: func(_ context.Context, _, _ string) (net.Conn, error) {
			return net.Dial("unix", dockerUnixSock)
		},
		MaxIdleConns: 1,
	}
)

func createEndpoint(w http.ResponseWriter, r *http.Request) {
	var (
		req  createEndpointReq
		resp createEndpointResp
		err  error

		cidr, mac string
		cidrParts []string
		found     bool
		swtch     *logicaldev.Switch
		sport     *logicaldev.SwitchPort
	)

	if err = json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(err.Error()))
		return
	}

	log.Debugf("createEndpoint: got %+v", req)

	if req.EndpointID == "" {
		resp.Err = "empty EndpointID"
		goto Done
	}

	if len(req.Interface) == 0 {
		resp.Err = "request with emtpy endpoint Interface data is not supported"
		goto Done
	}

	if cidr, found = req.Interface[interfaceAddress]; !found || cidr == "" {
		resp.Err = "request without ip address provided is not supported"
		goto Done
	}

	cidrParts = strings.SplitN(cidr, "/", 2)

	if mac, found = req.Interface[interfaceMac]; !found || mac == "" {
		mac = macFromIP(cidrParts[0])
	}

	swtch, err = controller.GetSwitch(req.NetworkID)
	if err != nil {
		resp.Err = err.Error()
		goto Done
	}

	sport = swtch.CreatePort(req.EndpointID, cidrParts[0], mac)
	err = controller.Save(sport)
	if err != nil {
		resp.Err = err.Error()
		goto Done
	}

Done:
	json.NewEncoder(w).Encode(&resp)
	return
}

func deleteEndpoint(w http.ResponseWriter, r *http.Request) {
	var (
		req  deleteEndpointReq
		resp deleteEndpointResp
		err  error

		swtch *logicaldev.Switch
		sport *logicaldev.SwitchPort
	)

	if err = json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(err.Error()))
		return
	}

	log.Debugf("deleteEndpoint: got %+v", req)

	if req.EndpointID == "" {
		resp.Err = "empty EndpointID"
		err = errors.New(resp.Err)
		goto Done
	}

	swtch, err = controller.GetSwitch(req.NetworkID)
	if err != nil {
		resp.Err = err.Error()
		goto Done
	}

	sport, err = controller.GetSwitchPort(swtch, req.EndpointID)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		resp.Err = err.Error()
		goto Done
	} else {
		err = controller.Delete(false, sport)
		if err != nil {
			resp.Err = err.Error()
			goto Done
		}
	}

Done:
	json.NewEncoder(w).Encode(&resp)
	return
}

func endpointOperInfo(w http.ResponseWriter, r *http.Request) {
	var (
		req  endpointOperInfoReq
		resp endpointOperInfoResp

		swtch       *logicaldev.Switch
		sport       *logicaldev.SwitchPort
		sandboxVeth string
		bridgeVeth  string
		err         error
	)

	if err = json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(err.Error()))
		return
	}

	log.Debugf("endpointOperInfo: got %+v", req)

	if req.NetworkID == "" || req.EndpointID == "" {
		resp.Err = "empty NetworkID or EndpointID"
		goto Done
	}

	swtch, err = controller.GetSwitch(req.NetworkID)
	if err != nil {
		resp.Err = err.Error()
		goto Done
	}

	sport, err = controller.GetSwitchPort(swtch, req.EndpointID)
	if err != nil {
		resp.Err = err.Error()
		goto Done
	}

	sandboxVeth, bridgeVeth = vethPairNamesFrom(req.EndpointID)

	resp.Value = map[string]interface{}{
		"IPv4Address": sport.IP,
		"MACAddress":  sport.MAC,
		"LocalVeth":   sandboxVeth,
		"PeerVeth":    bridgeVeth,
	}

Done:
	json.NewEncoder(w).Encode(&resp)
	return
}

func gatewayFromDocker(networkID string) (gateway string) {
	client := http.Client{Transport: dockerSockTransport}
	resp, err := client.Get(fmt.Sprintf("http://placeholder/networks/%s", networkID))
	if err != nil {
		log.Warnf("unable to get gateway from docker for network %s, network creation logic shall enforced a gateway, bug?: %v",
			networkID, err)
		return
	}
	defer resp.Body.Close()

	data, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		log.Warnf("unable to get gateway from docker for network %s, : %v", networkID, err)
		return
	}

	if resp.StatusCode != http.StatusOK {
		log.Warnf("unable to get gateway from docker for network %s, : %v", networkID, string(data))
		return
	}

	result := gatewaySearcher.FindSubmatch(data)
	if len(result) >= 2 {
		gateway = string(result[1])
	} else {
		log.Warnf("no gateway is provided when network %s is created", networkID)
	}

	return
}

func join(w http.ResponseWriter, r *http.Request) {
	var (
		req  joinReq
		resp joinResp

		swtch       *logicaldev.Switch
		sport       *logicaldev.SwitchPort
		sandboxVeth string
		bridgeVeth  string
		err         error
	)

	if err = json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(err.Error()))
		return
	}

	log.Debugf("join: got %+v", req)

	if req.NetworkID == "" || req.EndpointID == "" {
		resp.Err = "empty NetworkID or EndpointID"
		goto Done
	}

	swtch, err = controller.GetSwitch(req.NetworkID)
	if err != nil {
		resp.Err = err.Error()
		goto Done
	}

	sport, err = controller.GetSwitchPort(swtch, req.EndpointID)
	if err != nil {
		resp.Err = err.Error()
		goto Done
	}

	sandboxVeth, bridgeVeth = vethPairNamesFrom(req.EndpointID)
	err = createVethPair(req.EndpointID, sandboxVeth, bridgeVeth, sport.MAC)
	if err != nil {
		resp.Err = err.Error()
		goto Done
	}

	resp.InterfaceName.DstPrefix = "eth"
	resp.InterfaceName.SrcName = sandboxVeth
	resp.Gateway = gatewayFromDocker(req.NetworkID)

Done:
	json.NewEncoder(w).Encode(&resp)
	return
}

func leave(w http.ResponseWriter, r *http.Request) {
	var (
		req  leaveReq
		resp leaveResp

		sandboxVeth string
		bridgeVeth  string
		err         error
	)

	if err = json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(err.Error()))
		return
	}

	log.Debugf("leave: got %+v", req)

	if req.NetworkID == "" || req.EndpointID == "" {
		resp.Err = "empty NetworkID or EndpointID"
		goto Done
	}

	sandboxVeth, bridgeVeth = vethPairNamesFrom(req.EndpointID)
	err = deleteVethPair(sandboxVeth, bridgeVeth)
	if err != nil {
		resp.Err = err.Error()
		goto Done
	}

Done:
	json.NewEncoder(w).Encode(&resp)
	return
}
