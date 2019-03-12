import os
import commit_ovs as cm
import flow_common as fc
import logging
import logicalview as lgview
import lflow
import ecmp
import action as ovsaction
import match as ovsmatch
import time
from pyDatalog import pyDatalog
from tp_utils.run_env import is_gateway_chassis, get_extra
import tunnel

logger = logging.getLogger(__name__)
prev_zoo_ver = 0 # it should be 0 which same as entity_zoo's zoo_ver
had_clean_tunnel_ports = False
had_clean_ovs_flows = False
# NOTE: DO NOT revise the filename
MAC_IP_BIND_FILE = os.path.join(get_extra()['options']['TUPLENET_RUNDIR'],
                                'mac_ip_bind.data')
pyDatalog.create_terms('Table, Priority, Match, Action, State')
pyDatalog.create_terms('PORT_NAME, IP, UUID_CHASSIS')

def update_lsp_chassis(entity_set, system_id):
    lsp_chassis_changed = []
    lsp_portset = entity_set['lsp']
    ovsport_set = entity_set['ovsport']
    for _, ovsport in ovsport_set.items():
        key = ovsport.iface_id
        if lsp_portset.has_key(key) and \
           lsp_portset[key].chassis != system_id:
               lsp_chassis_changed.append(lsp_portset[key])
               logger.info('should update lsp %s chassis %s', key, system_id)
    return lsp_chassis_changed

def generate_lsp_kv(lsp_array, system_id):
    upload_data = []
    for lsp in lsp_array:
        key = 'LS/{}/lsp/{}'.format(lsp.ls_uuid, lsp.uuid)
        value = 'ip={},mac={},chassis={}'.format(lsp.ip,lsp.mac,
                                                 system_id)
        if lsp.peer != None:
            value += ',peer={}'.format(lsp.peer)
        upload_data.append((key, value))
    return upload_data

def revise_lsp_chassis(entity_zoo, system_id):
    with entity_zoo.zoo_gate as (entity_set, _):
        lsp_chassis_changed = update_lsp_chassis(entity_set,
                                                 system_id)
        return generate_lsp_kv(lsp_chassis_changed, system_id)

def _gen_arp_ip_flow(mac_addr, ip_int):
    match = 'table={t},priority=1,ip,reg2={dst},'.format(
                    t = fc.TABLE_SEARCH_IP_MAC, dst = ip_int)
    action = 'actions=mod_dl_dst:{}'.format(mac_addr)
    flow = match + action
    return flow

def update_ovs_arp_ip_mac(mac_addr, ip_int):
    flow = _gen_arp_ip_flow(mac_addr, ip_int)
    cm.commit_flows([flow], [])
    with open(MAC_IP_BIND_FILE, 'a') as fd:
        fd.write("{},{}\n".format(mac_addr, ip_int))

def _get_ovs_arp_ip_mac_from_file():
    flows = []
    if not os.path.isfile(MAC_IP_BIND_FILE):
        return flows

    logger.info("update arp mac_ip bind map from file %s", MAC_IP_BIND_FILE)
    try:
        with open(MAC_IP_BIND_FILE, 'r+') as fd:
            for line in fd:
                mac_addr,ip_int = line.split(',')
                ip_int = int(ip_int)
                flow = _gen_arp_ip_flow(mac_addr, ip_int)
                flows.append(flow)
            # erase the file contents, otherwise the size of file may increase
            # too big to reload
            fd.truncate(0)
    except:
        logger.exception("failed to read <mac,ip> pairs")
    return flows

def convert_tuple2flow(lflows):
    ovs_flows_add = []
    ovs_flows_del = []
    for table, priority, match, action, state in lflows:
        table = int(table) #TODO no idea why 1 become to True
        if state > 0:
            flow = "table={tab},priority={pri},{match},actions={action}".format(
                        tab = table, pri = priority,
                        match = ovsmatch.convert_tuple2match(match),
                        action = ovsaction.convert_tuple2action(action, table))
            logger.debug('insert flow:%s', flow)
            ovs_flows_add.append(flow)
        elif state < 0:
            flow = "table={tab},priority={pri},{match}".format(
                        tab = table, pri = priority,
                        match = ovsmatch.convert_tuple2match(match))
            if abs(state) % lgview.State_DEL != 0:
                logger.debug('no need to delete this flow:%s', flow)
                continue
            logger.debug('delete flow:%s', flow)
            ovs_flows_del.append(flow)
        elif state == 0:
            logger.error('state == 0, please revise the flow, %s,%s,%s,%s',
                         table, priority, match, action)
            continue
    return ovs_flows_add, ovs_flows_del

