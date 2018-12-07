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

# test bfd status of tunnel port
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
if [ "$ONDEMAND" == 0 ]; then
    is_tunnel_bfd_none hv1 hv4 || exit_test
fi

ofport_hv2=`get_ovs_iface_ofport hv1 tupleNet-3232261122`
ofport_hv3=`get_ovs_iface_ofport hv1 tupleNet-3232261123`
ofport_hv4=`get_ovs_iface_ofport hv1 tupleNet-3232261124`
pmsg "hv2,hv3,hv4 ofports are $ofport_hv2 $ofport_hv3 $ofport_hv4 in hv1 host"

test_bundle()
{
    # only get hv1 flow
    expect_bundle_ports=$1
    ovs_setenv hv1
    current_ovs_flows=`get_ovs_flows_sorted`
    # table 37 is ip route table
    bundle_flow=`echo "$current_ovs_flows"|grep bundle_load|grep "table=37"`
    # e.g. bundle_load(...,slave:1,2,3,4) ---> 1,2,3,4
    bundle_ports=`echo "$bundle_flow" |awk -F'slaves:' '{print $2}'|awk -F')' '{print $1}'`
    if [ "$bundle_ports" != "$expect_bundle_ports" ]; then
        pmsg "bundle error: "$bundle_ports" != "$expect_bundle_ports""
        return 1
    fi

    expect_ecmp_flows_num=$2
    ecmp_flows_num=`echo "$current_ovs_flows"|grep 'table=38'|grep reg4|grep -v "0xffff"|wc -l`
    if [ "$ecmp_flows_num" != "$expect_ecmp_flows_num" ]; then
        pmsg "ecmp flows error: $ecmp_flows_num != $expect_ecmp_flows_num"
        return 1
    fi
}

