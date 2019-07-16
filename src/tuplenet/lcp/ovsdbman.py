import socket
import json
import time
import random
import string
import threading
import logging
logger = logging.getLogger(__name__)

def _randstr(rlen = 32):
    return ''.join(random.choice(string.ascii_uppercase) for x in range(rlen))

def parse_map(map_list):
    ret_map = {}
    if map_list[0] != 'map':
        return None
    for entry in map_list[1]:
        ret_map[entry[0]] = entry[1]
    return ret_map

class OVSDBErr(Exception):
    pass

def ovsdb_resp_handle(fn):
    def wrapper(resp, param):
        resp_err = resp.get('error')
        if resp_err is not None:
            logger.warning("monitor interface hit error: %s", resp['error'])
            raise OVSDBErr("monitor interface hit error: %s" % resp['error'])

        resp_result = resp.get('result')
        if resp_result is not None:
            data = resp_result
            return fn(data, param)
        resp_method = resp.get('method', "")
        resp_param = resp.get('params')
        if resp_method == "update" and resp_param is not None and \
           resp_param[0] is None:
            data = resp_param[1]
            return fn(data, param)
    return wrapper

def parse_mul_json(s):
    json_objs = []
    while True:
        try:
            (element, position) = parse_mul_json.decoder.raw_decode(s)
            json_objs.append(element)
            s = s[position:]
        except ValueError:
            break
    return json_objs
parse_mul_json.decoder = json.JSONDecoder()

