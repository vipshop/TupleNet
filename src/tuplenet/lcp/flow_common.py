#pyhical flows, it should be in table 0
TABLE_CONVERT_PHY_LOGICAL = 0
# LSP pipeline
TABLE_LSP_TRACE_INGRESS_IN = 1
TABLE_LSP_INGRESS_PROCESS_EXT_LOGIC = 2
TABLE_LSP_INGRESS_ARP_CONTROLLER = 3
TABLE_LSP_INGRESS_ARP_RESPONSE = 4
TABLE_LSP_INGRESS_UNTUNNEL = 5
TABLE_LSP_INGRESS_LOOKUP_DST_PORT = 6
TABLE_LSP_INGRESS_OUTPUT_DST_PORT = 7
TABLE_LSP_TRACE_INGRESS_OUT = 7 # same to TABLE_LSP_INGRESS_OUTPUT_DST_PORT

TABLE_LSP_TRACE_EGRESS_IN = 20
TABLE_LSP_EGRESS_JUDGE_LOOPBACK = 21
TABLE_LSP_EGRESS_FORWARD_PACKET = 22
TABLE_LSP_EGRESS_PUSHOUT = 23
TABLE_LSP_TRACE_EGRESS_OUT = 23

TABLE_LSP_INGRESS_FIRST = TABLE_LSP_TRACE_INGRESS_IN
TABLE_LSP_EGRESS_FIRST = TABLE_LSP_TRACE_EGRESS_IN

# LRP pipeline
TABLE_LRP_TRACE_INGRESS_IN = 30
TABLE_LRP_INGRESS_PKT_RESPONSE = 31
TABLE_LRP_INGRESS_DROP_UNEXPECT = 32
TABLE_LRP_INGRESS_UNSNAT_STAGE1 = 33
TABLE_LRP_INGRESS_UNSNAT_STAGE2 = 34
TABLE_LRP_INGRESS_DNAT_STAGE1 = 35
TABLE_LRP_INGRESS_DNAT_STAGE2 = 36
TABLE_LRP_INGRESS_IP_ROUTE = 37
TABLE_LRP_INGRESS_ECMP = 38
TABLE_LRP_TRACE_INGRESS_OUT = 39

TABLE_LRP_TRACE_EGRESS_IN = 50
TABLE_LRP_EGRESS_UNDNAT_STAGE1 = 51
TABLE_LRP_EGRESS_UNDNAT_STAGE2 = 52
TABLE_LRP_EGRESS_SNAT_STAGE1 = 53
TABLE_LRP_EGRESS_SNAT_STAGE2 = 54
TABLE_LRP_EGRESS_UPDATE_ETH_DST = 55
TABLE_LRP_EGRESS_HANDLE_UNK_PKT = 56
TABLE_LRP_EGRESS_FORWARD_PACKET = 57
TABLE_LRP_TRACE_EGRESS_OUT = 58

TABLE_LRP_INGRESS_FIRST = TABLE_LRP_TRACE_INGRESS_IN
TABLE_LRP_EGRESS_FIRST = TABLE_LRP_TRACE_EGRESS_IN

# Independent table
TABLE_OUTPUT_PKT = 94
TABLE_REDIRECT_CHASSIS = 95
TABLE_ARP_FEEDBACK_CONSTRUCT = 96
TABLE_EMBED2_METADATA = 97
TABLE_EXTRACT_METADATA = 98
TABLE_PIPELINE_FORWARD = 99
TABLE_SEARCH_IP_MAC = 100
TABLE_DROP_PACKET = 101

# third-party table
TABLE_THIRD_PARTY = 201

flows_note_array = ['lsp_lookup_dst_port',
                    'lsp_output_dst_port',
                    'lsp_pushout_packet',
                    'lsp_arp_controller',
                    'lsp_arp_response',
                    'lsp_untunnel_deliver',
                    'convert_phy_logical',
                    'lsp_judge_loopback',
                    'lsp_forward_packet',
                    'lrp_pkt_response',
                    'lrp_drop_unexpect',
                    'lrp_ip_route',
                    'lrp_ip_unsnat_stage1',
                    'lrp_ip_unsnat_stage2',
                    'lrp_ip_dnat_stage1',
                    'lrp_ip_dnat_stage2',
                    'lrp_ecmp_judge',
                    'lrp_update_eth_dst',
                    'lrp_ip_undnat_stage1',
                    'lrp_ip_undnat_stage2',
                    'lrp_ip_snat_stage1',
                    'lrp_ip_snat_stage2',
                    'lrp_handle_unknow_dst_pkt',
                    'lrp_forward_packet',
                    'pkt_trace_lsp_ingress_in',
                    'pkt_trace_lsp_lookup_dst_port',
                    'pkt_trace_lsp_output_dst_port',
                    'pkt_trace_lsp_pushout_packet',
                    'pkt_trace_lsp_egress_in',
                    'pkt_trace_lsp_forward_packet',
                    'pkt_trace_lrp_ingress_in',
                    'pkt_trace_lrp_ingress_out',
                    'pkt_trace_lrp_egress_in',
                    'pkt_trace_lrp_egress_out',
                    'pkt_trace_drop_packet',
                    'pkt_trace_output_pkt',
                    'arp_feedback_construct',
                    'embed_metadata',
                    'extract_metadata',
                    'pipeline_forward',
                    'redirect_other_chassis',
                    'output_pkt',
                    'process_third_logic',
                   ]

