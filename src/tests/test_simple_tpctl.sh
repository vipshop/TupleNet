#!/usr/bin/env bash
. env_utils.sh
pmsg "preparing env"
env_init ${0##*/} # 0##*/ is the filename

# setup
pmsg "building tpctl"
bash ${CONTROL_BIN_PATH}/build.sh || exit_test

# below command shall not require ectd to be up
! (tpctl | grep 'error') || exit_test

# invalid paramters check
(tpctl lr show aaa bbb | grep 'require')|| exit_test
(tpctl lr add | grep 'require')|| exit_test
(tpctl lr add aaa bbb cc| grep 'require')|| exit_test
(tpctl lr add "  " bbb | grep 'only spaces')|| exit_test
(tpctl lr add a/aa bbb | grep 'not allowed')|| exit_test
(tpctl lr del | grep 'require') || exit_test
(tpctl lr del aaa bbb | grep 'require') || exit_test

(tpctl lrp show aaa bbb ccc | grep 'require')|| exit_test
(tpctl lrp add | grep 'require') || exit_test
(tpctl lrp add aaa | grep 'require') || exit_test
(tpctl lrp add aaa bbb | grep 'require') || exit_test
(tpctl lrp add aaa bbb ddd | grep 'invalid') || exit_test
(tpctl lrp add aaa bbb 10.200.100.1 00:00:00:00:00:00 | grep 'invalid') || exit_test
(tpctl lrp add aaa bbb 10.200.100.1/24 ccc | grep 'invalid') || exit_test
(tpctl lrp add aaa bbb 10.200.100.1/24 00:00:00:00:00:00 ccc ddd | grep 'require') || exit_test
(tpctl lrp add aaa bbb 10.200.100.1/24 00:00:00:00:00:00 ccc ddd | grep 'require') || exit_test
(tpctl lrp add aaa "  " 10.200.100.1/24 00:00:00:00:00:00 peer | grep 'only spaces') || exit_test
(tpctl lrp add aaa b/bb 10.200.100.1/24 00:00:00:00:00:00 peer | grep 'not allowed') || exit_test
(tpctl lrp del | grep 'require') || exit_test
(tpctl lrp del aaa | grep 'require') || exit_test
(tpctl lrp del aaa bbb ccc | grep 'require') || exit_test

(tpctl lsr show aaa bbb ccc | grep 'require') || exit_test
(tpctl lsr add | grep 'require') || exit_test
(tpctl lsr add aaa | grep 'require') || exit_test
(tpctl lsr add aaa bbb | grep 'require') || exit_test
(tpctl lsr add aaa bbb ccc | grep 'require') || exit_test
(tpctl lsr add aaa bbb ccc ddd | grep 'require') || exit_test
(tpctl lsr add aaa bbb ccc ddd | grep 'require') || exit_test
(tpctl lsr add aaa bbb ccc ddd eee | grep 'invalid') || exit_test
(tpctl lsr add aaa bbb 10.200.100.1 ccc ddd | grep 'invalid') || exit_test
(tpctl lsr add aaa bbb 10.200.100.1/24 ccc ddd | grep 'invalid') || exit_test
(tpctl lsr add aaa bbb 10.200.100.1/24 ccc ddd eee | grep 'require') || exit_test
(tpctl lsr add aaa "  " 10.200.100.1/24 10.200.100.1 ddd | grep 'only spaces') || exit_test
(tpctl lsr add aaa b/bb 10.200.100.1/24 10.200.100.1 ddd | grep 'not allowed') || exit_test

(tpctl lnat show aaa bbb ccc | grep 'require') || exit_test
(tpctl lnat add | grep 'require') || exit_test
(tpctl lnat add aaa | grep 'require') || exit_test
(tpctl lnat add aaa bbb | grep 'require') || exit_test
(tpctl lnat add aaa bbb ccc | grep 'require') || exit_test
(tpctl lnat add aaa bbb ccc ddd | grep 'require') || exit_test
(tpctl lnat add aaa bbb ccc ddd | grep 'require') || exit_test
(tpctl lnat add aaa bbb ccc ddd eee | grep 'invalid') || exit_test
(tpctl lnat add aaa bbb 10.200.100.1 ccc ddd | grep 'invalid') || exit_test
(tpctl lnat add aaa bbb 10.200.100.1/24 ccc ddd | grep 'invalid') || exit_test
(tpctl lnat add aaa bbb 10.200.100.1/24 snat ddd | grep 'invalid') || exit_test
(tpctl lnat add aaa bbb 10.200.100.1/24 ccc ddd eee | grep 'require') || exit_test
(tpctl lnat add aaa "  " 10.200.100.1/24 snat 10.200.100.1 | grep 'only spaces') || exit_test
(tpctl lnat add aaa b/bb 10.200.100.1/24 snat 10.200.100.1 | grep 'not allowed') || exit_test

(tpctl ls show aaa bbb | grep 'require')|| exit_test
(tpctl ls add | grep 'require') || exit_test
(tpctl ls add aaa bbb | grep 'require') || exit_test
(tpctl ls add "  " | grep 'only spaces')|| exit_test
(tpctl ls add a/aa | grep 'not allowed')|| exit_test
(tpctl ls del | grep 'require') || exit_test
(tpctl ls del aaa bbb | grep 'require') || exit_test

(tpctl lsp add | grep 'require') || exit_test
(tpctl lsp add aaa | grep 'require') || exit_test
(tpctl lsp add aaa bbb | grep 'require') || exit_test
(tpctl lsp add aaa bbb 10.200.100.a 00:00:00:00:00:00 | grep 'invalid') || exit_test
(tpctl lsp add aaa bbb 10.200.100.1/24 ccc | grep 'invalid') || exit_test
(tpctl lsp add aaa bbb 10.200.100.1 zz:00:00:00:00:00 ddd | grep 'invalid') || exit_test
(tpctl lsp add aaa bbb 10.200.100.1 00:00:00:00:00:00 ddd eee | grep 'require') || exit_test
(tpctl lsp add aaa "  " 10.200.100.1 00:00:00:00:00:00 peer | grep 'only spaces') || exit_test
(tpctl lsp add aaa b/bb 10.200.100.1 00:00:00:00:00:00 peer | grep 'not allowed') || exit_test
(tpctl lsp del | grep 'require') || exit_test
(tpctl lsp del aaa bbb ccc | grep 'require') || exit_test

(tpctl ch del | grep 'require') || exit_test
(tpctl ch del aaa bbb | grep 'require') || exit_test

# non existence checks
(tpctl lr  del aaa | grep 'not found') || exit_test
(tpctl lrp del aaa bbb | grep 'not found') || exit_test
(tpctl lsr del aaa bbb | grep 'not found') || exit_test
(tpctl ls  del aaa | grep 'not found') || exit_test
(tpctl lsp del aaa bbb | grep 'not found') || exit_test
(tpctl ch  del aaa | grep 'not found') || exit_test

# add LR-1
tpctl lr add LR-1

result="$(tpctl lr show LR-1)"
expected="
LR-1:
  - id     : 1
  - chassis: 
"
equal_str "$result" "$expected" || exit_test
(tpctl lrp show LR-1 | grep 'empty data set') || exit_test
(tpctl lsr show LR-1 | grep 'empty data set') || exit_test
(tpctl lnat show LR-1 | grep 'empty data set') || exit_test

# add LS-1
tpctl ls add LS-1
etcdctl --endpoints ${etcd_client_specs} get --prefix ""
result="$(tpctl ls show LS-1)"
expected="
LS-1:
  - id: 2
"
equal_str "$result" "$expected" || exit_test
(tpctl lsp show LS-1 | grep 'empty data set') || exit_test

# batch add 
tpctl lr add LR-2 || exit_test
tpctl lr add LR-3 || exit_test
tpctl lr add LR-4 || exit_test
(tpctl lr add LR-1 | grep 'unable to perform save') || exit_test
(tpctl lr add LR-2 | grep 'unable to perform save') || exit_test
(tpctl lr add LR-3 | grep 'unable to perform save') || exit_test
(tpctl lr add LR-4 | grep 'unable to perform save') || exit_test

tpctl ls add LS-2 || exit_test
tpctl ls add LS-3 || exit_test
tpctl ls add LS-4 || exit_test
(tpctl ls add LS-1 | grep 'unable to perform save') || exit_test
(tpctl ls add LS-2 | grep 'unable to perform save') || exit_test
(tpctl ls add LS-3 | grep 'unable to perform save') || exit_test
(tpctl ls add LS-4 | grep 'unable to perform save') || exit_test

result="$(tpctl lr show)"
expected="
LR-1:
  - id     : 1
  - chassis: 
LR-2:
  - id     : 3
  - chassis: 
LR-3:
  - id     : 4
  - chassis: 
LR-4:
  - id     : 5
  - chassis: 
"
equal_str "$result" "$expected" || exit_test

result="$(tpctl ls show)"
expected="
LS-1:
  - id: 2
LS-2:
  - id: 6
LS-3:
  - id: 7
LS-4:
  - id: 8
"
equal_str "$result" "$expected" || exit_test

# inject conflict id
etcdctl --endpoints ${etcd_client_specs} put ${DATA_STORE_PREFIX}/entity_view/LR/LR-CONFLICT 'id=2' || exit_test
etcdctl --endpoints ${etcd_client_specs} put ${DATA_STORE_PREFIX}/entity_view/LS/LS-CONFLICT 'id=4' || exit_test
etcdctl --endpoints ${etcd_client_specs} get --prefix ""
tpctl toolbox find-id-conflict > ${test_path}/tmp.txt
result="$(sort ${test_path}/tmp.txt)"
expected="
LS-1 has the same id of LR-CONFLICT: 2
LS-CONFLICT has the same id of LR-3: 4
"
equal_str "$result" "$expected" || exit_test
tpctl lr del LR-CONFLICT || exit_test
tpctl ls del LS-CONFLICT || exit_test

# if device id map is missing, shall create automatically
[ 1 -eq $(etcdctl --endpoints ${etcd_client_specs} del ${DATA_STORE_PREFIX}/globals/device_ids | wc -l) ] || exit_test
tpctl ls add dummy || exit_test
result="$(tpctl ls show dummy)"
expected="
dummy:
  - id: 9
"
equal_str "$result" "$expected" || exit_test
tpctl toolbox find-id-conflict || exit_test
tpctl ls del dummy || exit_test

# batch link lsp to lrp
for i in `seq 1 4`; do
  (tpctl lr link LR-${i} LS-${i} 10.0.0.${i}/24 | grep -F "LR-${i} linked to LS-${i}") || exit_test
  (tpctl lr link LR-${i} LS-${i} 10.0.0.${i}/24 | grep 'exists') || exit_test

  result="$(tpctl lsp show LS-${i})"
  expected="
LS-${i}_to_LR-${i}:
  - ip     : 10.0.0.${i}
  - mac    : f2:01:0a:00:00:0${i}
  - peer   : LR-${i}_to_LS-${i}
  - chassis: 
"

  equal_str "$result" "$expected" || exit_test

  result="$(tpctl lrp show LR-${i})"
  expected="
LR-${i}_to_LS-${i}:
  - ip    : 10.0.0.${i}
  - prefix: 24
  - mac   : f2:01:0a:00:00:0${i}
  - peer  : LS-${i}_to_LR-${i}
"
  equal_str "$result" "$expected" || exit_test
done

# create lsp and lrp
for j in `seq 1 255`;do
  a=$(expr ${j} / 256)
  b=$(expr ${j} % 256)
  tpctl lsp add LS-1 LSP-${j} 10.${a}.${b}.1 || exit_test
  (tpctl lsp add LS-1 LSP-${j} 10.${a}.${b}.1 | grep 'exists') || exit_test
  (tpctl lsp add LS-1 LSP-A 10.${a}.${b}.1 | grep 'conflict with other IP') || exit_test

  tpctl lrp add LR-1 LRP-${j} 10.${a}.${b}.1/24 || exit_test
  (tpctl lrp add LR-1 LRP-A 20.${a}.${b}.1/24 | grep 'conflict with other IP') || exit_test

  tpctl lsr add LR-1 LSR-${j} 10.${a}.${b}.1/24 10.${a}.${b}.1 outport || exit_test
  (tpctl lsr add LR-1 LSR-${j} 10.${a}.${b}.1/24 10.${a}.${b}.1 outport | grep 'exists')  || exit_test

  tpctl lnat add LR-1 LNAT-${j} 10.${a}.${b}.1/24 snat 10.${a}.${b}.1 || exit_test
  (tpctl lnat add LR-1 LNAT-${j} 10.${a}.${b}.1/24 dnat 10.${a}.${b}.1 | grep 'exists')  || exit_test
done

# delete all things
for i in `seq 1 3`; do
  (echo "asdf" | tpctl lr del -r LR-${i} | grep 'operation canceled') || exit_test
  (yes | tpctl lr del -r LR-${i}) || exit_test
  (echo "asdf" | tpctl ls del -r LS-${i} | grep 'operation canceled') || exit_test
  (yes yes | tpctl ls del -r LS-${i}) || exit_test
done

# delete with remaining ports and static routes
tpctl lsr add LR-4 LSR-4 10.0.0.1/24 10.0.1.1 outport || exit_test
result="$(tpctl lsr show LR-4)"
expected="
LSR-4:
  - ip      : 10.0.0.1
  - prefix  : 24
  - next_hop: 10.0.1.1
  - outport : outport
"
equal_str "$result" "$expected" || exit_test
(tpctl lr del LR-4 | grep 'failed to delete') || exit_test

tpctl lnat add LR-4 LNAT4 10.0.0.1/24 dnat 10.0.1.1 || exit_test
result="$(tpctl lnat show LR-4)"
expected="
LNAT4:
  - ip        : 10.0.0.1
  - prefix    : 24
  - xlate_type: dnat
  - xlate_ip  : 10.0.1.1
"
equal_str "$result" "$expected" || exit_test
(tpctl lr del LR-4 | grep 'failed to delete') || exit_test

tpctl lsr del LR-4 LSR-4 || exit_test
(tpctl lr del LR-4 | grep 'failed to delete') || exit_test
tpctl lnat del LR-4 LNAT4 || exit_test
(tpctl lr del LR-4 | grep 'failed to delete') || exit_test

yes | tpctl lr del -r LR-4 || exit_test
(yes | tpctl lr del -r LR-4 | grep 'not found') || exit_test

# delete with remaining ports
(tpctl ls del LS-4 | grep 'failed to delete') || exit_test
(yes | tpctl ls del -r LS-4) || exit_test
(yes | tpctl ls del -r LS-4 | grep 'not found') || exit_test

etcdctl --endpoints ${etcd_client_specs} put ${DATA_STORE_PREFIX}/entity_view/chassis/CH-A 'ip=10.199.211.131,tick=1524118021' || exit_test
result="$(tpctl ch show)"
expected="
CH-A:
  - ip  : 10.199.211.131
  - tick: 1524118021
"
equal_str "$result" "$expected" || exit_test
(tpctl ch del CH-A | grep 'deleted') || exit_test

# inject conflicted data and test
tpctl ls add LS-A || exit_test
tpctl lsp add LS-A LSP-A-1 192.168.0.1 || exit_test
tpctl lsp add LS-A LSP-A-2 192.168.0.2 || exit_test

tpctl ls add LS-B || exit_test
tpctl lsp add LS-B LSP-B-1 192.168.0.1 || exit_test
tpctl lsp add LS-B LSP-B-2 192.168.0.2 || exit_test

tpctl lr add LR-A || exit_test
tpctl lrp add LR-A LRP-A-1 192.168.0.1/24 || exit_test
tpctl lrp add LR-A LRP-A-2 192.168.0.2/24 || exit_test

tpctl lr add LR-B || exit_test
tpctl lrp add LR-B LRP-B-1 192.168.0.1/24 || exit_test
tpctl lrp add LR-B LRP-B-2 192.168.0.2/24 || exit_test

etcdctl --endpoints ${etcd_client_specs} put ${DATA_STORE_PREFIX}/entity_view/LS/LS-A/lsp/LSP-A-2 ip=192.168.0.1 || exit_test
etcdctl --endpoints ${etcd_client_specs} put ${DATA_STORE_PREFIX}/entity_view/LR/LR-B/lrp/LRP-B-1 ip=192.168.0.2,prefix=24 || exit_test
etcdctl --endpoints ${etcd_client_specs} get --prefix "" || exit_test
tpctl toolbox find-ip-conflict > ${test_path}/tmp.txt
result="$(sort ${test_path}/tmp.txt)"
# the order of each line is purely random, so need to compare 4 possible combinations
expected="
in LR-B, LRP-B-1 use the same IP as LRP-B-2: 192.168.0.2
in LS-A, LSP-A-1 use the same IP as LSP-A-2: 192.168.0.1
"
expected2="
in LR-B, LRP-B-2 use the same IP as LRP-B-1: 192.168.0.2
in LS-A, LSP-A-1 use the same IP as LSP-A-2: 192.168.0.1
"
expected3="
in LR-B, LRP-B-2 use the same IP as LRP-B-1: 192.168.0.2
in LS-A, LSP-A-2 use the same IP as LSP-A-1: 192.168.0.1
"
expected4="
in LR-B, LRP-B-1 use the same IP as LRP-B-2: 192.168.0.2
in LS-A, LSP-A-2 use the same IP as LSP-A-1: 192.168.0.1
"
equal_str "$result" "$expected" || equal_str "$result" "$expected2" || equal_str "$result" "$expected3" || equal_str "$result" "$expected4" ||exit_test

(yes | tpctl lr del -r LR-A) || exit_test
(yes | tpctl lr del -r LR-B) || exit_test
(yes | tpctl ls del -r LS-A) || exit_test
(yes | tpctl ls del -r LS-B) || exit_test

# should block access if tpctl version is lower
etcdctl --endpoints ${etcd_client_specs} put ${DATA_STORE_PREFIX}/globals/version 65535
(tpctl lr show | grep "db accessed by higher version") || exit_test

# shall get version info and device map
result="$(etcdctl --endpoints ${etcd_client_specs} get --prefix=true "")"
expected="
${test_name}/globals/device_ids
OjAAAAAAAAA=
${test_name}/globals/version
65535
"
equal_str "$result" "$expected" || exit_test

pass_test
