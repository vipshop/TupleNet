
NONE_IDX = 0

REG0_IDX = 1
REG1_IDX = 2
REG2_IDX = 3
REG3_IDX = 4
REG4_IDX = 5
REG5_IDX = 6
REG6_IDX = 7
REG7_IDX = 8
REG8_IDX = 9
REG9_IDX = 10
REG10_IDX = 11
REG11_IDX = 12
REG12_IDX = 13
REG13_IDX = 14
REG14_IDX = 15
REG15_IDX = 16

XREG0_IDX = 20
XREG1_IDX = 21
XREG2_IDX = 22
XREG3_IDX = 23
XREG4_IDX = 24
XREG5_IDX = 25
XREG6_IDX = 26
XREG7_IDX = 27

XXREG0_IDX = 30
XXREG1_IDX = 31
XXREG2_IDX = 32
XXREG3_IDX = 33

ETH_SRC_IDX = 40
ETH_DST_IDX = 41
ETH_TYPE_IDX = 42

VLAN_VID_IDX = 50
VLAN_PCP_IDX = 51
VLAN_TCI_IDX = 52

MPLS_LABEL_IDX = 60
MPLS_TC_IDX = 61
MPLS_BOS_IDX = 62
MPLS_TTL_IDX = 63

IP_SRC_IDX = 70
IP_DST_IDX = 71
IPV6_SRC_IDX = 72
IPV6_DST_IDX = 73
IPV6_LABEL_IDX = 74
IP_PROTO_IDX = 75
IP_TTL_IDX = 76
IP_FRAG_IDX = 77
IP_TOS_IDX = 78
IP_DSCP_IDX = 79
IP_ECN_IDX = 80

ARP_OP_IDX = 90
ARP_SPA_IDX = 91
ARP_TPA_IDX = 92
ARP_SHA_IDX = 93
ARP_THA_IDX = 94

TCP_SRC_IDX = 100
TCP_DST_IDX = 101
TCP_FLAGS_IDX = 102
UDP_SRC_IDX = 103
UDP_DST_IDX = 104
SCTP_SRC_IDX = 105
SCTP_DST_IDX = 106

ICMP_TYPE_IDX = 110
ICMP_CODE_IDX = 111
ICMPV6_TYPE_IDX = 112
ICMPV6_CODE_IDX = 113
ND_TAEGET_IDX = 114
ND_SLL_IDX = 115
ND_TLL_IDX = 116

ETH_PROTO_IDX = 200
IP_PROTO_IDX = 201
IPV6_PROTO_IDX = 202
ICMP_PROTO_IDX = 203
ICMP6_PROTO_IDX = 204
TCP_PROTO_IDX = 205
TCP6_PROTO_IDX = 206
UDP_PROTO_IDX = 207
UDP6_PROTO_IDX = 208
SCTP_PROTO_IDX = 29
SCTP6_PROTO_IDX = 210
ARP_PROTO_IDX = 211
RARP_PROTO_IDX = 212
MPLS_PROTO_IDX = 213
MPLSM_PROTO_IDX = 214

TUN_ID_IDX = 220
TUN_SRC_IDX = 221
TUN_DST_IDX = 222
TUN_IPV6_SRC_IDX = 223
TUN_IPV6_DST_IDX = 224
TUN_GBP_ID_IDX = 225
TUN_GBP_FLAGS_IDX = 226
TUN_FLAGS = 227

TUN_METADATA0_IDX = 230
TUN_METADATA1_IDX = 231
TUN_METADATA2_IDX = 232
TUN_METADATA3_IDX = 233
TUN_METADATA4_IDX = 234
TUN_METADATA5_IDX = 235
TUN_METADATA6_IDX = 236
TUN_METADATA7_IDX = 237
TUN_METADATA8_IDX = 238
TUN_METADATA9_IDX = 239

METADATA_IDX = 300
IN_PORT_IDX = 301
IN_PORT_OXM_IDX = 302
SKB_PRIORITY_IDX = 303
PKT_MARK_IDX = 304
ACTSET_OUTPUT_IDX = 305
PACKET_TYPE_IDX = 306

REG_DP_IDX = METADATA_IDX
REG_SRC_IDX = REG0_IDX
REG_DST_IDX = REG1_IDX
REG_FLAG_IDX = REG10_IDX
REG_DST_TUN_IP_IDX = REG11_IDX

