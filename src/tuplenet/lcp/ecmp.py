from pyDatalog import pyDatalog
import action
import match
from logicalview import *
from flow_common import *
from reg import *

pyDatalog.create_terms('Table, Priority, Match, Action')
pyDatalog.create_terms('Action1, Action2, Action3, Action4, Action5')
pyDatalog.create_terms('Action6, Action7, Action8, Action9, Action10')
pyDatalog.create_terms('Match1, Match2, Match3, Match4, Match5')
pyDatalog.create_terms('Route1, Route2, OFPORT1, OFPORT2')
pyDatalog.create_terms('PHY_CHASSIS1, PHY_CHASSIS2')
pyDatalog.create_terms('A,B,C,D,E,F,G,H,X,Y,Z')
pyDatalog.create_terms('ecmp_aggregate_outport, ecmp_aggregate_outport_readd')
pyDatalog.create_terms('ecmp_static_route, ecmp_static_route_judge, ecmp_bfd_port')
pyDatalog.create_terms('State_COMBIND1, State_COMBIND2')

# NOTE: same to the function of _cal_priority in lrp_ingress.py
def _cal_priority(prefix, level, idx):
    return (int(prefix) << 10) + (int(level) << 6) + idx
pyDatalog.create_terms('_cal_priority')

def init_ecmp_clause(options):
    # for adding
    # NOTE: this clause is consumed by ecmp_static_route.
    # There is NO circumstances that ecmp_static_route's LR's state is not zero, but
    # ecmp_aggregate_outport's state is zero. Because next_hop_ovsport need LR's state.
    # If you try to update ecmp_static_route, we should consider it!
    (ecmp_aggregate_outport[X] == tuple_(Y, order_by=Z)) <= (
        lroute_array(Route1, UUID_LR, State1) &
        lroute_array(Route2, UUID_LR, State2) &
        (State1 + State2 >= 0) &
        (Route1[LSR_UUID] != Route2[LSR_UUID]) &
        (Route1[LSR_IP] == Route2[LSR_IP]) &
        (Route1[LSR_PREFIX] == Route2[LSR_PREFIX]) &
        (Route1[LSR_NEXT_HOP] == Route2[LSR_NEXT_HOP]) &
        (Route1[LSR_OUTPORT] != Route2[LSR_OUTPORT]) &
        next_hop_ovsport(Route1[LSR_OUTPORT], OFPORT1, State3) &
        next_hop_ovsport(Route2[LSR_OUTPORT], OFPORT2, State4) &
        (State1 + State2 + State3 + State4 > 0) &
        (X == (UUID_LR, Route1[LSR_IP], Route1[LSR_PREFIX],
               State_ADD, 'adding')) &
        (Y == OFPORT1) & (Z == Route1[LSR_UUID])
        )

    # for readding slave port, deletion delete the whole flow,
    # but some ports should stay in bundle slave as well,
    # we should add those ports back
    (ecmp_aggregate_outport_readd[X] == tuple_(Y, order_by=Z)) <= (
        lroute_array(Route1, UUID_LR, State1) &
        lroute_array(Route2, UUID_LR, State2) &
        (State_COMBIND1 == State1 + State2) & (State_COMBIND1 >= 0) &
        (Route1[LSR_UUID] != Route2[LSR_UUID]) &
        (Route1[LSR_IP] == Route2[LSR_IP]) &
        (Route1[LSR_PREFIX] == Route2[LSR_PREFIX]) &
        (Route1[LSR_NEXT_HOP] == Route2[LSR_NEXT_HOP]) &
        (Route1[LSR_OUTPORT] != Route2[LSR_OUTPORT]) &
        next_hop_ovsport(Route1[LSR_OUTPORT], OFPORT1, State3) &
        next_hop_ovsport(Route2[LSR_OUTPORT], OFPORT2, State4) &
        (State_COMBIND2 == State1 + State2 + State3 + State4) & (State_COMBIND2 >= 0) &
        (ecmp_aggregate_outport[A] == B) &
        (A[0] == UUID_LR) & (A[1] == Route1[LSR_IP]) &
        (A[2] == Route1[LSR_PREFIX]) & (A[4] == 'deleting') &
        (X == (UUID_LR, Route1[LSR_IP], Route1[LSR_PREFIX],
               State_ADD, 'readding')) &
        (Y == OFPORT1) & (Z == Route1[LSR_UUID])
        )

    # for deleting
    (ecmp_aggregate_outport[X] == tuple_(Y, order_by=Y)) <= (
        lroute_array(Route1, UUID_LR, State1) &
        lroute_array(Route2, UUID_LR, State2) &
        (Route1[LSR_UUID] != Route2[LSR_UUID]) &
        (Route1[LSR_LR_UUID] == Route2[LSR_LR_UUID]) &
        (Route1[LSR_IP] == Route2[LSR_IP]) &
        (Route1[LSR_PREFIX] == Route2[LSR_PREFIX]) &
        (Route1[LSR_NEXT_HOP] == Route2[LSR_NEXT_HOP]) &
        (Route1[LSR_OUTPORT] != Route2[LSR_OUTPORT]) &
        next_hop_ovsport(Route1[LSR_OUTPORT], OFPORT, State3) &
        (State1 + State2 + State3 < 0) &
        (X == (Route1[LSR_LR_UUID], Route1[LSR_IP], Route1[LSR_PREFIX],
               State_DEL, 'deleting')) &
        (Y == OFPORT)
        )

    # adding and readding may generate same flow, it is ok.
    ecmp_static_route(LR, Priority, Match, Action, State) <= (
        lr_array(LR, UUID_LR, State1) &
        (ecmp_aggregate_outport[X] == Y) &
        (State == State1 + X[3]) & (State != 0) &
        (X[0] == UUID_LR) &
        (Priority == _cal_priority(X[2], 2, 0)) &
        match.ip_proto(Match1) &
        match.ip_dst_prefix(X[1], X[2], Match2) &
        (Match == Match1 + Match2) &
        action.bundle_load(NXM_Reg(REG_OUTPORT_IDX), Y, Action1) &
        action.resubmit_next(Action2) &
        (Action == Action1 + Action2)
        )

    ecmp_static_route(LR, Priority, Match, Action, State) <= (
        lr_array(LR, UUID_LR, State1) &
        (ecmp_aggregate_outport_readd[X] == Y) &
        (State == State1 + X[3]) & (State != 0) &
        (X[0] == UUID_LR) &
        (Priority == _cal_priority(X[2], 2, 0)) &
        match.ip_proto(Match1) &
        match.ip_dst_prefix(X[1], X[2], Match2) &
        (Match == Match1 + Match2) &
        action.bundle_load(NXM_Reg(REG_OUTPORT_IDX), Y, Action1) &
        action.resubmit_next(Action2) &
        (Action == Action1 + Action2)
        )

    # gateway chassis no need to consider ecmp
    if not options.has_key('GATEWAY'):
        # after hitting bundle_load action, flows should be add to forward packet
        # to different port base on value of reg4
        ecmp_static_route_judge(LR, Priority, Match, Action, State) <= (
            lroute_array(Route, UUID_LR, State1) &
            next_hop_ovsport(Route[LSR_OUTPORT], OFPORT, State2) &
            lr_array(LR, UUID_LR, State3) &
            lrp_array(Route[LSR_OUTPORT], LRP, UUID_LR, UUID_LSP, State4) &
            (State == State1 + State2 + State3 + State4) & (State != 0) &
            (Priority == _cal_priority(Route[LSR_PREFIX], 2, 0)) &
            match.reg_outport(OFPORT, Match1) &
            match.ip_proto(Match2) &
            match.ip_dst_prefix(Route[LSR_IP], Route[LSR_PREFIX], Match3) &
            (Match == Match1 + Match2 + Match3) &
            action.load(LRP[LRP_PORTID], NXM_Reg(REG_DST_IDX), Action1) &
            action.load(LRP[LRP_MAC_INT], NXM_Reg(ETH_SRC_IDX), Action2) &
            action.load(Route[LSR_NEXT_HOP_INT], NXM_Reg(REG2_IDX), Action3) &
            action.load(LRP[LRP_IP_INT], NXM_Reg(REG3_IDX), Action4) &
            action.resubmit_next(Action5) &
            (Action == Action1 + Action2 + Action3 + Action4 + Action5)
            )

        # drop packets if all bundle slave ports are not in 'up' status
        # TODO if we should ignore failure and deliver packet to
        # one of output ports
        ecmp_static_route_judge(LR, Priority, Match, Action, State) <= (
            lr_array(LR, UUID_LR, State) & (State != 0) &
            (Priority == 1) &
            match.reg_outport(0xffff, Match) &
            action.resubmit_table(TABLE_DROP_PACKET, Action)
            )

    # resubmit next stage without hitting any flows above
    ecmp_static_route_judge(LR, Priority, Match, Action, State) <= (
        lr_array(LR, UUID_LR, State) & (State != 0) &
        (Priority == 0) &
        match.match_none(Match) &
        action.resubmit_next(Action)
        )

    if options.has_key('GATEWAY'):
        # gateway chassis should set all tunnel port's bfd to true, unless the
        # chassis was deleted
        ecmp_bfd_port(PORT_NAME, State) <= (
            ovsport_chassis(PORT_NAME, UUID_CHASSIS, OFPORT, State1) &
            # we only enable ovsport that exist
            (State1 >= 0) & (UUID_CHASSIS != 'flow_base_tunnel') &
            chassis_array(PHY_CHASSIS, UUID_CHASSIS, State2) &
            (State == State1 + State2) & (State != 0)
            )
        # disable all tunnel port bfd if we found our chassis was deleted
        ecmp_bfd_port(PORT_NAME, State) <= (
            local_system_id(UUID_CHASSIS) &
            chassis_array(PHY_CHASSIS1, UUID_CHASSIS, State1) &
            # prevent event like chassis tick update,
            # ecmp_bfd_port will grep out PORT_NAME with state above 0.
            # In the same time, it also grep out PORT_NAME with state has negative
            # value. But config_tunnel_bfd help us eliminate negative part
            # NOTE: it can grep out (State1=1) (State2=1) (State=1),
            # (State1=1) (State2=-1)(State=-1),(State1=-1) (State2=-1)(State=-1)
            # but config_tunnel_bfd will keep (State=1) only
            chassis_array(PHY_CHASSIS2, UUID_CHASSIS, State2) &
            (State == State1 + State2) & (State != 0) &
            # figure out all tunnel port
            ovsport_chassis(PORT_NAME, UUID_CHASSIS1, OFPORT, State3) & (State3 >= 0) &
            (UUID_CHASSIS1 != 'flow_base_tunnel')
            )
    else:
        ecmp_bfd_port(PORT_NAME, State) <= (
            lroute_array(Route, UUID_LR, State1) &
            next_hop_ovsport(Route[LSR_OUTPORT], OFPORT, State2) &
            # we only enable/disable ovsport that exist
            ovsport_chassis(PORT_NAME, UUID_CHASSIS, OFPORT, State3) & (State3 >= 0) &
            chassis_array(PHY_CHASSIS, UUID_CHASSIS, State4) &
            (State == State1 + State2 + State3 + State4)
            )

