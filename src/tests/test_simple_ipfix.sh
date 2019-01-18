#!/bin/bash
. env_utils.sh

env_init ${0##*/} # 0##*/ is the filename
sim_create hv1 || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test

# create logical switch first
tpctl ls add LS-A || exit_test

ONDEMAND=0 IPFIX_COLLECTOR=127.0.0.1:4379 IPFIX_SAMPLING_RATE=1 \
start_tuplenet_daemon hv1 192.168.100.1

install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv1 lsp-port1 || exit_test
port_add hv1 lsp-port2 || exit_test
tpctl lsp add LS-A lsp-port1 10.10.1.2 00:00:06:08:06:01 || exit_test
tpctl lsp add LS-A lsp-port2 10.10.1.3 00:00:06:08:06:03 || exit_test

wait_for_flows_unchange # waiting for installing flows

# send icmp from lsp-portA to lsp-portB
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 1 3`
packet=`build_icmp_request 000006080601 000006080603 $ip_src $ip_dst 09 5b91 8510`
for i in `seq 1 10`;do
    inject_pkt hv1 lsp-port1 "$packet" || exit_test
done

ovs_setenv hv1
result="$(ovs-ofctl dump-ipfix-bridge br-int | sed -nr 's/^ *bridge ipfix: (.+)/\1/p' | sed 's|, |\n|g')"
expected="
flows=20
current flows=0
sampled pkts=20
ipv4 ok=20
ipv6 ok=0
tx pkts=20
"
equal_str "$result" "$expected" || exit_test

pass_test
