from __future__ import print_function
import os
import sys
import subprocess
import time
import struct
import socket
from optparse import OptionParser
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
from lcp.flow_common import table_note_dict
from lcp import flow_common

TUPLENET_DIR = ''
TUPLENET_ENTITY_VIEW_DIR = 'entity_view/'
UNKNOW_SYMBOL = "<UNKNOW>"
logical_view = None
etcd_env = os.environ.copy()
etcd_env['ETCDCTL_API'] = '3'
etcd_endpoints = "localhost:2379"

def errprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def call_popen(cmd, shell=False):
    child = subprocess.Popen(cmd, shell, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             env=etcd_env)
    output = child.communicate()
    if child.returncode:
        raise RuntimeError("error executing %s" % (cmd))
    if len(output) == 0 or output[0] is None:
        output = ""
    else:
        output = output[0].strip()
    return output

def call_prog(prog, args_list):
    cmd = [prog] + args_list
    return call_popen(cmd)

def etcdctl(*args):
    args = ['--endpoints={}'.format(etcd_endpoints)] + list(args)
    return call_prog("etcdctl", args)

def etcdctl_lease(key, value, ttl):
    key = TUPLENET_DIR + 'communicate/push/' + key
    lease_str = etcdctl('lease', 'grant', str(ttl))
    lease = lease_str.split(' ')[1]
    etcdctl('put', '--lease={}'.format(lease), key, value)

def split_hop_path(other_hop_path, prev_hop_tun_ip, prev_hop_src_port_id):
    trace_path = []
    total_trace_num = 0
    try_num = 0
    for _, path in other_hop_path.items():
        total_trace_num += len(path)
    while len(trace_path) != total_trace_num and try_num < 100:
        try_num += 1
        for chassis_id, path in other_hop_path.items():
            if len(path) == 0:
                continue
            # only need to check first trace path in each hop
            table_id = int(path[0]["table_id"])
            src_port_id = path[0]["src_port_id"]
            tun_src = path[0]["tun_src"]
            if tun_src != prev_hop_tun_ip or \
               (table_id != flow_common.TABLE_LSP_TRACE_EGRESS_IN and table_id != flow_common.TABLE_LRP_TRACE_INGRESS_OUT) or \
               src_port_id != prev_hop_src_port_id:
                continue

            final_idx = 0
            for i in xrange(len(path)):
                trace = path[i]
                if trace["tun_src"] != prev_hop_tun_ip:
                    break
                trace_path.append(trace)
                final_idx = i
                # check if next trace not in same hop
                if int(trace["table_id"]) == \
                        flow_common.TABLE_LSP_TRACE_INGRESS_OUT and \
                   i + 1 < len(path) and \
                   path[i+1]["src_port_id"] != trace["src_port_id"]:
                    break
            # del trace which had been inserted in trace_path
            other_hop_path[chassis_id] = path[final_idx+1:]

            prev_hop_tun_ip = get_ip_by_chassis(trace_path[-1]["chassis_id"])
            prev_hop_src_port_id = trace_path[-1]["src_port_id"]
    return trace_path

def get_ip_by_chassis(chassis_id):
    for i in xrange(0, len(logical_view), 2):
        if logical_view[i] != TUPLENET_ENTITY_VIEW_DIR + 'chassis/{}'.format(chassis_id):
            continue
        properties = logical_view[i + 1].split(',')
        for p in properties:
            p = p.split('=')
            pname = p[0]
            if pname == 'ip':
                ip = p[1]
                return ip

def find_chassis_by_port(lport):
    global logical_view
    chassis_id = None
    output = etcdctl('get', '--prefix', TUPLENET_ENTITY_VIEW_DIR)
    output = output.split('\n')
    if len(output) < 2:
        errprint('cannot get enough data from etcd')
        return
    for i in xrange(0, len(output), 2):
        key = output[i].split('/')
        if key[-2] != 'lsp' or key[-1] != lport:
            continue
        properties = output[i + 1].split(',')
        for p in properties:
            p = p.split('=')
            pname = p[0]
            if pname == 'chassis':
                chassis_id = p[1]
                break
    logical_view = output
    return chassis_id

def etcdctl_config_pkt_trace(lport, packet):
    chassis_id = find_chassis_by_port(lport)
    if chassis_id is None:
        errprint("cannot found logical port %s pin on a chassis" % lport)
        return
    cmd_id = int(time.time() * 100) & 0xffff
    key = chassis_id + '/cmd/' + str(cmd_id)
    value = "cmd=pkt_trace,packet={},port={}".format(packet, lport)
    etcdctl_lease(key, value, 10)
    return cmd_id

