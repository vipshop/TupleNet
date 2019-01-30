#!/usr/bin/python
from __future__ import print_function
import os
import sys, threading
import logging
import time
import struct
import socket
import random
from optparse import OptionParser
import ConfigParser
from multiprocessing.pool import ThreadPool

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ppparent_dir = os.path.dirname(os.path.dirname(parent_dir))
py_third_dir = os.path.join(ppparent_dir, 'py_third')
sys.path.append(parent_dir)
sys.path.append(py_third_dir)
from lcp import link_master as lm
from lcp.flow_common import table_note_dict
from lcp import flow_common


BASIC_SEC_NAME = 'basic'
THREAD_POOL_MAX_N = 100
WAIT_TRACE_TIMEOUT = 0
logger = None
TUPLENET_DIR = ''
UNKNOW_SYMBOL = "<UNKNOW>"
AUTO_DETECT_LOOP_ENV_NAME = 'DETECT_LOOP'
BATCH_NUM_ENV_NAME = 'BATCH_NUM'
wmaster = None
entity_zoo = {}

class TPObject:
    def __init__(self, name, properties):
        self.__setattr__('name', name)
        for k,v in properties.items():
            self.__setattr__(k, v)


    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def __getattr__(self, name):
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

def init_logger():
    global logger
    env = os.environ.copy()
    if env.has_key('LOGDIR'):
        log_type = logging.FileHandler(os.path.join(env['LOGDIR'], 'pkt-trace.log'))
    else:
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

def errprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def update_entity_data(add_pool, del_pool):
    if del_pool is not None:
        for etype,entity_dict in del_pool.items():
            if not entity_zoo.has_key(etype):
                continue
            for key, entity in entity_dict.items():
                key = key.split('/')[-1]
                entity_zoo[etype].pop(key)
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
    if wmaster == None:
        wmaster = lm.WatchMaster(etcd_endpoints, TUPLENET_DIR)
    data_type, add_pool, del_pool = wmaster.read_remote_kvdata()
    update_entity_data(add_pool, del_pool)

def _find_all_active_lsp_by_ls(ls_array):
    lsp_array = []
    for lsp in entity_zoo['lsp'].values():
        if lsp.chassis is None or \
           lsp.parent not in ls_array or \
           not entity_zoo['chassis'].has_key(lsp.chassis):
            continue
        lsp_array.append(lsp)
    return lsp_array

def select_random_src_target(ls_array, target_ip_array, batch_n):
    lsp_array = _find_all_active_lsp_by_ls(ls_array)
    # generate N * (N - 1 + M) detect pairs
    batch_n = min(len(lsp_array) * (len(lsp_array)+len(target_ip_array)-1),
                  batch_n)
    src_lsp_array = lsp_array
    target_array = lsp_array + target_ip_array

    n = 0
    pairs = {}
    while n < batch_n:
        src_lsp = random.choice(src_lsp_array)
        target = random.choice(target_array)
        k = str(src_lsp) + str(target)
        if pairs.has_key(k):
            continue
        pairs[k] = (src_lsp, target)
        n += 1
    return pairs

def _get_gw_mac(lsname):
    for lsp in entity_zoo['lsp'].values():
        if lsp.peer is None or \
           lsp.parent != lsname:
            continue
        return lsp.mac

def _convert_src_target2pkt(src_lsp, target):
    gw_mac = _get_gw_mac(src_lsp.parent)
    if isinstance(target, TPObject):
        if target.parent == src_lsp.parent:
            target_mac = target.mac
        else:
            target_mac = gw_mac
        target_ip = target.ip
    else:
        target_mac = gw_mac
        target_ip = target
    # do NOT construct icmp request packet, a lrp port will revise the icmp
    # requst packet into reply packet and send it back
    return construct_icmp_reply(src_lsp.mac, target_mac,
                                src_lsp.ip, target_ip)

def _find_incorrect_trace(result, expect_target_list):
    incorrect = []
    for i, traces in enumerate(result):
        last_trace = traces[-1]
        expect_target = expect_target_list[i]
        try:
            to_iface_id = last_trace.split(',')[3].split(':')[-1]

            if isinstance(expect_target, TPObject):
                if to_iface_id != expect_target.name:
                   incorrect.append((traces, expect_target))
            elif not entity_zoo['lsp'].has_key(to_iface_id):
                incorrect.append((traces, expect_target))
            elif entity_zoo['lsp'][to_iface_id].ip != expect_target:
                incorrect.append((traces, expect_target))
        except:
            incorrect.append((traces, expect_target))
    return incorrect

