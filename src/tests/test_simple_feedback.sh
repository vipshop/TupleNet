#!/bin/bash
. env_utils.sh

env_init ${0##*/} # 0##*/ is the filename
sim_create hv1 || exit_test
sim_create hv2 || exit_test
sim_create hv3 || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test
net_join phy hv2 || exit_test
net_join phy hv3 || exit_test

# create logical switch and logical router first
etcd_ls_add LS-A
etcd_ls_add LS-B
etcd_lr_add LR-A
etcd_lr_add LR-carrier hv3

start_tuplenet_daemon hv1 192.168.100.1
start_tuplenet_daemon hv2 192.168.100.2
ONDEMAND=0 start_tuplenet_daemon hv3 192.168.100.3
install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv1 lsp-portA || exit_test
port_add hv2 lsp-portB || exit_test
port_add hv2 lsp-portC || exit_test
# link LS-A to LR-A
etcd_ls_link_lr LS-A LR-A 10.10.1.1 24 00:00:06:08:06:01
# link LS-B to LR-A
etcd_ls_link_lr LS-B LR-A 10.10.2.1 24 00:00:06:08:06:02
# create logical switch port
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:06:03
etcd_lsp_add LS-B lsp-portB 10.10.2.3 00:00:06:08:06:04
etcd_lsp_add LS-A lsp-portC 10.10.1.3 00:00:06:08:06:05
wait_for_flows_unchange # waiting for install flows

# send arp packet to request feedback
sha=000006080603
spa=`ip_to_hex 10 10 1 2`
tpa=`ip_to_hex 10 10 1 1`
# build arp request
packet=ffffffffffff${sha}08060001080006040001${sha}${spa}ffffffffffff${tpa}
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
# build arp feedback
reply_ha=000006080601
expect_pkt=${sha}${reply_ha}08060001080006040002${reply_ha}${tpa}${sha}${spa}
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# send arp packet to request feedback
sha=000006080603
spa=`ip_to_hex 10 10 1 2`
tpa=`ip_to_hex 10 10 1 3`
# build arp request
packet=ffffffffffff${sha}08060001080006040001${sha}${spa}ffffffffffff${tpa}
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
# build arp feedback
reply_ha=000006080605
expect_pkt="$expect_pkt ${sha}${reply_ha}08060001080006040002${reply_ha}${tpa}${sha}${spa}"
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# send icmp packet to request feedback
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 1 1`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b93 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=fe
expect_pkt="$expect_pkt `build_icmp_response 000006080601 000006080603 $ip_dst $ip_src $ttl 6692 8d10`"
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# send icmp packet to request feedback
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 1`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b93 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=fe
expect_pkt="$expect_pkt `build_icmp_response 000006080601 000006080603 $ip_dst $ip_src $ttl 6692 8d10`"
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

pass_test
