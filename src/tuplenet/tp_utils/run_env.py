import os
import logging
import socket
import struct

logger = logging.getLogger(__name__)

extra = {}
def get_extra():
    if len(extra) == 0:
        acquire_outside_env()
    return extra

def acquire_outside_env():
    extra['options'] = {}
    if not os.environ.has_key('TUPLENET_RUNDIR'):
        extra['options']['TUPLENET_RUNDIR'] = '/var/run/tuplenet/'
    else:
        extra['options']['TUPLENET_RUNDIR'] = os.path.join(os.environ['TUPLENET_RUNDIR'])

    if not os.environ.has_key('TUPLENET_OVSDB_PATH'):
        extra['options']['TUPLENET_OVSDB_PATH'] = '/var/run/openvswitch/db.sock'
    else:
        extra['options']['TUPLENET_OVSDB_PATH'] = os.environ['TUPLENET_OVSDB_PATH']

    # enable ONDEMAND by default
    if not os.environ.has_key('ONDEMAND') or \
       (os.environ.has_key('ONDEMAND') and os.environ['ONDEMAND'] == '1'):
        extra['options']['ONDEMAND'] = 1
        logger.info("enable ondemand feature")
    else:
        logger.info("disable ondemand feature")

    if not os.environ.has_key('ENABLE_REDIRECT') or \
       os.environ.has_key('ENABLE_REDIRECT') and os.environ['ENABLE_REDIRECT'] == '1':
        extra['options']['ENABLE_REDIRECT'] = 1
        logger.info("enable redirect feature")

    if os.environ.has_key('GATEWAY') and os.environ['GATEWAY'] == '1':
        extra['options']['GATEWAY'] = 1
        logger.info("enable gateway feature")

    if os.environ.has_key('ENABLE_UNTUNNEL') and os.environ['ENABLE_UNTUNNEL'] == '1':
        extra['options']['ENABLE_UNTUNNEL'] = 1
        logger.info("enable untunnel feature")

    if os.environ.has_key('HASH_FN') and \
       os.environ['HASH_FN'] in ['eth_src', 'symmetric_l4', 'symmetric_l3l4',
                                 'symmetric_l3l4+udp', 'nw_src', 'nw_dst']:
        extra['options']['HASH_FN'] = os.environ['HASH_FN']
    else:
        extra['options']['HASH_FN'] = 'nw_dst'
    logger.info("HASH_FN is %s", extra['options']['HASH_FN'])

    if os.environ.has_key('IPFIX_COLLECTOR'):
        try:
            # validate collector ip:port
            collector = os.environ['IPFIX_COLLECTOR']
            ip, port = collector.split(":", 1)
            socket.inet_aton(ip)
            p = int(port)
            if p <= 0 or p > 65535:
                raise Exception("collector port out of range")

            # validate sampling rate
            sampling_rate = int(os.getenv('IPFIX_SAMPLING_RATE', 64))
            if sampling_rate <=0 :
                raise Exception("sampling rate expected to be non-zero")

            # use host ip as domain id
            host_addr = socket.gethostbyname(socket.gethostname())

            extra['options']['IPFIX_CFG'] = {
                'collector': collector, "sampling_rate": sampling_rate,
                'domain_id': struct.unpack("!I", socket.inet_aton(host_addr))[0],
                'point_id': 0 }
        except Exception as e:
            logger.error('invalid ipfix setting {}'.format(e))
            raise e

def is_gateway_chassis():
    return extra['options'].has_key('GATEWAY')

