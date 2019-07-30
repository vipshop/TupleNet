import time
import threading
import logging
import pyDatalog
import pickle
from tp_utils import pipe
logger = logging.getLogger(__name__)

def data_handler(entity_zoo, data):
    if len(data) == 0:
        return
    opcode, msg = pickle.loads(data)
    if opcode == 'query_clause':
        with entity_zoo.lock:
            try:
                answer = pyDatalog.pyDatalog.ask(msg)
                if answer is None:
                    logger.info('clause %s has no result', msg)
                    return

                output = ""
                for line in answer.answers:
                    output += str(line) + '\n'
                return output
            except Exception as err:
                logger.info('failed to query_clause, the clause is %s', msg)
    elif opcode == 'query_entity':
        with entity_zoo.lock:
            try:
                logical_entity = entity_zoo.entity_set[msg]
            except Exception as err:
                logger.info('failed to query_entity, the query entity is %s', msg)
                return
            return str(logical_entity)
    else:
        logger.info('unsupport command type:%s', opcode)

def monitor_debug_info(entity_zoo, extra):
    pyDatalog.Logic(extra['logic'])
    read_fn = pipe.create_debug_pipe(pipe.DEBUG_PIPE_PATH, data_handler)
    read_fn(entity_zoo)

def start_monitor_debug_info(entity_zoo, extra):
    t = threading.Thread(target = monitor_debug_info, args = (entity_zoo, extra))
    t.setDaemon(True)
    t.start()
    return t
