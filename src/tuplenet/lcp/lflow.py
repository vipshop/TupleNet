from pyDatalog import pyDatalog
import physical_flow
import middle_table as mid
import lsp_ingress
import lsp_egress
import lrp_ingress
import lrp_egress
import pkt_trace
import action
import match
from reg import *
from logicalview import *
from flow_common import *

pyDatalog.create_terms('Table, Priority, Match, Action, LS')
pyDatalog.create_terms('Match1, Match2, Match3')
pyDatalog.create_terms('Action1, Action2, Action3, Action4')
pyDatalog.create_terms('Priority1, Priority2')

pyDatalog.create_terms('build_flows_phy')
pyDatalog.create_terms('build_flows_mid')
pyDatalog.create_terms('build_flows_lsp')
pyDatalog.create_terms('build_flows_lrp')
pyDatalog.create_terms('build_flows_drop')
pyDatalog.create_terms('build_flows')
pyDatalog.create_terms('build_const_flows')

def init_build_flows_clause(options):
    action.init_action_clause()
    match.init_match_clause()
    init_entity_clause(options)
    physical_flow.init_physical_flow_clause(options)
    lsp_ingress.init_lsp_ingress_clause(options)
    lsp_egress.init_lsp_egress_clause(options)
    lrp_ingress.init_lrp_ingress_clause(options)
    lrp_egress.init_lrp_egress_clause(options)

    build_flows(Table, Priority, Match, Action, State) <= (
            build_flows_lrp(Table, Priority, Match, Action, State))

    build_flows(Table, Priority, Match, Action, State) <= (
            build_flows_lsp(Table, Priority, Match, Action, State))

    build_flows(Table, Priority, Match, Action, State) <= (
            build_flows_phy(Table, Priority, Match, Action, State))

    build_flows(Table, Priority, Match, Action, State) <= (
            build_flows_mid(Table, Priority, Match, Action, State))


# build const flows which were executed only once
    build_const_flows(Table, Priority, Match, Action) <= (
            build_flows_drop(Table, Priority, Match, Action))

    build_const_flows(Table, Priority, Match, Action) <= (
            build_flows_phy(Table, Priority, Match, Action))

    build_const_flows(Table, Priority, Match, Action) <= (
            build_flows_lsp(Table, Priority, Match, Action))

    build_const_flows(Table, Priority, Match, Action) <= (
            build_flows_lrp(Table, Priority, Match, Action))

    build_const_flows(Table, Priority, Match, Action) <= (
            build_flows_mid(Table, Priority, Match, Action))


# build physical flows
    build_flows_phy(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_CONVERT_PHY_LOGICAL) &
                physical_flow.convert_phy_logical(Priority, Match,
                                                  Action1, State) &
                action.note(flows_note2idx('convert_phy_logical'), Action2) &
                (Action == Action1 + Action2)
                )

    build_flows_phy(Table, Priority, Match, Action, State) <= (
                physical_flow.arp_feedback_construct(LS, Priority, Match2,
                                                     Action, State) &
                # TODO adding note here introduce performance regression
                # should figure out the root cause
                match.datapath(LS[LS_ID], Match1) &
                (Match == Match1 + Match2) &
                (Table == TABLE_ARP_FEEDBACK_CONSTRUCT)
                )

    build_flows_phy(Table, Priority, Match, Action) <= (
                physical_flow.output_pkt_by_reg(Priority, Match, Action1) &
                action.note(flows_note2idx('output_pkt'), Action2) &
                (Action == Action1 + Action2) &
                (Table == TABLE_OUTPUT_PKT)
                )

    build_flows_phy(Table, Priority, Match, Action) <= (
                pkt_trace.trace_pipeline_module(Match1, Action1) &
                # NOTE: refresh TUN_METADATA0_IDX, may output to remote chassis
                action.move(NXM_Reg(REG_FLAG_IDX, 0, 31),
                            NXM_Reg(TUN_METADATA0_IDX, 32, 63), Action2) &
                physical_flow.output_pkt_by_reg(Priority1, Match2, Action3) &
                (Priority == Priority1 + 10) &
                action.note(flows_note2idx('pkt_trace_output_pkt'), Action4) &
                (Match == Match1 + Match2) &
                (Action == Action1 + Action2 + Action3 + Action4) &
                (Table == TABLE_OUTPUT_PKT)
                )

