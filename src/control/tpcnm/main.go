package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"github.com/vipshop/tuplenet/control/controllers/etcd3"
	"go.uber.org/zap"
	"net"
	"net/http"
	"os"
	"strings"
)

type pluginCfg struct {
	EtcdCluster      string `json:"etcd_cluster"`
	DataStorePrefix  string `json:"data_store_prefix"`
	DockerUnixSock   string `json:"docker_unix_sock"`
	EgressRouterName string `json:"egress_router_name"` // optional
}

const listenPath = "/run/docker/plugins/tuplenet.sock"

var (
	controller       *etcd3.Controller
	egressRouterName string
	log              *zap.SugaredLogger

	dockerUnixSock = "/var/run/docker.sock"
)

func readConfig() {
	var (
		cfg       pluginCfg
		printHelp bool
		cfgPath   string
		err       error
		usage     func()
	)

	usage = func() {
		fmt.Println("config.json example:")
		fmt.Println("--------------------")
		cfg.EtcdCluster = "10.0.0.1:2379,10.0.0.2:2379,10.0.0.2:2379"
		cfg.DataStorePrefix = "/tuplenet"
		cfg.EgressRouterName = "LR-1"
		cfg.DockerUnixSock = "/var/run/docker.sock"
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		enc.Encode(&cfg)
		fmt.Println()
		os.Exit(0)
	}

	flag.StringVar(&cfgPath, "config", "./config.json", "config file path")
	flag.BoolVar(&printHelp, "h", false, "help on usage")
	flag.Parse()

	if printHelp {
		usage()
	}

	if cfgFile, err := os.Open(cfgPath); err != nil {
		fmt.Printf("unable to read config %v\n", err)
		usage()
		os.Exit(1)
	} else {
		err = json.NewDecoder(cfgFile).Decode(&cfg)
		if err != nil {
			fmt.Printf("unable to read config %v\n", err)
			os.Exit(2)
		}
	}

	if cfg.EtcdCluster == "" || cfg.DataStorePrefix == "" {
		fmt.Println("etcd3 cluster or data store prefix is empty")
		usage()
	}

	controller, err = etcd3.NewController(
		strings.Split(cfg.EtcdCluster, ","),
		cfg.DataStorePrefix,
		true)

	if err != nil {
		fmt.Printf("unable to setup: %v", err)
		os.Exit(3)
	}

	egressRouterName = cfg.EgressRouterName

	if cfg.DockerUnixSock != "" {
		dockerUnixSock = cfg.DockerUnixSock
	}
}

func main() {
	readConfig()
	l, _ := zap.NewDevelopment()
	log = l.Sugar()

	_, err := os.Stat(listenPath)
	if err == nil {
		conn, err := net.Dial("unix", listenPath)
		if err == nil {
			conn.Close()
			log.Fatalf("%s is used by another process", listenPath)
		}
		os.RemoveAll(listenPath)
	}

	listener, err := net.Listen("unix", listenPath)
	if err != nil {
		log.Fatal(err)
	}

	http.HandleFunc("/Plugin.Activate", func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`{"Implements": ["NetworkDriver"]}`))
	})

	http.HandleFunc("/NetworkDriver.GetCapabilities", func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`{"Scope": "global"}`))
	})

	// matches both DiscoverNew and DiscoverDelete
	http.HandleFunc("/NetworkDriver.Discover", func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`{}`))
	})

	http.HandleFunc("/NetworkDriver.CreateNetwork", createNetwork)
	http.HandleFunc("/NetworkDriver.DeleteNetwork", deleteNetwork)
	http.HandleFunc("/NetworkDriver.CreateEndpoint", createEndpoint)
	http.HandleFunc("/NetworkDriver.EndpointOperInfo", endpointOperInfo)
	http.HandleFunc("/NetworkDriver.DeleteEndpoint", deleteEndpoint)
	http.HandleFunc("/NetworkDriver.Join", join)
	http.HandleFunc("/NetworkDriver.Leave", leave)

	log.Fatal(http.Serve(listener, nil))
}
