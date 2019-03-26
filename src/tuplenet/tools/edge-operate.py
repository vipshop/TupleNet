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

logger = logging.getLogger('')
TUPLENET_DIR = ""
ETCD_ENDPOINT = ""
etcd = None
wmaster = None
system_id = ""
HOST_BR_PHY = ""
HOST_BR_INT = 'br-int'
entity_zoo = {}

class TPToolErr(Exception):
    pass

def init_logger():
    global logger
    env = os.environ.copy()
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


def ovs_add_patch_port(patchport, br_int, br_phy):
    peer = '{}-peer'.format(patchport)
    cm.ovs_vsctl('add-port', br_phy, peer, '--', 'set',
                 'Interface', peer, 'type=patch',
                 'options:peer={}'.format(patchport))

    cm.ovs_vsctl('add-port', br_int, patchport, '--', 'set',
                 'Interface', patchport, 'type=patch',
                 'external_ids:iface-id={}'.format(patchport),
                 'options:peer={}'.format(peer))


def ovs_del_patch_port(patchport, br_int, br_phy):
    peer = cm.ovs_vsctl('get', 'Interface', patchport, 'options:peer')
    peer = peer.encode('ascii','ignore').replace('"', '')

    iface_id = cm.ovs_vsctl('get', 'Interface', patchport,
                            'external_ids:iface-id')
    iface_id = iface_id.encode('ascii','ignore').replace('"', '')
    if iface_id != patchport:
        raise TPToolErr("Error, patchport %s iface-id is not %s" %
                        (patchport, patchport))

    cm.ovs_vsctl('del-port', peer)
    cm.ovs_vsctl('del-port', patchport)


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


class TPObject:
    def __init__(self, name, properties):
        self.__setattr__('name', name)
        for k,v in properties.items():
            self.__setattr__(k, v)


    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def __getattr__(self, name):
        if name == 'ip_int':
            ip = self.__dict__.get('ip')
            return struct.unpack("!L", socket.inet_aton(ip))[0]
        return self.__dict__.get(name)

    def __str__(self):
        ret = self.name + ":"
        for k,v in self.__dict__.items():
            ret += "{}={}, ".format(k,v)
        return ret

    def __hash__(self):
        return hash(str([self.name, self.type, self.parent]))

    def __eq__(self, other):
        return str(self) == str(other)

    __repr__ = __str__


def update_entity_data(add_pool):
    if add_pool is not None:
        for etype,entity_dict in add_pool.items():
            if not entity_zoo.has_key(etype):
                entity_zoo[etype] = {}
            for k, entity in entity_dict.items():
                parent,type,key = k.split('/')[-3:]
                type = k.split('/')[-2]
                entity_zoo[etype][key] = TPObject(key, entity)
                entity_zoo[etype][key].type = type
                entity_zoo[etype][key].parent = parent


def sync_etcd_data(etcd_endpoints):
    global wmaster
    wmaster = lm.WatchMaster(etcd_endpoints, TUPLENET_DIR)
    data_type, add_pool, del_pool = wmaster.read_remote_kvdata()
    update_entity_data(add_pool)

def find_all_edge_nodes():
    edges = []
    lr_set = entity_zoo.get('LR')
    if lr_set is None:
        return edges

    for lr in lr_set.values():
        if lr.chassis is not None:
            edges.append(lr)
    return edges

def _get_link_ls(lr):
    linked_ls = []
    lrp_set = entity_zoo.get('lrp')
    lsp_set = entity_zoo.get('lsp')
    ls_set = entity_zoo.get('LS')
    if lrp_set is None or \
       lsp_set is None or ls_set is None:
        return linked_ls

    for lrp in lrp_set.values():
        if lrp.parent != lr.name:
            continue
        lsp = lsp_set.get(lrp.peer)
        if lsp is None:
            continue
        ls = ls_set.get(lsp.parent)
        if ls is None:
            continue
        linked_ls.append(ls)
    return linked_ls

