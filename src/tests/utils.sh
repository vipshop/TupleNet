#!/bin/bash

_INFO_HDR_FMT="%.23s %s[line:%s]: "
_INFO_MSG_FMT="${_INFO_HDR_FMT}%s\n"
ETCDCTL_API=3; export ETCDCTL_API
COLOR_RED='\033[1;31m'
COLOR_GREEN='\033[1;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_RESET=`tput sgr0`
PYPY="../../pypy-5.0.1-vip/bin/pypy"
if [ -z "$PYTHON" ]; then
    PYTHON="python"
fi


pmsg()
{
    printf "$_INFO_MSG_FMT" $(date +%F.%T.%N) ${BASH_SOURCE[1]##*/} ${BASH_LINENO[0]} "${@}"
}

pmsg_green()
{
    printf "${COLOR_GREEN}$_INFO_MSG_FMT" $(date +%F.%T.%N) ${BASH_SOURCE[1]##*/} ${BASH_LINENO[0]} "${@}$COLOR_RESET"
}

pmsg_red()
{
    printf "${COLOR_RED}$_INFO_MSG_FMT" $(date +%F.%T.%N) ${BASH_SOURCE[1]##*/} ${BASH_LINENO[0]} "${@}$COLOR_RESET"
}

pmsg_exit()
{
    printf "${COLOR_RED}$_INFO_MSG_FMT" $(date +%F.%T.%N) ${BASH_SOURCE[1]##*/} ${BASH_LINENO[0]} "${@}$COLOR_RESET"
    exit 1
}

is_enable_ondemand()
{
    if [[ -z "$ONDEMAND" || "$ONDEMAND" == 1 ]]; then
        echo 1
    else
        echo 0
    fi
}

feature=`is_enable_ondemand`
if [ "$feature" == 1 ]; then
    pmsg "enable ondemand"
else
    pmsg "disable ondemand"
fi


wait_for_packet()
{
    sleep 0.1
}

equal_str () {
    x="`echo "$1" | sed '/^\s*$/d'`"
    y="`echo "$2" | sed '/^\s*$/d'`"
    if [ "$x" != "$y" ];then
        diff -y <(echo "$x") <(echo "$y")
        return 1
    fi
}

