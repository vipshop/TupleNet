import logging
from pyDatalog import pyDatalog
import socket, struct
import threading
from tp_utils.run_env import get_extra

logger = logging.getLogger(__name__)

LOGICAL_ENTITY_ID = '_id_'
LOGICAL_ENTITY_PARENT_ID = '_parent_'
LOGICAL_ENTITY_TYPE_LSP = 'lsp'
LOGICAL_ENTITY_TYPE_LRP = 'lrp'
LOGICAL_ENTITY_TYPE_LSR = 'lsr'
LOGICAL_ENTITY_TYPE_LNAT = 'lnat'
LOGICAL_ENTITY_TYPE_CHASSIS = 'chassis'
LOGICAL_ENTITY_TYPE_LS = 'LS'
LOGICAL_ENTITY_TYPE_LR = 'LR'
LOGICAL_ENTITY_TYPE_OVSPORT = 'ovsport'
LOGICAL_ENTITY_TYPE_OVSPORT_CHASSIS = 'ovsport_chassis'

State_NO = 0
State_ADD = 1
State_DEL = -100

def _gen_mac_by_ip(ip_int):
    # NOTE f2:01 is the prefix of mac address, please do NOT change it
    # the f2 means this mac address is locally administered addresses
    mac = "f2:01:{:02x}:{:02x}:{:02x}:{:02x}".format(
                    ip_int>>24 & 0xff,
                    ip_int>>16 & 0xff,
                    ip_int>>8 & 0xff,
                    ip_int & 0xff)
    return mac

class LogicalEntity(object):

    def __init__(self):
        self.state = State_ADD
        self.populated = False

    def populate(self):
        if self.populated is False:
            self._update_dup_data()
            self.add_clause()
            self.populated = True

    def _update(self, event):
        self.del_clause()
        self._update_dup_data()
        self.add_clause()

    def eliminate(self):
        self.del_clause()
        eliminate_me = getattr(self, '_eliminate', None)
        if eliminate_me is not None:
            eliminate_me()

    def mark(self, event):
        self.state = event
        self._update(event)

class ILKEntity(object):
    # user may config several lrp which has same ip and prefix but different
    # output. A deletion of lsr may delete other ilk lrp ovs-flow. We consume
    # priority to distinguish it to avoid overlap deletion.
    # Max value of priority is 65535, and max prefix is 32. So we set 64 to
    # max_ilk_n. 64 ilk lrp are enough for tuplenet network
    _max_ilk_n = 64
    _ilk_group = {}
    _whole_idx_set = set(i for i in range(_max_ilk_n))

    def __init__(self):
        self.ilk_idx = self._get_ilk_idx()

    def _get_free_idx(self, occupy_idx_set):
        free_idx_set = ILKEntity._whole_idx_set - occupy_idx_set
        if len(free_idx_set) == 0:
            return -1
        return free_idx_set.pop()

    def _free_ilk_idx(self):
        etype = self.entity_type
        ip_prefix_int = (self.ip_int >> (32 - self.prefix)) << (32 - self.prefix)
        key = "{}{}{}".format(self.lr_uuid, ip_prefix_int, self.prefix)
        ILKEntity._ilk_group[etype][key].remove(self.ilk_idx)
        return self.ilk_idx

    def _get_ilk_idx(self):
        idx = 0
        etype = self.entity_type
        ip_prefix_int = (self.ip_int >> (32 - self.prefix)) << (32 - self.prefix)
        key = "{}{}{}".format(self.lr_uuid, ip_prefix_int, self.prefix)
        if not ILKEntity._ilk_group.has_key(etype):
            ILKEntity._ilk_group[etype] = {}
        if ILKEntity._ilk_group[etype].has_key(key):
            idx = self._get_free_idx(ILKEntity._ilk_group[etype][key])
            if idx < 0:
                raise Exception("too many ilk, entity:%s" % self.uuid)
            ILKEntity._ilk_group[etype][key].add(idx)
        else:
            ILKEntity._ilk_group[etype][key] = set([idx])
        return idx

    # NOTE: please do NOT change the function name, it is consumed by
    # LogicalEntity
    def _eliminate(self):
        ilk_idx = self._free_ilk_idx()
        logger.debug("entity %s free ilk idx %u", self, ilk_idx)


pyDatalog.create_terms('lsp_array, exchange_lsp_array')
pyDatalog.create_terms('lrp_array, ls_array, lr_array, chassis_array')
pyDatalog.create_terms('lroute_array, Route, lnat_array')
pyDatalog.create_terms('lroute_lrp')
pyDatalog.create_terms('ovsport, ovsport_chassis')