def execute_pushed_cmd_inject_pkt(cmd_id, packet_data, lsp, entity_zoo):
    with entity_zoo.zoo_gate as (entity_set, _):
        ovsport_set = entity_set['ovsport']
        for _, ovsport in ovsport_set.items():
            if ovsport.iface_id == lsp:
                logger.info("inject packet to ovsport %s, packet_data:%s, "
                            "cmd_id:%s",
                            ovsport.ovsport_name, packet_data, cmd_id)
                cm.inject_pkt_to_ovsport(cmd_id, packet_data,
                                         ovsport.ofport)


def execute_pushed_cmd(cmd_set, entity_zoo):
    for path, value_set in cmd_set.items():
        try:
            if value_set.get('cmd') == 'pkt_trace':
                cmd_id = int(path.split('/')[-1])
                execute_pushed_cmd_inject_pkt(cmd_id,
                                              value_set['packet'],
                                              value_set['port'],
                                              entity_zoo)
            else:
                logger.warning("unknow command:%s", value_set['cmd'])
        except Exception as err:
            logger.warning("hit error in trying execute cmd, path:%s,value:%s,err:%s",
                           path, value_set, err)
            continue

def rebuild_chassis_tunnel(port_configs):
    global had_clean_tunnel_ports
    # no need to care about same IP but different operation, only the top tick
    # chassis IP was grep out
    for ip, uuid, state in port_configs:
        if state >= 0:
            if ip == '':
                cm.create_flowbased_tunnel(uuid)
            else:
                cm.create_tunnel(ip, uuid)
        else:
            cm.remove_tunnel_by_ip(ip)
    if not had_clean_tunnel_ports:
        logger.info("clean unused tunnel ports")
        # clean tunnel ports which we don't need
        had_clean_tunnel_ports = True
        tunnel.tunnel_port_delete_exist(PORT_NAME)
        for portname in PORT_NAME.data:
            cm.remove_tunnel_by_name(portname)

# NOTE: this function may update prev_zoo_ver
def need_recompute(entity_zoo):
    global prev_zoo_ver
    with entity_zoo.lock:
        if entity_zoo.zoo_ver == prev_zoo_ver:
            recompute = False
        else:
            recompute = True
        prev_zoo_ver = entity_zoo.zoo_ver
        return recompute

def update_entity(entity_zoo, add_pool, del_pool):
    if del_pool is not None:
        for entity_type,_ in lgview.LogicalEntityZoo.logical_entity_types.items():
            if not del_pool.has_key(entity_type):
                continue
            entity_zoo.move_entity2sink_by_pool(entity_type, del_pool[entity_type])

    if add_pool is not None:
        for entity_type,_ in lgview.LogicalEntityZoo.logical_entity_types.items():
            if not add_pool.has_key(entity_type):
                continue
            entity_zoo.convert_pool2entity(entity_type, add_pool[entity_type])


def update_entity_from_remote(entity_zoo, extra):
    wmaster = extra['lm']
    data_type, add_pool, del_pool = wmaster.read_remote_kvdata()
    if data_type == True and update_entity_from_remote.accept_diff == True:
        logger.warning("received data is not incremental data, link_master may "
                       "hit compact event")
        entity_zoo.move_all_entity2sink([lgview.LOGICAL_ENTITY_TYPE_OVSPORT,
                                         lgview.LOGICAL_ENTITY_TYPE_OVSPORT_CHASSIS])

    update_entity_from_remote.accept_diff = True
    update_entity(entity_zoo, add_pool, del_pool)
    if add_pool is not None and add_pool.has_key('cmd'):
        execute_pushed_cmd(add_pool['cmd'], entity_zoo)
update_entity_from_remote.accept_diff = False

