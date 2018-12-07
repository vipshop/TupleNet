from pyDatalog import pyDatalog
import action
import match
from reg import *
from logicalview import *
from flow_common import TABLE_LSP_EGRESS_FIRST, TABLE_LRP_INGRESS_IP_ROUTE, TABLE_EMBED2_METADATA, TABLE_DROP_PACKET
from run_env import get_init_trigger
pyDatalog.create_terms('Table, Priority, Match, Action')
pyDatalog.create_terms('Action1, Action2, Action3, Action4, Action5')
pyDatalog.create_terms('Match1, Match2, Match3, Match4, Match5')
pyDatalog.create_terms('get_init_trigger')
pyDatalog.create_terms('embed_metadata, extract_metadata, pipeline_forward')
pyDatalog.create_terms('redirect_other_chassis')
pyDatalog.create_terms('_gateway_state_sum, gateway_ofport')
pyDatalog.create_terms('_gateway_ofport, _gateway_ofport_readd')
pyDatalog.create_terms('A, B, C, X, Y, Z, UUID_CHASSIS')

# it does not count deleting-element in, because it was only consume by
# adding(_gateway_ofport) below
(_gateway_state_sum[X] == sum_(State, for_each=Z)) <= (
    remote_chassis(UUID_CHASSIS, PHY_CHASSIS, State1) &
    lr_array(LR, UUID_LR, State2) &
    (LR[LR_CHASSIS_UUID] == UUID_CHASSIS) &
    (State == State1 + State2) & (State >= 0) &
    (X == None) &
    (Z == PHY_CHASSIS[PCH_UUID])
)

(_gateway_ofport[X] == tuple_(Y, order_by=Z)) <= (
    remote_chassis(UUID_CHASSIS, PHY_CHASSIS, State1) &
    lr_array(LR, UUID_LR, State2) &
    (LR[LR_CHASSIS_UUID] == UUID_CHASSIS) &
    (State == State1 + State2) & (State >= 0) &
    (_gateway_state_sum[A] == B) &
    (X == ('adding', B)) &
    (Y == PHY_CHASSIS[PCH_OFPORT]) &
    (Z == PHY_CHASSIS[PCH_UUID])
)


(_gateway_ofport[X] == tuple_(Y, order_by=Z)) <= (
    (X == ('deleting', State_DEL)) &
    remote_chassis(UUID_CHASSIS, PHY_CHASSIS, State1) &
    lr_array(LR, UUID_LR, State2) &
    (LR[LR_CHASSIS_UUID] == UUID_CHASSIS) &
    (State == State1 + State2) & (State < 0) &
    (Y == PHY_CHASSIS[PCH_OFPORT]) &
    (Z == PHY_CHASSIS[PCH_UUID])
)

(_gateway_ofport_readd[X] == tuple_(Y, order_by=Z)) <= (
    (X == ('readding', State_ADD)) &
    (_gateway_ofport[A] == B) & (A[0] == 'deleting') &
    remote_chassis(UUID_CHASSIS, PHY_CHASSIS, State1) &
    lr_array(LR, UUID_LR, State2) &
    (LR[LR_CHASSIS_UUID] == UUID_CHASSIS) &
    (State == State1 + State2) & (State >= 0) &
    (Y == PHY_CHASSIS[PCH_OFPORT]) &
    (Z == PHY_CHASSIS[PCH_UUID])
)

(gateway_ofport[X] == Y) <= (_gateway_ofport[X] == Y)
(gateway_ofport[X] == Y) <= (_gateway_ofport_readd[X] == Y)

redirect_other_chassis(Priority, Match, Action, State) <= (
    (Priority == 1) &
    (gateway_ofport[X] == OFPORT) &
    (State == X[1]) & (State != 0) &
    match.match_none(Match) &
    action.load(1, NXM_Reg(REG_FLAG_IDX, FLAG_REDIRECT_BIT_IDX,
                           FLAG_REDIRECT_BIT_IDX), Action1) &
    action.bundle_load(NXM_Reg(REG4_IDX), OFPORT, Action2) &
    action.resubmit_table(TABLE_EMBED2_METADATA, Action3) &
    action.output_reg(NXM_Reg(REG4_IDX), Action4) &
    (Action == Action1 + Action2 + Action3 + Action4)
    )

redirect_other_chassis(Priority, Match, Action, State) <= (
    (Priority == 0) &
    (State == get_init_trigger(Priority)) & (State != 0) &
    match.match_none(Match) &
    action.resubmit_table(TABLE_DROP_PACKET, Action)
    )

embed_metadata(Priority, Match, Action, State) <= (
    (Priority == 0) &
    (State == get_init_trigger(Priority)) & (State != 0) &
    match.match_none(Match) &
    action.move(NXM_Reg(REG_DP_IDX, 0, 23),
                NXM_Reg(TUN_ID_IDX, 0, 23), Action1) &
    action.move(NXM_Reg(REG_SRC_IDX, 0, 15),
                NXM_Reg(TUN_METADATA0_IDX, 0, 15), Action2) &
    action.move(NXM_Reg(REG_DST_IDX, 0, 15),
                NXM_Reg(TUN_METADATA0_IDX, 16, 31), Action3) &
    action.move(NXM_Reg(REG_FLAG_IDX, 0, 31),
                NXM_Reg(TUN_METADATA0_IDX, 32, 63), Action4) &
    (Action == Action1 + Action2 + Action3 + Action4)
    )

extract_metadata(Priority, Match, Action, State) <= (
    (Priority == 0) &
    (State == get_init_trigger(Priority)) & (State != 0) &
    match.match_none(Match) &
    action.move(NXM_Reg(TUN_ID_IDX, 0, 23),
                NXM_Reg(REG_DP_IDX, 0, 23), Action1) &
    action.move(NXM_Reg(TUN_METADATA0_IDX, 0, 15),
                NXM_Reg(REG_SRC_IDX, 0, 15), Action2) &
    action.move(NXM_Reg(TUN_METADATA0_IDX, 16, 31),
                NXM_Reg(REG_DST_IDX, 0, 15), Action3) &
    action.move(NXM_Reg(TUN_METADATA0_IDX, 32, 63),
                NXM_Reg(REG_FLAG_IDX, 0, 31), Action4) &
    (Action == Action1 + Action2 + Action3 + Action4)
    )

pipeline_forward(Priority, Match, Action, State) <= (
    (Priority == 1) &
    (State == get_init_trigger(Priority)) & (State != 0) &
    match.ip_proto(Match1) &
    # a ip packet with 00 macaddress means it was a redirect packet which
    # send out by other host, deliver this packet to LR to help redirect
    match.eth_dst("00:00:00:00:00:00", Match2) &
    match.reg_flag(FLAG_REDIRECT, Match3) &
    (Match == Match1 + Match2 + Match3) &
    # TABLE_LRP_INGRESS_FIRST table is a tracing-point
    # as well and dec_ttl, skip that table
    action.resubmit_table(TABLE_LRP_INGRESS_IP_ROUTE, Action)
    )

# it is a regular packet, foward to lsp egress table immediately
pipeline_forward(Priority, Match, Action, State) <= (
    (Priority == 0) &
    (State == get_init_trigger(Priority)) & (State != 0) &
    match.match_none(Match) &
    action.resubmit_table(TABLE_LSP_EGRESS_FIRST, Action)
    )
