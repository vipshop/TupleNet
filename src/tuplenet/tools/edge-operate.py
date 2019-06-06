#!/usr/bin/python
import sys, os, time
import logging
import struct, socket
from optparse import OptionParser
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ppparent_dir = os.path.dirname(os.path.dirname(parent_dir))
py_third_dir = os.path.join(ppparent_dir, 'py_third')
sys.path = [parent_dir, py_third_dir] + sys.path
from lcp import link_master as lm
from lcp import commit_ovs as cm
from pyDatalog import pyDatalog


logger = logging.getLogger('')
TUPLENET_DIR = ""
ETCD_ENDPOINT = ""
etcd = None
wmaster = None
system_id = ""
HOST_BR_PHY = ""
HOST_BR_INT = 'br-int'
entity_list = []

class TPToolErr(Exception):
    pass

class LSwitch(pyDatalog.Mixin):
    def __init__(self, uuid):
        super(LSwitch, self).__init__()
        self.uuid = uuid
        self.name = uuid
    def __repr__(self):
        return self.uuid

class LRouter(pyDatalog.Mixin):
    def __init__(self, uuid, chassis = None):
        super(LRouter, self).__init__()
        self.uuid = uuid
        self.chassis = chassis
        self.name = uuid
    def __repr__(self):
        return "%s:(chassis:%s)" %(self.uuid, self.chassis)

class LSPort(pyDatalog.Mixin):
    def __init__(self, uuid, ip, mac, parent, chassis = None, peer = None):
        super(LSPort, self).__init__()
        self.uuid = uuid
        self.ip = ip
        self.mac = mac
        self.parent = parent
        self.chassis = chassis
        self.peer = peer
        self.name = uuid

    def __repr__(self):
        return "%s:(ip:%s, parent:%s)" % (self.uuid, self.ip, self.parent)

class LRPort(pyDatalog.Mixin):
    def __init__(self, uuid, ip, prefix, mac, parent,
                 chassis = None, peer = None):
        super(LRPort, self).__init__()
        self.uuid = uuid
        self.ip = ip
        self.prefix = int(prefix)
        self.mac = mac
        self.parent = parent
        self.chassis = chassis
        self.peer = peer
        self.name = uuid

    def __repr__(self):
        return "%s:(ip:%s/%d, parent:%s)" % (self.uuid, self.ip,
                        self.prefix, self.parent)

class LStaticRoute(pyDatalog.Mixin):
    def __init__(self, uuid, ip, prefix, next_hop, outport, parent):
        super(LStaticRoute, self).__init__()
        self.uuid = uuid
        self.ip = ip
        self.prefix = int(prefix)
        self.next_hop = next_hop
        self.outport = outport
        self.parent = parent
        self.name = uuid

    def __repr__(self):
        return self.uuid

class Chassis(pyDatalog.Mixin):
    def __init__(self, uuid, ip, tick):
        super(Chassis, self).__init__()
        self.uuid = uuid
        self.ip = ip
        self.tick = tick
        self.name = uuid

    def __repr__(self):
        return self.uuid

def init_logger():
    global logger
    log_type = logging.NullHandler()
    logger = logging.getLogger('')
    format_type = ("%(asctime)s.%(msecs)03d %(levelname)s %(filename)s "
                   "[line:%(lineno)d]: %(message)s")
    datefmt = '%Y-%m-%d %H:%M:%S'
    console = log_type
    console_formater = logging.Formatter(format_type, datefmt)
    console.setFormatter(console_formater)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(console)
    logger.info("")


def ecmp_execute_cmds(cmd_tpctl_list, cmd_first = None, cmd_final = None):
    if cmd_first is not None:
        tpctl_execute([cmd_first])
        time.sleep(5)
    tpctl_execute(cmd_tpctl_list)
    if cmd_final is not None:
        time.sleep(5)
        tpctl_execute([cmd_final])

def tpctl_execute(cmd_list):
    endpoint_cmd = "--endpoints={}".format(ETCD_ENDPOINT)
    prefix_cmd = "--prefix={}".format(TUPLENET_DIR)
    for cmd in cmd_list:
        cmd = cmd.split()
        cmd.insert(1, prefix_cmd)
        cmd.insert(1, endpoint_cmd)
        cm.call_popen(cmd, commu='yes\n', shell=False)