class OvsdbMan():
    _MAX_RESP_TIMEOUT = 10
    _MAX_SILENCE_TIMEOUT = 3
    _MAX_RESP_BUF_SIZE = 1024 * 1024
    def __init__(self, socket_path):
        self.lock = threading.RLock()
        self.monitor_thread = None
        self.stop_event = False
        self.dbsock = None
        self.conn_param = socket_path
        self.handlers = {'echo':(self._echo_feedback, None),
                         'echo_feedback': (self._echo_skip, None)}
        self.sync_time = 0
        self.monitor_dict = {}
        self._rebuild_conn(3)

    def stop(self):
        if self.monitor_thread is not None and \
           self.monitor_thread.isAlive():
            self.stop_event = True;
        if self.dbsock is not None:
            self.dbsock.close()

    def _rebuild_conn(self, max_retry = 0xffffff):
        logger.info("try to build connection between ovsdb")
        while max_retry > 0:
            with self.lock:
                self.dbsock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.dbsock.settimeout(2)
                try:
                    self.dbsock.connect(self.conn_param)
                except Exception as err:
                    logger.warning("failed to connect ovsdb, err:%s", err)
                    max_retry -= 1
                    time.sleep(1)
                    continue
                else:
                    self.sync_time = time.time()
                    logger.info("ovsdb socket connected")
                    return
        raise OVSDBErr("failed to connnect ovsdb by using %s" %
                       str(self.conn_param))

    def _rebuild_monitor(self):
        logger.info("try to rebuild monitor")
        for monitor_id, (msg, fn, param) in self.monitor_dict.items():
            self._send(monitor_id, msg, fn, param)
            logger.info("monitor %s was rebuild", monitor_id)

    # ovsdb---(echo, id=None)-->client (if connecting a ptcp manager port)
    # client--(echo, id=echo_feedback)-->ovsdb
    # ovsdb---(echo, id=echo_feedback)-->client
    # client do recording
    def _echo_feedback(self, param0, param1):
        msg = {'method':'echo', 'id':'echo_feedback', 'params':[]}
        self._send(None, msg, self._echo_feedback, None)

    def _echo_skip(self, param0, param1):
        self.sync_time = time.time()

    def _send(self, id, msg, fn, param):
        with self.lock:
            if id is not None:
                self.handlers[id] = (fn, param)
            msg = json.dumps(msg)
            total_len = len(msg)
            total_sent = 0
            while total_sent < total_len:
                sent = self.dbsock.send(msg[total_sent:])
                if sent == 0:
                    raise OVSDBErr("socket connection broken")
                total_sent += sent

    def _rebuild_ovsdb(self):
        try:
            self._rebuild_conn()
            self._rebuild_monitor()
        except Exception as err:
            logger.warning("failed to rebuild connection to ovsdb, err:%s",
                           err)

    def _check_sync(self):
        if time.time() - self.sync_time > OvsdbMan._MAX_SILENCE_TIMEOUT:
            self._echo_feedback(None, None)

        if time.time() - self.sync_time < OvsdbMan._MAX_RESP_TIMEOUT:
            return
        logger.warning("ovsdb hit error, no echo sync for a long time")
        self._rebuild_ovsdb()


    def _run(self, init_fn, param):
        if init_fn is not None:
            init_fn(param)
        while True:
            # return to terminate this thread
            if self.stop_event is True:
                return

            try:
                response = self.dbsock.recv(
                                OvsdbMan._MAX_RESP_BUF_SIZE).decode('utf8')
            except socket.timeout as err:
                self._check_sync()
                continue
            except Exception as err:
                logger.warning("failed to read data from ovsdb, err:%s", err)
                self._rebuild_ovsdb()
                continue
            if response == "":
                self._rebuild_ovsdb()
                continue

            try:
                jresp_list = parse_mul_json(response)
            except Exception as err:
                logger.warning("failed to parse response to json, response:%s, err:%s",
                               response, err)
                continue

            for jresp in jresp_list:
                try:
                    rid = jresp['id']
                    handle_fn, handle_param = self.handlers.get(rid)
                    if handle_fn is None:
                        logger.info("has no handler for %s", rid)
                        continue
                    handle_fn(jresp, handle_param)
                except Exception as err:
                    logger.warning("hit error in processing ovsdb info, err:%s",
                                   err)
                    continue


    def run(self, init_fn = None, param = None):
        self.stop_event = False
        t = threading.Thread(target = self._run,
                             args=(init_fn, param))
        t.setDaemon(True)
        self.monitor_thread = t
        t.start()

    def _monitor(self, table, columns, fn, param):
        monitor_id = "monitor_{}_{}".format(table, _randstr())
        msg = {'method':'monitor', 'id':monitor_id,
               'params':['Open_vSwitch', None,
                         {table:[{'columns':columns,
                                  'select': {'initial': True, 'insert': True,
                                             'delete': True,'modify': True}
                                 }]}]}
        self.monitor_dict[monitor_id] = (msg, fn, param)
        # interface update event has no id, same handler to process updating of
        # interfaces in ovsdb
        self.handlers[None] = (fn, param)
        try:
            self._send(monitor_id, msg, fn, param)
        except OVSDBErr as err:
            logger.warning("failed to monitor %s[%s]", table, columns)
            return False
        return True

    def monitor_interfaces(self, hdl, param):
        return self._monitor('Interface', ['ofport', 'name',
                                           'external_ids', 'type'], hdl, param)

def parse_iface_record(record, op_type):
    if record is None:
        return None
    try:
        ofport = int(record['ofport'])
        port_name = str(record['name'])
        external_ids = parse_map(record['external_ids'])
        port_type = record['type']
    except Exception as err:
        logger.info("cannot parse iface record %s", record)
        return
    return [op_type, ofport, port_name, external_ids, port_type]

def iface_monitor_parse(data):
    iface_records = []
    ifaces = data['Interface']
    for _, record in ifaces.items():
        new_record = parse_iface_record(record.get('new'), 'new')
        old_record = parse_iface_record(record.get('old'), 'old')
        if new_record is None:
            iface_records.append((old_record))
        elif old_record is None:
            iface_records.append((new_record))
        else:
            iface_records.append((old_record))
            iface_records.append((new_record))
    return [x for x in iface_records if x is not None]