def is_chassis_is_edge():
    edges = find_all_edge_nodes()
    for edge in edges:
        if edge.chassis == system_id:
            return True
    return False

def find_all_patchports():
    patchports = []
    lsp_set = entity_zoo.get('lsp')
    if lsp_set is None:
        return patchports

    for lsp in lsp_set.values():
        if lsp.ip == "255.255.255.255":
            patchports.append(lsp)
    return patchports

def is_ip_occupied(ip):
    lsp_set = entity_zoo.get('lsp')
    lrp_set = entity_zoo.get('lrp')
    if lrp_set is not None:
        for lrp in lrp_set.values():
            if lrp.ip == ip:
                return True

    if lsp_set is not None:
        for lsp in lsp_set.values():
            if lsp.ip == ip:
                return True
    return False

def find_ls_patchport(ls):
    lsp_set = entity_zoo.get('lsp')
    if lsp_set is None:
        return None
    for lsp in lsp_set.values():
        if lsp.ip == "255.255.255.255" and lsp.parent == ls.name:
            return lsp

def find_ls_lr_ls(edges, patchports):
    ls_lr_ls = []
    for edge in edges:
        linked_ls = set(_get_link_ls(edge))
        if len(linked_ls) != 2:
            raise TPToolErr("edge %s linked to more then 2 ls" % edge.name)
        for ls in linked_ls:
            for pport in patchports:
                if pport.parent == ls.name:
                    ls_lr_ls.append((ls, edge, (linked_ls-set([ls])).pop()))
    return ls_lr_ls


def find_central_LR(inner_ls):
    lr_set = entity_zoo.get('LR')
    lsp_set = entity_zoo.get('lsp')
    lrp_set = entity_zoo.get('lrp')
    if lr_set is None or lsp_set is None or lrp_set is None:
        return None

    for lsp in lsp_set.values():
        if lsp.parent != inner_ls.name:
            continue
        lrp = lrp_set.get(lsp.peer)
        if lrp is None:
            continue
        lr = lr_set.get(lrp.parent)
        # should skip edge node, inner_ls link to edge and central lr
        if lr is None or lr.chassis is not None:
            continue
        return lr

def _is_to_ext_lsr(lsr, out):
    lrp_set = entity_zoo.get('lrp')
    lsp_set = entity_zoo.get('lsp')
    lsr_outport = lrp_set[lsr.outport]
    lsp = lsp_set[lsr_outport.peer]
    if lsp.parent == out.name:
        return True
    return False

def find_lsr_in_lr(lr, is_edge = False, out = None):
    lsr_set = entity_zoo.get('lsr')
    if lsr_set is None:
        raise TPToolErr("cannot found any lsr")

    lsr_array = []
    for lsr in lsr_set.values():
        if lsr.parent == lr.name:
            lsr_array.append(lsr)
    if len(lsr_array) == 0:
        raise TPToolErr("lr %s has no lsr", lr.name)
    if not is_edge:
        return lsr_array

    # edge's lsr
    if len(lsr_array) != 2:
        raise TPToolErr("lr %s has not lsr", lr.name)
    alsr, blsr = lsr_array[:]
    if _is_to_ext_lsr(alsr, out) == True and _is_to_ext_lsr(blsr, out) == False:
        to_ext_lsr = alsr
        to_virt_lsr = blsr
    elif _is_to_ext_lsr(alsr, out) == False and _is_to_ext_lsr(blsr, out) == True:
        to_ext_lsr = blsr
        to_virt_lsr = alsr
    else:
        raise TPToolErr("cannot distinguish to_ext and to_virt lsr")
    return [to_virt_lsr, to_ext_lsr]

def new_entity_name(etype, prefix_name):
    i = 1
    prefix_name = '{}_{}'.format(etype, prefix_name)
    while True:
        name = "tp_{}{}".format(prefix_name, i)
        i += 1
        if entity_zoo.has_key(etype) and entity_zoo[etype].has_key(name):
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

