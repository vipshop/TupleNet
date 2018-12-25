package logicaldev

type Switch struct {
	Name string `json:"name"`
	ID   uint32 `tn:"id" json:"id"`
}

type SwitchPort struct {
	Name               string `json:"name"`
	IP                 string `tn:"ip" json:"ip"`
	MAC                string `tn:"mac" json:"mac"`
	PeerRouterPortName string `tn:"peer,omitempty" json:"peer,omitempty"`
	Chassis            string `tn:"chassis,omitempty" json:"chassis,omitempty"`

	Owner *Switch
}

func (ptr *Switch) CreatePort(name, ip string, mac string) *SwitchPort {
	return &SwitchPort{
		Name:  name,
		IP:    ip,
		MAC:   mac,
		Owner: ptr,
	}
}
