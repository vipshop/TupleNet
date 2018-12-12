#!/usr/bin/env bash
. env_utils.sh ; skip_if_in_container

pmsg "preparing env"
env_init ${0##*/} # 0##*/ is the filename

PLUGIN_CONFIG_PATH=${test_path}/config.json
PLUGIN_PID=0

add_revert() {
    sed '0,/^/ s//__PLACEHOLDER__\n/' -i ${test_path}/cleanup
    sed "s|__PLACEHOLDER__|$1|" -i ${test_path}/cleanup
}

run_tpcnm_with_cfg() {
    if [ $PLUGIN_PID -ne 0 ];then
        kill -9 $PLUGIN_PID
    fi
    mkdir -p /run/docker/plugins/

    echo "$1" > ${PLUGIN_CONFIG_PATH}
    ${CONTROL_BIN_PATH}bin/tpcnm  -config=${PLUGIN_CONFIG_PATH} &>>${test_path}/tpcnm.log &
    NEW_PID=$!
    sleep 2
    kill -0 $NEW_PID || (echo 'tpcnm is not running' ; exit_test)

    if [ $PLUGIN_PID -ne 0 ];then
        sed "s/kill -9 $PLUGIN_PID$/kill -9 $NEW_PID/" -i ${test_path}/cleanup
    else
        add_revert "kill -9 $NEW_PID"
    fi

    PLUGIN_PID=${NEW_PID}
}

run_dockerd_and_build_image(){
    # can only use /tmp, or containerd complains: unix socket path too long (> 104)
    if [ -n "$USE_SYSTEM_DOCKER" ]; then
        DOCKER_PATH=/var
        echo "pidof docker:`pidof dockerd`"
        if [ -f "/etc/init.d/docker" ]; then
            pmsg "try to stop and kill dockerd"
            /etc/init.d/docker stop
        fi

        kill -TERM `pidof dockerd`
    fi
    DOCKER_PATH=/tmp/$(basename $0)
    mkdir ${DOCKER_PATH}
    dockerd --cluster-store etcd://${etcd_client_specs} \
            --data-root ${DOCKER_PATH}/lib --exec-root ${DOCKER_PATH}/run \
            --pidfile ${DOCKER_PATH}/run/docker.pid \
            -H unix://${DOCKER_PATH}/run/docker.sock &>${test_path}/dockerd.log &
    pid=$!
    add_revert "kill -9 $pid"
    add_revert "rm -rf ${DOCKER_PATH}"

    if [ $(local_docker images --filter=reference="${TAG}:*" | wc -l) == "1" ];then
    mkdir ${test_path}/image
    cp alpine-minirootfs-3.8.1-x86_64.tar.gz ${test_path}/image
    cat > ${test_path}/image/Dockerfile <<EOF
FROM scratch
ADD alpine-minirootfs-3.8.1-x86_64.tar.gz /
EOF
        cd ${test_path}/image
        TAG="tpcnm-test"
        local_docker build --tag ${TAG} . || exit_test
        cd -
    fi

}

local_docker() {
    docker -H unix://${DOCKER_PATH}/run/docker.sock "$@"
}


create_container() {
    id=$(local_docker run --rm --net=$1 -td ${TAG} /bin/sh) || exit_test
    add_revert "docker -H unix://${DOCKER_PATH}/run/docker.sock kill ${id}"
    while read action;do
        add_revert "${action}"
    done <<< $(mount | grep -F ${id} | awk  '{printf "umount %s\n", $3}')
    echo $id
}

# setup
pmsg "building tpctl and tpcnm"
bash ${CONTROL_BIN_PATH}/build.sh || exit_test


# start ovs
DISABLE_DUMMY=1
sim_create hv1 || exit_test
ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv1 172.20.11.1 || exit_test
wait_for_brint # waiting for building br-int bridge

# prepare docker environment
run_dockerd_and_build_image

# run tpcnm before docker
run_tpcnm_with_cfg "
{
    \"etcd_cluster\": \"${etcd_client_specs}\",
    \"data_store_prefix\": \"${DATA_STORE_PREFIX}\",
    \"docker_unix_sock\": \"${DOCKER_PATH}/run/docker.sock\"
}
"

# create net1 
net1=$(local_docker network create --driver=tuplenet --subnet=10.0.1.1/24 --gateway=10.0.1.1 net1) || exit_test
result="$(tpctl ls show ${net1})"
expected="
${net1}:
  - id: 1
"
equal_str "$result" "$expected" || exit_test

# test intra logical switch connectivity
container11=$(create_container $net1) || exit_test
container12=$(create_container $net1) || exit_test

wait_for_flows_unchange

ip11=$(local_docker exec ${container11} ip -4 addr show eth0 | grep -oP "(?<=inet ).*(?=/)") || exit_test
ip12=$(local_docker exec ${container12} ip -4 addr show eth0 | grep -oP "(?<=inet ).*(?=/)") || exit_test
echo '----------------'
local_docker exec ${container11} ip route
echo '----------------'
local_docker exec ${container11} ping ${ip12} -c 1 -W 1 || exit_test

# create net2
net2=$(local_docker network create --driver=tuplenet --subnet=10.0.2.1/24 --gateway=10.0.2.1 net2) || exit_test
result="$(tpctl ls show ${net2})"
expected="
${net2}:
  - id: 2
"
equal_str "$result" "$expected" || exit_test

tpctl ch show

container21=$(create_container $net2) || exit_test
container22=$(create_container $net2) || exit_test
ip21=$(local_docker exec ${container21} ip -4 addr show eth0 | grep -oP "(?<=inet ).*(?=/)") || exit_test
ip22=$(local_docker exec ${container21} ip -4 addr show eth0 | grep -oP "(?<=inet ).*(?=/)") || exit_test
local_docker exec ${container21} ping ${ip22} -c 1 -W 1 || exit_test
!(local_docker exec ${container11} ping ${ip21} -c 1 -W 1) || exit_test
!(local_docker exec ${container12} ping ${ip21} -c 1 -W 1) || exit_test
!(local_docker exec ${container11} ping ${ip22} -c 1 -W 1) || exit_test
!(local_docker exec ${container12} ping ${ip22} -c 1 -W 1) || exit_test

tpctl lr add LR-1 || exit_test
tpctl lr link LR-1 ${net1} 10.0.1.1/24 || exit_test
tpctl lr link LR-1 ${net2} 10.0.2.1/24 || exit_test

wait_for_flows_unchange

local_docker exec ${container21} ping ${ip22} -c 1 -W 1 || exit_test
local_docker exec ${container11} ping ${ip12} -c 1 -W 1 || exit_test
local_docker exec ${container11} ping ${ip21} -c 1 -W 1 || exit_test
local_docker exec ${container12} ping ${ip21} -c 1 -W 1 || exit_test
local_docker exec ${container12} ping ${ip22} -c 1 -W 1 || exit_test

tpctl lr add LR-2 || exit_test

run_tpcnm_with_cfg "
{
    \"etcd_cluster\": \"${etcd_client_specs}\",
    \"data_store_prefix\": \"${DATA_STORE_PREFIX}\",
    \"egress_router_name\": \"LR-2\",
    \"docker_unix_sock\": \"${DOCKER_PATH}/run/docker.sock\"
}
"

net3=$(local_docker network create --driver=tuplenet --subnet=10.0.3.1/24 --gateway=10.0.3.1 net3) || exit_test
result="$(tpctl lrp show LR-2)" || exit_test
expected="
to_${net3}:
  - ip    : 10.0.3.1
  - prefix: 24
  - mac   : f2:01:0a:00:03:01
  - peer  : to_LR-2
"
equal_str "$result" "$expected" || exit_test
container31=$(create_container $net3) || exit_test
ip31=$(local_docker exec ${container31} ip -4 addr show eth0 | grep -oP "(?<=inet ).*(?=/)") || exit_test
container32=$(create_container $net3) || exit_test
ip32=$(local_docker exec ${container32} ip -4 addr show eth0 | grep -oP "(?<=inet ).*(?=/)") || exit_test
wait_for_flows_unchange  # waiting for updating ovs-flow
local_docker exec ${container31} ping ${ip32} -c 1 -W 1 || exit_test
!(local_docker exec ${container11} ping ${ip31} -c 1 -W 1) || exit_test
!(local_docker exec ${container12} ping ${ip31} -c 1 -W 1) || exit_test
!(local_docker exec ${container21} ping ${ip31} -c 1 -W 1) || exit_test
!(local_docker exec ${container21} ping ${ip32} -c 1 -W 1) || exit_test

tpctl lrp add LR-1 lr1_to_br1 10.0.0.1/24 "" br1_to_lr1 || exit_test
tpctl lrp add LR-2 lr2_to_br1 10.0.0.2/24 "" br1_to_lr2 || exit_test
tpctl lsr add LR-1 r1 10.0.3.0/24 10.0.0.2 lr1_to_br1 || exit_test
tpctl lsr add LR-2 r3 10.0.1.0/24 10.0.0.1 lr2_to_br1 || exit_test
tpctl lsr add LR-2 r2 10.0.2.0/24 10.0.0.1 lr2_to_br1 || exit_test

tpctl ls add BR-1 || exit_test
tpctl lsp add BR-1 br1_to_lr1 10.0.0.1 "" lr1_to_br1 || exit_test
tpctl lsp add BR-1 br1_to_lr2 10.0.0.2 "" lr2_to_br1 || exit_test

wait_for_flows_unchange

local_docker exec ${container11} ping ${ip12} -c 1 -W 1 || exit_test
local_docker exec ${container21} ping ${ip22} -c 1 -W 1 || exit_test
local_docker exec ${container31} ping ${ip32} -c 1 -W 1 || exit_test
local_docker exec ${container11} ping ${ip21} -c 1 -W 1 || exit_test
local_docker exec ${container11} ping ${ip22} -c 1 -W 1 || exit_test
local_docker exec ${container12} ping ${ip21} -c 1 -W 1 || exit_test
local_docker exec ${container12} ping ${ip22} -c 1 -W 1 || exit_test
local_docker exec ${container11} ping ${ip31} -c 1 -W 1 || exit_test
local_docker exec ${container11} ping ${ip32} -c 1 -W 1 || exit_test
local_docker exec ${container12} ping ${ip31} -c 1 -W 1 || exit_test
local_docker exec ${container12} ping ${ip32} -c 1 -W 1 || exit_test
local_docker exec ${container21} ping ${ip31} -c 1 -W 1 || exit_test
local_docker exec ${container21} ping ${ip32} -c 1 -W 1 || exit_test
local_docker exec ${container22} ping ${ip31} -c 1 -W 1 || exit_test
local_docker exec ${container22} ping ${ip32} -c 1 -W 1 || exit_test

pass_test
