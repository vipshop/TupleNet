package api

import (
	"net/http"
)

func (b *TuplenetAPI) Version() {
	var m Info
	var res Response
	m.GitCommit = "v1.0"
	m.Version = "v1.0"
	m.BuildTime = "2019-06-10"

	res.Code = http.StatusOK
	res.Message = m
	b.Data["json"] = res
	b.ServeJSON()

}

type Info struct {
	GitCommit string
	Version   string
	BuildTime string
}