def _auto_detect_network(ls_array, target_ip_array, batch_n):
    inject_list = []
    expect_target_list = []
    pairs = select_random_src_target(ls_array, target_ip_array, batch_n)
    for src_lsp, target in pairs.values():
        packet = _convert_src_target2pkt(src_lsp, target)
        inject_list.append((src_lsp.name, packet))
        expect_target_list.append(target)

    result = run_pkt_trace_async(inject_list)
    incorrect = _find_incorrect_trace(result, expect_target_list)
    return incorrect

def auto_detect_network(auto_detect, n):
    batch_n = int(THREAD_POOL_MAX_N/10)
    env = os.environ.copy()
    if env.has_key(BATCH_NUM_ENV_NAME):
        try:
            batch_n = int(env[BATCH_NUM_ENV_NAME])
        except:
            pass

    batch_n = min(THREAD_POOL_MAX_N, batch_n)
    ls_array = []
    target_ip_array = []
    segments = auto_detect.split(',')
    for s in segments:
        try:
            socket.inet_aton(s)
        except:
            # not a ip address, we treat it as a name of LogicalSwitch
            ls_array.append(s)
        else:
            target_ip_array.append(s)
    for i in range(n):
        incorrect = _auto_detect_network(ls_array, target_ip_array,
                                         batch_n)
        if len(incorrect) != 0:
            errprint(incorrect)
            return
        sync_etcd_data(None)


def find_chassis_by_port(lport):
    lsp = entity_zoo['lsp'].get(lport)
    if lsp is None:
        return
    ch = entity_zoo['chassis'].get(lsp.chassis)
    return ch.name if ch is not None else None

def etcd_config_pkt_trace(lport, packet):
    chassis_id = find_chassis_by_port(lport)
    if chassis_id is None:
        raise Exception("cannot found logical port %s pin on a chassis" % lport)

    with etcd_config_pkt_trace.lock:
        if etcd_config_pkt_trace.cmd_id == 0:
            etcd_config_pkt_trace.cmd_id = int(time.time() * 100) & 0xffff
        else:
            # increase the cmd_id one by one to distinguish the command
            # NOTE the cmd_id may roll back from 0xffff to 0x0
            etcd_config_pkt_trace.cmd_id = \
                        (etcd_config_pkt_trace.cmd_id + 1) & 0xffff
        cmd_id = etcd_config_pkt_trace.cmd_id
    key = 'push/' + chassis_id + '/cmd/' + str(cmd_id)
    value = "cmd=pkt_trace,packet={},port={}".format(packet, lport)
    wmaster.lease_communicate(key, value, 10)
    return cmd_id
etcd_config_pkt_trace.cmd_id = 0 # init the static variable
etcd_config_pkt_trace.lock = threading.RLock()

def etcd_read_cmd_result(cmd_id):
    ret_data = wmaster.get_prefix(TUPLENET_DIR +
                        'communicate/cmd_result/{}/'.format(cmd_id))

    trace_info = []
    for value, meta in ret_data:
        key = meta.key.split('/')
        chassis_id = key[-1]
        seq_n = int(key[-2])
        trace_info.append((chassis_id, value, seq_n))
    trace_info = sorted(trace_info, key = lambda t:t[2])

    trace_path = []
    for chassis_id,path,_ in trace_info:
        table_id, datapath_id, src_port_id, dst_port_id, tun_src, iface_id = \
                                            parse_trace_path(path)
        trace_path.append({"table_id":table_id,
                           "datapath_id":datapath_id,
                           "src_port_id":src_port_id,
                           "dst_port_id":dst_port_id,
                           "tun_src":tun_src,
                           "chassis_id":chassis_id,
                           "output_iface_id":iface_id})

    #NOTE
    # we have to replace current datapath with previous datapath,
    # before entering TABLE_LRP_TRACE_EGRESS_OUT, the datapath had been
    # change into next pipeline datapath id
    for i in xrange(len(trace_path)):
        trace = trace_path[i]
        if int(trace["table_id"]) == flow_common.TABLE_LRP_TRACE_EGRESS_OUT and i > 0:
            prev_datapath = trace_path[i-1]["datapath_id"]
            trace["datapath_id"] = prev_datapath
    return trace_path

