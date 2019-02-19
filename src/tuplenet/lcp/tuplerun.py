#!/usr/bin/env python
import sys
import os
import time
import logging
import threading
from logging.handlers import RotatingFileHandler
import socket
import fcntl
import struct
import signal
import re

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ppparent_dir = os.path.dirname(os.path.dirname(parent_dir))
py_third_dir = os.path.join(ppparent_dir, 'py_third')
sys.path = [parent_dir, ppparent_dir, py_third_dir] + sys.path
import lflow
import commit_ovs as cm
import logicalview as lgview
import state_update
import tentacle
import tuplesync
import link_master as lm
from optparse import OptionParser
from pyDatalog import pyDatalog
from tp_utils import run_env, pipe
import syscmd
import version

logger = None
extra = run_env.get_extra()
entity_zoo = lgview.get_zoo()

def handle_exit_signal(signum, frame):
    logger.info('receive signum:%s', signum)
    try:
        clean_env(extra, 0)
    except Exception as err:
        logger.warning("error in clearning environment, err:%s", err)
    logger.info('Exit tuplenet')
    sys.exit(0)

def killme():
    os.kill(os.getpid(), signal.SIGTERM)


def clean_env(extra, ret):
    if os.path.exists(extra['flock']):
        os.remove(extra['flock'])
    if extra.has_key('lm'):
        extra['lm'].stop_all_watches()
    pipe.destory_runtime_files()

def get_if_ip(ifname_list = ['eth0', 'br0']):
    for ifname in ifname_list:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ip = socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915,
                                      struct.pack('256s', ifname[:15]))[20:24])
            return ip
        except Exception as err:
            logger.info('skip %s, failed get the ip address', ifname)
            continue

def write_pid_into_file(pid_lock_file):
    with open(pid_lock_file, 'w+') as fd:
        try:
            fd.write(str(os.getpid()))
        except IOError:
            raise IOError('failed to write pid into %s', pid_lock_file)
        extra['flock'] = pid_lock_file

def check_single_instance():
    current_file_name = os.path.realpath(__file__).split('/')[-1]
    pid_lock_file = os.path.join(extra['options']['TUPLENET_RUNDIR'],
                                 current_file_name + '.pid')
    if os.path.exists(pid_lock_file):
        with open(pid_lock_file, 'r') as fd:
            pid = int(fd.read())
            try:
                os.kill(pid, signal.SIGKILL)
                logger.warning('kill the running instance')
            except OSError as err:
                logger.info('the previous may hit some issue and exit without '
                            'clean the environment')
    write_pid_into_file(pid_lock_file)

def _correct_sysctl_config(kv):
    try:
        for k,v in kv.items():
            current_v = syscmd.sysctl_read(k)
            if current_v != v:
                syscmd.sysctl_write(k, v)
    except syscmd.SyscmdErr as err:
        logger.warning("failed to write sysctl config, err:%s", err)
        return False
    return True

def create_watch_master(hosts, prefix, local_system_id):
    extra['lm'] = lm.WatchMaster(lm.sanity_etcdhost(hosts),
                                 prefix, local_system_id)

def init_env(options):
    signal.signal(signal.SIGINT, handle_exit_signal)
    signal.signal(signal.SIGTERM, handle_exit_signal)
    signal.signal(signal.SIGQUIT, handle_exit_signal)

    pipe.create_runtime_folder()
    check_single_instance()

    system_id = cm.system_id()
    if system_id is None or system_id == "":
        logger.error('openvswitch has no chassis id')
        killme()

    extra['system_id'] = system_id
    logic = pyDatalog.Logic(True)
    extra['logic'] = logic

    br_int_mac = cm.build_br_integration()
    extra['options']['br-int_mac'] = br_int_mac
    if extra['options'].has_key('ENABLE_UNTUNNEL'):
        config = {'net.ipv4.conf.all.rp_filter':'0'}
        config['net.ipv4.ip_forward'] = '1'
        config['net.ipv4.conf.br-int.rp_filter'] = '0'
        config['net.ipv4.conf.br-int.forwarding'] = '1'
        if _correct_sysctl_config(config) is False:
            logger.error('failed to correct sysctl config:%s', config)
            killme()
        try:
            br = 'br-int'
            syscmd.network_ifup(br)
            logger.info('ifup the interface %s', br)
        except Exception as err:
            logger.error('failed to ifup %s interface, err:', br, err)
            killme()

    +lgview.local_system_id(system_id)
    lflow.init_build_flows_clause(extra['options'])

    try:
        cm.insert_ovs_ipfix()
        cm.set_tunnel_tlv()
        create_watch_master(options.host, options.path_prefix, system_id)
    except Exception as err:
        logger.error("hit error in init_env, err:%s", err)
        killme()

