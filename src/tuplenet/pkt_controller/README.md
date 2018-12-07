### How to compile pkt_controller in Redhat/Centos
- install the rpm of openvswitch-devel
- ./boot.sh
- ./configure
- make

### How to compile pkt_controller in Ubuntu (may specific the path of header files of ovs)
- install the deb libopenvswitch-dev
- ./boot.sh
- ./configure CPPFLAGS=-I/usr/include/openvswitch
- make