#!/bin/bash
. ovs_utils.sh
. tuplenet_utils.sh
. etcd_utils.sh
. http_utils.sh

env_init()
{
    test_name=$1
    current_path=`pwd`
    test_path=$current_path/dir_test/$test_name
    ovs_base=$test_path/ovs
    tuplenet_base=$test_path/tuplenet
    etcd_base=$test_path/etcd
    rm -rf $test_path
    mkdir -p $tuplenet_base
    mkdir -p $ovs_base
    mkdir -p $etcd_base
    trap '. "$test_path/cleanup"' 0
    : > $test_path/cleanup

    tuplenet_init $test_name
    run_etcd_instance
    . tpcli_utils.sh
}

skip_if_in_container()
{
    cgroup="`cat /proc/1/cgroup`"
    ret=`echo "$cgroup"|grep -E "lxc|docker"|wc -l`
    if [ $ret != 0 ]; then
        exit 0
    fi
}

random_short_str()
{
    rand="`cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 3 | head -n 1`"
    echo "$1${rand}"
}

exit_test()
{
    printf "${COLOR_RED}failed at $test_name:$BASH_LINENO\n${COLOR_RESET}"
    dump_ovs_info
    dump_etcd_kv
    exit 1
}

pass_test()
{
    printf "${COLOR_GREEN}PASS $test_name\n${COLOR_RESET}"
    dump_ovs_info
    dump_etcd_kv
    exit 0
}

