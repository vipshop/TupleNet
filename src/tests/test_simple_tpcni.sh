#!/usr/bin/env bash
#noparallel
. env_utils.sh
skip_if_in_container

pmsg "preparing env"
env_init ${0##*/} # 0##*/ is the filename

LS_A="LS-A"
conf_path=${test_path}/mytpcni.conf
subnet="10.10.1.1/28"
cat <<EOF  > $conf_path
{
    "cniVersion": "0.3.0",
    "name": "tpcni-network",
    "type": "tpcni",
    "mtu": 1400,
    "switchname": "${LS_A}",
    "subnet": "${subnet}",
    "etcd_cluster": "${etcd_client_specs}",
    "data_store_prefix": "${DATA_STORE_PREFIX}"
}
EOF

add_revert() {
    sed '0,/^/ s//__PLACEHOLDER__\n/' -i ${test_path}/cleanup
    sed "s|__PLACEHOLDER__|$1|" -i ${test_path}/cleanup
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
    dockerd --data-root ${DOCKER_PATH}/lib --exec-root ${DOCKER_PATH}/run \
            --pidfile ${DOCKER_PATH}/run/docker.pid \
            -H unix://${DOCKER_PATH}/run/docker.sock &>${test_path}/dockerd.log &
    pid=$!
    add_revert "kill -9 $pid"
    add_revert "rm -rf ${DOCKER_PATH}"

    sleep 2

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

check_container_num() {
    expect=$1
    cnum=$((`local_docker ps|wc -l` - 1))
    if [ "$expect" != "$cnum" ]; then
        pmsg "expect container num:$expect, current container num:$cnum"
        return 1
    fi
    return 0
}


create_container() {
    id=$(local_docker run --rm --net=none -td ${TAG} /bin/sh) || exit_test
    add_revert "docker -H unix://${DOCKER_PATH}/run/docker.sock kill ${id}"
    while read action;do
        add_revert "${action}"
    done <<< $(mount | grep -F ${id} | awk  '{printf "umount %s\n", $3}')
    echo $id
}

stop_container() {
    id=$1
    output=`local_docker stop $id`
    ret=$?
    pmsg "$output"
    return $ret
}

container_ns() {
    id=$1
    info="$(local_docker inspect $id)" || exit_test
    ns=`echo "$info" | grep -w "SandboxKey"| awk '{print $2}' | sed s/\"//g | sed s/\,//g`
    echo $ns
}

tpcni_add() {
    id=$1
    ns=$2
    out=`CNI_COMMAND=ADD CNI_CONTAINERID=$id CNI_NETNS=$ns CNI_IFNAME=eth0 CNI_PATH=/tmp/ ${CONTROL_BIN_PATH}bin/tpcni < $conf_path`
    ret=$?
    pmsg "$out"
    return $ret
}

tpcni_del() {
    id=$1
    ns=$2
    out=`CNI_COMMAND=DEL CNI_CONTAINERID=$id CNI_NETNS=$ns CNI_IFNAME=eth0 CNI_PATH=/tmp/ ${CONTROL_BIN_PATH}bin/tpcni < $conf_path`
    ret=$?
    pmsg "$out"
    return $ret
}

check_lsp_ip() {
    lsp_name=$1
    expect_ip=$2
    output="`tpctl lsp show $LS_A $lsp_name | grep -w "$expect_ip"| wc -l`"
    if [ $output != "1" ]; then
        pmsg "$lsp_name get no ip of $expect_ip"
        return 1
    fi
    return 0
}

find_ovsport_by_lsp() {
    lsp=$1
    isexist="`ovs-vsctl --columns=name find interface external_ids={iface-id=$lsp} | wc -l`"
    if [ "$isexist" != "1" ]; then
        return 1
    fi
    return 0
}

# setup
pmsg "building tpctl and tpcni"
bash ${CONTROL_BIN_PATH}/build.sh || exit_test


# start ovs
DISABLE_DUMMY=1
sim_create hv1 || exit_test
ONDEMAND=0 GATEWAY=1 start_tuplenet_daemon hv1 172.20.11.1 || exit_test
wait_for_brint # waiting for building br-int bridge

# prepare docker environment
run_dockerd_and_build_image

tpctl lr add LR-central || exit_test
tpctl ls add $LS_A || exit_test

# test intra logical switch connectivity
container1=$(create_container) || exit_test
container2=$(create_container) || exit_test
ns1=$(container_ns $container1)
ns2=$(container_ns $container2)
tpcni_add $container1 $ns1 || exit_test
tpcni_add $container2 $ns2 || exit_test
lsp_name1="lsp-eth0-$container1"
lsp_name2="lsp-eth0-$container2"
tpctl lsp show $LS_A $lsp_name1 || exit_test
tpctl lsp show $LS_A $lsp_name2 || exit_test

ip2=$(local_docker exec ${container2} ip -4 addr show eth0 | grep -oP "(?<=inet ).*(?=/)") || exit_test

wait_for_flows_unchange

gwip="10.10.1.1"
! local_docker exec ${container1} ping ${gwip} -c 1 -W 1 || exit_test
tpctl lr link LR-central $LS_A $subnet
wait_for_flows_unchange
local_docker exec ${container1} ping ${gwip} -c 1 -W 1 || exit_test
local_docker exec ${container1} ping ${ip2} -c 1 -W 1 || exit_test
# execute tpcni_add again, tpcni should return error
pmsg "execute tpcni_add again on same container again"
! tpcni_add $container1 $ns1 || exit_test

# delete container2's eth
find_ovsport_by_lsp $lsp_name2 || exit_test
tpcni_del $container2 $ns2 || exit_test
! find_ovsport_by_lsp $lsp_name2 || exit_test
# delete container2's eth again, tpcni should return without error
pmsg "execute tpcni_del again on same container again"
tpcni_del $container2 $ns2 || exit_test
! tpctl lsp show $LS_A $lsp_name2 || exit_test
local_docker exec ${container1} ping ${gwip} -c 1 -W 1 || exit_test
! local_docker exec ${container1} ping ${ip2} -c 1 -W 1 || exit_test

find_ovsport_by_lsp $lsp_name1 || exit_test
tpcni_del $container1 $ns1 || exit_test
! find_ovsport_by_lsp $lsp_name1 || exit_test
! tpctl lsp show $LS_A $lsp_name1 || exit_test
check_container_num 2 || exit_test
stop_container $container1 || exit_test
stop_container $container2 || exit_test
check_container_num 0 || exit_test

# add container config eth as many as possible
for i in {2..20}; do
    container=$(create_container) || exit_test
    ns=$(container_ns $container)
    lsp_name="lsp-eth0-$container"

    cid_array[$i]=$container
    ns_array[$i]=$ns
    lsp_array[$i]=$lsp_name

    if [ $i -ge 15 ]; then
        ! tpcni_add $container $ns || exit_test
        ! tpctl lsp show $LS_A $lsp_name || exit_test
    else
        tpcni_add $container $ns || exit_test
        tpctl lsp show $LS_A $lsp_name || exit_test
        check_lsp_ip $lsp_name 10.10.1.${i} || exit_test
    fi
done

wait_for_flows_unchange
local_docker exec ${cid_array[5]} ping 10.10.1.3  -c 1 -W 1 || exit_test
local_docker exec ${cid_array[5]} ping 10.10.1.4  -c 1 -W 1 || exit_test

# remove this container's nic
tpcni_del ${cid_array[4]} ${ns_array[4]} || exit_test
! check_lsp_ip ${lsp_array[4]} 10.10.1.4 || exit_test
! local_docker exec ${cid_array[5]} ping 10.10.1.4  -c 1 -W 1 || exit_test
# add nic back
tpcni_add ${cid_array[4]} ${ns_array[4]} || exit_test
wait_for_flows_unchange
local_docker exec ${cid_array[5]} ping 10.10.1.4  -c 1 -W 1 || exit_test
check_lsp_ip ${lsp_array[4]} 10.10.1.4 || exit_test

pass_test
