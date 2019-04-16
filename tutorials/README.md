# 1. Building connection between two hosts


####  Suppose you have two host, Host-Alice(ip:192.168.1.10), Host-Bob(ip:192.168.1.11) 


**1.1 install etcd, ovs on Host-Alice, and run the etcd and ovs**
 - suppose the etcd listening port is 2379, and the etcd should support v3 api
 - you should use a ovs above(include) version 2.8.0
 - each tuplenet node should install and start ovs, and the ovsdb must has has system-id
 - - you can use **ovs-vsctl get open_vswitch . external-ids:system-id** to see if the ovsdb has system-id
 - - you can use **ovs-vsctl set open_vswitch . external-ids:system-id=${your-host-system-id}**

**1.2 create logical switch and logical router(you can create them on any host which had been installed tuplenet)**
```
tpctl ls add LS-A   **(you may need to specified the etcd  e.g. tpctl --endpoints 10.199.132.54:2379  ls add LS-A)**
tpctl ls add LS-B
tpctl lr add LR-central
tpctl lsp add LS-A lsp-alice 10.20.1.10 f2:01:00:00:00:01
tpctl lsp add LS-B lsp-bob 10.20.2.10 f2:01:00:00:00:02
tpctl lr link LR-central LS-A 10.20.1.1/24
tpctl lr link LR-central LS-B 10.20.2.1/24
 ```
you can use tpctl lsp show LS-A or tpctl lrp show to see what you had configured. The above commands try to build a virtual networking like
 
```
             +------------------------+
             |                        |
        +----+       LR-central       +-----+
        |    |                        |     |
        |    +------------------------+     |
        |                                   |
  +----------+                        +----------+
  |          |                        |          |
  |   LS-A   |                        |   LS-B   |
  |          |                        |          |
  +----------+                        +----------+

```
**1.3 install tuplenet on both Host-Alice and Host-Bob**
```
pip install tuplenet
running tuplenet on each hosts by using command: tuplenet --interface eth0 --host 192.168.1.10:2379
```

**1.4 create namespaces on Host-Alice and Host-Bob**
on Host-Alice:
```
ip netns add ns-alice
ip link add nseth0 type veth peer name nseth0-peer
ip link set nseth0 netns ns-alice
ovs-vsctl add-port br-int nseth0-peer -- set Interface  nseth0-peer external-ids:iface-id=lsp-alice
ip netns exec ns-alice ip addr add 10.20.1.10/24 dev nseth0
ip netns exec ns-alice ip link set dev nseth0 address f2:01:00:00:00:01
ip netns exec ns-alice ip link set dev nseth0 up
ip netns exec ns-alice ip route add default via 10.20.1.1
ifconfig nseth0-peer up
```
on Host-Bob: 
```
ip netns add ns-bob
ip link add nseth0 type veth peer name nseth0-peer
ip link set nseth0 netns ns-bob
ovs-vsctl add-port br-int nseth0-peer -- set Interface  nseth0-peer external-ids:iface-id=lsp-bob
ip netns exec ns-bob ip addr add 10.20.2.10/24 dev nseth0
ip netns exec ns-bob ip link set dev nseth0 address f2:01:00:00:00:02
ip netns exec ns-bob ip link set dev nseth0 up
ip netns exec ns-bob ip route add default via 10.20.2.1
ifconfig nseth0-peer up
```
 
**1.5 now try to ping namespace !**
```
on Host-Alice: ip netns exec ns-alice ping 10.20.2.10

on Host-Bob: ip netns exec ns-bob ping 10.20.1.10
```


# 2. Building connection between virtual networking and physical networking

#### suppose you had already build connection between Host-Alice and Host-Bob which mention above. And now you have a another host name host-edge1

**2.1  install tuplenet on host-edge1 and run the tuplenet as a gateway**
```
pip install tuplenet
```
we should add a nic(which link to physical networking) into a ovs bridge, if you have two nics(eth1 is the nic links to the physical networking, eth0 rx/tx the tunnel frames)
```
ovs-vsctl add-br br0
ovs-vsctl add-port br0 eth1 (eth1 is the nic links to the physical networking, eth0 rx/tx the tunnel frames)
ONDEMAND=0 GATEWAY=1 tuplenet --interface eth0 --host 192.168.1.10:2379  (ONDEMAND=0 means this tuplenet instance generate all ovs-flow, GATEWAY=1 means the tuplenet should generate some specified ovs-flows which work on gateway node only)
ovs-vsctl add-port br-int patchport-outside1 -- set Interface patchport-outside1 type=patch external_ids:iface-id=patchport-outside1 options:peer=patchport-outside1-peer
ovs-vsctl add-port br0 patchport-outside1-peer -- set Interface patchport-outside1-peer type=patch options:peer=patchport-outside1
```
if you only have one nic(eth0 link to physical networking and eth0 was used to rx/tx tunnel frames)
```
ovs-vsctl add-br br0
ifconfig br0 up; ifconfig br0 \${eth0_ip}; ovs-vsctl add-port br0 eth0; ifconfig eth0 0; route add default gw \${default_gw}
ONDEMAND=0 GATEWAY=1 tuplenet --interface br0 --host 192.168.1.10:2379  (ONDEMAND=0 means this tuplenet instance generate all ovs-flow, GATEWAY=1 means the tuplenet should generate some specified ovs-flows which work on gateway node only)
ovs-vsctl add-port br-int patchport-outside1 -- set Interface patchport-outside1 type=patch external_ids:iface-id=patchport-outside1 options:peer=patchport-outside1-peer
ovs-vsctl add-port br0 patchport-outside1-peer -- set Interface patchport-outside1-peer type=patch options:peer=patchport-outside1
```


