#!/bin/bash
. utils.sh

instance_num=0
run_etcd_instance()
{
    if [ -z "$MAX_ETCD_INSTANCE" ]; then
        MAX_ETCD_INSTANCE=1
    fi

    i=0
    while [ $i -lt $MAX_ETCD_INSTANCE ]; do
        cport[$i]=`get_unbind_port`
        consumed_port="$consumed_port ${cport[$i]}"
        pport[$i]=`get_unbind_port $cport`
        consumed_port="$consumed_port ${pport[$i]}"
        name[$i]="tuplenet-etcd-${i}"
        data_dir[$i]="${etcd_base}/${name[$i]}-default.etcd"
        client_spec[$i]="127.0.0.1:${cport[$i]}"
        client_url[$i]="http://${client_spec[$i]}"
        peer_url[$i]="http://127.0.0.1:${pport[$i]}"
        log_file[$i]=${etcd_base}/${name[$i]}.log
        cluster="$cluster,${name[$i]}=${peer_url[$i]}"
        etcd_client_specs="$etcd_client_specs,${client_spec[$i]}"
        i=$((i+1))
    done

    cluster=${cluster:1} #delete the ,
    etcd_client_specs=${etcd_client_specs:1}
    pmsg "etcd_client_specs: $etcd_client_specs"
    pmsg "cluster: $cluster"
    while [ $instance_num -lt $MAX_ETCD_INSTANCE ]; do
        etcd --name=${name[$instance_num]} --data-dir=${data_dir[$instance_num]} \
             --listen-client-urls=${client_url[$instance_num]} \
             --advertise-client-urls=${client_url[$instance_num]} \
             --initial-advertise-peer-urls=${peer_url[$instance_num]} \
             --listen-peer-urls=${peer_url[$instance_num]} \
             --initial-cluster=$cluster \
             -initial-cluster-state=new >${log_file[$instance_num]} 2>&1 &
        etcd_pid[$instance_num]=$!
        on_etcd_exit "kill ${etcd_pid[$instance_num]} 2>/dev/null; sleep 2; kill -9 ${etcd_pid[$instance_num]} 2>/dev/null"
        instance_num=$((instance_num+1))
    done

    if [ $instance_num != 1 ]; then
        pmsg "sleep 6s to give etcd cluster sync time"
        sleep 6
    else
        sleep 2
    fi
    print_etcd_member_list
}

start_etcd_instance()
{
    idx=$1
    etcd --name=${name[$idx]} --data-dir=${data_dir[$idx]} \
         --listen-client-urls=${client_url[$idx]} \
         --advertise-client-urls=${client_url[$idx]} \
         --initial-advertise-peer-urls=${peer_url[$idx]} \
         --listen-peer-urls=${peer_url[$idx]} \
         --initial-cluster=$cluster \
         -initial-cluster-state=new >>${log_file[$idx]} 2>&1 &
    etcd_pid[$idx]=$!
    pmsg "start etcd instance ${name[$idx]}, pid:${etcd_pid[$idx]}"
    on_etcd_exit "kill ${etcd_pid[$idx]} 2>/dev/null; sleep 1; kill -9  ${etcd_pid[$idx]} 2>/dev/null"
}

stop_etcd_instance()
{
    idx=$1
    pmsg "kill etcd instance ${name[$idx]}, pid:${etcd_pid[$idx]}"
    kill ${etcd_pid[$idx]} 2>/dev/null; sleep 1; kill -9 ${etcd_pid[$idx]} 2>/dev/null
}

