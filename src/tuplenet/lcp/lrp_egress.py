from pyDatalog import pyDatalog
from logicalview import *
from reg import *
from flow_common import *
import match
import action
import nat


pyDatalog.create_terms('Table, Priority, Match, Action')
pyDatalog.create_terms('LRP, LR, LSP, LSP1, MAC, IP_INT')
pyDatalog.create_terms('Action1, Action2, Action3, Action4, Action5')
pyDatalog.create_terms('Action6, Action7, Action8, Action9, Action10')
pyDatalog.create_terms('Match1, Match2, Match3, Match4, Match5, State6')
pyDatalog.create_terms('UUID_LR_CHASSIS, X, Y, Z')
pyDatalog.create_terms('lrp_forward_packet')
pyDatalog.create_terms('lrp_update_eth_dst')
pyDatalog.create_terms('lrp_ip_snat_stage1, lrp_ip_snat_stage2')
pyDatalog.create_terms('lrp_ip_undnat_stage1, lrp_ip_undnat_stage2')
pyDatalog.create_terms('lrp_handle_unknow_dst_pkt')
pyDatalog.create_terms('opposite_side_changed_lsp')
pyDatalog.create_terms('opposite_side_has_patch_port')

# NOTE
# reg0: src_port_id
# reg1: dst_port_id
# reg2: dst_ip
# reg3: next lrp
# reg4: the output ofport
# reg10: flag

