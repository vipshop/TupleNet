#!/bin/bash
. utils.sh

# set ovs runtime environment
ovs_setenv()
{
    sandbox=$1
    ovs_dir=$ovs_base/${sandbox}
    OVS_RUNDIR=$ovs_dir; export OVS_RUNDIR
    OVS_LOGDIR=$ovs_dir; export OVS_LOGDIR
    OVS_DBDIR=$ovs_dir; export OVS_DBDIR
    OVS_SYSCONFDIR=$ovs_dir; export OVS_SYSCONFDIR
    OVS_PKGDATADIR=$ovs_dir; export OVS_PKGDATADIR
}

start_ovs_daemon()
{
    "$@" -vconsole:off --detach --no-chdir --pidfile --log-file
    pidfile="$OVS_RUNDIR"/$1.pid
    on_ovs_exit "test -e \"$pidfile\" && kill \`cat \"$pidfile\"\`"
}

on_ovs_exit()
{
    (echo "$1"; cat $test_path/cleanup) > $test_path/cleanup.tmp
    mv $test_path/cleanup.tmp $test_path/cleanup
}

ovs_boot()
{
    local sim_id=$1
    local path=${ovs_base}/$1
    ovs_setenv $sim_id
    pmsg "start ovsdb-server instance $sim_id"
    start_ovs_daemon ovsdb-server --remote=punix:"$path"/db.sock || return 1
    ovs-vsctl --no-wait -- init || return 1
    pmsg "start ovs-vswitchd instance $sim_id"
    if [ "$DISABLE_DUMMY" == 1 ]; then
        pmsg "this ovs daemon disable dummy interface"
        start_ovs_daemon ovs-vswitchd -vvconn -vofproto_dpif \
                         -vunixctl || return 1
    else
        start_ovs_daemon ovs-vswitchd --enable-dummy=system -vvconn -vofproto_dpif \
                         -vunixctl || return 1
    fi
}

# create ovs simulator, this function start ovsdb-server and ovs-vswitchd
# ovs-vswitchd instance running with enable-dummy
sim_create()
{
    local sim_id=$1
    local path=${ovs_base}/$1
    mkdir -p $path || return 1
    ovs_setenv $sim_id
    ovsdb-tool create "$path"/conf.db \
      /usr/share/openvswitch/vswitch.ovsschema || return 1
    ovs_boot $sim_id || return 1
    ovs-vsctl set Open_vSwitch . external_ids:system-id=$1
    if [ $sim_id != main ]; then
        sim_array="$sim_array $sim_id"
    fi
}

sim_destroy()
{
    local sim_id=$1
    ovs_setenv $sim_id
    local pidfile="$OVS_RUNDIR"/ovsdb-server.pid
    test -e "$pidfile" && kill `cat $pidfile`
    pidfile="$OVS_RUNDIR"/ovs-vswitchd.pid
    test -e "$pidfile" && kill `cat $pidfile`
    remove_arp_from_array $sim_id
}

is_br_int_secure_failmode()
{
    local sim_id=$1
    ovs_setenv $sim_id
    mode=`ovs-vsctl get-fail-mode br-int`
    if [ "$mode" != "secure" ]; then
        return 1
    fi
    return 0
}

remove_sim_id_from_array()
{
    remove_sim=$1
    for sim_id in $sim_array; do
        if [ $sim_id == "$remove_sim" ]; then
            continue
        fi
        new_array="$sim_id $new_array"
    done
    sim_array=$new_array
}

# create main
net_create()
{
    test -d "$ovs_base"/main || sim_create main || return 1
    ovs_setenv main
    ovs-vsctl add-br "$1"
}

