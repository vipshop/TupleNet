from pyDatalog import pyDatalog
from logicalview import *
from reg import *
from flow_common import *
import match
import action
import tpstatic as st


pyDatalog.create_terms('Action1, Action2, Action3, Action4, Action5')
pyDatalog.create_terms('Match1, Match2, Match3')
pyDatalog.create_terms('Table, Priority, Match, Action')
pyDatalog.create_terms('UUID_LR_CHASSIS')
pyDatalog.create_terms('lsp_forward_packet')
pyDatalog.create_terms('lsp_judge_loopback')
pyDatalog.create_terms('lsp_pushout_packet')

# NOTE
# reg0: src_port_id
# reg1: dst_port_id
# reg4: the output ofport
# reg5: interim reg
# reg6: interim reg, store next LR's id
# reg7: interim reg, store next LR's port id
# reg10: flag


def init_lsp_egress_clause(way):

    lsp_judge_loopback(LS, Priority, Match, Action, State) <= (
        (Priority == 2) &
        ls_array(LS, UUID_LS, State) & (State != 0) &
        match.reg_flag(FLAG_LOOPBACK, Match) &
        # load 0xffff(OFPP_NONE) -> inport to avoid dropping loopback packet
        action.load(st.TP_OFPORT_NONE, NXM_Reg(IN_PORT_IDX), Action1) &
        action.resubmit_next(Action2) &
        (Action == Action1 + Action2)
        )

    lsp_judge_loopback(LS, Priority, Match, Action, State) <= (
        (Priority == 0) &
        ls_array(LS, UUID_LS, State) & (State != 0) &
        match.match_none(Match) &
        action.resubmit_next(Action)
        )

    # output packet to local ovs-port
    lsp_forward_packet(LS, Priority, Match, Action, State) <= (
        (Priority == 3) &
        local_bond_lsp(LSP, LS, State) & (State != 0) &
        match.reg_dst(LSP[LSP_PORTID], Match) &
        action.load(1, NXM_Reg(REG5_IDX), Action1) &
        action.load(LSP[LSP_OFPORT], NXM_Reg(REG_OUTPORT_IDX), Action2) &
        action.resubmit_next(Action3) &
        (Action == Action1 + Action2 + Action3)
        )

    # set the packet's destination, the destination is next LR's LRP
    lsp_forward_packet(LS, Priority, Match, Action, State) <= (
        (Priority == 2) &
        lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR,
                     UUID_LR, UUID_LR_CHASSIS, State) & (State != 0) &
        match.reg_dst(LSP[LSP_PORTID], Match) &
        # load next LR's ID to reg6, next stage's flow will move reg6 --> DP
        # load next LR's port to reg7, next stage's flow will move reg7
        # --> REG_SRC_IDX
        action.load(LR[LR_ID], NXM_Reg(REG6_IDX), Action1) &
        action.load(LRP[LRP_PORTID], NXM_Reg(REG7_IDX), Action2) &
        action.resubmit_next(Action3) &
        (Action == Action1 + Action2 + Action3)
        )

    # if above flows are not hit, then it means the destination is not
    # on this host and this packet must be a redirect packet. We should
    # send it to lsp_lookup_dst_port, then lsp_output_dst_port will use
    # output action to output packet later.
    # And we decrease ttl the packet.(we assume all packet comes in lsp
    # egress should be IP packet).
    lsp_forward_packet(LS, Priority, Match, Action, State) <= (
        (Priority == 0) &
        ls_array(LS, UUID_LS, State) & (State != 0) &
        match.ip_proto(Match) &
        # we set REDIRECT bit again, just try to avoid infinite loop
        action.load(1, NXM_Reg(REG_FLAG_IDX, FLAG_REDIRECT_BIT_IDX,
                               FLAG_REDIRECT_BIT_IDX), Action1) &
        action.resubmit_table(TABLE_LSP_INGRESS_LOOKUP_DST_PORT, Action2) &
        (Action ==  Action1 + Action2)
        )

    # if above flows are not hit, then it means the destination is not
    # on this host and this packet must be a redirect packet. We should
    # convert this arp request into arp response and send it back to
    # tunnel port which it comes from
    lsp_forward_packet(LS, Priority, Match, Action, State) <= (
        (Priority == 0) &
        ls_array(LS, UUID_LS, State) & (State != 0) &
        match.arp_proto(Match1) &
        match.arp_op(1, Match2) &
        (Match == Match1 + Match2) &
        # set REDIRECT bit again to avoid infinite loop
        action.load(1, NXM_Reg(REG_FLAG_IDX, FLAG_REDIRECT_BIT_IDX,
                               FLAG_REDIRECT_BIT_IDX), Action1) &
        action.resubmit_table(TABLE_ARP_FEEDBACK_CONSTRUCT, Action2) &
        action.resubmit_table(TABLE_LSP_INGRESS_LOOKUP_DST_PORT, Action3) &
        (Action ==  Action1 + Action2 + Action3)
        )

    lsp_pushout_packet(LS, Priority, Match, Action, State) <= (
        (Priority == 2) &
        ls_array(LS, UUID_LS, State) & (State != 0) &
        match.reg_5(1, Match) &
        action.resubmit_table(TABLE_OUTPUT_PKT, Action)
        )

    lsp_pushout_packet(LS, Priority, Match, Action, State) <= (
        (Priority == 1) &
        ls_array(LS, UUID_LS, State) & (State != 0) &
        match.match_none(Match) &
        action.move(NXM_Reg(REG6_IDX, 0, 23), NXM_Reg(REG_DP_IDX, 0, 23), Action1) &
        action.move(NXM_Reg(REG7_IDX), NXM_Reg(REG_SRC_IDX), Action2) &
        # set reg6 back to 0
        action.load(0, NXM_Reg(REG6_IDX), Action3) &
        action.load(0, NXM_Reg(REG7_IDX), Action4) &
        action.resubmit_table(TABLE_LRP_TRACE_INGRESS_IN, Action5) &
        (Action ==  Action1 + Action2 + Action3 + Action4 + Action5)
        )

