from pyDatalog import pyDatalog
from tp_utils import run_env
hash_fn = run_env.get_extra()['options']['HASH_FN']

Action_output = 1
Action_output_reg = 2
Action_output_max_len = 3
Action_output_group = 4
Action_normal = 5
Action_flood = 6
Action_all = 7
Action_local = 8
Action_output_inport = 9

Action_enqueue = 20
Action_drop = 21

Action_mod_vlan_vid = 31
Acton_mod_vlan_pcp = 32
Action_strip_vlan = 33
Action_push_vlan = 34
Action_push_mpls = 35
Action_pop_mpls = 36

Action_mod_dl_src = 40
Action_mod_dl_dst = 41
Action_mod_nw_src = 42
Action_mod_nw_dst = 43
Action_mod_nw_tos = 44
Action_mod_nw_ecn = 45
Action_mod_nw_ttl = 46
Action_mod_tp_src = 47
Action_mod_tp_dst = 48

Action_resubmit = 50
Action_resubmit_table = 51
Action_resubmit_ct = 52

Action_set_tunnel = 60
Action_set_tunnel64 = 61
Action_set_queue = 62
Action_pop_queue = 63

Action_ct = 70

Action_dec_ttl = 80
Action_set_mpls_label = 81
Action_set_mpls_tc = 82
Action_set_mpls_ttl = 83
Action_dec_mpls_ttl = 84

Action_note = 90

Action_move = 100
Action_load = 101
Action_push = 102
Action_pop = 103

Action_multipath = 110
Action_bundle = 111
Action_bundle_load = 112

Action_learn = 120
Action_clear_actions = 121
Action_write_actions = 122

Action_write_metadata = 130
Action_meter = 131
Action_goto_table = 132
Action_fin_timeout = 133
Action_sample = 134
Action_exit = 135
Action_conjunction = 136
Action_clone = 137
Action_encap = 138
Action_decap = 139

Action_set_bit = 200
Action_clear_bit = 201
Action_resubmit_next = 202
Action_exchange = 203
Action_upload_arp = 204
Action_generate_arp = 205
Action_upload_trace = 206
Action_upload_unknow_dst = 207
Action_snat = 208
Action_unsnat = 209
Action_dnat = 210
Action_undnat = 211

ACTION_STR_MAP = {
        Action_output:'output:{}',
        Action_output_reg:'output:{}',
        Action_drop:'drop',
        Action_mod_dl_src:'mod_dl_src:{}',
        Action_mod_dl_dst:'mod_dl_dst:{}',
        Action_mod_nw_src:'mod_nw_src:{}',
        Action_mod_nw_dst:'mod_nw_dst:{}',
        Action_mod_nw_ttl:'mod_nw_ttl:{}',
        Action_dec_ttl:'dec_ttl',
        Action_mod_tp_dst:'mod_tp_dst:{}',
        Action_mod_tp_src:'mod_tp_src:{}',

        Action_resubmit:'resubmit({},{})',
        Action_resubmit_table:'resubmit(,{})',

        Action_move:'move:{}->{}',
        Action_load:'load:{}->{}',
        Action_push:'push:{}',
        Action_pop:'pop:{}',

        Action_snat:'ct(commit,nat(src={}),table={})',
        Action_unsnat:'ct(nat,table={})',
        Action_dnat:'ct(commit,nat(dst={}),table={})',
        Action_undnat:'ct(nat,table={})',

        Action_bundle:'bundle({},0,active_backup,ofport,slaves:{{}})'.format(hash_fn),
        Action_bundle_load:'bundle_load({},0,hrw,ofport,{{}},slaves:{{}})'.format(hash_fn),

        Action_note:'note:{:02x}',

        #self define
        Action_resubmit_next:'resubmit(,{})',
        Action_exchange:'push:{},push:{},pop:{},pop:{}',
        Action_upload_arp:'controller(userdata=00.00.00.01.00.00.00.00)',
        Action_generate_arp:'controller(userdata=00.00.00.02.00.00.00.00.ff.ff.00.10.00.00.23.20.00.0e.ff.f8.{:02x}.00.00.00)',
        Action_upload_trace:'controller(userdata=00.00.00.03.00.00.00.{:02x},pause)',
        Action_upload_unknow_dst:'controller(userdata=00.00.00.04.00.00.00.00)',
        }


pyDatalog.create_terms('A, B, C, D, E, F, G, H, I, J, K, L, N, M, O, P, Q, R, S, T, U, V, W, X, Y, Z')
pyDatalog.create_terms('resubmit_table')
pyDatalog.create_terms('move')
pyDatalog.create_terms('load')
pyDatalog.create_terms('output')
pyDatalog.create_terms('output_reg')
pyDatalog.create_terms('bundle')
pyDatalog.create_terms('bundle_load')
pyDatalog.create_terms('drop')
pyDatalog.create_terms('mod_nw_dst')
pyDatalog.create_terms('mod_nw_src')
pyDatalog.create_terms('mod_dl_src')
pyDatalog.create_terms('mod_dl_dst')
pyDatalog.create_terms('mod_nw_tos')
pyDatalog.create_terms('mod_nw_ecn')
pyDatalog.create_terms('mod_nw_ttl')
pyDatalog.create_terms('dec_ttl')
pyDatalog.create_terms('mod_nw_tp_src')
pyDatalog.create_terms('mod_nw_tp_dst')
pyDatalog.create_terms('note')
pyDatalog.create_terms('push')