net_join()
{
    ovs_setenv main
    local net=$1
    local sim_id=$2
    local port=${net}_${sim_id}
    ovs-vsctl add-port $net $port \
      -- set Interface $port \
      options:pstream="punix:$ovs_base/main/$port.sock" \
      options:rxq_pcap="$ovs_base/main/$port-rx.pcap" \
      options:tx_pcap="$ovs_base/main/$port-tx.pcap" || return 1

    ovs_setenv $sim_id
    local sim_port="br0"
    local sim_bridge=$sim_port
    ovs-vsctl add-br $sim_bridge
    ovs-vsctl -- set Interface $sim_port \
      options:tx_pcap="$ovs_base/$sim_id/$sim_port-tx.pcap" \
      options:rxq_pcap="$ovs_base/$sim_id/$sim_port-rx.pcap" || return 1

    local sim_port=$sim_port-$net
    ovs-vsctl add-port $sim_bridge $sim_port -- set Interface $sim_port \
      options:stream="unix:$ovs_base/main/$port.sock" \
      options:tx_pcap="$ovs_base/$sim_id/$sim_port-tx.pcap" \
      options:rxq_pcap="$ovs_base/$sim_id/$sim_port-rx.pcap" || return 1
}

net_dropout()
{
    ovs_setenv main
    local net=$1
    local sim_id=$2
    local port=${net}_${sim_id}
    ovs-vsctl del-port $port || return 1

    ovs_setenv $sim_id
    local sim_bridge="br0"
    ovs-vsctl del-br $sim_bridge || return 1
    remove_arp_from_array $sim_id
}

port_add()
{
    # sometimes we cannot create ovs port, then try again
    t=0
    while ! _port_add $1 $2 $3 $4
    do
        if [ $t -ge 10 ]; then
            return 1
        fi
        sleep 0.5
        t=$((t+1))
    done
}

_port_add()
{
    if [ "$DISABLE_DUMMY" == 1 ]; then
        local sim_namespace=$1
        local ip_addr=$2
        local mac_addr=$3
        local gateway_ip_addr=$4
        local sim_port=nsport-$sim_namespace
        local sim_peer_port=ovsport-$sim_namespace
        pmsg "create ovs-port $sim_peer_port in namespace $sim_namespace"
        ip link add $sim_port type veth peer name $sim_peer_port || return 1
        ip link set $sim_port netns $sim_namespace || return 1
        ip link set dev $sim_peer_port up
        ovs-vsctl add-port "br-int" $sim_peer_port -- set Interface $sim_peer_port \
            external-ids:iface-id="$sim_peer_port" || return 1
        ip netns exec $sim_namespace ip addr add $ip_addr dev $sim_port || return 1
        ip netns exec $sim_namespace ip link set dev $sim_port up || return 1
        ip netns exec $sim_namespace ip link set dev $sim_port address $mac_addr || return 1
        ip netns exec $sim_namespace ip route add default via $gateway_ip_addr || return 1
        on_ovs_exit "ip link del $sim_peer_port"
    else
        local sim_id=$1
        local sim_port=$2
        pmsg "create ovs-port $sim_port in hypervisor $sim_id"
        ovs_setenv $sim_id
        ovs-vsctl add-port "br-int" $sim_port -- set Interface $sim_port \
            options:tx_pcap="$ovs_base/$sim_id/$sim_port-tx.pcap" \
            options:rxq_pcap="$ovs_base/$sim_id/$sim_port-rx.pcap" \
            external_ids:iface-id=$sim_port || return 1
    fi
    return 0
}

port_del()
{
    local sim_id=$1
    local sim_port=$2
    ovs_setenv $sim_id
    pmsg "delete ovs-port $sim_port in hypervisor $sim_id"
    ovs-vsctl del-port $sim_port || return 1
}

net_namespace_exec()
{
    ip netns exec $1  "$2"
}

net_namespace_del()
{
    local sim_namespace=$1
    ip netns del $sim_namespace >/dev/null 2>&1
}

net_namespace_add()
{
    local sim_namespace=$1
    net_namespace_del $sim_namespace
    ip netns add $sim_namespace || return 1
    ip netns exec $sim_namespace sysctl -w net.netfilter.nf_conntrack_helper=0
    on_ovs_exit "ip netns del $sim_namespace"

}

clear_ovsport_txpcap()
{
    local sim_id=$1
    local sim_port=$2
    ovs_setenv $sim_id
    pmsg "clear tx pcap file of ovs-port $sim_port in hypervisor $sim_id"
    echo "" > $ovs_base/$sim_id/$sim_port-tx.pcap
}

