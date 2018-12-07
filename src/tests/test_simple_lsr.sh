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
etcd_lr_add LR-A hv1
etcd_ls_add LS-B
etcd_lr_add LR-B hv2
etcd_ls_add LS-C
etcd_lr_add LR-C hv1
etcd_ls_add LS-D
etcd_lr_add LR-D hv2

# create agent which help to redirect traffic
etcd_lr_add LR-agent hv3

start_tuplenet_daemon hv1 192.168.100.1
start_tuplenet_daemon hv2 192.168.100.2
ONDEMAND=0 start_tuplenet_daemon hv3 192.168.100.3
install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv1 lsp-portA || exit_test
port_add hv2 lsp-portB || exit_test
# link LS-A to LR-A
etcd_ls_link_lr LS-A LR-A 10.10.1.1 24 00:00:06:08:06:01
# link LS-B to LR-A
etcd_ls_link_lr LS-B LR-A 10.10.2.1 24 00:00:06:08:06:02
# link LS-B to LR-B
etcd_ls_link_lr LS-B LR-B 10.10.2.2 24 00:00:06:08:06:03
# link LS-C to LR-B
etcd_ls_link_lr LS-C LR-B 10.10.3.1 24 00:00:06:08:06:04
# link LS-C to LR-C
etcd_ls_link_lr LS-C LR-C 10.10.3.2 24 00:00:06:08:06:05
# link LS-D to LR-C
etcd_ls_link_lr LS-D LR-C 10.10.4.1 24 00:00:06:08:06:06
# link LS-D to LR-D
etcd_ls_link_lr LS-D LR-D 10.10.4.2 24 00:00:06:08:06:07

# create static route from LS-A to LS-D
etcd_lsr_add LR-A 10.10.4.0 24 10.10.2.2 LR-A_to_LS-B
etcd_lsr_add LR-B 10.10.4.0 24 10.10.3.2 LR-B_to_LS-C
# create static route from LR-D to LS-A
etcd_lsr_add LR-D 10.10.1.0 24 10.10.4.1 LR-D_to_LS-D
etcd_lsr_add LR-C 10.10.1.0 24 10.10.3.1 LR-C_to_LS-C
etcd_lsr_add LR-B 10.10.1.0 24 10.10.2.1 LR-B_to_LS-B

# create logical switch port
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:07:03
etcd_lsp_add LS-D lsp-portB 10.10.4.3 00:00:06:08:07:04
wait_for_flows_unchange # waiting for install flows

ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 4 3`
ttl=09
packet=`build_icmp_request 000006080703 000006080601 $ip_src $ip_dst $ttl 5891 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=06
expect_pkt=`build_icmp_request 000006080606 000006080704 $ip_src $ip_dst $ttl 5b91 8510`
real_pkt=`get_tx_pkt hv2 lsp-portB`
verify_pkt $expect_pkt $real_pkt || exit_test

ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 4 2`
ttl=09
packet=`build_icmp_request 000006080703 000006080601 $ip_src $ip_dst $ttl 5892 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=fb
expect_pkt=`build_icmp_response 000006080601 000006080703 $ip_dst $ip_src $ttl 6691 8d10`
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

pass_test
