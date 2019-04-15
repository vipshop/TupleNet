#!/bin/bash
. ovs_utils.sh

tuplenet_init()
{
    pmsg "init tuplenet env"
    tuplenet_prefix="$1"/; export tuplenet_prefix
}

tuplenet_setenv()
{
    sandbox=$1
    tuplenet_dir=$tuplenet_base/$sandbox
    TUPLENET_RUNDIR=$tuplenet_dir; export TUPLENET_RUNDIR
    TUPLENET_LOGDIR=$tuplenet_dir; export TUPLENET_LOGDIR
}

on_tuplenet_exit()
{
    (echo "$1"; cat $test_path/cleanup) > $test_path/cleanup.tmp
    mv $test_path/cleanup.tmp $test_path/cleanup
}

kill_tuplenet_daemon()
{
    local sim_id=$1
    local signal=$2
    ovs_setenv $sim_id
    tuplenet_setenv $sim_id
    local pidfile="$TUPLENET_RUNDIR"/tuplerun.py.pid
    test -e "$pidfile" && kill $signal `cat $pidfile` # $2 was the signal
}

tuplenet_boot()
{
    local sim_id=$1
    local ip=$2
    ovs_setenv $sim_id
    tuplenet_setenv $sim_id
    if [ "$DISABLE_DUMMY" == 1 ]; then
        :
    else
        pmsg "set ip4addr, route"
        ovs-appctl netdev-dummy/ip4addr "br0" $ip/24 >/dev/null  || return 1
        ovs-appctl ovs/route/add $ip/24 "br0" >/dev/null  || return 1
    fi

    pmsg "start tuplenet main instance $sim_id"
    $PYTHON ../tuplenet/lcp/tuplerun.py -a $etcd_client_specs -i 1 -f $ip -l $TUPLENET_LOGDIR -p $tuplenet_prefix >/dev/null 2>&1 &
    local pidfile="$TUPLENET_RUNDIR"/tuplerun.py.pid
    on_tuplenet_exit "test -e \"$pidfile\" && kill \`cat \"$pidfile\"\`"
}

# start tuplerun and link_master instance to manage ovs
start_tuplenet_daemon()
{
    local sim_id=$1
    local ip=$2

    ovs_setenv $sim_id

    if [ "$DISABLE_DUMMY" == 1 ]; then
        :
    else
        update_arp_table $sim_id $ip
    fi

    tuplenet_setenv $sim_id
    mkdir -p $TUPLENET_RUNDIR
    tuplenet_boot $sim_id $ip
}

update_arp_table()
{
    sim_id=$1
    ip=$2
    bridge="br0"
    mac=`ovs-vsctl get Interface br0 mac_in_use | sed s/\"//g`
    arp_table="$arp_table $sim_id,$bridge,$ip,$mac"
}

remove_arp_from_array()
{
    local sim_id=$1
    local new_arp_table=""
    for e1 in $arp_table; do
        set `echo $e1 | sed 's/,/ /g'`; sb1=$1 br1=$2 ip=$3 mac=$4
        if [ $sb1 != $sim_id ] ; then
            new_arp_table="$new_arp_table $sb1,$br1,$ip,$mac"
        fi
    done
    arp_table=$new_arp_table
}

#install arp table into bridge, then the testing packet would not trigger
# arp again and would not be drop.
install_arp()
{
    pmsg "arp table:$arp_table"
    for e1 in $arp_table; do
        set `echo $e1 | sed 's/,/ /g'`; sb1=$1 br1=$2 ip=$3 mac=$4
        for e2 in $arp_table; do
            set `echo $e2 | sed 's/,/ /g'`; sb2=$1 br2=$2
            if test $sb1,$br1 != $sb2,$br2; then
                ovs_setenv $sb2
                ovs-appctl tnl/neigh/set $br2 $ip $mac > /dev/null
            fi
        done
    done
}

flush_arp()
{
    hv_array="$1"
    pmsg "flush $hv_array arp table"

    for hv in $hv_array; do
        ovs_setenv $hv
        ovs-appctl tnl/neigh/flush
    done
}

inject_trace_packet()
{
    if [ -z "$TRACE_WAIT_TIME" ]; then
        TRACE_WAIT_TIME=3
    fi
    if [ $# == 1 ]; then
        $PYTHON ../tuplenet/tools/pkt-trace.py --endpoints $etcd_client_specs  -p $tuplenet_prefix --wait_time=$TRACE_WAIT_TIME --auto_detect $1
    elif [ $# == 2 ]; then
        local port=$1
        local pkt=$2
        $PYTHON ../tuplenet/tools/pkt-trace.py --endpoints $etcd_client_specs -j $port -p $tuplenet_prefix -d $pkt --wait_time=$TRACE_WAIT_TIME
    else
        local port=$1
        local src_mac=$2
        local src_ip=$3
        local dst_mac=$4
        local dst_ip=$5
        $PYTHON ../tuplenet/tools/pkt-trace.py --endpoints $etcd_client_specs -j $port -p $tuplenet_prefix \
                --src_mac $src_mac --src_ip $src_ip --dst_mac $dst_mac --dst_ip $dst_ip --wait_time=$TRACE_WAIT_TIME
    fi
}

init_ecmp_road()
{
    sim_id=$1
    vip=$2
    virt=$3
    inner="100.64.88.200/24"
    ext_gw=$4
    # NOTE: only one etcd address
    ovs_setenv $sim_id
    echo "yes" |  PATH=$PATH:$CONTROL_BIN_PATH/bin/  $PYTHON ../tuplenet/tools/edge-operate.py --endpoint $etcd_client_specs \
                       --prefix $tuplenet_prefix --op=init \
                       --phy_br=br0 --vip=$vip --virt=$virt \
                       --inner=$inner --ext_gw=$ext_gw || return 1
}

add_ecmp_road()
{
    sim_id=$1
    vip=$2
    # NOTE: only one etcd address
    ovs_setenv $sim_id
    echo "yes" |  PATH=$PATH:$CONTROL_BIN_PATH/bin/  $PYTHON ../tuplenet/tools/edge-operate.py --endpoint $etcd_client_specs \
                       --prefix $tuplenet_prefix --op=add \
                       --phy_br=br0 --vip=$vip || return 1
}

remove_ecmp_road()
{
    sim_id=$1
    vip=$2
    # NOTE: only one etcd address
    ovs_setenv $sim_id
    tuplenet_setenv $sim_id
    echo "yes" |  PATH=$PATH:$CONTROL_BIN_PATH/bin/  $PYTHON ../tuplenet/tools/edge-operate.py --endpoint $etcd_client_specs \
                       --prefix $tuplenet_prefix --op=remove \
                       --phy_br=br0 --vip=$vip || return 1
}

tp_add_patchport()
{
    sim_id=$1
    chassis=$sim_id
    lsname=$2
    portname=$3
    ovs_setenv $sim_id
    tuplenet_setenv $sim_id
    tpctl patchport add $lsname $portname $chassis br0 || return 1
}
