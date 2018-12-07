import signal
from ctypes import cdll

PR_SET_PDEATHSIG = 1
class PrCtlError(Exception):
    pass

def on_parent_exit(signame):
    signum = getattr(signal, signame)
    def set_parent_exit_signal():
        ret = cdll['libc.so.6'].prctl(PR_SET_PDEATHSIG, signum)
        if ret != 0:
            raise PrCtlError('prctl failed with error code %s' % result)

    return set_parent_exit_signal
