#!/bin/bash
. env_utils.sh

env_init ${0##*/} # 0##*/ is the filename
sim_create hv1 || exit_test
sim_create hv2 || exit_test
sim_create ext1 || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test
net_join phy hv2 || exit_test
net_join phy ext1 || exit_test

# create logical switch and logical router first
etcd_ls_add LS-A
etcd_ls_add LS-B
etcd_lr_add LR-A

start_tuplenet_daemon hv1 192.168.100.2
GATEWAY=1 ONDEMAND=0 start_tuplenet_daemon hv2 192.168.100.3
start_tuplenet_daemon ext1 192.168.100.6
install_arp
wait_for_brint # waiting for building br-int bridge

# link LS-A to LR-A
etcd_ls_link_lr LS-A LR-A 10.10.1.1 24 00:00:06:08:06:01
# link LS-B to LR-A
port_add hv1 lsp-portA || exit_test
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:07:01
wait_for_flows_unchange # waiting for install flows

# adding a new ecmp road
init_ecmp_road hv2 192.168.100.51/24 10.10.0.0/16 192.168.100.1 || exit_test
wait_for_flows_unchange # waiting for install flows

# send arp to edge1 from ext1
# send arp packet to request feedback
src_mac=`get_ovs_iface_mac ext1 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
sha=$src_mac
spa=`ip_to_hex 192 168 100 6`
tpa=`ip_to_hex 192 168 100 51`
# build arp request
packet=ffffffffffff${sha}08060001080006040001${sha}${spa}ffffffffffff${tpa}
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
reply_ha=f201c0a86433
expect_pkt=${sha}${reply_ha}08060001080006040002${reply_ha}${tpa}${sha}${spa}
real_pkt=`get_tx_last_pkt ext1 br0`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# send icmp from ext1 to lsp-portA through edge1(hv2)
ip_src=`ip_to_hex 192 168 100 6`
ip_dst=`ip_to_hex 10 10 1 2`
ttl=09
packet=`build_icmp_request $src_mac $reply_ha $ip_src $ip_dst $ttl af85 8510`
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=07
expect_pkt=`build_icmp_request 000006080601 000006080701 $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

patchport="tp_lsp_tp_LS_outside1-patchport1"
peer_patchport="tp_lsp_tp_LS_outside1-patchport1-peer"

# delete peer-patchport to test if the peer-patchport can be rebuild.
port_del hv2 $peer_patchport || exit_test
sleep 3
#ovs_setenv hv2
#ovs-vsctl show
is_port_exist hv2 $peer_patchport || exit_test
# send icmp again(fix ttl) from ext1 to lsp-portA through edge1(hv2)
ip_src=`ip_to_hex 192 168 100 6`
ip_dst=`ip_to_hex 10 10 1 2`
ttl=08
packet=`build_icmp_request $src_mac $reply_ha $ip_src $ip_dst $ttl af85 8510`
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=06
expect_pkt=`build_icmp_request 000006080601 000006080701 $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# delete patchport to test if the patchport can be rebuild.
port_del hv2 $patchport || exit_test
sleep 3
is_port_exist hv2 $patchport || exit_test
# send icmp again(fix ttl) from ext1 to lsp-portA through edge1(hv2)
ip_src=`ip_to_hex 192 168 100 6`
ip_dst=`ip_to_hex 10 10 1 2`
ttl=07
packet=`build_icmp_request $src_mac $reply_ha $ip_src $ip_dst $ttl af85 8510`
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=05
expect_pkt=`build_icmp_request 000006080601 000006080701 $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# delete patchport and peer port to test if those ports can be rebuild.
port_del hv2 $patchport || exit_test
port_del hv2 $peer_patchport || exit_test
sleep 3
is_port_exist hv2 $patchport || exit_test
is_port_exist hv2 $peer_patchport || exit_test
# send icmp again(fix ttl) from ext1 to lsp-portA through edge1(hv2)
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

# delete hv2 br0 bridge
net_dropout phy hv2 || exit_test
sleep 2
is_port_exist hv2 $patchport || exit_test
! is_port_exist hv2 $peer_patchport || exit_test
net_join phy hv2 || exit_test
update_arp_table hv2 192.168.100.3
flush_arp "hv1 hv2" # flush arp first before installing arp table
install_arp

# disable bfd here because we don't want ovs bfd issue break the testing
disable_bfd hv2 hv1
disable_bfd hv1 hv2
wait_for_flows_unchange
is_port_exist hv2 $patchport || exit_test
is_port_exist hv2 $peer_patchport || exit_test
# send icmp again(fix ttl) from ext1 to lsp-portA through edge1(hv2)
ip_src=`ip_to_hex 192 168 100 6`
ip_dst=`ip_to_hex 10 10 1 2`
ttl=05
packet=`build_icmp_request $src_mac $reply_ha $ip_src $ip_dst $ttl af85 8510`
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=03
expect_pkt=`build_icmp_request 000006080601 000006080701 $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

remove_ecmp_road hv2 192.168.100.51/24 || exit_test
wait_for_flows_unchange # waiting for install flows
! is_port_exist hv2 $patchport || exit_test
! is_port_exist hv2 $peer_patchport || exit_test

init_ecmp_road hv2 192.168.100.51/24 10.10.0.0/16 192.168.100.1 || exit_test
wait_for_flows_unchange # waiting for install flows

is_port_exist hv2 $patchport || exit_test
is_port_exist hv2 $peer_patchport || exit_test
# send icmp again(fix ttl) from ext1 to lsp-portA through edge1(hv2)
ip_src=`ip_to_hex 192 168 100 6`
ip_dst=`ip_to_hex 10 10 1 2`
ttl=04
packet=`build_icmp_request $src_mac $reply_ha $ip_src $ip_dst $ttl af85 8510`
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
ttl=02
expect_pkt=`build_icmp_request 000006080601 000006080701 $ip_src $ip_dst $ttl b185 8510`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# delete the br0 bridge
net_dropout phy hv2 || exit_test
sleep 2
is_port_exist hv2 $patchport || exit_test
# remove the patchport in etcd, NOTE: tp_LS_outside1 was create by init_ecmp_road
tpctl lsp del tp_LS_outside1 $patchport || exit_test
wait_for_flows_unchange
! is_port_exist hv2 $patchport || exit_test
! is_port_exist hv2 $peer_patchport || exit_test

pass_test
