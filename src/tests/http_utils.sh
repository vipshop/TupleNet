#!/bin/bash
. utils.sh

on_http_exit()
{
    (echo "$1"; cat $test_path/cleanup) > $test_path/cleanup.tmp
    mv $test_path/cleanup.tmp $test_path/cleanup
}

start_http_instance()
{
    ip netns exec $2 $PYTHON http_simple_server.py $1 &
    pid=$!
    on_http_exit "kill -9 $pid"
}