def config_tunnel_bfd(port_configs):
    # NOTE: remote chassis reboot will update the tick and ecmp_bfd_port
    # generate two records like:
    #    port tupleNet-3232261123 --> bfd_to_true
    #    port tupleNet-3232261123 --> bfd_to_false
    # tuplenet should handle it by elimiate bfd_to_false if found bfd_to_true
    # in same port. There is no circumstance that that keep bfd_to_false and
    # delete bfd_to_true. Our etcd linkmaster can merge add-->delete operation, so
    # add-->delete is a empty operation
    _tun_bfd_dict = {}
    for portname, state in port_configs:
        if not _tun_bfd_dict.has_key(portname):
            _tun_bfd_dict[portname] = int(state)
        else:
            _tun_bfd_dict[portname] = max(int(state), _tun_bfd_dict[portname])
    #TODO need to consider in different centre-LR has different route, some
    # of them may deliver packet to gateway, but some did not. For same port
    # we may enable bfd by this route, but maybe disable in other routes.
    for portname, state in _tun_bfd_dict.items():
        if state > 0:
            state = 'enable=true'
        elif state < 0:
            state = 'enable=false'
        else:
            continue
        logger.info("config %s bfd to %s", portname, state)
        cm.config_ovsport_bfd(portname, state)

def update_ovs_side(entity_zoo):
    global had_clean_ovs_flows
    bfd_port_configs = []
    tunnel_port_configs = []
    # we must lock the whole process of generating flow and sweepping zoo
    # otherwise we may mark some new entities to State_NO, without generating
    # any ovs flows
    with entity_zoo.lock:
        start_time = time.time()
        lflow.build_flows(Table, Priority, Match, Action, State)
        lflows = zip(Table.data, Priority.data, Match.data,
                     Action.data, State.data)
        # must insert const flows in init stage
        if not had_clean_ovs_flows:
            lflow.build_const_flows(Table, Priority, Match, Action)
            static_lflows = zip(Table.data, Priority.data, Match.data,
                                Action.data, [1]*len(Table.data))
            lflows += static_lflows
        tunnel.tunnel_port_oper(IP, UUID_CHASSIS, State)
        tunnel_port_configs = zip(IP.data, UUID_CHASSIS.data, State.data)
        ecmp.ecmp_bfd_port(PORT_NAME, State)
        bfd_port_configs = zip(PORT_NAME.data, State.data)

        cost_time = time.time() - start_time
        entity_zoo.sweep_zoo()

    ovs_flows_add, ovs_flows_del = convert_tuple2flow(lflows)
    # on testing mode, it avoids similar flow replacing the others
    if os.environ.has_key('RUNTEST'):
        ovs_flows_add.sort()
    logger.info("pydatalog cost %fs in computing flows and config", cost_time)
    if not had_clean_ovs_flows:
        had_clean_ovs_flows = True
        ovs_flows_add += _get_ovs_arp_ip_mac_from_file()
        cm.commit_replaceflows(ovs_flows_add)
    else:
        cm.commit_flows(ovs_flows_add, ovs_flows_del)
    logger.info('insert flow number:%d, del flow number:%d',
                len(ovs_flows_add), len(ovs_flows_del))

    rebuild_chassis_tunnel(tunnel_port_configs)
    config_tunnel_bfd(bfd_port_configs)

def update_logical_view(entity_zoo, extra):
    cnt_upload = 0
    wmaster = extra['lm']
    update_entity_from_remote(entity_zoo, extra)
    upload_data = revise_lsp_chassis(entity_zoo, extra['system_id'])
    if len(upload_data) > 0:
        cnt_upload = wmaster.put_entity_view_batch(upload_data)

    # insert operation will change entity number, del/update operation
    # will change del entity group number
    if not need_recompute(entity_zoo):
        if update_logical_view.cnt % 30 == 0:
            logger.info("entity set has no change, wait...")
        update_logical_view.cnt += 1
        return

    update_ovs_side(entity_zoo)
    # update chassis information to remote if tuplenet had been install ovsflow
    if update_logical_view.updated_chassis is False:
        ret = wmaster.update_chassis(extra['consume_ip'])
        if ret == 1:
            update_logical_view.updated_chassis = True
        else:
            logger.warning("failed to update chassis information to remote etcd")
        cnt_upload += ret

    # call this function again immediately because tuplenet update the lsp
    # so we should read the change of etcd as soon as possible
    if cnt_upload > 0:
        update_logical_view(entity_zoo, extra)

update_logical_view.cnt = 0
update_logical_view.updated_chassis = False
