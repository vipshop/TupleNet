import os, sys
import random
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ppparent_dir = os.path.dirname(os.path.dirname(parent_dir))
py_third_dir = os.path.join(ppparent_dir, 'py_third')
sys.path.append(parent_dir)
sys.path.append(ppparent_dir)
sys.path.append(py_third_dir)

from pyDatalog import pyDatalog, Logic, pyEngine
from pyDatalog.pyDatalog import assert_fact, load, ask
from logicalview import *
import lflow
from tp_utils import run_env
import time
import sys
import ecmp
import tunnel
from tp_utils.run_env import get_extra
import lsp_ingress, lsp_egress, lrp_ingress, lrp_egress, physical_flow
import middle_table as mid
import logging
logging.basicConfig(level = logging.INFO,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("performance")
pyDatalog.create_terms('Table, Priority, Match, Action, State')
pyDatalog.create_terms('A,B,C,D,E,F,G,H,I,J,K,X,Y,Z')

lsp_ingress_flows = {
                     'lsp_arp_response':lsp_ingress.lsp_arp_response,
                     'lsp_arp_controller':lsp_ingress.lsp_arp_controller,
                     'lsp_untunnel_deliver':lsp_ingress.lsp_untunnel_deliver,
                     'lsp_lookup_dst_port':lsp_ingress.lsp_lookup_dst_port,
                     'lsp_output_dst_port':lsp_ingress.lsp_output_dst_port,
                    }

lsp_egress_flows = {'lsp_judge_loopback':lsp_egress.lsp_judge_loopback,
                     'lsp_forward_packet':lsp_egress.lsp_forward_packet,
                     'lsp_pushout_packet':lsp_egress.lsp_pushout_packet,
                    }

lrp_ingress_flows = {'lrp_pkt_response':lrp_ingress.lrp_pkt_response,
                     'lrp_drop_unexpect':lrp_ingress.lrp_drop_unexpect,
                     'lrp_ecmp_judge':lrp_ingress.lrp_ecmp_judge,
                     'lrp_ip_route':lrp_ingress.lrp_ip_route,
                     'lrp_ip_unsnat_stage1':lrp_ingress.lrp_ip_unsnat_stage1,
                     'lrp_ip_unsnat_stage2':lrp_ingress.lrp_ip_unsnat_stage2,
                     'lrp_ip_dnat_stage1':lrp_ingress.lrp_ip_dnat_stage1,
                     'lrp_ip_dnat_stage2':lrp_ingress.lrp_ip_dnat_stage2,
                    }
lrp_egress_flows = {'lrp_update_eth_dst':lrp_egress.lrp_update_eth_dst,
                    'lrp_handle_unknow_dst_pkt':lrp_egress.lrp_handle_unknow_dst_pkt,
                    'lrp_forward_packet':lrp_egress.lrp_forward_packet,
                    'lrp_ip_undnat_stage1':lrp_egress.lrp_ip_undnat_stage1,
                    'lrp_ip_undnat_stage2':lrp_egress.lrp_ip_undnat_stage2,
                    'lrp_ip_snat_stage1':lrp_egress.lrp_ip_snat_stage1,
                    'lrp_ip_snat_stage2':lrp_egress.lrp_ip_snat_stage2,
                   }
phy_flows= {'build_flows_phy':lflow.build_flows_phy,
            'build_flows_mid':lflow.build_flows_mid,
            'build_flows_drop':lflow.build_flows_drop}
phy_detail_flows = {'convert_phy_logical': physical_flow.convert_phy_logical,
                    'arp_feedback_construct':physical_flow.arp_feedback_construct,
                    'embed_metadata':mid.embed_metadata,
                    'extract_metadata':mid.extract_metadata,
                    'pipeline_forward':mid.pipeline_forward,
                    'redirect_other_chassis':mid.redirect_other_chassis}
logical_flows = [phy_flows, phy_detail_flows, lsp_ingress_flows, lsp_egress_flows,
                 lrp_ingress_flows, lrp_egress_flows]

def populate_all():
    for group in entity_set.values():
        for entity in group.values():
            if entity.populated is False:
                entity.populate()


def test_rand_entity(entity_set, rand_ls_num, rand_chassis_num, rand_lsp_num):
    lsp_set = entity_set['lsp']
    lrp_set = entity_set['lrp']
    ls_set = entity_set['LS']
    lr_set = entity_set['LR']
    lsr_set = entity_set['lsr']
    lnat_set = entity_set['lnat']
    chassis_set = entity_set['chassis']
    ovsport_chassis_set = entity_set['ovsport_chassis']

    +local_system_id('chassis-local')
    ls_set['LS-A'] = LogicalSwitch('LS-A', '9')
    ls_set['LS-B'] = LogicalSwitch('LS-B', '10')
    lr_set['LR-A'] = LogicalRouter('LR-A', '11')
    ls_set['LS-m1'] = LogicalSwitch('LS-m1', '12')
    ls_set['LS-m2'] = LogicalSwitch('LS-m2', '13')
    lr_set['LR-edge1'] = LogicalRouter('LR-edge1', '14', 'chassis2')
    lr_set['LR-edge2'] = LogicalRouter('LR-edge2', '15', 'chassis3')
    ls_set['LS-outside1'] = LogicalSwitch('LS-outside1', '16')
    ls_set['LS-outside2'] = LogicalSwitch('LS-outside2', '17')

    lsp_set['LS-A_to_LR-A'] = LogicalSwitchPort('LS-A_to_LR-A',
                                                '192.168.1.1',
                                                '03:04:01:02:03:04',
                                                'LS-A', None, 'LR-A_to_LS-A')
    lrp_set['LR-A_to_LS-A'] = LogicalRouterPort('LR-A_to_LS-A',
                                                '192.168.1.1', 24,
                                                '03:04:01:02:03:04',
                                                'LR-A', 'LS-A_to_LR-A')
    lsp_set['LS-B_to_LR-A'] = LogicalSwitchPort('LS-B_to_LR-A',
                                                '192.168.2.1',
                                                '03:04:01:02:03:05',
                                                'LS-B', None, 'LR-A_to_LS-B')
    lrp_set['LR-A_to_LS-B'] = LogicalRouterPort('LR-A_to_LS-B',
                                                '192.168.2.1', 24,
                                                '03:04:01:02:03:05',
                                                'LR-A', 'LS-B_to_LR-A')

    for i in range(50, 50+rand_ls_num):
        ls_name = 'LS-random'+str(i)
        ls_set[ls_name] = LogicalSwitch(ls_name, str(i))
        lsp_name = ls_name+'_to_LR-A'
        lrp_name = 'LR-A_to_'+ls_name
        lsp_mac = "08:02:{:02x}:{:02x}:{:02x}:{:02x}".format(random.randint(0x00, 0xff),
                                                             random.randint(0x00, 0xff),
                                                             random.randint(0x00, 0xff),
                                                             random.randint(0x00, 0xff))
        lsp_set[lsp_name] = LogicalSwitchPort(lsp_name,
                                              '192.168.%d.1'%i,
                                              lsp_mac,
                                              ls_name, None, lrp_name)

        lrp_set[lrp_name] = LogicalRouterPort(lrp_name,
                                              '192.168.%d.1'%i, 24,
                                              lsp_mac, 'LR-A', lsp_name)

    def get_one_rand_ls(i):
        rid = i % 3
        if rid == 0:
            return 'LS-A'
        elif rid == 1:
            return 'LS-B'
        else:
            return 'LS-random'+str(50 + i%rand_ls_num)


    lsp_set['LS-m1_to_LR-A'] = LogicalSwitchPort('LS-m1_to_LR-A',
                                                '100.10.10.1',
                                                '03:04:01:02:03:06',
                                                'LS-m1', None, 'LR-A_to_LS-m1')
    lrp_set['LR-A_to_LS-m1'] = LogicalRouterPort('LR-A_to_LS-m1',
                                                '100.10.10.1', 24,
                                                '03:04:01:02:03:06',
                                                'LR-A', 'LS-m1_to_LR-A')
    lsp_set['LS-m2_to_LR-A'] = LogicalSwitchPort('LS-m2_to_LR-A',
                                                '100.10.10.3',
                                                '03:04:01:02:03:07',
                                                'LS-m2', None, 'LR-A_to_LS-m2')
    lrp_set['LR-A_to_LS-m2'] = LogicalRouterPort('LR-A_to_LS-m2',
                                                '100.10.10.3', 24,
                                                '03:04:01:02:03:07',
                                                'LR-A', 'LS-m2_to_LR-A')
    lsp_set['LS-m1_to_LR-edge1'] = LogicalSwitchPort('LS-m1_to_LR-edge1',
                                                     '100.10.10.2',
                                                     '03:04:01:02:03:08',
                                                     'LS-m1', None, 'LR-edge1_to_LS-m1')
    lrp_set['LR-edge1_to_LS-m1'] = LogicalRouterPort('LR-edge1_to_LS-m1',
                                                     '100.10.10.2', 24,
                                                     '03:04:01:02:03:08',
                                                     'LR-edge1', 'LS-m1_to_LR-edge1')
    lsp_set['LS-m2_to_LR-edge2'] = LogicalSwitchPort('LS-m2_to_LR-edge2',
                                                     '100.10.10.2',
                                                     '03:04:01:02:03:09',
                                                     'LS-m2', None, 'LR-edge2_to_LS-m2')
    lrp_set['LR-edge2_to_LS-m2'] = LogicalRouterPort('LR-edge2_to_LS-m2',
                                                     '100.10.10.2', 24,
                                                     '03:04:01:02:03:09',
                                                     'LR-edge2', 'LS-m2_to_LR-edge2')

    lsr_set['ecmp1'] = LogicalStaticRoute('ecmp1', '0.0.0.0', 0, '100.10.10.2', 'LR-A_to_LS-m1', 'LR-A')
    lsr_set['ecmp2'] = LogicalStaticRoute('ecmp2', '0.0.0.0', 0, '100.10.10.2', 'LR-A_to_LS-m2', 'LR-A')

    for i in xrange(rand_chassis_num):
        chassis_id = 'chassis'+str(i)
        ch = PhysicalChassis(chassis_id,
                             "192.{}.{}.{}".format(random.randint(1,254),
                                                   random.randint(1,254),
                                                   random.randint(1,254)),
                             int(time.time()))
        chassis_set[chassis_id] = ch
        ovsport_chassis_set['ovsport'+str(i)] = OVSPort('ovsport'+str(i),
                                                        chassis_id,
                                                        i, True)
    for i in xrange(rand_lsp_num):
        while True:
            randmac = "01:02:{:02x}:{:02x}:{:02x}:{:02x}".format(random.randint(0x00, 0xff),
                                                                 random.randint(0x00, 0xff),
                                                                 random.randint(0x00, 0xff),
                                                                 random.randint(0x00, 0xff))
            randip = "192.{}.{}.{}".format(random.randint(1,254),
                                           random.randint(1,254),
                                           random.randint(1,254))
            randid = 'AArandport'+str(i)
            try:
                lsp_set[randid] = LogicalSwitchPort(randid, randip, randmac, get_one_rand_ls(i),
                                                    'chassis'+str(i%rand_chassis_num))
            except:
                continue
            else:
                break

    populate_all()

    logger.info("start building flows")
    start_time = time.time()
    lflow.build_flows(Table, Priority, Match, Action, State)
    table_tuple = Table.data; priority_tuple = Priority.data
    match_tuple = Match.data; action_tuple = Action.data
    entity_zoo.sweep_zoo()
    logger.info('cost time:%s, total flows number:%d',
                 time.time()-start_time, len(table_tuple))
    for i in xrange(1):
        lsp_set['newone'+str(i)] = \
                    LogicalSwitchPort('newone'+str(i),
                                      '192.1.{}.{}'.format(random.randint(1,254), random.randint(1,254)),
                                      '11:11:11:11:11:{:02x}'.format(i),'LS-A',
                                      'chassis10')
        chassis_id = 'chassis_new'+str(i)
        ch = PhysicalChassis(chassis_id,
                             "{}.{}.{}.{}".format(random.randint(1,254),
                                                  random.randint(1,254),
                                                  random.randint(1,254),
                                                  random.randint(1,254)),
                             int(time.time()))
        chassis_set[chassis_id] = ch
        ovsport_chassis_set['new_ovsport'+str(i)] = OVSPort('new_ovsport'+str(i),
                                                            chassis_id,
                                                            0xffff+i, True)
        lnat_set['lsnat'+str(i)] = LogicalNetAddrXlate('lsnat'+str(i), "10.10.1.1", i,
                                                       "192.168.4.5", 'snat', "LR-edge1")
        lnat_set['ldnat'+str(i)] = LogicalNetAddrXlate('ldnat'+str(i), "10.10.5.%d"%i, 32,
                                                       "192.168.5.5", 'dnat', "LR-edge2")


        populate_all()

        start_time = time.time()
        lflow.build_flows(Table, Priority, Match, Action, State)
        table_tuple = Table.data; priority_tuple = Priority.data
        match_tuple = Match.data; action_tuple = Action.data
        logger.info('total cost time:%s, flow_n:%d',
                     time.time()-start_time, len(table_tuple))

        start_time = time.time()
        lflow.build_flows_lsp(Table, Priority, Match, Action, State)
        table_tuple = Table.data; priority_tuple = Priority.data
        match_tuple = Match.data; action_tuple = Action.data
        logger.info('lsp cost time:%s, flow_n:%d',
                     time.time()-start_time, len(table_tuple))

        start_time = time.time()
        lflow.build_flows_lrp(Table, Priority, Match, Action, State)
        table_tuple = Table.data; priority_tuple = Priority.data
        match_tuple = Match.data; action_tuple = Action.data
        logger.info('lrp cost time:%s, flow_n:%d',
                     time.time()-start_time, len(table_tuple))


        for flows_group in logical_flows:
            for name, flow_clause in flows_group.items():
                start_time = time.time()
                if name == 'convert_phy_logical':
                    flow_clause(Priority, Match, Action, State)
                else:
                    flow_clause(A, Priority, Match, Action, State)
                    table_tuple = A.data;
                priority_tuple = Priority.data
                match_tuple = Match.data; action_tuple = Action.data
                logger.info('%s cost time:%s, num:%d', name,
                            time.time()-start_time, len(priority_tuple))

        chassis_id = 'chassis_fake'+str(i)
        ch = PhysicalChassis(chassis_id,
                             "192.{}.{}.{}".format(random.randint(1,254),
                                                   random.randint(1,254),
                                                   random.randint(1,254)),
                             int(time.time()))
        chassis_set[chassis_id] = ch
        populate_all()
        start_time = time.time()
        tunnel.tunnel_port_oper(A,B,C)
        tmp=A.data; tmp=B.data; tmp=C.data
        logger.info('tunnel_port_oper cost time:%s, num:%d',
                    time.time()-start_time, len(tmp))
        start_time = time.time()
        active_lsp(A,B,C,State);tmp=A.data;
        logger.info('active_lsp cost time:%s', time.time()-start_time)

        logger.info('\n\n')



extra = get_extra()
extra['system_id'] = 'chassis-local'
extra['options'] = {}
extra['options']['ENABLE_REDIRECT'] = ''
extra['options']['ENABLE_PERFORMANCE_TESTING'] = ''
extra['options']['ONDEMAND'] = ''
extra['options']['ENABLE_UNTUNNEL'] = ''
extra['options']['br-int_mac'] = '00:00:00:11:11:11'
entity_set = entity_zoo.entity_set
lflow.init_build_flows_clause(extra['options'])
test_rand_entity(entity_set, 20, 500, 5000)
