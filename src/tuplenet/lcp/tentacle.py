import time
import threading
import logging
import pyDatalog
from tp_utils import pipe
logger = logging.getLogger(__name__)

def monitor_debug_info(entity_zoo, extra):
    pyDatalog.Logic(extra['logic'])
    while True:
        try:
            data = pipe.read_debug_pipe()
        except Exception as err:
            logger.warning('failed to monitor income msg from %s', DEBUG_PIPE_PATH)
            time.sleep(0.1)
            continue
        opcode, msg = data
        if opcode == 'query_clause':
            with entity_zoo.lock:
                try:
                    answer = pyDatalog.pyDatalog.ask(msg)
                    if answer is None:
                        logger.info('clause %s has no result', msg)
                        continue

                    output = ""
                    for line in answer.answers:
                        output += str(line) + '\n'
                    logger.info('--------- clause %s result ----------', msg)
                    logger.info('\n%s', output)
                    logger.info('--------- clause %s end ----------', msg)
                except Exception as err:
                    logger.info('failed to query_clause, the clause is %s', msg)
        elif opcode == 'query_entity':
            with entity_zoo.lock:
                try:
                    logical_entity = entity_zoo.entity_set[msg]
                except Exception as err:
                    logger.info('failed to query_entity, the query entity is %s', msg)
                    continue
                logger.info('--------- entity %s result ----------', msg)
                logger.info('\n%s', logical_entity)
                logger.info('--------- entity %s end ----------', msg)
        else:
            logger.info('unsupport command type:%s', opcode)

def start_monitor_debug_info(entity_zoo, extra):
    t = threading.Thread(target = monitor_debug_info, args = (entity_zoo, extra))
    t.setDaemon(True)
    t.start()
    return t
