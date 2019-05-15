#!/bin/bash
. env_utils.sh

env_init ${0##*/} # 0##*/ is the filename
sim_create hv1 || exit_test
sim_create hv2 || exit_test
sim_create hv3 || exit_test
sim_create hv_new || exit_test
sim_create ext1 || exit_test
sim_create ext2 || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test
net_join phy hv2 || exit_test
net_join phy hv3 || exit_test
net_join phy hv_new || exit_test
net_join phy ext1 || exit_test
net_join phy ext2 || exit_test

# create logical switch and logical router first
etcd_ls_add LS-A
etcd_ls_add LS-B
etcd_lr_add LR-A
etcd_ls_add m1
etcd_ls_add m2
etcd_lr_add edge1 hv2
etcd_lr_add edge2 hv3
etcd_ls_add outside1
etcd_ls_add outside2

start_tuplenet_daemon hv1 172.20.11.1
GATEWAY=1 ONDEMAND=0 start_tuplenet_daemon hv2 172.20.11.2
GATEWAY=1 ONDEMAND=0 start_tuplenet_daemon hv3 172.20.11.3
start_tuplenet_daemon ext1 172.20.11.7
start_tuplenet_daemon ext2 172.20.11.6
start_tuplenet_daemon hv_new 172.20.11.9
install_arp
wait_for_brint # waiting for building br-int bridge

tp_add_patchport hv2 outside1 patchport-outside1 || exit_test
tp_add_patchport hv3 outside2 patchport-outside2 || exit_test

# link LS-A to LR-A
etcd_ls_link_lr LS-A LR-A 10.10.1.1 24 00:00:06:08:06:01
# link LS-B to LR-A
etcd_ls_link_lr LS-B LR-A 10.10.2.1 24 00:00:06:08:06:02
# link m1 to LR-A
etcd_ls_link_lr m1 LR-A 100.10.10.1 24 00:00:06:08:06:03
# link m2 to LR-A
etcd_ls_link_lr m2 LR-A 100.10.10.3 24 00:00:06:08:06:04
# link m1 to edge1
etcd_ls_link_lr m1 edge1 100.10.10.2 24 00:00:06:08:06:05
# link m2 to edge2
etcd_ls_link_lr m2 edge2 100.10.10.2 24 00:00:06:08:06:06
# link outside1 to edge1
etcd_ls_link_lr outside1 edge1 172.20.11.11 24 00:00:06:08:06:07
# link outside2 to edge2
etcd_ls_link_lr outside2 edge2 172.20.11.12 24 00:00:06:08:06:08

# set static route on LR-A, the route is ecmp route
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m1"
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m2"
# set static route on edge1
etcd_lsr_add edge1 10.10.0.0 16 100.10.10.1 edge1_to_m1
# set static route on edge2
etcd_lsr_add edge2 10.10.0.0 16 100.10.10.3 edge2_to_m2

# create logical switch port
port_add hv1 lsp-portA || exit_test
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:07:01
port_add hv1 lsp-port_old || exit_test
etcd_lsp_add LS-A lsp-port_old 10.10.1.15 00:00:06:08:05:05
wait_for_flows_unchange # waiting for installing flows

ofport_hv1=`get_ovs_iface_ofport hv2 tupleNet-2886994689`
ofport_hv3=`get_ovs_iface_ofport hv2 tupleNet-2886994691`
pmsg "hv1,hv3 ofports are $ofport_hv1 $ofport_hv3 in hv2 host"


test_bundle()
{
    # only get hv2(edge1) flow
    expect_bundle_ports=$1
    ovs_setenv hv2
    current_ovs_flows=`get_ovs_flows_sorted`
    bundle_flow="`echo "$current_ovs_flows"|grep bundle|grep -v bundle_load`"
    for flow in $bundle_flow; do
        flow=${flow#*bundle}
        # e.g. bundle(...,slave:1,2,3,4) ---> 1,2,3,4
        bundle_ports=`echo "$flow" |awk -F':' '{print $2}'|awk -F')' '{print $1}'`
        if [ "$bundle_ports" != "$expect_bundle_ports" ]; then
            pmsg "bundle error: "$bundle_ports" != "$expect_bundle_ports""
            return 1
        fi
    done
}

check_ovsflow_unknow_dst_pkt ()
{
    sim_id=$1
    ovs_setenv $sim_id
    current_ovs_flows=`get_ovs_flows_sorted`
    num="`echo "$current_ovs_flows" |grep controller|grep "(userdata=00.00.00.04" | wc -l`"
    if [ "$num" != "0" ]; then
        return 1
    fi
    return 0
}

# send arp packet to request feedback, it helps edge2 learn ext1 mac
src_mac=`get_ovs_iface_mac ext1 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
sha=$src_mac
spa=`ip_to_hex 172 20 11 7`
tpa=`ip_to_hex 172 20 11 12`
# build arp request
packet=ffffffffffff${sha}08060001080006040001${sha}${spa}ffffffffffff${tpa}
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
reply_ha=000006080608
expect_pkt=${sha}${reply_ha}08060001080006040002${reply_ha}${tpa}${sha}${spa}
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# stop tuplenet hv3, add now we add a new lsp to test if ext1 can send
# packet to this new lsp through hv3.(hv3 doesn't know where is new lsp is, so
# it tries to redirect to other edge(edge1 hv2))
kill_tuplenet_daemon hv3 -TERM
sleep 3
port_add hv1 lsp-portT || exit_test
etcd_lsp_add LS-A lsp-portT 10.10.1.20 00:00:06:08:07:20
wait_for_flows_unchange # waiting for installing flows
# send icmp from ext1 to lsp-portT through edge2(hv3),
# but edge2 redirect packet to edge1(hv2)
src_mac=`get_ovs_iface_mac ext1 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ip_src=`ip_to_hex 172 20 11 7`
ip_dst=`ip_to_hex 10 10 1 20`
ttl=09
packet=`build_icmp_request $src_mac 000006080608 $ip_src $ip_dst $ttl af85 8510`
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=07
expect_pkt=`build_icmp_request 000006080601 000006080720 $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_pkt hv1 lsp-portT`
verify_pkt $expect_pkt $real_pkt || exit_test
pkt_dump="`get_rx_tcpdump hv1 br0-phy`"
num=`echo "$pkt_dump" | grep -E 'ICMP|length 118' | grep "172.20.11.2" | wc -l`
if [ "$num" != 1 ]; then
    echo "error tcpdump:$pkt_dump"
    exit_test
fi

ovs_verify_drop_pkt_num hv3 0 || exit_test
ovs_verify_drop_pkt_num hv2 0 || exit_test
# send a unknow packet through hv3.(hv3 doesn't know the dst so it redirect hv2
# but hv2 still have no idea, hv2 will drop it finally.)
src_mac=`get_ovs_iface_mac ext1 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ip_src=`ip_to_hex 172 20 11 7`
ip_dst=`ip_to_hex 10 10 1 80`
ttl=09
packet=`build_icmp_request $src_mac 000006080608 $ip_src $ip_dst $ttl af85 8510`
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ovs_verify_drop_pkt_num hv3 0 || exit_test
ovs_verify_drop_pkt_num hv2 1 || exit_test
# hv3 and hv2 ONDEMAND=0, should not send any unknow-dst packet to controller
check_ovsflow_unknow_dst_pkt hv3 || exit_test
check_ovsflow_unknow_dst_pkt hv2 || exit_test


# send arp from ext1 to edge2(hv3) again to test if dead-tuplenet break ovs
# send arp packet to request feedback
src_mac=`get_ovs_iface_mac ext1 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
sha=$src_mac
spa=`ip_to_hex 172 20 11 7`
tpa=`ip_to_hex 172 20 11 12`
# build arp request
packet=ffffffffffff${sha}08060001080006040001${sha}${spa}ffffffffffff${tpa}
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
reply_ha=000006080608
expect_pkt=${sha}${reply_ha}08060001080006040002${reply_ha}${tpa}${sha}${spa}
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# send icmp to ext1 from hv1 through edge2(hv3, which tuplenet is down)
# NOTE: hv3's ovs already get ext1 mac address
ip_src=`ip_to_hex 10 10 1 20`
ip_dst=`ip_to_hex 172 20 11 7`
ttl=09
packet=`build_icmp_request 000006080720 000006080601 $ip_src $ip_dst $ttl af85 8510`
inject_pkt hv1 lsp-portT "$packet" || exit_test
wait_for_packet # wait for packet
dst_mac=`get_ovs_iface_mac ext1 br0`
dst_mac=${dst_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ttl=07
expect_pkt=`build_icmp_request 000006080608 $dst_mac $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt $expect_pkt $real_pkt || exit_test

# delete lsp-port_old, create lsp-port_new on hv_new which has lsp-port_old's
# mac and ip. Send icmp to lsp-port_new from ext1 through dead edge node(hv3),
# hv3 will deliver packet to hv1 first(because ovs in hv3 still has
# lsp-port_old's information, but has no idea that lsp-port_old had been
# removed). hv1 receive this icmp packet then figure out the right
# destination. So hv2 can deliver it to hv_new if hv2 receive next icmp.
port_del hv1 lsp-port_old || exit_test
etcd_lsp_del LS-A lsp-port_old || exit_test
etcd_lsp_add LS-A lsp-port_new 10.10.1.15 00:00:06:08:05:05
port_add hv_new lsp-port_new || exit_test
wait_for_flows_unchange
src_mac=`get_ovs_iface_mac ext1 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ip_src=`ip_to_hex 172 20 11 7`
ip_dst=`ip_to_hex 10 10 1 15`
ttl=09
packet=`build_icmp_request $src_mac 000006080608 $ip_src $ip_dst $ttl af85 8510`
if [[ -z "$ONDEMAND" || "$ONDEMAND" == 1 ]]; then
    inject_pkt ext1 br0 "$packet" || exit_test
    wait_for_packet # wait for packet
    real_pkt=`get_tx_pkt hv_new lsp-port_new`
    expect_pkt="" # cannot receive first icmp, first icmp trigger hv1's caculation
    verify_pkt $expect_pkt $real_pkt || exit_test
    sleep 2
fi
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet
ttl=07
expect_pkt=`build_icmp_request 000006080601 000006080505 $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_pkt hv_new lsp-port_new`
verify_pkt $expect_pkt $real_pkt || exit_test


# bring hv3 tuplenet back
GATEWAY=1 ONDEMAND=0 tuplenet_boot hv3 172.20.11.3
wait_for_flows_unchange

# disable the bfd detection between hv1 and hv3. then make hv3 believe that
# hv1 is not reachable, so it will redirect the packet to edge1(hv2)
disable_bfd hv1 hv3
sleep 4
# send icmp from ext1 to lsp-portA through edge2(hv3),
# but edge2 redirect packet to edge1(hv2)
ip_src=`ip_to_hex 172 20 11 7`
ip_dst=`ip_to_hex 10 10 1 2`
ttl=09
packet=`build_icmp_request $src_mac 000006080608 $ip_src $ip_dst $ttl af85 8510`
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=07
expect_pkt=`build_icmp_request 000006080601 000006080701 $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test
pkt_dump="`get_rx_tcpdump hv1 br0-phy`"
num=`echo "$pkt_dump" | grep -E 'ICMP|length 118' | grep "172.20.11.2" | wc -l`
if [ "$num" != 2 ]; then
    echo "error tcpdump:$pkt_dump"
    exit_test
fi

# send arp from ext2 to edge1(hv2)
# send arp packet to request feedback
src_mac=`get_ovs_iface_mac ext2 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
sha=$src_mac
spa=`ip_to_hex 172 20 11 6`
tpa=`ip_to_hex 172 20 11 11`
# build arp request
packet=ffffffffffff${sha}08060001080006040001${sha}${spa}ffffffffffff${tpa}
inject_pkt ext2 br0 "$packet" || exit_test
reply_ha=000006080607
expect_pkt=${sha}${reply_ha}08060001080006040002${reply_ha}${tpa}${sha}${spa}
real_pkt=`get_tx_last_pkt ext2 br0`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# send icmp from ext2 to lsp-portA through edge1(hv2)
ip_src=`ip_to_hex 172 20 11 6`
ip_dst=`ip_to_hex 10 10 1 2`
ttl=09
src_mac=`get_ovs_iface_mac ext2 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
packet=`build_icmp_request $src_mac 000006080607 $ip_src $ip_dst $ttl af83 8510`
inject_pkt ext2 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=07
expect_pkt=`build_icmp_request 000006080601 000006080701 $ip_src $ip_dst $ttl b183 8510`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# all bundle action has ofport_hv3
test_bundle $ofport_hv3 || exit_test

sim_create hv4 || exit_test
sim_create hv5 || exit_test
net_join phy hv4 || exit_test
net_join phy hv5 || exit_test
GATEWAY=1 ONDEMAND=0 start_tuplenet_daemon hv4 172.20.11.7
GATEWAY=1 ONDEMAND=0 start_tuplenet_daemon hv5 172.20.11.8
install_arp
wait_for_brint # waiting for building br-int bridge

etcd_ls_add m3
etcd_ls_add m4
etcd_lr_add edge3 hv4
etcd_lr_add edge4 hv5
etcd_ls_add outside3
etcd_ls_add outside4

tp_add_patchport hv4 outside3 patchport-outside3 || exit_test
tp_add_patchport hv5 outside4 patchport-outside4 || exit_test

etcd_ls_link_lr m3 LR-A 100.10.10.4 24 00:00:06:09:06:01
etcd_ls_link_lr m4 LR-A 100.10.10.5 24 00:00:06:09:06:02
etcd_ls_link_lr m3 edge3 100.10.10.2 24 00:00:06:09:06:03
etcd_ls_link_lr m4 edge4 100.10.10.2 24 00:00:06:09:06:04

etcd_ls_link_lr outside3 edge3 172.20.11.13 24 00:00:06:09:06:05
etcd_ls_link_lr outside4 edge4 172.20.11.14 24 00:00:06:09:06:06

# set static route on LR-A, the route is ecmp route
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m3"
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m3"

# set static route on edge3
etcd_lsr_add edge3 10.10.0.0 16 100.10.10.4 edge3_to_m3
# set static route on edge4
etcd_lsr_add edge4 10.10.0.0 16 100.10.10.5 edge4_to_m4
wait_for_flows_unchange # waiting for installing flows

ofport_hv4=`get_ovs_iface_ofport hv2 tupleNet-2886994695`
ofport_hv5=`get_ovs_iface_ofport hv2 tupleNet-2886994696`
pmsg "hv4 hv5 ofports are $ofport_hv4 $ofport_hv5 in hv2 host"
test_bundle $ofport_hv3,$ofport_hv4,$ofport_hv5 || exit_test


etcd_lr_del edge3
wait_for_flows_unchange # waiting for installing flows
test_bundle $ofport_hv3,$ofport_hv5 || exit_test

etcd_lsp_add LS-A lsp-portB 10.10.1.3 00:00:06:08:07:11
wait_for_flows_unchange # waiting for installing flows
test_bundle $ofport_hv3,$ofport_hv5 || exit_test

etcd_lsp_del LS-A lsp-portB
wait_for_flows_unchange
test_bundle $ofport_hv3,$ofport_hv5 || exit_test

pass_test