# build middle table flows
    build_flows_mid(Table, Priority, Match, Action) <= (
                mid.embed_metadata(Priority, Match, Action1) &
                action.note(flows_note2idx('embed_metadata'), Action2) &
                (Action == Action1 + Action2) &
                (Table == TABLE_EMBED2_METADATA)
                )

    build_flows_mid(Table, Priority, Match, Action) <= (
                mid.extract_metadata(Priority, Match, Action1) &
                action.note(flows_note2idx('extract_metadata'), Action2) &
                (Action == Action1 + Action2) &
                (Table == TABLE_EXTRACT_METADATA)
                )

    build_flows_mid(Table, Priority, Match, Action) <= (
                mid.pipeline_forward(Priority, Match, Action1) &
                action.note(flows_note2idx('pipeline_forward'), Action2) &
                (Action == Action1 + Action2) &
                (Table == TABLE_PIPELINE_FORWARD)
                )

    build_flows_mid(Table, Priority, Match, Action, State) <= (
                mid.redirect_other_chassis(Priority, Match, Action1, State) &
                action.note(flows_note2idx('redirect_other_chassis'), Action2) &
                (Action == Action1 + Action2) &
                (Table == TABLE_REDIRECT_CHASSIS)
                )

    # const flow
    build_flows_mid(Table, Priority, Match, Action) <= (
                mid.redirect_other_chassis(Priority, Match, Action1) &
                action.note(flows_note2idx('redirect_other_chassis'), Action2) &
                (Action == Action1 + Action2) &
                (Table == TABLE_REDIRECT_CHASSIS)
                )


# build flows for logical port ingress pipline
    build_flows_lsp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LSP_INGRESS_OUTPUT_DST_PORT) &
                lsp_ingress.lsp_output_dst_port(LS, Priority, Match2,
                                                Action1, State) &
                action.note(flows_note2idx('lsp_output_dst_port'), Action2) &
                (Action == Action1 + Action2) &
                (match.datapath(LS[LS_ID], Match1)) &
                (Match == Match1 + Match2)
                )

    build_flows_lsp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LSP_INGRESS_LOOKUP_DST_PORT) &
                lsp_ingress.lsp_lookup_dst_port(LS, Priority, Match2,
                                                Action1, State) &
                action.note(flows_note2idx('lsp_lookup_dst_port'), Action2) &
                (Action == Action1 + Action2) &
                (match.datapath(LS[LS_ID], Match1)) &
                (Match == Match1 + Match2)
                )

    build_flows_lsp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LSP_INGRESS_ARP_CONTROLLER) &
                lsp_ingress.lsp_arp_controller(LS, Priority, Match2,
                                               Action1, State) &
                action.note(flows_note2idx('lsp_arp_controller'), Action2) &
                (Action == Action1 + Action2) &
                (match.datapath(LS[LS_ID], Match1)) &
                (Match == Match1 + Match2)
                )

    build_flows_lsp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LSP_INGRESS_ARP_RESPONSE) &
                lsp_ingress.lsp_arp_response(LS, Priority, Match2,
                                             Action1, State) &
                action.note(flows_note2idx('lsp_arp_response'), Action2) &
                (Action == Action1 + Action2) &
                (match.datapath(LS[LS_ID], Match1)) &
                (Match == Match1 + Match2)
                )