def update_entity(entity_list, add_pool):
    if add_pool.has_key('LS'):
        for path, value_set in add_pool['LS'].items():
            path = path.split('/')
            entity_id = path[-1]
            entity_list.append(LSwitch(entity_id))

    if add_pool.has_key('LR'):
        for path, value_set in add_pool['LR'].items():
            path = path.split('/')
            entity_id = path[-1]
            entity_list.append(LRouter(entity_id, value_set.get('chassis')))

    if add_pool.has_key('lsp'):
        for path, value_set in add_pool['lsp'].items():
            path = path.split('/')
            entity_id = path[-1]
            parent = path[-3]
            entity_list.append(LSPort(entity_id, value_set['ip'],
                                      value_set['mac'], parent,
                                      value_set.get('chassis'),
                                      value_set.get('peer')))

    if add_pool.has_key('lrp'):
        for path, value_set in add_pool['lrp'].items():
            path = path.split('/')
            entity_id = path[-1]
            parent = path[-3]
            entity_list.append(LRPort(entity_id, value_set['ip'],
                                      value_set['prefix'],
                                      value_set['mac'], parent,
                                      value_set.get('chassis'),
                                      value_set.get('peer')))

    if add_pool.has_key('lsr'):
        for path, value_set in add_pool['lsr'].items():
            path = path.split('/')
            entity_id = path[-1]
            parent = path[-3]
            entity_list.append(LStaticRoute(entity_id, value_set['ip'],
                                      value_set['prefix'],
                                      value_set['next_hop'],
                                      value_set['outport'],
                                      parent))

    if add_pool.has_key('chassis'):
        for path, value_set in add_pool['chassis'].items():
            path = path.split('/')
            entity_id = path[-1]
            parent = path[-3]
            entity_list.append(Chassis(entity_id, value_set['ip'],
                                       value_set['tick']))


def sync_etcd_data(etcd_endpoints):
    global wmaster
    wmaster = lm.WatchMaster(etcd_endpoints, TUPLENET_DIR)
    data_type, add_pool, del_pool = wmaster.read_remote_kvdata()
    update_entity(entity_list, add_pool)

pyDatalog.create_terms('X,Y,Z')
pyDatalog.create_terms('LR, LS, LSP, LRP, LSR')
pyDatalog.create_terms('LR1, LS1, LSP1, LRP1, LSR1')
pyDatalog.create_terms('LR2, LS2, LSP2, LRP2, LSR2')
pyDatalog.create_terms('LR3, LS3, LSP3, LRP3, LSR3')
pyDatalog.create_terms('LS_OUT, LSP_OUT_TO_EDGE, LRP_EDGE_TO_OUT, LR_EDGE')
pyDatalog.create_terms('LRP_EDGE_TO_INNER, LSP_INNER_TO_EDGE, LS_INNER')
pyDatalog.create_terms('LSP_INNER_TO_CEN, LRP_CEN_TO_INNER, LR_CEN')
pyDatalog.create_terms('LSR_VIRT, LSR_EDGE, LSR_OUT')
def datalog_lr_central():
    LRouter.uuid[X] == Y
    if len(X.data) != 1:
        raise TPToolErr("failed to know central LR")
    return X.v()

def datalog_check_port_occupied_ip(ips):
    for ip in ips:
        LSPort.ip[X] == ip
        if len(X.data) != 0:
            raise TPToolErr("ip %s was occupied by other lsp" % ip)
        LRPort.ip[X] == ip
        if len(X.data) != 0:
            raise TPToolErr("ip %s was occupied by other lrp" % ip)

def datalog_check_chassis_exist(system_id):
    Chassis.uuid[X] == system_id
    if len(X.data) != 1:
        raise TPToolErr("chassis %s is not registed in etcd" % system_id)

def datalog_check_chassis_is_edge():
    LRouter.chassis[X] == system_id
    if len(X.data) == 0:
        raise TPToolErr("chassis %s is an edge already" % system_id)

def datalog_is_entity_exist(uuid):
    LSwitch.uuid[X] == uuid
    if len(X.data) != 0:
        return True
    LRouter.uuid[X] == uuid
    if len(X.data) != 0:
        return True
    LSPort.uuid[X] == uuid
    if len(X.data) != 0:
        return True
    LRPort.uuid[X] == uuid
    if len(X.data) != 0:
        return True
    LStaticRoute.uuid[X] == uuid
    if len(X.data) != 0:
        return True
    return False