# get tcp port hasn't been used
get_unbind_port()
{
    bindports=`netstat -nltp|grep tcp|grep -v tcp6|awk '{print $4}'|awk -F':' '{print $2}'|sort -n|uniq`
    if [ $# == 1 ]; then
        bindports="$bindports $1"
    fi
    while [ 1 == 1 ]; do
        port=$RANDOM
        port=$((port%3000 + 2000))
        if [ `echo "$bindports"|grep $port|wc -l` -eq 1 ]; then
            continue
        else
            break
        fi
    done
    echo $port
}

on_etcd_exit()
{
    (echo "$1"; cat $test_path/cleanup) > $test_path/cleanup.tmp
    mv $test_path/cleanup.tmp $test_path/cleanup
}

dump_etcd_kv()
{
    local prefix=${tuplenet_prefix}
    pmsg "dump etcd $prefix key value"
    etcdctl --endpoints $etcd_client_specs get --prefix $prefix > ${etcd_base}/dump.txt
}

entity_id=1
increase_entity_id()
{
    entity_id=$((entity_id+1))
}

reset_entity_id()
{
    entity_id=1
}

print_etcd_member_list()
{
    list=`etcdctl --endpoints "$etcd_client_specs" member list`
    pmsg "etcd member list:$list"
}

etcdcompact()
{
    key=`etcdctl --endpoints $etcd_client_specs get --prefix ""|head -n1`
    revision=`etcdctl --endpoints $etcd_client_specs get $key -w json|awk -F',' '{print $3}'|awk -F':' '{print $2}'`
    pmsg "compact etcd revision to $revision"
    etcdctl --endpoints $etcd_client_specs compact $revision
}

etcdput()
{
    local prefix=${tuplenet_prefix}entity_view/
    pmsg "etcdput key:${prefix}${1}  value:$2"
    etcdctl --endpoints "$etcd_client_specs" put ${prefix}$1 $2 || return 1
}

etcddel()
{
    local prefix=${tuplenet_prefix}entity_view/
    pmsg "etcddel key:${prefix}${1}"
    etcdctl --endpoints $etcd_client_specs del ${prefix}$1 || return 1
}

etcd_chassis_add()
{
    hv=$1
    ip=$2
    tick=$3
    etcdput chassis/$hv ip=$ip,tick=$tick
}

etcd_chassis_del()
{
    hv=$1
    etcddel chassis/$hv
}

etcd_ls_add()
{
    ls_name=$1
    etcdput LS/$ls_name id=$entity_id || return 1
    increase_entity_id
}

etcd_ls_del()
{
    ls_name=$1
    etcddel LS/$ls_name || return 1
}

etcd_lr_add()
{
    lr_name=$1
    if [ $# == 1 ]; then
        etcdput LR/$lr_name id=$entity_id
    elif [ $# == 2 ]; then
        chassis=$2
        etcdput LR/$lr_name id=$entity_id,chassis=$chassis
    else
        return 1
    fi
    increase_entity_id
}

etcd_lr_del()
{
    lr_name=$1
    etcddel LR/$lr_name || return 1
}

etcd_lsr_add()
{
    lr_name=$1
    ip=$2
    prefix=$3
    next_hop=$4
    outport=$5
    lsr_name=${ip}_${prefix}_to_${outport}
    etcdput LR/$lr_name/lsr/$lsr_name ip=$ip,prefix=$prefix,next_hop=$next_hop,outport=$outport || return 1
}

etcd_lsr_del()
{
    lr_name=$1
    ip=$2
    prefix=$3
    outport=$4
    lsr_name=${ip}_${prefix}_to_${outport}
    etcddel LR/$lr_name/lsr/$lsr_name || return 1
}

etcd_lnat_add()
{
    lr_name=$1
    ip=$2
    prefix=$3
    xlate_ip=$4
    xlate_type=$5
    lnat_name=${ip}_${prefix}_${xlate_type}_to_${xlate_ip}
    etcdput LR/$lr_name/lnat/$lnat_name ip=$ip,prefix=$prefix,xlate_ip=$xlate_ip,xlate_type=$xlate_type || return 1
}

etcd_lnat_del()
{
    lr_name=$1
    ip=$2
    prefix=$3
    xlate_ip=$4
    xlate_type=$5
    lnat_name=${ip}_${prefix}_${xlate_type}_to_${xlate_ip}
    etcddel LR/$lr_name/lnat/$lnat_name || return 1
}

etcd_lsp_add()
{
    ls_name=$1
    lsp_name=$2
    ip=$3;mac=$4
    if [ $# == 5 ]; then
        chassis=$5
        etcdput LS/$ls_name/lsp/$lsp_name ip=$ip,mac=$mac,chassis=$chassis || return 1
    else
        etcdput LS/$ls_name/lsp/$lsp_name ip=$ip,mac=$mac || return 1
    fi
}

etcd_lsp_del()
{
    ls_name=$1
    lsp_name=$2
    etcddel LS/$ls_name/lsp/$lsp_name || return 1
}

etcd_patchport_add()
{
    ls_name=$1
    lsp_name=$2
    etcdput LS/$ls_name/lsp/$lsp_name ip=255.255.255.255,mac=ff:ff:ff:ff:ff:ee || return 1
}

etcd_ls_link_lr()
{
    ls_name=$1
    lr_name=$2
    ip=$3
    prefix=$4
    mac=$5
    lsp_name="${ls_name}_to_${lr_name}"
    lrp_name="${lr_name}_to_${ls_name}"
    etcdput LS/$ls_name/lsp/$lsp_name ip=$ip,mac=$mac,peer=$lrp_name || return 1
    etcdput LR/$lr_name/lrp/$lrp_name \
      ip=$ip,mac=$mac,prefix=$prefix,peer=$lsp_name || return 1
}

etcd_ls_unlink_lr()
{
    ls_name=$1
    lr_name=$2
    lsp_name="${ls_name}_to_${lr_name}"
    lrp_name="${lr_name}_to_${ls_name}"
    etcddel LS/$ls_name/lsp/$lsp_name || return 1
    etcddel LR/$lr_name/lrp/$lrp_name || return 1
}

etcd_inject_packet()
{
    hv=$1
    port=$2
    data=$3
    local prefix=${tuplenet_prefix}communicate/
    etcdctl --endpoints $etcd_client_specs put ${prefix}${hv}/cmd/1 cmd=pkt_trace,port=$port,packet=$data || return 1
}

etcd_ipbook()
{
    local action=$1
    local type=$2
    local key=${tuplenet_prefix}ip_book/LS/$3
    local val=$4

    case ${type} in
    LS|LR)
    ;;
    *)
        pmsg "invalid type ${type}"; return 1
    ;;
    esac

    case ${action} in
    get|del)
        etcdctl --endpoints "$etcd_client_specs" ${action} ${key} || return 1
    ;;
    put)
        etcdctl --endpoints "$etcd_client_specs" ${action} ${key} "${val}" || return 1
    ;;
    *)
        pmsg "invalid action: ${action}"; return 1
    ;;
    esac
}