def find_datapath_by_id(datapath_id):
    for ls in entity_zoo['LS'].values():
        if ls.id == datapath_id:
            return ls

    for lr in entity_zoo['LR'].values():
        if lr.id == datapath_id:
            return lr

def find_port_by_id(datapath, port_id):
    if port_id == '0':
        return UNKNOW_SYMBOL
    if datapath.type == 'LS':
        for lsp in entity_zoo['lsp'].values():
            if lsp.parent != datapath.name:
                continue
            ip_int = struct.unpack("!L", socket.inet_aton(lsp.ip))[0]
            if str(ip_int & 0xffff) == port_id:
                return lsp.name
    elif datapath.type == 'LR':
        for lrp in entity_zoo['lrp'].values():
            if lrp.parent != datapath.name:
                continue
            ip_int = struct.unpack("!L", socket.inet_aton(lrp.ip))[0]
            if str(ip_int & 0xffff) == port_id:
                return lrp.name
    else:
        raise Exception("Unknow datapath type")
    return UNKNOW_SYMBOL

def parse_trace_path(trace_path):
    properties = trace_path.split(',')
    for p in properties:
        pname, pval = p.split('=')
        if pname == 'table_id':
            table_id = pval
            continue
        if pname == 'datapath_id':
            datapath_id = pval
            continue
        if pname == 'src_port_id':
            src_port_id = pval
            continue
        if pname == 'dst_port_id':
            dst_port_id = pval
            continue
        if pname == 'tun_src':
            ip_int = int(pval)
            tun_src = socket.inet_ntoa(struct.pack('I',socket.htonl(ip_int)))
            continue
        if pname == 'output_iface_id':
            iface_id = pval
    return table_id, datapath_id, src_port_id, dst_port_id, tun_src, iface_id

def run_pkt_trace(lport, packet):
    try:
        cmd_id = etcd_config_pkt_trace(lport, packet)
    except Exception as err:
        return ['%s'%err]

    time.sleep(WAIT_TRACE_TIMEOUT)
    trace_path = etcd_read_cmd_result(cmd_id)
    traces = []
    for trace in trace_path:
        datapath = find_datapath_by_id(trace["datapath_id"])
        if datapath is None:
            traces.append("<ERROR>")
            continue
        src_port_name = find_port_by_id(datapath, trace["src_port_id"])
        dst_port_name = find_port_by_id(datapath, trace["dst_port_id"])
        stage = table_note_dict[int(trace["table_id"])]
        trace = ("type:{},pipeline:{},from:{},to:{},stage:{},"
                 "chassis:{},output_iface_id:{}").format(
                        datapath.type, datapath.name,
                        src_port_name, dst_port_name,
                        stage, trace["chassis_id"],
                        trace['output_iface_id'])
        traces.append(trace)
    if len(traces) == 0:
        return ['error no traces']
    return traces

def run_pkt_trace_async(inject_info_list):
    pool = ThreadPool(processes = THREAD_POOL_MAX_N)
    async_result_list = []
    for inject_port, packet in inject_info_list:
        async_result_list.append(pool.apply_async(run_pkt_trace,
                                                  (inject_port, packet)))
    result = []
    for async_result in async_result_list:
        result.append(async_result.get())
    return result

def cal_checksum(header):
    header = struct.unpack("!10H", header)
    sum_num = 0
    reverse_str = ""
    for h in header:
        sum_num += h
        if sum_num > 0xffff:
            sum_num &= 0xffff
            sum_num += 1
    sum_num = "{:0>16b}".format(sum_num)
    for i in xrange(16):
        if sum_num[i] == "0":
            reverse_str += "1"
        else:
            reverse_str += "0"

    reverse = int(reverse_str, 2)
    header = struct.pack("!H", reverse)
    return header

def construct_icmp_request(src_mac, dst_mac, src_ip, dst_ip):
    return _construct_icmp(src_mac, dst_mac, src_ip, dst_ip, 'request')

def construct_icmp_reply(src_mac, dst_mac, src_ip, dst_ip):
    return _construct_icmp(src_mac, dst_mac, src_ip, dst_ip, 'reply')