#self define
pyDatalog.create_terms('resubmit_next')
pyDatalog.create_terms('exchange')
pyDatalog.create_terms('upload_arp')
pyDatalog.create_terms('generate_arp')
pyDatalog.create_terms('upload_trace')
pyDatalog.create_terms('upload_unknow_dst')
pyDatalog.create_terms('snat, unsnat, dnat, undnat')

def init_action_clause():

    resubmit_table(X, Y) <= (Y == [(Action_resubmit_table, X)])

    move(X, Y, Z) <= (Z == [(Action_move, X, Y)])

    load(X, Y, Z) <= (Z == [(Action_load, X, Y)])

    output(X, Y) <= (Y == [(Action_output, X)])

    output_reg(X, Y) <= (Y == [(Action_output_reg, X)])

    bundle(X, Y) <= (Y == [(Action_bundle, X)])

    bundle_load(X, Y, Z) <= (Z == [(Action_bundle_load, X, Y)])

    drop(X) <= (X == [(Action_drop, )])

    mod_nw_dst(X, Y) <= (Y==[(Action_mod_nw_dst, X)])

    mod_nw_src(X, Y) <= (Y==[(Action_mod_nw_src, X)])

    mod_dl_src(X, Y) <= (Y==[(Action_mod_dl_src, X)])

    mod_dl_dst(X, Y) <= (Y==[(Action_mod_dl_dst, X)])

    mod_nw_tos(X, Y) <= (Y==[(Action_mod_nw_tos, X)])

    mod_nw_ecn(X, Y) <= (Y==[(Action_mod_nw_ecn, X)])

    mod_nw_ttl(X, Y) <= (Y==[(Action_mod_nw_ttl, X)])

    note(X, Y) <= (Y == [(Action_note, X)])

    dec_ttl(X) <= (X == [(Action_dec_ttl, )])

    mod_nw_tp_src(X, Y) <= (Y==[(Action_mod_tp_src, X)])

    mod_nw_tp_dst(X, Y) <= (Y==[(Action_mod_tp_dst, X)])

    push(X, Y) <= (Y == [(Action_push, X)])

    resubmit_next(X) <= (X == [(Action_resubmit_next, )])

    exchange(X, Y, Z) <= (Z == [(Action_exchange, X, Y)])

    upload_arp(X) <= (X == [(Action_upload_arp, )])

    upload_trace(X) <= (X == [(Action_upload_trace, )])

    upload_unknow_dst(X) <= (X == [(Action_upload_unknow_dst, )])

    generate_arp(X, Y) <= (Y == [(Action_generate_arp, X)])

    snat(X, Y, Z) <= (Z == [(Action_snat, X, Y)])

    unsnat(X, Y) <= (Y == [(Action_unsnat, X)])

    dnat(X, Y, Z) <= (Z == [(Action_dnat, X, Y)])

    undnat(X, Y) <= (Y == [(Action_undnat, X)])


#self define action, set_bit(regX, bit_idx)
pyDatalog.create_terms('set_bit')
set_bit(X, Y, Z) <= (Z==[(Action_set_bit, X, Y)])

#self define action, clear_bit(regX, bit_idx)
pyDatalog.create_terms('clear_bit')
clear_bit(X, Y, Z) <= (Z==[(Action_clear_bit, X, Y)])



def parse_action_tuple(action_tuple, cur_table):
    action = ACTION_STR_MAP[action_tuple[0]]
    if action_tuple[0] == Action_resubmit_next:
        action = action.format(cur_table + 1)
    elif action_tuple[0] == Action_exchange:
        action = action.format(action_tuple[1], action_tuple[2],
                               action_tuple[1], action_tuple[2])
    elif action_tuple[0] == Action_bundle:
        action = action.format(",".join(str(n) for n in action_tuple[1]))
    elif action_tuple[0] == Action_bundle_load:
        action = action.format(action_tuple[1], ",".join(str(n) for n in action_tuple[2]))
    elif action_tuple[0] == Action_upload_trace:
        action = action.format(cur_table)
    elif len(action_tuple) > 1:
        action = action.format(*action_tuple[1:])
    return action

def convert_tuple2action(action_tuple, table):
    opcode_array = []
    for action_exp in action_tuple:
        exp = parse_action_tuple(action_exp, table)
        opcode_array.append(exp)
    return ','.join(opcode_array)

