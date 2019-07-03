package main

import (
	"os"
	"net/http"
	"github.com/astaxie/beego"
	"github.com/vipshop/tuplenet/control/logger"
	"github.com/vipshop/tuplenet/control/api"
	"github.com/astaxie/beego/context"
	"encoding/json"
)

func initRouters() {

	beego.InsertFilter("*", beego.BeforeExec, func(ctx *context.Context) {
		if ctx.Input.IsGet() { // don't authorize for GET method
			return
		}
		auth := os.Getenv("AUTH_STRING")
		if len(auth) == 0 {
			logger.Warnf("tpmpa skipped auth")
			return
		}

		rejectRequest := func(status int, message []byte) {
			ctx.Output.SetStatus(status)
			ctx.Output.Body(message)
		}

		token := ctx.Input.Header("X-TUPLENET-AUTH")
		if len(token) == 0 || token != auth {
			res := make(map[string]interface{})
			logger.Errorf("auth failed %s", token)
			res["Code"] = http.StatusUnauthorized
			res["Message"] = "auth failed"
			result, _ := json.Marshal(res)
			rejectRequest(200, result)
			return
		}

	}, false)

	beego.Router("/api/v1/route_add", &api.TuplenetAPI{}, "post:AddRoute")
	beego.Router("/api/v1/route_show", &api.TuplenetAPI{}, "get:ShowRouter")
	beego.Router("/api/v1/route_del", &api.TuplenetAPI{}, "post:DelRouter")
	beego.Router("/api/v1/link_switch", &api.TuplenetAPI{}, "post:LinkSwitch")
	beego.Router("/api/v1/route_port_add", &api.TuplenetAPI{}, "post:AddRouterPort")
	beego.Router("/api/v1/route_port_show", &api.TuplenetAPI{}, "get:ShowRouterPort")
	beego.Router("/api/v1/route_port_del", &api.TuplenetAPI{}, "post:DelRouterPort")
	beego.Router("/api/v1/route_static_add", &api.TuplenetAPI{}, "post:AddStaticRoute")
	beego.Router("/api/v1/route_static_show", &api.TuplenetAPI{}, "get:ShowStaticRoute")
	beego.Router("/api/v1/route_static_del", &api.TuplenetAPI{}, "post:DelStaticRoute")
	beego.Router("/api/v1/route_nat_add", &api.TuplenetAPI{}, "post:AddNAT")
	beego.Router("/api/v1/route_nat_show", &api.TuplenetAPI{}, "get:ShowNAT")
	beego.Router("/api/v1/route_nat_del", &api.TuplenetAPI{}, "post:DelNAT")
	beego.Router("/api/v1/switch_add", &api.TuplenetAPI{}, "post:AddSwitch")
	beego.Router("/api/v1/switch_show", &api.TuplenetAPI{}, "get:ShowSwitch")
	beego.Router("/api/v1/switch_del", &api.TuplenetAPI{}, "post:DelSwitch")
	beego.Router("/api/v1/switch_port_add", &api.TuplenetAPI{}, "post:AddSwitchPort")
	beego.Router("/api/v1/switch_port_show", &api.TuplenetAPI{}, "get:ShowSwitchPort")
	beego.Router("/api/v1/switch_port_del", &api.TuplenetAPI{}, "post:DelSwitchPort")
	beego.Router("/api/v1/edge_init", &api.TuplenetAPI{}, "post:InitEdge")
	beego.Router("/api/v1/edge_add", &api.TuplenetAPI{}, "post:AddEdge")
	beego.Router("/api/v1/edge_del", &api.TuplenetAPI{}, "post:DelEdge")
	beego.Router("/api/v1/patch_port_add", &api.TuplenetAPI{}, "post:AddPatchPort")
	beego.Router("/api/v1/chassis_show", &api.TuplenetAPI{}, "get:ShowChassis")
	beego.Router("/api/v1/chassis_del", &api.TuplenetAPI{}, "post:DelChassis")
	logger.Infof("init routers finish")
}
