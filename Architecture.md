## Architecture
TupleNet 的架构是一种面向数据库架构模式，在TupleNet构建的系统中所有TupleNet都是平等的，在控制层面上不会存在中控节点。但是为了使得TupleNet可以互相配合实现虚拟网络，我们使用ETCD作为这个TupleNet系统的中控大脑，ETCD中存储了所有的虚拟节点信息（虚拟交换机，虚拟路由器，以及虚拟port）和物理节点信息（TupleNet所在主机的IP）。

所有的TupleNet都会连接ETCD集群并持续watch这些网络拓扑信息，一旦发生改动（增加，删除）就会自动同步到所有的TupleNet节点，TupleNet将会根据这些变化进行相应的计算，并在本地生成ovs-flow插入到ovs-vswitchd中。整个过程相当于每个TupleNet几点都保存了一份ETCD完整数据，并且ovs-flow生成都由本地完成，通过这种方式我们将数据存储的快速访问和计算都offload到每个TupleNet节点，所以局部TupleNet节点的存活状态并不会影响其他节点。

之所以采用ETCD是因为它非常适合存储持久化的配置信息，即使TupleNet节点数量太大，也可以通过部署etcd proxy 来分散etcd cluster的压力，水平扩展性非常好。



```
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
TupleNet的dataplane使用的是openvswitch（版本大于等于2.8.0）来实现的，OVS是一个很优秀的开源软件交换机，并且被广泛使用，而且特性也很多，例如bonding，Mirroring，BFD。除此之外openvswitch可以通过在runtime时候配置ovs-flow来实现各种各样的网络数据包操作。

为了屏蔽物理网络设备影响，TupleNet通过使用Geneve在physical networking上组建virtual-networking，Geneve是一种扩展性很好的用于组建Overlay network的协议，和VXLAN很类似，它通过UDP来进行二次封包来解决跨越网络的问题。Geneve的扩展性非常好，并且很多网络已经支持Geneve的TSO，速度上和VXLAN，STT是相近的，而Geneve可以支持option headers，可以在一定程度上任意添加metadata，而更多的metadata数据为更好描述encapsulated报文提供了便捷。

```
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |Ver|  Opt Len  |O|C|    Rsvd.  |          Protocol Type        |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |        Virtual Network Identifier (VNI)       |    Reserved   |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |                    Variable Length Options                    |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

## Implementation of control-plane

### python and pyDatalog
TupleNet的绝大部分代码是python书写的，因为python灵活，易于排查问题的特点，非常适合开发控制平面，能快速迭代出新的网络功能。虽然control-plane使用解析性动态语言后性能不如编译型程序快，但是control-plane并不会影响datapath的效率，不会引入数据包的转发耗时。所以我们认为使用python 动态语言来实现control-plane是非常合适的。

在虚拟网络中，网络报文的行为需要实时根据目前的虚拟网络网络拓扑和物理网络拓扑来决定，而虚拟网络拓扑在实际使用中是易变的，且变化是频繁的。我们需要一种方便的工具能快速帮我们解析实时网络状态的迁移，因为这种状态的变更是完全stateless的，所以我们采用Datalog这种古老的语言帮助我们屏蔽网络拓扑变化带来的编程复杂性。PyDatalog是Datalog在python的一种实现，它语法形式类似Datalog。我们编写好地pyDatalog规则后输入网络拓扑数据就可以用pyDatalog 引擎动态计算出目前需要插入和删除的ovs-flow。pyDatalog是一个python lib库，可以有机地和python结合起来，使得python既有命令式编程能能力，同时也具备声明式编程能力。

### Consume ovsdb-client，ovs-vsctl and ovs-ofctl immediately
TupleNet 没有使用ovs python库来直接和ovsdb来进行通信，也没有直接和ovs-vswitch通信来插入ovs-flows，我们认为绝大部分时候control-path并不会影响datapath的性能，而整个controlplane的耗时瓶颈也不在ovs-flow的插入，而在于flow的计算。所以我们直接采用调用ovsdb-client来监听ovsdb interface的变化，使用ovs-vsctl 和 ovs-ofctl来配置ovs以及往ovs中插入ovs-flow。这种取舍使得我们能精简大量代码，将大量工作直接交给ovs tools，并且大大简化了ovs-flow的生成。

