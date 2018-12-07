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

# create LR-agent which help to redirect traffic
etcd_lr_add LR-agent hv-agent

start_tuplenet_daemon hv1 192.168.100.1
start_tuplenet_daemon hv2 192.168.100.2
ONDEMAND=0 start_tuplenet_daemon hv-agent 192.168.100.10
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

# simulate the hv2's ovs & tuplenet hit error and die
# and reboot hv2
pmsg "terminate hv2"
kill_tuplenet_daemon hv2 -TERM
sim_destroy hv2
wait_for_flows_unchange
# tupleNet-3232261122 should not exist in hv1, because hv2 exit gracefull
! is_port_exist hv1 tupleNet-3232261122 || exit_test
pmsg "restart hv2"
ovs_boot hv2
tuplenet_boot hv2 192.168.100.2
wait_for_brint # waiting for building br-int bridge

wait_for_flows_unchange 6 # waiting for install flows

ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 3`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=08
expect_pkt=`build_icmp_request 000006080602 000006080604 $ip_src $ip_dst $ttl 5c91 8510`
real_pkt=`get_tx_pkt hv2 lsp-portB`
verify_pkt $expect_pkt $real_pkt || exit_test

# kill hv2, create a new hv3 but get same IP
kill_tuplenet_daemon hv2 -TERM
sim_destroy hv2
remove_sim_id_from_array hv2 # remove the hv2 from sim_array
sleep 1
sim_create hv3 || exit_test
net_join phy hv3 || exit_test
start_tuplenet_daemon hv3 192.168.100.2
install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv3 lsp-portB || exit_test
wait_for_flows_unchange 6 # waiting for install flows

# send packet to new host's lsp-portB
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 3`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=08
expect_pkt=`build_icmp_request 000006080602 000006080604 $ip_src $ip_dst $ttl 5c91 8510`
real_pkt=`get_tx_pkt hv3 lsp-portB`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

wait_for_flows_unchange # waiting for generating ondemand flow and tunnel port
# hv3 has same IP, so we can get tupleNet-3232261122 from hv1
is_port_exist hv1 tupleNet-3232261122 || exit_test
chassis_id=`get_tunnel_port_chassis_id hv1 tupleNet-3232261122`
if [ "$chassis_id" != "hv3" ]; then
    exit_test
fi

pmsg "kill hv3 tuplenet and ovs"
kill_tuplenet_daemon hv3 -KILL
sim_destroy hv3
sleep 3
# hv1's tunnel port(tuplenet-iphv3) should exist
is_port_exist hv1 tupleNet-3232261122 || exit_test
# start hv3 again, but with different ip
pmsg "restart hv3 tuplenet and ovs"
ovs_boot hv3
start_tuplenet_daemon hv3 192.168.100.3
install_arp
wait_for_brint # waiting for building br-int bridge
sleep 5 # sleep for a while to wait sync with etcd/inserting flows
wait_for_flows_unchange # waiting for install flows
# send packet to new host's lsp-portB
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 3`
ttl=04
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5f91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=03
expect_pkt=`build_icmp_request 000006080602 000006080604 $ip_src $ip_dst $ttl 6091 8510`
real_pkt=`get_tx_last_pkt hv3 lsp-portB`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

wait_for_flows_unchange # waiting for generating ondemand flow and tunnel port

! is_port_exist hv1 tupleNet-3232261122 || exit_test
is_port_exist hv1 tupleNet-3232261123 || exit_test

# create two chassis and lsp
etcd_chassis_add hv4 192.168.100.4 10
etcd_chassis_add hv5 192.168.100.5 10
etcd_lsp_add LS-B lsp-portD 10.10.2.5 00:00:06:08:06:06 hv4
etcd_lsp_add LS-A lsp-portE 10.10.1.5 00:00:06:08:06:07 hv5
wait_for_flows_unchange

# send icmp to lsp-portD from lsp-portA to trigger generating tunnel port
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 5`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test

# send icmp to lsp-portE from lsp-portA to trigger generating tunnel port
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 1 5`
ttl=09
packet=`build_icmp_request 000006080603 000006080607 $ip_src $ip_dst $ttl 5b91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test

wait_for_flows_unchange # waiting for generating ondemand flow and tunnel port

is_port_exist hv1 tupleNet-3232261124 || exit_test
is_port_exist hv1 tupleNet-3232261125 || exit_test
# delete the ovsport to test if tuplenet can add it back
port_del hv1 tupleNet-3232261124
wait_for_flows_unchange
is_port_exist hv1 tupleNet-3232261124 || exit_test

# delete hv4, add hv6 at same time
etcd_chassis_del hv4
etcd_chassis_add hv6 192.168.100.6 10
etcd_lr_add LR-dummy1 hv6 # hv6 is a chassis in virtual network map, it will
                         # be touched automaticlly
etcd_lsp_add LS-A lsp-portF 10.10.1.6 00:00:06:08:06:08 hv6
wait_for_flows_unchange

! is_port_exist hv1 tupleNet-3232261124 || exit_test
is_port_exist hv1 tupleNet-3232261125 || exit_test
is_port_exist hv1 tupleNet-3232261126 || exit_test

# modify the tick, we should not add/delete any ovs tunnel port
ofport_hv6=`get_ovs_iface_ofport hv1 tupleNet-3232261126`
etcd_chassis_add hv6 192.168.100.6 11
wait_for_flows_unchange

is_port_exist hv1 tupleNet-3232261126 || exit_test
ofport_hv6_current=`get_ovs_iface_ofport hv1 tupleNet-3232261126`
if [ "$ofport_hv6" != "$ofport_hv6_current" ]; then
    exit_test
fi

# add hv7, has same ip as hv6, but tick is 10 which smaller than hv6's
etcd_chassis_add hv7 192.168.100.6 10
etcd_lr_add LR-dummy2 hv7
wait_for_flows_unchange
is_port_exist hv1 tupleNet-3232261126 || exit_test
# ovs tunnel port should not change
ofport_hv6_current=`get_ovs_iface_ofport hv1 tupleNet-3232261126`
if [ "$ofport_hv6" != "$ofport_hv6_current" ]; then
    exit_test
fi
chassis_id=`get_tunnel_port_chassis_id hv1 tupleNet-3232261126`
if [ "$chassis_id" != "hv6" ]; then
    exit_test
fi

# delete hv6, so hv7 is the only chassis who occupy ip 192.168.100.6
etcd_chassis_del hv6
wait_for_flows_unchange
# the chassis-id should be hv7 now
chassis_id=`get_tunnel_port_chassis_id hv1 tupleNet-3232261126`
if [ "$chassis_id" != "hv7" ]; then
    exit_test
fi

pass_test