def _cmd_new_patchport(ls_name, portname):
    cmd = "tpctl lsp add {} {} 255.255.255.255 ff:ff:ff:ff:ff:ee".format(
                    ls_name, portname)
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


def _find_lrp_by_vip(vip):
    lrp_set = entity_zoo.get('lrp')
    if lrp_set is None:
        return None
    for lrp in lrp_set.values():
        if lrp.ip == vip:
            return lrp


def _gen_lrp_property(ip_int, prefix):
    lrp_set = entity_zoo.get('lrp')
    mprefix = 32 - prefix
    max_ip_int = ((ip_int >> mprefix) << mprefix) + (0xffffffff >> prefix)
    min_ip_int = ((ip_int >> mprefix) << mprefix)
    for ip_int in xrange(max_ip_int-1, min_ip_int, -1):
        conflict = False
        for lrp in lrp_set.values():
            if lrp.ip_int == ip_int:
                conflict = True
                break
        if conflict is False:
            ip = socket.inet_ntoa(struct.pack('I',socket.htonl(ip_int)))
            return ip, prefix
    raise TPToolErr("cannot found a lrp due to ip confict")


def _add_ecmp_road(central_lr, inner_ls, edge, outside,
                   central_lsr, edge_to_virt_lsr,
                   edge_to_ext_lsr, vip, vip_prefix):
    lsp_set = entity_zoo.get('lsp')
    lrp_set = entity_zoo.get('lrp')

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
    tp_cmd_list.append(_cmd_new_patchport(out_ls_name, patchport))

    # create link command
    # lrp_cen_to_m is an exist lrp which link to a inner ls
    lrp_cen_to_m = lrp_set[central_lsr.outport]
    central_ip, central_prefix = _gen_lrp_property(lrp_cen_to_m.ip_int,
                                                   int(lrp_cen_to_m.prefix))
    tp_cmd_list.append(_cmd_new_link(central_lr.name, inner_ls_name,
                                     central_ip, central_prefix))

    # all edge_port(link to inner_ls has same ip and prefix)
    edge_port = lrp_set[edge_to_virt_lsr.outport]
    tp_cmd_list.append(_cmd_new_link(edge_lr_name, inner_ls_name,
                                     edge_port.ip, edge_port.prefix))

    tp_cmd_list.append(_cmd_new_link(edge_lr_name, out_ls_name,
                                     vip, vip_prefix))

    # create lsr command
    outport = '{}_to_{}'.format(edge_lr_name, inner_ls_name)
    tp_cmd_list.append(_cmd_new_lsr(edge_lr_name, edge_to_virt_lsr.ip,
                                    edge_to_virt_lsr.prefix,
                                    central_ip, outport))

    outport = '{}_to_{}'.format(edge_lr_name, out_ls_name)
    tp_cmd_list.append(_cmd_new_lsr(edge_lr_name, edge_to_ext_lsr.ip,
                                    edge_to_ext_lsr.prefix,
                                    edge_to_ext_lsr.next_hop, outport))

    # NOTE: this lsr should be add in last stage. once lsr was add then
    # traffic may be redirect to this edge node
    outport = '{}_to_{}'.format(central_lr.name, inner_ls_name)
    tp_cmd_list.append(_cmd_new_lsr(central_lr.name,
                                    central_lsr.ip, central_lsr.prefix,
                                    edge_port.ip, outport))

    print("tpctl will executes following commands")
    print('\n'.join(tp_cmd_list))
    is_execute = raw_input(("Please verify tpctl commands and press "
                            "yes to add an ecmp path:"))
    if is_execute == 'yes':
        ovs_add_patch_port(patchport, HOST_BR_INT, HOST_BR_PHY)
        ecmp_execute_cmds(tp_cmd_list[:len(tp_cmd_list) - 1],
                          cmd_final=tp_cmd_list[-1])
        print("Done")
    else:
        sys.exit(0)


