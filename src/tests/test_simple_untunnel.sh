#!/bin/bash
#noparallel
. env_utils.sh

env_init ${0##*/} # 0##*/ is the filename

# this testing cannot run inside a container
skip_if_in_container

DISABLE_DUMMY=1
sim_create hv1 || exit_test
ENABLE_UNTUNNEL=1 ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv1 172.20.11.1
wait_for_brint # waiting for building br-int bridge

# for supporting parallel testing, must generate uniq namespace name
LS_A=`random_short_str "LS-A"`
LS_B=`random_short_str "LS-B"`
out1=`random_short_str "out1"`
out2=`random_short_str "out2"`
net_namespace_add ${LS_A}
net_namespace_add ${LS_B}
net_namespace_add ${out1}
net_namespace_add ${out2}

tpctl ls add ${LS_A} || exit_test
tpctl ls add ${LS_B} || exit_test
tpctl lr add LR-A || exit_test
tpctl ls add m1 || exit_test
tpctl ls add m2 || exit_test
tpctl lr add edge1 hv1 || exit_test
tpctl lr add edge2 hv1 || exit_test
tpctl ls add ${out1} || exit_test
tpctl ls add ${out2} || exit_test

# link ${LS_A} to LR-A
tpctl lr link LR-A ${LS_A} 10.10.1.1/24 || exit_test
# link ${LS_B} to LR-A
tpctl lr link LR-A ${LS_B} 10.10.2.1/24 || exit_test
# link m1 to LR-A
tpctl lr link LR-A m1 100.10.10.1/24 || exit_test
# link m2 to LR-A
tpctl lr link LR-A m2 100.10.10.3/24 || exit_test
# link m1 to edge1
tpctl lr link edge1 m1 100.10.10.2/24 || exit_test
# link m2 to edge2
tpctl lr link edge2 m2 100.10.10.2/24 || exit_test
# link ${out1} to edge1
tpctl lr link edge1 ${out1} 172.20.11.19/24 || exit_test
# link ${out2} to edge2
tpctl lr link edge2 ${out2} 172.20.12.20/24 || exit_test

# set static routes on LR-A to dispatch traffic to m1,m2
tpctl lsr add LR-A lsr1 172.20.11.0/24 100.10.10.2 LR-A_to_m1 || exit_test
tpctl lsr add LR-A lsr2 172.20.12.0/24 100.10.10.2 LR-A_to_m2 || exit_test
# set static route on edge1
tpctl lsr add edge1 lsr3 10.10.0.0/16 100.10.10.1 edge1_to_m1 || exit_test
# set static route on edge2
tpctl lsr add edge2 lsr4 10.10.0.0/16 100.10.10.3 edge2_to_m2 || exit_test
# add snat on edge1, edge2
tpctl lnat add edge1 snat1_rule 10.10.0.0/16 snat 172.20.11.100 || exit_test
tpctl lnat add edge2 snat2_rule 10.10.0.0/16 snat 172.20.12.101 || exit_test

port_add ${LS_A} 10.10.1.2/24 00:00:06:08:08:01 10.10.1.1 || exit_test
port_add ${LS_B} 10.10.2.2/24 00:00:06:08:08:02 10.10.2.1 || exit_test
port_add ${out1} 172.20.11.16/24 00:00:06:08:08:03 172.20.11.1 || exit_test
port_add ${out2} 172.20.12.18/24 00:00:06:08:08:04 172.20.12.1 || exit_test
tpctl lsp add ${LS_A} ovsport-${LS_A} 10.10.1.2 00:00:06:08:08:01 || exit_test
tpctl lsp add ${LS_B} ovsport-${LS_B} 10.10.2.2 00:00:06:08:08:02 || exit_test
tpctl lsp add ${out1} ovsport-${out1} 172.20.11.16 00:00:06:08:08:03 || exit_test
tpctl lsp add ${out2} ovsport-${out2} 172.20.12.18 00:00:06:08:08:04 || exit_test
wait_for_flows_unchange # waiting for install flows

ret="`ip netns exec ${LS_A} ping 172.20.11.16 -c 1`"
verify_has_str "$ret" "1 received" || exit_test
ret="`ip netns exec ${LS_A} ping 172.20.12.18 -c 1`"
verify_has_str "$ret" "1 received" || exit_test
ret="`ip netns exec ${LS_B} ping 172.20.11.16 -c 1`"
verify_has_str "$ret" "1 received" || exit_test
ret="`ip netns exec ${LS_B} ping 172.20.12.18 -c 1`"
verify_has_str "$ret" "1 received" || exit_test

ret="`ip netns exec ${LS_A} ping 100.10.10.1 -c 1`"
verify_has_str "$ret" "1 received" || exit_test
ret="`ip netns exec ${LS_A} ping 100.10.10.2 -c 1`"
verify_has_str "$ret" "1 received" || exit_test
ret="`ip netns exec ${LS_A} ping 100.10.10.3 -c 1`"
verify_has_str "$ret" "1 received" || exit_test


tcpdump_file=`random_short_str "${OVS_RUNDIR}/tcpdump.pcap"`
tcpdump -i br-int-dsrgw icmp -nevvv -w $tcpdump_file &
tcpdump_pid=$!
on_tuplenet_exit "kill $tcpdump_pid 2>/dev/null"
sleep 2
ret="`ip netns exec ${LS_B} ping 192.168.30.10 -c 1`"
pmsg "$ret"
kill $tcpdump_pid 2>/dev/null
sleep 1 # tcpdump need sometime to dump packet into file
pkt_dump="`tcpdump -r $tcpdump_file -nnevvv`"
verify_has_str "$pkt_dump" "192.168.30.10" || exit_test

# delete m1 to test if it cause overlap deletion
(yes | tpctl ls del -r m1) || exit_test
wait_for_flows_unchange # waiting for install flows
ret="`ip netns exec ${LS_A} ping 100.10.10.3 -c 1`"
verify_has_str "$ret" "1 received" || exit_test

pass_test
