import os
import sys
import commit_ovs as cm
import pkt_trace
import logging
import logicalview as lgview
import lflow
import ecmp
import action as ovsaction
import match as ovsmatch
import link_master as lm
import time
from pyDatalog import pyDatalog
from run_env import disable_init_trigger, is_gateway_chassis
import tunnel

logger = logging.getLogger(__name__)
prev_zoo_ver = 0 # it should be 0 which same as entity_zoo's zoo_ver
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
                logger.info("inject packet to ovsport %s, packet_data:%s",
                            ovsport.ovsport_name, packet_data)
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

def rebuild_chassis_tunnel():
    tunnel.tunnel_port_oper(IP, UUID_CHASSIS, State)
    ips = IP.data
    uuids = UUID_CHASSIS.data
    states = State.data

    port_configs = zip(ips, uuids, states)
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
    if data_type == True and extra['accept_diff'] == True:
        logger.warning("received data is not incremental data, link_master may "
                       "hit compact event")
        entity_zoo.move_all_entity2sink([lgview.LOGICAL_ENTITY_TYPE_OVSPORT,
                                         lgview.LOGICAL_ENTITY_TYPE_OVSPORT_CHASSIS])

    extra['accept_diff'] = True
    update_entity(entity_zoo, add_pool, del_pool)
    if add_pool is not None and add_pool.has_key('cmd'):
        execute_pushed_cmd(add_pool['cmd'], entity_zoo)

def config_tunnel_bfd():
    if is_gateway_chassis():
        # no need to config bfd on a gateway tunnel port. It was configed
        # enable-bfd after creating
        return

    ecmp.ecmp_bfd_port(PORT_NAME, State)
    port_names = PORT_NAME.data
    states = State.data
    port_configs = zip(port_names, states)
    #TODO need to consider in different centre-LR has different route, some
    # of them may deliver packet to gateway, but some did not. For same port
    # we may enable bfd by this route, but maybe disable in other routes.
    for name, state in port_configs:
        if state > 0:
            state = 'enable=true'
        elif state < 0:
            state = 'enable=false'
        else:
            continue
        logger.info("config %s bfd to %s", name, state)
        cm.config_ovsport_bfd(name, state)

def update_ovs_side(entity_zoo):
    # we must lock the whole process of generating flow and sweepping zoo
    # otherwise we may mark some new entities to State_NO, without generating
    # any ovs flows
    with entity_zoo.lock:
        start_time = time.time()
        lflow.build_flows(Table, Priority, Match, Action, State)
        lflows = zip(Table.data, Priority.data, Match.data,
                     Action.data, State.data)
        cost_time = time.time() - start_time
        config_tunnel_bfd()
        rebuild_chassis_tunnel()
        entity_zoo.sweep_zoo()

    ovs_flows_add, ovs_flows_del = convert_tuple2flow(lflows)
    # on testing mode, it avoids similar flow replacing the others
    if os.environ.has_key('RUNTEST'):
        ovs_flows_add.sort()
    logger.info('insert flow number:%d, del flow number:%d',
                len(ovs_flows_add), len(ovs_flows_del))
    logger.info("pydatalog cost %fs in generating flows", cost_time)
    cm.commit_flows(ovs_flows_add, ovs_flows_del)

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
        logger.info("entity set has no change, wait...")
        return

    update_ovs_side(entity_zoo)
    # set init_trigger==0, then tuplenet would not generate
    # traceflow/init flows again and again
    disable_init_trigger()
    # call this function again immediately because tuplenet update the lsp
    # so we should read the change of etcd as soon as possible
    if cnt_upload > 0:
        update_logical_view(entity_zoo, extra)
