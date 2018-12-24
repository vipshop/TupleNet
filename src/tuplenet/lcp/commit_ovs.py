import sys, os
import json
import subprocess
import logging
import threading
import struct, socket
import time, random, string
import logicalview as lgview
from pyDatalog import pyDatalog
from onexit import on_parent_exit
from run_env import is_gateway_chassis

logger = logging.getLogger(__name__)
flow_lock = threading.Lock()
TP_TUNNEL_PORT_NAME_PREFIX = "tupleNet-"

class OVSToolErr(Exception):
    pass

def call_popen(cmd, commu=None, shell=False):
    child = subprocess.Popen(cmd, shell, stdout=subprocess.PIPE,
                             stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    if commu is None:
        output = child.communicate()
    else:
        output = child.communicate(commu)
    if child.returncode:
        raise RuntimeError("error executing %s" % (' '.join(cmd)))
    if len(output) == 0 or output[0] is None:
        output = ""
    else:
        output = output[0].decode("utf8").strip()
    return output

def call_ovsprog(prog, args_list, commu=None):
    cmd = [prog, "--timeout=5"] + args_list
    retry_n = 0
    while True:
        try:
            return call_popen(cmd, commu)
        except Exception as err:
            retry_n += 1
            if retry_n == 3:
                raise err
            continue

def ovs_ofctl(*args):
    return call_ovsprog("ovs-ofctl", list(args))

def aggregate_flows(flows):
    length = 500
    flow_seg = [flows[x : x + length] for x in range(0, len(flows), length)]
    for seg in flow_seg:
        yield '\n'.join(seg)

def ovs_ofctl_delflows_batch(br, flows):
    for flow_combind in aggregate_flows(flows):
        call_ovsprog("ovs-ofctl", ['del-flows', br, '--strict', '-'],
                     commu=flow_combind)


def ovs_ofctl_addflows_batch(br, flows):
    for flow_combind in aggregate_flows(flows):
        call_ovsprog("ovs-ofctl", ['add-flow', br, '-'], commu=flow_combind)

def ovs_vsctl(*args):
    return call_ovsprog("ovs-vsctl", list(args))

def parse_map(map_list):
    ret_map = {}
    if map_list[0] != 'map':
        return None
    for entry in map_list[1]:
        ret_map[entry[0]] = entry[1]
    return ret_map

def update_ovsport(record, entity_zoo):
    action_type = record[1]
    if action_type in ['new', 'initial', 'delete', 'old', 'insert']:
        # some operations may not contain some essential fields
        if not isinstance(record[2], int) or \
           record[3] == None or record[4] == None:
            logger.debug('action %s does not container enough info, msg:%s',
                         action_type, record)
            return
    else:
        logger.warning("unknow action_type:%s", action_type)
        return

    logger.info("ovsport action type:%s", action_type)

    ofport = record[2]
    name = record[3]
    external_ids = record[4]
    external_ids = parse_map(external_ids)
    if external_ids.has_key('iface-id'):
        uuid = external_ids['iface-id']
        is_remote = False
        entity_type = lgview.LOGICAL_ENTITY_TYPE_OVSPORT
    elif external_ids.has_key('chassis-id'):
        uuid = external_ids['chassis-id']
        is_remote = True
        entity_type = lgview.LOGICAL_ENTITY_TYPE_OVSPORT_CHASSIS
    else:
        logger.info('external_ids has no chassis-id or iface-id, record:%s',
                    record)
        return

    if action_type in ['old', 'delete']:
        logger.info("try to move port to sink %s uuid:%s", name, uuid)
        entity_zoo.move_entity2sink(entity_type, name)
    else:
        logger.info("try to add ovsport entity %s ofport:%d, uuid:%s in zoo",
                    name, ofport, uuid)
        entity_zoo.add_entity(entity_type, name, uuid, ofport, is_remote)
    return


def monitor_ovsdb(entity_zoo, extra):
    pyDatalog.Logic(extra['logic'])
    cmd = ['ovsdb-client', 'monitor', 'Interface',
           'ofport', 'name', 'external_ids', '--format=json']

    logger.info("start ovsdb-client instance")
    try:
        child = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 preexec_fn=on_parent_exit('SIGTERM'))
        with extra['lock']:
            extra['ovsdb-client'] = child
        logger.info("monitoring the ovsdb")
        while child.poll() == None:
            json_str = child.stdout.readline().strip()
            output = json.loads(json_str)
            with entity_zoo.lock:
                for record in output['data']:
                    update_ovsport(record, entity_zoo)
    except ValueError as err:
        if json_str != "":
            logger.warning("cannot parse %s to json object", json_str)
        else:
            logger.info('json_str is empty, maybe we should exit')
        subprocess.Popen.kill(child)
        return
    except Exception as err:
        logger.exception("exit ovsdb-client monitor, err:%s", str(err))
        subprocess.Popen.kill(child)
        return

