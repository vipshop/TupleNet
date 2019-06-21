#!/usr/bin/env python
import sys
import os

def redefine_sys_path():
    system_site_packet64_path = '/usr/lib/python2.7/site-packages'
    system_site_packet_path = '/usr/lib64/python2.7/site-packages'
    file_path = os.path.realpath(__file__)
    file_path = file_path.split('/')
    file_path = '/'.join(file_path[0:-3])
    file_path += '/py_third'
    if system_site_packet64_path in sys.path:
        sys.path.remove(system_site_packet64_path)
    if system_site_packet_path in sys.path:
        sys.path.remove(system_site_packet_path)
    sys.path = [file_path] + sys.path
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(parent_dir)

redefine_sys_path()
import etcd3
from optparse import OptionParser

if __name__ == "__main__":
    parser = OptionParser("")
    parser.add_option("-a", "--host", dest = "host",
                      action = "store", type = "string",
                      default = "localhost:2379", help = "etcd host address")
    parser.add_option("-f", "--file", dest = "file",
                      action = "store", type = "string",
                      default = "data.txt",
                      help = "data file to construct tuplenet env")

    (options, args) = parser.parse_args()
    host_ip = options.host.split(':')[0]
    host_port = options.host.split(':')[1]
    etcd = etcd3.client(host_ip, host_port)

    fd = open(options.file, 'r')
    etcd_data = fd.readlines()
    fd.close()

    kv_array = []
    for i in xrange(0, len(etcd_data), 2):
        key = etcd_data[i].rstrip('\n')
        value = etcd_data[i+1].rstrip('\n')
        kv_array.append((key, value))

    for key,value in kv_array:
        etcd.put(key,value)
