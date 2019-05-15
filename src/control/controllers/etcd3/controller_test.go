package etcd3

import (
	"fmt"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"os/exec"
	"reflect"
	"regexp"
	"testing"
)

// TestMarshalUnmarshalTuplenet test the correctness of tuplnet marshaller and unmarshaller
func TestMarshalUnmarshalTuplenet(t *testing.T) {
	type TestStruct struct {
		F1 string  `tn:"t1"`
		F2 int16   `tn:"t2"`
		F3 uint64  `tn:"t3"`
		F4 float32 `tn:"t4"`

		F5 string  `tn:"t5,omitempty"`
		F6 int16   `tn:"t6,omitempty"`
		F7 uint64  `tn:"t7,omitempty"`
		F8 float32 `tn:"t8,omitempty"`
	}

	structA := TestStruct{"field 1", 2, 3, 0, "", 0, 0, 0}

	// struct value
	expectedValue := "t1=field 1,t2=2,t3=3,t4=0"
	if data := MarshalTuplenet(structA); expectedValue != data {
		t.Fatalf("data marshaled %s is not the same as expected %s", data, expectedValue)
	}

	// struct pointer
	if data := MarshalTuplenet(&structA); expectedValue != data {
		t.Fatalf("data marshaled %s is not the same as expected %s", data, expectedValue)
	}

	// pointer to struct pointer
	ptr2Ptr := &structA
	if data := MarshalTuplenet(&ptr2Ptr); expectedValue != data {
		t.Fatalf("data marshaled %s is not the same as expected %s", data, expectedValue)
	}

	expectedStruct := TestStruct{F1: structA.F1, F2: structA.F2, F3: structA.F3, F4: structA.F4}
	var structB TestStruct
	err := UnmarshalTuplenet(structB, expectedValue)
	if err == nil {
		t.Fatalf("expected unmarshal to fail on a copy of struct")
	}

	err = UnmarshalTuplenet(&structB, expectedValue)
	if err != nil {
		t.Fatalf("expected unmarshal to succeed on pointer to struct")
	}
	if !reflect.DeepEqual(structB, expectedStruct) {
		t.Fatalf("value umarshaled %v not the same as %v", structB, structA)
	}

	var structC TestStruct
	ptr2Ptr = &structC
	err = UnmarshalTuplenet(&ptr2Ptr, expectedValue)
	if err != nil {
		t.Fatalf("expected unmarshal to succeed on pointer to pointer to struct")
	}
	if !reflect.DeepEqual(structC, expectedStruct) {
		t.Fatalf("value umarshaled %v not the same as %v", structB, expectedValue)
	}

	var ptr *TestStruct
	err = UnmarshalTuplenet(ptr, expectedValue)
	if err == nil {
		t.Fatalf("expected unmarshal to fail on a nil pointer")
	}
	if !reflect.DeepEqual(structC, TestStruct{F1: structA.F1, F2: structA.F2, F3: structA.F3, F4: structA.F4}) {
		t.Fatalf("value umarshaled %v not the same as %v", structB, expectedValue)
	}
}