LSP_UUID = 0
LSP_IP = 1
LSP_IP_INT = 2
LSP_MAC = 3
LSP_MAC_INT = 4
LSP_CHASSIS_UUID = 5
LSP_LS_UUID = 6
LSP_PEER = 7
LSP_PORTID = 8
LSP_State = 9
LSP_OFPORT = 10 #external data
+lsp_array(0,0,0,0,0,0)
-lsp_array(0,0,0,0,0,0)
+exchange_lsp_array(0,0,0,0,0,0)
-exchange_lsp_array(0,0,0,0,0,0)
class LogicalSwitchPort(LogicalEntity):
    # NOTE: order of property-key is essential !
    property_keys = [LOGICAL_ENTITY_ID, 'ip', 'mac',
                     LOGICAL_ENTITY_PARENT_ID, 'chassis', 'peer']
    entity_type = LOGICAL_ENTITY_TYPE_LSP
    # NOTE: please change the name of variable if you had changed the string
    #       in uniq_check_keys. _insert_entity_idxmap consumes them.
    uniq_check_keys = ['ls_view_ip', 'ls_view_mac']

    def __init__(self, uuid, ip, mac, ls_uuid,
                 chassis = None, peer = None):
        super(LogicalSwitchPort, self).__init__()
        self.uuid = uuid
        self.ip = ip
        self.ip_int = struct.unpack("!L", socket.inet_aton(ip))[0]
        self.mac = mac;
        self.mac_int = int(mac.translate(None, ":.- "), 16)
        self.chassis = chassis
        self.ls_uuid = ls_uuid
        self.peer = peer
        self.portID = self.ip_int & 0xffff # 0 ~ 0xffff
        self.ls_view_ip = '{}{}'.format(self.ls_uuid, self.ip)
        self.ls_view_mac = '{}{}'.format(self.ls_uuid, self.mac)
        self.lsp_shop = lsp_array if peer is None else exchange_lsp_array
        # only regular lsp need to be touched
        self.touched = False if peer is None else True

    def _update_dup_data(self):
        self.lsp = [self.uuid, self.ip, self.ip_int, self.mac,
                    self.mac_int, self.chassis, self.ls_uuid,
                    self.peer, self.portID, self.state]

    def _is_update_clause(self):
        if not get_extra()['options'].has_key('ONDEMAND'):
            return True
        if self.chassis == get_extra()['system_id']:
            return True
        return self.touched

    # touch lsp, means we should generate flow and count this lsp in
    def touch(self):
        if self.touched is True:
            return
        self.touched = True
        self.state = State_ADD
        self._update_dup_data()
        self.add_clause()

    def del_clause(self):
        if self._is_update_clause() is False:
            return
        -self.lsp_shop(self.lsp[LSP_UUID], self.lsp,
                       self.lsp[LSP_LS_UUID], self.lsp[LSP_CHASSIS_UUID],
                       self.lsp[LSP_PEER], self.lsp[LSP_State])

    def add_clause(self):
        if self._is_update_clause() is False:
            return
        +self.lsp_shop(self.lsp[LSP_UUID], self.lsp,
                       self.lsp[LSP_LS_UUID], self.lsp[LSP_CHASSIS_UUID],
                       self.lsp[LSP_PEER], self.lsp[LSP_State])

    def is_same(self, uuid, ip, mac, ls_uuid, chassis, peer):
        return self.uuid == uuid and self.ip == ip and \
               self.mac == mac and self.ls_uuid == ls_uuid and \
               self.chassis == chassis and self.peer == peer

    def __repr__(self):
        return "lsp({},ip:{},mac:{},chassis:{})".format(self.uuid, self.ip,
                                                        self.mac, self.chassis)


