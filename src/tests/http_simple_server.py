#!/usr/bin/env python
import sys
import SimpleHTTPServer
import SocketServer

PORT = 9979
if len(sys.argv) > 1:
    PORT = int(sys.argv[1])
Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
httpd = SocketServer.TCPServer(("", PORT), Handler)
httpd.serve_forever()
