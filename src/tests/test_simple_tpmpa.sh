#!/usr/bin/env bash
. env_utils.sh
pmsg "preparing env"
env_init ${0##*/} # 0##*/ is the filename


# setup and run tpmpa
pmsg "building tpmpa and run it"
export tuplenet_prefix=/test_simple_tpmpa.sh/
export ETCD_PREFIX=/test_simple_tpmpa.sh/
export ETCD_HOSTS=${etcd_client_specs}
export EDGE_SHELL_PATH=../tuplenet/tools/edge-operate.py
chmod 755 ../tuplenet/tools/edge-operate.py
export AUTH_STRING=YWZhc2Zhc2Zhc2Z3cXJ0cTUxMjVmZ2Znbm82NzgwZmFm

sim_create hv1 || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test

GATEWAY=1 ONDEMAND=0 start_tuplenet_daemon hv1 192.168.100.3

sleep 5
ovs_setenv hv1
bash ./run_tpmpa.sh  -use-vendor
sleep 10

jsonHead="Content-Type:application/json"
authHead="X-TUPLENET-AUTH:YWZhc2Zhc2Zhc2Z3cXJ0cTUxMjVmZ2Znbm82NzgwZmFm"
address="http://127.0.0.1"


echo -e "\033[34m #test route add# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/route_add | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_add | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_add  -d '{"route":"LR-edge6"}' | grep 'Code":200' || exit_test

echo -e "\033[34m #test route show# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/route_show | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_show | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_show  -d '{"all":true}'| grep 'Code":200' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_show  -d '{"route":"LR-edge6"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test route port add# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/route_port_add | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_add -d  '{"cidr":"10.189.114.206/22","portName":"LR-edge6_to_outside7","peer":"outside7_to_LR-edge6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_add -d  '{"route":"LR-edge6","portName":"LR-edge6_to_outside7","peer":"outside7_to_LR-edge6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_add -d  '{"route":"LR-edge6","cidr":"10.189.114.206/22","peer":"outside7_to_LR-edge6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_add -d  '{"route":"LR-edge6","cidr":"10.189.114.206/22","portName":"LR-edge6_to_outside7"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_add -d  '{"route":"LR-edge6","cidr":"10.189.114.206/22","portName":"LR-edge6_to_outside7","peer":"outside7_to_LR-edge6"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test route port show# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/route_port_show | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_show | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_show -d '{"route":"LR-edge6"}' | grep 'Code":200' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_show -d '{"route":"LR-edge6","portName":"LR-edge6_to_outside7"}' | grep 'Code":200' || exit_test

echo -e "\033[34m #test route static add# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/route_static_add | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_add | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_add -d '{"rName":"to_virt6","cidr":"192.168.40.0/24","nextHop":"100.80.10.206","outPort":"LR-edge6_to_m6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_add -d '{"route":"LR-edge6","cidr":"192.168.40.0/24","nextHop":"100.80.10.206","outPort":"LR-edge6_to_m6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_add -d '{"route":"LR-edge6","rName":"to_virt6","nextHop":"100.80.10.206","outPort":"LR-edge6_to_m6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_add -d '{"route":"LR-edge6","rName":"to_virt6","cidr":"192.168.40.0/24","outPort":"LR-edge6_to_m6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_add -d '{"route":"LR-edge6","rName":"to_virt6","cidr":"192.168.40.0/24","nextHop":"100.80.10.206",}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_add -d '{"route":"LR-edge6","rName":"to_virt6","cidr":"192.168.40.0/24","nextHop":"100.80.10.206","outPort":"LR-edge6_to_m6"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test route static show# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/route_static_show | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_show | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_show  -d '{"route":"LR-edge6"}'| grep 'Code":200' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_show  -d '{"route":"LR-edge6","rName":"to_virt6"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test route nat add# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/route_nat_add | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_add | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_add -d '{"natName":"snat_rule1","cidr":"192.168.40.0/24","xlateType":"snat","xlateIP":"10.189.114.206"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_add -d '{"route":"LR-edge6","cidr":"192.168.40.0/24","xlateType":"snat","xlateIP":"10.189.114.206"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_add -d '{"route":"LR-edge6","natName":"snat_rule1","xlateType":"snat","xlateIP":"10.189.114.206"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_add -d '{"route":"LR-edge6","natName":"snat_rule1","cidr":"192.168.40.0/24","xlateIP":"10.189.114.206"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_add -d '{"route":"LR-edge6","natName":"snat_rule1","cidr":"192.168.40.0/24","xlateType":"snat"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_add -d '{"route":"LR-edge6","natName":"snat_rule1","cidr":"192.168.40.0/24","xlateType":"snat","xlateIP":"10.189.114.206"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test route nat show# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/route_nat_show | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_show | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_show -d '{"route":"LR-edge6"}'| grep 'Code":200' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_show -d '{"route":"LR-edge6","natName":"snat_rule1"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test switch add# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/switch_add | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_add | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_add -d '{"switch":"outside6"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test switch show# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/switch_show | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_show | grep 'Code":200' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_show -d '{"switch":"outside6"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test switch port add# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/switch_port_add | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_port_add | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_port_add  -d '{"portName":"patchport-outside6","ip":"255.255.255.255"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_port_add  -d '{"switch":"outside6","ip":"255.255.255.255"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_port_add  -d '{"switch":"outside6","portName":"patchport-outside6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_port_add  -d '{"switch":"outside6","portName":"patchport-outside6","ip":"255.255.255.255"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test switch port show# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/switch_port_show | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_port_show | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_port_show -d '{"switch":"outside6"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test link-switch# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/link_switch | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/link_switch | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/link_switch -d '{"switch":"outside6","cidr":"192.168.41.0/24"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/link_switch -d '{"route":"LR-edge6","cidr":"192.168.41.0/24"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/link_switch -d '{"route":"LR-edge6","switch":"outside6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/link_switch -d '{"route":"LR-edge6","switch":"outside6","cidr":"192.168.41.0/24"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test del switch port# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/switch_port_del | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_port_del | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_port_del -d '{"portName":"patchport-outside6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_port_del -d '{"switch":"outside6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_port_del -d '{"switch":"outside6","portName":"patchport-outside6"}'| grep 'Code":200' || exit_test
echo -e "\033[34m #del link-switch-port# \033[0m"
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_port_del -d '{"switch":"outside6","portName":"outside6_to_LR-edge6"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test del switch# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/switch_del | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_del | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/switch_del -d '{"switch":"outside6"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test del route nat# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/route_nat_del | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_del | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_del -d ' {"natName":"snat_rule1"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_del -d ' {"route":"LR-edge6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_nat_del -d ' {"route":"LR-edge6","natName":"snat_rule1"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test del route port# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/route_port_del | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_del | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_del -d  '{"portName":"LR-edge6_to_outside7"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_del -d  '{"route":"LR-edge6"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_del -d  '{"route":"LR-edge6","portName":"LR-edge6_to_outside7"}'| grep 'Code":200' || exit_test
echo -e "\033[34m #del link-route-port# \033[0m"
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_port_del -d  '{"route":"LR-edge6","portName":"LR-edge6_to_outside6"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #test del static route# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/route_static_del | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_del | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_del -d '{"rName":"to_virt6"}' | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_del -d '{"route":"LR-edge6"}' | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_static_del -d '{"route":"LR-edge6","rName":"to_virt6"}' | grep 'Code":200' || exit_test

echo -e "\033[34m #test del route# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/route_del | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_del | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_del -d  '{"route":"LR-edge6"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #first add edge node# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/edge_add | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_add | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_add  -d '{"phyBr":"br0"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_add  -d '{"vip":"10.189.114.206/22"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_add  -d '{"vip":"10.189.114.206/22","phyBr":"br0"}'| grep 'Code":500' || exit_test

echo -e "\033[34m #init edge node# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/edge_init | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_init | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_init | grep 'Code":400' || exit_test
echo -e "\033[34m #add LR-central route# \033[0m"
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/route_add  -d '{"route":"LR-central"}' | grep 'Code":200' || exit_test
sleep 3
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_init -d '{"inner":"100.80.10.206/24","virt":"100.80.10.202/24","vip":"10.189.114.206/22","extGw":"10.189.112.1"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_init -d '{"phyBr":"br0","virt":"100.80.10.202/24","vip":"10.189.114.206/22","extGw":"10.189.112.1"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_init -d '{"phyBr":"br0","inner":"100.80.10.206/24","vip":"10.189.114.206/22","extGw":"10.189.112.1"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_init -d '{"phyBr":"br0","inner":"100.80.10.206/24","virt":"100.80.10.202/24","extGw":"10.189.112.1"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_init -d '{"phyBr":"br0","inner":"100.80.10.206/24","virt":"100.80.10.202/24","vip":"10.189.114.206/22"}'| grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_init -d '{"phyBr":"br0","inner":"100.80.10.206/24","virt":"100.80.10.202/24","vip":"10.189.114.206/22","extGw":"10.189.112.1"}'| grep 'Code":200' || exit_test

echo -e "\033[34m #del edge node# \033[0m"
curl -s -H  ${jsonHead} -X POST ${address}/api/v1/edge_del | grep 'Code":401' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_del | grep 'Code":400' || exit_test
curl -s -H  ${jsonHead} -H  ${authHead} -X POST ${address}/api/v1/edge_del -d '{"vip":"10.189.114.206/22"}'| grep 'Code":200' || exit_test


pass_test
