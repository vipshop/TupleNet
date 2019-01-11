from pyDatalog import pyDatalog
from logicalview import *

pyDatalog.create_terms('X, Y, Z, IP')
pyDatalog.create_terms('latest_chassis, tunnel_port_oper, tunnel_port')
pyDatalog.create_terms('tunnel_port_delete_exist, cur_chassis_list')

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

# delete port if we delete chassis but ovsport_chassis exist
tunnel_port(PHY_CHASSIS, State_DEL) <= (
    # NOTE: make sure the chassis_array is the lowest clause, because
    # we use State_DEL to grep the chassis_array
    chassis_array(PHY_CHASSIS, UUID_CHASSIS, State_DEL) &
    ovsport_chassis(PORT_NAME, UUID_CHASSIS, OFPORT, State2) & (State2 >= 0) &
    ~local_system_id(UUID_CHASSIS)
)

tunnel_port_oper(IP, UUID_CHASSIS, State) <= (
    # the chassis should be a latest chassis
    tunnel_port(PHY_CHASSIS, State) & (latest_chassis[X] == Y) &
    (PHY_CHASSIS == Y) &
    (IP == PHY_CHASSIS[PCH_IP]) & (UUID_CHASSIS == PHY_CHASSIS[PCH_UUID])
)

# construct a tuple which contains all chassis-id
(cur_chassis_list[X] == tuple_(Y, order_by=Y)) <= (
    chassis_array(PHY_CHASSIS, UUID_CHASSIS, State) &
    (State >=0) & (X == 0) & (Y == UUID_CHASSIS)
)

# delete port if we don't have chassis but ovsport_chassis exist
# this function was consume in booting tuplenet to delete unused tunnel ports
tunnel_port_delete_exist(PORT_NAME) <= (
    ovsport_chassis(PORT_NAME, UUID_CHASSIS, OFPORT, State1) & (State1 >= 0) &
    (cur_chassis_list[X] == Y) &
    ~(UUID_CHASSIS._in(Y)) &
    ~local_system_id(UUID_CHASSIS)
)