LRP_UUID = 0
LRP_PREFIX = 1
LRP_IP = 2
LRP_IP_INT = 3
LRP_MAC = 4
LRP_MAC_INT = 5
LRP_LR_UUID = 6
LRP_PEER = 7
LRP_PORTID = 8
LRP_ILK_IDX = 9
LRP_State = 10
+lrp_array(0,0,0,0,0)
-lrp_array(0,0,0,0,0)
class LogicalRouterPort(LogicalEntity, ILKEntity):
    property_keys = [LOGICAL_ENTITY_ID, 'ip', 'prefix', 'mac',
                     LOGICAL_ENTITY_PARENT_ID, 'peer']
    entity_type = LOGICAL_ENTITY_TYPE_LRP
    uniq_check_keys = ['lr_view_ip', 'lr_view_mac']

    def __init__(self, uuid, ip, prefix,
                 mac, lr_uuid, peer = None):
        super(LogicalRouterPort, self).__init__()
        self.uuid = uuid
        self.prefix = max(min(int(prefix), 32), 0)
        self.ip = ip
        self.ip_int = struct.unpack("!L", socket.inet_aton(ip))[0]
        self.mac = mac;
        self.mac_int = int(mac.translate(None, ":.- "), 16)
        self.lr_uuid = lr_uuid
        self.peer = peer
        self.portID = self.ip_int & 0xffff # 0 ~ 0xffff
        self.lr_view_ip = '{}{}'.format(self.lr_uuid, self.ip)
        self.lr_view_mac = '{}{}'.format(self.lr_uuid, self.mac)
        ILKEntity.__init__(self)

    def _update_dup_data(self):
        self.lrp = [self.uuid, self.prefix, self.ip,
                    self.ip_int, self.mac, self.mac_int,
                    self.lr_uuid, self.peer,
                    self.portID, self.ilk_idx, self.state]

    def del_clause(self):
        -lrp_array(self.lrp[LRP_UUID], self.lrp, self.lrp[LRP_LR_UUID],
                   self.lrp[LRP_PEER], self.lrp[LRP_State])

    def add_clause(self):
        +lrp_array(self.lrp[LRP_UUID], self.lrp, self.lrp[LRP_LR_UUID],
                   self.lrp[LRP_PEER], self.lrp[LRP_State])

    def is_same(self, uuid, ip, prefix, mac, lr_uuid, peer):
        return self.uuid == uuid and self.ip == ip and \
               self.prefix == int(prefix) and self.mac == mac and \
               self.lr_uuid == lr_uuid and self.peer == peer

    def __repr__(self):
        return "lrp({},ip:{},mac:{},peer:{}, ilk_idx:{})".format(
                        self.uuid, self.ip, self.mac, self.peer, self.ilk_idx)


LR_UUID = 0
LR_CHASSIS_UUID = 1
LR_ID = 2
LR_State = 3
+lr_array(0,0,0)
-lr_array(0,0,0)
class LogicalRouter(LogicalEntity):
    property_keys = [LOGICAL_ENTITY_ID, 'id', 'chassis']
    entity_type = LOGICAL_ENTITY_TYPE_LR
    uniq_check_keys = ['global_view_id']
    def __init__(self, uuid, lrID, chassis = None):
        super(LogicalRouter, self).__init__()
        self.uuid = uuid
        self.chassis = chassis
        self.lrID = int(lrID)
        self.global_view_id = str(self.lrID)

    def _update_dup_data(self):
        self.lr = [self.uuid, self.chassis, self.lrID, self.state]

    def del_clause(self):
        -lr_array(self.lr, self.lr[LR_UUID], self.lr[LR_State])

    def add_clause(self):
        +lr_array(self.lr, self.lr[LR_UUID], self.lr[LR_State])

    def is_same(self, uuid, lrID, chassis):
        return self.uuid == uuid and self.lrID == int(lrID) and \
               self.chassis == chassis
    def __repr__(self):
        return "lr({},id:{})".format(self.uuid, self.lrID)



LSR_UUID = 0
LSR_LR_UUID = 1
LSR_IP = 2
LSR_IP_INT = 3
LSR_PREFIX = 4
LSR_NEXT_HOP = 5
LSR_NEXT_HOP_INT = 6
LSR_OUTPORT = 7
LSR_ILK_IDX = 8
LSR_State = 9
+lroute_array(0,0,0)
-lroute_array(0,0,0)
class LogicalStaticRoute(LogicalEntity, ILKEntity):
    property_keys = [LOGICAL_ENTITY_ID, 'ip', 'prefix', 'next_hop',
                     'outport', LOGICAL_ENTITY_PARENT_ID]
    entity_type = LOGICAL_ENTITY_TYPE_LSR
    uniq_check_keys = ['lr_view_lsr']

    def __init__(self, uuid, ip, prefix, next_hop,
                 outport, lr_uuid):
        super(LogicalStaticRoute, self).__init__()
        self.uuid = uuid
        self.lr_uuid = lr_uuid
        self.prefix = max(min(int(prefix), 32), 0)
        self.ip = ip
        self.ip_int = struct.unpack("!L", socket.inet_aton(ip))[0]
        self.ip_int = (self.ip_int >> (32 - self.prefix)) << (32 - self.prefix)
        self.next_hop = next_hop
        self.next_hop_int = struct.unpack("!L", socket.inet_aton(next_hop))[0]
        self.outport = outport
        self.lr_view_lsr = "lsr{}{}{}{}{}".format(self.lr_uuid, self.ip,
                                                  self.prefix, self.next_hop,
                                                  self.outport)
        ILKEntity.__init__(self)

    def _update_dup_data(self):
        self.lsr = [self.uuid, self.lr_uuid, self.ip,
                    self.ip_int, self.prefix, self.next_hop,
                    self.next_hop_int, self.outport,
                    self.ilk_idx, self.state]

    def del_clause(self):
        -lroute_array(self.lsr, self.lsr[LSR_LR_UUID], self.lsr[LSR_State])

    def add_clause(self):
        +lroute_array(self.lsr, self.lsr[LSR_LR_UUID], self.lsr[LSR_State])

    def is_same(self, uuid, ip, prefix, next_hop, outport, lr_uuid):
        return self.uuid == uuid and self.ip == ip and \
               self.prefix == int(prefix) and self.next_hop == next_hop and \
               self.outport == outport and self.lr_uuid == lr_uuid

    def __repr__(self):
        return "lsr:({}, rule:{}/{}, output:{}, ilk_idx:{})".format(
                        self.uuid, self.ip, self.prefix,
                        self.outport, self.ilk_idx)