## Implementation of data-plane
目前我们在Geneve的option header中使用64个bit来存储encapsulated frame需要的metadata信息，其中source port ID 和destination port ID（logcial switch和logical router的port都会占用一个port ID，该ID目前根据给定的port IP的后16bit来自动生成）各占用16bit，也就是说一个logical switch或logical router中，最多只能有65536个port。Frame Flag会说明payload里面数据报文的特殊意义，比如表明这个数据包是特殊的需要帮助转发的报文。Command ID是用来和etcd交互的，它用来标记该数据报文属于某个特殊命令，目前被用于pkt-tracing。
```
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |  Source port ID               |     Destination port ID       |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |  Frame Flag                   |     Command ID                |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```


### PipeLine

为了灵活处理各种类型的数据报文，我们为virtualswitch，virtualrouter建立了相应的数据报文处理pipeline，所有数据报文都需要经过pipeline的处理。
```


                 PORT        +--------------------------------------------------------------------------------------------------------------------------+
                  +          |                                                                                                                          |
                  |          |                                +----------------------------------------------------+                                    |
                  |          |                                |                                                    |                                    |
  +---------------v----------v----+                           |                                                    |                                    |
  |     LSP_TRACE_INGRESS_IN      |               PORT        |                                    +---------------v---------------+    +-------------------------------+
  +-------------------------------+                ^          |                                    |     LRP_TRACE_INGRESS_IN      |    |      LRP_TRACE_EGRESS_OUT     |
                  |                                |          |                                    +-------------------------------+    +-------------------------------+
                  v                                |          |                                                    |                                    ^
                                                   |          |                                                    v                                    |
  +-------------------------------+           +-------------------------------+                                                                         |
  |   LSP_INGRESS_ARP_CONTROLLER  |           |     LSP_EGRESS_PUSHOUT        |                    +-------------------------------+    +-------------------------------+
  +-------------------------------+           +-------------------------------+                    |   LRP_INGRESS_PKT_RESPONSE    |    |   LRP_EGRESS_FORWARD_PACKET   |
                  |                                            ^                                   +-------------------------------+    +-------------------------------+
                  v                                            |                                                   |                                    ^
                                                               |                                                   v                                    |
  +-------------------------------+           +-------------------------------+                                                                         |
  |   LSP_INGRESS_ARP_RESPONSE    |           |     LSP_EGRESS_PUSHOUT        |                    +-------------------------------+    +-------------------------------+
  +-------------------------------+           +-------------------------------+                    |   LRP_INGRESS_DROP_UNEXPECT   |    |   LRP_EGRESS_UPDATE_ETH_DST   |
                  |                                            ^                                   +-------------------------------+    +-------------------------------+
                  v                                            |                                                   |                                    ^
                                                               |                                                   v                                    |
  +-------------------------------+           +-------------------------------+                                                                         |
  |   LSP_INGRESS_LOOKUP_DST_PORT |           |  LSP_EGRESS_FORWARD_PACKET    |                    +-------------------------------+    +-------------------------------+
  +-------------------------------+           +-------------------------------+                    |   LRP_INGRESS_UNSNAT_STAGE1   |    |    LRP_EGRESS_SNAT_STAGE2     |
                  |                                            ^                                   +-------------------------------+    +-------------------------------+
                  v                                            |                                                   |                                    ^
                                                               |                                                   v                                    |
  +-------------------------------+           +-------------------------------+                                                                         |
  |   LSP_INGRESS_OUTPUT_DST_PORT |           |  LSP_EGRESS_JUDGE_LOOPBACK    |                    +-------------------------------+    +-------------------------------+
  +-------------------------------+           +-------------------------------+                    |   LRP_INGRESS_UNSNAT_STAGE2   |    |    LRP_EGRESS_SNAT_STAGE1     |
                  |                                            ^                                   +-------------------------------+    +-------------------------------+
                  v                                            |                                                   |                                    ^
                                                               |                                                   v                                    |
  +-------------------------------+           +-------------------------------+                                                                         |
  |    LSP_TRACE_INGRESS_OUT      |           |     LSP_TRACE_EGRESS_IN       |                    +-------------------------------+    +-------------------------------+
  +-------------------------------+           +-------------------------------+                    |   LRP_INGRESS_DNAT_STAGE1     |    |    LRP_EGRESS_UNDNAT_STAGE2   |
                  |                                            ^                                   +-------------------------------+    +-------------------------------+
                  |                                            |                                                   |                                    ^
                  |                                            |                                                   v                                    |
                  |                                            |                                                                                        |
                  |                                            |                                   +-------------------------------+    +-------------------------------+
                  |                                            |                                   |   LRP_INGRESS_DNAT_STAGE2     |    |    LRP_EGRESS_UNDNAT_STAGE1   |
                  +--------------------------------------------+                                   +-------------------------------+    +-------------------------------+
                                                                                                                   |                                    ^
                                                                                                                   v                                    |
                                                                                                                                                        |
                                                                                                   +-------------------------------+    +-------------------------------+
                                                                                                   |     LRP_INGRESS_IP_ROUTE      |    |     LRP_TRACE_EGRESS_IN       |
                                                                                                   +-------------------------------+    +-------------------------------+
                                                                                                                   |                                    ^
                                                                                                                   v                                    |
                                                                                                                                                        |
                                                                                                   +-------------------------------+                    |
                                                                                                   |        LRP_INGRESS_ECMP       |                    |
                                                                                                   +-------------------------------+                    |
                                                                                                                   |                                    |
                                                                                                                   v                                    |
                                                                                                                                                        |
                                                                                                   +-------------------------------+                    |
                                                                                                   |     LRP_TRACE_INGRESS_OUT     |                    |
                                                                                                   +-------------------------------+                    |
                                                                                                                   |                                    |
                                                                                                                   |                                    |
                                                                                                                   |                                    |
                                                                                                                   +------------------------------------+



```

