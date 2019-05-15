import sys
import commands

class SyscmdErr(Exception):
    pass

def sysctl_read(path):
    cmd = 'sysctl %s' % path
    status, output = commands.getstatusoutput(cmd)
    if status != 0:
        raise SyscmdErr("failed to execute %s" % cmd)
    return output.split('=')[-1].strip()

def sysctl_write(path, value):
    cmd = 'sysctl -w %s=%s' % (path, value)
    status, output = commands.getstatusoutput(cmd)
    if status != 0:
        raise SyscmdErr("failed to execute %s" % cmd)
    if value != sysctl_read(path):
        raise SyscmdErr("failed to change sysctl value by using %s" % cmd)

def network_ifup(port):
    up_cmd = 'ip link set %s up' % port
    status, output = commands.getstatusoutput(up_cmd)
    if status != 0:
        raise SyscmdErr("failed to execute %s" % up_cmd)

    show_cmd = 'ip link show %s up' % port
    status, output = commands.getstatusoutput(show_cmd)
    if status != 0:
        raise SyscmdErr("failed to execute %s" % show_cmd)
    if output == '':
        raise SyscmdErr("failed to ifup interface by using %s" % up_cmd)

