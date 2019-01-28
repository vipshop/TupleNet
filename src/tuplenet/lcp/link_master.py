import time
import logging
import logging.handlers
import threading
import os
import random
import etcd3
import grpc

logger = logging.getLogger(__name__)
PREFIX_PATH_ENTITY_VIEW = 'entity_view/'
PREFIX_PATH_COMMUNICATE = 'communicate/'
PREFIX_PATH_COMMU_PUSH = PREFIX_PATH_COMMUNICATE + 'push/'
ENTITY_TYPE = 'TYPE'
LSP_MARK = 'lsp'
LRP_MARK = 'lrp'
LSR_MARK = 'lsr'
LNAT_MARK = 'lnat'
CHASSIS_MARK = 'chassis'
LS_MARK = 'LS'
LR_MARK = 'LR'
COMMUNICATE_CMD_MARK = 'cmd'
entity_type_list = [LSP_MARK, LRP_MARK, LSR_MARK, LNAT_MARK,
                    CHASSIS_MARK, LS_MARK, LR_MARK, COMMUNICATE_CMD_MARK]

WATCH_ID = 'watch_id'
WATCH_STATUS = 'watch_status'

g_fetch_data_cnt = 0

def parse_value(s):
    kv_set = {}
    kv_array = s.split(',')
    for kv in kv_array:
        kv = kv.split('=', 1)
        if len(kv) < 2:
            logger.warning("invald kv pair, kv:%s", kv)
            continue
        key = kv[0]
        value = kv[1]
        if key is None or value is None:
            logger.warning("invald kv pair,k:%s, v:%s", key, value)
            continue
        kv_set[key] = value

    return kv_set

def parse_key(key):
    try:
        key_type = key.split('/')[-2] # key's parent dir means type
        if key_type not in entity_type_list:
            return key, None
        return key, key_type
    except Exception as err:
        return key, None