### traffic redirecting
Traffic redirecting是TupleNet的一个重要特性。TupleNet默认启动时候会使用ondemand方式来生成ovs-flow，也就是说当TupleNet收到traffic中的第一个网络报文时候才会生成相应的ovs-flow。这样做的好处是能最大节约TupleNet所在机器的CPU，只计算真正需要的ovs-flow，但是这种方式同时也会带来traffic中首包被丢弃或产生严重延迟的问题。但是如果采用全量计算ovs-flow就会占用大量的CPU资源生成无用的ovs-flow，而且每次网络拓扑的微小变化都要通过pyDatalog来计算。为了解决这个问题，我们引入了redirecting功能。

Redirecting主要功能场景有两块：
-  当某个Edge TupleNet节点和普通的TupleNet节点产生网络路径异常（不能将报文发给对方）时候，BFD会发现它们之间的通路存在问题。这个时候如果Edge TupleNet启动了redirecting功能后就可以将报文先发给其他的Edge节点，收到这个报文的Edge节点判断出这个报文是个redirecting报文后就会帮助转发到相应的TupleNet节点，而这个TupleNet节点通过BFD和ECMP可以自动选择其他路径，跳过有问题的Edge几点，将数据报文转发给正常的Edge节点。

-  因为TupleNet默认是开启ondemand方式来生成ovs-flow的，所以TupleNet启动后ovs中只有一些基本的ovs-flow。当某个数据报文在ovs找不到对应的目的地时候，将会做两个动作：一个是告诉TupleNet，让TupleNet生成相应的ovs-flow；第二是将该数据报文转发给Agent节点（某个LogicalRouter只存在于独立的节点就是Agent，例如Edge节点就是Agent节点）。Agent TupleNet节点一般会禁用ondemand功能，它会全量生成所有可能的ovs-flow，不存在首包延迟的问题。 所以整个流程就变成未知目的地的报文默认会转发到Agent节点，Agent节点已经有了全量的ovs-flow，所以能快速转发。源TupleNet经过计算后，将优先级更高的新ovs-flow写入到ovs中，后续的未知目的地报文就可以根据这些新的ovs-flow路由到正确目的地。Redirecting功能可以非常好地解决首包延迟问题，而且不会对Agent节点产生压力，因为经过短时间间隔后（新的ovs-flow计算好后）就会旁路Agent节点而发送到正确目的地。

