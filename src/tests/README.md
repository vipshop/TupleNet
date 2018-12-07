## Run Testing

### 1. Before running test-suite
#### Set your environment
- Install [docker-ce](https://docs.docker.com/install/linux/docker-ce/centos/#prerequisites)
- Install etcd-3
- install [golang](https://golang.org/doc/install)(version above 1.11 and set the environment)
- Compile Tuplenet CLI
- - cd TupleNet/src/control
- - ./build.sh
- Compile pkt_controller
- - ./boot.sh
- - ./configure
- - make
- install [openvswitch](http://docs.openvswitch.org/en/latest/intro/install/distributions/)(version above 2.8.0)


### 2. Run test-suite
#### 2.1 Run all test-suite
- cd TupleNet/src/tests
- ./runtest.sh (it runs all test-suites which name start with **test_**)

#### 2.2 Run all testcases in parallel way
- ./runtest.sh 4 (4 means it generate 4 threads to run testcases, it helps accelerate the speed of whole testing)

#### 2.3 Run a single test-suite
- e.g. 
- -  ./test_simple_ls.sh

#### 2.4 Run test-suite with ONDEMAND disable
**TupleNet enable ondemand feature by default, please set "ONDEMAND=0" if you want to run it without ondemand**
- e.g.
- - ONDEMAND=0 ./test_simple_ls.sh
- - ONDEMAND=0 ./runtest.sh

### Test-suite debugging
**All test-suite create log and data while running in dir_test/${test_suite_file_name}, it record essential information you may need**
**etcd data and log store in dir_test/${test_suite_file_name}/etcd**
**ovs data and log store in dir_test/${test_suite_file_name}/ovs**
**tuplenet data and log store in dir_test/${test_suite_file_name}/tuplenet**
