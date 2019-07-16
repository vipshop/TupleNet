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

# create logical switch first
tpctl ls add LS-A

start_tuplenet_daemon hv1 192.168.100.1
start_tuplenet_daemon hv2 192.168.100.2
ONDEMAND=0 start_tuplenet_daemon hv3 192.168.100.3
install_arp
wait_for_brint # waiting for building br-int bridge

sleep 3

restart_ovsdb_daemon hv1 10
restart_ovsdb_daemon hv2 15

tpctl lr add agent_LR hv3

port_add hv1 lsp-portA || exit_test
port_add hv2 lsp-portB || exit_test
tpctl lsp add LS-A lsp-portA 10.10.1.2 00:00:06:08:06:01
tpctl lsp add LS-A lsp-portB 10.10.1.3 00:00:06:08:06:03
wait_for_flows_unchange # waiting for installing flows

# send icmp from lsp-portA to lsp-portB
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 1 3`
ttl=09
packet=`build_icmp_request 000006080601 000006080603 $ip_src $ip_dst $ttl 5b91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
expect_pkt=$packet
wait_for_packet # wait for packet
real_pkt=`get_tx_pkt hv2 lsp-portB`
verify_pkt $expect_pkt $real_pkt || exit_test

for i in `seq 1 50`;do
    port_add hv1 lsp-portC
    port_del hv1 lsp-portC
done

# send icmp from lsp-portA to lsp-portC
port_add hv1 lsp-portC || exit_test
tpctl lsp add LS-A lsp-portC 10.10.1.4 00:00:06:08:06:04
wait_for_flows_unchange # waiting for installing flows
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 1 4`
ttl=09
packet=`build_icmp_request 000006080601 000006080604 $ip_src $ip_dst $ttl 5b91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
expect_pkt=$packet
real_pkt=`get_tx_pkt hv1 lsp-portC`
verify_pkt $expect_pkt $real_pkt || exit_test

pass_test
