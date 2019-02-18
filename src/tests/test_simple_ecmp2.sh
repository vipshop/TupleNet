#!/bin/bash
. env_utils.sh

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
GATEWAY=1 ONDEMAND=0 start_tuplenet_daemon hv2 192.168.100.2
GATEWAY=1 ONDEMAND=0 start_tuplenet_daemon hv3 192.168.100.3
GATEWAY=1 ONDEMAND=0 start_tuplenet_daemon hv4 192.168.100.4
install_arp
wait_for_brint # waiting for building br-int bridge


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
etcd_ls_link_lr outside2 edge2 172.20.11.15 24 00:00:06:08:06:08

# set static route on LR-A, the route is ecmp route
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m1"
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m2"
# set static route on edge1
etcd_lsr_add edge1 10.10.0.0 16 100.10.10.1 edge1_to_m1
# set static route on edge2
etcd_lsr_add edge2 10.10.0.0 16 100.10.10.3 edge2_to_m2

# create logical switch port
port_add hv1 lsp-portA || exit_test
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:07:01
wait_for_flows_unchange # waiting for install flows

ovs_setenv hv1
prev_ovs_flows=`get_ovs_flows`
# the route table number is 37
prev_lrp_flow_n=`echo "$prev_ovs_flows" | grep "table=37," |grep "metadata=0x3"| wc -l`
for i in {4..70}; do
    mac_hex=`int_to_hex $i`
    lsname=m${i}
    etcd_ls_add $lsname
    etcd_ls_link_lr $lsname  LR-A 100.10.10.$i 24 00:00:06:99:99:$mac_hex
done
wait_for_flows_unchange # waiting for install flows
ovs_setenv hv1
current_ovs_flows=`get_ovs_flows`
current_lrp_flow_n=`echo "$current_ovs_flows" | grep "table=37,"|grep "metadata=0x3" | wc -l`

if [ $(($prev_lrp_flow_n + 62)) != $current_lrp_flow_n ]; then
    pmsg "error ovs flow number $prev_lrp_flow_n, $current_lrp_flow_n"
    exit_test
fi

prev_lrp_flow_n=$current_lrp_flow_n
for i in {4..20}; do
    mac_hex=`int_to_hex $i`
    lsname=m${i}
    etcd_ls_unlink_lr $lsname LR-A
done
wait_for_flows_unchange # waiting for install flows
ovs_setenv hv1
current_ovs_flows=`get_ovs_flows`
current_lrp_flow_n=`echo "$current_ovs_flows" | grep "table=37,"|grep "metadata=0x3" | wc -l`

if [ $(($prev_lrp_flow_n - 17)) != $current_lrp_flow_n ]; then
    pmsg "error ovs flow number $prev_lrp_flow_n, $current_lrp_flow_n"
    exit_test
fi

prev_lrp_flow_n=$current_lrp_flow_n
for i in {4..10}; do
    mac_hex=`int_to_hex $i`
    lsname=m${i}
    etcd_ls_link_lr $lsname  LR-A 100.10.10.$i 24 00:00:06:99:99:$mac_hex
done
wait_for_flows_unchange # waiting for install flows
ovs_setenv hv1
current_ovs_flows=`get_ovs_flows`
current_lrp_flow_n=`echo "$current_ovs_flows" | grep "table=37,"|grep "metadata=0x3" | wc -l`

if [ $(($prev_lrp_flow_n + 7)) != $current_lrp_flow_n ]; then
    pmsg "error ovs flow number $prev_lrp_flow_n, $current_lrp_flow_n"
    exit_test
fi

pass_test
