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
hv_array=(hv1 hv2 hv3)

etcd_ls_add LS-A

ONDEMAND=0 start_tuplenet_daemon hv1 192.168.100.1
ONDEMAND=0 start_tuplenet_daemon hv2 192.168.100.2
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
    idx=$((i%3))
    current_hv=${hv_array[$idx]}
    current_LR=LR-$i
    next_LS=LS-$i
    pre_subnet=10.10.${i}.2
    pre_hop=10.10.${i}.1
    n=$((i+1))
    next_subnet=10.10.${n}.1
    next_hop=10.10.${n}.2
    mac_hex=`int_to_hex $i`
    etcd_lr_add $current_LR $current_hv
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
wait_for_flows_unchange # waiting for install flows

ip_src=`ip_to_hex 10 10 1 5`
ip_dst=`ip_to_hex 10 10 $last_subnet_id 3`
ttl=fe
packet=`build_icmp_request 000006080703 000006080601 $ip_src $ip_dst $ttl 528d 8510`

# this packet is for generating flows in ONDEMAND mode
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
wait_for_packet # wait for packet

real_path=`inject_trace_packet hv1 lsp-portA "$packet"`
ttl=ea
expect_pkt=`build_icmp_request 0000060805${mac_hex} 000006080704 $ip_src $ip_dst $ttl 668d 8510`
real_pkt=`get_tx_last_pkt hv2 lsp-portB`
wait_for_packet # wait for packet
verify_pkt $expect_pkt $real_pkt || exit_test

