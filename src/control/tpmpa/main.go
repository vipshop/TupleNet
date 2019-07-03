package main

import (
	"github.com/astaxie/beego"
	"github.com/vipshop/tuplenet/control/logger"
	"os"
	"fmt"
)

var (
	version   string
	commit    string
	buildTime string
)

func main() {
	args := os.Args
	if len(args) == 2 && (args[1] == "--version" || args[1] == "-v") {
		fmt.Printf(getVersion())
		return
	}
	initRouters()
	logger.Infof("http server Running on 0.0.0.0:80")
	beego.Run("0.0.0.0:80")

}

func getVersion() string {
	if CheckNilParam(version) {
		version = "untagged"
	}
	if CheckNilParam(commit) {
		commit = "undefined"
	}
	if CheckNilParam(buildTime) {
		buildTime = "unknown"
	}
	return fmt.Sprintf("Version: %s\n", version) +
		fmt.Sprintf("GitCommit: %s\n", commit) +
		fmt.Sprintf("BuildTime: %s\n", buildTime)
}

func CheckNilParam(param string, params ...string) bool {
	if param == "" {
		return true
	}
	for _, v := range params {
		if v == "" {
			return true
		}
	}
	return false
}
