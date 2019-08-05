from pyDatalog import pyDatalog
import action
import match
from logicalview import *
from flow_common import *
from ecmp import *
from reg import *
import nat

pyDatalog.create_terms('lrp_pkt_response')
pyDatalog.create_terms('lrp_drop_unexpect')
pyDatalog.create_terms('lrp_ip_unsnat_stage1, lrp_ip_unsnat_stage2')
pyDatalog.create_terms('lrp_ip_dnat_stage1, lrp_ip_dnat_stage2')
pyDatalog.create_terms('lrp_ip_route')
pyDatalog.create_terms('lrp_ecmp_judge')
pyDatalog.create_terms('_live_lsp_link_lrp')
pyDatalog.create_terms('_static_route_changed')
pyDatalog.create_terms('_next_live_hop_lr')

# NOTE: value of priority is in [0,65535]
# ---------------------------------------------
# |PREFIX(6Bit) | Level(4Bit) | lrp_idx(6Bit) |
# ---------------------------------------------

def _cal_priority(prefix, level, idx):
    return (int(prefix) << 10) + (int(level) << 6) + idx
pyDatalog.create_terms('_cal_priority')


# NOTE: all lsp and lrp use IP least 16bits as a portID,
# so a lrp(ip=10.10.1.1) has same portID=0x0101, and lrp(ip=20.20.1.1)
# has same portID=0x0101

# NOTE
# reg0: src_port_id
# reg1: dst_port_id
# reg2: dst_ip
# reg3: next lrp
# reg4: the output ofport
# reg10: flag

