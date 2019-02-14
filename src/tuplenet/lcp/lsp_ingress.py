from pyDatalog import pyDatalog
import action
import match
from reg import *
from logicalview import *
from flow_common import *

pyDatalog.create_terms('Table, Priority, Match, Action')
pyDatalog.create_terms('Action1, Action2, Action3, Action4, Action5')
pyDatalog.create_terms('Action6, Action7, Action8, Action9, Action10')
pyDatalog.create_terms('Match1, Match2, Match3, Match4, Match5')
pyDatalog.create_terms('LS1, UUID_LS1')

pyDatalog.create_terms('lsp_output_dst_port')
pyDatalog.create_terms('lsp_lookup_dst_port')
pyDatalog.create_terms('lsp_arp_controller')
pyDatalog.create_terms('lsp_arp_response')
pyDatalog.create_terms('lsp_untunnel_deliver')
pyDatalog.create_terms('_lsp_remote_lsp_changed')

# NOTE
# reg0: src_port_id
# reg1: dst_port_id
# reg4: the output ofport
# reg5: interim reg
# reg10: flag


def init_lsp_ingress_clause(options):

    if options.has_key('GATEWAY'):
        # push RARP to controller, only Edge node should consider receiving rarp
        lsp_arp_controller(LS, Priority, Match, Action, State) <= (
            (Priority == 2) &
            ls_array(LS, UUID_LS, State) & (State != 0) &
            match.arp_proto(Match1) &
            match.arp_op(2, Match2) &
            (Match == Match1 + Match2) &
            action.upload_arp(Action)
            )

    if not options.has_key('ONDEMAND'):
        # maybe gratuitous ARP, push to controller.
        # maybe a unknow dst arp
        lsp_arp_controller(LS, Priority, Match, Action, State) <= (
            (Priority == 1) &
            ls_array(LS, UUID_LS, State) & (State != 0) &
            match.arp_proto(Match1) &
            match.arp_op(1, Match2) &
            (Match == Match1 + Match2) &
            action.upload_arp(Action1) &
            action.resubmit_next(Action2) &
            (Action == Action1 + Action2)
            )

    lsp_arp_controller(LS, Priority, Match, Action, State) <= (
        (Priority == 0) &
        ls_array(LS, UUID_LS, State) & (State != 0) &
        (match.match_none(Match)) &
        action.resubmit_next(Action)
        )

    lsp_arp_response(LS, Priority, Match, Action, State) <= (
        (Priority == 2) &
        ls_array(LS, UUID_LS, State) & (State != 0) &
        match.arp_proto(Match1) &
        match.arp_op(1, Match2) &
        (Match == Match1 + Match2) &
        action.resubmit_table(TABLE_ARP_FEEDBACK_CONSTRUCT, Action1) &
        action.resubmit_next(Action2) &
        (Action == Action1 + Action2)
        )

    lsp_arp_response(LS, Priority, Match, Action, State) <= (
        (Priority == 0) &
        ls_array(LS, UUID_LS, State) & (State != 0) &
        (match.match_none(Match)) &
        action.resubmit_next(Action)
        )


    if options.has_key('ENABLE_UNTUNNEL'):
        lsp_untunnel_deliver(LS, Priority, Match, Action, State) <= (
            (Priority == 2) &
            ls_array(LS, UUID_LS, State1) &
            lsp_link_lrp(LSP, LS1, UUID_LS1, LRP, LR,
                         UUID_LR, UUID_LR_CHASSIS, State2) &
            (State == State1 + State2) & (State != 0) &
            match.ip_proto(Match1) &
            match.ip_dst_prefix(LRP[LRP_IP], LRP[LRP_PREFIX], Match2) &
            (Match == Match1 + Match2) &
            action.resubmit_next(Action)
        )

        lsp_untunnel_deliver(LS, Priority, Match, Action, State) <= (
            (Priority == 1) &
            ls_array(LS, UUID_LS, State) & (State != 0) &
            match.ip_proto(Match) &
            # output packet to local port which is an internal port.
            # packet goes into tcpip stack
            action.mod_dl_dst(options['br-int_mac'], Action1) &
            action.output('LOCAL', Action2) &
            (Action == Action1 + Action2)
            )


    lsp_untunnel_deliver(LS, Priority, Match, Action, State) <= (
        (Priority == 0) &
        ls_array(LS, UUID_LS, State) & (State != 0) &
        (match.match_none(Match)) &
        action.resubmit_next(Action)
        )

    # deliver to LR which has snat/dnat
    lsp_lookup_dst_port(LS, Priority, Match, Action, State) <= (
        (Priority == 5) &
        # TODO optimize it
        lnat_data(LNAT, LR, XLATE_TYPE, UUID_LR, State1) &
        lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR,
                     UUID_LR, UUID_LR_CHASSIS, State2) &
        (State == State1 + State2) & (State != 0) &
        match.eth_dst(LNAT[LNAT_XLATE_MAC], Match) &
        action.load(LSP[LSP_PORTID], NXM_Reg(REG_DST_IDX), Action1) &
        action.resubmit_next(Action2) &
        (Action == Action1 + Action2)
        )

    # deliver to another lsp on local chassis
    lsp_lookup_dst_port(LS, Priority, Match, Action, State) <= (
        (Priority == 4) &
        local_lsp(LSP, LS, State) & (State != 0) &
        match.eth_dst(LSP[LSP_MAC], Match) &
        action.load(LSP[LSP_PORTID],
                    NXM_Reg(REG_DST_IDX), Action1) &
        action.resubmit_next(Action2) &
        (Action == Action1 + Action2)
        )

    # it helps reduce time-cost
    _lsp_remote_lsp_changed(LSP, LS, PHY_CHASSIS, State) <= (
                    remote_lsp(LSP, LS, PHY_CHASSIS, State) & (State != 0))

    if options.has_key('ENABLE_REDIRECT'):
        # output deliver to another remote chassis.
        # use bundle_load to check if dst chassis is dead or live.
        lsp_lookup_dst_port(LS, Priority, Match, Action, State) <= (
            (Priority == 3) &
            _lsp_remote_lsp_changed(LSP, LS, PHY_CHASSIS, State) &
            match.eth_dst(LSP[LSP_MAC], Match) &
            action.load(LSP[LSP_PORTID],
                        NXM_Reg(REG_DST_IDX), Action1) &
            action.bundle_load(NXM_Reg(REG_OUTPORT_IDX),
                               [PHY_CHASSIS[PCH_OFPORT]], Action2) &
            # if we want output this packet in next step, we set 1->reg5
            # in next step flow, no need to clean this reg5, because
            # it should output a port means the end of packet process
            action.load(1, NXM_Reg(REG5_IDX), Action3) &
            action.resubmit_next(Action4) &
            (Action == Action1 + Action2 + Action3 + Action4)
            )
    else:
        # deliver to remote chassis by using output,(set outport to reg4)
        lsp_lookup_dst_port(LS, Priority, Match, Action, State) <= (
            (Priority == 3) &
            _lsp_remote_lsp_changed(LSP, LS, PHY_CHASSIS, State) &
            match.eth_dst(LSP[LSP_MAC], Match) &
            action.load(LSP[LSP_PORTID],
                        NXM_Reg(REG_DST_IDX), Action1) &
            action.load(PHY_CHASSIS[PCH_OFPORT],
                        NXM_Reg(REG_OUTPORT_IDX), Action2) &
            # if we want output this packet in next step, we set 1->reg5
            # in next step flow, no need to clean this reg5, because
            # it should output a a port means the end of packet process
            action.load(1, NXM_Reg(REG5_IDX), Action3) &
            action.resubmit_next(Action4) &
            (Action == Action1 + Action2 + Action3 + Action4)
            )

    # deliver the packet which not match above flow to the patchport
    # patch port's mac address should be ff:ff:ff:ff:ff:ee
    lsp_lookup_dst_port(LS, Priority, Match, Action, State) <= (
        (Priority == 2) &
        local_lsp(LSP, LS, State) & (State != 0) &
        (LSP[LSP_MAC] == 'ff:ff:ff:ff:ff:ee') &
        match.match_none(Match) &
        action.load(LSP[LSP_PORTID],
                    NXM_Reg(REG_DST_IDX), Action1) &
        action.resubmit_table(TABLE_LSP_EGRESS_FIRST, Action2) &
        (Action == Action1 + Action2)
        )

    if options.has_key('ONDEMAND'):
        # ovs must upload this packet to controller if cannot found the
        # destination. controller will tell tuplenet to generate more flows
        lsp_lookup_dst_port(LS, Priority, Match, Action, State) <= (
            (Priority == 0) &
            ls_array(LS, UUID_LS, State) & (State != 0) &
            match.match_none(Match) &
            action.upload_unknow_dst(Action1) &
            # resubmit this packet to next stage, gateway host can
            # do delivering if gateway enable redirect feature
            action.load(0xffff, NXM_Reg(REG_OUTPORT_IDX), Action2) &
            action.load(1, NXM_Reg(REG5_IDX), Action3) &
            action.resubmit_next(Action4) &
            (Action == Action1 + Action2 + Action3 + Action4)
            )

    else:
        # deliver packet to drop table if this packet cannot
        # found the destination.
        lsp_lookup_dst_port(LS, Priority, Match, Action, State) <= (
            (Priority == 0) &
            ls_array(LS, UUID_LS, State) & (State != 0) &
            match.match_none(Match) &
            action.resubmit_table(TABLE_DROP_PACKET, Action)
            )

    if options.has_key('ENABLE_REDIRECT'):
        # if it is a redirectd packet and reg4 is 0xffff, then we should drop
        # it, because we don't want cause infinite loop
        lsp_output_dst_port(LS, Priority, Match, Action, State) <= (
            (Priority == 4) &
            ls_array(LS, UUID_LS, State) & (State != 0) &
            match.reg_5(1, Match1) &
            match.reg_flag(FLAG_REDIRECT, Match2) &
            match.reg_outport(0xffff, Match3) &
            (Match == Match1 + Match2 + Match3) &
            action.resubmit_table(TABLE_DROP_PACKET, Action)
            )

        # if this packet was failed to deliver to remote chassis, we send it to
        # other gateway to help forwarding
        lsp_output_dst_port(LS, Priority, Match, Action, State) <= (
            (Priority == 3) &
            ls_array(LS, UUID_LS, State) & (State != 0) &
            match.reg_5(1, Match1) &
            match.reg_outport(0xffff, Match2) &
            (Match == Match1 + Match2) &
            action.resubmit_table(TABLE_REDIRECT_CHASSIS, Action)
            )

    # output to a port base on reg4's value
    lsp_output_dst_port(LS, Priority, Match, Action, State) <= (
        (Priority == 2) &
        ls_array(LS, UUID_LS, State) &  (State != 0) &
        match.reg_5(1, Match) &
        action.resubmit_table(TABLE_EMBED2_METADATA, Action1) &
        action.resubmit_table(TABLE_OUTPUT_PKT, Action2) &
        (Action == Action1 + Action2)
        )

    # just deliver to next stage
    lsp_output_dst_port(LS, Priority, Match, Action, State) <= (
        (Priority == 1) &
        ls_array(LS, UUID_LS, State) & (State != 0) &
        match.match_none(Match) &
        action.resubmit_table(TABLE_LSP_EGRESS_FIRST, Action)
        )

