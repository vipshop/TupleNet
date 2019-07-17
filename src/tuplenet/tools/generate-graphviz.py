#!/usr/bin/env python
import sys
import os

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ppparent_dir = os.path.dirname(os.path.dirname(parent_dir))
py_third_dir = os.path.join(ppparent_dir, 'py_third')
sys.path.append(parent_dir)
sys.path.append(ppparent_dir)
sys.path.append(py_third_dir)
import etcd3
from optparse import OptionParser
etcd = None
g_path_prefix = ""
log_node_dict = {}
label_name_dict = {}
name_label_dict = {}
g_name_id = 0

def get_node_name():
    global g_name_id
    s = "ATPNODE%d"%g_name_id
    g_name_id += 1
    return s

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

class TPLogNode():
    def __init__(self, name, label, type, parent, properties, parent_path):
        self.name = name
        self.label = label
        self.type = type
        self.parent = parent
        self.properties = properties
        self.parent_path = parent_path
        self.children = {}

    def update_relation(self):
        if self.type == 'lsp' and \
           self.properties.has_key('chassis'):
            name = label_name_dict['chassis'].get(self.properties['chassis'],
                                                  "NONE")
            self.properties['chassis'] = name
        elif self.type == 'lsp' and \
             self.properties.has_key('peer'):
            name = label_name_dict['lrp'].get(self.properties['peer'], "NONE")
            self.properties['peer'] = name
        elif self.type == 'lrp' and \
             self.properties.has_key('peer'):
            name = label_name_dict['lsp'].get(self.properties['peer'], "NONE")
            self.properties['peer'] = name
        elif self.type == 'lsr' and \
             self.properties.has_key('outport'):
            name = label_name_dict['lrp'].get(self.properties['outport'], "NONE")
            self.properties['outport'] = name

    def add_child(self, child):
        self.children[child.name] = child
        if child.type == 'lsr' and \
           self.children.has_key(child.properties.get('outport')):
            self.children[child.properties['outport']].properties['lsr'] = child
        elif child.type == 'lrp':
            for _, c in self.children.items():
                if c.type != 'lsr':
                    continue
                if c.properties.get('outport') != child.name:
                    continue
                child.properties['lsr'] = c

    def properties_to_lable(self):
        s = ""
        for k,v in self.properties.items():
            # convert some properites' value from name to label
            v = name_label_dict.get(v, v)
            s +="|{}:{}".format(k,v)
        return s

    def to_graph(self):
        s = ""
        if self.type == 'LS':
            s = """subgraph cluster_{} {{
                        label="{}";
                        bgcolor="yellow";
                        penwidth=3;
                """.format(self.name, self.label)
        elif self.type == 'LR':
            s = """subgraph cluster_{} {{
                        label="{}";
                        bgcolor="green";
                        penwidth=3;
                """.format(self.name, self.label)

        for _,child in self.children.items():
            s += child.to_graph()

        if self.type == 'LS' or self.type == 'LR':
            s += "\n};"
        elif self.type == 'lsp' or self.type == 'lrp' or self.type == 'chassis':
            s = """{} [label="{{ {}{} }}"];\n""".format(
                        self.name, self.label,
                        self.properties_to_lable())
        return s + "\n"



def build_whole_map():
    data = etcd.get_prefix(g_path_prefix+'entity_view/')
    for value, meta in data:
        path_array = meta.key.split('/')
        node_label = path_array[-1]
        node_type = path_array[-2]
        node_name = get_node_name()
        if not label_name_dict.has_key(node_type):
            label_name_dict[node_type] = {}
        label_name_dict[node_type][node_label] = node_name
        name_label_dict[node_name] = node_label
        node_parent = path_array[-3]
        node_properties = parse_value(value)
        parent_path = '/'.join(path_array[:-2])
        log_node = TPLogNode(node_name, node_label, node_type,
                             node_parent, node_properties, parent_path)
        log_node_dict[meta.key] = log_node

    for _, log_node in log_node_dict.items():
        log_node.update_relation()
        parent_path = log_node.parent_path
        if log_node_dict.has_key(parent_path):
            log_node_dict[parent_path].add_child(log_node)

def show_whole_graph():
    graph_str = """digraph G{
          fontname = "Courier New"
          fontsize = 10
          node [ fontname = "Courier New", fontsize = 10, shape = "Mrecord" ];
          edge [ fontname = "Courier New", fontsize = 10, penwidth=5 ];


        """
    # show all node
    for _, log_node in log_node_dict.items():
        if log_node.type == 'LS' or \
           log_node.type == 'LR' or \
           log_node.type == 'chassis':
            node_graph = log_node.to_graph()
            graph_str += node_graph

    graph_str += "{rank=same;"
    for _, log_node in log_node_dict.items():
        if log_node.type == 'chassis':
            graph_str += log_node.name + ";"
    graph_str += "}\n"

    # show the links
    for _, log_node in log_node_dict.items():
        if log_node.type == 'lsp':
            if log_node.properties.has_key('peer'):
                graph_str += "{}->{}[color=yellow]\n".format(
                         log_node.name,
                         log_node.properties['peer'])
            if log_node.properties.has_key('chassis'):
                graph_str += "{}->{}[color=blue,style=dotted]\n".format(
                         log_node.name,
                         log_node.properties['chassis'])

        if log_node.type == 'lrp':
            route = ""
            if not log_node.properties.has_key('peer'):
                continue
            if log_node.properties.has_key('ip') and \
               log_node.properties.has_key('prefix'):
                route = "default:{}/{}\l".format(log_node.properties['ip'],
                                               log_node.properties['prefix'])

            lsr = log_node.properties.get('lsr')
            if lsr is not None:
                route += "{}:{}/{}".format(lsr.label, lsr.properties['ip'],
                                           lsr.properties['prefix'])
            graph_str += """{}->{}[color=green,label="{}"]\n""".format(
                         log_node.name,
                         log_node.properties['peer'],
                         route
                         )


    graph_str += "\n}\n"
    return graph_str


if __name__ == "__main__":
    parser = OptionParser("""
    this tool can dump etcd tuplenet data to generate
    graphviz data which can be parse by graphviz.
    You can paste graphviz data into textbox of http://www.webgraphviz.com/ """)
    parser.add_option("-a", "--host", dest = "host",
                      action = "store", type = "string",
                      default = "localhost:2379",
                      help = "etcd host address, default:ocalhost:2379")
    parser.add_option("-p", "--prefix", dest = "prefix",
                      action = "store", type = "string",
                      default = "/tuplenet/",
                      help = """prefix path of tuplenet data in etcd
                                default:/tuplenet/""")

    (options, args) = parser.parse_args()
    g_path_prefix = options.prefix
    host_ip = options.host.split(':')[0]
    host_port = options.host.split(':')[1]
    etcd = etcd3.client(host_ip, host_port)
    build_whole_map()
    graph_data = show_whole_graph()
    print(graph_data)

