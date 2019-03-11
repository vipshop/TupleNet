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

start_tuplenet_daemon hv1 172.20.11.2
ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv2 172.20.11.3
ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv3 172.20.11.4
install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv1 lsp-portA || exit_test
port_add hv1 lsp-portB || exit_test
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
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# send icmp to edge2 from hv1, should not receive icmp feedback
ip_dst=`ip_to_hex 172 20 11 12`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl f891 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
real_pkt=`get_tx_pkt hv1 lsp-portA`  # the received packets has no change, becuase we don't want to get a feed back
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# disable bfd on hv2's tunnel interface which forward traffic to hv1
disable_bfd hv2 hv1
sleep 5
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=fd
response_pkt=`build_icmp_response 000006080601 000006080701 $ip_dst $ip_src $ttl 0491 8d10`
real_pkt=`get_tx_pkt hv1 lsp-portA`
expect_pkt="$expect_pkt $response_pkt" # we should receive icmp response
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# enable bfd on hv2's tunnel interface which forward traffic to hv1
enable_bfd hv2 hv1
sleep 5
ip_dst=`ip_to_hex 172 20 11 12`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl f891 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
real_pkt=`get_tx_pkt hv1 lsp-portA`  # the received packets has no change, becuase we don't want to get a feed back
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# set static route on edge1
etcd_lsr_add edge1 0.0.0.0 0 172.20.11.1 edge1_to_outside1
# set static route on edge2
etcd_lsr_add edge2 0.0.0.0 0 172.20.11.1 edge2_to_outside2
patchport_add hv2 patchport-outside1 || exit_test
patchport_add hv3 patchport-outside2 || exit_test

# add patchport into etcd
etcd_patchport_add outside1 patchport-outside1
etcd_patchport_add outside2 patchport-outside2
wait_for_flows_unchange

ip_src=`ip_to_hex 10 10 2 3`
ip_dst=`ip_to_hex 172 20 11 12`
ttl=09
packet=`build_icmp_request 000006080702 000006080602 $ip_src $ip_dst $ttl f891 8510`
inject_pkt hv1 lsp-portB "$packet" || exit_test
wait_for_packet # wait for packet
ttl=fd
expect_pkt=""
# should not receive any icmp packet, this packet should be forward to hv2(which
# has no 172 20 11 12, but it will ask arp)
real_pkt=`get_tx_pkt hv1 lsp-portB`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test
sleep 1
# send icmp packet again. hv2 will send it to outside phy which deliver to hv3,
# once hv3 get the icmp(from outside network) then generate icmp route back to
# hv1's lsp-portB
inject_pkt hv1 lsp-portB "$packet" || exit_test
wait_for_packet # wait for packet
expect_pkt=`build_icmp_response 000006080602 000006080702 $ip_dst $ip_src $ttl 0491 8d10`
real_pkt=`get_tx_pkt hv1 lsp-portB`
verify_pkt "$expect_pkt" "$real_pkt" || exit_test

# kill a edge tuplenet
kill_tuplenet_daemon hv2 -TERM
# restart it again to simulate a upgrade
ONDEMAND=0 GATEWAY=1 tuplenet_boot hv2 192.168.100.2
wait_for_flows_unchange
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv2 hv1 || exit_test
is_tunnel_bfd_enable hv2 hv3 || exit_test
is_tunnel_bfd_enable hv3 hv1 || exit_test
is_tunnel_bfd_enable hv3 hv2 || exit_test

kill_tuplenet_daemon hv3 -TERM
# restart it again to simulate a upgrade
ONDEMAND=0 GATEWAY=1 tuplenet_boot hv3 192.168.100.3
wait_for_flows_unchange
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv2 hv1 || exit_test
is_tunnel_bfd_enable hv2 hv3 || exit_test
is_tunnel_bfd_enable hv3 hv1 || exit_test
is_tunnel_bfd_enable hv3 hv2 || exit_test

etcd_lsr_del LR-A 0.0.0.0 0 "LR-A_to_m1"
wait_for_flows_unchange
is_tunnel_bfd_disable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv3 hv1 || exit_test
is_tunnel_bfd_enable hv3 hv2 || exit_test

etcd_lsr_del LR-A 0.0.0.0 0 "LR-A_to_m2"
wait_for_flows_unchange
is_tunnel_bfd_disable hv1 hv2 || exit_test
is_tunnel_bfd_disable hv1 hv3 || exit_test

# bring lsr back
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m1"
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m2"
wait_for_flows_unchange
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv2 hv1 || exit_test
is_tunnel_bfd_enable hv2 hv3 || exit_test
is_tunnel_bfd_enable hv3 hv1 || exit_test
is_tunnel_bfd_enable hv3 hv2 || exit_test


is_port_exist hv1 tupleNet-3232261123 || exit_test
is_port_exist hv2 tupleNet-3232261123 || exit_test
# delete hv3 record in etcd side. hv3's all tunnel ports should disable bfd
# other host should not has tunnelport which dst-ip is hv3
tpctl ch del hv3 || exit_test
wait_for_flows_unchange
is_tunnel_bfd_disable hv3 hv1 || exit_test
is_tunnel_bfd_disable hv3 hv2 || exit_test
! is_port_exist hv1 tupleNet-3232261123 || exit_test
! is_port_exist hv2 tupleNet-3232261123 || exit_test

kill_tuplenet_daemon hv3 -TERM
ONDEMAND=0 GATEWAY=1 tuplenet_boot hv3 192.168.100.3
wait_for_flows_unchange
is_tunnel_bfd_enable hv3 hv1 || exit_test
is_tunnel_bfd_enable hv3 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv2 hv3 || exit_test

wait_for_flows_unchange
pass_test
