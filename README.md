# TupleNet

[![Build Status](https://www.travis-ci.org/vipshop/TupleNet.svg?branch=master)](https://www.travis-ci.org/vipshop/TupleNet)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](http://www.apache.org/licenses/LICENSE-2.0)

TupleNet 是基于OVS提供网络虚拟化的系统，它利用Geneve tunnel技术在物理网络上建立虚拟网络。 使用TupleNet可以非常简便地建立一个高效灵活的虚拟网络。

*TupleNet is a system was built base on OVS, it leverages Geneve tunneling to construct virtual networking on physical networking.  Anyone can use TupleNet to run an efficient and agile virtual networking easily.*

TupleNet和Flannel，Calico类似采用的基于数据库的架构方式。TupleNet中控模块由ETCD来担当，而TupleNet运行在每个compute-node节点，用于在该节点调用ovs来建立和提供虚拟网络。

*Like Flannel and Calico the architecture of Tuplenet is base on Database. Etcd play a role of brain, and each compute-node has a TupleNet instance which utilizes OVS to construct virtual networking.*

``` python
                                     +-----------------+
                                     |      ETCD       |
                                     |                 |
                                     +-----------------+
                                              |
                                +---------------------------+
                                |        Control-path       |
                          +----------+                +----------+
                          |          |                |          |  +-------------+
                 +-----+  |          |                |          +--+ Container   |
                 | VM  +--+ TupleNet |                | TupleNet |  +-------------+
                 +-----+  |          |                |          |         |
                    |     +----------+                +----------+         |
                    |     |   OVS    |                |   OVS    |         |
                    |     +----------+                +----------+         |
                    |          |       Phy-network          |              |
                    |          +----------------------------+              |
                    +------------------------------------------------------+
                                      Virtual-network


```

## Why TupleNet
### 1. TupleNet 采用了及其简便的架构方式，没有中心控制节点，部署方便快捷
TupleNet 是stateless的，它没有中控节点，TupleNet相互之间只需要通过etcd就可以相互构建完整的虚拟网络。其中TupleNet的重要节点（Edge TupleNet）是可以多套部署，所以在TupleNet的网络中是可以避免单点故障。

### 2. TupleNet 的redirecting特性可以支持让其他TupleNet节点作为中间节点转发数据报文，减少网络故障带来的影响
在TupleNet网络中可能存在某个Edge节点不能和某些节点进行通信，开启了redirecting功能后Edge TupleNet节点发现和报文接收方之间存在网络问题（普通TupleNet节点和Edge TupleNet节点通过BFD进行健康探测）后可以将数据报文先转发到其他Edge节点，让这个Edge节点帮助转发数据报文。Redirecting可以减少网络故障带来的影响。

### 3. TupleNet采用on-demand方式生成flow，可以大幅降低control-plane的cpu使用率，而且可以完美解决传统on-demand方式出现的首包延迟问题
TupleNet 的所有ovs-flow都是在本地生成，不需要一个额外的controller来发送OpenFlow。Ovs-flow生成的方式可以选择是否on-demand方式生成（默认是ondemand方式生成ovs-flow），采用on-demand方式可以大大减少生成不必要的ovs-flow。由于采用on-demand后ovs-flow的生成总是要迟于数据流，当ovs-flow没有被及时生成时候TupleNet会将数据报文转发到特定节点帮忙转发，从而解决因为实时计算ovs-flow带来的网络数据报文延迟问题。

### 4. TupleNet使用ovs的BFD与Edge TupleNet节点进行健康探测，实时获知Edge节点存活状态，屏蔽单点故障。并且TupleNet支持ECMP，可以充分利用所有Edge节点的带宽，解决单个Edge性能瓶颈问题
 虚拟网络里面的数据报文如果要和外部网络通信必须经过Edge节点，TupleNet支持同时部署和使用多台Edge TupleNet节点。普通的TupleNet节点通过ECMP方式可以将数据报文分发给不同的Edge节点，避免Edge节点成为物理网络和虚拟网络之间的瓶颈。
普通的TupleNet节点和Edge TupleNet节点使用BFD不间断进行健康探测，当普通的TupleNet节点发现某个Edge节点异常后可以自动切换，将发送数据报文给健康的Edge节点。

### 5. TupleNet支持虚拟路径的 + 物理节点的数据报文tracing，快速定位网络故障
在实际网络中很可能会出现某个网络链路出现问题，或者人为导致TupleNet配置错误，这些情况都会导致在虚拟网络中出现网路不可达。TupleNet提供了Packet tracing功能，可以通过pkt-trace工具从指定logical port发送被标记好的报文，报文所经过的TupleNet节点和虚拟网络中的虚拟节点（logical switch，logical router，logical port）都会被完整记录下来。这些信息可以帮助运维人员快速定位故障。


## TupleNet目前支持以下特性：(TupleNet's features)
- **分布式虚拟 Switch  (distributed virtual switch)**
- **分布式虚拟 Router (distributed virtual router)**
- **HA-HA Edge(虚拟网络与外部网络交互Gateway)**
- **Arp Proxy**
- **ECMP to Edge(Gateway)，BFD探测Edge，自动切换**
- **Router 设置静态路由规则 (static routes)**
- **Redirect，支持使用其他host帮助转发数据报文 (Redircte: other tuplenet node can help deliver traffic )**
- **Pkt-tracing，支持发送“染色”探测报文，并分析出所经过的整条链路  (it send out packet which can be traced and print the whole path)**
- **SNAT，DNAT, floating-ip**
- **HostSwitch IPFIX**

**很快将会支持的特性 (Feature coming soon)**
- - [ ]LoadBalance
- - [ ]ACL
- - [ ]Mirroring


## TupleNet 概要 (What TupleNet is)
- TupleNet的设计目标是尽量用最简单的方式建立一个支持**500**物理节点，**5000** 虚拟节点的中型网络。所以整个TupleNet代码架构非常精简，其主要使用[**PyDatalog**](https://sites.google.com/site/pydatalog/home)来根据目前的网络拓扑动态实时生成ovs-flow。 *TupleNet was designed to support a system which contains 500 physical node and 5000 virtual node at most. Therefore we simplify whole architecture and code in TupleNet to make it easy to be upgraded and understand. TupleNet consume pyDatalog to generate ovs-flows in run-time *
- 同时TupleNet支持preprogrammed，ondemanded两种方式来生成ovs-flow，并支持将ondemand节点的packet offload给preprogrammed节点转发。 *TupleNet has two ways(on-demand and preprogrammed) to generate ovs-flow. Besides of that, tuplenet(on-demaned node ) can deliver traffic to other host to help forwarding*
- 为了更好支持特性的添加，TupleNet目前只支持使用Geneve Tunnel进行网络虚拟化.   *TupleNet only support Geneve tunneling due to adding new feature easily*
- [Want more details?](/Architecture.md)

## 如何编译TupleNet  (How to compile TupleNet)
TupleNet目前主要由三种语言编写，分别是
- Python  TupleNet的所有主要逻辑
- C  编写的pkt_controller用于和ovs，tuplenet交互
- Golang TupleNet的tpctl，tpcnm

TupleNet的主要逻辑都是由Python构建，只需要编译pkt_controller以及tpctl（用于将配置虚拟网络写入ETCD）和tpcnm（TupleNet虚拟网络的docker cnm接口实现）
- [编译pkt_controller](/src/tuplenet/pkt_controller/README.md)
- [编译tpcnm & tpctl](/src/control/README.md)


## 如何使用TupleNet  (Have fun with TupleNet)
- **on master-host:**
1. install [ETCD](https://coreos.com/etcd/)
2. config ETCD start ETCD cluster
- **on compute-host:**
1. install [openvswitch](https://www.openvswitch.org/)(please install ovs which version above 2.8.0)
2. pip install tuplenet-xxx.whl(generate whl by running python setup.py  bdist_wheel in TupleNet folder)
3. config & run tuplenet and enjoy it. For detail guide document, please visit [tutorials](/tutorials/README.md)

### NOTE1: TupleNet还处于0.1.X的版本，还有很多不足也有很多工作要做。目前TupleNet使用在唯品会内网的测试开发云平台，只经过小规模集群验证。如果你在使用中遇到问题，欢迎告诉我们。
### NOTE2: You can download and consume latest pypy to speed up the control path to accerlate generating ovs-flow