LNAT_UUID = 0
LNAT_LR_UUID = 1
LNAT_IP = 2
LNAT_IP_INT = 3
LNAT_PREFIX = 4
LNAT_XLATE_IP = 5
LNAT_XLATE_IP_INT = 6
LNAT_XLATE_MAC = 7
LNAT_XLATE_MAC_INT = 8
LNAT_TYPE = 9
LNAT_State = 10
+lnat_array(0,0,0,0)
-lnat_array(0,0,0,0)
class LogicalNetAddrXlate(LogicalEntity):
    property_keys = [LOGICAL_ENTITY_ID, 'ip', 'prefix', 'xlate_ip',
                     'xlate_type', LOGICAL_ENTITY_PARENT_ID]
    entity_type = LOGICAL_ENTITY_TYPE_LNAT
    uniq_check_keys = ['lr_view_lnat']
    def __init__(self, uuid, ip, prefix, xlate_ip,
                 xlate_type, lr_uuid):
        super(LogicalNetAddrXlate, self).__init__()
        self.uuid = uuid
        self.lr_uuid = lr_uuid
        self.ip = ip
        self.ip_int = struct.unpack("!L", socket.inet_aton(ip))[0]
        self.prefix = int(prefix)
        self.xlate_ip = xlate_ip
        self.xlate_ip_int = struct.unpack("!L", socket.inet_aton(xlate_ip))[0]
        self.xlate_mac = _gen_mac_by_ip(self.xlate_ip_int)
        self.xlate_mac_int = int(self.xlate_mac.translate(None, ":.- "), 16)
        self.xlate_type = xlate_type
        self.lr_view_lnat = "lnat{}{}{}{}".format(self.lr_uuid, self.ip,
                                                  self.prefix, self.xlate_type)

    def _update_dup_data(self):
        self.lnat = [self.uuid, self.lr_uuid, self.ip,
                     self.ip_int, self.prefix, self.xlate_ip,
                     self.xlate_ip_int, self.xlate_mac, self.xlate_mac_int,
                     self.xlate_type, self.state]

    def del_clause(self):
        -lnat_array(self.lnat, self.lnat[LNAT_LR_UUID],
                    self.lnat[LNAT_TYPE], self.lnat[LNAT_State])

    def add_clause(self):
        +lnat_array(self.lnat, self.lnat[LNAT_LR_UUID],
                    self.lnat[LNAT_TYPE], self.lnat[LNAT_State])

    def is_same(self, uuid, ip, prefix, xlate_ip, xlate_type, lr_uuid):
        return self.uuid == uuid and self.ip == ip and \
               self.prefix == int(prefix) and self.xlate_ip == xlate_ip and \
               self.xlate_type == xlate_type and self.lr_uuid == lr_uuid

    def __repr__(self):
        return "lnat:({}, {}/{} => {}, type:{})".format(self.uuid, self.ip,
                                                        self.prefix,
                                                        self.xlate_ip,
                                                        self.xlate_type)



LS_UUID = 0
LS_ID = 1
LS_State = 2
+ls_array(0,0,0)
-ls_array(0,0,0)
class LogicalSwitch(LogicalEntity):
    property_keys = [LOGICAL_ENTITY_ID, 'id']
    entity_type = LOGICAL_ENTITY_TYPE_LS
    uniq_check_keys = ['global_view_id']
    def __init__(self, uuid, lsID):
        super(LogicalSwitch, self).__init__()
        self.uuid = uuid
        self.lsID = lsID
        self.global_view_id = str(self.lsID)

    def _update_dup_data(self):
        self.ls = [self.uuid, self.lsID, self.state]

    def del_clause(self):
        -ls_array(self.ls, self.ls[LS_UUID], self.ls[LS_State])

    def add_clause(self):
        +ls_array(self.ls, self.ls[LS_UUID], self.ls[LS_State])

    def is_same(self, uuid, lsID):
        return self.uuid == uuid and self.lsID == lsID

    def __repr__(self):
        return "ls({},id:{})".format(self.uuid, self.lsID)


PCH_UUID = 0
PCH_IP = 1
PCH_TICK = 2
PCH_State = 3
PCH_OFPORT = 4 # external data
+chassis_array(['flow_base_tunnel', '', 0, 0],
               'flow_base_tunnel', 0)