**2.2 adding new virtual networking device**
```
tpctl lr add LR-edge1 **edge1-node**  (the edge1-node is the host-edge1's system-id in ovsdb, the LR-edge1 pin on host-edge1, all traffic go through LR-edge1 should deliver to host-edge1.)
tpctl ls add m1
tpctl ls add outside1
tpctl lr link LR-central m1 100.10.10.1/24
tpctl lr link LR-edge1 m1  100.10.10.2/24
tpctl lr link LR-edge1 outside1 192.168.1.20/24
tpctl lsr add LR-central to_outside1 0.0.0.0/0 100.10.10.2 LR-central_to_m1
tpctl lsr add LR-edge1 to_virt1 10.20.0.0/16 100.10.10.1 LR-edge1_to_m1
tpctl lsr add LR-edge1 to_ext_world1 0.0.0.0/0  192.168.1.1 LR-edge1_to_outside1   (the 192.168.1.1 is the outside default gateway)
tpctl lsp add outside1 patchport-outside1 255.255.255.255 ff:ff:ff:ff:ff:ee (all patchport's mac should be ff:ff:ff:ff:ff:ee, it tell tuplenet unknow/outter traffic can deliver to this port)
tpctl lnat add LR-edge1 snat_rule1 10.20.0.0/16 snat 192.168.1.30   (create snat on LR-edge1)
```

```

              +-----------------+
              |    outside1     |
              +-----------------+
                       |
                       |
                 +------------+
                 |            |
                 |   edge1    |
                 +------------+
                        |
                        |
                   +---------+
                   |   m1    |
                   +---------+
                        |
                        |
            +------------------------+
            |                        |
       +----+       LR-central       +-----+
       |    |                        |     |
       |    +------------------------+     |
       |                                   |
 +----------+                        +----------+
 |          |                        |          |
 |   LS-A   |                        |   LS-B   |
 |          |                        |          |
 +----------+                        +----------+

```


**2.2 config mtu and try to ping/wget**
```
on Host-Alice: ip netns exec ns-alice ip link set dev nseth0 mtu 1400 (if the physical networking mtu is 1500, the mtu of endpoints in overlay networking should minus 100, tuplenet utilizes Geneve to construct frames)
on Host-Bob: ip netns exec ns-bob ip link set dev nseth0 mtu 1400
```
Now you can try to ping each other
```
ip netns exec ns-alice ping 192.168.X.X
ip netns exec ns-alice wget X.X.X.X
```

# 3. ECMP and HA-HA edge

#### tuplenet support ecmp(tuplenet node deliver traffic to edge node in ecmp way), tuplenet node consume bfd to detect status of tuplenet edge nodes and deliver to other edge node once it found no edge node is dead.

**3.1  install tuplenet on host-edge2 and run the tuplenet as a gateway**
- reference the commands in 2.1
- change " patchport-outside1" to " patchport-outside2",  " patchport-outside1-peer" to " patchport-outside2-peer"

**3.2 adding new virtual edge node**
```
tpctl lr add LR-edge2 **edge2-node**  (the edge2-node is the host-edge2's system-id in ovsdb, the LR-edge2 pin on host-edge2, all traffic go through LR-edge2 should deliver to host-edge2.)
tpctl ls add m2
tpctl ls add outside2
tpctl lr link LR-central m2 100.10.10.3/24
tpctl lr link LR-edge2 m2 100.10.10.2/24
tpctl lr link LR-edge2 outside2 192.168.1.21/24
tpctl lsr add LR-central to_outside2 0.0.0.0/0 100.10.10.2 LR-central_to_m2 (ecmp enable once adding same static route policy, ovs side consume frame's dst_ip to hash to each edge node. Bfd enabled as well and it tells the status of edge nodes)
tpctl lsr add LR-edge2 to_virt2 10.20.0.0/16 100.10.10.3 LR-edge2_to_m2
tpctl lsr add LR-edge2 to_ext_world2 0.0.0.0/0  192.168.1.1 LR-edge2_to_outside2   (the 192.168.1.1 is the outside default gateway)
tpctl lsp add outside2 patchport-outside2 255.255.255.255 ff:ff:ff:ff:ff:ee (all patchport's mac should be ff:ff:ff:ff:ff:ee, it tell tuplenet unknow/outter traffic can deliver to this port)
tpctl lnat add LR-edge2 snat_rule2 10.20.0.0/16 snat 192.168.1.31  (create snat on LR-edge2)
```

