#!/bin/bash
. env_utils.sh

env_init ${0##*/} # 0##*/ is the filename
sim_create hv1 || exit_test
sim_create hv2 || exit_test
sim_create hv-agent || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test
net_join phy hv2 || exit_test
net_join phy hv-agent || exit_test

# create logical switch and logical router first
etcd_ls_add LS-A
etcd_ls_add LS-B
etcd_lr_add LR-A

# create agent which help to redirect traffic
etcd_lr_add LR-agent hv-agent

# enable ONDEMAND feature
start_tuplenet_daemon hv1 192.168.100.1
start_tuplenet_daemon hv2 192.168.100.2
ONDEMAND=0 start_tuplenet_daemon hv-agent 192.168.100.10
install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv1 lsp-portA || exit_test
port_add hv2 lsp-portB || exit_test
port_add hv1 lsp-portC || exit_test

max_port_num=16
i=1
while [ $i -le $max_port_num ]; do
    mac_hex=`int_to_hex $i`
    port_add hv2 lsp-portT${i} || exit_test
    etcd_lsp_add LS-B lsp-portT${i} 10.10.2.${i} 00:00:06:08:11:${mac_hex}
    i=$((i+1))
done

# link LS-A to LR-A
etcd_ls_link_lr LS-A LR-A 10.10.1.1 24 00:00:06:08:06:01
# link LS-B to LR-A
etcd_ls_link_lr LS-B LR-A 10.10.2.250 24 00:00:06:08:06:02
# create logical switch port
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:06:03
etcd_lsp_add LS-B lsp-portB 10.10.2.252 00:00:06:08:06:04
etcd_lsp_add LS-A lsp-portC 10.10.1.3 00:00:06:08:06:05
wait_for_flows_unchange # waiting for install flows

# send packet from lsp-portA to lsp-portB which on same host & LS
# The lsp-portC should receive icmp immediately
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 1 3`
ttl=09
packet=`build_icmp_request 000006080603 000006080605 $ip_src $ip_dst $ttl 5b91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
sleep 0.1 # wait for packet
expect_pkt="$packet"
real_pkt=`get_tx_pkt hv1 lsp-portC`
verify_pkt $expect_pkt $real_pkt || exit_test

# send packet from lsp-portA to 10.10.1.1 to acquire icmp response
# The lsp-portA should receive icmp feedback immediately
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 1 1`
ttl=fe
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b93 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
sleep 0.1 # wait for packet
expect_pkt=`build_icmp_response 000006080601 000006080603 $ip_dst $ip_src $ttl 5b93 8d10`
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# send packet from lsp-portA to lsp-portB which on another host & LS
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 252`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
sleep 1.5 # wait for packet
ttl=08
expect_pkt=`build_icmp_request 000006080602 000006080604 $ip_src $ip_dst $ttl 5c91 8510`
real_pkt=`get_tx_pkt hv2 lsp-portB`
verify_pkt $expect_pkt $real_pkt || exit_test


# send icmp to unknow dst to give stress to tuplenet
while [ 1 ]; do
    mac_hex=`int_to_hex $i`
    ip_src=`ip_to_hex 10 10 1 2`
    ip_dst=`ip_to_hex 10 10 2 77`
    ttl=09
    packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b91 8510`
    inject_pkt hv1 lsp-portA "$packet" || exit_test

    ip_dst=`ip_to_hex 10 10 2 88`
    packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b91 8510`
    inject_pkt hv1 lsp-portA "$packet" || exit_test

    ip_dst=`ip_to_hex 10 10 2 99`
    packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b91 8510`
    inject_pkt hv1 lsp-portA "$packet" || exit_test
done &

sleep 2

i=1
while [ $i -le $max_port_num ]; do
    mac_hex=`int_to_hex $i`
    ip_src=`ip_to_hex 10 10 1 2`
    ip_dst=`ip_to_hex 10 10 2 $i`
    ttl=09
    packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b91 8510`
    inject_pkt hv1 lsp-portA "$packet" || exit_test
    i=$((i+1))
done

sleep 0.1 # wait for packet

i=1
while [ $i -le $max_port_num ]; do
    mac_hex=`int_to_hex $i`
    ip_src=`ip_to_hex 10 10 1 2`
    ip_dst=`ip_to_hex 10 10 2 $i`
    ttl=09
    packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b91 8510`
    ttl=08
    expect_pkt=`build_icmp_request 000006080602 0000060811${mac_hex} $ip_src $ip_dst $ttl 5c91 8510`
    real_pkt=`get_tx_pkt hv2 lsp-portT${i}`
    verify_pkt $expect_pkt $real_pkt || exit_test
    i=$((i+1))
done

pass_test