def init_lrp_ingress_clause(options):

    init_ecmp_clause(options)

    if options.has_key('GATEWAY'):
        _live_lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR,
                           UUID_LR, None, State) <= (
            lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR,
                         UUID_LR, None, State)
        )
        _live_lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR, UUID_LR,
                           UUID_LR_CHASSIS, State) <= (
            lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR,
                         UUID_LR, UUID_LR_CHASSIS, State1) &
            chassis_array(PHY_CHASSIS, UUID_LR_CHASSIS, State2) &
            (State == State1 + State2)
        )
    else:
        _live_lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR,
                           UUID_LR, UUID_LR_CHASSIS, State) <= (
            lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR,
                         UUID_LR, UUID_LR_CHASSIS, State)
        )

    # response ICMP packet if receiving ICMP request
    lrp_pkt_response(LR, Priority, Match, Action, State) <= (
        (Priority == 3) &
        _live_lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR,
                           UUID_LR, UUID_LR_CHASSIS, State) & (State != 0) &
        match.icmp_proto(Match1) &
        match.icmp_type(8, Match2) &
        match.icmp_code(0, Match3) &
        match.ip_dst(LRP[LRP_IP], Match4) &
        (Match == Match1 + Match2 + Match3 + Match4) &
        action.exchange(NXM_Reg(IP_SRC_IDX), NXM_Reg(IP_DST_IDX), Action1) &
        action.load(0xff, NXM_Reg(IP_TTL_IDX), Action2) &
        action.load(0, NXM_Reg(ICMP_TYPE_IDX), Action3) &
        action.move(NXM_Reg(REG_SRC_IDX), NXM_Reg(REG_DST_IDX), Action4) &
        action.load(1, NXM_Reg(REG_FLAG_IDX, FLAG_LOOPBACK_BIT_IDX,
                               FLAG_LOOPBACK_BIT_IDX), Action5) &
        action.resubmit_next(Action6) &
        (Action == Action1 + Action2 + Action3 + Action4 +
                   Action5 + Action6)
        )


    lrp_pkt_response(LR, Priority, Match, Action, State) <= (
        (Priority == 0) &
        lr_array(LR, UUID_LR, State) & (State != 0) &
        match.ip_proto(Match) &
        action.resubmit_next(Action))

    lrp_drop_unexpect(LR, Priority, Match, Action, State) <= (
        (Priority == 2) &
        lr_array(LR, UUID_LR, State) & (State != 0) &
        match.ip_proto(Match1) &
        match.ip_ttl(1, Match2) &
        (Match == Match1 + Match2) &
        action.resubmit_table(TABLE_DROP_PACKET, Action)
        )

    lrp_drop_unexpect(LR, Priority, Match, Action, State) <= (
        (Priority == 0) &
        lr_array(LR, UUID_LR, State) & (State != 0) &
        match.ip_proto(Match) &
        action.dec_ttl(Action1) &
        action.resubmit_next(Action2) &
        (Action == Action1 + Action2)
        )

    lrp_ip_unsnat_stage1(LR, Priority, Match, Action, State) <= (
        nat.lunsnat_xlate_stage1(LR, Priority, Match, Action, State))
    lrp_ip_unsnat_stage2(LR, Priority, Match, Action, State) <= (
        nat.lunsnat_xlate_stage2(LR, Priority, Match, Action, State))

    lrp_ip_dnat_stage1(LR, Priority, Match, Action, State) <= (
        nat.ldnat_xlate_stage1(LR, Priority, Match, Action, State))
    lrp_ip_dnat_stage2(LR, Priority, Match, Action, State) <= (
        nat.ldnat_xlate_stage2(LR, Priority, Match, Action, State))

    #automatic route
    lrp_ip_route(LR, Priority, Match, Action, State) <= (
        lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR,
                     UUID_LR, UUID_LR_CHASSIS, State) & (State != 0) &
        (Priority == _cal_priority(LRP[LRP_PREFIX], 0, LRP[LRP_ILK_IDX])) &
        match.ip_proto(Match1) &
        match.ip_dst_prefix(LRP[LRP_IP],
                            LRP[LRP_PREFIX], Match2) &
        (Match == Match1 + Match2) &
        action.load(LRP[LRP_PORTID],
                    NXM_Reg(REG_DST_IDX), Action1) &
        action.load(LRP[LRP_MAC_INT],
                    NXM_Reg(ETH_SRC_IDX), Action2) &
        action.move(NXM_Reg(IP_DST_IDX), NXM_Reg(REG2_IDX), Action3) &
        # lrp_handle_unknow_dst_pkt may use it to modify IP to
        # construct right arp request
        action.load(LRP[LRP_IP_INT],
                    NXM_Reg(REG3_IDX), Action4) &
        action.resubmit_next(Action5) &
        (Action == Action1 + Action2 + Action3 + Action4 + Action5)
        )


    if options.has_key('GATEWAY'):
        _static_route_changed(Route, LR, LRP, State) <= (
            local_system_id(UUID_CHASSIS) &
            lroute_array(Route, UUID_LR, State1) &
            lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR,
                         UUID_LR, UUID_CHASSIS, State2) &
            (Route[LSR_OUTPORT] == LRP[LRP_UUID]) &
            local_patchport(LSP1, LS, State3) &
            (State == State1 + State2 + State3) & (State != 0)
            )

    _next_live_hop_lr(UUID_LRP, LRP, LR, LR_NEXT, State) <= (
        next_hop_lr(UUID_LRP, LRP, LR, LR_NEXT, State) &
        (LR_NEXT[LR_CHASSIS_UUID] == None)
        )
    # if next LR is pining on a chassis, tuplenet have to verify if the geneve
    # tunnel port had been create. Otherwise, some packet may deliver to this
    # LR which has no tunnel port to remote chassis. It cause packet drop once
    # a gateway chassis was re-add.
    _next_live_hop_lr(UUID_LRP, LRP, LR, LR_NEXT, State) <= (
        next_hop_lr(UUID_LRP, LRP, LR, LR_NEXT, State1) &
        (LR_NEXT[LR_CHASSIS_UUID] != None) &
        remote_chassis(LR_NEXT[LR_CHASSIS_UUID], PHY_CHASSIS_WITH_OFPORT, State2) &
        (State == State1 + State2)
        )
    _next_live_hop_lr(UUID_LRP, LRP, LR, LR_NEXT, State) <= (
        next_hop_lr(UUID_LRP, LRP, LR, LR_NEXT, State) &
        local_system_id(LR_NEXT[LR_CHASSIS_UUID])
        )

    _static_route_changed(Route, LR, LRP, State) <= (
        lroute_array(Route, UUID_LR, State1) &
        _next_live_hop_lr(Route[LSR_OUTPORT], LRP, LR, LR_NEXT, State2) &
        (State == State1 + State2) & (State != 0)
        )

    #static route
    lrp_ip_route(LR, Priority, Match, Action, State) <= (
        _static_route_changed(Route, LR, LRP, State) &
        (Priority == _cal_priority(Route[LSR_PREFIX], 1, Route[LSR_ILK_IDX])) &
        match.ip_proto(Match1) &
        match.ip_dst_prefix(Route[LSR_IP],
                            Route[LSR_PREFIX], Match2) &
        (Match == Match1 + Match2) &
        action.load(LRP[LRP_PORTID],
                    NXM_Reg(REG_DST_IDX), Action1) &
        action.load(LRP[LRP_MAC_INT],
                    NXM_Reg(ETH_SRC_IDX), Action2) &
        action.load(Route[LSR_NEXT_HOP_INT],
                    NXM_Reg(REG2_IDX), Action3) &
        # lrp_handle_unknow_dst_pkt may use it to modify IP to
        # construct right arp request
        action.load(LRP[LRP_IP_INT],
                    NXM_Reg(REG3_IDX), Action4) &
        action.resubmit_next(Action5) &
        (Action == Action1 + Action2 + Action3 + Action4 + Action5)
        )

    # gateway chassis no need to consider ecmp
    if not options.has_key('GATEWAY'):
        lrp_ip_route(LR, Priority, Match, Action, State) <= (
            ecmp_static_route(LR, Priority, Match, Action, State)
            )

    lrp_ecmp_judge(LR, Priority, Match, Action, State) <= (
        ecmp_static_route_judge(LR, Priority, Match, Action, State)
        )

    # drop packet if we cannot found route for this packet
    lrp_ip_route(LR, Priority, Match, Action, State) <= (
        (Priority == 0) &
        lr_array(LR, UUID_LR, State) & (State != 0) &
        match.match_none(Match) &
        action.resubmit_table(TABLE_DROP_PACKET, Action)
        )