def init_lrp_egress_clause(options):

    # figure out all linked lsp on a LS which has a connection with this LRP
    opposite_side_changed_lsp(LR, LRP, LSP, State) <= (
        lsp_link_lrp(LSP1, LS, UUID_LS, LRP, LR,UUID_LR, UUID_LR_CHASSIS, State1) &
        exchange_lsp_array(UUID_LSP, LSP, UUID_LS, UUID_CHASSIS, UUID_LRP1, State2) &
        (State == State1 + State2) & (State != 0))
    # figure out all regular lsp
    opposite_side_changed_lsp(LR, LRP, LSP, State) <= (
        lrp_array(UUID_LRP, LRP, UUID_LR, UUID_LSP1, State1) &
        exchange_lsp_array(UUID_LSP1, LSP1, UUID_LS, UUID_CHASSIS1, UUID_LRP, State2) &
        ls_array(LS, UUID_LS, State3) &
        lr_array(LR, UUID_LR, State4) &
        lsp_array(UUID_LSP, LSP, UUID_LS, UUID_CHASSIS2, UUID_LRP2, State5) &
        (UUID_CHASSIS2 != None) &
        (State == State1 + State2 + State3 + State4 + State5) & (State != 0)
        )

    opposite_side_has_patch_port(LR, LRP, State) <= (
        local_patchport(LSP, LS, State1) &
        lsp_link_lrp(LSP1, LS, UUID_LS, LRP, LR,
                     UUID_LR, UUID_LR_CHASSIS, State2) &
        # NOTE only consider local_patchport, it means a gateway's oppsite
        # LS has remote patchport cannot trigger this flow
        (State == State1 + State2)
        )

    # update eth_dst by searching active lsp
    lrp_update_eth_dst(LR, Priority, Match, Action, State) <= (
        (Priority == 3) &
        opposite_side_changed_lsp(LR, LRP, LSP, State) &
        match.ip_proto(Match1) &
        # we have to match the lrp portID, because in ecmp,
        # two ports may have same dst IP but different dst mac
        match.reg_dst(LRP[LRP_PORTID], Match2) &
        match.reg_2(LSP[LSP_IP_INT], Match3) &
        (Match == Match1 + Match2 + Match3) &
        action.load(LSP[LSP_MAC_INT],
                    NXM_Reg(ETH_DST_IDX), Action1) &
        action.resubmit_next(Action2) &
        (Action == Action1 + Action2)
        )


    # push packet to table TABLE_SEARCH_IP_MAC to search unknow mac,ip pair
    lrp_update_eth_dst(LR, Priority, Match, Action, State) <= (
        (Priority == 2) &
        lr_array(LR, UUID_LR, State) & (State != 0) &
        match.match_none(Match) &
        action.mod_dl_dst("00:00:00:00:00:00", Action1) &
        action.resubmit_table(TABLE_SEARCH_IP_MAC, Action2) &
        action.resubmit_next(Action3) &
        (Action == Action1 + Action2 + Action3)
        )

    lrp_ip_undnat_stage1(LR, Priority, Match, Action, State) <= (
        nat.lundnat_xlate_stage1(LR, Priority, Match, Action, State))
    lrp_ip_undnat_stage2(LR, Priority, Match, Action, State) <= (
        nat.lundnat_xlate_stage2(LR, Priority, Match, Action, State))

    lrp_ip_snat_stage1(LR, Priority, Match, Action, State) <= (
        nat.lsnat_xlate_stage1(LR, Priority, Match, Action, State))
    lrp_ip_snat_stage2(LR, Priority, Match, Action, State) <= (
        nat.lsnat_xlate_stage2(LR, Priority, Match, Action, State))


    # ovs should drop it if the packet's dst_mac = 00:00:00:00:00:00 and
    # it is a redirect packet. This flow avoids infinite loop.
    lrp_handle_unknow_dst_pkt(LR, Priority, Match, Action, State) <= (
        (Priority == 4) &
        lr_array(LR, UUID_LR, State) & (State != 0) &
        match.reg_flag(FLAG_REDIRECT, Match1) &
        match.eth_dst("00:00:00:00:00:00", Match2) &
        (Match == Match1 + Match2) &
        action.resubmit_table(TABLE_DROP_PACKET, Action)
        )

    # ask controller to generate arp, if we cannot found the ip,mac pair.
    # If opposite LS has patch-port will create this flow
    lrp_handle_unknow_dst_pkt(LR, Priority, Match, Action, State) <= (
        (Priority == 3) &
        # oppsite LS must has patchport
        opposite_side_has_patch_port(LR, LRP, State) & (State != 0) &
        match.ip_proto(Match1) &
        match.eth_dst("00:00:00:00:00:00", Match2) &
        match.reg_dst(LRP[LRP_PORTID], Match3) &
        (Match == Match1 + Match2 + Match3) &
        # reg2 and reg3 were transfered to pkt_controller as well
        action.generate_arp(TABLE_LRP_EGRESS_FORWARD_PACKET, Action1) &
        action.resubmit_table(TABLE_DROP_PACKET, Action2) &
        (Action == Action1 + Action2)
        )

    # upload packet to controller, if this packet cannot trigger generating
    # arp and didn't know the destination's macaddress. controller will
    # ask tuplenet to generate it.
    if options.has_key('ONDEMAND'):
        if options.has_key('ENABLE_REDIRECT'):
            # A regular tuplenet node(with ondemand) may not know where dst lsp is,
            # so it uploads packet to controller and redirects pkt to an edge node.
            lrp_handle_unknow_dst_pkt(LR, Priority, Match, Action, State) <= (
                (Priority == 2) &
                lr_array(LR, UUID_LR, State) & (State != 0) &
                match.ip_proto(Match1) &
                # set macaddress to 0, then other host know this packet
                # should be threw to LR pipline
                match.eth_dst("00:00:00:00:00:00", Match2) &
                (Match == Match1 + Match2) &
                action.load(1, NXM_Reg(REG_FLAG_IDX, FLAG_REDIRECT_BIT_IDX,
                                       FLAG_REDIRECT_BIT_IDX), Action1) &
                action.upload_unknow_dst(Action2) &
                action.resubmit_table(TABLE_EMBED2_METADATA, Action3) &
                action.resubmit_table(TABLE_REDIRECT_CHASSIS, Action4) &
                (Action == Action1 + Action2 + Action3 + Action4)
                )
        else:
            lrp_handle_unknow_dst_pkt(LR, Priority, Match, Action, State) <= (
                (Priority == 2) &
                lr_array(LR, UUID_LR, State) & (State != 0) &
                match.ip_proto(Match1) &
                match.eth_dst("00:00:00:00:00:00", Match2) &
                (Match == Match1 + Match2) &
                action.upload_unknow_dst(Action)
                )
    else:
        if options.has_key('ENABLE_REDIRECT'):
            # A edge node(with ondemand disable) should know where is dst, but
            # tuplenet instance may down so ovs-flow doesn't know the new dst(
            # a lsp may be create while tuplenet is down, ovs-flow not updated).
            # This ovs-flow should redirect this packet to other edge now as well,
            # BUT NOT upload to controller
            lrp_handle_unknow_dst_pkt(LR, Priority, Match, Action, State) <= (
                (Priority == 2) &
                lr_array(LR, UUID_LR, State) & (State != 0) &
                match.ip_proto(Match1) &
                # set macaddress to 0, then other host know this packet
                # should be threw to LR pipline
                match.eth_dst("00:00:00:00:00:00", Match2) &
                (Match == Match1 + Match2) &
                action.load(1, NXM_Reg(REG_FLAG_IDX, FLAG_REDIRECT_BIT_IDX,
                                       FLAG_REDIRECT_BIT_IDX), Action1) &
                action.resubmit_table(TABLE_EMBED2_METADATA, Action2) &
                action.resubmit_table(TABLE_REDIRECT_CHASSIS, Action3) &
                (Action == Action1 + Action2 + Action3)
                )

    lrp_handle_unknow_dst_pkt(LR, Priority, Match, Action, State) <= (
        (Priority == 1) &
        lr_array(LR, UUID_LR, State) & (State != 0) &
        match.eth_dst("00:00:00:00:00:00", Match) &
        action.resubmit_table(TABLE_DROP_PACKET, Action)
        )

    lrp_handle_unknow_dst_pkt(LR, Priority, Match, Action, State) <= (
        (Priority == 0) &
        lr_array(LR, UUID_LR, State) & (State != 0) &
        match.match_none(Match) &
        action.resubmit_next(Action)
        )

    lrp_forward_packet(LR, Priority, Match, Action, State) <= (
        (Priority == 3) &
        lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR,
                     UUID_LR, UUID_LR_CHASSIS, State) & (State != 0) &
        match.reg_dst(LRP[LRP_PORTID], Match) &
        action.load(LS[LS_ID], NXM_Reg(REG_DP_IDX), Action1) &
        action.load(LSP[LSP_PORTID], NXM_Reg(REG_SRC_IDX), Action2) &
        action.resubmit_next(Action3) &
        (Action == Action1 + Action2 + Action3)
        )

