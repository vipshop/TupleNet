#!/bin/bash
. env_utils.sh

export RUNTEST=1 # it tells tuplenet your are in test mode
                 # the tuplenet will sort ovs-flows before
                 # inserting into ovs

env_init ${0##*/} # 0##*/ is the filename
sim_create hv1 || exit_test
sim_create hv2 || exit_test
sim_create hv3 || exit_test
sim_create hv4 || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test
net_join phy hv2 || exit_test
net_join phy hv3 || exit_test
net_join phy hv4 || exit_test

# create logical switch and logical router first
etcd_ls_add LS-A
etcd_ls_add LS-B
etcd_lr_add LR-A
etcd_ls_add m1
etcd_ls_add m2
etcd_lr_add edge1 hv2
etcd_lr_add edge2 hv3
etcd_ls_add outside1
etcd_ls_add outside2

start_tuplenet_daemon hv1 192.168.100.1
start_tuplenet_daemon hv4 192.168.100.4
ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv2 192.168.100.2
ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv3 192.168.100.3
install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv1 lsp-portA || exit_test
port_add hv2 lsp-portB || exit_test
port_add hv3 lsp-portC || exit_test

# link LS-A to LR-A
etcd_ls_link_lr LS-A LR-A 10.10.1.1 24 00:00:06:08:06:01
# link LS-B to LR-A
etcd_ls_link_lr LS-B LR-A 10.10.2.1 24 00:00:06:08:06:02
# link m1 to LR-A
etcd_ls_link_lr m1 LR-A 100.10.10.1 24 00:00:06:08:06:03
# link m2 to LR-A
etcd_ls_link_lr m2 LR-A 100.10.10.3 24 00:00:06:08:06:04
# link m1 to edge1
etcd_ls_link_lr m1 edge1 100.10.10.2 24 00:00:06:08:06:05
# link m2 to edge2
etcd_ls_link_lr m2 edge2 100.10.10.2 24 00:00:06:08:06:06
# link outside1 to edge1
etcd_ls_link_lr outside1 edge1 172.20.11.11 24 00:00:06:08:06:07
# link outside2 to edge2
etcd_ls_link_lr outside2 edge2 172.20.11.12 24 00:00:06:08:06:08

# set static route on LR-A, the route is ecmp route
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m1"
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m2"
# set static route on edge1
etcd_lsr_add edge1 10.10.0.0 16 100.10.10.1 edge1_to_m1
# set static route on edge2
etcd_lsr_add edge2 10.10.0.0 16 100.10.10.3 edge2_to_m2

# create logical switch port
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:07:01
etcd_lsp_add LS-B lsp-portB 10.10.2.3 00:00:06:08:07:02
etcd_lsp_add LS-A lsp-portC 10.10.1.3 00:00:06:08:07:03
wait_for_flows_unchange # waiting for install flows

# send arp to unknow dst
sha=000006080701
spa=`ip_to_hex 10 10 1 2`
tpa=`ip_to_hex 10 10 1 9`
# build arp request
packet=ffffffffffff${sha}08060001080006040001${sha}${spa}ffffffffffff${tpa}
real_path=`inject_trace_packet lsp-portA $packet`
wait_for_packet # wait for packet
# we don't update expect_pkt, because we won't expect receiving arp back
verify_pkt $expect_pkt $real_pkt || exit_test
# ondemand & redirect feature will direct traffic to other chassis
if [[ -z "$ONDEMAND" || "$ONDEMAND" == 1 ]]; then
    expect_path="type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1,output_iface_id:<INVALID_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_OUTPUT_PKT,chassis:hv1,output_iface_id:hv3
type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv3,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_DROP_PACKET,chassis:hv3,output_iface_id:<UNK_PORT>"
else
    expect_path="type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_DROP_PACKET,chassis:hv1,output_iface_id:<UNK_PORT>"
fi
verify_trace "$expect_path" "$real_path" || exit_test


# send arp to lsp-portC
sha=000006080701
spa=`ip_to_hex 10 10 1 2`
tpa=`ip_to_hex 10 10 1 3`
# build arp request
packet=ffffffffffff${sha}08060001080006040001${sha}${spa}ffffffffffff${tpa}
real_path=`inject_trace_packet lsp-portA $packet`
wait_for_packet # wait for packet
# build arp feedback
reply_ha=000006080703
expect_pkt=${sha}${reply_ha}08060001080006040002${reply_ha}${tpa}${sha}${spa}
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test
# ondemand & redirect feature will direct traffic to other chassis
if [[ -z "$ONDEMAND" || "$ONDEMAND" == 1 ]]; then
    expect_path="type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1,output_iface_id:<INVALID_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_OUTPUT_PKT,chassis:hv1,output_iface_id:hv3
type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv3,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:lsp-portA,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv3,output_iface_id:hv1
type:LS,pipeline:LS-A,from:lsp-portA,to:lsp-portA,stage:TABLE_OUTPUT_PKT,chassis:hv3,output_iface_id:hv1
type:LS,pipeline:LS-A,from:lsp-portA,to:lsp-portA,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:lsp-portA,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:lsp-portA,stage:TABLE_OUTPUT_PKT,chassis:hv1,output_iface_id:<UNK_PORT>"
else
    expect_path="type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:lsp-portA,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:lsp-portA,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:lsp-portA,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:lsp-portA,stage:TABLE_OUTPUT_PKT,chassis:hv1,output_iface_id:<UNK_PORT>"
fi
verify_trace "$expect_path" "$real_path" || exit_test


# send icmp to edge1 from hv1
real_path=`inject_trace_packet lsp-portA 00:00:06:08:07:01 10.10.1.2 00:00:06:08:06:01 172.20.11.11`
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 172 20 11 11`
ttl=fd
expect_pkt=`build_icmp_response 000006080601 000006080701 $ip_dst $ip_src $ttl bb7d 8d10`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
wait_for_packet # wait for packet
wait_for_packet # wait for packet
wait_for_packet # wait for packet
verify_pkt $expect_pkt $real_pkt || exit_test

expect_path="type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-A,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-A,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-A,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m1,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv1,output_iface_id:hv2
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m1,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv1,output_iface_id:hv2
type:LR,pipeline:LR-A,from:LR-A_to_m1,to:LR-A_to_m1,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv1,output_iface_id:hv2
type:LS,pipeline:m1,from:m1_to_LR-A,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1,output_iface_id:hv2
type:LS,pipeline:m1,from:m1_to_LR-A,to:m1_to_edge1,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1,output_iface_id:hv2
type:LS,pipeline:m1,from:m1_to_LR-A,to:m1_to_edge1,stage:TABLE_OUTPUT_PKT,chassis:hv1,output_iface_id:hv2
type:LS,pipeline:m1,from:m1_to_LR-A,to:m1_to_edge1,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv2,output_iface_id:<UNK_PORT>
type:LS,pipeline:m1,from:m1_to_LR-A,to:m1_to_edge1,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv2,output_iface_id:<UNK_PORT>
type:LR,pipeline:edge1,from:edge1_to_m1,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv2,output_iface_id:<UNK_PORT>
type:LR,pipeline:edge1,from:edge1_to_m1,to:edge1_to_m1,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv2,output_iface_id:<UNK_PORT>
type:LR,pipeline:edge1,from:edge1_to_m1,to:edge1_to_m1,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv2,output_iface_id:<UNK_PORT>
type:LR,pipeline:edge1,from:edge1_to_m1,to:edge1_to_m1,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv2,output_iface_id:<UNK_PORT>
type:LS,pipeline:m1,from:m1_to_edge1,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv2,output_iface_id:<UNK_PORT>
type:LS,pipeline:m1,from:m1_to_edge1,to:m1_to_LR-A,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv2,output_iface_id:<UNK_PORT>
type:LS,pipeline:m1,from:m1_to_edge1,to:m1_to_LR-A,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv2,output_iface_id:<UNK_PORT>
type:LS,pipeline:m1,from:m1_to_edge1,to:m1_to_LR-A,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv2,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_m1,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv2,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_m1,to:LR-A_to_LS-A,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv2,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_m1,to:LR-A_to_LS-A,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv2,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_LS-A,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv2,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:LS-A_to_LR-A,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv2,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:LS-A_to_LR-A,to:lsp-portA,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv2,output_iface_id:hv1
type:LS,pipeline:LS-A,from:LS-A_to_LR-A,to:lsp-portA,stage:TABLE_OUTPUT_PKT,chassis:hv2,output_iface_id:hv1
type:LS,pipeline:LS-A,from:LS-A_to_LR-A,to:lsp-portA,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:LS-A_to_LR-A,to:lsp-portA,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:LS-A_to_LR-A,to:lsp-portA,stage:TABLE_OUTPUT_PKT,chassis:hv1,output_iface_id:<UNK_PORT>"

verify_trace "$expect_path" "$real_path" || exit_test

# send icmp to a unknow address from hv1
real_path=`inject_trace_packet lsp-portA 00:00:06:08:07:01 10.10.1.2 00:00:06:08:06:01 172.20.11.66`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
# we don't update expect_pkt, because we won't expect receiving icmp back
verify_pkt $expect_pkt $real_pkt || exit_test
expect_path="type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-A,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-A,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-A,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m2,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv1,output_iface_id:hv3
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m2,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv1,output_iface_id:hv3
type:LR,pipeline:LR-A,from:LR-A_to_m2,to:LR-A_to_m2,stage:TABLE_LRP_TRACE_EGRESS_OUT,chassis:hv1,output_iface_id:hv3
type:LS,pipeline:m2,from:m2_to_LR-A,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1,output_iface_id:hv3
type:LS,pipeline:m2,from:m2_to_LR-A,to:m2_to_edge2,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1,output_iface_id:hv3
type:LS,pipeline:m2,from:m2_to_LR-A,to:m2_to_edge2,stage:TABLE_OUTPUT_PKT,chassis:hv1,output_iface_id:hv3
type:LS,pipeline:m2,from:m2_to_LR-A,to:m2_to_edge2,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv3,output_iface_id:<UNK_PORT>
type:LS,pipeline:m2,from:m2_to_LR-A,to:m2_to_edge2,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv3,output_iface_id:<UNK_PORT>
type:LR,pipeline:edge2,from:edge2_to_m2,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv3,output_iface_id:<UNK_PORT>
type:LR,pipeline:edge2,from:edge2_to_m2,to:edge2_to_outside2,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv3,output_iface_id:<UNK_PORT>
type:LR,pipeline:edge2,from:edge2_to_m2,to:edge2_to_outside2,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv3,output_iface_id:<UNK_PORT>
type:LR,pipeline:edge2,from:edge2_to_m2,to:edge2_to_outside2,stage:TABLE_DROP_PACKET,chassis:hv3,output_iface_id:<UNK_PORT>"
verify_trace "$expect_path" "$real_path" || exit_test

real_path=`inject_trace_packet lsp-portA 00:00:06:08:07:01 10.10.1.2 00:00:06:08:06:01 100.10.10.111`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
# we don't update expect_pkt, because we won't expect receiving icmp back
verify_pkt $expect_pkt $real_pkt || exit_test
expect_path="type:LS,pipeline:LS-A,from:lsp-portA,to:<UNKNOW>,stage:TABLE_LSP_TRACE_INGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-A,stage:TABLE_LSP_TRACE_INGRESS_OUT,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-A,stage:TABLE_LSP_TRACE_EGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LS,pipeline:LS-A,from:lsp-portA,to:LS-A_to_LR-A,stage:TABLE_LSP_TRACE_EGRESS_OUT,chassis:hv1,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:<UNKNOW>,stage:TABLE_LRP_TRACE_INGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m2,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv1,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m2,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv1,output_iface_id:<UNK_PORT>\n"

# ondemand & redirect feature will direct traffic to other chassis, so it would not drop this packet
# then the last path(TABLE_DROP_PACKET) should be deleted
if [[ -z "$ONDEMAND" || "$ONDEMAND" == 1 ]]; then
    last_path="type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m2,stage:TABLE_OUTPUT_PKT,chassis:hv1,output_iface_id:hv3
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m2,stage:TABLE_LRP_TRACE_INGRESS_OUT,chassis:hv3,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m2,stage:TABLE_LRP_TRACE_EGRESS_IN,chassis:hv3,output_iface_id:<UNK_PORT>
type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m2,stage:TABLE_DROP_PACKET,chassis:hv3,output_iface_id:<UNK_PORT>"
else
    last_path="type:LR,pipeline:LR-A,from:LR-A_to_LS-A,to:LR-A_to_m2,stage:TABLE_DROP_PACKET,chassis:hv1,output_iface_id:<UNK_PORT>"
fi

expect_path=`echo -e "${expect_path}${last_path}"`
verify_trace "$expect_path" "$real_path" || exit_test

# create a lot of lsp to test if pkt-trace works well.
i=15
MAX_PORT_N=$((10+i))
while [ $i -lt $MAX_PORT_N ]; do
    mac_hex=`int_to_hex $i`
    port_add hv4 lsp-portA${i} || exit_test
    etcd_lsp_add LS-A lsp-portA${i} 10.10.1.${i} 00:00:09:09:09:$mac_hex
    port_add hv1 lsp-portB${i} || exit_test
    etcd_lsp_add LS-B lsp-portB${i} 10.10.2.${i} 00:00:09:09:0a:$mac_hex
    i=$((i+1))
done
wait_for_flows_unchange
output="$(BATCH_NUM=20 TRACE_WAIT_TIME=6 DETECT_LOOP=3 inject_trace_packet LS-A,LS-B 2>&1)"
if [ "$output" != "" ]; then
    pmsg "error tracing output"
    pmsg "$output"
    exit_test
fi

pass_test