class PhysicalChassis(LogicalEntity):
    property_keys = [LOGICAL_ENTITY_ID, 'ip', 'tick']
    entity_type = LOGICAL_ENTITY_TYPE_CHASSIS
    uniq_check_keys = ['global_view_chassis']
    def __init__(self, uuid, ip, tick):
        super(PhysicalChassis, self).__init__()
        self.uuid = uuid
        self.ip = ip
        self.ip_int = struct.unpack("!L", socket.inet_aton(ip))[0]
        # it tells which chassis(has same IP) is the latest one
        self.tick = int(tick)
        self.global_view_chassis = "chassis{}{}".format(self.ip, self.tick)
        self.touched = False

    def _update_dup_data(self):
        self.ch = [self.uuid, self.ip, self.tick, self.state]

    def _is_update_clause(self):
        if not get_extra()['options'].has_key('ONDEMAND'):
            return True
        if self.uuid == get_extra()['system_id']:
            return True
        return self.touched

    # touch lsp, means we should generate flow and count this lsp in
    def touch(self):
        if self.touched is True:
            return
        self.touched = True
        self.state = State_ADD
        self._update_dup_data()
        self.add_clause()

    def del_clause(self):
        if self._is_update_clause() is False:
            return
        -chassis_array(self.ch, self.ch[PCH_UUID], self.ch[PCH_State])

    def add_clause(self):
        if self._is_update_clause() is False:
            return
        +chassis_array(self.ch, self.ch[PCH_UUID], self.ch[PCH_State])

    def is_same(self, uuid, ip, tick):
        return self.uuid == uuid and self.ip == ip and self.tick == int(tick)

    def __repr__(self):
        return "chassis({}, ip:{}, tick:{})".format(self.uuid, self.ip,
                                                    self.tick)

OVSPORT_NAME = 0
OVSPORT_IFACE_ID = 1
OVSPORT_OFPORT = 2
OVSPORT_State = 3
+ovsport(0,0,0,0)
-ovsport(0,0,0,0)
+ovsport_chassis(0,0,0,0)
-ovsport_chassis(0,0,0,0)
class OVSPort(LogicalEntity):
    uniq_check_keys = ['host_view_ovsport']
    def __init__(self, name, iface_id, ofport, is_remote):
        super(OVSPort, self).__init__()
        self.ovsport_name = name
        self.uuid = self.ovsport_name
        self.iface_id = iface_id
        self.ofport = ofport
        self.is_remote = is_remote
        self.host_view_ovsport = "ovsport{}{}{}".format(self.ovsport_name,
                                                        self.iface_id, self.ofport)
        self.port_shop = ovsport_chassis if is_remote else ovsport


    def _update_dup_data(self):
        self.port = [self.ovsport_name, self.iface_id, self.ofport, self.state]

    def del_clause(self):
        -self.port_shop(self.port[OVSPORT_NAME],
                        self.port[OVSPORT_IFACE_ID],
                        self.port[OVSPORT_OFPORT],
                        self.port[OVSPORT_State])

    def add_clause(self):
        +self.port_shop(self.port[OVSPORT_NAME],
                        self.port[OVSPORT_IFACE_ID],
                        self.port[OVSPORT_OFPORT],
                        self.port[OVSPORT_State])

    def is_same(self, name, iface_id, ofport, is_remote):
        return self.ovsport_name == name and self.iface_id == iface_id and \
               self.ofport == ofport and self.is_remote == is_remote

    def __repr__(self):
        return "ovsport({},iface_id:{},ofport:{})".format(self.ovsport_name,
                                                          self.iface_id,
                                                          self.ofport)

class ZooGate():
    def __init__(self, zoo, sink_zoo, lock = threading.Lock()):
        self.lock = lock
        self.zoo = zoo
        self.sink_zoo = sink_zoo

    def __enter__(self):
        self.lock.acquire()
        return self.zoo, self.sink_zoo

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.lock.release()
        if exc_tb is None:
            return True
        return False