### Edge HA & ECMP

TupleNet的Edge节点都是平等的，不存在优先级。当我们部署了多台Edge节点后，可以配置相应的logical static route来自动开启ECMP功能，其他的TupleNet节点的数据报文就可以分散到不同的Edge节点上，实现Edge节点的负载均衡。所有的普通的TupleNet节点和Edge TupleNet节点都会保持BFD心跳，用来实时探测之间网络异常。当TupleNet节点发现某个Edge节点不可达后就会利用ovs的ecmp功能自动将数据包转发到其他Edge节点。

### Packet tracing

Packet tracing主要是用来做trouble-shooting的。在虚拟网络和物理网络上，出现网络异常是非常常见且不可避免的事情，有可能是物理网络存在故障，有可能是虚拟网络本身的bug或者配置错误引起的。而Packet tracing就是用来检测整个网络通路的工具。它可以发送指定的数据报文，这个数据报文经过各个TupleNet的ovs时候都会被记录下，这些路径消息最后会被聚合起来展示给用户，告知用户该数据报文时候正确到达目的地或被中途丢弃。下面的例子可以非常详细地记录该数据报文到达了那些TupleNet节点，经过了那些pipeline，为我们定位错误提供了非常便捷地工具。

``` python
type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-A,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-A,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-A,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv1
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m1,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m1,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv1
type:LR,pipeline:LR-A,from:LR-A_to_m1,to:LR-A_to_m1,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv1
type:LS,pipeline:m1,from:m1_to_LR-A,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1
type:LS,pipeline:m1,from:m1_to_LR-A,to:m1_to_edge1,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1
type:LS,pipeline:m1,from:m1_to_LR-A,to:m1_to_edge1,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv2
type:LS,pipeline:m1,from:m1_to_LR-A,to:m1_to_edge1,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv2
type:LR,pipeline:edge1,from:edge1_to_m1,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv2
type:LR,pipeline:edge1,from:edge1_to_m1,to:edge1_to_m1,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv2
type:LR,pipeline:edge1,from:edge1_to_m1,to:edge1_to_m1,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv2
type:LR,pipeline:edge1,from:edge1_to_m1,to:edge1_to_m1,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv2
type:LS,pipeline:m1,from:m1_to_edge1,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv2
type:LS,pipeline:m1,from:m1_to_edge1,to:m1_to_LR-A,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv2
type:LS,pipeline:m1,from:m1_to_edge1,to:m1_to_LR-A,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv2
type:LS,pipeline:m1,from:m1_to_edge1,to:m1_to_LR-A,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-A,from:LR-A_to_m1,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv2
type:LR,pipeline:LR-A,from:LR-A_to_m1,to:LR-A_to_LS-A,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-A,from:LR-A_to_m1,to:LR-A_to_LS-A,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv2
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_LS-A,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-A,from:LS-A_to_LR-A,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv2
type:LS,pipeline:LS-A,from:LS-A_to_LR-A,to:lsp-portA,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-A,from:LS-A_to_LR-A,to:lsp-portA,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1
type:LS,pipeline:LS-A,from:LS-A_to_LR-A,to:lsp-portA,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1
```

## 可视化拓扑图
TupleNet的所有相关网络拓扑实时数据都存储在etcd集群中，而这些数据是弱关联的key/value，难以阅读和理解。
为了能让使用者更好理解当前拓扑，可以使用generate-graphviz.py来生成graphviz数据，这些graphviz数据可以被graphviz解析并渲染出相应图像。用户可以将graphviz数据粘贴到[webgraphviz](http://www.webgraphviz.com/) 文本框中，来生成相应的可视化网络拓扑视图。

## Auto-testing

TupleNet为了保证系统地稳定性建立了不少自动化testcases，testcase都是由bash和python组建，利于扩展和调试。这些testcase可以在本地比较完整地模拟复杂的物理环境和虚拟环境，充分测试各个功能的正确性，可以较好地保证TupleNet质量。而且这些testcase都是可以并行运行，尽最大化减少test耗费的时间。
