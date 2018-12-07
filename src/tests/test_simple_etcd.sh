#!/bin/bash
export RUNTEST=1 # it tells tuplenet that your are in test mode
. env_utils.sh

MAX_ETCD_INSTANCE=3 # start 3 etcd instance
env_init ${0##*/} # 0##*/ is the filename
sim_create hv1 || exit_test
sim_create hv2 || exit_test
sim_create hv5 || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test
net_join phy hv2 || exit_test
net_join phy hv5 || exit_test

# create logical switch and logical router first
etcd_ls_add LS-A
etcd_ls_add LS-B
etcd_lr_add LR-A

# create agent which help to redirect traffic
etcd_lr_add LR-agent hv5

start_tuplenet_daemon hv1 192.168.100.1
start_tuplenet_daemon hv2 192.168.100.2
ONDEMAND=0 start_tuplenet_daemon hv5 192.168.100.5
install_arp
wait_for_brint # waiting for building br-int bridge

port_add hv1 lsp-portA || exit_test
port_add hv2 lsp-portB || exit_test
port_add hv1 lsp-portC || exit_test
# link LS-A to LR-A
etcd_ls_link_lr LS-A LR-A 10.10.1.1 24 00:00:06:08:06:01
# link LS-B to LR-A
etcd_ls_link_lr LS-B LR-A 10.10.2.1 24 00:00:06:08:06:02

# create logical switch port, tuplenet will revise the lsp's chassis and update to etcd
etcd_lsp_add LS-A lsp-portA 10.10.1.2 00:00:06:08:06:03
sleep 0.1

# stop the first etcd instance and add a lsp immediately
stop_etcd_instance 0
pmsg "sleep 10s to give etcd cluster sync time"
sleep 10
# create logical switch port
etcd_lsp_add LS-B lsp-portB 10.10.2.3 00:00:06:08:06:04
wait_for_flows_unchange # waiting for install flows

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

# stop all etcd instance
stop_etcd_instance 1
stop_etcd_instance 2
pmsg "sleep 10s make sure tuplenet start trying to reconnect etcd host"
sleep 10
# start etcd instance 1 and 2
start_etcd_instance 1
start_etcd_instance 2
pmsg "sleep 10s to give etcd cluster sync time and tuplenet reconn time"
sleep 10

etcd_lsp_add LS-B lsp-portC 10.10.2.4 00:00:06:08:06:05
wait_for_flows_unchange 6 # waiting for install flows
ip_src=`ip_to_hex 10 10 1 2`
ip_dst=`ip_to_hex 10 10 2 4`
ttl=09
packet=`build_icmp_request 000006080603 000006080601 $ip_src $ip_dst $ttl 5b91 8510`
inject_pkt hv1 lsp-portA "$packet" || exit_test
wait_for_packet # wait for packet
ttl=08
expect_pkt=`build_icmp_request 000006080602 000006080605 $ip_src $ip_dst $ttl 5c91 8510`
real_pkt=`get_tx_pkt hv1 lsp-portC`
verify_pkt $expect_pkt $real_pkt || exit_test

# test handling compact
start_etcd_instance 0 # start the first etcd instance
pmsg "sleep 10s to give etcd cluster sync time"
sleep 10
# start a tuplenet instance but only ask it connect to first etcd(had been stop)
prev_specs=$etcd_client_specs
etcd_client_specs=`echo $etcd_client_specs | awk -F',' '{print $1}'`
sim_create hv3 || exit_test
net_join phy hv3 || exit_test
start_tuplenet_daemon hv3 192.168.100.3
etcd_client_specs=$prev_specs
install_arp
wait_for_brint # waiting for building br-int bridge
wait_for_flows_unchange # waiting for install flows
stop_etcd_instance 0
pmsg "sleep 6s to give etcd cluster sync time"
sleep 6
etcd_lsp_add LS-B lsp-portD 10.10.2.5 00:00:06:08:06:06
etcd_lsp_del LS-B lsp-portD
etcdcompact   #compat here becase update chassis would disable compact testing
start_etcd_instance 0
pmsg "sleep 25s to give etcd cluster sync time, and make sure tuplenet connect the etcd"
sleep 25

etcd_lsp_add LS-B lsp-portE 10.10.2.6 00:00:06:08:06:07
port_add hv3 lsp-portE || exit_test
wait_for_flows_unchange # waiting for install flows
ip_src=`ip_to_hex 10 10 2 6`
ip_dst=`ip_to_hex 10 10 1 2`
ttl=09
packet=`build_icmp_request 000006080607 000006080602 $ip_src $ip_dst $ttl 5b91 8510`
inject_pkt hv3 lsp-portE "$packet" || exit_test
wait_for_packet # wait for packet
ttl=08
expect_pkt=`build_icmp_request 000006080601 000006080603 $ip_src $ip_dst $ttl 5c91 8510`
real_pkt=`get_tx_pkt hv1 lsp-portA`
verify_pkt $expect_pkt $real_pkt || exit_test

pass_test
