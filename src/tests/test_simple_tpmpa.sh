#!/usr/bin/env bash
. env_utils.sh
pmsg_green "preparing env"
env_init ${0##*/} # 0##*/ is the filename
# setup and run tpmpa
pmsg_green "building tpmpa and run it"
tuplenet_init  test_simple_tpmpa.sh
export ETCD_PREFIX=${tuplenet_prefix}
export ETCD_HOSTS=${etcd_client_specs}
export AUTH_STRING="YWZhc2Zhc2Zhc2Z3cXJ0cTUxMjVmZ2Znbm82NzgwZmFm"
export EDGE_SHELL_PATH="../tuplenet/tools/edge-operate.py"
export PATH=../control/bin/:$PATH

on_tpmpa_exit()
{
    (echo "$1"; cat $test_path/cleanup) > $test_path/cleanup.tmp
    mv $test_path/cleanup.tmp $test_path/cleanup
}
sim_create hv1 || exit_test
net_create phy || exit_test
net_join phy hv1 || exit_test
GATEWAY=1 ONDEMAND=0 start_tuplenet_daemon hv1 192.168.100.3
wait_for_brint  #wait tuplenet start
ovs_setenv hv1
export OVS_TMP_DIR=$ovs_dir
pmsg_green "run tpmpa process"
../control/bin/tpmpa &
pid=$!
on_tpmpa_exit  "kill ${pid} 2>/dev/null; sleep 2; kill -9 ${pid} 2>/dev/null"
# wait tpmpa run
sleep 2
jsonHead="Content-Type:application/json"
authHead="X-TUPLENET-AUTH:YWZhc2Zhc2Zhc2Z3cXJ0cTUxMjVmZ2Znbm82NzgwZmFm"
address="http://127.0.0.1"

get_200_request()
{
    local url=${address}$1
    curl -s -X GET ${url} | grep "Code\":200" || exit_test
}

get_400_request()
{
 local url=${address}$1
 curl -s -X GET ${url} | grep "Code\":400" || exit_test
}

get_500_request()
{
 local url=${address}$1
 curl -s -X GET ${url} | grep "Code\":500" || exit_test
}

post_no_param_request()
{
    local url=$1
    local grepStr=$2
    curl -s -H ${jsonHead} -H ${authHead} -X POST ${url} | grep "${grepStr}" || exit_test
}

post_param_request()
{
    local url=$1
    local param=$2
    local grepStr=$3
    curl -s -H  ${jsonHead} -H ${authHead} -X POST ${url} -d "${param}" | grep "${grepStr}" || exit_test
}

post_401_request()
{
    local url=${address}$1
    curl -s -H ${jsonHead} -X POST ${url} | grep "Code\":401" || exit_test
}

post_400_request()
{
    local url=${address}$1
    local param=$2
    if [ "${param}" == "" ]
    then
        post_no_param_request ${url}  "Code\":400"
     else
        post_param_request ${url} "${param}" "Code\":400"
    fi
}

post_200_request()
{
    local url=${address}$1
    local param=$2
    if [ "${param}" == "" ]
    then
        post_no_param_request ${url} "Code\":200"
     else
        post_param_request ${url} "${param}" "Code\":200"
    fi
}

post_500_request()
{
    local url=${address}$1
    local param=$2
    if [ "${param}" == "" ]
    then
        post_no_param_request ${url}  'Code":500'
     else
        post_param_request ${url}  "${param}"  'Code":500'
    fi
}

pmsg_green "test route add"
post_401_request /api/v1/route_add
post_400_request /api/v1/route_add
post_200_request /api/v1/route_add  '{"route":"LR-edge6"}'

pmsg_green "test route show"
get_200_request /api/v1/route_show
get_200_request /api/v1/route_show?route=LR-edge6

pmsg_green "test route port add"
post_401_request /api/v1/route_port_add
post_400_request /api/v1/route_port_add  '{"cidr":"10.189.114.206/22","portName":"LR-edge6_to_outside7","peer":"outside7_to_LR-edge6"}'
post_400_request /api/v1/route_port_add  '{"route":"LR-edge6","portName":"LR-edge6_to_outside7","peer":"outside7_to_LR-edge6"}'
post_400_request /api/v1/route_port_add  '{"route":"LR-edge6","cidr":"10.189.114.206/22","peer":"outside7_to_LR-edge6"}'
post_400_request /api/v1/route_port_add  '{"route":"LR-edge6","cidr":"10.189.114.206/22","portName":"LR-edge6_to_outside7"}'
post_200_request /api/v1/route_port_add  '{"route":"LR-edge6","cidr":"10.189.114.206/22","portName":"LR-edge6_to_outside7","peer":"outside7_to_LR-edge6"}'

pmsg_green  "test route port show"
get_400_request /api/v1/route_port_show
get_200_request /api/v1/route_port_show?route=LR-edge6
get_200_request /api/v1/route_port_show?route=LR-edge6&portName=LR-edge6_to_outside7

pmsg_green "test route static add"
post_401_request /api/v1/route_static_add
post_400_request /api/v1/route_static_add
post_400_request /api/v1/route_static_add  '{"rName":"to_virt6","cidr":"192.168.40.0/24","nextHop":"100.80.10.206","outPort":"LR-edge6_to_m6"}'
post_400_request /api/v1/route_static_add  '{"route":"LR-edge6","cidr":"192.168.40.0/24","nextHop":"100.80.10.206","outPort":"LR-edge6_to_m6"}'
post_400_request /api/v1/route_static_add  '{"route":"LR-edge6","rName":"to_virt6","nextHop":"100.80.10.206","outPort":"LR-edge6_to_m6"}'
post_400_request /api/v1/route_static_add  '{"route":"LR-edge6","rName":"to_virt6","cidr":"192.168.40.0/24","outPort":"LR-edge6_to_m6"}'
post_400_request /api/v1/route_static_add  '{"route":"LR-edge6","rName":"to_virt6","cidr":"192.168.40.0/24","nextHop":"100.80.10.206",}'
post_200_request /api/v1/route_static_add  '{"route":"LR-edge6","rName":"to_virt6","cidr":"192.168.40.0/24","nextHop":"100.80.10.206","outPort":"LR-edge6_to_m6"}'

pmsg_green "test route static show"
get_400_request /api/v1/route_static_show
get_200_request /api/v1/route_static_show?route=LR-edge6
get_200_request /api/v1/route_static_show?route=LR-edge6&rName=to_virt6

pmsg_green "test route nat add"
post_401_request /api/v1/route_nat_add
post_400_request /api/v1/route_nat_add
post_400_request /api/v1/route_nat_add  '{"natName":"snat_rule1","cidr":"192.168.40.0/24","xlateType":"snat","xlateIP":"10.189.114.206"}'
post_400_request /api/v1/route_nat_add  '{"route":"LR-edge6","cidr":"192.168.40.0/24","xlateType":"snat","xlateIP":"10.189.114.206"}'
post_400_request /api/v1/route_nat_add  '{"route":"LR-edge6","natName":"snat_rule1","xlateType":"snat","xlateIP":"10.189.114.206"}'
post_400_request /api/v1/route_nat_add  '{"route":"LR-edge6","natName":"snat_rule1","cidr":"192.168.40.0/24","xlateIP":"10.189.114.206"}'
post_400_request /api/v1/route_nat_add  '{"route":"LR-edge6","natName":"snat_rule1","cidr":"192.168.40.0/24","xlateType":"snat"}'
post_200_request /api/v1/route_nat_add  '{"route":"LR-edge6","natName":"snat_rule1","cidr":"192.168.40.0/24","xlateType":"snat","xlateIP":"10.189.114.206"}'

pmsg_green "test route nat show"
get_400_request  /api/v1/route_nat_show
get_200_request  /api/v1/route_nat_show?route=LR-edge6
get_200_request  /api/v1/route_nat_show?route=LR-edge6&natName=snat_rule1

pmsg_green "test switch add"
post_401_request /api/v1/switch_add
post_400_request /api/v1/switch_add
post_200_request /api/v1/switch_add  '{"switch":"outside6"}'

pmsg_green "test switch show"
get_200_request /api/v1/switch_show
get_200_request /api/v1/switch_show?switch=outside6

pmsg_green "test switch port add"
post_401_request /api/v1/switch_port_add
post_400_request /api/v1/switch_port_add
post_400_request /api/v1/switch_port_add   '{"portName":"patchport-outside6","ip":"255.255.255.255"}'
post_400_request /api/v1/switch_port_add   '{"switch":"outside6","ip":"255.255.255.255"}'
post_400_request /api/v1/switch_port_add   '{"switch":"outside6","portName":"patchport-outside6"}'
post_200_request /api/v1/switch_port_add   '{"switch":"outside6","portName":"patchport-outside6","ip":"255.255.255.255"}'

pmsg_green "test switch port show"
get_400_request /api/v1/switch_port_show
get_200_request /api/v1/switch_port_show?switch=outside6
get_200_request /api/v1/switch_port_show?switch=outside6&portName=patchport-outside6

pmsg_green "test link-switch"
post_401_request /api/v1/link_switch
post_400_request /api/v1/link_switch
post_400_request /api/v1/link_switch  '{"switch":"outside6","cidr":"192.168.41.0/24"}'
post_400_request /api/v1/link_switch  '{"route":"LR-edge6","cidr":"192.168.41.0/24"}'
post_400_request /api/v1/link_switch  '{"route":"LR-edge6","switch":"outside6"}'
post_200_request /api/v1/link_switch  '{"route":"LR-edge6","switch":"outside6","cidr":"192.168.41.0/24"}'

pmsg_green "test add switch patch port"
post_401_request /api/v1/patch_port_add
post_400_request /api/v1/patch_port_add
post_400_request /api/v1/patch_port_add  '{"portName":"patchport-outside6","chassis":"hv1","peer":"LR-edge6_to_outside7"}'
post_400_request /api/v1/patch_port_add  '{"switch":"outside6","chassis":"hv1","peer":"LR-edge6_to_outside7"}'
post_400_request /api/v1/patch_port_add  '{"switch":"outside6","portName":"patchport-outside6","peer":"LR-edge6_to_outside7"}'
post_400_request /api/v1/patch_port_add  '{"switch":"outside6","portName":"patchport-outside6","chassis":"hv1"}'
post_200_request /api/v1/patch_port_add  '{"switch":"outside6","portName":"patchport-outside6","chassis":"hv1","peer":"LR-edge6_to_outside7"}'

pmsg_green "test chassis show"
get_200_request /api/v1/chassis_show
get_200_request /api/v1/chassis_show?name=hv1
get_500_request /api/v1/chassis_show?name=hv2

pmsg_green "first add edge node"
post_401_request /api/v1/edge_add
post_400_request /api/v1/edge_add
post_400_request /api/v1/edge_add   '{"phyBr":"br0"}'
post_400_request /api/v1/edge_add   '{"vip":"10.189.114.206/22"}'
post_500_request /api/v1/edge_add   '{"vip":"10.189.114.206/22","phyBr":"br0"}'

pmsg_green "init edge node"
post_401_request /api/v1/edge_init
post_400_request /api/v1/edge_init
post_400_request /api/v1/edge_init  '{"inner":"100.80.10.206/24","virt":"100.80.10.202/24","vip":"10.189.114.207/22","extGw":"10.189.112.1"}'
post_400_request /api/v1/edge_init  '{"phyBr":"br0","virt":"100.80.10.202/24","vip":"10.189.114.207/22","extGw":"10.189.112.1"}'
post_400_request /api/v1/edge_init  '{"phyBr":"br0","inner":"100.80.10.206/24","vip":"10.189.114.207/22","extGw":"10.189.112.1"}'
post_400_request /api/v1/edge_init  '{"phyBr":"br0","inner":"100.80.10.206/24","virt":"100.80.10.202/24","extGw":"10.189.112.1"}'
post_400_request /api/v1/edge_init  '{"phyBr":"br0","inner":"100.80.10.206/24","virt":"100.80.10.202/24","vip":"10.189.114.207/22"}'
post_200_request /api/v1/edge_init  '{"phyBr":"br0","inner":"100.80.10.206/24","virt":"100.80.10.202/24","vip":"10.189.114.207/22","extGw":"10.189.112.1"}'

pmsg_green "test del switch port"
post_401_request /api/v1/switch_port_del
post_400_request /api/v1/switch_port_del
post_400_request /api/v1/switch_port_del  '{"portName":"patchport-outside6"}'
post_400_request /api/v1/switch_port_del  '{"switch":"outside6"}'
post_200_request /api/v1/switch_port_del  '{"switch":"outside6","portName":"patchport-outside6"}'
pmsg_green "del link-switch-port"
post_200_request /api/v1/switch_port_del  '{"switch":"outside6","portName":"outside6_to_LR-edge6"}'

pmsg_green "test del switch"
post_401_request /api/v1/switch_del
post_400_request /api/v1/switch_del
post_200_request /api/v1/switch_del  '{"switch":"outside6"}'

pmsg_green "test del route nat"
post_401_request /api/v1/route_nat_del
post_400_request /api/v1/route_nat_del
post_400_request /api/v1/route_nat_del  '{"natName":"snat_rule1"}'
post_400_request /api/v1/route_nat_del  '{"route":"LR-edge6"}'
post_200_request /api/v1/route_nat_del  '{"route":"LR-edge6","natName":"snat_rule1"}'

pmsg_green "test del route port"
post_401_request /api/v1/route_port_del
post_400_request /api/v1/route_port_del
post_400_request /api/v1/route_port_del   '{"portName":"LR-edge6_to_outside7"}'
post_400_request /api/v1/route_port_del   '{"route":"LR-edge6"}'
post_200_request /api/v1/route_port_del   '{"route":"LR-edge6","portName":"LR-edge6_to_outside7"}'
pmsg_green "del link-route-port"
post_200_request /api/v1/route_port_del   '{"route":"LR-edge6","portName":"LR-edge6_to_outside6"}'

pmsg_green "test del static route"
post_401_request /api/v1/route_static_del
post_400_request /api/v1/route_static_del
post_400_request /api/v1/route_static_del  '{"rName":"to_virt6"}'
post_400_request /api/v1/route_static_del  '{"route":"LR-edge6"}'
post_200_request /api/v1/route_static_del  '{"route":"LR-edge6","rName":"to_virt6"}'

pmsg_green "del edge node"
post_401_request /api/v1/edge_del
post_400_request /api/v1/edge_del
post_200_request /api/v1/edge_del  '{"vip":"10.189.114.207/22"}'

pmsg_green "test del route"
post_401_request /api/v1/route_del
post_400_request /api/v1/route_del
post_200_request /api/v1/route_del  '{"route":"LR-edge6"}'
post_500_request /api/v1/route_del  '{"route":"LR-edge6","recursive":true}'

pmsg_green "test chassis del"
post_401_request /api/v1/chassis_del
post_400_request /api/v1/chassis_del
post_200_request /api/v1/chassis_del '{"nameOrIP":"hv1"}'
post_500_request /api/v1/chassis_del '{"nameOrIP":"127.0.0.1"}'

pass_test
