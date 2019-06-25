#!/usr/bin/env bash
. env_utils.sh
pmsg "preparing env"
env_init ${0##*/} # 0##*/ is the filename
# setup and run tpmpa
pmsg "building tpmpa and run it"
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
sleep 5
ovs_setenv hv1
export OVS_TMP_DIR=$ovs_dir
echo "run tpmpa process"
../control/bin/tpmpa &
pid=`ps axu|grep tpmpa|awk '/control\/bin\/tpmpa/{print $2}'`
on_tpmpa_exit  "kill ${pid} 2>/dev/null; sleep 2; kill -9 ${pid} 2>/dev/null"
sleep 5
jsonHead="Content-Type:application/json"
authHead="X-TUPLENET-AUTH:YWZhc2Zhc2Zhc2Z3cXJ0cTUxMjVmZ2Znbm82NzgwZmFm"
address="http://127.0.0.1"

post_no_param_request()
{
    local url=$1
    local grepStr=$2
    curl -s -H ${jsonHead} -H ${authHead} -X POST ${url} | grep ${grepStr} || exit_test
}

post_param_request()
{
    local url=$1
    local param=$2
    local grepStr=$3
    curl -s -H  ${jsonHead} -H ${authHead} -X POST ${url} -d "${param}" >> /tmp/a.txt #| grep ${grepStr} || exit_test
}

post_401_request()
{
    local url=${address}$1
    curl -s -H ${jsonHead} -X POST ${url} | grep 'Code":401' || exit_test
}

post_400_request()
{
    local url=${address}$1
    local param=$2
    if [ "${param}" == "" ]
    then
        post_no_param_request ${url}  'Code":400'
     else
        post_param_request ${url} "${param}" 'Code":400'
    fi
}

post_200_request()
{
    local url=${address}$1
    local param=$2
    if [ "${param}" == "" ]
    then
        post_no_param_request ${url} 'Code":200'
     else
        post_param_request ${url} "${param}" 'Code":200'
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

echo -e "\033[34m #test route add# \033[0m"
post_401_request /api/v1/route_add
post_400_request /api/v1/route_add
post_200_request /api/v1/route_add  '{"route":"LR-edge6"}'

echo -e "\033[34m #test route show# \033[0m"
post_401_request /api/v1/route_show
post_400_request /api/v1/route_show
post_200_request /api/v1/route_show   '{"all":true}'
post_200_request /api/v1/route_show  '{"route":"LR-edge6"}'

echo -e "\033[34m #test route port add# \033[0m"
post_401_request /api/v1/route_port_add
post_400_request /api/v1/route_port_add  '{"cidr":"10.189.114.206/22","portName":"LR-edge6_to_outside7","peer":"outside7_to_LR-edge6"}'
post_400_request /api/v1/route_port_add  '{"route":"LR-edge6","portName":"LR-edge6_to_outside7","peer":"outside7_to_LR-edge6"}'
post_400_request /api/v1/route_port_add  '{"route":"LR-edge6","cidr":"10.189.114.206/22","peer":"outside7_to_LR-edge6"}'
post_400_request /api/v1/route_port_add  '{"route":"LR-edge6","cidr":"10.189.114.206/22","portName":"LR-edge6_to_outside7"}'
post_200_request /api/v1/route_port_add  '{"route":"LR-edge6","cidr":"10.189.114.206/22","portName":"LR-edge6_to_outside7","peer":"outside7_to_LR-edge6"}'

echo -e "\033[34m #test route port show# \033[0m"
post_401_request /api/v1/route_port_show
post_400_request /api/v1/route_port_show
post_200_request /api/v1/route_port_show '{"route":"LR-edge6"}'
post_200_request /api/v1/route_port_show '{"route":"LR-edge6","portName":"LR-edge6_to_outside7"}'

echo -e "\033[34m #test route static add# \033[0m"
post_401_request /api/v1/route_static_add
post_400_request /api/v1/route_static_add
post_400_request /api/v1/route_static_add  '{"rName":"to_virt6","cidr":"192.168.40.0/24","nextHop":"100.80.10.206","outPort":"LR-edge6_to_m6"}'
post_400_request /api/v1/route_static_add  '{"route":"LR-edge6","cidr":"192.168.40.0/24","nextHop":"100.80.10.206","outPort":"LR-edge6_to_m6"}'
post_400_request /api/v1/route_static_add  '{"route":"LR-edge6","rName":"to_virt6","nextHop":"100.80.10.206","outPort":"LR-edge6_to_m6"}'
post_400_request /api/v1/route_static_add  '{"route":"LR-edge6","rName":"to_virt6","cidr":"192.168.40.0/24","outPort":"LR-edge6_to_m6"}'
post_400_request /api/v1/route_static_add  '{"route":"LR-edge6","rName":"to_virt6","cidr":"192.168.40.0/24","nextHop":"100.80.10.206",}'
post_200_request /api/v1/route_static_add  '{"route":"LR-edge6","rName":"to_virt6","cidr":"192.168.40.0/24","nextHop":"100.80.10.206","outPort":"LR-edge6_to_m6"}'

echo -e "\033[34m #test route static show# \033[0m"
post_401_request /api/v1/route_static_show
post_400_request /api/v1/route_static_show
post_200_request /api/v1/route_static_show  '{"route":"LR-edge6"}'
post_200_request /api/v1/route_static_show  '{"route":"LR-edge6","rName":"to_virt6"}'

echo -e "\033[34m #test route nat add# \033[0m"
post_401_request /api/v1/route_nat_add
post_400_request /api/v1/route_nat_add
post_400_request /api/v1/route_nat_add  '{"natName":"snat_rule1","cidr":"192.168.40.0/24","xlateType":"snat","xlateIP":"10.189.114.206"}'
post_400_request /api/v1/route_nat_add  '{"route":"LR-edge6","cidr":"192.168.40.0/24","xlateType":"snat","xlateIP":"10.189.114.206"}'
post_400_request /api/v1/route_nat_add  '{"route":"LR-edge6","natName":"snat_rule1","xlateType":"snat","xlateIP":"10.189.114.206"}'
post_400_request /api/v1/route_nat_add  '{"route":"LR-edge6","natName":"snat_rule1","cidr":"192.168.40.0/24","xlateIP":"10.189.114.206"}'
post_400_request /api/v1/route_nat_add  '{"route":"LR-edge6","natName":"snat_rule1","cidr":"192.168.40.0/24","xlateType":"snat"}'
post_200_request /api/v1/route_nat_add  '{"route":"LR-edge6","natName":"snat_rule1","cidr":"192.168.40.0/24","xlateType":"snat","xlateIP":"10.189.114.206"}'

echo -e "\033[34m #test route nat show# \033[0m"
post_401_request  /api/v1/route_nat_show
post_400_request  /api/v1/route_nat_show
post_200_request  /api/v1/route_nat_show  '{"route":"LR-edge6"}'
post_200_request  /api/v1/route_nat_show  '{"route":"LR-edge6","natName":"snat_rule1"}'

echo -e "\033[34m #test switch add# \033[0m"
post_401_request /api/v1/switch_add
post_400_request /api/v1/switch_add
post_200_request /api/v1/switch_add  '{"switch":"outside6"}'

echo -e "\033[34m #test switch show# \033[0m"
post_401_request /api/v1/switch_show
post_200_request /api/v1/switch_show
post_200_request /api/v1/switch_show  '{"switch":"outside6"}'

echo -e "\033[34m #test switch port add# \033[0m"
post_401_request /api/v1/switch_port_add
post_400_request /api/v1/switch_port_add
post_400_request /api/v1/switch_port_add   '{"portName":"patchport-outside6","ip":"255.255.255.255"}'
post_400_request /api/v1/switch_port_add   '{"switch":"outside6","ip":"255.255.255.255"}'
post_400_request /api/v1/switch_port_add   '{"switch":"outside6","portName":"patchport-outside6"}'
post_200_request /api/v1/switch_port_add   '{"switch":"outside6","portName":"patchport-outside6","ip":"255.255.255.255"}'

echo -e "\033[34m #test switch port show# \033[0m"
post_401_request /api/v1/switch_port_show
post_400_request /api/v1/switch_port_show
post_200_request /api/v1/switch_port_show  '{"switch":"outside6"}'

echo -e "\033[34m #test link-switch# \033[0m"
post_401_request /api/v1/link_switch
post_400_request /api/v1/link_switch
post_400_request /api/v1/link_switch  '{"switch":"outside6","cidr":"192.168.41.0/24"}'
post_400_request /api/v1/link_switch  '{"route":"LR-edge6","cidr":"192.168.41.0/24"}'
post_400_request /api/v1/link_switch  '{"route":"LR-edge6","switch":"outside6"}'
post_200_request /api/v1/link_switch  '{"route":"LR-edge6","switch":"outside6","cidr":"192.168.41.0/24"}'

echo -e "\033[34m #test add switch patch port# \033[0m"
post_401_request /api/v1/patch_port_add
post_400_request /api/v1/patch_port_add
post_400_request /api/v1/patch_port_add  '{"portName":"patchport-outside6","chassis":"hv1","peer":"LR-edge6_to_outside7"}'
post_400_request /api/v1/patch_port_add  '{"switch":"outside6","chassis":"hv1","peer":"LR-edge6_to_outside7"}'
post_400_request /api/v1/patch_port_add  '{"switch":"outside6","portName":"patchport-outside6","peer":"LR-edge6_to_outside7"}'
post_400_request /api/v1/patch_port_add  '{"switch":"outside6","portName":"patchport-outside6","chassis":"hv1"}'
post_200_request /api/v1/patch_port_add  '{"switch":"outside6","portName":"patchport-outside6","chassis":"hv1","peer":"LR-edge6_to_outside7"}'

echo -e "\033[34m #test chassis show # \033[0m"
post_401_request /api/v1/chassis_show
post_200_request /api/v1/chassis_show
post_200_request /api/v1/chassis_show '{"chassis":"hv1"}'

echo -e "\033[34m #test del switch port# \033[0m"
post_401_request /api/v1/switch_port_del
post_400_request /api/v1/switch_port_del
post_400_request /api/v1/switch_port_del  '{"portName":"patchport-outside6"}'
post_400_request /api/v1/switch_port_del  '{"switch":"outside6"}'
post_200_request /api/v1/switch_port_del  '{"switch":"outside6","portName":"patchport-outside6"}'
echo -e "\033[34m #del link-switch-port# \033[0m"
post_200_request /api/v1/switch_port_del  '{"switch":"outside6","portName":"outside6_to_LR-edge6"}'

echo -e "\033[34m #test del switch# \033[0m"
post_401_request /api/v1/switch_del
post_400_request /api/v1/switch_del
post_200_request /api/v1/switch_del  '{"switch":"outside6"}'

echo -e "\033[34m #test del route nat# \033[0m"
post_401_request /api/v1/route_nat_del
post_400_request /api/v1/route_nat_del
post_400_request /api/v1/route_nat_del  '{"natName":"snat_rule1"}'
post_400_request /api/v1/route_nat_del  '{"route":"LR-edge6"}'
post_200_request /api/v1/route_nat_del  '{"route":"LR-edge6","natName":"snat_rule1"}'

echo -e "\033[34m #test del route port# \033[0m"
post_401_request /api/v1/route_port_del
post_400_request /api/v1/route_port_del
post_400_request /api/v1/route_port_del   '{"portName":"LR-edge6_to_outside7"}'
post_400_request /api/v1/route_port_del   '{"route":"LR-edge6"}'
post_200_request /api/v1/route_port_del   '{"route":"LR-edge6","portName":"LR-edge6_to_outside7"}'
echo -e "\033[34m #del link-route-port# \033[0m"
post_200_request /api/v1/route_port_del   '{"route":"LR-edge6","portName":"LR-edge6_to_outside6"}'

echo -e "\033[34m #test del static route# \033[0m"
post_401_request /api/v1/route_static_del
post_400_request /api/v1/route_static_del
post_400_request /api/v1/route_static_del  '{"rName":"to_virt6"}'
post_400_request /api/v1/route_static_del  '{"route":"LR-edge6"}'
post_200_request /api/v1/route_static_del  '{"route":"LR-edge6","rName":"to_virt6"}'

echo -e "\033[34m #test del route# \033[0m"
post_401_request /api/v1/route_del
post_400_request /api/v1/route_del
post_200_request /api/v1/route_del  '{"route":"LR-edge6"}'

echo -e "\033[34m #first add edge node# \033[0m"
post_401_request /api/v1/edge_add
post_400_request /api/v1/edge_add
post_400_request /api/v1/edge_add   '{"phyBr":"br0"}'
post_400_request /api/v1/edge_add   '{"vip":"10.189.114.206/22"}'
post_500_request /api/v1/edge_add   '{"vip":"10.189.114.206/22","phyBr":"br0"}'

echo -e "\033[34m #init edge node# \033[0m"
post_401_request /api/v1/edge_init
post_400_request /api/v1/edge_init
post_400_request /api/v1/edge_init  '{"inner":"100.80.10.206/24","virt":"100.80.10.202/24","vip":"10.189.114.206/22","extGw":"10.189.112.1"}'
post_400_request /api/v1/edge_init  '{"phyBr":"br0","virt":"100.80.10.202/24","vip":"10.189.114.206/22","extGw":"10.189.112.1"}'
post_400_request /api/v1/edge_init  '{"phyBr":"br0","inner":"100.80.10.206/24","vip":"10.189.114.206/22","extGw":"10.189.112.1"}'
post_400_request /api/v1/edge_init  '{"phyBr":"br0","inner":"100.80.10.206/24","virt":"100.80.10.202/24","extGw":"10.189.112.1"}'
post_400_request /api/v1/edge_init  '{"phyBr":"br0","inner":"100.80.10.206/24","virt":"100.80.10.202/24","vip":"10.189.114.206/22"}'
post_200_request /api/v1/edge_init  '{"phyBr":"br0","inner":"100.80.10.206/24","virt":"100.80.10.202/24","vip":"10.189.114.206/22","extGw":"10.189.112.1"}'

echo -e "\033[34m #del edge node# \033[0m"
post_401_request /api/v1/edge_del
post_400_request /api/v1/edge_del
post_200_request /api/v1/edge_del  '{"vip":"10.189.114.206/22"}'

echo -e "\033[34m #test chassis del # \033[0m"
post_401_request /api/v1/chassis_del
post_400_request /api/v1/chassis_del
post_200_request /api/v1/chassis_del '{"chassis":"hv1"}'
post_500_request /api/v1/chassis_del '{"chassis":"127.0.0.1"}'

pass_test
