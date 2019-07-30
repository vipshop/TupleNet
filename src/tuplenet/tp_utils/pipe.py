import pickle
import socket
import os
import logging
import threading
import run_env

options = run_env.get_extra()['options']
RUNNING_ENV_PATH = options['TUPLENET_RUNDIR']
PKT_CONTROLLER_PIPE_PATH = os.path.join(RUNNING_ENV_PATH, 'pkt_controller_pipe')
DEBUG_PIPE_PATH = os.path.join(RUNNING_ENV_PATH, 'debug_pipe.sock')

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

def create_debug_pipe(addr, fn):
    MAX_DEBUG_RECV_BUF_SIZE = 10240
    def read_debug_pipe(param):
        sock.listen(1)
        while True:
            conn, _ = sock.accept()
            try:
                while True:
                    data = conn.recv(MAX_DEBUG_RECV_BUF_SIZE)
                    if len(data) == 0:
                        break
                    feedback = fn(param, data)
                    if feedback is not None:
                        conn.sendall(feedback)
                    else:
                        conn.sendall("ERROR")
            except Exception as err:
                logger.exception("hit error in debug pipe, err:%s", err)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(addr)
    return read_debug_pipe

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