def _init_ecmp_road(central_lr, vip, vip_prefix, virt_ip, virt_prefix,
                    inner_ip, inner_prefix, ext_gw):
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
    tp_cmd_list.append(_cmd_new_patchport(out_ls_name, patchport))

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
    tp_cmd_list.append(_cmd_new_link(central_lr.name, inner_ls_name,
                                     central_lr_ip, inner_prefix))

    # create lsr command
    outport = "{}_to_{}".format(edge_lr_name, out_ls_name)
    tp_cmd_list.append(_cmd_new_lsr(edge_lr_name, '0.0.0.0', 0,
                                    ext_gw, outport))

    outport = "{}_to_{}".format(edge_lr_name, inner_ls_name)
    tp_cmd_list.append(_cmd_new_lsr(edge_lr_name, virt_ip, virt_prefix,
                                    central_lr_ip, outport))

    outport = "{}_to_{}".format(central_lr.name, inner_ls_name)
    tp_cmd_list.append(_cmd_new_lsr(central_lr.name, '0.0.0.0', 0,
                                    inner_ip, outport))

    print("tpctl will executes following commands")
    print('\n'.join(tp_cmd_list))
    is_execute = raw_input(("Please verify tpctl commands and press "
                            "yes to init an ecmp path:"))
    if is_execute == 'yes':
        ovs_add_patch_port(patchport, HOST_BR_INT, HOST_BR_PHY)
        ecmp_execute_cmds(tp_cmd_list)
        print("Done")
    else:
        sys.exit(0)


def init_ecmp_road(vip, vip_prefix, virt_ip, virt_prefix,
                   inner_ip, inner_prefix, ext_gw):
    if is_ip_occupied(vip):
        raise TPToolErr("vip %s was occupied by other lsp/lrp" % vip)
    if is_chassis_is_edge():
        raise TPToolErr("chassis %s is an edge already" % system_id)
    lrp_set = entity_zoo.get('lrp', {})
    lsp_set = entity_zoo.get('lsp', {})
    lr_set = entity_zoo.get('LR')
    if lr_set is None or len(lr_set) != 1:
        raise TPToolErr("do not know the candidate LR-central")

    for lrp in lrp_set.values():
        if lrp.ip == vip or \
           lrp.ip == inner_ip or lrp.ip == ext_gw:
            raise TPToolErr("lrp %s has duplicate ip", lrp)

    for lsp in lsp_set.values():
        if lsp.ip == vip or \
           lsp.ip == inner_ip or lsp.ip == ext_gw:
            raise TPToolErr("lsp %s has duplicate ip", lsp)

    central_lr = lr_set.values()[0]
    _init_ecmp_road(central_lr, vip, vip_prefix, virt_ip, virt_prefix,
                    inner_ip, inner_prefix, ext_gw)


def _remove_ecmp_road(out, edge, inner, central_lr):
    outport_name = "{}_to_{}".format(central_lr.name, inner.name)
    lrp_set = entity_zoo.get('lrp')
    tp_cmd_list = []
    tp_cmd_list.append(_cmd_del_lr(edge.name))
    tp_cmd_list.append(_cmd_del_ls(inner.name))
    tp_cmd_list.append(_cmd_del_ls(out.name))

    found = False
    for lrp in lrp_set.values():
        if lrp.name == outport_name and lrp.parent == central_lr.name:
            found = True
            tp_cmd_list.append(_cmd_del_lrp(central_lr.name, lrp.name))
            break
    if found is False:
        raise TPToolErr("error in founding central LR lrp")

    lsr_set = entity_zoo.get('lsr')
    found = False
    for lsr in lsr_set.values():
        if lsr.outport == outport_name and lsr.parent == central_lr.name:
            found = True
            # NOTE: this lsr should be the first command which help to
            # redirect traffic to other edge
            tp_cmd_list.insert(0, _cmd_del_lsr(central_lr.name, lsr.name))
            break
    if found is False:
        raise TPToolErr("failed to found central LR's lsr(forward to edge)")

    patchport = find_ls_patchport(out)
    if patchport is None:
        raise TPToolErr("failed to search lr %s patchport", out.name)

    print("tpctl will executes following commands")
    print('\n'.join(tp_cmd_list))
    is_execute = raw_input(("Please verify tpctl commands and press "
                            "yes to remove a ecmp path:"))
    if is_execute == 'yes':
        ecmp_execute_cmds(tp_cmd_list[1:], cmd_first = tp_cmd_list[0])
        ovs_del_patch_port(patchport.name, HOST_BR_INT, HOST_BR_PHY)
        print("Done")
    else:
        sys.exit(0)


