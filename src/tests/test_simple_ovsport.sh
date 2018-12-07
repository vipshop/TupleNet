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

# create agent which help to redirect traffic
etcd_lr_add LR-agent hv3

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
etcd_lsp_add LS-B lsp-portD 10.10.2.5 00:00:06:08:06:06

# change iface-id to a random string
modify_port_iface_random_id hv2 lsp-portB || exit_test
wait_for_flows_unchange # waiting for install flows
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 3`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5a91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
expect_pkt="" # should not receive packet
real_pkt=`get_tx_pkt hv2 lsp-portB`
verify_pkt $expect_pkt $real_pkt || exit_test

# change iface_id to random string and change back to lsp-portB
modify_port_iface_random_id hv2 lsp-portB || exit_test
sleep 1
modify_port_iface_random_id hv2 lsp-portB || exit_test
sleep 1
modify_port_iface_random_id hv2 lsp-portB || exit_test
sleep 1
modify_port_iface_id hv2 lsp-portB lsp-portB || exit_test
wait_for_flows_unchange # waiting for install flows
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 3`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5a91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=08
expect_pkt=`build_icmp_request 000006080602 000006080604 $ip_src $ip_dst $ttl 5b91 8510`
real_pkt=`get_tx_pkt hv2 lsp-portB`
verify_pkt $expect_pkt $real_pkt || exit_test

port_del hv1 lsp-portC || exit_test
wait_for_flows_unchange # waiting for install flows
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 4`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5a90 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=08
expect_pkt="" # should not receive packet
real_pkt=`get_tx_pkt hv1 lsp-portC`
verify_pkt $expect_pkt $real_pkt || exit_test

port_add hv1 lsp-portC || exit_test
wait_for_flows_unchange # waiting for install flows
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 4`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5a90 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=08
expect_pkt=`build_icmp_request 000006080602 000006080605 $ip_src $ip_dst $ttl 5b90 8510`
real_pkt=`get_tx_pkt hv1 lsp-portC`
verify_pkt $expect_pkt $real_pkt || exit_test

port_add hv1 lsp-portD || exit_test
modify_port_iface_random_id hv1 lsp-portD || exit_test
modify_port_iface_random_id hv1 lsp-portD || exit_test
modify_port_iface_id hv1 lsp-portD lsp-portD || exit_test
wait_for_flows_unchange # waiting for install flows
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 5`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5a8f 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=08
expect_pkt=`build_icmp_request 000006080602 000006080606 $ip_src $ip_dst $ttl 5b8f 8510`
real_pkt=`get_tx_pkt hv1 lsp-portD`
verify_pkt $expect_pkt $real_pkt || exit_test

pass_test
