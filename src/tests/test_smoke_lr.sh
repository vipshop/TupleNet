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

etcd_ls_add LS-A

# create agent which help to redirect traffic
etcd_lr_add LR-agent hv3

start_tuplenet_daemon hv1 192.168.100.1
start_tuplenet_daemon hv2 192.168.100.2
ONDEMAND=0 start_tuplenet_daemon hv3 192.168.100.3
install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv1 lsp-portA || exit_test
port_add hv2 lsp-portB || exit_test

prev_LS=LS-A
max_lr_num=20 # we cannot make it 50 or bigger, because the ovs may treat the packet as a recircle packet
last_subnet_id=$((max_lr_num+1))
i=1
while [ $i -le $max_lr_num ]; do
    current_LR=LR-$i
    next_LS=LS-$i
    pre_subnet=10.10.${i}.2
    pre_hop=10.10.${i}.1
    n=$((i+1))
    next_subnet=10.10.${n}.1
    next_hop=10.10.${n}.2
    mac_hex=`int_to_hex $i`
    etcd_lr_add $current_LR
    etcd_ls_add $next_LS
    etcd_ls_link_lr $prev_LS $current_LR $pre_subnet 24 00:00:06:08:06:$mac_hex
    etcd_ls_link_lr $next_LS $current_LR $next_subnet 24 00:00:06:08:05:$mac_hex
    if [ $i != $max_lr_num ]; then
        etcd_lsr_add $current_LR 10.10.${last_subnet_id}.0 24 $next_hop ${current_LR}_to_${next_LS}
    fi
    if [ $i != 1 ]; then
        etcd_lsr_add $current_LR 10.10.1.0 24 $pre_hop ${current_LR}_to_${prev_LS}
    fi
    prev_LS=$next_LS
    i=$((i+1))
done

# create logical switch port
etcd_lsp_add LS-A lsp-portA 10.10.1.5 00:00:06:08:07:03
etcd_lsp_add $next_LS lsp-portB 10.10.${last_subnet_id}.3 00:00:06:08:07:04
wait_for_flows_unchange 10 # waiting for install flows

ip_src=`ip_to_hex 10 10 1 5`
ip_dst=`ip_to_hex 10 10 $last_subnet_id 3`
ttl=fe
packet=`build_icmp_request 000006080703 000006080601 $ip_src $ip_dst $ttl 528d 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet

ttl=ea
expect_pkt=`build_icmp_request 0000060805${mac_hex} 000006080704 $ip_src $ip_dst $ttl 668d 8510`
real_pkt=`get_tx_pkt hv2 lsp-portB`
verify_pkt $expect_pkt $real_pkt || exit_test

ip_src=`ip_to_hex 10 10 1 5`
ip_dst=`ip_to_hex 10 10 $last_subnet_id 1`
ttl=fe
packet=`build_icmp_request 000006080703 000006080601 $ip_src $ip_dst $ttl 528f 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=eb
expect_pkt=`build_icmp_response 000006080601 000006080703 $ip_dst $ip_src $ttl 658f 8d10`
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

pass_test