def start_monitor_ovsdb(entity_zoo, extra):
    t = threading.Thread(target = monitor_ovsdb,
                         args=(entity_zoo, extra))
    t.setDaemon(True)
    t.start()
    return t

def clean_ovs_flows(br = 'br-int'):
    try:
        ovs_ofctl("del-flows", br)
    except Exception as err:
        logger.error("failed to clean bridge %s flows", br)
        raise OVSToolErr("failed to clean ovs flows")
    else:
        logger.info("clean all flows in %s", br)

def system_id():
    cmd = ['ovsdb-client', '-v', 'transact',
           '["Open_vSwitch",{"op":"select", \
             "table":"Open_vSwitch","columns":["external_ids"], \
             "where":[]}]']
    try:
        json_str = call_popen(cmd, shell=True)
    except Exception:
        logger.error('failed to get system-id')
        return
    output = json.loads(json_str)[0]
    external_ids = parse_map(output['rows'][0]['external_ids'])
    if external_ids.has_key('system-id'):
        return external_ids['system-id']

def remove_tunnel_by_name(portname):
    try:
        ovs_vsctl('get', 'interface', portname, 'name')
    except Exception as err:
        # cannot found this port, return immedately
        logger.debug("port %s is not exist, no need to remove it", portname)
        return
    try:
        ovs_vsctl('del-port', 'br-int', portname)
    except Exception as err:
        logger.info("cannot delete tunnel port:%s", err)
    return

def get_tunnel_chassis_id(portname):
    try:
        return ovs_vsctl('get', 'interface', portname,
                         'external_ids:chassis-id').strip("\"")
    except Exception as err:
        return ""

def chassis_ip_to_portname(ip):
    chassis_ip_int = struct.unpack("!L", socket.inet_aton(ip))[0]
    portname = '{}{}'.format(TP_TUNNEL_PORT_NAME_PREFIX, chassis_ip_int)
    return portname

def remove_tunnel_by_ip(ip):
    portname = chassis_ip_to_portname(ip)
    remove_tunnel_by_name(portname)

def create_tunnel(ip, uuid):
    portname = chassis_ip_to_portname(ip)
    if get_tunnel_chassis_id(portname) == uuid:
        logger.info("found a exist tunnel ovsport has "
                    "same chassis-id and portname, skip adding tunnel ovsport")
        return portname
    remove_tunnel_by_name(portname)
    cmd = ['add-port', 'br-int', portname, '--', 'set', 'interface',
           portname, 'type=geneve', 'options:remote_ip={}'.format(ip),
           'options:key=flow', 'options:csum=true',
           'external_ids:chassis-id={}'.format(uuid)]
    try:
        ovs_vsctl(*cmd)
    except Exception as err:
        logger.error('cannot create tunnle, cmd:%s, err:%s', cmd, err)
        return portname

    # if this host is a gateway, then we should enable bfd for each tunnle port
    if is_gateway_chassis():
        logger.info("local host is gateway, enable bfd on %s", portname)
        config_ovsport_bfd(portname, 'enable=true')
    return portname

def create_flowbased_tunnel(chassis_id):
    portname = "{}flowbased".format(TP_TUNNEL_PORT_NAME_PREFIX)
    remove_tunnel_by_name(portname)
    cmd = ['add-port', 'br-int', portname, '--', 'set', 'interface',
           portname, 'type=geneve', 'options:remote_ip=flow',
           'options:key=flow', 'options:csum=true',
           'external_ids:chassis-id={}'.format(chassis_id)]
    try:
        ovs_vsctl(*cmd)
    except Exception as err:
        logger.error('cannot create flow-based tunnle, cmd:%s, err:%s',
                     cmd, err)
    return portname


def create_patch_port(uuid, peer_bridge):
    portname = 'patch-' + 'br-int' + peer_bridge + str(uuid)[0:8]
    peername = 'patch-' + peer_bridge + 'br-int' + str(uuid)[0:8]

    cmd = ['add-port', 'br-int', portname, '--', 'set', 'interface',
           portname, 'type=patch',
           'external_ids:iface-id={}'.format(uuid),
           'options:peer={}'.format(peername)]
    ovs_vsctl(*cmd)
    cmd = ['add-port', peer_bridge, peername, '--', 'set', 'interface',
           peername, 'type=patch',
           'options:peer={}'.format(portname)]
    ovs_vsctl(*cmd)