class LogicalEntityZoo():
    logical_entity_types = {LOGICAL_ENTITY_TYPE_LSP:LogicalSwitchPort,
                            LOGICAL_ENTITY_TYPE_LRP:LogicalRouterPort,
                            LOGICAL_ENTITY_TYPE_LSR:LogicalStaticRoute,
                            LOGICAL_ENTITY_TYPE_LNAT:LogicalNetAddrXlate,
                            LOGICAL_ENTITY_TYPE_CHASSIS:PhysicalChassis,
                            LOGICAL_ENTITY_TYPE_LS:LogicalSwitch,
                            LOGICAL_ENTITY_TYPE_LR:LogicalRouter,
                            LOGICAL_ENTITY_TYPE_OVSPORT:OVSPort,
                            LOGICAL_ENTITY_TYPE_OVSPORT_CHASSIS:OVSPort}
    def __init__(self):
        self.lock = threading.RLock()
        self.zoo_ver = 0 # if you modify the init value, please fix prev_zoo_ver as well
        self.entity_set = {}
        self.entity_sink_set = {}
        self.entity_idxmap = {}
        self.zoo_gate = ZooGate(self.entity_set, self.entity_sink_set,
                                self.lock)
        for name in LogicalEntityZoo.logical_entity_types:
            self.entity_set[name] = {}
            self.entity_sink_set[name] = {}

    def _add_entity_in_zoo(self, entity_type, entity):
        if entity is None:
            return
        entity_group = self.entity_set[entity_type]
        with self.lock:
            # pop out previous entity into entity_sink_set for removing later
            if entity_group.has_key(entity.uuid):
                logger.info("pop out old entity %s into sink", entity.uuid)
                self.move_entity2sink(entity_type, entity.uuid)

            if self._insert_entity_idxmap(entity) is False:
                logger.warn("faild to insert entity into idxmap")
                return
            entity_group[entity.uuid] = entity
            self.zoo_ver += 1
        logger.info('create a new %s:%s', entity_type, entity)
        return entity

    def convert_pool2entity(self, entity_type, add_pool):
        entity_class = LogicalEntityZoo.logical_entity_types[entity_type]
        for path, value_set in add_pool.items():
            path = path.split('/')
            self._convert_kv2entity(entity_class, path, value_set)


    def _convert_kv2entity(self, entity_class, path, properties):
        args = []
        entity_id = path[-1]
        try:
            for pname in entity_class.property_keys:
                if pname == LOGICAL_ENTITY_ID:
                    args.append(entity_id)
                    continue
                if pname == LOGICAL_ENTITY_PARENT_ID:
                    args.append(path[-3])
                    continue
                args.append(properties.get(pname))
            self.add_entity(entity_class.entity_type, *args)
        except Exception as err:
            logger.exception("hit error in converting properties to entity "
                             "property:%s, err:%s", properties, err)

    def _insert_entity_idxmap(self, entity):
        with self.lock:
            for k in entity.uniq_check_keys:
                v = getattr(entity, k)
                if not self.entity_idxmap.has_key(k):
                    self.entity_idxmap[k] = {}
                if self.entity_idxmap[k].has_key(v):
                    logger.info('cannot insert %s in entity_idxmap, it already '
                                'has %s', entity, self.entity_idxmap[k][v])
                    return False
                self.entity_idxmap[k][v] = entity

        return True

    def _del_entity_idxmap(self, entity):
        with self.lock:
            for k in entity.uniq_check_keys:
                v = getattr(entity, k)
                try:
                    self.entity_idxmap[k].pop(v)
                except:
                    logger.exception("failed to remove entity:%s "
                                     "from entity_idxmap", entity)
                    return


    def add_entity(self, entity_type, *properties):
        entity_class = LogicalEntityZoo.logical_entity_types.get(entity_type)
        if entity_class is None:
            logger.warning('unknow entity_type %s', entity_type)
            return

        entity_id = properties[0]
        entity_group = self.entity_set[entity_type]
        with self.lock:
            if entity_group.has_key(entity_id) and \
               entity_group[entity_id].is_same(*properties):
                logger.info('entity_set[%s] has same property entity '
                            'exist entity:%s, conflict entity:%s',
                            entity_type, entity_group[entity_id], properties)
                return
            try:
                e = entity_class(*properties)
            except Exception as err:
                logger.exception("hit error in adding entity %s, "
                                 "property:%s, err:%s",
                                 entity_type, properties, err)
                return
        e = self._add_entity_in_zoo(entity_type, e)
        if e is None:
            return None
        e.populate()

        # a chassis which a LR pin on should be touch to generate
        # tunnel. This tunnel was use to redirect traffic.
        if not get_extra()['options'].has_key('ONDEMAND'):
            return
        # a LR pin on a remote chassis means this chassis s a
        # gateway or agent. The tunnel should be generated immediately.
        if entity_type == LOGICAL_ENTITY_TYPE_LR:
            self._touch_gateway_by_LR(e)
        if entity_type == LOGICAL_ENTITY_TYPE_CHASSIS:
            self._touch_gateway_by_chassis(e)

    def has_entity(self, entity_type, key):
        with self.lock:
            if not self.entity_set.has_key(entity_type):
                return False
            return entity_set[entity_type].has_key(key)

    def move_entity2sink(self, entity_type, key):
        if not LogicalEntityZoo.logical_entity_types.has_key(entity_type):
            logger.warning('unknow entity_type %s', entity_type)
            return

        with self.lock:
            entity_group = self.entity_set[entity_type]
            entity_sink_group = self.entity_sink_set[entity_type]
            entity = entity_group.pop(key, None)
            if entity is None:
                logger.info('cannot found entity %s', key)
                return

            entity.mark(State_DEL)
            if entity_sink_group.has_key(key):
                entity_sink_group[key].append(entity)
            else:
                entity_sink_group[key] = [entity]
            self._del_entity_idxmap(entity)
            # update the zoo version as well
            self.zoo_ver += 1
        logger.info('move %s to sink', entity)

    def move_entity2sink_by_pool(self, entity_type, del_pool):
        for path, _ in del_pool.items():
            key = path.split('/')[-1]
            self.move_entity2sink(entity_type, key)

    def move_all_entity2sink(self, exclude_entity_type_list = []):
        with self.lock:
            for entity_type, group in self.entity_set.items():
                if entity_type in exclude_entity_type_list:
                    # skip exclude list
                    continue
                for entity_key in group.keys():
                    self.move_entity2sink(entity_type, entity_key)

    def get_entity_by_fn(self, entity_type, fn, key):
        with self.lock:
            try:
                array = fn(self.entity_set[entity_type], key)
                return array
            except Exception as err:
                logger.exception("error in searching entity, err:%s", err)
                return []

    def touch_entity(self, entity_type, fn, key):
        with self.lock:
            array = self.get_entity_by_fn(entity_type, fn, key)
            if len(array) == 0:
                logger.info("cannot touch %s's entity by using %s",
                            entity_type, key)
                return array
            for entity in array:
                try:
                    entity.touch()
                except Exception as err:
                    logger.exception("error in touching entity, err:%s", err)
                    continue
                logger.info("touch entity %s", entity)
            return array

    def _touch_gateway_by_LR(self, lr):
        chassis_set = self.entity_set[LOGICAL_ENTITY_TYPE_CHASSIS]
        chassis = chassis_set.get(lr.chassis)
        if chassis is None:
            return
        chassis.touch()
        logger.debug("touch gateway chassis %s", chassis)

    def _touch_gateway_by_chassis(self, chassis):
        lr_set = self.entity_set[LOGICAL_ENTITY_TYPE_LR]
        for lr in lr_set.values():
            if lr.chassis == chassis.uuid:
                chassis.touch()
                logger.debug("touch gateway chassis %s", chassis)

    def sweep_zoo(self):
         with self.lock:
            # delete the entity which was move into sink in previous process
            self._clean_sink()
            self._sweep_entity_set()

    def _sweep_entity_set(self):
        # TODO it is a time cost function
        for group in self.entity_set.values():
            for key,e in group.items():
                if e.state == State_ADD:
                    e.mark(State_NO)
                    logger.debug('remark %s to State_NO', e)


    def _clean_sink(self):
        for group in self.entity_sink_set.values():
            for key, e in group.items():
                for entry in e:
                    entry.eliminate()
                    logger.debug('eliminate %s from sink', entry)
                group.pop(key)


