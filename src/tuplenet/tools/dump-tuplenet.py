#!/usr/bin/env python
import sys
import os
import pickle
import socket
from optparse import OptionParser
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
from tp_utils import pipe

MAX_RECV_BUF = 102400

def write_debug_pipe(obj):
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(pipe.DEBUG_PIPE_PATH)
        data = pickle.dumps(obj)
        sock.sendall(data)
        data = sock.recv(MAX_RECV_BUF)
        print(data)
    except Exception as err:
        print("failed to get result from DEBUG socket, err:%s" % err)

if __name__ == "__main__":
    usage = """usage: python %prog [options]
            -t, --type        operation type
            -m, --message     operation message"""
    parser = OptionParser(usage)
    parser.add_option("-t", "--type", dest = "cmd_type",
                      action = "store", type = "string",
                      default = "",
                      help = "operation type, type candidate: query_clause,query_entity")
    parser.add_option("-m", "--message", dest = "msg",
                      action = "store", type = "string",
                      default = "",
                      help = "operation msg")

    (options, args) = parser.parse_args()
    if options.cmd_type == "" or options.msg == "":
        print('type and message are invalid, type:%s, message:%s'
              %(options.cmd_type, options.msg))
        sys.exit(-1)

    print('type:%s, message:%s'%(options.cmd_type, options.msg))
    write_debug_pipe((options.cmd_type, options.msg))
