package api

import (
	"os"
	"github.com/astaxie/beego"
	"github.com/vipshop/tuplenet/control/logger"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
)

var (
	controller    *etcd3.Controller
	etcdHost      string
	etcdPrefix    string
	edgeShellPath string
)

// set auth string
const (
	defaultEtcdpoints    = "127.0.0.1:2379"
	defaultEtcdPrefix    = "/tuplenet"
	defaultEdgeShellPath = "src/tuplenet/tools/edge-operate.py"
)

func init() {
	var err error
	etcdHost = os.Getenv("ETCD_HOSTS")
	if etcdHost == "" {
		etcdHost = defaultEtcdpoints
	}
	etcdPrefix = os.Getenv("ETCD_PREFIX")
	if etcdPrefix == "" {
		etcdPrefix = defaultEtcdPrefix
	}
	if controller, err = etcd3.NewController([]string{etcdHost}, etcdPrefix, false); err != nil {
		logger.Errorf("init connect etcd service failed %s", err)
		return
	}
	edgeShellPath = os.Getenv("EDGE_SHELL_PATH")
	if edgeShellPath == "" {
		edgeShellPath = defaultEdgeShellPath
	}
}

func EdgeEtcdPrefix(etcdPrefix string) string {
	var preFixArg string
	if etcdPrefix == defaultEtcdPrefix {
		preFixArg = "--prefix=" + etcdPrefix + "/"
	} else {
		preFixArg = "--prefix=" + etcdPrefix
	}
	return preFixArg
}

type TuplenetAPI struct {
	beego.Controller
}

type EdgeRequest struct {
	PhyBr string `json:phyBr`
	Inner string `json:inner`
	Virt  string `json:virt`
	ExtGw string `json:extGw`
	Vip   string `json:vip`
}

type RouteStaticRequest struct {
	Route   string `json:route`             // route name
	RName   string `json:"rName,omitempty"` // to_outside7  to_ext_world7
	Cidr    string `json:"cidr,omitempty"`  // CIDR 0.0.0.0/24
	NextHop string `json:"nextHop,omitempty"`
	OutPort string `json:"outPort,omitempty"` // LR-central_to_m7 LR-edge7_to_outside7
}

type RouteRequest struct {
	Route     string `json:route` // route name
	Chassis   string `json:"chassis,omitempty"`
	Switch    string `json:"switch,omitempty"`    // switch name
	Cidr      string `json:"cidr,omitempty"`      // CIDR 0.0.0.0/24
	All       bool   `josn:"all,omitempty"`       // get all route port message
	Recursive bool   `json:"recursive,omitempty"` // force delete all ports and route
	PortName  string `json:"portName,omitempty"`
	Mac       string `json:"mac,omitempty"`
	Peer      string `json:"peer,omitempty"`
}

type NetRequest struct {
	Route     string `json:route` // route name
	NatName   string `json:natName`
	Cidr      string `json:"cidr,omitempty"`
	XlateType string `json:"xlateType,omitempty"` // snat or dnat
	XlateIP   string `json:"xlateIP,omitempty"`   // snat or dnat ip
}

type SwitchRequest struct {
	Switch    string `json:switch`
	Recursive bool   `json:"recursive,omitempty"` // force delete all ports and switch
}

type SwitchPortRequest struct {
	Switch   string `json:switch`
	PortName string `json:"portName,omitempty"`
	IP       string `json:"ip,omitempty"`
	Peer     string `json:"peer,omitempty"`
	Mac      string `json:"mac,omitempty"`
}

type Response struct {
	Code    int         `json:code`
	Message interface{} `json:message`
}