pyDatalog.create_terms('dl_LS_has_patchport')
dl_LS_has_patchport(LS) <= (
    (LSPort.ip[LSP] == '255.255.255.255') &
    (LSwitch.uuid[LS] == LSPort.parent[LSP])
    )
pyDatalog.create_terms('dl_edge_LR_peer_LS')
dl_edge_LR_peer_LS(LR, LRP, LS, LSP) <= (
    (LRouter.chassis[LR] != None) &
    (LRouter.uuid[LR] == LRPort.parent[LRP]) &
    (LRPort.uuid[LRP] == LSPort.peer[LSP]) &
    (LSPort.parent[LSP] == LSwitch.uuid[LS])
    )

pyDatalog.create_terms('dl_edge_LR_peer_LR')
dl_edge_LR_peer_LR(LR, LRP, LR1, LRP1) <= (
    dl_edge_LR_peer_LS(LR, LRP, LS, LSP) &
    (LSPort.parent[LSP1] == LSwitch.uuid[LS]) &
    (LSPort.peer[LSP1] == LRPort.uuid[LRP1]) &
    (LRPort.peer[LRP1] == LSPort.uuid[LSP1]) &
    (LRouter.uuid[LR1] == LRPort.parent[LRP1]) &
    (LR != LR1)
    )

pyDatalog.create_terms('dl_ecmp_road')
dl_ecmp_road(LS_OUT, LSP_OUT_TO_EDGE, LRP_EDGE_TO_OUT, LR_EDGE,
             LRP_EDGE_TO_INNER, LSP_INNER_TO_EDGE, LS_INNER,
             LRP_CEN_TO_INNER, LR_CEN, LSR_VIRT, LSR_OUT, LSR_EDGE
             ) <= (
    dl_edge_LR_peer_LS(LR_EDGE, LRP_EDGE_TO_OUT,
                       LS_OUT, LSP_OUT_TO_EDGE) &
    dl_LS_has_patchport(LS_OUT) &

    dl_edge_LR_peer_LS(LR_EDGE, LRP_EDGE_TO_INNER,
                       LS_INNER, LSP_INNER_TO_EDGE) &
    (LS_OUT != LS_INNER) &

    dl_edge_LR_peer_LR(LR_EDGE, LRP_EDGE_TO_INNER, LR_CEN, LRP_CEN_TO_INNER) &

    (LStaticRoute.parent[LSR_VIRT] == LRouter.uuid[LR_EDGE]) &
    (LStaticRoute.outport[LSR_VIRT] == LRPort.uuid[LRP_EDGE_TO_INNER]) &

    (LStaticRoute.parent[LSR_OUT] == LRouter.uuid[LR_EDGE]) &
    (LStaticRoute.outport[LSR_OUT] == LRPort.uuid[LRP_EDGE_TO_OUT]) &

    (LStaticRoute.parent[LSR_EDGE] == LRouter.uuid[LR_CEN]) &
    (LStaticRoute.outport[LSR_EDGE] == LRPort.uuid[LRP_CEN_TO_INNER])
    )


def new_entity_name(etype, prefix_name):
    i = 1
    prefix_name = '{}_{}'.format(etype, prefix_name)
    while True:
        name = "tp_{}{}".format(prefix_name, i)
        i += 1
        if datalog_is_entity_exist(name):
            continue
        return name

def _cmd_new_link(lr_name, ls_name, ip, prefix):
    cmd = "tpctl lr link {} {} {}/{}".format(lr_name, ls_name, ip, prefix)
    return cmd

def _cmd_new_lsr(lr_name, ip, prefix, next_hop, outport):
    lsr_name = "{}_{}-{}_to_{}_{}".format(lr_name, ip, prefix,
                                          next_hop, outport)
    cmd = "tpctl lsr add {} {} {}/{} {} {}".format(
                    lr_name, lsr_name, ip, prefix, next_hop, outport)
    return cmd

def _cmd_new_patchport(ls_name, portname, chassis, peer_br):
    cmd = "tpctl patchport add {} {} {} {}".format(
                    ls_name, portname, chassis, peer_br)
    return cmd

def _cmd_del_patchport(ls_name, portname):
    cmd = "tpctl lsp add {} {}".format(ls_name, portname)
    return cmd