expect_path="type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-1,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-1,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv2
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-1,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-1,from:LR-1_to_LS-A,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv2
type:LR,pipeline:LR-1,from:LR-1_to_LS-A,to:LR-1_to_LS-1,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-1,from:LR-1_to_LS-A,to:LR-1_to_LS-1,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv2
type:LR,pipeline:LR-1,from:LR-1_to_LS-1,to:LR-1_to_LS-1,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-1,from:LS-1_to_LR-1,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv2
type:LS,pipeline:LS-1,from:LS-1_to_LR-1,to:LS-1_to_LR-2,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-1,from:LS-1_to_LR-1,to:LS-1_to_LR-2,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv3
type:LS,pipeline:LS-1,from:LS-1_to_LR-1,to:LS-1_to_LR-2,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-2,from:LR-2_to_LS-1,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv3
type:LR,pipeline:LR-2,from:LR-2_to_LS-1,to:LR-2_to_LS-2,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-2,from:LR-2_to_LS-1,to:LR-2_to_LS-2,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv3
type:LR,pipeline:LR-2,from:LR-2_to_LS-2,to:LR-2_to_LS-2,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-2,from:LS-2_to_LR-2,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv3
type:LS,pipeline:LS-2,from:LS-2_to_LR-2,to:LS-2_to_LR-3,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-2,from:LS-2_to_LR-2,to:LS-2_to_LR-3,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1
type:LS,pipeline:LS-2,from:LS-2_to_LR-2,to:LS-2_to_LR-3,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-3,from:LR-3_to_LS-2,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv1
type:LR,pipeline:LR-3,from:LR-3_to_LS-2,to:LR-3_to_LS-3,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-3,from:LR-3_to_LS-2,to:LR-3_to_LS-3,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv1
type:LR,pipeline:LR-3,from:LR-3_to_LS-3,to:LR-3_to_LS-3,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-3,from:LS-3_to_LR-3,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1
type:LS,pipeline:LS-3,from:LS-3_to_LR-3,to:LS-3_to_LR-4,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-3,from:LS-3_to_LR-3,to:LS-3_to_LR-4,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv2
type:LS,pipeline:LS-3,from:LS-3_to_LR-3,to:LS-3_to_LR-4,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-4,from:LR-4_to_LS-3,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv2
type:LR,pipeline:LR-4,from:LR-4_to_LS-3,to:LR-4_to_LS-4,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-4,from:LR-4_to_LS-3,to:LR-4_to_LS-4,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv2
type:LR,pipeline:LR-4,from:LR-4_to_LS-4,to:LR-4_to_LS-4,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-4,from:LS-4_to_LR-4,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv2
type:LS,pipeline:LS-4,from:LS-4_to_LR-4,to:LS-4_to_LR-5,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-4,from:LS-4_to_LR-4,to:LS-4_to_LR-5,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv3
type:LS,pipeline:LS-4,from:LS-4_to_LR-4,to:LS-4_to_LR-5,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-5,from:LR-5_to_LS-4,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv3
type:LR,pipeline:LR-5,from:LR-5_to_LS-4,to:LR-5_to_LS-5,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-5,from:LR-5_to_LS-4,to:LR-5_to_LS-5,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv3
type:LR,pipeline:LR-5,from:LR-5_to_LS-5,to:LR-5_to_LS-5,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-5,from:LS-5_to_LR-5,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv3
type:LS,pipeline:LS-5,from:LS-5_to_LR-5,to:LS-5_to_LR-6,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-5,from:LS-5_to_LR-5,to:LS-5_to_LR-6,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1
type:LS,pipeline:LS-5,from:LS-5_to_LR-5,to:LS-5_to_LR-6,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-6,from:LR-6_to_LS-5,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv1
type:LR,pipeline:LR-6,from:LR-6_to_LS-5,to:LR-6_to_LS-6,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-6,from:LR-6_to_LS-5,to:LR-6_to_LS-6,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv1
type:LR,pipeline:LR-6,from:LR-6_to_LS-6,to:LR-6_to_LS-6,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-6,from:LS-6_to_LR-6,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1
type:LS,pipeline:LS-6,from:LS-6_to_LR-6,to:LS-6_to_LR-7,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-6,from:LS-6_to_LR-6,to:LS-6_to_LR-7,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv2
type:LS,pipeline:LS-6,from:LS-6_to_LR-6,to:LS-6_to_LR-7,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-7,from:LR-7_to_LS-6,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv2
type:LR,pipeline:LR-7,from:LR-7_to_LS-6,to:LR-7_to_LS-7,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-7,from:LR-7_to_LS-6,to:LR-7_to_LS-7,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv2
type:LR,pipeline:LR-7,from:LR-7_to_LS-7,to:LR-7_to_LS-7,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-7,from:LS-7_to_LR-7,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv2
type:LS,pipeline:LS-7,from:LS-7_to_LR-7,to:LS-7_to_LR-8,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-7,from:LS-7_to_LR-7,to:LS-7_to_LR-8,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv3
type:LS,pipeline:LS-7,from:LS-7_to_LR-7,to:LS-7_to_LR-8,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-8,from:LR-8_to_LS-7,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv3
type:LR,pipeline:LR-8,from:LR-8_to_LS-7,to:LR-8_to_LS-8,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-8,from:LR-8_to_LS-7,to:LR-8_to_LS-8,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv3
type:LR,pipeline:LR-8,from:LR-8_to_LS-8,to:LR-8_to_LS-8,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-8,from:LS-8_to_LR-8,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv3
type:LS,pipeline:LS-8,from:LS-8_to_LR-8,to:LS-8_to_LR-9,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-8,from:LS-8_to_LR-8,to:LS-8_to_LR-9,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1
type:LS,pipeline:LS-8,from:LS-8_to_LR-8,to:LS-8_to_LR-9,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-9,from:LR-9_to_LS-8,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv1
type:LR,pipeline:LR-9,from:LR-9_to_LS-8,to:LR-9_to_LS-9,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-9,from:LR-9_to_LS-8,to:LR-9_to_LS-9,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv1
type:LR,pipeline:LR-9,from:LR-9_to_LS-9,to:LR-9_to_LS-9,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-9,from:LS-9_to_LR-9,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1
type:LS,pipeline:LS-9,from:LS-9_to_LR-9,to:LS-9_to_LR-10,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-9,from:LS-9_to_LR-9,to:LS-9_to_LR-10,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv2
type:LS,pipeline:LS-9,from:LS-9_to_LR-9,to:LS-9_to_LR-10,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-10,from:LR-10_to_LS-9,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv2
type:LR,pipeline:LR-10,from:LR-10_to_LS-9,to:LR-10_to_LS-10,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-10,from:LR-10_to_LS-9,to:LR-10_to_LS-10,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv2
type:LR,pipeline:LR-10,from:LR-10_to_LS-10,to:LR-10_to_LS-10,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-10,from:LS-10_to_LR-10,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv2
type:LS,pipeline:LS-10,from:LS-10_to_LR-10,to:LS-10_to_LR-11,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-10,from:LS-10_to_LR-10,to:LS-10_to_LR-11,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv3
type:LS,pipeline:LS-10,from:LS-10_to_LR-10,to:LS-10_to_LR-11,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-11,from:LR-11_to_LS-10,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv3
type:LR,pipeline:LR-11,from:LR-11_to_LS-10,to:LR-11_to_LS-11,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-11,from:LR-11_to_LS-10,to:LR-11_to_LS-11,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv3
type:LR,pipeline:LR-11,from:LR-11_to_LS-11,to:LR-11_to_LS-11,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-11,from:LS-11_to_LR-11,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv3
type:LS,pipeline:LS-11,from:LS-11_to_LR-11,to:LS-11_to_LR-12,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-11,from:LS-11_to_LR-11,to:LS-11_to_LR-12,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1
type:LS,pipeline:LS-11,from:LS-11_to_LR-11,to:LS-11_to_LR-12,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-12,from:LR-12_to_LS-11,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv1
type:LR,pipeline:LR-12,from:LR-12_to_LS-11,to:LR-12_to_LS-12,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-12,from:LR-12_to_LS-11,to:LR-12_to_LS-12,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv1
type:LR,pipeline:LR-12,from:LR-12_to_LS-12,to:LR-12_to_LS-12,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-12,from:LS-12_to_LR-12,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1
type:LS,pipeline:LS-12,from:LS-12_to_LR-12,to:LS-12_to_LR-13,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-12,from:LS-12_to_LR-12,to:LS-12_to_LR-13,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv2
type:LS,pipeline:LS-12,from:LS-12_to_LR-12,to:LS-12_to_LR-13,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-13,from:LR-13_to_LS-12,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv2
type:LR,pipeline:LR-13,from:LR-13_to_LS-12,to:LR-13_to_LS-13,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-13,from:LR-13_to_LS-12,to:LR-13_to_LS-13,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv2
type:LR,pipeline:LR-13,from:LR-13_to_LS-13,to:LR-13_to_LS-13,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-13,from:LS-13_to_LR-13,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv2
type:LS,pipeline:LS-13,from:LS-13_to_LR-13,to:LS-13_to_LR-14,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-13,from:LS-13_to_LR-13,to:LS-13_to_LR-14,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv3
type:LS,pipeline:LS-13,from:LS-13_to_LR-13,to:LS-13_to_LR-14,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-14,from:LR-14_to_LS-13,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv3
type:LR,pipeline:LR-14,from:LR-14_to_LS-13,to:LR-14_to_LS-14,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-14,from:LR-14_to_LS-13,to:LR-14_to_LS-14,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv3
type:LR,pipeline:LR-14,from:LR-14_to_LS-14,to:LR-14_to_LS-14,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-14,from:LS-14_to_LR-14,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv3
type:LS,pipeline:LS-14,from:LS-14_to_LR-14,to:LS-14_to_LR-15,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-14,from:LS-14_to_LR-14,to:LS-14_to_LR-15,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1
type:LS,pipeline:LS-14,from:LS-14_to_LR-14,to:LS-14_to_LR-15,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-15,from:LR-15_to_LS-14,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv1
type:LR,pipeline:LR-15,from:LR-15_to_LS-14,to:LR-15_to_LS-15,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-15,from:LR-15_to_LS-14,to:LR-15_to_LS-15,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv1
type:LR,pipeline:LR-15,from:LR-15_to_LS-15,to:LR-15_to_LS-15,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-15,from:LS-15_to_LR-15,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1
type:LS,pipeline:LS-15,from:LS-15_to_LR-15,to:LS-15_to_LR-16,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-15,from:LS-15_to_LR-15,to:LS-15_to_LR-16,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv2
type:LS,pipeline:LS-15,from:LS-15_to_LR-15,to:LS-15_to_LR-16,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-16,from:LR-16_to_LS-15,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv2
type:LR,pipeline:LR-16,from:LR-16_to_LS-15,to:LR-16_to_LS-16,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-16,from:LR-16_to_LS-15,to:LR-16_to_LS-16,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv2
type:LR,pipeline:LR-16,from:LR-16_to_LS-16,to:LR-16_to_LS-16,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-16,from:LS-16_to_LR-16,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv2
type:LS,pipeline:LS-16,from:LS-16_to_LR-16,to:LS-16_to_LR-17,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-16,from:LS-16_to_LR-16,to:LS-16_to_LR-17,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv3
type:LS,pipeline:LS-16,from:LS-16_to_LR-16,to:LS-16_to_LR-17,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-17,from:LR-17_to_LS-16,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv3
type:LR,pipeline:LR-17,from:LR-17_to_LS-16,to:LR-17_to_LS-17,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-17,from:LR-17_to_LS-16,to:LR-17_to_LS-17,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv3
type:LR,pipeline:LR-17,from:LR-17_to_LS-17,to:LR-17_to_LS-17,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-17,from:LS-17_to_LR-17,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv3
type:LS,pipeline:LS-17,from:LS-17_to_LR-17,to:LS-17_to_LR-18,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-17,from:LS-17_to_LR-17,to:LS-17_to_LR-18,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1
type:LS,pipeline:LS-17,from:LS-17_to_LR-17,to:LS-17_to_LR-18,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-18,from:LR-18_to_LS-17,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv1
type:LR,pipeline:LR-18,from:LR-18_to_LS-17,to:LR-18_to_LS-18,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv1
type:LR,pipeline:LR-18,from:LR-18_to_LS-17,to:LR-18_to_LS-18,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv1
type:LR,pipeline:LR-18,from:LR-18_to_LS-18,to:LR-18_to_LS-18,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-18,from:LS-18_to_LR-18,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1
type:LS,pipeline:LS-18,from:LS-18_to_LR-18,to:LS-18_to_LR-19,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1
type:LS,pipeline:LS-18,from:LS-18_to_LR-18,to:LS-18_to_LR-19,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv2
type:LS,pipeline:LS-18,from:LS-18_to_LR-18,to:LS-18_to_LR-19,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-19,from:LR-19_to_LS-18,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv2
type:LR,pipeline:LR-19,from:LR-19_to_LS-18,to:LR-19_to_LS-19,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv2
type:LR,pipeline:LR-19,from:LR-19_to_LS-18,to:LR-19_to_LS-19,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv2
type:LR,pipeline:LR-19,from:LR-19_to_LS-19,to:LR-19_to_LS-19,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-19,from:LS-19_to_LR-19,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv2
type:LS,pipeline:LS-19,from:LS-19_to_LR-19,to:LS-19_to_LR-20,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv2
type:LS,pipeline:LS-19,from:LS-19_to_LR-19,to:LS-19_to_LR-20,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv3
type:LS,pipeline:LS-19,from:LS-19_to_LR-19,to:LS-19_to_LR-20,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-20,from:LR-20_to_LS-19,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv3
type:LR,pipeline:LR-20,from:LR-20_to_LS-19,to:LR-20_to_LS-20,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv3
type:LR,pipeline:LR-20,from:LR-20_to_LS-19,to:LR-20_to_LS-20,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv3
type:LR,pipeline:LR-20,from:LR-20_to_LS-20,to:LR-20_to_LS-20,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-20,from:LS-20_to_LR-20,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv3
type:LS,pipeline:LS-20,from:LS-20_to_LR-20,to:lsp-portB,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv3
type:LS,pipeline:LS-20,from:LS-20_to_LR-20,to:lsp-portB,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv2
type:LS,pipeline:LS-20,from:LS-20_to_LR-20,to:lsp-portB,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv2"

verify_trace "$expect_path" "$real_path" || exit_test

pass_test