def _construct_icmp(src_mac, dst_mac, src_ip, dst_ip, type):
    src_mac = src_mac.split(":")
    dst_mac = dst_mac.split(":")
    for i in xrange(6):
        src_mac[i] = int(src_mac[i], 16)
        dst_mac[i] = int(dst_mac[i], 16)
    src_ip = struct.unpack("!L", socket.inet_aton(src_ip))[0]
    dst_ip = struct.unpack("!L", socket.inet_aton(dst_ip))[0]
    src_mac = struct.pack("6B", src_mac[0], src_mac[1], src_mac[2],
                          src_mac[3], src_mac[4], src_mac[5])
    dst_mac = struct.pack("6B", dst_mac[0], dst_mac[1], dst_mac[2],
                          dst_mac[3], dst_mac[4], dst_mac[5])
    l2_proto = struct.pack("!H", 0x0800)
    eth_header = dst_mac + src_mac + l2_proto

    l3_head = struct.pack("8B", 0x45, 0x00, 0x00, 0x54,
                          0x00, 0x00, 0x40, 0x00)
    ttl = struct.pack("B", 9)
    protocol = struct.pack("B", 1)
    ip_checksum = struct.pack("BB", 0, 0)
    src_ip = struct.pack("!L", src_ip)
    dst_ip = struct.pack("!L", dst_ip)
    ip_checksum = cal_checksum(l3_head + ttl + protocol +
                               ip_checksum + src_ip + dst_ip)
    ip_header = l3_head + ttl + protocol + ip_checksum + src_ip + dst_ip

    if type == 'request':
        icmp_type = struct.pack("!H", 0x0800)
    elif type == 'reply':
        icmp_type = struct.pack("!H", 0x0)
    icmp_chksum = struct.pack("!H", 0x8510)
    icmp_id = struct.pack("!H", 0x5fbf)
    icmp_seq = struct.pack("!H", 0x0001)
    icmp_data = struct.pack("B", 1)
    for i in range(2, 57):
        icmp_data += struct.pack("B", i)
    icmp_payload = icmp_type + icmp_chksum + icmp_id + \
                   icmp_seq + icmp_data

    icmp_packet = eth_header + ip_header + icmp_payload

    icmp = struct.unpack("98B", icmp_packet)
    icmp_str = ""
    for i in icmp:
        icmp_str += "{:02x}".format(i)
    return icmp_str

def config_sanity_check(config):
    etcd_endpoints = lm.sanity_etcdhost(config.get(BASIC_SEC_NAME, 'endpoints'))
    prefix = config.get(BASIC_SEC_NAME, 'prefix')
    wait_time = config.getint(BASIC_SEC_NAME, 'wait_time')
    if not prefix.endswith('/'):
        raise Exception('prefix should be end with \'/\'')

    try:
        auto_detect = config.get(BASIC_SEC_NAME, 'auto_detect')
    except ConfigParser.NoOptionError:
        auto_detect = ""
    # auto_detect has high priority
    if auto_detect != "":
        return (etcd_endpoints, prefix, wait_time), auto_detect, None

    inject_info_list = []
    for section in config.sections():
        if section == BASIC_SEC_NAME:
            continue
        try:
            inject_port = config.get(section, 'port')
            try:
                header = config.get(section, 'header')
            except ConfigParser.NoOptionError:
                src_mac = config.get(section, 'src_mac')
                dst_mac = config.get(section, 'dst_mac')
                src_ip = config.get(section, 'src_ip')
                dst_ip = config.get(section, 'dst_ip')
                packet = construct_icmp_request(src_mac, dst_mac,
                                                src_ip, dst_ip)
            else:
                packet = header
            inject_info_list.append((inject_port, packet))
        except ConfigParser.NoSectionError:
            continue

    return (etcd_endpoints, prefix, wait_time), \
           auto_detect, inject_info_list

def init_env(config):
    global WAIT_TRACE_TIMEOUT, TUPLENET_DIR
    etcd_endpoints, path_prefix, wait_time = config
    TUPLENET_DIR = path_prefix
    WAIT_TRACE_TIMEOUT = wait_time
    sync_etcd_data(etcd_endpoints)

