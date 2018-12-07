#!/bin/bash
. utils.sh

CONTROL_BIN_PATH=$(dirname $0)/../control/
DATA_STORE_PREFIX=${test_name}

tpctl() {
    ETCD=${etcd_client_specs:+"-e ${etcd_client_specs}"}
    ${CONTROL_BIN_PATH}bin/tpctl ${ETCD} -p ${DATA_STORE_PREFIX} "$@"
}