entity_zoo = LogicalEntityZoo()
def get_zoo():
    return entity_zoo

pyDatalog.create_terms('LSP, LS, LRP, LNAT, LR, PHY_CHASSIS')
pyDatalog.create_terms('UUID_LS, UUID_LR, UUID_LSP, UUID_LRP, UUID_CHASSIS')
pyDatalog.create_terms('UUID_LS1, UUID_LR1, UUID_LSP1, UUID_LRP1, UUID_CHASSIS1')
pyDatalog.create_terms('UUID_LS2, UUID_LR2, UUID_LSP2, UUID_LRP2,UUID_CHASSIS2')
pyDatalog.create_terms('UUID_LR_CHASSIS1, UUID_LR_CHASSIS2')
pyDatalog.create_terms('LSP1, LSP2, LRP1, LRP2, LR1, LR2')
pyDatalog.create_terms('UUID_LR_CHASSIS')
pyDatalog.create_terms('LSP_WITH_OFPORT, PHY_CHASSIS_WITH_OFPORT, OFPORT')
pyDatalog.create_terms('State, State1, State2, State3, State4, State5, State6')
pyDatalog.create_terms('PORT_NAME, XLATE_TYPE')

pyDatalog.create_terms('remote_lsp')
pyDatalog.create_terms('active_lsp')
pyDatalog.create_terms('remote_chassis')
pyDatalog.create_terms('local_chassis')
pyDatalog.create_terms('remote_unable_chassis')
pyDatalog.create_terms('local_lsp, local_bond_lsp')
pyDatalog.create_terms('lsp_link_lrp')
pyDatalog.create_terms('lnat_data')
pyDatalog.create_terms('local_system_id')
pyDatalog.create_terms('next_hop_ovsport')

