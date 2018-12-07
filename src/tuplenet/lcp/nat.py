from pyDatalog import pyDatalog
import action
import match
from reg import *
from logicalview import *
import flow_common as fc

pyDatalog.create_terms('Table, Priority, Match, Action')
pyDatalog.create_terms('Action1, Action2, Action3, Action4, Action5')
pyDatalog.create_terms('Action6, Action7, Action8, Action9, Action10')
pyDatalog.create_terms('Match1, Match2, Match3, Match4, Match5')

pyDatalog.create_terms('lsnat_xlate_stage1, lsnat_xlate_stage2')
pyDatalog.create_terms('lunsnat_xlate_stage1, lunsnat_xlate_stage2')
pyDatalog.create_terms('ldnat_xlate_stage1, ldnat_xlate_stage2')
pyDatalog.create_terms('lundnat_xlate_stage1, lundnat_xlate_stage2')
pyDatalog.create_terms('LNAT1, LNAT2')


lunsnat_xlate_stage1(LR, Priority, Match, Action, State) <= (
    (Priority == 2) &
    lnat_data(LNAT1, LR, 'snat', UUID_LR, State1) &
    lnat_data(LNAT2, LR1, 'dnat', UUID_LR, State2) &
    (State == State1 + State2) & (State != 0) &
    (LNAT1[LNAT_XLATE_IP] == LNAT2[LNAT_XLATE_IP]) &
    (LNAT1[LNAT_IP] == LNAT2[LNAT_IP]) &
    (LNAT1[LNAT_PREFIX] == 32) & (LNAT2[LNAT_PREFIX] == 32) &
    match.ip_proto(Match1) &
    match.ip_dst(LNAT1[LNAT_XLATE_IP], Match2) &
    (Match == Match1 + Match2) &
    action.mod_nw_dst(LNAT1[LNAT_IP], Action1) &
    action.resubmit_next(Action2) &
    (Action == Action1 + Action2)
    )

lunsnat_xlate_stage1(LR, Priority, Match, Action, State) <= (
    (Priority == 1) &
    lnat_data(LNAT, LR, 'snat', UUID_LR, State) & (State != 0) &
    match.ip_proto(Match1) &
    match.ip_dst(LNAT[LNAT_XLATE_IP], Match2) &
    (Match == Match1 + Match2) &
    action.unsnat(fc.TABLE_LRP_INGRESS_UNSNAT_STAGE2, Action)
    )

lunsnat_xlate_stage1(LR, Priority, Match, Action, State) <= (
    (Priority == 0) &
    lr_array(LR, UUID_LR, State) & (State != 0) &
    match.match_none(Match) &
    action.resubmit_next(Action)
    )

lunsnat_xlate_stage2(LR, Priority, Match, Action, State) <= (
    (Priority == 0) &
    lr_array(LR, UUID_LR, State) & (State != 0) &
    match.match_none(Match) &
    action.resubmit_next(Action)
    )

lsnat_xlate_stage1(LR, Priority, Match, Action, State) <= (
    lnat_data(LNAT, LR, 'snat', UUID_LR, State) & (State != 0) &
    (Priority == LNAT[LNAT_PREFIX] + 1) &
    match.ip_proto(Match1) &
    match.ip_src_prefix(LNAT[LNAT_IP], LNAT[LNAT_PREFIX], Match2) &
    (Match == Match1 + Match2) &
    action.load(1, NXM_Reg(REG_FLAG_IDX, FLAG_NAT_BIT_IDX,
                           FLAG_NAT_BIT_IDX), Action1) &
    action.snat(LNAT[LNAT_XLATE_IP], fc.TABLE_LRP_EGRESS_SNAT_STAGE2 ,Action2) &
    (Action == Action1 + Action2)
    )

lsnat_xlate_stage1(LR, Priority, Match, Action, State) <= (
    (Priority == 0) &
    lr_array(LR, UUID_LR, State) & (State != 0) &
    match.match_none(Match) &
    action.resubmit_next(Action)
    )

lsnat_xlate_stage2(LR, Priority, Match, Action, State) <= (
    (Priority == 1) &
    lnat_data(LNAT, LR, 'snat', UUID_LR, State) & (State != 0) &
    match.reg_flag(FLAG_NAT, Match1) &
    match.ip_proto(Match2) &
    match.ip_src(LNAT[LNAT_XLATE_IP], Match3) &
    (Match == Match1 + Match2 + Match3) &
    action.mod_dl_src(LNAT[LNAT_XLATE_MAC], Action1) &
    action.resubmit_next(Action2) &
    (Action == Action1 + Action2)
    )