def remove_ecmp_road(vip):
    edges = find_all_edge_nodes()
    patchports = find_all_patchports()
    ls_lr_ls_list = find_ls_lr_ls(edges, patchports)
    prev_lr_central = None
    for out,edge,inner in ls_lr_ls_list:
        # sanity check central LR
        lr_central = find_central_LR(inner)
        if prev_lr_central is not None and prev_lr_central is not lr_central:
            raise TPToolErr("Get two central LR, %s  %s" %
                            (lr_central, prev_lr_central))
        prev_lr_central = lr_central

    if lr_central is None:
        raise TPToolErr("failed to search central lr")

    found = False
    lrp = _find_lrp_by_vip(vip)
    for out,edge,inner in ls_lr_ls_list:
        if edge.name == lrp.parent:
            if edge.chassis != system_id:
                raise TPToolErr("you cannot remove a edge in other host")
            found = True
            _remove_ecmp_road(out, edge, inner, lr_central)
            break
    if found is False:
        raise TPToolErr("failed to search ecmp path by using vip:%s" % vip)

def add_ecmp_road(vip, vip_prefix):
    if is_ip_occupied(vip):
        raise TPToolErr("vip %s was occupied by other lsp/lrp" % vip)
    if is_chassis_is_edge():
        raise TPToolErr("chassis %s is an edge already" % system_id)
    edges = find_all_edge_nodes()
    patchports = find_all_patchports()
    ls_lr_ls_list = find_ls_lr_ls(edges, patchports)
    prev_lr_central = None
    for out,edge,inner in ls_lr_ls_list:
        # sanity check central LR
        lr_central = find_central_LR(inner)
        if prev_lr_central is not None and prev_lr_central is not lr_central:
            raise TPToolErr("Get two central LR, %s  %s" %
                            (lr_central, prev_lr_central))
        prev_lr_central = lr_central

    # it take a assumption that all lsr in central_lr is similar(has
    # same ip,prefix,next_hop)
    central_lsr = find_lsr_in_lr(prev_lr_central)[0] # only get one
    out,edge,inner = ls_lr_ls_list[0] # only get the first path of edge route
    edge_to_virt_lsr, edge_to_ext_lsr = find_lsr_in_lr(edge, True, out)
    _add_ecmp_road(prev_lr_central, inner, edge, out,
                   central_lsr, edge_to_virt_lsr, edge_to_ext_lsr,
                   vip, vip_prefix)


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
    if system_id == "":
        raise TPToolErr("failed to get ovs system-id")

    if options.phy_br == 'br-int':
        raise TPToolErr("phy_br should not be a tuplenet bridge")
    try:
        cm.ovs_vsctl('get', 'bridge', options.phy_br, 'datapath_id')
    except TPToolErr:
        raise TPToolErr("please check if we have ovs bridge %s" % options.phy_br)

    chassis_set = entity_zoo.get('chassis')
    if chassis_set is None:
        raise TPToolErr("etcd side has no chassis list")
    if not chassis_set.has_key(system_id):
        raise TPToolErr("cannot found %s in chassis list" % system_id)

    try:
        tpctl_execute(['tpctl --help'])
    except TPToolErr as err:
        print(("failed to execute tpctl, please check if tpctl "
                "had been installed"))
        raise err

    try:
        tpctl_execute(['tpctl lr show'])
    except TPToolErr as err:
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