def init_entity_clause(options):

    local_bond_lsp(LSP_WITH_OFPORT, LS, State) <= (
        ovsport(PORT_NAME, UUID_LSP, OFPORT, State1) &
        (OFPORT > 0) &
        ls_array(LS, UUID_LS, State2) &
        lsp_array(UUID_LSP, LSP, UUID_LS, UUID_CHASSIS, UUID_LRP, State3) &
        local_system_id(UUID_CHASSIS) &
        (LSP_WITH_OFPORT == (LSP + [OFPORT])) &
        (State == State1 + State2 + State3)
        )

    local_lsp(LSP, LS, State) <= (
        (UUID_LR_CHASSIS == None) &
        lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR, UUID_LR, UUID_LR_CHASSIS, State)
        )
    local_lsp(LSP, LS, State) <= (
        local_system_id(UUID_LR_CHASSIS) &
        lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR, UUID_LR, UUID_LR_CHASSIS, State)
        )
    local_lsp(LSP, LS, State) <= (local_bond_lsp(LSP, LS, State))

    active_lsp(LSP, LS, UUID_LS, State) <= (
        ls_array(LS, UUID_LS, State1) &
        lsp_array(UUID_LSP, LSP, UUID_LS, UUID_CHASSIS, UUID_LRP, State2) &
        chassis_array(PHY_CHASSIS, UUID_CHASSIS, State3) &
        (State == State1 + State2 + State3)
        )
    active_lsp(LSP, LS, UUID_LS, State) <= (
        lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR, UUID_LR, UUID_LR_CHASSIS, State))

    remote_chassis(UUID_CHASSIS, PHY_CHASSIS_WITH_OFPORT, State) <= (
        ovsport_chassis(PORT_NAME, UUID_CHASSIS, OFPORT, State1) &
        (OFPORT > 0) &
        chassis_array(PHY_CHASSIS, UUID_CHASSIS, State2) &
        (PHY_CHASSIS_WITH_OFPORT == PHY_CHASSIS + [OFPORT]) &
        (State == State1 + State2)
        )

    local_chassis(PHY_CHASSIS, State) <= (
        local_system_id(UUID_CHASSIS) &
        chassis_array(PHY_CHASSIS, UUID_CHASSIS, State)
        )

    remote_lsp(LSP, LS, PHY_CHASSIS, State) <= (
        remote_chassis(UUID_CHASSIS, PHY_CHASSIS, State1) &
        lsp_array(UUID_LSP, LSP, UUID_LS, UUID_CHASSIS, UUID_LRP, State2) &
        ls_array(LS, UUID_LS, State3) &
        (State == State1 + State2 + State3)
        )

    remote_lsp(LSP, LS, PHY_CHASSIS, State) <= (
        lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR, UUID_LR, UUID_LR_CHASSIS, State1) &
        remote_chassis(UUID_LR_CHASSIS, PHY_CHASSIS, State2) &
        (State == State1 + State2)
        )


    lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR, UUID_LR, UUID_LR_CHASSIS, State) <= (
        lrp_array(UUID_LRP, LRP, UUID_LR, UUID_LSP, State1) &
        exchange_lsp_array(UUID_LSP, LSP, UUID_LS, UUID_CHASSIS, UUID_LRP, State2) &
        ls_array(LS, UUID_LS, State3) &
        lr_array(LR, UUID_LR, State4) &
        (UUID_LR_CHASSIS == LR[LR_CHASSIS_UUID]) &
        (State == State1 + State2 + State3 +State4)
        )

    next_hop_ovsport(UUID_LRP, OFPORT, State) <= (
        lrp_array(UUID_LRP, LRP, UUID_LR, UUID_LSP, State1) &
        exchange_lsp_array(UUID_LSP1, LSP1, UUID_LS, UUID_CHASSIS1, UUID_LRP, State2) &
        exchange_lsp_array(UUID_LSP2, LSP2, UUID_LS, UUID_CHASSIS2, UUID_LRP2, State3) &
        lrp_array(UUID_LRP2, LRP2, UUID_LR2, UUID_LSP2, State4) & (UUID_LR != UUID_LR2) &
        lr_array(LR2, UUID_LR2, State5) &
        ovsport_chassis(PORT_NAME, LR2[LR_CHASSIS_UUID], OFPORT, State6) &
        (State == State1 + State2 + State3 + State4 + State5 + State6)
        )

    if not get_extra()['options'].has_key('ENABLE_PERFORMANCE_TESTING'):
        lnat_data(LNAT, LR, XLATE_TYPE, UUID_LR, State) <= (
            lr_array(LR, UUID_LR, State1) &
            # TODO local_system_id, UUID_CHASSIS here introduce
            # performance regression
            (UUID_CHASSIS == LR[LR_CHASSIS_UUID]) &
            local_system_id(UUID_CHASSIS) &
            lnat_array(LNAT, UUID_LR, XLATE_TYPE, State2) &
            (State == State1 + State2)
        )
    else:
        lnat_data(LNAT, LR, XLATE_TYPE, UUID_LR, State) <= (
            lr_array(LR, UUID_LR, State1) &
            lnat_array(LNAT, UUID_LR, XLATE_TYPE, State2) &
            (State == State1 + State2)
        )



