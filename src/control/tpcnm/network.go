package main

import (
	"encoding/json"
	"fmt"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"net/http"
	"strconv"
	"strings"
)

type ipSpec struct {
	AddressSpace, Gateway string
	AuxAddresses          map[string]string
}

type createNetworkReq struct {
	NetworkID string
	IPv4Data  []ipSpec
	IPv6Data  []ipSpec
	Options   map[string]interface{}
}

type createNetworkResp struct {
	Err string `json:",omitempty"`
}

type deleteNetworkReq struct {
	NetworkID string
}

type deleteNetworkResp struct {
	Err string `json:",omitempty"`
}

func portNameByPeer(name string) string {
	return "to_" + name
}

func createNetwork(w http.ResponseWriter, r *http.Request) {
	var (
		req  createNetworkReq
		resp createNetworkResp
		err  error

		cidrParts []string
		prefix    uint64
		mac       string

		devices []logicaldev.Device
		router  *logicaldev.Router
		sw      *logicaldev.Switch
		rport   *logicaldev.RouterPort
		sport   *logicaldev.SwitchPort
	)

	if err = json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(err.Error()))
		return
	}

	log.Debugf("createNetwork: got %+v", req)

	if req.NetworkID == "" {
		resp.Err = "empty NetworkID"
		goto Done
	}

	if len(req.IPv4Data) == 0 {
		resp.Err = "no ip v4 data provided"
		goto Done
	}

	sw = logicaldev.NewSwitch(req.NetworkID)
	devices = append(devices, sw)

	if egressRouterName != "" {
		cidrParts = strings.SplitN(req.IPv4Data[0].Gateway, "/", 2)
		if len(cidrParts) != 2 {
			resp.Err = fmt.Sprintf("unable to parse IPv4 CIDR address %s", req.IPv4Data[0].Gateway)
			goto Done
		}

		prefix, err = strconv.ParseUint(cidrParts[1], 10, 8)
		if err != nil {
			resp.Err = fmt.Sprintf("unable to parse IPv4 CIDR address %s", req.IPv4Data[0].Gateway)
			goto Done
		}

		router, err = controller.GetRouter(egressRouterName)
		if err != nil {
			resp.Err = err.Error()
			goto Done
		}

		mac = etcd3.MacFromIP(cidrParts[0])
		rport = router.CreatePort(portNameByPeer(req.NetworkID), cidrParts[0], uint8(prefix), mac)
		sport = sw.CreatePort(portNameByPeer(router.Name), cidrParts[0], mac)
		rport.Link(sport)

		devices = append(devices, sport, rport)
	}

	err = controller.Save(devices...)
	if err != nil {
		resp.Err = err.Error()
		goto Done
	}

Done:

	json.NewEncoder(w).Encode(&resp)
	return
}

func deleteNetwork(w http.ResponseWriter, r *http.Request) {
	var (
		req  deleteNetworkReq
		resp deleteNetworkResp
		err  error

		router *logicaldev.Router
		swtch  *logicaldev.Switch
		rport  *logicaldev.RouterPort

		devices []logicaldev.Device
	)

	if err = json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(err.Error()))
		return
	}

	log.Debugf("deleteNetwork: got %+v", req)

	swtch, err = controller.GetSwitch(req.NetworkID)
	if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
		resp.Err = err.Error()
		goto Done
	} else {
		devices = append(devices, swtch)
	}

	if egressRouterName != "" {
		router, err = controller.GetRouter(egressRouterName)
		if err != nil {
			resp.Err = err.Error()
			goto Done
		}

		rport, err = controller.GetRouterPort(router, portNameByPeer(req.NetworkID))
		if err != nil && errors.Cause(err) != etcd3.ErrKeyNotFound {
			resp.Err = err.Error()
			goto Done
		}

		devices = append(devices, rport)
	}

	err = controller.Delete(true, devices...)
	if err != nil {
		resp.Err = err.Error()
		goto Done
	}

Done:
	json.NewEncoder(w).Encode(&resp)
	return
}
