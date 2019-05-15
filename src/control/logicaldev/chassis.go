package logicaldev

type Chassis struct {
	Name string `json:"name"`
	IP   string `tn:"ip" json:"ip"`
	Tick uint64 `tn:"tick" json:"tick"`
}

func (ptr *Chassis) dummy() {}
