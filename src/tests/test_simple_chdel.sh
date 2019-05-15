#!/bin/bash
. env_utils.sh

env_init ${0##*/} # 0##*/ is the filename
sim_create hv1 || exit_test
sim_create hv2 || exit_test
sim_create hv3 || exit_test
sim_create hv4 || exit_test
sim_create ext1 || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test
net_join phy hv2 || exit_test
net_join phy hv3 || exit_test
net_join phy hv4 || exit_test
net_join phy ext1 || exit_test

# create logical switch and logical router first
etcd_ls_add LS-A
etcd_ls_add LS-B
etcd_lr_add LR-A

start_tuplenet_daemon hv1 192.168.100.2
start_tuplenet_daemon hv2 192.168.100.3
GATEWAY=1 ONDEMAND=0 start_tuplenet_daemon hv3 192.168.100.4
GATEWAY=1 ONDEMAND=0 start_tuplenet_daemon hv4 192.168.100.5
start_tuplenet_daemon ext1 192.168.100.6
install_arp
wait_for_brint # waiting for building br-int bridge

# link LS-A to LR-A
etcd_ls_link_lr LS-A LR-A 10.10.1.1 24 00:00:06:08:06:01
# link LS-B to LR-A
etcd_ls_link_lr LS-B LR-A 10.10.2.1 24 00:00:06:08:06:02
port_add hv1 lsp-portA || exit_test
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:07:01
port_add hv1 lsp-portB || exit_test
etcd_lsp_add LS-B lsp-portB 10.10.2.2 00:00:06:08:09:01
wait_for_flows_unchange # waiting for install flows


# adding a new ecmp road(on hv4)
init_ecmp_road hv4 192.168.100.57/24 10.10.0.0/16 192.168.100.1 || exit_test
# wait here, make sure the edge1,lrp should occupies ilk 0
# so edge2 has high priority
wait_for_flows_unchange # waiting for install flows
wait_for_flows_unchange # waiting for install flows
add_ecmp_road hv3 192.168.100.61/24 || exit_test
port_add hv1 lsp-portC || exit_test
etcd_lsp_add LS-B lsp-portC 10.10.2.3 00:00:06:08:09:05
port_add hv2 lsp-portD || exit_test
etcd_lsp_add LS-B lsp-portD 10.10.2.4 00:00:06:08:09:06
wait_for_flows_unchange # waiting for install flows

# NOTE: kill hv2 here because we want hv2 send packet to hv3(edge),
# so stopping tuplenet on hv2 would not update ovsflow even we
# delete hv3 from etcd side.
# Besides that, should disable bfd on hv2, make it believe that hv3
# is still alive
kill_tuplenet_daemon hv2 -TERM
sleep 2
disable_bfd hv2 hv3

# del hv3(edge node), the hv3 tuplenet will disable icmp ping of LR-edge, but
# other features should works well. hv3 can help to forward packet as usual.
tpctl ch del hv3 || exit_test
wait_for_flows_unchange

# send arp to hv edge from ext1
# send arp packet to request feedback
src_mac=`get_ovs_iface_mac ext1 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
sha=$src_mac
spa=`ip_to_hex 192 168 100 6`
tpa=`ip_to_hex 192 168 100 61`
# build arp request
packet=ffffffffffff${sha}08060001080006040001${sha}${spa}ffffffffffff${tpa}
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
reply_ha=f201c0a8643d
expect_pkt=${sha}${reply_ha}08060001080006040002${reply_ha}${tpa}${sha}${spa}
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# send icmp from ext1 to lsp-portA through hv3. even hv3 was deleted, but
# hv3 still forward packet
ip_src=`ip_to_hex 192 168 100 6`
ip_dst=`ip_to_hex 10 10 1 2`
ttl=06
packet=`build_icmp_request $src_mac $reply_ha $ip_src $ip_dst $ttl af85 8510`
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=04
expect_pkt=`build_icmp_request 000006080601 000006080701 $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# on the other hand, hv3's edge should not response icmp from ext1 anymore.
ip_src=`ip_to_hex 192 168 100 6`
ip_dst=`ip_to_hex 192 168 100 61`
expect_pkt="`get_tx_pkt ext1 br0`"
ttl=06
packet=`build_icmp_request $src_mac $reply_ha $ip_src $ip_dst $ttl af85 8510`
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=04
real_pkt="`get_tx_pkt ext1 br0`"
verify_pkt "$expect_pkt" "$real_pkt" || exit_test


# send icmp from lsp-portD(on hv2) to ext1 through hv3
dst_mac=`get_ovs_iface_mac ext1 br0`
dst_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
# NOTE: the hash_fn in hv2 is nw_src, NOT nw_dst
ip_src=`ip_to_hex 10 10 2 4`
ip_dst=`ip_to_hex 192 168 100 6`
ttl=04
packet=`build_icmp_request 000006080906 000006080602 $ip_src $ip_dst $ttl af76 8510`
inject_pkt hv2 lsp-portD "$packet" || exit_test
wait_for_packet # wait for packet
ttl=02
expect_pkt=`build_icmp_request f201c0a8643d $dst_mac $ip_src $ip_dst $ttl b176 8510`
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt $expect_pkt $real_pkt || exit_test

# send icmp from lsp-portA(on hv1) to ext1 through hv4
dst_mac=`get_ovs_iface_mac ext1 br0`
dst_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 192 168 100 6`
ttl=04
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af76 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=02
# the mac is f201c0a86439 which belong to 192.168.100.57
expect_pkt=`build_icmp_request f201c0a86439 $dst_mac $ip_src $ip_dst $ttl b176 8510`
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt $expect_pkt $real_pkt || exit_test


# reboot the hv3, then all work as usual
kill_tuplenet_daemon hv3 -TERM
GATEWAY=1 ONDEMAND=0 tuplenet_boot hv3 192.168.100.4
tuplenet_boot hv2 192.168.100.3
wait_for_flows_unchange # waiting for install flows
# NOTE: we have to disable bfd because the bfd issue would break the test.
# the bfd issue( tunnel bfd interface can send/receive bfd packet but still in
# down or init state)
disable_bfd hv3 hv2 || exit_test
disable_bfd hv3 hv1 || exit_test
disable_bfd hv1 hv3 || exit_test
disable_bfd hv2 hv3 || exit_test

# send icmp from lsp-portD(on hv2) to ext1 through hv3
dst_mac=`get_ovs_iface_mac ext1 br0`
dst_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ip_src=`ip_to_hex 10 10 2 4`
ip_dst=`ip_to_hex 192 168 100 6`
ttl=04
packet=`build_icmp_request 000006080906 000006080602 $ip_src $ip_dst $ttl af76 8510`
inject_pkt hv2 lsp-portD "$packet" || exit_test
wait_for_packet # wait for packet
ttl=02
expect_pkt=`build_icmp_request f201c0a8643d $dst_mac $ip_src $ip_dst $ttl b176 8510`
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt $expect_pkt $real_pkt || exit_test

# send icmp from lsp-portA(on hv1) to ext1 through hv3.(hv3 is back now)
dst_mac=`get_ovs_iface_mac ext1 br0`
dst_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 192 168 100 6`
ttl=04
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af76 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=02
expect_pkt=`build_icmp_request f201c0a8643d $dst_mac $ip_src $ip_dst $ttl b176 8510`
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt $expect_pkt $real_pkt || exit_test

# delete the hv3 but readd it back
tpctl ch del hv3 || exit_test
wait_for_flows_unchange
etcd_chassis_add hv3 192.168.100.4 10
wait_for_flows_unchange
# NOTE: we have to disable bfd because the bfd issue would break the test.
# the bfd issue( tunnel bfd interface can send/receive bfd packet but still in
# down or init state)
disable_bfd hv3 hv2 || exit_test
disable_bfd hv3 hv1 || exit_test
disable_bfd hv1 hv3 || exit_test
disable_bfd hv2 hv3 || exit_test
# send icmp from lsp-portD(on hv2) to ext1 through hv3
dst_mac=`get_ovs_iface_mac ext1 br0`
dst_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ip_src=`ip_to_hex 10 10 2 4`
ip_dst=`ip_to_hex 192 168 100 6`
ttl=04
packet=`build_icmp_request 000006080906 000006080602 $ip_src $ip_dst $ttl af76 8510`
inject_pkt hv2 lsp-portD "$packet" || exit_test
wait_for_packet # wait for packet
ttl=02
expect_pkt=`build_icmp_request f201c0a8643d $dst_mac $ip_src $ip_dst $ttl b176 8510`
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt $expect_pkt $real_pkt || exit_test

# send icmp from lsp-portA(on hv1) to ext1 through hv3.(hv3 is back now)
dst_mac=`get_ovs_iface_mac ext1 br0`
dst_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 192 168 100 6`
ttl=04
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af76 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=02
expect_pkt=`build_icmp_request f201c0a8643d $dst_mac $ip_src $ip_dst $ttl b176 8510`
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt $expect_pkt $real_pkt || exit_test

pass_test