if __name__ == "__main__":
    usage = """usage: python %prog [options]
            --endpoints       the etcd cluster
            -j, --port        inject src port
            -p, --prefix      prefix path in etcd
            --src_mac         source macaddress of packet
            --dst_mac         destination macaddress of packet
            --src_ip          source ip address of packet
            --dst_ip          destination ip address of packet
            -d, --header      packet header and payload
            --wait_time       the time of waiting results of a tracing
            --auto_detect     the logical switch and ip you want to detect: --auto_detect LS1,LS2,100.1.1.1
                              program will randomly detect the the ports connectivity between LS1,LS2,100.1.1.1
            the config file like:

            [basic]
            endpoints=127.0.0.1:2379
            prefix=/tuplenet/
            wait_time=3

            [inject0]
            inject_port=lsp-portA
            src_mac=00:00:06:08:06:01
            src_ip=10.193.40.10
            dst_ip=10.193.40.1
            dst_mac=00:00:06:08:06:09

            [inject1]
            inject_port=lsp-portA
            src_mac=00:00:06:08:06:01
            src_ip=10.193.40.10
            dst_ip=10.193.40.7
            dst_mac=00:00:06:08:06:10
            """
    parser = OptionParser(usage)
    parser.add_option("-j", "--port", dest = "inject_port",
                      action = "store", type = "string",
                      default = "",
                      help = "which port you want inject packet in")
    parser.add_option("-p", "--prefix", dest = "path_prefix",
                      action = "store", type = "string",
                      default = "/tuplenet/", help = "etcd tuplenet prefix path")
    parser.add_option("--src_mac", dest = "src_mac",
                      action = "store", type = "string",
                      default = "", help = "source macaddress of packet")
    parser.add_option("--dst_mac", dest = "dst_mac",
                      action = "store", type = "string",
                      default = "", help = "destination macaddress of packet")
    parser.add_option("--src_ip", dest = "src_ip",
                      action = "store", type = "string",
                      default = "", help = "source ip address of packet")
    parser.add_option("--dst_ip", dest = "dst_ip",
                      action = "store", type = "string",
                      default = "", help = "destination ip address of packet")
    parser.add_option("-d", "--header", dest = "packet",
                      action = "store", type = "string",
                      default = "",
                      help = "packet header and payload, it should be hex")
    parser.add_option("--endpoints", dest = "endpoints",
                      action = "store", type = "string",
                      default = "localhost:2379",
                      help = " a comma-delimited list of machine addresses in the cluster")
    parser.add_option("--wait_time", dest = "wait_time",
                      action = "store", type = "int",
                      default = 3,
                      help = "the time of waiting results of a tracing")
    parser.add_option("-c", "--config", dest = "config_file",
                      action = "store", type = "string",
                      default = "",
                      help = "a file contains inject port, src_mac...")
    parser.add_option("--auto_detect", dest = "auto_detect",
                      action = "store", type = "string",
                      default = "",
                      help = "a batch of logicalswitch or ip, like: --auto_detect LS-A,10.1.1.1")

    (options, args) = parser.parse_args()

    init_logger()

    config = ConfigParser.RawConfigParser()
    if not options.config_file == "":
        config.read(options.config_file)
    else:
        config.add_section(BASIC_SEC_NAME)
        config.set(BASIC_SEC_NAME, 'endpoints', options.endpoints)
        config.set(BASIC_SEC_NAME, 'prefix', options.path_prefix)
        config.set(BASIC_SEC_NAME, 'wait_time', options.wait_time)
        config.set(BASIC_SEC_NAME, 'auto_detect', options.auto_detect)

        config.add_section('inject')
        config.set('inject', 'port', options.inject_port)
        config.set('inject', 'src_mac', options.src_mac)
        config.set('inject', 'src_ip', options.src_ip)
        config.set('inject', 'dst_mac', options.dst_mac)
        config.set('inject', 'dst_ip', options.dst_ip)
        if options.packet != "":
            config.set('inject', 'header', options.packet)

    basic_config, auto_detect, inject_info_list = config_sanity_check(config)
    init_env(basic_config)
    if auto_detect != "":
        try:
            n = int(os.environ.get(AUTO_DETECT_LOOP_ENV_NAME))
        except:
            n = 0xffffff
        auto_detect_network(auto_detect, n)
        sys.exit()

    result = run_pkt_trace_async(inject_info_list)
    for i, traces in enumerate(result):
        if i:
            print() # print a blank line to split tracepath segment
        print('\n'.join(traces[:]))