modify_port_iface_id()
{
    local sim_id=$1
    local sim_port=$2
    local iface_id=$3
    pmsg "change ${sim_id}'s ${sim_port} iface-id to ${iface_id}"
    ovs_setenv $sim_id
    ovs-vsctl set Interface $sim_port external_ids:iface-id=$iface_id || return 1
}

modify_port_iface_random_id()
{
    local sim_id=$1
    local sim_port=$2
    iface_id=`cat /proc/sys/kernel/random/uuid|awk -F'-' '{print $1}'`
    modify_port_iface_id $sim_id $sim_port $iface_id || return 1
}


print_bridge_detail()
{
    local sim_id=$1
    ovs_setenv $sim_id
    local output=`ovs-vsctl show`
    echo "$output"
}

inject_pkt()
{
    local sim_id=$1
    local port=$2
    local pkt=$3
    ovs_setenv $sim_id
    pmsg "inject packet $pkt"
    ovs-appctl netdev-dummy/receive $port $pkt || return 1
}

ip_to_hex()
{
    printf "%02x%02x%02x%02x" "$@"
}

int_to_hex()
{
    printf "%02x" "$@"
}

build_icmp_pkt()
{
    local eth_src=$1
    local eth_dst=$2
    local ip_src=$3
    local ip_dst=$4
    local ip_ttl=$5
    local ip_chksum=$6
    local icmp_chksum=$7
    local icmp_id=5fbf
    local icmp_seq=0001
    local icmp_data=$(seq 1 56 | xargs printf "%02x")
    local icmp_type_code_request=$8
    local icmp_payload=${icmp_type_code_request}${icmp_chksum}${icmp_id}${icmp_seq}${icmp_data}
    local packet=${eth_dst}${eth_src}08004500005400004000${ip_ttl}01${ip_chksum}${ip_src}${ip_dst}${icmp_payload}
    echo $packet
}

build_icmp_request()
{
    echo `build_icmp_pkt $1 $2 $3 $4 $5 $6 $7 0800`
}

build_icmp_response()
{
    echo `build_icmp_pkt $1 $2 $3 $4 $5 $6 $7 0000`
}

build_tcp_pkt()
{
    local eth_src=$1
    local eth_dst=$2
    local ip_src=$3
    local ip_dst=$4
    local ip_ttl=$5
    local ip_chksum=$6
    local tcp_src_port=`printf "%04x" $7`
    local tcp_dst_port=`printf "%04x" $8`
    local tcp_flag=$9
    local tcp_data=$(seq 1 56 | xargs printf "%02x")
    #                                               seq    ack-num tcp_len     win cksum urgent
    #                                               |       |       |           |   |   |
    #                                               V       V       V           V   V   V
    local tcp_payload=${tcp_src_port}${tcp_dst_port}4a97dd9c4456fa7a50${tcp_flag}00ee7cc50000
    #                                      len  id flag          tcp
    #                                        |   |   |            |
    #                                        V   V   V            V
    local packet=${eth_dst}${eth_src}08004500006079be4000${ip_ttl}06${ip_chksum}${ip_src}${ip_dst}${tcp_payload}${tcp_data}
    echo $packet
}

build_tcp_syn()
{
    echo `build_tcp_pkt $1 $2 $3 $4 $5 $6 $7 $8 12`
}

build_tcp_regular()
{
    echo `build_tcp_pkt $1 $2 $3 $4 $5 $6 $7 $8 10`
}

get_iface_tcpdump()
{
    local sim_id=$1
    local sim_port=$2
    local direction=$3
    ovs_setenv $sim_id
    echo "`tcpdump -r "$ovs_base/$sim_id/${sim_port}-${direction}.pcap" -n`"
}

get_tx_tcpdump()
{
    echo "`get_iface_tcpdump $1 $2 tx`"
}

get_rx_tcpdump()
{
    echo "`get_iface_tcpdump $1 $2 rx`"
}

get_iface_pkt()
{
    local sim_id=$1
    local sim_port=$2
    local direction=$3
    ovs_setenv $sim_id
    echo `$current_path/ovs-pcap "$ovs_base/$sim_id/${sim_port}-${direction}.pcap"`
}

get_tx_pkt()
{
    echo `get_iface_pkt $1 $2 tx`
}

