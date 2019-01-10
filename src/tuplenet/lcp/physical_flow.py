from pyDatalog import pyDatalog
import action
import match
from reg import *
from logicalview import *
from flow_common import TABLE_PIPELINE_FORWARD, TABLE_EXTRACT_METADATA

pyDatalog.create_terms('Table, Priority, Match, Action')
pyDatalog.create_terms('Action1, Action2, Action3, Action4, Action5')
pyDatalog.create_terms('Action6, Action7, Action8, Action9')
pyDatalog.create_terms('Match1, Match2, Match3, Match4, Match5')
pyDatalog.create_terms('X, Y, Z, UUID_CHASSIS')

pyDatalog.create_terms('convert_phy_logical')
pyDatalog.create_terms('arp_feedback_construct')
pyDatalog.create_terms('output_pkt_by_reg')
pyDatalog.create_terms('_arp_ip_mac')
pyDatalog.create_terms('IP, IP_INT, MAC, MAC_INT')

def init_physical_flow_clause(options):

    # handle tunnel port ingress traffic
    convert_phy_logical(Priority, Match, Action, State) <= (
        (Priority == 2) &
        remote_chassis(UUID_CHASSIS, PHY_CHASSIS, State) & (State != 0) &
        match.in_port(PHY_CHASSIS[PCH_OFPORT], Match) &
        action.resubmit_table(TABLE_EXTRACT_METADATA, Action1) &
        action.load(1, NXM_Reg(REG_FLAG_IDX, FLAG_LOOPBACK_BIT_IDX,
                               FLAG_LOOPBACK_BIT_IDX),
                    Action2) &
        action.resubmit_table(TABLE_PIPELINE_FORWARD, Action3) &
        (Action == Action1 + Action2 + Action3)
        )

    # handle regular port ingress traffic
    convert_phy_logical(Priority, Match, Action, State) <= (
        (Priority == 2) &
        local_bond_lsp(LSP, LS, State) & (State != 0) &
        match.in_port(LSP[LSP_OFPORT], Match) &
        action.load(LSP[LSP_PORTID],
                    NXM_Reg(REG_SRC_IDX), Action1) &
        action.load(LS[LS_ID], NXM_Reg(REG_DP_IDX), Action2) &
        action.resubmit_next(Action3) &
        (Action == Action1 + Action2 + Action3)
        )

    # it helps reduce time-cost
    _arp_ip_mac(IP, IP_INT, MAC, MAC_INT, LS, State) <= (
        active_lsp(LSP, LS, UUID_LS, State) &
        (State != 0) &
        (IP == LSP[LSP_IP]) & (IP_INT == LSP[LSP_IP_INT]) &
        (MAC == LSP[LSP_MAC]) & (MAC_INT == LSP[LSP_MAC_INT])
        )

    _arp_ip_mac(IP, IP_INT, MAC, MAC_INT, LS, State) <= (
        lnat_data(LNAT, LR, XLATE_TYPE, UUID_LR, State1) &
        lsp_link_lrp(LSP, LS, UUID_LS, LRP, LR, UUID_LR, UUID_LR_CHASSIS, State2) &
        (State == State1 + State2) & (State != 0) &
        (IP == LNAT[LNAT_XLATE_IP]) & (IP_INT ==  LNAT[LNAT_XLATE_IP_INT]) &
        (MAC == LNAT[LNAT_XLATE_MAC]) & (MAC_INT ==  LNAT[LNAT_XLATE_MAC_INT])
        )
    # regular lsp arp feedback
    arp_feedback_construct(LS, Priority, Match, Action, State) <= (
        (Priority == 0) &
        _arp_ip_mac(IP, IP_INT, MAC, MAC_INT, LS, State) &
        match.arp_proto(Match1) &
        match.arp_tpa(IP, Match2) &
        match.arp_op(1, Match3) &
        (Match == Match1 + Match2 + Match3) &
        action.load(1, NXM_Reg(REG_FLAG_IDX, FLAG_LOOPBACK_BIT_IDX,
                               FLAG_LOOPBACK_BIT_IDX), Action1) &
        action.move(NXM_Reg(ETH_SRC_IDX), NXM_Reg(ETH_DST_IDX), Action2) &
        action.mod_dl_src(MAC, Action3) &
        action.load(2, NXM_Reg(ARP_OP_IDX), Action4) &
        action.move(NXM_Reg(ARP_SHA_IDX), NXM_Reg(ARP_THA_IDX), Action5) &
        action.load(MAC_INT,
                    NXM_Reg(ARP_SHA_IDX), Action6) &
        action.move(NXM_Reg(ARP_SPA_IDX), NXM_Reg(ARP_TPA_IDX), Action7) &
        action.load(IP_INT,
                    NXM_Reg(ARP_SPA_IDX), Action8) &
        action.move(NXM_Reg(REG_SRC_IDX), NXM_Reg(REG_DST_IDX), Action9) &
        (Action == Action1 + Action2 + Action3 + Action4 +
                   Action5 + Action6 + Action7 + Action8 + Action9)
        )

    output_pkt_by_reg(Priority, Match, Action) <= (
        (Priority == 0) &
        match.match_none(Match) &
        action.output_reg(NXM_Reg(REG_OUTPORT_IDX), Action)
        )

