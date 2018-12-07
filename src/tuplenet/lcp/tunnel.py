from pyDatalog import pyDatalog
from logicalview import *
from run_env import get_init_trigger

pyDatalog.create_terms('X, Y, Z, IP')
pyDatalog.create_terms('latest_chassis, tunnel_port_oper, tunnel_port')
pyDatalog.create_terms('get_init_trigger')

(latest_chassis[X] == max_(Y, order_by=Z)) <= (
    chassis_array(PHY_CHASSIS, UUID_CHASSIS, State) &
    (X == PHY_CHASSIS[PCH_IP]) &
    (Y == PHY_CHASSIS) &
    (Z == PHY_CHASSIS[PCH_TICK])
)

# add tunnel port if we have chassis but get no ovsport_chassis
tunnel_port(PHY_CHASSIS, State1) <= (
    chassis_array(PHY_CHASSIS, UUID_CHASSIS, State1) & (State1 >= 0) &
    ~ovsport_chassis(PORT_NAME, UUID_CHASSIS, OFPORT, State2) &
    ~local_system_id(UUID_CHASSIS)
)

# add tunnel port if we have chassis but ovsport_chassis was deleted
tunnel_port(PHY_CHASSIS, State1) <= (
    chassis_array(PHY_CHASSIS, UUID_CHASSIS, State1) & (State1 >= 0) &
    # NOTE: make sure the ovsport_chassis is the lowest clause, because
    # we use State_DEL to grep the ovsport_chassis
    ovsport_chassis(PORT_NAME, UUID_CHASSIS, OFPORT, State_DEL) &
    ~local_system_id(UUID_CHASSIS)
)

# delete port if we don't have chassis but ovsport_chassis exist
tunnel_port(PHY_CHASSIS, State_DEL) <= (
    # NOTE: make sure the chassis_array is the lowest clause, because
    # we use State_DEL to grep the chassis_array
    chassis_array(PHY_CHASSIS, UUID_CHASSIS, State_DEL) &
    ovsport_chassis(PORT_NAME, UUID_CHASSIS, OFPORT, State2) & (State2 >= 0) &
    ~local_system_id(UUID_CHASSIS)
)

# create the default flow-based tunnel port
#tunnel_port_oper(IP, UUID_CHASSIS, State) <= (
#    (IP == '') & (State == get_init_trigger(IP)) & (State != 0) &
#    (UUID_CHASSIS == 'flow_base_tunnel')
#)

tunnel_port_oper(IP, UUID_CHASSIS, State) <= (
    # the chassis should be a latest chassis
    tunnel_port(PHY_CHASSIS, State) & (latest_chassis[X] == Y) &
    (PHY_CHASSIS == Y) &
    (IP == PHY_CHASSIS[PCH_IP]) & (UUID_CHASSIS == PHY_CHASSIS[PCH_UUID])
)

