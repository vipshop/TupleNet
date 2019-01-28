from pyDatalog import pyDatalog
import action
import match
from reg import *
from logicalview import *

pyDatalog.create_terms('Table, Priority, Priority1, Match, Action')
pyDatalog.create_terms('Action1, Action2, Action3, Action4, Action5')
pyDatalog.create_terms('Action6, Action7, Action8, Action9, Action10')
pyDatalog.create_terms('Match1, Match2, Match3, Match4, Match5')
pyDatalog.create_terms('trace_pipeline_start, trace_pipeline_end')
pyDatalog.create_terms('trace_pipeline_module')

# trace_pipeline_start will be inserted into each LS/LR's
# first ingress/egress stage
trace_pipeline_start(Priority, Match, Action) <= (
    (Priority == 100) &
    match.reg_flag(FLAG_TRACE, Match) &
    action.upload_trace(Action1) &
    action.resubmit_next(Action2) &
    (Action == Action1 + Action2)
    )

# default flow to resubmit to next table
trace_pipeline_start(Priority, Match, Action) <= (
    (Priority == 0) &
    match.match_none(Match) &
    action.resubmit_next(Action)
    )

# trace_pipeline_end will be inserted into each LS/LR's
# last ingress/egress stage
# the caller will add resumbit action
trace_pipeline_end(Priority, Match, Action) <= (
    (Priority == 100) &
    match.reg_flag(FLAG_TRACE, Match) &
    action.upload_trace(Action)
    )

# default flow, the caller will add resumbit action
trace_pipeline_end(Priority, Match, Action) <= (
    (Priority == 0) &
    match.match_none(Match) &
    # this push action just adding a dummy action,
    # you can replace it with other actions
    action.push(NXM_Reg(REG_DST_IDX), Action)
    )

trace_pipeline_module(Match, Action) <= (
    match.reg_flag(FLAG_TRACE, Match) &
    action.upload_trace(Action)
    )
