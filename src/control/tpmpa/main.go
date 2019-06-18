package main

import (
	"github.com/astaxie/beego"
	"github.com/vipshop/tuplenet/control/logger"
)

func main() {
	initRouters()
	logger.Infof("http server Running on 0.0.0.0:80")
	beego.Run("0.0.0.0:80")

}
