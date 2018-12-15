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
LS_NUM=200
i=0
while [ $i -lt $LS_NUM ]; do
    etcd_ls_add LS-A$i
    i=$((i+1))
done

# create agent which help to redirect traffic
etcd_lr_add LR-agent hv3

start_tuplenet_daemon hv1 192.168.100.1
start_tuplenet_daemon hv2 192.168.100.2
ONDEMAND=0 start_tuplenet_daemon hv3 192.168.100.3
install_arp
wait_for_brint # waiting for building br-int bridge

i=0
while [ $i -lt $LS_NUM ]; do
    port_add hv1 lsp-portA$i || exit_test
    port_add hv2 lsp-portB$i || exit_test
    etcd_lsp_add LS-A$i lsp-portA$i 10.10.1.2 00:00:06:08:06:01
    etcd_lsp_add LS-A$i lsp-portB$i 10.10.1.3 00:00:06:08:06:03
    i=$((i+1))
done

wait_for_flows_unchange 10 # waiting for installing flows

# send icmp from lsp-portA to lsp-portB
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 1 3`
ttl=09
packet=`build_icmp_request 000006080601 000006080603 $ip_src $ip_dst $ttl 5b91 8510`
i=0
while [ $i -lt $LS_NUM ]; do
    inject_pkt hv1 lsp-portA$i "$packet" || exit_test
    # this block of code is for ONDEMAND feature.
    # pydatalog cost time to generate flows
    if [ $i == 0 ]; then
        sleep 1 # wait for touching lsp/chassis
    fi
    # end of block
    wait_for_packet
    expect_pkt=$packet
    real_pkt=`get_tx_pkt hv2 lsp-portB$i`
    verify_pkt $expect_pkt $real_pkt || exit_test
    i=$((i+1))
done

pass_test
