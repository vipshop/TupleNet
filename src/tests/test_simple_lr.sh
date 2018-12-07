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

# build a agent_LR to help redirect traffic
etcd_lr_add agent_LR hv3

start_tuplenet_daemon hv1 192.168.100.1
start_tuplenet_daemon hv2 192.168.100.2
ONDEMAND=0 start_tuplenet_daemon hv3 192.168.100.3
install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv1 lsp-portA || exit_test
port_add hv2 lsp-portB || exit_test
port_add hv1 lsp-portC || exit_test
# link LS-A to LR-A
etcd_ls_link_lr LS-A LR-A 10.10.1.1 24 00:00:06:08:06:01
# link LS-B to LR-A
etcd_ls_link_lr LS-B LR-A 10.10.2.1 24 00:00:06:08:06:02
# create logical switch port
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:06:03
etcd_lsp_add LS-B lsp-portB 10.10.2.3 00:00:06:08:06:04
etcd_lsp_add LS-B lsp-portC 10.10.2.4 00:00:06:08:06:05
wait_for_flows_unchange # waiting for install flows

ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 3`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=08
expect_pkt=`build_icmp_request 000006080602 000006080604 $ip_src $ip_dst $ttl 5c91 8510`
real_pkt=`get_tx_pkt hv2 lsp-portB`
verify_pkt $expect_pkt $real_pkt || exit_test

ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 4`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=08
expect_pkt=`build_icmp_request 000006080602 000006080605 $ip_src $ip_dst $ttl 5c91 8510`
real_pkt=`get_tx_pkt hv1 lsp-portC`
verify_pkt $expect_pkt $real_pkt || exit_test

pass_test