get_rx_pkt()
{
    echo `get_iface_pkt $1 $2 rx`
}

get_tx_last_pkt()
{
    pkt_array=`get_tx_pkt $1 $2`
    echo ${pkt_array##* } # get last str which split by " "
}

get_rx_last_pkt()
{
    pkt_array=`get_rx_pkt $1 $2`
    echo ${pkt_array##* } # get last str which split by " "
}

get_ovs_iface_mac()
{
    local sim_id=$1
    local iface=$2
    ovs_setenv $sim_id
    local mac=`ovs-vsctl get Interface $iface mac_in_use | sed s/\"//g`
    echo $mac
}

get_ovs_iface_ofport()
{
    local sim_id=$1
    local iface=$2
    ovs_setenv $sim_id
    local ofport=`ovs-vsctl get Interface $iface ofport`
    echo $ofport
}

dump_ovs_info()
{
    pmsg "Try to dump $sim_array ovs information"
    for sim_id in $sim_array; do
        ovs_setenv $sim_id
        ovs-vsctl show > "$ovs_base/$sim_id/ovs-vsctl_show.txt"
        ovs-vsctl list interface > "$ovs_base/$sim_id/ovs-vsctl_list_interface.txt"
        ovs-vsctl list port > "$ovs_base/$sim_id/ovs-vsctl_list_port.txt"
        ovs-ofctl dump-flows br-int > "$ovs_base/$sim_id/ovs-ofctl_dump-flows.txt"
        ovs-ofctl dump-tlv-map br-int > "$ovs_base/$sim_id/ovs-ofctl_dump-tlv.txt"
        ovs-vsctl list ipfix > "$ovs_base/$sim_id/ovs-vsctl_list_ipfix.txt"
    done
}

verify_str()
{
    local cmp_type=$1
    local expect=$2
    local real=$3
    if [ "$expect" != "$real" ]; then
        pmsg "Error! expect!=real"
        pmsg "expect: $expect"
        pmsg "real:   $real"
        return 1
    fi
    pmsg "verify $cmp_type success, $cmp_type:$real"
    return 0
}

# check if expect packet is same as real receive packet
verify_pkt()
{
    verify_str pkt "$1" "$2"
}

# check if trace paths are same
verify_trace()
{
    verify_str trace "$1" "$2"
}

verify_ovsflow()
{
   verify_str ovsflow "$1" "$2"
}

verify_has_str()
{
    local orig_str="$1"
    local expect_has_str="$2"
    local ret=`echo "$orig_str" | grep "$expect_has_str" | wc -l`
    if [ "$ret" == 0 ]; then
        pmsg "orig_str:$orig_str"
        pmsg "expect_has_str:$expect_has_str"
        return 1
    fi
    return 0
}

config_bfd()
{
    local sim_id=$1
    local peer_chassis=$2
    local config=$3
    ovs_setenv $sim_id
    iface=`ovs-vsctl list interface|grep -E "name   |external_ids"|grep "chassis-id" -A 1|grep $peer_chassis -A 1|tail -n1|awk '{print \$3}'|sed s/\"//g`
    pmsg "set Interface $iface bfd:$config"
    ovs-vsctl set Interface $iface bfd:$config || return 1
}

enable_bfd()
{
    config_bfd $1 $2 "enable=true" || return 1
}

disable_bfd()
{
    config_bfd $1 $2 "enable=false" || return 1
}

is_tunnel_bfd_fit()
{
    local sim_id=$1
    local peer_chassis=$2
    local expect_config=$3
    ovs_setenv $sim_id
    iface=`ovs-vsctl list interface|grep -E "name   |external_ids"|grep "chassis-id" -A 1|grep $peer_chassis -A 1|tail -n1|awk '{print \$3}'|sed s/\"//g`
    config=`ovs-vsctl get Interface $iface bfd`
    if [ "$config" != "$expect_config" ]; then
        pmsg "config:$config, expect_config:$expect_config"
        return 1
    fi
}

is_tunnel_bfd_enable()
{
    is_tunnel_bfd_fit $1 $2 "{enable=\"true\"}"
    return $?
}

is_tunnel_bfd_disable()
{
    is_tunnel_bfd_fit $1 $2 "{enable=\"false\"}"
    return $?
}

is_tunnel_bfd_none()
{
    is_tunnel_bfd_fit $1 $2 "{}"
    return $?
}

ovs_verify_drop_pkt_num()
{
    local sim_id=$1
    local expect_num=$2
    ovs_setenv $sim_id
    num=`ovs-ofctl dump-flows br-int|grep "actions=drop"|awk '{print $4}'|awk -F '=|,' '{print $2}'`
    if [ "$num" != "$expect_num" ]; then
        pmsg "expect drop num:$expect_num, real drop num:$num"
        return 1
    fi
}

get_ovs_flows()
{
    echo "`ovs-ofctl dump-flows br-int|awk '{print $3 $7 $8}'`"
}

get_ovs_flows_num()
{
    flows=`get_ovs_flows`
    # we should grep table here, because dump-flows will contain extra lines
    len=`echo "$flows"|grep table|wc -l`
    echo $len
}

get_ovs_flows_sorted()
{
    flows="`get_ovs_flows`"
    flows="`echo "$flows" | sort`"
    echo "$flows"
}

wait_for_flows_unchange()
{
    if [ $# == 1 ]; then
        sleep_time=$1
    else
        if [ -z "$WAIT_FLOW_TIMEOUT" ]; then
            sleep_time=3
        else
            sleep_time=$WAIT_FLOW_TIMEOUT
        fi
    fi

    start_time=$(date +%s)
    pmsg "waiting for ovs-flows...."

    prev_flows_array=""
    current_flows_array=""
    for sim_id in $sim_array; do
        ovs_setenv $sim_id
        # get ovs-flow's table,match,action
        current_flows=`get_ovs_flows`
        current_flows_array="$current_flows $current_flows_array"
    done

    while [ "$current_flows_array" != "$prev_flows_array" ]
    do
        prev_flows_array=$current_flows_array
        sleep $sleep_time
        current_flows_array=""
        for sim_id in $sim_array; do
            ovs_setenv $sim_id
            # get ovs-flow's table,match,action
            current_flows=`get_ovs_flows`
            current_flows_array="$current_flows $current_flows_array"
        done
    done
    end_time=$(date +%s)
    cost_time=$((end_time - start_time))
    pmsg "inserting ovs-flows cost $cost_time second"
}

wait_for_brint()
{
    start_time=$(date +%s)
    pmsg "waiting for building br-int...."
    i=1
    for sim_id in $sim_array; do
        ovs_setenv $sim_id
        ovs-vsctl list interface br-int >/dev/null 2>&1
        while [ "$?" != 0 ]; do
            if [ $i == 10 ]; then
                echo "cannot get br-int in $OVS_RUNDIR, exit waiting" >&2
                break
            fi
            sleep 1;
            i=$((i+1))
            ovs-vsctl list interface br-int >/dev/null 2>&1
        done
    done

    end_time=$(date +%s)
    cost_time=$((end_time - start_time))
    pmsg "building br-int cost $cost_time second"
}

wait_bfd_state_up()
{
    local sim_id=$1
    local peer_chassis=$2
    ovs_setenv $sim_id
    iface=`ovs-vsctl list interface|grep -E "name   |external_ids"|grep "chassis-id" -A 1|grep $peer_chassis -A 1|tail -n1|awk '{print \$3}'|sed s/\"//g`

    i=0
    while [ $i -le 10 ]; do
        i=$((i+1))
        config=`ovs-vsctl get Interface $iface bfd_status:state`
        if [ "$config" != "up" ]; then
            pmsg "bfd state:$config, iface=$iface"
            sleep 3
        else
            return 0
        fi
    done
    pmsg "exceed 30s, bfd state is not in up state"
    return 1
}

is_port_exist()
{
    sim_id=$1
    port=$2
    ovs_setenv $sim_id
    ovs-vsctl get interface $port name >/dev/null 2>&1
    return $?
}

get_tunnel_port_chassis_id()
{
    sim_id=$1
    port=$2
    ovs_setenv $sim_id
    echo `ovs-vsctl get interface $port external_ids:chassis-id|sed s/\"//g`
}