def etcdctl_read_cmd_result(cmd_id):
    output = etcdctl('get', '--prefix',
                     TUPLENET_DIR + 'communicate/cmd_result/{}/'.format(cmd_id))
    output = output.split('\n')
    if len(output) < 2:
        errprint("cannot read any cmd result from etcd")
        return []
    trace_info = []
    for i in xrange(0, len(output), 2):
        key = output[i].split('/')
        chassis_id = key[-1]
        seq_n = int(key[-2])
        value = output[i + 1]
        trace_info.append((chassis_id, value, seq_n))
    trace_info = sorted(trace_info, key = lambda t:(t[0], t[2]))

    first_hop_path = []
    other_hop_path = {}
    for i in xrange(len(trace_info)):
        chassis_id, trace_path, _ = trace_info[i]
        table_id, datapath_id, src_port_id, dst_port_id, tun_src = parse_trace_path(trace_path)
        # the first hop should get no tun_src
        if tun_src != '0.0.0.0':
            if not other_hop_path.has_key(chassis_id):
                other_hop_path[chassis_id] = []
            other_hop_path[chassis_id].append({"table_id":table_id,
                                               "datapath_id":datapath_id,
                                               "src_port_id":src_port_id,
                                               "dst_port_id":dst_port_id,
                                               "tun_src":tun_src,
                                               "chassis_id":chassis_id})
            continue
        first_hop_path.append({"table_id":table_id,
                               "datapath_id":datapath_id,
                               "src_port_id":src_port_id,
                               "dst_port_id":dst_port_id,
                               "tun_src":tun_src,
                               "chassis_id":chassis_id})

    first_hop_chassis = first_hop_path[0]["chassis_id"]
    prev_hop_src_port_id = first_hop_path[-1]["src_port_id"]
    prev_hop_tun_ip = get_ip_by_chassis(first_hop_chassis)
    trace_path = split_hop_path(other_hop_path, prev_hop_tun_ip,
                                prev_hop_src_port_id)
    trace_path = first_hop_path + trace_path
    #TODO
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
    for i in xrange(0, len(logical_view), 2):
        key = logical_view[i].split('/')
        if key[-2] != 'LR' and key[-2] != 'LS':
            continue
        datapath_name = logical_view[i]
        properties = logical_view[i + 1].split(',')
        for p in properties:
            p = p.split('=')
            pname = p[0]
            pval = p[1]
            if pname == 'id' and pval == datapath_id:
                return datapath_name

def find_port_by_id(datapath_name, port_id):
    if port_id == '0':
        return UNKNOW_SYMBOL
    for i in xrange(0, len(logical_view), 2):
        if not logical_view[i].startswith(datapath_name):
            continue
        if logical_view[i] == datapath_name:
            # the LS/LR, not lsp,lrp
            continue
        port_name = logical_view[i].split('/')[-1]
        properties = logical_view[i + 1].split(',')
        for p in properties:
            p = p.split('=')
            pname = p[0]
            pval = p[1]
            if pname == 'ip':
                ip_int = struct.unpack("!L", socket.inet_aton(pval))[0]
                if str(ip_int & 0xffff) == port_id:
                    return port_name

def parse_trace_path(trace_path):
    properties = trace_path.split(',')
    for p in properties:
        p = p.split('=')
        pname = p[0]
        pval = p[1]
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
    return table_id, datapath_id, src_port_id, dst_port_id, tun_src

def run_pkt_trace(lport, packet):
    cmd_id = etcdctl_config_pkt_trace(lport, packet)
    try:
        cmd_id = int(cmd_id)
    except Exception as err:
        errprint('config pkt trace cmd hit error')
        return
    time.sleep(5)
    trace_path = etcdctl_read_cmd_result(cmd_id)
    for trace in trace_path:
        datapath_name = find_datapath_by_id(trace["datapath_id"])
        src_port_name = find_port_by_id(datapath_name, trace["src_port_id"])
        dst_port_name = find_port_by_id(datapath_name, trace["dst_port_id"])
        entity_name = datapath_name.split('/')[-1]
        entity_type = datapath_name.split('/')[-2]
        stage = table_note_dict[int(trace["table_id"])]
        trace = "type:{},pipeline:{},from:{},to:{},stage:{},chassis:{}".format(
                        entity_type, entity_name, src_port_name, dst_port_name,
                        stage, trace["chassis_id"])
        print(trace)

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

def construct_icmp(src_mac, dst_mac, src_ip, dst_ip):
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

    icmp_type = struct.pack("!H", 0x0800)
    icmp_chksum = struct.pack("!H", 0x8510)
    icmp_id = struct.pack("!H", 0x5fbf)
    icmp_seq = struct.pack("!H", 0x0001)
    icmp_data = struct.pack("B", 1)
    for i in range(2, 57):
        icmp_data += struct.pack("B", i)
    icmp_payload = icmp_type + icmp_chksum + icmp_id + icmp_seq + icmp_data

    icmp_packet = eth_header + ip_header + icmp_payload

    icmp = struct.unpack("98B", icmp_packet)
    icmp_str = ""
    for i in icmp:
        icmp_str += "{:02x}".format(i)
    return icmp_str


if __name__ == "__main__":
    usage = """usage: python %prog [options]
            -j, --port        inject src port
            -p, --prefix      prefix path in etcd
            --src_mac         source macaddress of packet
            --dst_mac         destination macaddress of packet
            --src_ip          source ip address of packet
            --dst_ip          destination ip address of packet
            -d, --header      packet header and payload"""
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
    parser.add_option("--endpoints", "--endpoints", dest = "endpoints",
                      action = "store", type = "string",
                      default = "localhost:2379",
                      help = " a comma-delimited list of machine addresses in the cluster")

    (options, args) = parser.parse_args()
    if options.inject_port == "":
        errprint('invalid inject port, port:%s' % options.packet)
        sys.exit(-1)
    if not options.path_prefix.endswith('/'):
        errprint('prefix should be end with \'/\'')
        sys.exit(-1)


    TUPLENET_DIR = options.path_prefix
    TUPLENET_ENTITY_VIEW_DIR = TUPLENET_DIR + TUPLENET_ENTITY_VIEW_DIR
    etcd_endpoints = options.endpoints

    if options.packet != "":
        run_pkt_trace(options.inject_port, options.packet)
    else:
        if options.src_mac == "" or options.dst_mac == "" or \
           options.src_ip == "" or options.dst_ip == "":
            errprint('you have specify the inject packet data or header infor')
            sys.exit(-1)
        else:
            packet = construct_icmp(options.src_mac, options.dst_mac,
                                    options.src_ip, options.dst_ip)
            run_pkt_trace(options.inject_port, packet)