lsnat_xlate_stage2(LR, Priority, Match, Action, State) <= (
    (Priority == 0) &
    lr_array(LR, UUID_LR, State) & (State != 0) &
    match.match_none(Match) &
    action.resubmit_next(Action)
    )


ldnat_xlate_stage1(LR, Priority, Match, Action, State) <= (
    lnat_data(LNAT, LR, 'dnat', UUID_LR, State) & (State != 0) &
    (LNAT[LNAT_PREFIX] == 32) & # the dnat ip range should be 1
    (Priority == LNAT[LNAT_PREFIX] + 1) &
    match.ip_proto(Match1) &
    match.ip_dst(LNAT[LNAT_XLATE_IP], Match2) &
    (Match == Match1 + Match2) &
    action.load(1, NXM_Reg(REG_FLAG_IDX, FLAG_NAT_BIT_IDX,
                           FLAG_NAT_BIT_IDX), Action1) &
    action.dnat(LNAT[LNAT_IP], fc.TABLE_LRP_INGRESS_DNAT_STAGE2 ,Action2) &
    (Action == Action1 + Action2)
    )

ldnat_xlate_stage1(LR, Priority, Match, Action, State) <= (
    (Priority == 0) &
    lr_array(LR, UUID_LR, State) & (State != 0) &
    match.match_none(Match) &
    action.resubmit_next(Action)
    )

ldnat_xlate_stage2(LR, Priority, Match, Action, State) <= (
    (Priority == 0) &
    lr_array(LR, UUID_LR, State) & (State != 0) &
    match.match_none(Match) &
    action.resubmit_next(Action)
    )

lundnat_xlate_stage1(LR, Priority, Match, Action, State) <= (
    (Priority == 2) &
    lnat_data(LNAT1, LR, 'snat', UUID_LR, State1) &
    lnat_data(LNAT2, LR1, 'dnat', UUID_LR, State2) &
    (State == State1 + State2) & (State != 0) &
    (LNAT1[LNAT_XLATE_IP] == LNAT2[LNAT_XLATE_IP]) &
    (LNAT1[LNAT_IP] == LNAT2[LNAT_IP]) &
    (LNAT1[LNAT_PREFIX] == 32) & (LNAT2[LNAT_PREFIX] == 32) &
    match.ip_proto(Match1) &
    match.ip_src(LNAT1[LNAT_IP], Match2) &
    (Match == Match1 + Match2) &
    action.mod_nw_src(LNAT1[LNAT_XLATE_IP], Action1) &
    action.resubmit_next(Action2) &
    (Action == Action1 + Action2)
    )

lundnat_xlate_stage1(LR, Priority, Match, Action, State) <= (
    (Priority == 1) &
    lnat_data(LNAT, LR, 'dnat', UUID_LR, State) & (State != 0) &
    match.ip_proto(Match1) &
    match.ip_src(LNAT[LNAT_IP], Match2) &
    (Match == Match1 + Match2) &
    action.load(1, NXM_Reg(REG_FLAG_IDX, FLAG_NAT_BIT_IDX,
                           FLAG_NAT_BIT_IDX), Action1) &
    action.undnat(fc.TABLE_LRP_EGRESS_UNDNAT_STAGE2 ,Action2) &
    (Action == Action1 + Action2)
    )

lundnat_xlate_stage1(LR, Priority, Match, Action, State) <= (
    (Priority == 0) &
    lr_array(LR, UUID_LR, State) & (State != 0) &
    match.match_none(Match) &
    action.resubmit_next(Action)
    )

lundnat_xlate_stage2(LR, Priority, Match, Action, State) <= (
    (Priority == 1) &
    lnat_data(LNAT, LR, 'dnat', UUID_LR, State) & (State != 0) &
    match.reg_flag(FLAG_NAT, Match1) &
    match.ip_proto(Match2) &
    match.ip_src(LNAT[LNAT_XLATE_IP], Match3) &
    (Match == Match1 + Match2 + Match3) &
    action.mod_dl_src(LNAT[LNAT_XLATE_MAC], Action1) &
    action.resubmit_next(Action2) &
    (Action == Action1 + Action2)
    )

lundnat_xlate_stage2(LR, Priority, Match, Action, State) <= (
    (Priority == 0) &
    lr_array(LR, UUID_LR, State) & (State != 0) &
    match.match_none(Match) &
    action.resubmit_next(Action)
    )


