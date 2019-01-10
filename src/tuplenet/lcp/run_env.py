import os
import logging
from pyDatalog import pyDatalog

logger = logging.getLogger(__name__)

extra = {'accept_diff': False}
def get_extra():
    return extra

def acquire_outside_env():
    extra['options'] = {}
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

def is_gateway_chassis():
    return extra['options'].has_key('GATEWAY')

