from pyDatalog import pyDatalog
from logicalview import *
pyDatalog.create_terms('patchport_single, patchport_oper')
pyDatalog.create_terms('PEER_BR')

patchport_single(UUID_LSP, PEER_BR, State) <= (
    ls_array(LS, UUID_LS, State1) &
    local_system_id(UUID_CHASSIS) &
    exchange_lsp_array(UUID_LSP, LSP, UUID_LS, UUID_CHASSIS, UUID_LRP, State2) &
    (LSP[LSP_IP] == '255.255.255.255') &
    (LSP[LSP_PEER] != None) &
    (PEER_BR == LSP[LSP_PEER]) &
    (State == State1 + State2)
    )

# has no ovsport for logical patchport
patchport_oper(UUID_LSP, PEER_BR, State) <= (
    patchport_single(UUID_LSP, PEER_BR, State) & (State >= 0) &
     ~ovsport(PORT_NAME, UUID_LSP, OFPORT, State1)
    )
patchport_oper(UUID_LSP, PEER_BR, State) <= (
    patchport_single(UUID_LSP, PEER_BR, State) & (State >= 0) &
    ovsport(PORT_NAME, UUID_LSP, OFPORT, State_DEL)
    )
# has no peer-ovsport for logical patchport
patchport_oper(UUID_LSP, PEER_BR, State) <= (
    patchport_single(UUID_LSP, PEER_BR, State) & (State >= 0) &
    (UUID_LSP1 == UUID_LSP + "-peer") &
    ~ovsport(PORT_NAME, UUID_LSP1, OFPORT1, State2)
    )
patchport_oper(UUID_LSP, PEER_BR, State) <= (
    patchport_single(UUID_LSP, PEER_BR, State) & (State >= 0) &
    (UUID_LSP1 == UUID_LSP + "-peer") &
    ovsport(PORT_NAME, UUID_LSP1, OFPORT1, State_DEL)
    )

# delete patchport
patchport_oper(UUID_LSP, PEER_BR, State) <= (
    patchport_single(UUID_LSP, PEER_BR, State) & (State < 0) &
    ovsport(PORT_NAME, UUID_LSP, OFPORT, State1) & (State1 >= 0)
    )
patchport_oper(UUID_LSP, PEER_BR, State) <= (
    patchport_single(UUID_LSP, PEER_BR, State) & (State < 0) &
    (UUID_LSP1 == UUID_LSP + "-peer") &
    ovsport(PORT_NAME, UUID_LSP1, OFPORT1, State1) & (State1 >= 0)
    )