```

      +-----------------+            +-----------------+
      |    outside1     |            |    outside2     |
      +-----------------+            +-----------------+
               |                              |
               |                              |
         +------------+                 +------------+
         |            |                 |            |
         |   edge1    |                 |   edge2    |
         +------------+                 +------------+
                |                              |
                |                              |
           +---------+                    +---------+
           |   m1    |                    |   m2    |
           +---------+                    +---------+
                |                              |
                +------------------------------+
                              |
                  +------------------------+
                  |                        |
             +----+       LR-central       +-----+
             |    |                        |     |
             |    +------------------------+     |
             |                                   |
       +----------+                        +----------+
       |          |                        |          |
       |   LS-A   |                        |   LS-B   |
       |          |                        |          |
       +----------+                        +----------+


```


# 4. CNM in tuplenet

#### tuplenet implement cnm interface which can be consumed by docker
run tpcnm, it communicates with docker, tuplenet etcd and ovs side
- create a config.json file
- input essential info into config.json: e.g
``` json
{
  "etcd_cluster": "192.168.5.50:2379,192.168.5.51:2379,192.168.5.53:2379",
  "data_store_prefix": "/tuplenet",
  "docker_unix_sock": "/var/run/docker.sock",
  "egress_router_name": "LR-central"
}
```
data_store_prefix: it is the default tuplenet's etcd prefix datapath 
egress_route_name: it is a optional parameter, if it was set then it means 


suppose all docker in tuplenet node were connected to a single [cluster](https://docker-k8s-lab.readthedocs.io/en/latest/docker/docker-etcd.html).

**4.1 run tpcnm**
```
tpcnm -config /tmp/config.json
```
NOTE: please exec mkdir -p /run/docker/plugins/ if it show err msg "listen unix /run/docker/plugins/tuplenet.sock: bind: no such file or directory"

**4.2 create tuplenet network**
```
- docker network create -d tuplenet --subnet=10.20.3.0/24 --gateway=10.20.3.1  tp-docker-net1 (this networking is global you just need to create it once. tp-docker-net1 will link to LR-central if config.json has ***"egress_router_name": "LR-central"*** )
```
NOTE: the name of tp-docker-net1 in tuplenet's etcd may be a just a uuid. 

NOTE: please confirm whether your docker has connected to a cluster before running this command to create a global networking

**4.3 create container link to tp-docker-net1**
```
docker run  --privileged --net=tp-docker-net1 -ti -d centos-tool /bin/bash (tpcnm will create lsp on switch tp-docker-net1 automatically )
```
NOTE: please decrease the mtu of container's ethX as well, the mtu of endpoints in overlay networking should minus 100, tuplenet utilizes Geneve to construct frames. 

```
   +-----------------+            +-----------------+
   |    outside1     |            |    outside2     |
   +-----------------+            +-----------------+
            |                              |
            |                              |
      +------------+                 +------------+
      |            |                 |            |
      |   edge1    |                 |   edge2    |
      +------------+                 +------------+
             |                              |
             |                              |
        +---------+                    +---------+
        |   m1    |                    |   m2    |
        +---------+                    +---------+
             |                              |
             +------------------------------+
                           |
               +------------------------+
               |                        |
          +----+       LR+central       +-----+
          |    |                        |     |
          |    +------------------------+     |
          |                 |                 |
    +----------+            |           +----------+
    |          |            |           |          |
    |   LS_A   |            |           |   LS_B   |
    |          |            |           |          |
    +----------+            |           +----------+
                            |
                  +-------------------+
                  |  tp-docker-net1   |
                  |                   |
                  +-------------------+

```

# 5. CNI in TupleNet

#### TupleNet implement CNI interface which can be consumed by kubelet

**5.1 config tpcni.conf**
```
cat <<EOF  > /etc/cni/net.d/tpcni.conf
{
        "cniVersion": "0.3.0",
        "name": "tpcni-network",
        "type": "tpcni",
        "mtu": 1400,
        "switchname": "LS_A",
        "subnet": "10.20.1.1/24",
        "etcd_cluster": "YOUR_ETCD_IP:PORT",
        "data_store_prefix": "/tuplenet"
}
EOF
```
This config file tell tpcni that it should allocate ip from 10.20.1.1/24, and the created lsp was pinned on LS-A.(the IP 10.20.1.1 is default gw)

**5.1 build link for tpcni**

Once tpcni.conf was built the kubelet searchs tpcni in /opt/cni/bin. User must set link for tpcni in /opt/cni/bin
```
ln -s /usr/bin/tpcni /opt/cni/bin/tpcni
```
Now please try to restart kubelet and create a new POD.


# 6. Metrics and monitoring

**6.1 how to enable IPFIX in tuplenet node**

Append IPFIX_COLLECTOR=IP:port and optional IPFIX_SAMPLING_RATE=x to environment variable. Domain ID will be the uint32 representation of the tuplenet node IP

# 7. Enable UNTUNNEL mode

Once enable untunnel mode, the regular tuplenet's out-traffic(should forward to physical network) would not deliver to edge node. Instead, those traffic will be deliver to host tcpip stack through br-int port which is an internal port. It helps to improve latency and throughput.

Append ENABLE_UNTUNNEL=1 to environment variable, restart tuplenet then it enable the untunnel mode.