// TestController_DeviceOperation test the device manipulation correctness
func TestController_DeviceOperation(t *testing.T) {
	// err is used by helper closures
	var err error

	expectSucceed := func(format string, args ...interface{}) {
		t.Helper()
		if err != nil {
			s := fmt.Sprintf(format, args...)
			t.Fatalf("%s expected to succeed but failed: %v", s, err)
		}
	}

	expectFail := func(format string, args ...interface{}) {
		t.Helper()
		if err == nil {
			s := fmt.Sprintf(format, args...)
			t.Fatalf("%s expected to fail but succeeded", s)
		}
	}

	expectSame := func(a interface{}, b interface{}) {
		t.Helper()
		if same := reflect.DeepEqual(a, b); !same {
			t.Fatalf("expected %+v and %+v to be the same", a, b)
		}
	}

	// test baby sit tasks
	controller, err := NewController([]string{"http://localhost:2379"}, "/test-prefix", true)
	expectSucceed("controller shall be able to connects to etcd")

	// test invalid devs to save and delete
	invalidDevs := []interface{}{nil, 32, "string", 15.1, true, struct{}{}}
	for i := range invalidDevs {
		err = controller.Save(invalidDevs[i:])
		expectFail("save invalid dev starting from %d", i)
		err = controller.Delete(false, invalidDevs[i:])
		expectFail("delete invalid dev starting from %d", i)
	}

	// test Router creation
	name := "router-1"
	r := logicaldev.NewRouter(name, "asdfasdfasdfasdfasdf")

	// create a router
	err = controller.Save(r)
	expectSucceed("save %s", r)

	// create a router with same Name
	err = controller.Save(r)
	expectFail("creation of %s for the second time", name)

	// test Router creation
	name = "switch-1"
	s := logicaldev.NewSwitch(name)
	err = controller.Save(s)
	expectSucceed("create %s", s)

	// create a switch with same Name
	err = controller.Save(s)
	expectFail("switch creation of %s for the second time", name)

	// create a router port and switch port
	routerPort := r.CreatePort("router-port-1", "10.216.100.1", 24, "11:11:11:11:11:11")
	switchPort := s.CreatePort("switch-port-1", "10.216.100.1", "11:11:11:11:11:11")
	routerPort.Link(switchPort)
	err = controller.Save(routerPort, switchPort)
	expectSucceed("create router-port-1 and switch-port-2")

	portWithSameIP := s.CreatePort("switch-port-2", "10.116.100.1", "11:11:11:11:11:11")
	err = controller.Save(portWithSameIP)
	expectFail("port creation with IP lower 16 bits conflict")

	// read back data and check
	routerInDB, err := controller.GetRouter(r.Name)
	expectSucceed("get router-1 from db")
	expectSame(r, routerInDB)

	switchInDB, err := controller.GetSwitch(s.Name)
	expectSucceed("get switch-1 from db")
	expectSame(s, switchInDB)

	routerPortInDB, err := controller.GetRouterPort(routerInDB, routerPort.Name)
	expectSucceed("get router port %s from db", routerPort.Name)
	expectSame(routerPort, routerPortInDB)

	routerPortsInDB, err := controller.GetRouterPorts(routerInDB)
	expectSucceed("get router-1 ports from db")
	expectSame(routerPort, routerPortsInDB[0])

	switchPortInDB, err := controller.GetSwitchPort(switchInDB, switchPort.Name)
	expectSucceed("get switch port %s from db", switchPort.Name)
	expectSame(switchPort, switchPortInDB)

	switchPortsInDB, err := controller.GetSwitchPorts(switchInDB)
	expectSucceed("get switch-1 ports from db")
	expectSame(switchPort, switchPortsInDB[0])

	staticRoute := r.CreateStaticRoute("static-route-1", "10.122.100.1", 24, "198.123.44.29", "test")
	err = controller.Save(staticRoute)
	expectSucceed("create static-route-1")

	staticRouteInDb, err := controller.GetRouterStaticRoute(r, staticRoute.Name)
	expectSucceed("get static-route-1 from db")
	expectSame(staticRoute, staticRouteInDb)

	nat1 := r.CreateNAT("nat1", "10.0.0.1", 30, "snat", "10.0.0.1")
	nat2 := r.CreateNAT("nat2", "10.0.1.1", 30, "snat", "10.0.0.2")
	err = controller.Save(nat1, nat2)
	expectSucceed("create nat-1")
	nats, err := controller.GetRouterNATs(r)
	expectSucceed("read nats in db")
	if len(nats) != 2 {
		t.Fatalf("expect to get 2 nat back, but got %d", len(nats))
	}

	nat1InDb, err := controller.GetRouterNAT(r, nat1.Name)
	expectSucceed("read nat1 in db")
	expectSame(nat1, nat1InDb)

	nat2InDb, err := controller.GetRouterNAT(r, nat2.Name)
	expectSucceed("read nat2 in db")
	expectSame(nat2, nat2InDb)

	// test create lsp with auto-generate ip
	swIPAM := logicaldev.NewSwitch("switch-ipam")
	err = controller.Save(swIPAM)
	expectSucceed("create %s", swIPAM)
	for i := 0; i < 16; i++ {
		name := fmt.Sprintf("lsp-ipam-%d", i)
		mac := fmt.Sprintf("12:34:56:78:11:%02x", i)
		switchPort := swIPAM.CreatePort(name, "0.0.0.0", mac)
		err = controller.SaveSwitchPort(switchPort, "172.16.1.1", 28)
		if i < 13 {
			expectSucceed("create %s success", name)
		} else {
			expectFail("cannot create %s", name)
		}
	}

	// delete switch-ipam recursively
	err = controller.Delete(true, swIPAM)
	expectSucceed("remove %s", swIPAM.Name)

	// delete the router recursively
	r2 := logicaldev.NewRouter(r.Name+"1", "")
	err = controller.Save(r2)
	expectSucceed("save %s", r2.Name)

	err = controller.Delete(true, r)
	expectSucceed("remove %s and its children", r.Name)

	// delete r shall not delete r2
	_, err = controller.GetRouter(r2.Name)
	expectSucceed("read %s from etcd", r2.Name)

	err = controller.Delete(false, r2)
	expectSucceed("remove %s", r2.Name)

	err = controller.Delete(false, r2)
	expectFail("remove %s", r2.Name)

	// delete the switch and port
	err = controller.Delete(false, s, switchPort)
	expectSucceed("remove %s, %s", r.Name, routerPort.Name)

	// check device id bitmap
	_, val, err := controller.getIDMap(deviceIDsPath)
	expectSucceed("get %s", deviceIDsPath)
	expectSame(val, "")

	_, err = controller.getKV(versionPath)
	expectSucceed("read version")

	// check there is no garbage left
	cmd := exec.Command("etcdctl", "get", "--prefix=true", "--keys-only=true", "")
	cmd.Env = []string{"ETCDCTL_API=3"}
	data, err := cmd.CombinedOutput()
	expectSucceed("read keys")
	re := regexp.MustCompilePOSIX("\n+")
	keys := re.Split(string(data), -1) // last item is empty string
	if len(keys) > 2 || keys[1] != "" {
		t.Fatalf("unexpected garbage data in etcd3: %#v", keys)
	}
}