# build flows for logical port egress pipline
    build_flows_lsp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LSP_EGRESS_JUDGE_LOOPBACK) &
                lsp_egress.lsp_judge_loopback(LS, Priority, Match2,
                                              Action1, State) &
                action.note(flows_note2idx('lsp_judge_loopback'), Action2) &
                (Action == Action1 + Action2) &
                (match.datapath(LS[LS_ID], Match1)) &
                (Match == Match1 + Match2)
                )

    build_flows_lsp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LSP_EGRESS_FORWARD_PACKET) &
                lsp_egress.lsp_forward_packet(LS, Priority, Match2,
                                              Action1, State) &
                action.note(flows_note2idx('lsp_forward_packet'), Action2) &
                (Action == Action1 + Action2) &
                (match.datapath(LS[LS_ID], Match1)) &
                (Match == Match1 + Match2)
                )

    build_flows_lsp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LSP_EGRESS_PUSHOUT) &
                lsp_egress.lsp_pushout_packet(LS, Priority, Match2,
                                              Action1, State) &
                action.note(flows_note2idx('lsp_pushout_packet'), Action2) &
                (Action == Action1 + Action2) &
                (match.datapath(LS[LS_ID], Match1)) &
                (Match == Match1 + Match2)
                )

    # build const trace flow for in first stage of lsp ingress
    build_flows_lsp(Table, Priority, Match, Action) <= (
                (Table == TABLE_LSP_TRACE_INGRESS_IN) &
                action.load(0, NXM_Reg(REG_DST_IDX), Action1) &
                pkt_trace.trace_pipeline_start(Priority, Match, Action2) &
                action.note(flows_note2idx('pkt_trace_lsp_ingress_in'), Action3) &
                (Action == Action1 + Action2 + Action3)
                )

    # build trace flow for in end stage of lsp ingress
    # because the end stage of lsp ingress has no uniq path, so
    # we have to add similar flows(simliar to regular flow) to trace
    build_flows_lsp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LSP_TRACE_INGRESS_OUT) &
                pkt_trace.trace_pipeline_module(Match1, Action1) &
                lsp_ingress.lsp_output_dst_port(LS, Priority1, Match2,
                                                Action2, State) &
                (Priority == Priority1 + 10) &
                (match.datapath(LS[LS_ID], Match3)) &
                (Match == Match1 + Match2 + Match3) &
                action.note(flows_note2idx('pkt_trace_lsp_output_dst_port'),
                            Action3) &
                (Action == Action1 + Action2 + Action3)
                )

    # build const trace flow in first stage of lsp egress
    build_flows_lsp(Table, Priority, Match, Action) <= (
                (Table == TABLE_LSP_TRACE_EGRESS_IN) &
                pkt_trace.trace_pipeline_start(Priority, Match, Action1) &
                action.note(flows_note2idx('pkt_trace_lsp_egress_in'), Action2) &
                (Action == Action1 + Action2)
                )

    # build trace flow in end stage of lsp egress
    # because the end stage of lsp egress has no uniq path, so
    # we have to add similar flows(simliar to regular flow) to trace
    build_flows_lsp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LSP_TRACE_EGRESS_OUT) &
                pkt_trace.trace_pipeline_module(Match1, Action1) &
                lsp_egress.lsp_pushout_packet(LS, Priority1, Match2,
                                              Action2, State) &
                action.note(flows_note2idx('pkt_trace_lsp_pushout_packet'),
                            Action3) &
                (Priority == Priority1 + 10) &
                (match.datapath(LS[LS_ID], Match3)) &
                (Match == Match1 + Match2 + Match3) &
                (Action == Action1 + Action2 + Action3)
                )

#-----------------------------LRP---------------------------------------------

