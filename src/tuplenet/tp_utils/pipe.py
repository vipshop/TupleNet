import pickle
import os
import logging
import threading

if not os.environ.has_key('TUPLENET_RUNDIR'):
    RUNNING_ENV_PATH = '/var/run/tuplenet/'
else:
    RUNNING_ENV_PATH = os.environ['TUPLENET_RUNDIR'] + '/'
PKT_CONTROLLER_PIPE_PATH = RUNNING_ENV_PATH + 'pkt_controller_pipe'
DEBUG_PIPE_PATH = RUNNING_ENV_PATH + 'debug_pipe'

logger = logging.getLogger(__name__)
logger.info('RUNNING_ENV_PATH:%s', RUNNING_ENV_PATH)

plock = threading.Lock()

def write_pipe(obj, path):
    with open(path, 'wb') as fd:
        pickle.dump(obj, fd)

def write_pipe_cb(cb, path):
    with open(path, 'wb') as fd:
        obj = cb()
        pickle.dump(obj, fd)

def read_pipe(path):
    with open(path, 'rb') as fd:
        return pickle.load(fd)

def read_debug_pipe():
    return read_pipe(DEBUG_PIPE_PATH)

def create_pkt_controller_tunnel():
    pipe_fd = os.open(PKT_CONTROLLER_PIPE_PATH, os.O_RDONLY)
    logger.info("connect to pkt_controller")
    return pipe_fd

def create_runtime_folder():
    path = RUNNING_ENV_PATH
    is_exist = os.path.exists(path)
    try:
        if not is_exist:
            os.makedirs(path)
        if not os.path.exists(PKT_CONTROLLER_PIPE_PATH):
            os.mkfifo(PKT_CONTROLLER_PIPE_PATH)
        if not os.path.exists(DEBUG_PIPE_PATH):
            os.mkfifo(DEBUG_PIPE_PATH)
    except Exception as err:
        logger.error("failed to create tuplenet runtime files, err:%s", err)

def destory_runtime_files():
    try:
        if os.path.exists(PKT_CONTROLLER_PIPE_PATH):
            os.remove(PKT_CONTROLLER_PIPE_PATH)
        if os.path.exists(DEBUG_PIPE_PATH):
            os.remove(DEBUG_PIPE_PATH)
    except Exception as err:
        logger.warning("failed to clear tuplenet runtime files, err:%s", err)
