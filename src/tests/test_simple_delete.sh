#!/bin/bash
. env_utils.sh

export RUNTEST=1 # it tells tuplenet your are in test mode
                 # the tuplenet will sort ovs-flows before
                 # inserting into ovs

env_init ${0##*/} # 0##*/ is the filename
sim_create hv1 || exit_test
sim_create hv2 || exit_test
sim_create hv3 || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test
net_join phy hv2 || exit_test
net_join phy hv3 || exit_test

# create logical switch and logical router first
etcd_ls_add LS-A || exit_test
etcd_ls_add LS-B || exit_test
etcd_lr_add LR-A || exit_test
etcd_ls_add m1 || exit_test
etcd_ls_add m2 || exit_test
etcd_lr_add edge1 hv2 || exit_test
etcd_lr_add edge2 hv3 || exit_test
etcd_ls_add outside1 || exit_test
etcd_ls_add outside2 || exit_test

start_tuplenet_daemon hv1 192.168.100.1
ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv2 192.168.100.2
ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv3 192.168.100.3
install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv1 lsp-portA || exit_test
port_add hv2 lsp-portB || exit_test
port_add hv3 lsp-portC || exit_test

# link LS-A to LR-A
etcd_ls_link_lr LS-A LR-A 10.10.1.1 24 00:00:06:08:06:01 || exit_test
# link LS-B to LR-A
etcd_ls_link_lr LS-B LR-A 10.10.2.1 24 00:00:06:08:06:02 || exit_test
# link m1 to LR-A
etcd_ls_link_lr m1 LR-A 100.10.10.1 24 00:00:06:08:06:03 || exit_test
# link m2 to LR-A
etcd_ls_link_lr m2 LR-A 100.10.10.3 24 00:00:06:08:06:04 || exit_test
# link m1 to edge1
etcd_ls_link_lr m1 edge1 100.10.10.2 24 00:00:06:08:06:05 || exit_test
# link m2 to edge2
etcd_ls_link_lr m2 edge2 100.10.10.2 24 00:00:06:08:06:06 || exit_test
# link outside1 to edge1
etcd_ls_link_lr outside1 edge1 172.20.11.11 24 00:00:06:08:06:07 || exit_test
# link outside2 to edge2
etcd_ls_link_lr outside2 edge2 172.20.11.12 24 00:00:06:08:06:08 || exit_test

# set static route on LR-A, the route is ecmp route
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m2" || exit_test
sleep 2; # make sure the the static route to m2 is the lower priority route if
         # ovs has no bundle ecmp flows(in edge node)
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m1" || exit_test
# set static route on edge1
etcd_lsr_add edge1 10.10.0.0 16 100.10.10.1 edge1_to_m1 || exit_test
# set static route on edge2
etcd_lsr_add edge2 10.10.0.0 16 100.10.10.3 edge2_to_m2 || exit_test

# NOTE: this snat can create nat flows but cannot translate ip because
# this ovs-simulator cannot utilze the kernel conntrack
etcd_lnat_add edge2 10.10.0.0 16 172.20.11.100 snat || exit_test

# create logical switch port
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:07:01 || exit_test
etcd_lsp_add LS-B lsp-portB 10.10.2.3 00:00:06:08:07:02 || exit_test
etcd_lsp_add LS-A lsp-portC 10.10.1.3 00:00:06:08:07:03 || exit_test
wait_for_flows_unchange # waiting for install flows

prev_ovs_flows=`get_ovs_flows_sorted`
echo "$prev_ovs_flows" > $OVS_LOGDIR/prev_ovs_flows.txt
etcd_ls_del LS-A || exit_test
etcd_ls_del m2 || exit_test
etcd_lnat_del edge2 10.10.0.0 16 172.20.11.100 snat || exit_test
etcd_lsp_del LS-A lsp-portA || exit_test
wait_for_flows_unchange
entity_id=1
etcd_ls_add LS-A || exit_test
entity_id=5
etcd_lnat_add edge2 10.10.0.0 16 172.20.11.100 snat || exit_test
etcd_ls_add m2 || exit_test
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:07:01 || exit_test
wait_for_flows_unchange
current_ovs_flows=`get_ovs_flows_sorted`
echo "$current_ovs_flows" > $OVS_LOGDIR/current_ovs_flows.txt
verify_ovsflow "$prev_ovs_flows" "$current_ovs_flows" || exit_test

prev_ovs_flows=$current_ovs_flows
echo "$prev_ovs_flows" > $OVS_LOGDIR/prev_ovs_flows.txt
etcd_lr_del LR-A || exit_test
etcd_lr_del edge1 || exit_test
etcd_ls_del outside1 || exit_test
wait_for_flows_unchange
entity_id=3
etcd_lr_add LR-A || exit_test
entity_id=6
etcd_lr_add edge1 hv2 || exit_test
entity_id=8
etcd_ls_add outside1 || exit_test
wait_for_flows_unchange
current_ovs_flows=`get_ovs_flows_sorted`
echo "$current_ovs_flows" > $OVS_LOGDIR/current_ovs_flows.txt
verify_ovsflow "$prev_ovs_flows" "$current_ovs_flows" || exit_test

prev_ovs_flows=$current_ovs_flows
echo "$prev_ovs_flows" > $OVS_LOGDIR/prev_ovs_flows.txt
etcd_ls_unlink_lr LS-A LR-A || exit_test
etcd_ls_unlink_lr m2 edge2 || exit_test
etcd_lsr_del edge1 10.10.0.0 16 edge1_to_m1 || exit_test
wait_for_flows_unchange
etcd_ls_link_lr LS-A LR-A 10.10.1.1 24 00:00:06:08:06:01 || exit_test
etcd_ls_link_lr m2 edge2 100.10.10.2 24 00:00:06:08:06:06 || exit_test
etcd_lsr_add edge1 10.10.0.0 16 100.10.10.1 edge1_to_m1 || exit_test
wait_for_flows_unchange
current_ovs_flows=`get_ovs_flows_sorted`
echo "$current_ovs_flows" > $OVS_LOGDIR/current_ovs_flows.txt
verify_ovsflow "$prev_ovs_flows" "$current_ovs_flows" || exit_test

prev_ovs_flows=$current_ovs_flows
echo "$prev_ovs_flows" > $OVS_LOGDIR/prev_ovs_flows.txt
etcd_ls_unlink_lr m2 LR-A
etcd_lsp_del LS-B lsp-portB
etcd_ls_link_lr m2 LR-A 100.10.10.3 24 00:00:06:08:06:04 || exit_test
wait_for_flows_unchange
etcd_lsp_add LS-B lsp-portB 10.10.2.3 00:00:06:08:07:02 || exit_test
etcd_lsp_del LS-A lsp-portC
etcd_lsp_add LS-A lsp-portC 10.10.1.3 00:00:06:08:07:03 || exit_test
wait_for_flows_unchange
current_ovs_flows=`get_ovs_flows_sorted`
echo "$current_ovs_flows" > $OVS_LOGDIR/current_ovs_flows.txt
verify_ovsflow "$prev_ovs_flows" "$current_ovs_flows" || exit_test

sleep 3 # waiting for BFD sync between nodes

# send icmp to edge1 from hv1
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 172 20 11 11`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl f891 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=fd
expect_pkt=`build_icmp_response 000006080601 000006080701 $ip_dst $ip_src $ttl 0491 8d10`
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test
# send icmp to edge2 from hv1, should not receive icmp feedback
ip_dst=`ip_to_hex 172 20 11 12`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl f891 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
real_pkt=`get_tx_pkt hv1 lsp-portA`  # the receive packets has no change, becuase we don't want to get a feed back
verify_pkt "$expect_pkt" "$real_pkt" || exit_test


# send icmp to edge2 from hv3, hv3 is edge
ip_src=`ip_to_hex 10 10 1 3`
ip_dst=`ip_to_hex 172 20 11 12`
ttl=09
packet=`build_icmp_request 000006080703 000006080601 $ip_src $ip_dst $ttl f891 8510`
inject_pkt hv3 lsp-portC "$packet" || exit_test
wait_for_packet # wait for packet
ttl=fd
expect_pkt=""
real_pkt=`get_tx_pkt hv3 lsp-portC`  # the receive packets has no change, becuase we don't want to get a feed back
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# send icmp to edge1 from hv3
ip_src=`ip_to_hex 10 10 1 3`
ip_dst=`ip_to_hex 172 20 11 11`
ttl=fd
packet=`build_icmp_request 000006080703 000006080601 $ip_src $ip_dst $ttl f891 8510`
inject_pkt hv3 lsp-portC "$packet" || exit_test
wait_for_packet # wait for packet
expect_pkt=`build_icmp_response 000006080601 000006080703 $ip_dst $ip_src $ttl f891 8d10`
real_pkt=`get_tx_pkt hv3 lsp-portC`
verify_pkt $expect_pkt $real_pkt || exit_test

pass_test
