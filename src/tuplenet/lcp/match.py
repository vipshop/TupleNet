from pyDatalog import pyDatalog
from reg import *

pyDatalog.create_terms('X, Y, Z')

pyDatalog.create_terms('match_none')
pyDatalog.create_terms('datapath')
pyDatalog.create_terms('in_port')
pyDatalog.create_terms('reg_src')
pyDatalog.create_terms('reg_dst')
pyDatalog.create_terms('reg_flag')
pyDatalog.create_terms('reg_2')
pyDatalog.create_terms('reg_3')
pyDatalog.create_terms('reg_4')
pyDatalog.create_terms('reg_5')
pyDatalog.create_terms('reg_6')
pyDatalog.create_terms('reg_7')
pyDatalog.create_terms('reg_8')
pyDatalog.create_terms('reg_9')
pyDatalog.create_terms('reg_10')
pyDatalog.create_terms('reg_11')
pyDatalog.create_terms('ip_proto')
pyDatalog.create_terms('ip_dst, ip_src')
pyDatalog.create_terms('ip_dst_prefix, ip_src_prefix')
pyDatalog.create_terms('ip_ttl')
pyDatalog.create_terms('eth_dst')
pyDatalog.create_terms('arp_proto')
pyDatalog.create_terms('arp_tpa')
pyDatalog.create_terms('arp_op')

pyDatalog.create_terms('icmp_proto, icmp_type, icmp_code')

def init_match_clause():
    match_none(X) <= (X == [(NONE_IDX, )])

    datapath(X, Y) <= (Y == [(REG_DP_IDX, X)])

    in_port(X, Y) <= (Y == [(IN_PORT_IDX, X)])

    reg_2(X, Y) <= (Y == [(REG2_IDX, X)])

    reg_3(X, Y) <= (Y == [(REG3_IDX, X)])

    reg_4(X, Y) <= (Y == [(REG4_IDX, X)])

    reg_5(X, Y) <= (Y == [(REG5_IDX, X)])

    reg_6(X, Y) <= (Y == [(REG6_IDX, X)])

    reg_7(X, Y) <= (Y == [(REG7_IDX, X)])

    reg_8(X, Y) <= (Y == [(REG8_IDX, X)])

    reg_9(X, Y) <= (Y == [(REG9_IDX, X)])

    reg_10(X, Y) <= (Y == [(REG10_IDX, X)])

    reg_src(X, Y) <= (Y == [(REG_SRC_IDX, X)])

    reg_dst(X, Y) <= (Y == [(REG_DST_IDX, X)])

    reg_flag(X, Y) <= (Y == [(REG_FLAG_IDX, X)])

    ip_proto(X) <= (X == [(IP_PROTO_IDX, )])

    ip_dst(X, Y) <= (Y == [(IP_DST_IDX, X)])

    ip_src(X, Y) <= (Y == [(IP_SRC_IDX, X)])

    ip_dst_prefix (X, Y, Z) <= (Z == [(IP_DST_IDX, X, Y)])

    ip_src_prefix (X, Y, Z) <= (Z == [(IP_SRC_IDX, X, Y)])

    ip_ttl(X, Y) <= (Y == [(IP_TTL_IDX, X)])

    eth_dst(X, Y) <= (Y == [(ETH_DST_IDX, X)])

    arp_proto(X) <= (X == [(ARP_PROTO_IDX, )])

    arp_tpa(X, Y) <= (Y == [(ARP_TPA_IDX, X)])

    arp_op(X, Y) <= (Y == [(ARP_OP_IDX, X)])

    icmp_proto(X) <= (X == [(ICMP_PROTO_IDX, )])

    icmp_type(X, Y) <= (Y == [(ICMP_TYPE_IDX, X)])

    icmp_code(X, Y) <= (Y == [(ICMP_CODE_IDX, X)])

def convert_flags(flags):
    # e.g flag = 1 means it occupies the first bit
    # and flag = 4 means it occupies the third bit
    sumflag = sum(flags)
    return '{}/{}'.format(sumflag, sumflag)

def convert_tuple2match(match_tuple):
    opcode_array = []
    prev_flags = []
    for match_exp in match_tuple:
        match_type = match_exp[0]
        if len(match_exp) >= 2:
            match_parameter1 = match_exp[1]
        if match_type == REG_FLAG_IDX:
            # REG_FLAG_IDX match should get at least one parameter
            prev_flags.append(match_parameter1)
            # we change match_parameter1 here,
            # and the below code will consume it
            match_parameter1 = convert_flags(prev_flags)

        exp = REG_MATCH_DICT[match_type]
        if len(match_exp) == 2:
            exp += '=' + str(match_parameter1)
        elif len(match_exp) == 3:
            # like ip_dst = xx.xx.xx.xx/16
            match_parameter2 = match_exp[2]
            exp += '=' + str(match_parameter1) + '/' + str(match_parameter2)
        opcode_array.append(exp)

    return ','.join(opcode_array)

