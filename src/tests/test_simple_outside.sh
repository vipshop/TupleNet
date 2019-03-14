#!/bin/bash
. env_utils.sh

env_init ${0##*/} # 0##*/ is the filename
sim_create hv1 || exit_test
sim_create hv2 || exit_test
sim_create hv3 || exit_test
sim_create ext1 || exit_test
sim_create ext2 || exit_test
sim_create ext_gw || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test
net_join phy hv2 || exit_test
net_join phy hv3 || exit_test
net_join phy ext1 || exit_test
net_join phy ext2 || exit_test
net_join phy ext_gw || exit_test

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

start_tuplenet_daemon hv1 172.20.11.10
ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv2 172.20.11.2
ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv3 172.20.11.3
start_tuplenet_daemon ext1 172.20.11.4
start_tuplenet_daemon ext2 172.20.11.6
start_tuplenet_daemon ext_gw 172.20.11.1
install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv1 lsp-portA || exit_test
patchport_add hv2 patchport-outside1 || exit_test
patchport_add hv3 patchport-outside2 || exit_test

# add patchport into etcd
etcd_patchport_add outside1 patchport-outside1
etcd_patchport_add outside2 patchport-outside2

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

etcd_lsr_add edge1 0.0.0.0 0 172.20.11.1 edge1_to_outside1
etcd_lsr_add edge2 0.0.0.0 0 172.20.11.1 edge2_to_outside2

# create logical switch port
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:07:01
wait_for_flows_unchange # waiting for install flows

# send icmp to ext1 from hv1 through edge1(hv2)
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 172 20 11 4`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af85 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test # it will cause edge collecting send arp and collect rarp
sleep 1
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
dst_mac=`get_ovs_iface_mac ext1 br0`
dst_mac=${dst_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ttl=07
expect_pkt=`build_icmp_request 000006080607 $dst_mac $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt $expect_pkt $real_pkt || exit_test
ovs_verify_drop_pkt_num hv2 1 || exit_test

# send icmp to other phy-subnet from hv1 through edge2(hv3)
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 192 168 99 99`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af85 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test # it makes edge to collect send arp/rarp
sleep 1
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
dst_mac=`get_ovs_iface_mac ext_gw br0`
dst_mac=${dst_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ttl=07
expect_pkt=`build_icmp_request 000006080608 $dst_mac $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_last_pkt ext_gw br0`
verify_pkt $expect_pkt $real_pkt || exit_test
ovs_verify_drop_pkt_num hv3 1 || exit_test

# send icmp to ext2 from hv1 through edge2(hv3)
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 172 20 11 6`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af84 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test # it will cause edge collecting send arp and collect rarp
sleep 1
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
dst_mac=`get_ovs_iface_mac ext2 br0`
dst_mac=${dst_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ttl=07
expect_pkt=`build_icmp_request 000006080608 $dst_mac $ip_src $ip_dst $ttl b184 8510`
real_pkt=`get_tx_last_pkt ext2 br0`
verify_pkt $expect_pkt $real_pkt || exit_test
ovs_verify_drop_pkt_num hv3 2 || exit_test

# send arp from ext1 to edge2(hv3)
# send arp packet to request feedback
src_mac=`get_ovs_iface_mac ext1 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
sha=$src_mac
spa=`ip_to_hex 172 20 11 4`
tpa=`ip_to_hex 172 20 11 12`
# build arp request
packet=ffffffffffff${sha}08060001080006040001${sha}${spa}ffffffffffff${tpa}
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
reply_ha=000006080608
expect_pkt=${sha}${reply_ha}08060001080006040002${reply_ha}${tpa}${sha}${spa}
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# send icmp from ext1 to lsp-portA through edge2(hv3)
ip_src=`ip_to_hex 172 20 11 4`
ip_dst=`ip_to_hex 10 10 1 2`
ttl=09
packet=`build_icmp_request $src_mac 000006080608 $ip_src $ip_dst $ttl af85 8510`
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=07
expect_pkt=`build_icmp_request 000006080601 000006080701 $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

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
wait_for_packet # wait for packet
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
packet=`build_icmp_request $src_mac 000006080607 $ip_src $ip_dst $ttl af84 8510`
inject_pkt ext2 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=07
expect_pkt=`build_icmp_request 000006080601 000006080701 $ip_src $ip_dst $ttl b184 8510`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# edge1 drop one icmp packet(To generate arp(ext1))
# edge2 drop two icmp packet(to generate arp(request ext_gw, ext2))
ovs_verify_drop_pkt_num hv2 1 || exit_test
ovs_verify_drop_pkt_num hv3 2 || exit_test

# clear the tx pcap of lsp-portA. Then we can observe if this port can receive packet in future
clear_ovsport_txpcap hv1 lsp-portA

# send unknow dst icmp from ext2 through edge1(hv2)
ip_src=`ip_to_hex 172 20 11 6`
ip_dst=`ip_to_hex 10 10 1 99`
ttl=09
src_mac=`get_ovs_iface_mac ext2 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
packet=`build_icmp_request $src_mac 000006080607 $ip_src $ip_dst $ttl af84 8510`
inject_pkt ext2 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=07
expect_pkt=""
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# edge1 do not know this unknow dst icmp packet, redirect this packet to edge2
# edge2 do not know this the dst as well, so drop it in edge2(hv3)
ovs_verify_drop_pkt_num hv2 1 || exit_test
ovs_verify_drop_pkt_num hv3 3 || exit_test

# kill ext1 and restart a new ext3, has same IP, but different mac
pmsg "kill ext1"
kill_tuplenet_daemon ext1 -KILL
sim_destroy ext1
remove_sim_id_from_array ext1
sleep 3
pmsg "boot ext3"
sim_create ext3 || exit_test
net_join phy ext3 || exit_test
start_tuplenet_daemon ext3 172.20.11.4 || exit_test
install_arp
wait_for_flows_unchange # waiting for install flows

# send gratuitous ARP from ext3 to all host
src_mac=`get_ovs_iface_mac ext3 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
sha=$src_mac
spa=`ip_to_hex 172 20 11 4`
tpa=`ip_to_hex 172 20 11 4`
# build arp request
packet=ffffffffffff${sha}08060001080006040001${sha}${spa}ffffffffffff${tpa}
inject_pkt ext3 br0 "$packet" || exit_test
wait_for_flows_unchange # waiting for tuplenet generate mac_ip bind flow

# send icmp to ext3 from hv1 through edge1(hv2)
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 172 20 11 4`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af85 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
dst_mac=`get_ovs_iface_mac ext3 br0`
dst_mac=${dst_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ttl=07
expect_pkt=`build_icmp_request 000006080607 $dst_mac $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_last_pkt ext3 br0`
verify_pkt $expect_pkt $real_pkt || exit_test

pmsg "restart the edge node"
kill_tuplenet_daemon hv2 -TERM
ONDEMAND=0 GATEWAY=1 tuplenet_boot hv2 172.20.11.2
wait_for_flows_unchange
# send icmp to ext3 from hv1 through edge1(hv2) again, test the hv2 node if it
# can reload <mac,ip>
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 172 20 11 4`
ttl=05 # change ttl
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af85 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
dst_mac=`get_ovs_iface_mac ext3 br0`
dst_mac=${dst_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ttl=03
expect_pkt=`build_icmp_request 000006080607 $dst_mac $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_last_pkt ext3 br0`
verify_pkt $expect_pkt $real_pkt || exit_test

pass_test