class WatchMaster():
    def __init__(self, host_spec_array, prefix_path,
                 system_id = None, timeout = 3):
        self.last_ver = -1
        self.host_spec_array = host_spec_array
        self.system_id = system_id
        self.timeout = timeout
        # read entire data in first time
        self.read_remote_func = self.read_remote_entire_kvdata
        self.prefix_path = prefix_path
        self.default_watch_path = prefix_path + PREFIX_PATH_ENTITY_VIEW
        self.watch_lock = threading.RLock()
        self.watch_canceled = True
        self.watch_id_hash = {}
        self._previous_choose_id = -1
        self.reconn_master(3)

    def __del__(self):
        if not self.watch_canceled:
            self.stop_all_watches()

    # list etcd members
    # avoid dummy connection with etcd, reconnect etcd once
    # lost connection
    def _avoid_dummy_connection(self):
        try:
            for member in self.etcd.members:
                pass
        except Exception as err:
            logger.warning('failed to get member list, retry..')
            self.reconn_master()


    def reconn_master(self, retry_n = 0xffffffff):
        while True:
            if retry_n == 0:
                raise Exception('failed to connect remote etcd')

            if os.environ.has_key('RUNTEST'):
                # on testing mode, we consume etcd one by one
                logger.debug("we are in testing mode!")
                choose_id = (self._previous_choose_id + 1) % len(
                                                        self.host_spec_array)
                self._previous_choose_id = choose_id
            else:
                choose_id = random.randint(0, len(self.host_spec_array) - 1)
            host_spec = self.host_spec_array[choose_id]
            logger.info('try to use etcd %s:%s', host_spec.host, host_spec.port)

            # mark disable all watches first before connecting to next etcd
            self._disable_all_watches()
            self.etcd = etcd3.client(host_spec.host, host_spec.port,
                                     timeout = self.timeout)
            # printing member list test if cluster is in service
            logger.info('the etcd member dynamic list')
            logger.info('----------list start----------')
            try:
                for member in self.etcd.members:
                    logger.info('member name:%s, id:%s, peerURLs:%s',
                                member.name, member.id, member.peer_urls)
                logger.info('----------list end----------')
                self._op = {'put': self.etcd.put,
                            'get_prefix': self.etcd.get_prefix,
                            'lease': self.etcd.lease,
                            'delete': self.etcd.delete,
                            'add_watch_callback': self.etcd.add_watch_callback}
            except Exception as err:
                logger.warning('failed to get member list, retry..')
                time.sleep(1)
                continue
            finally:
                retry_n -= 1
            return

    def _etcd_operate(self, op, *args, **kwargs):
        while True:
            try:
                return self._op[op](*args, **kwargs)
            except etcd3.exceptions.Etcd3Exception as err:
                logger.warning("hit etcd exception, etcd side "
                               "may down, current revision: %u, err:%s",
                               self.last_ver, err)
                self.reconn_master()
                continue

    # would not retry and catch any exception
    def _delete_no_retry(self, key):
        key = self.prefix_path + key
        return self._op['delete'](key)

    def delete_entity_no_retry(self, key):
        key = PREFIX_PATH_ENTITY_VIEW + key
        return self._delete_no_retry(key)

    def put(self, key, *args, **kwargs):
        key = self.prefix_path + key
        return self._etcd_operate('put', key, *args, **kwargs)

    def get_prefix(self, key, *args, **kwargs):
        return self._etcd_operate('get_prefix', key, *args, **kwargs)

    def add_watch_callback(self, *args, **kwargs):
        return self._etcd_operate('add_watch_callback', *args, **kwargs)

    def put_entity_view_batch(self, kv_array):
        cnt = 0
        for key, value in kv_array:
            try:
                key = PREFIX_PATH_ENTITY_VIEW + key
                self.put(key, value)
                cnt += 1
            except Exception as err:
                logger.warning("failed to update kv, key:%s, value:%s",
                               key, value)
                continue
        return cnt

    def put_entity_view(self, key, value):
        try:
            key = PREFIX_PATH_ENTITY_VIEW + key
            self.put(key, value)
            return 1
        except Exception as err:
            logger.warning("failed to update kv, key:%s, value:%s, err:%s",
                           key, value, err)
            return 0

    def lease(self, key, value, ttl):
        key = self.prefix_path + key
        lease = self._etcd_operate('lease', ttl)
        return self._etcd_operate('put', key, value, lease)

    def lease_communicate(self, key, value, ttl):
        try:
            key = PREFIX_PATH_COMMUNICATE + key
            self.lease(key, value, ttl)
            return 1
        except Exception as err:
            logger.warning('failed to release kv, key:%s, value:%s, err:%s',
                           key, value, err)
            return 0

    def read_remote_kvdata(self):
        global g_fetch_data_cnt
        g_fetch_data_cnt += 1
        if g_fetch_data_cnt % 10 == 0:
            # read etcd members to avoid dummy connection
            # NOTE: in some circumstance, the tcp connection may become a
            # dummy connection if it sustaine a long time with etcd
            self._avoid_dummy_connection()

        try:
            data_type, add, remove = self.read_remote_func()
        except Exception as err:
            logger.warning('failed to read data from etcd, err:%s', err)
            return True if self.read_remote_func == self.read_remote_entire_kvdata else False, None, None

        # watch etcd path data, function ignores watching if it
        # had already watching those data
        self.run_default_watch()
        if add is None:
            # failed to get the data from etcd
            self.read_remote_func = self.read_remote_entire_kvdata
        else:
            self.read_remote_func = self.read_remote_incremental_kvdata

        if add is not None and len(add) > 0:
            logger.info("add entity:%s", add)
        if remove is not None and len(remove) > 0:
            logger.info("remove entity:%s", remove)
        return (data_type, add, remove)


    def read_remote_entire_kvdata(self):
        add_pool = {}
        version = -1
        logger.info('reading %s entire data from etcd...',
                    self.default_watch_path)
        try:
            data = self.get_prefix(self.default_watch_path)
        except Exception as err:
            logger.warning('failed to get_prefix %s from etcd, err:%s',
                            self.default_watch_path, str(err))
            return None, None, None

        for value, meta in data:
            version = max(meta.mod_revision, version)
            key, mark = parse_key(meta.key)
            if mark is None:
                logger.info("unknow key type:%s", key)
                continue

            value_kv_set = parse_value(value)
            value_kv_set[ENTITY_TYPE] = mark
            add_pool[key] = value_kv_set
            logger.debug('insert data, key:%s, value:%s', key, value_kv_set)

        self.last_ver = max(version, self.last_ver)
        pool = dispatch_pool(add_pool)
        # True means the data is entire data
        return True, pool, None

    def watch_callback(self, event):
        with self.watch_lock:
            if self.watch_canceled:
                return
            if isinstance(event, etcd3.exceptions.RevisionCompactedError):
                logger.info('etcd has compacted, the revision is %d now',
                             event.compacted_revision)
                # abandon the previous data we get, we should
                # get etcd whole data in next period
                self.last_ver = event.compacted_revision
                self.read_remote_func = self.read_remote_entire_kvdata
                self.entity_add_pool = None
                self.entity_del_pool = None
                self._disable_all_watches()
                return
            elif isinstance(event, grpc.RpcError):
                logger.warning('watch_callback grpc error:%s', event)
                self._disable_all_watches()
                return

            self.last_ver = max(event.mod_revision, self.last_ver)

            # we accept elements we acutually need
            key = event.key
            key, mark = parse_key(key)
            if mark is None:
                logger.warning("invalid key:%s, cannot know the type of kv", key)
                return

            if isinstance(event, etcd3.events.DeleteEvent):
                # entity_add_pool and entity_del_pool are used to
                # store operations and operations aggregation
                logger.debug('etcd side del data, key:%s', key)
                if self.entity_add_pool.has_key(key):
                    logger.debug('pop out from entity_add_pool')
                    self.entity_add_pool.pop(key)
                else:
                    logger.debug('add in entity_del_pool')
                    self.entity_del_pool[key] = {ENTITY_TYPE:mark}
                return
            else:
                logger.debug('etcd side put data, key:%s', key)
                if self.entity_del_pool.has_key(key):
                    logger.debug('pop out entity_del_pool')
                    self.entity_del_pool.pop(key)

            value = event.value
            value_kv_set = parse_value(value)
            value_kv_set[ENTITY_TYPE] = mark
            self.entity_add_pool[key] = value_kv_set
            logger.debug('insert data, key:%s, value:%s', key, value_kv_set)

    def _add_watch(self, watch_key, revision = None, init_f = None):
        watch_key = self.prefix_path + watch_key
        if self.watch_id_hash.has_key(watch_key):
            if self.watch_id_hash[watch_key][WATCH_STATUS] is not None:
                return self.watch_id_hash[watch_key][WATCH_ID]
            else:
                self._stop_watch(self.watch_id_hash[watch_key][WATCH_ID])
                logger.info('stop previous etcd watching %s', watch_key)
        key_prefix = etcd3.utils.increment_last_byte(
                        etcd3.utils.to_bytes(watch_key))
        try:
            with self.watch_lock:
                if init_f is not None:
                    init_f()
                watch_id = self.add_watch_callback(
                                key = watch_key,
                                callback = self.watch_callback,
                                range_end = key_prefix,
                                start_revision = revision)
                self.watch_canceled = False
        except Exception as err:
            logger.warning('failed to watch etcd, err:%s', err)
            return
        self.watch_id_hash[watch_key] = {WATCH_ID:watch_id, WATCH_STATUS:1}
        logger.info('watching etcd %s, revision:%s', watch_key, revision)
        return watch_id

    def _init_entity_pool(self):
        self.entity_add_pool = {}
        self.entity_del_pool = {}

    def _run_entity_watch(self):
        watch_id = self._add_watch(PREFIX_PATH_ENTITY_VIEW,
                                   self.last_ver + 1,
                                   self._init_entity_pool)
        return watch_id

    def _run_communicate_watch(self):
        if self.system_id is not None:
            watch_id = self._add_watch(PREFIX_PATH_COMMU_PUSH + self.system_id)
            return watch_id

    def run_default_watch(self):
        self._run_entity_watch()
        self._run_communicate_watch()

    def _stop_watch(self, watch_id):
        try:
            self.etcd.cancel_watch(watch_id)
        except etcd3.exceptions.Etcd3Exception as err:
            logger.info('hit etcd3 exceptions in canceling watching %s',
                        watch_id)
        return

    def stop_watch(self, watch_key):
        with self.watch_lock:
            watch_info = self.watch_id_hash.get(watch_key)
            if watch_info is None:
                logger.warning("cannot stop watching, cannot found "
                               "watch_key %s", watch_key)
                return
            self._stop_watch(watch_info[WATCH_ID])
            self.watch_canceled = True
            self.watch_id_hash.pop(watch_key, None)
            logger.info('stopped watching %s', watch_key)

    def stop_all_watches(self):
        logger.info("stop all watches")
        for watch_key, _ in self.watch_id_hash.items():
            self.stop_watch(watch_key)

    def _disable_all_watches(self):
        logger.info("disable all watches")
        # mark all watches, that we should disable those watch,
        # so before we recover watching we should stop them first in _add_watch
        for watch_key, _ in self.watch_id_hash.items():
            self.watch_id_hash[watch_key][WATCH_STATUS] = None
        # it tells the watch callback function do not to process any data
        self.watch_canceled = True

    def read_remote_incremental_kvdata(self):
        with self.watch_lock:
            # add_pool, del_pool may be none if self.entity_add_pool or
            # self.entity_del_pool is none
            add_pool, del_pool = dispatch_pool(self.entity_add_pool,
                                               self.entity_del_pool)
            self.entity_add_pool = {}
            self.entity_del_pool = {}
            # False means the data is incremental data
            return False, add_pool, del_pool

def dispatch_pool(*args):
    ret = []
    for pool in args:
        if pool is None:
            ret.append(None)
            continue
        dis_pool={}
        for key, value_kv_set in pool.items():
            if not dis_pool.has_key(value_kv_set[ENTITY_TYPE]):
                dis_pool[value_kv_set[ENTITY_TYPE]] = {}
            dis_pool[value_kv_set[ENTITY_TYPE]][key] = value_kv_set
        ret.append(dis_pool)
    return ret if len(ret) > 1 else ret[0]

class HostSpec():
    def __init__(self, host, port):
        self.host = host
        self.port = port

def sanity_etcdhost(s):
    hosts = s.split(',')
    host_spec = []
    try:
        for detail in hosts:
            if detail == "":
                continue
            host = detail.split(':')[0]
            port = detail.split(':')[1]
            host_spec.append(HostSpec(host, port))
        return host_spec
    except Exception as err:
        logger.warning("error etcd host address:%s", s)
        raise RuntimeError("error etcd host address:%s"%s)