# send icmp to edge1 from hv1
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 172 20 11 11`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af76 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=fd
expect_pkt=`build_icmp_response 000006080601 000006080701 $ip_dst $ip_src $ttl bb75 8d10`
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# send icmp to edge2 from hv1
ip_dst=`ip_to_hex 172 20 11 15`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af70 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=fd
expect_pkt=`build_icmp_response 000006080601 000006080701 $ip_dst $ip_src $ttl bb6f 8d10`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

etcd_ls_add m3
etcd_lr_add edge3 hv4
etcd_ls_add outside3
etcd_ls_link_lr m3 LR-A 100.10.10.4 24 00:00:06:08:09:01
etcd_ls_link_lr m3 edge3 100.10.10.2 24 00:00:06:08:09:02
etcd_ls_link_lr outside3 edge3 172.20.11.37 24 00:00:06:08:09:03

# delete route between LR-A and m2
etcd_lsr_del LR-A 0.0.0.0 0 "LR-A_to_m2"
# build route between LR-A to m3
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m3"
etcd_lsr_add edge3 10.10.0.0 16 100.10.10.4 edge3_to_m3
wait_for_flows_unchange

is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_disable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv1 hv4 || exit_test

# send icmp to edge1 from hv1
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 172 20 11 11`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af76 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=fd
expect_pkt=`build_icmp_response 000006080601 000006080701 $ip_dst $ip_src $ttl bb75 8d10`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# send icmp to edge2 from hv1, but we don't expect receiving feedback
ip_dst=`ip_to_hex 172 20 11 15`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af70 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
# NOTE: do not update expect packet, we don't expect receiving feedback
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# send icmp to edge3 from hv1
ip_dst=`ip_to_hex 172 20 11 37`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af70 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=fd
expect_pkt=`build_icmp_response 000006080601 000006080701 $ip_dst $ip_src $ttl bb6f 8d10`
real_pkt=`get_tx_last_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

# NOTE:enable ondemand feature may not get ofport_hv4 above, get it again
ofport_hv4=`get_ovs_iface_ofport hv1 tupleNet-3232261124`
# build route between LR-A to m2 again
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m2"
wait_for_flows_unchange
test_bundle "${ofport_hv2},${ofport_hv3},${ofport_hv4}" 3 || exit_test
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv1 hv4 || exit_test

etcd_lr_del edge1
wait_for_flows_unchange
test_bundle "${ofport_hv3},${ofport_hv4}" 2 || exit_test
is_tunnel_bfd_disable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv1 hv4 || exit_test

etcd_lr_del edge2
wait_for_flows_unchange
# only one port, would not have bundle flow, but one ecmp flow remain
test_bundle "" 1 || exit_test
is_tunnel_bfd_disable hv1 hv2 || exit_test
is_tunnel_bfd_disable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv1 hv4 || exit_test

etcd_lr_add edge1 hv2
etcd_lr_add edge2 hv3
wait_for_flows_unchange
test_bundle "${ofport_hv2},${ofport_hv3},${ofport_hv4}" 3 || exit_test
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv1 hv4 || exit_test

etcd_ls_unlink_lr m3 edge3
wait_for_flows_unchange
test_bundle "${ofport_hv2},${ofport_hv3}" 2 || exit_test
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_disable hv1 hv4 || exit_test

etcd_ls_unlink_lr m2 LR-A
wait_for_flows_unchange
# only one port, would not have bundle flow
#TODO !!!
test_bundle "" 1 || exit_test
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_disable hv1 hv3 || exit_test
is_tunnel_bfd_disable hv1 hv4 || exit_test

# add all things back
etcd_ls_link_lr m3 edge3 100.10.10.2 24 00:00:06:08:09:02
etcd_ls_link_lr m2 LR-A 100.10.10.3 24 00:00:06:08:06:04
wait_for_flows_unchange
test_bundle "${ofport_hv2},${ofport_hv3},${ofport_hv4}" 3 || exit_test
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv1 hv4 || exit_test


# simulate adding a new gateway chassis
sim_create hv5 || exit_test
net_join phy hv5 || exit_test
GATEWAY=1 start_tuplenet_daemon hv5 192.168.100.5
install_arp
wait_for_brint # waiting for building br-int bridge

etcd_ls_add m4
etcd_lr_add edge4 hv5

etcd_ls_add outside4
etcd_ls_link_lr m4 LR-A 100.10.10.5 24 00:00:06:08:12:01
etcd_ls_link_lr m4 edge4 100.10.10.2 24 00:00:06:08:12:02
etcd_ls_link_lr outside4 edge4 172.20.11.40 24 00:00:06:08:12:03
etcd_lsr_add LR-A 0.0.0.0 0 100.10.10.2 "LR-A_to_m4"
etcd_lsr_add edge4 10.10.0.0 16 100.10.10.5 edge4_to_m4

wait_for_flows_unchange # waiting for install flows
ofport_hv5=`get_ovs_iface_ofport hv1 tupleNet-3232261125`

test_bundle "${ofport_hv2},${ofport_hv3},${ofport_hv4},${ofport_hv5}" 4 || exit_test
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv1 hv4 || exit_test
is_tunnel_bfd_enable hv1 hv5 || exit_test

etcd_lr_del edge4
wait_for_flows_unchange # waiting for install flows
test_bundle "${ofport_hv2},${ofport_hv3},${ofport_hv4}" 3 || exit_test
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv1 hv4 || exit_test

# delete edge1 and add edge4 then we can see adding/readding/deleting at same time
etcd_lr_del edge1
etcd_lr_add edge4 hv5
wait_for_flows_unchange
test_bundle "${ofport_hv3},${ofport_hv4},${ofport_hv5}" 3 || exit_test
is_tunnel_bfd_disable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv1 hv4 || exit_test
is_tunnel_bfd_enable hv1 hv5 || exit_test

etcd_lr_add edge1 hv2
wait_for_flows_unchange
test_bundle "${ofport_hv2},${ofport_hv3},${ofport_hv4},${ofport_hv5}" 4 || exit_test
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv1 hv4 || exit_test
is_tunnel_bfd_enable hv1 hv5 || exit_test

etcd_lr_del LR-A
wait_for_flows_unchange
etcd_lr_add LR-A
wait_for_flows_unchange
test_bundle "${ofport_hv2},${ofport_hv3},${ofport_hv4},${ofport_hv5}" 4 || exit_test
is_tunnel_bfd_enable hv1 hv2 || exit_test
is_tunnel_bfd_enable hv1 hv3 || exit_test
is_tunnel_bfd_enable hv1 hv4 || exit_test
is_tunnel_bfd_enable hv1 hv5 || exit_test

pass_test