def update_chassis(interface_list):
    if re.match(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$", interface_list[0]):
        host_ip = interface_list[0]
    else:
        host_ip = get_if_ip(interface_list)
    if host_ip is None:
        logger.error('cannot get a valid ip for ovs tunnel')
        killme()
    logger.info('consume %s as tunnel ip', host_ip)
    wmaster = extra['lm']
    key = 'chassis/{}'.format(extra['system_id'])
    value = 'ip={},tick={}'.format(host_ip, int(time.time()))
    ret = wmaster.put_entity_view(key, value)
    if ret == 0:
        raise Exception("error in updating chassis")
    logger.info("update local system-id %s to remote etcd", extra['system_id'])

def run_monitor_thread():
    extra['lock'] = threading.Lock()
    logger.info("start a monitor thread")
    mon_ovsdb_thread = cm.start_monitor_ovsdb(entity_zoo, extra)
    start_time = time.time()
    while True:
        # we have to wait here, because sometimes
        # python may hangs on Popen ovsdb-client.
        # TODO we should figure out the root cause
        if time.time() - start_time > 5:
            logger.error("tuplenet hangs on starting ovsdb-client")
            killme()
        with extra['lock']:
            if extra.has_key('ovsdb-client'):
                break;
        time.sleep(0.1)
        logger.info("waitting for starting ovsdb-client")
    extra['mon_ovsdb_thread'] = mon_ovsdb_thread

def run_arp_update_thread():
    logger.info("start a arp update thread")
    arp_update_thread = state_update.start_monitor_pkt_controller_tunnel(entity_zoo, extra)
    extra['arp_update_thread'] = arp_update_thread

def run_debug_thread():
    logger.info("start debug thread")
    debug_thread = tentacle.start_monitor_debug_info(entity_zoo, extra)
    extra['debug_thread'] = debug_thread

def check_monitor_thread():
    mon_ovsdb_thread = extra['mon_ovsdb_thread']
    arp_update_thread = extra['arp_update_thread']
    debug_thread = extra['debug_thread']
    if not mon_ovsdb_thread.isAlive():
        logger.warning("mon_ovsdb_thread dead, try to restart it")
        run_monitor_thread()

    if not arp_update_thread.isAlive():
        logger.warning("arp_update_thread dead, try to restart it")
        run_arp_update_thread()

    if not debug_thread.isAlive():
        logger.warning("debug_thread dead, try to restart it")
        run_debug_thread()


def run_main(interval):
    last_refresh_time = 0
    while True:
        if time.time() - last_refresh_time < interval:
            time.sleep(0.1)
            continue
        else:
            last_refresh_time = time.time()

        check_monitor_thread()
        try:
            tuplesync.update_logical_view(entity_zoo, extra)
        except Exception as err:
            logger.exception("main process hit error, err:%s", err)


def init_logger(log_dir, log_level = logging.DEBUG):
    global logger

    format_type = '%(asctime)s.%(msecs)03d %(levelname)s %(process)d %(filename)s[line:%(lineno)d]: %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(format_type, datefmt)
    logger = logging.getLogger('')
    logger.setLevel(log_level)
    extra['log_dir'] = log_dir
    if log_dir != "":
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
            except Exception as e:
                print "can not create dir %s, err:%s" % (log_dir, str(e))
                sys.exit(1)

        # config regular and warning log path
        log_path = log_dir + '/tuplenet.log'
        rotate_handler = RotatingFileHandler(log_path, maxBytes = 2000 * 1024 * 1024,
                                             backupCount = 5)
        rotate_handler.setFormatter(formatter)
        logger.addHandler(rotate_handler)

        # config warning log path, output warn/error log into another file
        log_path = log_dir + '/tuplenet_warn.log'
        rotate_handler = RotatingFileHandler(log_path, maxBytes = 2000 * 1024 * 1024,
                                             backupCount = 5)
        rotate_handler.setFormatter(formatter)
        rotate_handler.setLevel(logging.WARN)
        logger.addHandler(rotate_handler)

    else:
        console = logging.StreamHandler();
        console_formater = logging.Formatter(format_type, datefmt)
        console.setFormatter(console_formater)
        logger.addHandler(console)


def main():
    usage = """usage: python %prog [options]
            -f, --interface        tunnel interface
            -l, --log              log dir path
            -i, --interval         ovs update interval
            -p, --prefix           etcd tuplenet prefix path
            -a, --host             etcd host
            -v, --version          the version of tuplenet"""
    parser = OptionParser(usage)
    parser.add_option("-f", "--interface", dest = "interface",
                      action = "store", type = "string",
                      default = "eth0,br0",
                      help = "interfaces for tunnel, e.g. -f eth0 or -f 1.1.1.1")
    parser.add_option("-l", "--log", dest = "log_dir",
                      action = "store", type = "string",
                      default = "",
                      help = "specify log dir path")
    parser.add_option("-i", "--interval", dest = "interval",
                      action = "store", type = "int",
                      default = 1,
                      help = "specify ovs update interval")
    parser.add_option("-p", "--prefix", dest = "path_prefix",
                      action = "store", type = "string",
                      default = "/tuplenet/", help = "etcd tuplenet prefix path")
    parser.add_option("-a", "--host", dest = "host",
                      action = "store", type = "string",
                      default = "localhost:2379", help = "etcd host address")
    parser.add_option("-v", "--version", dest = "version",
                      action = "store_true",
                      help = "print version of tuplenet")

    (options, args) = parser.parse_args()
    if options.version:
        print(version.__version__)
        print("git version:%s" % version.git_version)
        sys.exit(0)
    init_logger(options.log_dir)
    if options.interval < 1:
        logger.error('invalid interval')
        sys.exit(-1)
    interface_list = options.interface.split(',')
    logger.info("accept interface list:%s", interface_list)
    logger.info("accept log path:%s", options.log_dir)
    logger.info("accept interval:%s", options.interval)
    logger.info("accept etcd host:%s", options.host)
    logger.info("features config:%s", extra['options'])
    init_env(options)
    run_monitor_thread()
    run_arp_update_thread()
    run_debug_thread()
    update_chassis(interface_list)
    run_main(options.interval)


if __name__ == "__main__":
    main()