def commit_replaceflows(replace_flows, br = 'br-int'):
    # commit_replaceflows is only consumed by update_logical_view in booting
    # tuplenet stage. Keep all flows in a file to avoid using stdin which may
    # introduce buffer size issue.
    # this function can help to avoid ports' issue of breaking-network, the
    # replace-flows is a transaction, so would not change flows if it hit issue
    filepath = '/tmp/ovs-flow-{}'.format(''.join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(5)))
    filepath += str(time.time())
    try:
        with open(filepath, 'w') as fp:
            fp.write('\n'.join(replace_flows))
        # In  OpenFlow  1.0  and  1.1,  re-adding a flow always resets the
        # flow's packet and byte counters to 0.
        ovs_ofctl('replace-flows', '-O' , 'OpenFlow14', br, filepath)
        os.remove(filepath)
    except IOError as err:
        logger.error("failed to write flows into file %s", filepath)
        raise
    except RuntimeError as err:
        logger.error("failed to replace flows in {}".format(filepath))
        raise OVSToolErr("failed to replace flows")
    except OSError as err:
        logger.warning("failed to remove the %s", filepath)
        raise



def commit_flows(add_flows, del_flows):
    # consume batch method to insert/delete flows first.
    # update ovs flow one by one if updateing flow hit issue.

    with flow_lock:
        try:
            total_flow_n = len(del_flows) + len(add_flows)
            if len(del_flows) > 0:
                ovs_ofctl_delflows_batch('br-int', del_flows)
                del_flows = []
            if len(add_flows) > 0:
                ovs_ofctl_addflows_batch('br-int', add_flows)
                add_flows = []
            return total_flow_n
        except Exception as err:
            logger.warn("failed to batch modify flows, "
                        "will try to update one by one, err:%s", err)

        # insert/delete flow one by one once the batch processing hit error
        cm_cnt = 0
        for flow in del_flows:
            try:
                ovs_ofctl('del-flows', 'br-int', flow, '--strict')
            except Exception as err:
                logger.error('failed to delete flow(%s) at ovs, err:%s',
                             flow, err)
                continue;
            cm_cnt += 1

        for flow in add_flows:
            try:
                ovs_ofctl('add-flow', 'br-int', flow)
            except Exception as err:
                logger.error('failed to add flow(%s) at ovs, err:%s',
                             flow, err)
                continue;
            cm_cnt += 1
    return cm_cnt;

def build_br_integration(br = 'br-int'):
    try:
        ovs_vsctl('br-exists', br)
        logger.info("the bridge %s is exist", br)
        # if we hit no issue, then it means the bridge is exist
        return
    except Exception as err:
        logger.info("the bridge %s is not exist, try to create a new one", br)
    try:
        ovs_vsctl('add-br', br)
        logger.info("create bridge %s for integration", br)
    except Exception as err:
        logger.error("failed to create %s", br)
        raise OVSToolErr("failed to create integration bridge")

    clean_ovs_flows()

def set_tunnel_tlv(vipclass = 0xffee, br = 'br-int'):
    while True:
        try:
            output = ovs_ofctl('dump-tlv-map', br)
        except Exception as err:
            logger.error("failed dump %s tlv, err:%s", br, err)
            raise OVSToolErr("failed to dump tlv")
        # TODO it is a fool check, update it
        if "tun_metadata0" in output:
            logger.info(output)
            return

        try:
            ovs_ofctl('del-tlv-map', br)
        except Exception as err:
            logger.error("failed to clean %s tlv, err:%s", br, err)
            raise OVSToolErr("failed to clean tlv")

        tlv = "{{class={},type=0,len=8}}->tun_metadata0".format(vipclass)
        try:
            ovs_ofctl('add-tlv-map', br, tlv)
        except Exception as err:
            logger.error('failed to config tlv %s to %s, err:%s', tlv, br, err)
            raise OVSToolErr("failed to config tlv")

        logger.info("set tlv %s on %s", tlv, br)

def set_upcall_rate(br = 'br-int', rate = 100):
    #TODO we need to limite the packet rate of upcalling to packet_controller
    pass


def config_ovsport_bfd(portname, config):
    try:
        ovs_vsctl('set', 'Interface', portname, 'bfd:{}'.format(config))
    except Exception as err:
        logger.info("failed to config %s bfd to %s, "
                    "port may not exist, err:%s",
                    portname, config, err)

def inject_pkt_to_ovsport(cmd_id, packet_data, ofport):
    try:
        ovs_ofctl('packet-out', 'br-int', 'NONE',
                  'load:{}->NXM_OF_IN_PORT[],'
                  'load:{}->NXM_NX_REG10[16..31],'
                  'load:1->NXM_NX_REG10[1],resubmit(,0)'.format(ofport, cmd_id),
                  packet_data)
    except Exception as err:
        logger.warning("failed to inject packet %s to ofport %d",
                       packet_data, ofport)

