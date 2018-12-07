#!/bin/bash
. env_utils.sh

env_init ${0##*/} # 0##*/ is the filename
sim_create hv1 || exit_test
sim_create hv2 || exit_test
sim_create hv3 || exit_test
sim_create hv4 || exit_test
sim_create ext1 || exit_test
sim_create ext2 || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test
net_join phy hv2 || exit_test
net_join phy hv3 || exit_test
net_join phy hv4 || exit_test
net_join phy ext1 || exit_test
net_join phy ext2 || exit_test

# create logical switch and logical router first
etcd_ls_add LS-A
etcd_ls_add LS-B
etcd_lr_add LR-A
etcd_ls_add m1
etcd_ls_add m2
etcd_lr_add edge1 hv3
etcd_lr_add edge2 hv4
etcd_ls_add outside1
etcd_ls_add outside2

ONDEMAND=1 start_tuplenet_daemon hv1 172.20.11.1
ONDEMAND=1 start_tuplenet_daemon hv2 172.20.11.2
ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv3 172.20.11.3
ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv4 172.20.11.4
start_tuplenet_daemon ext1 172.20.11.8
start_tuplenet_daemon ext2 172.20.11.10
install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv1 lsp-portA || exit_test
port_add hv2 lsp-portB || exit_test
port_add hv2 lsp-portC || exit_test
patchport_add hv3 patchport-outside1 || exit_test
patchport_add hv4 patchport-outside2 || exit_test

# add patchport into etcd
etcd_patchport_add outside1 patchport-outside1
etcd_patchport_add outside2 patchport-outside2

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
etcd_lsp_add LS-A lsp-portB 10.10.1.3 00:00:06:08:07:02
etcd_lsp_add LS-B lsp-portC 10.10.2.5 00:00:06:08:07:03
wait_for_flows_unchange # waiting for install flows

# disable bfd on hv2's tunnel interface which forward traffic to edge1
disable_bfd hv2 hv3
# disable bfd on hv2's tunnel interface which forward traffic to edge2
disable_bfd hv2 hv4
sleep 5
# send icmp to lsp-portB from hv1 through edge1(hv3)
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 1 3`
ttl=09
packet=`build_icmp_request 000006080701 000006080702 $ip_src $ip_dst $ttl af85 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
expect_pkt="" # expect receive no packet
real_pkt=`get_tx_pkt hv2 lsp-portB`
verify_pkt $expect_pkt $real_pkt || exit_test
# edge1(hv3) receive one icmp packet which was redirected by edge2(hv4)
pkt_dump="`get_rx_tcpdump hv3 br0-phy`"
num=`echo "$pkt_dump" | grep -E 'ICMP|length 118' | grep "172.20.11.3" | wc -l`
if [ "$num" != 1 ]; then
    echo "error tcpdump:"$pkt_dump""
    exit_test
fi
# edge2(hv4) receive no geneve(icmp) packet, edge1 drop them once found those
# icmp packet are redirected packets
pkt_dump="`get_rx_tcpdump hv4 br0-phy`"
num=`echo "$pkt_dump" | grep -E 'ICMP|length 118' | grep "172.20.11.4" | wc -l`
if [ "$num" != 0 ]; then
    echo "error tcpdump:$pkt_dump"
    exit_test
fi

#send icmp to lsp_portC from hv1 through edge2(hv4)
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 3`
ttl=09
packet=`build_icmp_request 000006080701 000006080601 $ip_src $ip_dst $ttl af85 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
expect_pkt="" # expect receive no packet
real_pkt=`get_tx_pkt hv2 lsp-portC`
verify_pkt $expect_pkt $real_pkt || exit_test

# edge1(hv3) side has no change
pkt_dump="`get_rx_tcpdump hv3 br0-phy`"
num=`echo "$pkt_dump" | grep -E 'ICMP|length 118' | grep "172.20.11.3" | wc -l`
if [ "$num" != 1 ]; then
    echo "error tcpdump:"$pkt_dump""
    exit_test
fi
# edge2(hv4) receive one geneve(icmp) packet
pkt_dump="`get_rx_tcpdump hv4 br0-phy`"
num=`echo "$pkt_dump" | grep -E 'ICMP|length 118' | grep "172.20.11.4" | wc -l`
if [ "$num" != 1 ]; then
    echo "error tcpdump:$pkt_dump"
    exit_test
fi

# send icmp to lsp-portB from ext1 through edge1(hv3), edge1 redirect to
# edge2, edge2 drop it because found it cannot deliver to hv2 also
ip_src=`ip_to_hex 172 20 11 8`
ip_dst=`ip_to_hex 10 10 1 3`
ttl=09
src_mac=`get_ovs_iface_mac ext1 br0`
src_mac=${src_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
packet=`build_icmp_request $src_mac 000006080607 $ip_src $ip_dst $ttl af84 8510`
inject_pkt ext1 br0 "$packet" || exit_test
wait_for_packet # wait for packet
dst_mac=`get_ovs_iface_mac ext2 br0`
dst_mac=${dst_mac//:} # convert xx:xx:xx:xx:xx:xx -> xxxxxxxxxxxx
ttl=07
expect_pkt=""
real_pkt=`get_tx_pkt hv2 lsp-portB`
verify_pkt $expect_pkt $real_pkt || exit_test

# edge1(hv3) side receive one regular icmp packet
pkt_dump="`get_rx_tcpdump hv3 br0-phy`"
num=`echo "$pkt_dump" | grep 'ICMP' | grep "10.10.1.3" | grep "172.20.11.8" | wc -l`
if [ "$num" != 1 ]; then
    echo "error tcpdump:"$pkt_dump""
    echo "grep $num"
    exit_test
fi
# edge2(hv4) receive one more geneve(icmp) packet
pkt_dump="`get_rx_tcpdump hv4 br0-phy`"
num=`echo "$pkt_dump" | grep -E 'ICMP|length 118' | grep "172.20.11.4" | wc -l`
if [ "$num" != 2 ]; then
    echo "error tcpdump:$pkt_dump"
    echo "grep $num"
    exit_test
fi

pass_test