def _cmd_new_ls(ls_name):
    cmd = "tpctl ls add {}".format(ls_name)
    return cmd

def _cmd_del_ls(ls_name):
    cmd = "tpctl ls del {} -r".format(ls_name)
    return cmd

def _cmd_new_lr(lr_name, chassis = None):
    if chassis is None:
        cmd = "tpctl lr add {}".format(lr_name)
    else:
        cmd = "tpctl lr add {} {}".format(lr_name, chassis)
    return cmd

def _cmd_del_lr(lr_name):
    cmd = "tpctl lr del {} -r".format(lr_name)
    return cmd

def _cmd_del_lrp(lr_name, lrp_name):
    cmd = "tpctl lrp del {} {}".format(lr_name, lrp_name)
    return cmd

def _cmd_del_lsr(lr_name, lsr_name):
    cmd = "tpctl lsr del {} {}".format(lr_name, lsr_name)
    return cmd

def _gen_lrp_property(ip_int, prefix):
    mprefix = 32 - prefix
    max_ip_int = ((ip_int >> mprefix) << mprefix) + (0xffffffff >> prefix)
    min_ip_int = ((ip_int >> mprefix) << mprefix)

    for ip_int in xrange(max_ip_int-1, min_ip_int, -1):
        try:
            ip = socket.inet_ntoa(struct.pack("!I", ip_int))
            datalog_check_port_occupied_ip([ip])
        except:
            continue
        else:
            return ip, prefix
    raise TPToolErr("cannot found a lrp due to ip confict")


def _init_ecmp_road(should_wait, central_lr, vip, vip_prefix, virt_ip,
                    virt_prefix, out_net, out_prefix, inner_ip, inner_prefix,
                    edge_net, edge_net_prefix, ext_gw):
    tp_cmd_list = []
    # create LS and LR command
    out_ls_name = new_entity_name('LS', 'outside')
    tp_cmd_list.append(_cmd_new_ls(out_ls_name))
    edge_lr_name = new_entity_name('LR', 'edge')
    tp_cmd_list.append(_cmd_new_lr(edge_lr_name, system_id))
    inner_ls_name = new_entity_name('LS', 'm')
    tp_cmd_list.append(_cmd_new_ls(inner_ls_name))

    #create patch port
    patchport = new_entity_name('lsp', out_ls_name + "-patchport")
    tp_cmd_list.append(_cmd_new_patchport(out_ls_name, patchport,
                                          system_id, HOST_BR_PHY))

    # create link command
    tp_cmd_list.append(_cmd_new_link(edge_lr_name, out_ls_name,
                                     vip, vip_prefix))
    tp_cmd_list.append(_cmd_new_link(edge_lr_name, inner_ls_name,
                                     inner_ip, inner_prefix))

    # it take an assumption that there is no lport consume inner_ip/prefix
    ip_int = struct.unpack("!L", socket.inet_aton(inner_ip))[0]
    central_lr_ip, _ = _gen_lrp_property(ip_int, int(inner_prefix))
    if central_lr_ip == inner_ip:
        raise Exception(("failed to allocate ip for "
                         "central_lr port, please revise inner ip"))
    tp_cmd_list.append(_cmd_new_link(central_lr, inner_ls_name,
                                     central_lr_ip, inner_prefix))

    # create lsr command
    outport = "{}_to_{}".format(edge_lr_name, out_ls_name)
    tp_cmd_list.append(_cmd_new_lsr(edge_lr_name, out_net, out_prefix,
                                    ext_gw, outport))

    outport = "{}_to_{}".format(edge_lr_name, inner_ls_name)
    tp_cmd_list.append(_cmd_new_lsr(edge_lr_name, virt_ip, virt_prefix,
                                    central_lr_ip, outport))

    outport = "{}_to_{}".format(central_lr, inner_ls_name)
    tp_cmd_list.append(_cmd_new_lsr(central_lr, edge_net, edge_net_prefix,
                                    inner_ip, outport))

    print("tpctl will executes following commands")
    print('\n'.join(tp_cmd_list))
    is_execute = raw_input(("Please verify tpctl commands and press "
                            "yes to init an ecmp path:"))
    if is_execute == 'yes':
        if should_wait:
            ecmp_execute_cmds(tp_cmd_list[:-1], cmd_final=tp_cmd_list[-1])
        else:
            ecmp_execute_cmds(tp_cmd_list)
        print("Done")
    else:
        sys.exit(0)



