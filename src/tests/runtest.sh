#!/bin/bash
. utils.sh
current_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
testcase_num=0
thread_num=1
success_test_num=0
pid_array=""

exit_all_test()
{
    pmsg_green "exit testing, terminte all testings"
    for cpid in $pid_array; do
        kill -INT $cpid
    done
    kill 0
    exit -1
}
trap "exit_all_test" INT

run_tests()
{
    local thread_id=$1
    local all_testcase=$2
    local success_num=0
    pmsg_green "thread $thread_id will run tests:$2"
    for testcase in $all_testcase; do
        pmsg_green "start running $testcase"
        output=`bash $testcase`
        if [ $? == 0 ]; then
            success_num=$((success_num+1))
            pmsg_green "$testcase PASS!"
        else
            pmsg_red "$testcase FAILED!, testcase output:"
            pmsg_red "$output"
        fi
    done
    return $success_num
}

# we have to verify if the environment can run test or not
check_env()
{
    ret=`ovs-vswitchd --version`; echo "$ret"
    if [ $? != 0 ]; then pmsg_exit "ovs-vswitchd error"; fi
    ret=`ovsdb-server --version`;
    if [ $? != 0 ]; then pmsg_exit "ovsdb-server error"; fi
    ret=`ovs-vsctl --version`
    if [ $? != 0 ]; then pmsg_exit "ovs-vsctl error"; fi
    ret=`ovs-ofctl --version`
    if [ $? != 0 ]; then pmsg_exit "ovs-ofctl error"; fi
}

check_env

# collect all testfile need to run
for filename in $(ls $current_dir); do
    if [[ $filename == test_*.sh ]]; then
        testcase_num=$((testcase_num+1))
        testcase_array="$testcase_array $filename"
    fi
done

# sanity check thread_num
if [ "$1" != "" ]; then
    if [ $1 -gt $testcase_num ]; then
        thread_num=$testcase_num
    else
        thread_num=$1
    fi
fi

pmsg_green "thread number:$thread_num, testcase number:$testcase_num"

#dispatch testcase to each thread
i=0
for testcase in $testcase_array; do
    test_per_thread[$i]="${test_per_thread[$i]} $testcase"
    i=$((i+1))
    let i=i%thread_num
done

start_time=$(date +%s)
# run tests and add pid into pid_array
i=0
while [ $i -lt $thread_num ]; do
    run_tests $i "${test_per_thread[$i]}" &
    pid_array="$pid_array $!"
    i=$((i+1))
done

# waiting for testing finish
for pid in $(jobs -p); do
    wait $pid
    n=$?
    success_test_num=$((success_test_num+n))
done
fail_test_num=$((testcase_num-success_test_num))

end_time=$(date +%s)
cost_time=$((end_time - start_time))

retval=0
if [ $fail_test_num -ge 1 ]; then
    pmsg_red "fail test number:$fail_test_num"
    retval=-1
fi
pmsg_green "sucess test number:$success_test_num"
pmsg_green "Testing done, cost time:${cost_time}s"
exit $retval