START_IDX = 10
flow_note_dict = {}
for i in xrange(len(flows_note_array)):
    flow_note_dict[flows_note_array[i]] = i + START_IDX

def flows_note2idx(note):
    return flow_note_dict[note]

def flows_idx2note(idx):
    idx -= START_IDX
    return flows_note_array[idx]

table_note_dict = {
    TABLE_CONVERT_PHY_LOGICAL:'TABLE_CONVERT_PHY_LOGICAL',
    TABLE_LSP_TRACE_INGRESS_IN:'TABLE_LSP_TRACE_INGRESS_IN',
    TABLE_LSP_INGRESS_PROCESS_EXT_LOGIC:'TABLE_LSP_INGRESS_PROCESS_EXT_LOGIC',
    TABLE_LSP_INGRESS_ARP_RESPONSE:'TABLE_LSP_INGRESS_ARP_RESPONSE',
    TABLE_LSP_INGRESS_ARP_CONTROLLER:'TABLE_LSP_INGRESS_ARP_CONTROLLER',
    TABLE_LSP_INGRESS_UNTUNNEL:'TABLE_LSP_INGRESS_UNTUNNEL',
    TABLE_LSP_INGRESS_LOOKUP_DST_PORT:'TABLE_LSP_INGRESS_LOOKUP_DST_PORT',
    TABLE_LSP_TRACE_INGRESS_OUT:'TABLE_LSP_TRACE_INGRESS_OUT',
    TABLE_LSP_TRACE_EGRESS_IN:'TABLE_LSP_TRACE_EGRESS_IN',
    TABLE_LSP_EGRESS_JUDGE_LOOPBACK:'TABLE_LSP_EGRESS_JUDGE_LOOPBACK',
    TABLE_LSP_EGRESS_FORWARD_PACKET:'TABLE_LSP_EGRESS_FORWARD_PACKET',
    TABLE_LSP_TRACE_EGRESS_OUT:'TABLE_LSP_TRACE_EGRESS_OUT',
    TABLE_LRP_TRACE_INGRESS_IN:'TABLE_LRP_TRACE_INGRESS_IN',
    TABLE_LRP_INGRESS_PKT_RESPONSE:'TABLE_LRP_INGRESS_PKT_RESPONSE',
    TABLE_LRP_INGRESS_DROP_UNEXPECT:'TABLE_LRP_INGRESS_DROP_UNEXPECT',
    TABLE_LRP_INGRESS_UNSNAT_STAGE1:'TABLE_LRP_INGRESS_UNSNAT_STAGE1',
    TABLE_LRP_INGRESS_UNSNAT_STAGE2:'TABLE_LRP_INGRESS_UNSNAT_STAGE2',
    TABLE_LRP_INGRESS_DNAT_STAGE1:'TABLE_LRP_INGRESS_DNAT_STAGE1',
    TABLE_LRP_INGRESS_DNAT_STAGE2:'TABLE_LRP_INGRESS_DNAT_STAGE2',
    TABLE_LRP_INGRESS_IP_ROUTE:'TABLE_LRP_INGRESS_IP_ROUTE',
    TABLE_LRP_INGRESS_ECMP:'TABLE_LRP_INGRESS_ECMP',
    TABLE_LRP_TRACE_INGRESS_OUT:'TABLE_LRP_TRACE_INGRESS_OUT',
    TABLE_LRP_TRACE_EGRESS_IN:'TABLE_LRP_TRACE_EGRESS_IN',
    TABLE_LRP_EGRESS_UNDNAT_STAGE1:'TABLE_LRP_EGRESS_UNDNAT_STAGE1',
    TABLE_LRP_EGRESS_UNDNAT_STAGE2:'TABLE_LRP_EGRESS_UNDNAT_STAGE2',
    TABLE_LRP_EGRESS_SNAT_STAGE1:'TABLE_LRP_EGRESS_SNAT_STAGE1',
    TABLE_LRP_EGRESS_SNAT_STAGE2:'TABLE_LRP_EGRESS_SNAT_STAGE2',
    TABLE_LRP_EGRESS_UPDATE_ETH_DST:'TABLE_LRP_EGRESS_UPDATE_ETH_DST',
    TABLE_LRP_EGRESS_HANDLE_UNK_PKT:'TABLE_LRP_EGRESS_HANDLE_UNK_PKT',
    TABLE_LRP_EGRESS_FORWARD_PACKET:'TABLE_LRP_EGRESS_FORWARD_PACKET',
    TABLE_LRP_TRACE_EGRESS_OUT:'TABLE_LRP_TRACE_EGRESS_OUT',
    TABLE_OUTPUT_PKT:'TABLE_OUTPUT_PKT',
    TABLE_SEARCH_IP_MAC:'TABLE_SEARCH_IP_MAC',
    TABLE_DROP_PACKET:'TABLE_DROP_PACKET',
    TABLE_THIRD_PARTY:'TABLE_THIRD_PARTY',
}