def _remove_ecmp_road(should_wait, out, edge, inner, central_lr,
                      central_lsr, central_lrp):
    outport_name = "{}_to_{}".format(central_lr.name, inner.name)
    tp_cmd_list = []
    tp_cmd_list.append(_cmd_del_lr(edge.name))
    tp_cmd_list.append(_cmd_del_ls(inner.name))
    tp_cmd_list.append(_cmd_del_ls(out.name))

    tp_cmd_list.insert(0, _cmd_del_lsr(central_lr.name, central_lsr.name))
    tp_cmd_list.insert(0, _cmd_del_lrp(central_lr.name, central_lrp.name))


    print("tpctl will executes following commands")
    print('\n'.join(tp_cmd_list))
    is_execute = raw_input(("Please verify tpctl commands and press "
                            "yes to remove a ecmp path:"))
    if is_execute == 'yes':
        if should_wait:
            ecmp_execute_cmds(tp_cmd_list[1:], cmd_first = tp_cmd_list[0])
        else:
            ecmp_execute_cmds(tp_cmd_list)
        print("Done")
    else:
        sys.exit(0)


def remove_ecmp_road(vip):
    dl_ecmp_road(LS_OUT, LSP_OUT_TO_EDGE, LRP_EDGE_TO_OUT, LR_EDGE,
                 LRP_EDGE_TO_INNER, LSP_INNER_TO_EDGE, LS_INNER,
                 LRP_CEN_TO_INNER, LR_CEN, LSR_VIRT, LSR_OUT, LSR_EDGE)
    ecmp_road = zip(LS_OUT.data, LRP_EDGE_TO_OUT.data,
                    LR_EDGE.data, LS_INNER.data,
                    LR_CEN.data, LSR_EDGE.data, LRP_CEN_TO_INNER.data)
    found = False
    for out, lrp_edge_to_out, edge, inner, \
        lr_central, lsr_central, lrp_central in ecmp_road:
        if lrp_edge_to_out.ip == vip:
            found = True
            should_wait = False if len(ecmp_road) == 1 else True
            _remove_ecmp_road(should_wait, out, edge, inner, lr_central,
                              lsr_central, lrp_central)
            break
    if found is False:
        raise TPToolErr("failed to search ecmp path by using vip:%s" % vip)

def add_ecmp_road(vip, vip_prefix):
    datalog_check_port_occupied_ip([vip])
    dl_ecmp_road(LS_OUT, LSP_OUT_TO_EDGE, LRP_EDGE_TO_OUT, LR_EDGE,
                 LRP_EDGE_TO_INNER, LSP_INNER_TO_EDGE, LS_INNER,
                 LRP_CEN_TO_INNER, LR_CEN, LSR_VIRT, LSR_OUT, LSR_EDGE)
    if len(LS_OUT.data) == 0:
        raise TPToolErr("failed to found exist ecmp road")

    _init_ecmp_road(True, LR_CEN.v().uuid, vip, vip_prefix,
                    LSR_VIRT.v().ip, LSR_VIRT.v().prefix,
                    LSR_OUT.v().ip, LSR_OUT.v().prefix,
                    LRP.v().ip, LRP.v().prefix,
                    LSR_EDGE.v().ip, LSR_EDGE.v().prefix,
                    LSR_OUT.v().next_hop)

def init_ecmp_road(vip, vip_prefix, virt_ip, virt_prefix,
                   inner_ip, inner_prefix, ext_gw):
    datalog_check_port_occupied_ip([vip, inner_ip, ext_gw])
    central_lr = datalog_lr_central()
    _init_ecmp_road(False, central_lr.name, vip, vip_prefix,
                    virt_ip, virt_prefix,
                    '0.0.0.0', 0, inner_ip, inner_prefix,
                    '0.0.0.0', 0, ext_gw)