#build flows for logical router port ingress pipline
    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_INGRESS_PKT_RESPONSE) &
                lrp_ingress.lrp_pkt_response(LR, Priority, Match2, Action1, State) &
                action.note(flows_note2idx('lrp_pkt_response'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_INGRESS_DROP_UNEXPECT) &
                lrp_ingress.lrp_drop_unexpect(LR, Priority, Match2, Action1, State) &
                action.note(flows_note2idx('lrp_drop_unexpect'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_INGRESS_UNSNAT_STAGE1) &
                lrp_ingress.lrp_ip_unsnat_stage1(LR, Priority, Match2,
                                                 Action1, State) &
                action.note(flows_note2idx('lrp_ip_unsnat_stage1'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_INGRESS_UNSNAT_STAGE2) &
                lrp_ingress.lrp_ip_unsnat_stage2(LR, Priority, Match2,
                                                 Action1, State) &
                action.note(flows_note2idx('lrp_ip_unsnat_stage2'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_INGRESS_DNAT_STAGE1) &
                lrp_ingress.lrp_ip_dnat_stage1(LR, Priority, Match2,
                                               Action1, State) &
                action.note(flows_note2idx('lrp_ip_dnat_stage1'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_INGRESS_DNAT_STAGE2) &
                lrp_ingress.lrp_ip_dnat_stage2(LR, Priority, Match2,
                                               Action1, State) &
                action.note(flows_note2idx('lrp_ip_dnat_stage2'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_INGRESS_IP_ROUTE) &
                lrp_ingress.lrp_ip_route(LR, Priority, Match2, Action1, State) &
                action.note(flows_note2idx('lrp_ip_route'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_INGRESS_ECMP) &
                lrp_ingress.lrp_ecmp_judge(LR, Priority, Match2, Action1, State) &
                action.note(flows_note2idx('lrp_ecmp_judge'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

#build flows for logical router port egress pipline
    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_EGRESS_UPDATE_ETH_DST) &
                lrp_egress.lrp_update_eth_dst(LR, Priority, Match2, Action1, State) &
                action.note(flows_note2idx('lrp_update_eth_dst'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_EGRESS_UNDNAT_STAGE1) &
                lrp_egress.lrp_ip_undnat_stage1(LR, Priority, Match2,
                                                Action1, State) &
                action.note(flows_note2idx('lrp_ip_undnat_stage1'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_EGRESS_UNDNAT_STAGE2) &
                lrp_egress.lrp_ip_undnat_stage2(LR, Priority, Match2,
                                                Action1, State) &
                action.note(flows_note2idx('lrp_ip_undnat_stage2'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_EGRESS_SNAT_STAGE1) &
                lrp_egress.lrp_ip_snat_stage1(LR, Priority, Match2,
                                              Action1, State) &
                action.note(flows_note2idx('lrp_ip_snat_stage1'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_EGRESS_SNAT_STAGE2) &
                lrp_egress.lrp_ip_snat_stage2(LR, Priority, Match2,
                                              Action1, State) &
                action.note(flows_note2idx('lrp_ip_snat_stage2'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_EGRESS_HANDLE_UNK_PKT) &
                lrp_egress.lrp_handle_unknow_dst_pkt(LR, Priority, Match2,
                                                     Action1, State) &
                action.note(flows_note2idx('lrp_handle_unknow_dst_pkt'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    build_flows_lrp(Table, Priority, Match, Action, State) <= (
                (Table == TABLE_LRP_EGRESS_FORWARD_PACKET) &
                lrp_egress.lrp_forward_packet(LR, Priority, Match2, Action1, State) &
                action.note(flows_note2idx('lrp_forward_packet'), Action2) &
                (Action == Action1 + Action2) &
                match.datapath(LR[LR_ID], Match1) &
                (Match == Match1 + Match2)
                )

    # build const trace flow in first stage of lrp ingress
    build_flows_lrp(Table, Priority, Match, Action) <= (
                (Table == TABLE_LRP_TRACE_INGRESS_IN) &
                action.load(0, NXM_Reg(REG_DST_IDX), Action1) &
                pkt_trace.trace_pipeline_start(Priority, Match, Action2) &
                action.note(flows_note2idx('pkt_trace_lrp_ingress_in'), Action3) &
                (Action == Action1 + Action2 + Action3)
                )

    # build const trace flow in last stage of lrp ingress
    build_flows_lrp(Table, Priority, Match, Action) <= (
                (Table == TABLE_LRP_TRACE_INGRESS_OUT) &
                pkt_trace.trace_pipeline_end(Priority, Match, Action1) &
                action.resubmit_table(TABLE_LRP_EGRESS_FIRST, Action2) &
                action.note(flows_note2idx('pkt_trace_lrp_ingress_out'), Action3) &
                (Action == Action1 + Action2 + Action3)
                )

    # build const trace flow in first stage of lrp egress
    build_flows_lrp(Table, Priority, Match, Action) <= (
                (Table == TABLE_LRP_TRACE_EGRESS_IN) &
                pkt_trace.trace_pipeline_start(Priority, Match, Action1) &
                action.note(flows_note2idx('pkt_trace_lrp_egress_in'), Action2) &
                (Action == Action1 + Action2)
                )

    # build const trace flow in last stage of lrp egress
    build_flows_lrp(Table, Priority, Match, Action) <= (
                (Table == TABLE_LRP_TRACE_EGRESS_OUT) &
                pkt_trace.trace_pipeline_end(Priority, Match, Action1) &
                action.resubmit_table(TABLE_LSP_INGRESS_FIRST, Action2) &
                action.note(flows_note2idx('pkt_trace_lrp_egress_out'), Action3) &
                (Action == Action1 + Action2 + Action3)
                )

#---------------------const drop table--------------------------------
    build_flows_drop(Table, Priority, Match, Action) <= (
                (Priority == 0) &
                (Table == TABLE_DROP_PACKET) &
                match.match_none(Match) &
                action.drop(Action)
                )
    build_flows_drop(Table, Priority, Match, Action) <= (
                (Priority == 1) &
                (Table == TABLE_DROP_PACKET) &
                # we do not add drop action, because drop action
                # must not be accompanied by any other action or instruction
                # so we just add packet tracing action.
                pkt_trace.trace_pipeline_module(Match, Action1) &
                action.note(flows_note2idx('pkt_trace_drop_packet'), Action2) &
                (Action == Action1 + Action2)
                )
