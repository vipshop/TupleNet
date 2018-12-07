package logicaldev

type Router struct {
	Name    string `json:"name"`
	ID      uint32 `tn:"id" json:"id"`
	Chassis string `tn:"chassis,omitempty" json:"chassis,omitempty"`
}

type RouterPort struct {
	Name               string `json:"name"`
	IP                 string `tn:"ip" json:"ip"`
	Prefix             uint8  `tn:"prefix" json:"prefix"`
	MAC                string `tn:"mac" json:"mac"`
	PeerSwitchPortName string `tn:"peer" json:"peer"`

	Owner *Router
}

type StaticRoute struct {
	Name    string `json:"name"`
	IP      string `tn:"ip" json:"ip"`
	Prefix  uint8  `tn:"prefix" json:"prefix"`
	NextHop string `tn:"next_hop" json:"next_hop"`
	OutPort string `tn:"outport" json:"outport"`

	Owner *Router
}

type NAT struct {
	Name          string `json:"name"`
	IP            string `tn:"ip" json:"ip"`
	Prefix        uint8  `tn:"prefix" json:"prefix"`
	TranslateType string `tn:"xlate_type" json:"xlate_type"`
	TranslateIP   string `tn:"xlate_ip" json:"xlate_ip"`

	Owner *Router
}

func (ptr *Router) CreatePort(name, ip string, prefix uint8, mac string) *RouterPort {
	return &RouterPort{
		Name:   name,
		IP:     ip,
		Prefix: prefix,
		MAC:    mac,
		Owner:  ptr,
	}
}

func (ptr *Router) CreateStaticRoute(name, ip string, prefix uint8, nextHop, outRouterPort string) *StaticRoute {
	return &StaticRoute{
		Name:    name,
		IP:      ip,
		Prefix:  prefix,
		NextHop: nextHop,
		OutPort: outRouterPort,
		Owner:   ptr,
	}
}

func (ptr *RouterPort) Link(target *SwitchPort) {
	ptr.PeerSwitchPortName = target.Name
	target.PeerRouterPortName = ptr.Name
}

func (ptr *Router) CreateNAT(name, ip string, prefix uint8, xlateType, xlateIP string) *NAT {
	return &NAT{
		Name:          name,
		IP:            ip,
		Prefix:        prefix,
		TranslateType: xlateType,
		TranslateIP:   xlateIP,
		Owner:         ptr,
	}
}