def sanity_check_options(options):
    if options.op not in ['add', 'init', 'remove']:
        print("error operation, should be add, init or remove")
        return False
    try:
        vip,vip_prefix = options.vip.split('/')
        struct.unpack("!L", socket.inet_aton(vip))[0]
        vip_prefix = int(vip_prefix)
    except:
        print("error CIDR format vip")
        return False

    if options.op == 'init':
        try:
            virt_ip, virt_prefix = options.virt.split('/')
            struct.unpack("!L", socket.inet_aton(virt_ip))[0]
            virt_prefix = int(virt_prefix)
        except:
            print("error CIDR format virt")
            return False

        try:
            inner_ip, inner_prefix = options.inner.split('/')
            struct.unpack("!L", socket.inet_aton(inner_ip))[0]
            inner_prefix = int(inner_prefix)
            if inner_prefix < 2:
                print("inner perfix should large than 2")
                return False
        except:
            print("error CIDR format inner")
            return False

        try:
            struct.unpack("!L", socket.inet_aton(options.ext_gw))[0]
        except:
            print("error ext_gw ip address")
            return False
    return True

def check_env(options):
    global system_id
    system_id = cm.system_id()

    # remove operation do NOT need to check if etcd has chassis or local openvswitch has system-id
    if options.op == 'init' or options.op == 'add':
        if system_id is None or system_id == "":
            raise TPToolErr("failed to get ovs system-id")
        datalog_check_chassis_exist(system_id)
        if options.phy_br == 'br-int':
            raise TPToolErr("phy_br should not be a tuplenet bridge")
        try:
            cm.ovs_vsctl('get', 'bridge', options.phy_br, 'datapath_id')
        except Exception:
            raise TPToolErr("please check if we have ovs bridge %s" %
                            options.phy_br)

    try:
        tpctl_execute(['tpctl --help'])
    except Exception as err:
        print(("failed to execute tpctl, please check if tpctl "
                "had been installed"))
        raise err

    try:
        tpctl_execute(['tpctl lr show'])
    except Exception as err:
        print(("failed to execute tpctl lr show, please check etcd endpoints"))
        raise err


def main(options):
    check_env(options)
    vip, vip_prefix = options.vip.split('/')
    try:
        if options.op == 'add':
            add_ecmp_road(vip, vip_prefix)
        elif options.op == 'remove':
            remove_ecmp_road(vip)
        elif options.op == 'init':
            virt_ip, virt_prefix = options.virt.split('/')
            inner_ip, inner_prefix = options.inner.split('/')
            ext_gw = options.ext_gw
            init_ecmp_road(vip, vip_prefix, virt_ip, virt_prefix,
                           inner_ip, inner_prefix, ext_gw)
    except TPToolErr as err:
        print("hit error, err:%s" % err)
        sys.exit(-1)

if __name__ == "__main__":
    parser = OptionParser("""
    this tool can dump etcd tuplenet data to add/delete edge node
    please execute it on a candidate edge node """)
    parser.add_option("--endpoint", dest = "host",
                      action = "store", type = "string",
                      default = "localhost:2379",
                      help = "etcd host address, default:localhost:2379")
    parser.add_option("--prefix", dest = "prefix",
                      action = "store", type = "string",
                      default = "/tuplenet/",
                      help = """prefix path of tuplenet data in etcd
                                default:/tuplenet/""")
    parser.add_option("--op", dest = "op",
                      action = "store", type = "string",
                      help = """should be init, add or remove""")
    parser.add_option("--vip", dest = "vip",
                      action = "store", type = "string",
                      help = "the virtual ip(like:2.2.2.2/24) of edge node")
    parser.add_option("--phy_br", dest = "phy_br",
                      action = "store", type = "string",
                      help = "the bridge which connect to phy-network")
    parser.add_option("--virt", dest = "virt", default = "",
                      action = "store", type = "string",
                      help = "the whole virtual network(like:5.5.5.5/16)")
    parser.add_option("--inner", dest = "inner", default = "100.64.88.100/24",
                      action = "store", type = "string",
                      help = """the inner network(connect
                                virt to phy), default is 100.64.88.100/24""")
    parser.add_option("--ext_gw", dest = "ext_gw", default = "",
                      action = "store", type = "string",
                      help = "the physical gateway ip address")

    (options, args) = parser.parse_args()
    if not sanity_check_options(options):
        print("exit")
        sys.exit(-1)
    init_logger()
    TUPLENET_DIR = options.prefix
    HOST_BR_PHY = options.phy_br
    etcd_endpoints = lm.sanity_etcdhost(options.host)
    ETCD_ENDPOINT = options.host
    sync_etcd_data(etcd_endpoints)
    main(options)