REG_MATCH_DICT = {
          NONE_IDX:'',
          REG0_IDX:'reg0', REG1_IDX:'reg1', REG2_IDX:'reg2', REG3_IDX:'reg3',
          REG4_IDX:'reg4', REG5_IDX:'reg5', REG6_IDX:'reg6', REG7_IDX:'reg7',
          REG8_IDX:'reg8', REG9_IDX:'reg9',
          REG10_IDX:'reg10', REG11_IDX:'reg11', REG12_IDX:'reg12',
          REG13_IDX:'reg13', REG14_IDX:'reg14', REG15_IDX:'reg15',
          XREG0_IDX:'xreg0', XREG1_IDX:'xreg1', XREG2_IDX:'xreg2',
          XREG3_IDX:'xreg3', XREG4_IDX:'xreg4', XREG5_IDX:'xreg5',
          XREG6_IDX:'xreg6', XREG7_IDX:'xreg7',
          XXREG0_IDX:'xxreg0', XXREG1_IDX:'xxreg1',
          XXREG2_IDX:'xxreg2', XXREG3_IDX:'xxreg3',

          ETH_SRC_IDX:'eth_src', ETH_DST_IDX:'eth_dst', ETH_TYPE_IDX:'eth_type',

          VLAN_VID_IDX:'vlan_id', VLAN_PCP_IDX:'vlan_pcp',
          VLAN_TCI_IDX:'vlan_tci',

          MPLS_LABEL_IDX:'mpls_label', MPLS_TC_IDX:'mpls_tc',
          MPLS_BOS_IDX:'mpls_bos', MPLS_TTL_IDX:'mpls_ttl',

          IP_SRC_IDX:'ip_src', IP_DST_IDX:'ip_dst', IPV6_SRC_IDX:'ipv6_src',
          IPV6_DST_IDX:'ipv6_dst', IPV6_LABEL_IDX:'ipv6_label',
          IP_PROTO_IDX:'ip_proto', IP_TTL_IDX:'nw_ttl', IP_FRAG_IDX:'ip_frag',
          IP_TOS_IDX:'nw_tos', IP_DSCP_IDX:'ip_dscp', IP_ECN_IDX:'nw_ecn',

          ARP_OP_IDX:'arp_op', ARP_SPA_IDX:'arp_spa', ARP_TPA_IDX:'arp_tpa',
          ARP_SHA_IDX:'arp_sha', ARP_THA_IDX:'arp_tha',

          TCP_SRC_IDX:'tcp_src', TCP_DST_IDX:'tcp_dst',
          TCP_FLAGS_IDX:'tcp_flag', UDP_SRC_IDX:'udp_src',
          UDP_DST_IDX:'udp_dst', SCTP_SRC_IDX:'sctp_src',
          SCTP_DST_IDX:'sctp_dst',

          ICMP_TYPE_IDX:'icmp_type', ICMP_CODE_IDX:'icmp_code',
          ICMPV6_TYPE_IDX:'icmpv6_type', ICMPV6_CODE_IDX:'icmpv6_code',
          ND_TAEGET_IDX:'nd_target', ND_SLL_IDX:'nd_sll', ND_TLL_IDX:'nd_TLL',

          ETH_PROTO_IDX:'packet_type=(0,0)',
          IP_PROTO_IDX:'ip', IPV6_PROTO_IDX:'ipv6',
          ICMP_PROTO_IDX:'icmp', ICMP6_PROTO_IDX:'icmp6',
          TCP_PROTO_IDX:'tcp', TCP6_PROTO_IDX:'tcp6',
          UDP_PROTO_IDX:'udp', UDP6_PROTO_IDX:'udp6',
          SCTP_PROTO_IDX:'sctp', SCTP6_PROTO_IDX:'sctp6',
          ARP_PROTO_IDX:'arp', RARP_PROTO_IDX:'rarp',
          MPLS_PROTO_IDX:'mpls', MPLSM_PROTO_IDX:'mplsm',

          TUN_ID_IDX:'tun_id', TUN_SRC_IDX:'tun_src', TUN_DST_IDX:'tun_dst',
          TUN_IPV6_SRC_IDX:'tun_ipv6_src', TUN_IPV6_DST_IDX:'tun_ipv6_dst',
          TUN_GBP_ID_IDX:'tun_gbp_id', TUN_GBP_FLAGS_IDX:'tun_gbp_flags',
          TUN_FLAGS:'tun_flags',

          TUN_METADATA0_IDX:'tun_metadata0', TUN_METADATA1_IDX:'tun_metadata1',
          TUN_METADATA2_IDX:'tun_metadata2', TUN_METADATA3_IDX:'tun_metadata3',
          TUN_METADATA4_IDX:'tun_metadata4', TUN_METADATA5_IDX:'tun_metadata5',
          TUN_METADATA6_IDX:'tun_metadata6', TUN_METADATA7_IDX:'tun_metadata7',
          TUN_METADATA8_IDX:'tun_metadata8', TUN_METADATA9_IDX:'tun_metadata9',

          METADATA_IDX:'metadata', IN_PORT_IDX:'in_port',
          IN_PORT_OXM_IDX:'in_port_oxm', SKB_PRIORITY_IDX:'skb_priority',
          PKT_MARK_IDX:'pkt_mark', ACTSET_OUTPUT_IDX:'actset_output',
          PACKET_TYPE_IDX:'packet_type'
         }



