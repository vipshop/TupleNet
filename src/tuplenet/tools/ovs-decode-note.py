#!/usr/bin/python
import os
import sys
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
from lcp import flow_common

def get_flow_note_idx(flow):
    if 'note' not in flow:
        return None
    return int('0x'+flow.split('note:')[-1].split('.')[0], 16)

while True:
    try:
        flow = raw_input()
        idx = get_flow_note_idx(flow)
        if idx is None:
            print 'cannot decode flow:%s'%flow
            continue
        note = flow_common.flows_idx2note(idx)
        flow = flow.split('note')[0]
        flow = flow+"note:annotation({})".format(note)
        print flow
    except (EOFError):
        break