REG_ACTION_DICT = {
          REG0_IDX:'NXM_NX_REG0', REG1_IDX:'NXM_NX_REG1',
          REG2_IDX:'NXM_NX_REG2', REG3_IDX:'NXM_NX_REG3',
          REG4_IDX:'NXM_NX_REG4', REG5_IDX:'NXM_NX_REG5',
          REG6_IDX:'NXM_NX_REG6', REG7_IDX:'NXM_NX_REG7',
          REG8_IDX:'NXM_NX_REG8', REG9_IDX:'NXM_NX_REG9',
          REG10_IDX:'NXM_NX_REG10', REG11_IDX:'NXM_NX_REG11',
          REG12_IDX:'NXM_NX_REG12', REG13_IDX:'NXM_NX_REG13',
          REG14_IDX:'NXM_NX_REG14', REG15_IDX:'NXM_NX_REG15',
          XREG0_IDX:'OXM_OF_PKT_REG0', XREG1_IDX:'OXM_OF_PKT_REG1',
          XREG2_IDX:'OXM_OF_PKT_REG2', XREG3_IDX:'OXM_OF_PKT_REG3',
          XREG4_IDX:'OXM_OF_PKT_REG4', XREG5_IDX:'OXM_OF_PKT_REG5',
          XREG6_IDX:'OXM_OF_PKT_REG6', XREG7_IDX:'OXM_OF_PKT_REG7',
          XXREG0_IDX:'NXM_NX_XXREG0', XXREG1_IDX:'NXM_NX_XXREG1',
          XXREG2_IDX:'NXM_NX_XXREG2', XXREG3_IDX:'NXM_NX_XXREG3',

          ETH_SRC_IDX:'NXM_OF_ETH_SRC', ETH_DST_IDX:'NXM_OF_ETH_DST',
          ETH_TYPE_IDX:'NXM_OF_ETH_TYPE',

          VLAN_VID_IDX:'OXM_OF_VLAN_VID', VLAN_PCP_IDX:'OXM_OF_VLAN_PCP',
          VLAN_TCI_IDX:'NXM_OF_VLAN_TCI',

          MPLS_LABEL_IDX:'OXM_OF_MPLS_LABEL', MPLS_TC_IDX:'OXM_OF_MPLS_TC',
          MPLS_BOS_IDX:'OXM_OF_MPLS_BOS', MPLS_TTL_IDX:'NXM_NX_MPLS_TTL',

          IP_SRC_IDX:'NXM_OF_IP_SRC', IP_DST_IDX:'NXM_OF_IP_DST',
          IPV6_SRC_IDX:'NXM_NX_IPV6_SRC', IPV6_DST_IDX:'NXM_NX_IPV6_DST',
          IPV6_LABEL_IDX:'NXM_NX_IPV6_LABEL', IP_PROTO_IDX:'NXM_OF_IP_PROTO',
          IP_TTL_IDX:'NXM_NX_IP_TTL', IP_FRAG_IDX:'NXM_NX_IP_FRAG',
          IP_TOS_IDX:'NXM_OF_IP_TOS', IP_DSCP_IDX:'OXM_OF_IP_DSCP',
          IP_ECN_IDX:'NXM_NX_IP_ECN',

          ARP_OP_IDX:'NXM_OF_ARP_OP', ARP_SPA_IDX:'NXM_OF_ARP_SPA',
          ARP_TPA_IDX:'NXM_OF_ARP_TPA', ARP_SHA_IDX:'NXM_NX_ARP_SHA',
          ARP_THA_IDX:'NXM_NX_ARP_THA',

          TCP_SRC_IDX:'NXM_OF_TCP_SRC', TCP_DST_IDX:'NXM_OF_TCP_DST',
          TCP_FLAGS_IDX:'NXM_NX_TCP_FLAGS', UDP_SRC_IDX:'NXM_OF_UDP_SRC',
          UDP_DST_IDX:'NXM_OF_UDP_DST', SCTP_SRC_IDX:'OXM_OF_SCTP_SRC',
          SCTP_DST_IDX:'OXM_OF_SCTP_DST',

          ICMP_TYPE_IDX:'NXM_OF_ICMP_TYPE', ICMP_CODE_IDX:'NXM_OF_ICMP_CODE',
          ICMPV6_TYPE_IDX:'NXM_NX_ICMPV6_TYPE',
          ICMPV6_CODE_IDX:'NXM_NX_ICMPV6_CODE',
          ND_TAEGET_IDX:'NXM_NX_ND_TARGET', ND_SLL_IDX:'NXM_NX_ND_SLL',
          ND_TLL_IDX:'NXM_NX_ND_TLL',

          TUN_ID_IDX:'NXM_NX_TUN_ID', TUN_SRC_IDX:'NXM_NX_TUN_IPV4_SRC',
          TUN_DST_IDX:'NXM_NX_TUN_IPV4_DST',
          TUN_IPV6_SRC_IDX:'NXM_NX_TUN_IPV6_SRC',
          TUN_IPV6_DST_IDX:'NXM_NX_TUN_IPV6_DST',
          TUN_GBP_ID_IDX:'NXM_NX_TUN_GBP_ID',
          TUN_GBP_FLAGS_IDX:'NXM_NX_TUN_GBP_FLAGS',
          TUN_FLAGS:'NXM_NX_TUN_FLAGS',

          TUN_METADATA0_IDX:'NXM_NX_TUN_METADATA0',
          TUN_METADATA1_IDX:'NXM_NX_TUN_METADATA1',
          TUN_METADATA2_IDX:'NXM_NX_TUN_METADATA2',
          TUN_METADATA3_IDX:'NXM_NX_TUN_METADATA3',
          TUN_METADATA4_IDX:'NXM_NX_TUN_METADATA4',
          TUN_METADATA5_IDX:'NXM_NX_TUN_METADATA5',
          TUN_METADATA6_IDX:'NXM_NX_TUN_METADATA6',
          TUN_METADATA7_IDX:'NXM_NX_TUN_METADATA7',
          TUN_METADATA8_IDX:'NXM_NX_TUN_METADATA8',
          TUN_METADATA9_IDX:'NXM_NX_TUN_METADATA9',

          METADATA_IDX:'OXM_OF_METADATA', IN_PORT_IDX:'NXM_OF_IN_PORT',
          IN_PORT_OXM_IDX:'UNKNOW', SKB_PRIORITY_IDX:'UNKNOW',
          PKT_MARK_IDX:'NXM_NX_PKT_MARK',
          ACTSET_OUTPUT_IDX:'OXM_OF_ACTSET_OUTPUT',
          PACKET_TYPE_IDX:'OXM_OF_PACKET_TYPE'
        }

# Reg10[0..7] is for flags of packet
# Reg10[8..15] is for seq of pkt-trace
# Reg10[16..31] is for cmd_id
# loopback occupies first bit
# NOTE: do not change to order of flag bits
FLAG_LOOPBACK = 1
FLAG_LOOPBACK_BIT_IDX = 0
# tracing packet occupies second bit
FLAG_TRACE = 2
FLAG_TRACE_BIT_IDX = 1
# redirect packet occupies third bit
FLAG_REDIRECT = 4
FLAG_REDIRECT_BIT_IDX = 2
# NAT packet occupies fourth bit
FLAG_NAT = 8
FLAG_NAT_BIT_IDX = 3

class NXM_Reg():
    def __init__(self, idx, start=0, end=-1):
        self.idx = idx
        self.start = start
        self.end = end

    def __repr__(self):
        if self.end == -1:
            return '{name}[]'.format(name = REG_ACTION_DICT[self.idx])
        return '{name}[{start}..{end}]'.format(name = REG_ACTION_DICT[self.idx],
                                              start = self.start,
                                              end = self.end)
