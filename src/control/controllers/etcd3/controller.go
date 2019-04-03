package etcd3

import (
	"bytes"
	"context"
	"fmt"
	. "github.com/coreos/etcd/clientv3"
	. "github.com/coreos/etcd/clientv3/clientv3util"
	"github.com/coreos/etcd/clientv3/namespace"
	"github.com/coreos/etcd/etcdserver/etcdserverpb"
	"github.com/pkg/errors"
	"github.com/vipshop/tuplenet/control/controllers/bookkeeping"
	. "github.com/vipshop/tuplenet/control/logicaldev"
	"go.uber.org/zap"
	"reflect"
	"strings"
	"time"
)

const (
	versionPath           = "/globals/version"
	deviceIDsPath         = "/globals/device_ids"
	requestTimeoutSeconds = 3

	switchRootPath       = "/entity_view/LS/"
	switchIPBookRootPath = "/ip_book/LS/"

	routerRootPath       = "/entity_view/LR/"
	routerIPBookRootPath = "/ip_book/LR/"

	chassisRootPath = "/entity_view/chassis/"
)

var (
	currentVersion = "1"
	ErrKeyNotFound = errors.New("key not found")
)

// Controller shall be stateless
type Controller struct {
	etcdClient *Client
	logger     *zap.SugaredLogger
}

// NewController return a controller given serverAddresses as a slice of etcd3 server addresses
func NewController(serverAddresses []string, prefix string, loggingOn bool) (*Controller, error) {
	cfg := Config{
		Endpoints:   serverAddresses,
		DialTimeout: 5 * time.Second,
	}

	etcdClient, err := New(cfg)
	if err != nil {
		return nil, errors.Wrap(err, "Unable to setup etcd3 client")
	}

	// perform a test on the provided addresses
	ctx, cancel := context.WithTimeout(context.Background(), time.Second*time.Duration(requestTimeoutSeconds))
	_, err = etcdClient.MemberList(ctx)

	if err != nil {
		return nil, err
	}
	cancel()

	prefix = strings.TrimRight(prefix, "/")
	etcdClient.KV = namespace.NewKV(etcdClient.KV, prefix)
	etcdClient.Watcher = namespace.NewWatcher(etcdClient.Watcher, prefix)
	etcdClient.Lease = namespace.NewLease(etcdClient.Lease, prefix)

	controller := Controller{
		etcdClient: etcdClient,
	}

	err = controller.SyncDeviceID(false)
	if err != nil {
		return nil, err
	}
	// perform library version check
	v, err := controller.getKV(versionPath)
	if err != nil {
		if errors.Cause(err) == ErrKeyNotFound {
			err = controller.txn([]Cmp{KeyMissing(versionPath)}, []Op{OpPut(versionPath, currentVersion)})
			if err != nil {
				return nil, errors.Wrap(err, "unable to create version key")
			}
		} else {
			return nil, errors.Wrapf(err, "unable to read version key %s", versionPath)
		}
	} else {
		if currentVersion < v {
			return nil, errors.Errorf("db accessed by higher version controller: %s, local: %s",
				v, currentVersion)
		} else if currentVersion > v {
			err = controller.txn([]Cmp{Compare(Value(versionPath), "=", v)}, []Op{OpPut(versionPath, currentVersion)})
			if err != nil {
				return nil, errors.Wrap(err, "unable to update version key")
			}
		}
	}

	if loggingOn {
		l, _ := zap.NewDevelopment()
		controller.logger = l.Sugar()
	} else {
		controller.logger = zap.NewNop().Sugar()
	}

	return &controller, nil
}

func switchPath(s string) string {
	return switchRootPath + s
}

func switchPortPath(s, p string) string {
	return switchPath(s) + "/lsp/" + p
}

func switchIPBookPath(s string) string {
	return switchIPBookRootPath + s
}

func routerPath(r string) string {
	return routerRootPath + r
}

func routerPortPath(r, p string) string {
	return routerPath(r) + "/lrp/" + p
}

func routerIPBookPath(r string) string {
	return routerIPBookRootPath + r
}

func routerStaticRoutePath(r, s string) string {
	return routerPath(r) + "/lsr/" + s
}

func chassisPath(c string) string {
	return chassisRootPath + c
}

func routerNATPath(r, n string) string {
	return routerPath(r) + "/lnat/" + n
}

// GetSwitch read the named switch from db
func (ptr *Controller) GetSwitch(name string) (*Switch, error) {
	value, err := ptr.getKV(switchPath(name))
	if err != nil {
		return nil, errors.Wrapf(err, "unable to get switch %s", name)
	}

	s := &Switch{Name: name}
	UnmarshalTuplenet(s, value)

	return s, nil
}

// GetSwitches reads all switches from db
func (ptr *Controller) GetSwitches() ([]*Switch, error) {
	kvs, err := ptr.getKVs(switchPath(""))
	if err != nil {
		return nil, errors.Wrap(err, "unable to get switches")
	}

	switches := make([]*Switch, 0, len(kvs))
	for name, value := range kvs {
		s := &Switch{Name: name}
		UnmarshalTuplenet(s, value)
		switches = append(switches, s)
	}

	return switches, nil
}

// GetSwitchPort reads named port under Switch s from db
func (ptr *Controller) GetSwitchPort(s *Switch, portName string) (*SwitchPort, error) {
	key := switchPortPath(s.Name, portName)
	value, err := ptr.getKV(key)
	if err != nil {
		return nil, errors.Wrapf(err, "unable to get switch port %s", portName)
	}

	sp := &SwitchPort{Name: portName, Owner: s}
	UnmarshalTuplenet(sp, value)
	return sp, nil
}

// GetSwitchPorts reads all ports under Switch s from db
func (ptr *Controller) GetSwitchPorts(s *Switch) ([]*SwitchPort, error) {
	kvs, err := ptr.getKVs(switchPortPath(s.Name, ""))
	if err != nil {
		return nil, errors.Wrap(err, "unable to get switch ports")
	}

	ports := make([]*SwitchPort, 0, len(kvs))
	for name, value := range kvs {
		sp := &SwitchPort{Name: name, Owner: s}
		UnmarshalTuplenet(sp, value)
		ports = append(ports, sp)
	}

	return ports, nil
}

// GetRouter reads the named router from db
func (ptr *Controller) GetRouter(name string) (*Router, error) {
	value, err := ptr.getKV(routerPath(name))
	if err != nil {
		return nil, errors.Wrapf(err, "unable to get router %s", name)
	}

	r := &Router{Name: name}
	UnmarshalTuplenet(r, value)

	return r, nil
}

// GetRouters reads all routers from db
func (ptr *Controller) GetRouters() ([]*Router, error) {
	kvs, err := ptr.getKVs(routerPath(""))
	if err != nil {
		return nil, errors.Wrap(err, "unable to get routers")
	}

	routers := make([]*Router, 0, len(kvs))
	for name, value := range kvs {
		r := &Router{Name: name}
		UnmarshalTuplenet(r, value)
		routers = append(routers, r)
	}

	return routers, nil
}

// GetRouterPort reads the named port under Router r
func (ptr *Controller) GetRouterPort(r *Router, portName string) (*RouterPort, error) {
	value, err := ptr.getKV(routerPortPath(r.Name, portName))
	if err != nil {
		return nil, errors.Wrapf(err, "unable to get router port %s", portName)
	}

	rp := &RouterPort{Name: portName, Owner: r}
	UnmarshalTuplenet(rp, value)

	return rp, nil
}

// GetRouterPorts reads all ports of Router r from db
func (ptr *Controller) GetRouterPorts(r *Router) ([]*RouterPort, error) {
	kvs, err := ptr.getKVs(routerPortPath(r.Name, ""))
	if err != nil {
		return nil, errors.Wrap(err, "unable to get router ports")
	}

	ports := make([]*RouterPort, 0, len(kvs))
	for name, value := range kvs {
		rp := &RouterPort{Name: name, Owner: r}
		UnmarshalTuplenet(rp, value)
		ports = append(ports, rp)
	}

	return ports, nil
}

// GetRouterStaticRoutes reads all static routes of router r from db
func (ptr *Controller) GetRouterStaticRoutes(r *Router) ([]*StaticRoute, error) {
	kvs, err := ptr.getKVs(routerStaticRoutePath(r.Name, ""))
	if err != nil {
		return nil, errors.Wrap(err, "unable to get router static routes")
	}

	srs := make([]*StaticRoute, 0, len(kvs))
	for name, value := range kvs {
		sr := &StaticRoute{Name: name, Owner: r}
		UnmarshalTuplenet(sr, value)
		srs = append(srs, sr)
	}

	return srs, nil
}

// GetRouterStaticRoute reads the named static route under Router r from db
func (ptr *Controller) GetRouterStaticRoute(r *Router, name string) (*StaticRoute, error) {
	value, err := ptr.getKV(routerStaticRoutePath(r.Name, name))
	if err != nil {
		return nil, errors.Wrapf(err, "unable to get router port %s", name)
	}

	sr := &StaticRoute{Name: name, Owner: r}
	UnmarshalTuplenet(sr, value)

	return sr, nil
}

// GetRouterNATs reads all NAT config under Router r from db
func (ptr *Controller) GetRouterNATs(r *Router) ([]*NAT, error) {
	kvs, err := ptr.getKVs(routerNATPath(r.Name, ""))
	if err != nil {
		return nil, errors.Wrap(err, "unable to get router nats")
	}

	nats := make([]*NAT, 0, len(kvs))
	for name, value := range kvs {
		nat := &NAT{Name: name, Owner: r}
		UnmarshalTuplenet(nat, value)
		nats = append(nats, nat)
	}

	return nats, nil
}

// GetRouterNATs reads named NAT config under Router r from db
func (ptr *Controller) GetRouterNAT(r *Router, name string) (*NAT, error) {
	value, err := ptr.getKV(routerNATPath(r.Name, name))
	if err != nil {
		return nil, errors.Wrapf(err, "unable to get router nat %s", name)
	}

	nat := &NAT{Name: name, Owner: r}
	UnmarshalTuplenet(nat, value)

	return nat, nil
}

// GetChassis reads named chassis from db
func (ptr *Controller) GetChassis(name string) (*Chassis, error) {
	value, err := ptr.getKV(chassisPath(name))
	if err != nil {
		return nil, errors.Wrapf(err, "unable to get chassis %s", name)
	}

	c := &Chassis{Name: name}
	UnmarshalTuplenet(c, value)

	return c, nil
}

// GetChassises reads all chasisses from db
func (ptr *Controller) GetChassises() ([]*Chassis, error) {
	kvs, err := ptr.getKVs(chassisPath(""))
	if err != nil {
		return nil, errors.Wrap(err, "unable to get chassises")
	}

	chs := make([]*Chassis, 0, len(kvs))
	for name, value := range kvs {
		c := &Chassis{Name: name}
		UnmarshalTuplenet(c, value)
		chs = append(chs, c)
	}

	return chs, nil
}

func (ptr *Controller) RebuildIPBooks() (err error) {
	defer func() {
		if err != nil { // give error a context
			err = errors.Wrap(err, "unable to rebuild IP book")
		}
	}()

	routers, err := ptr.GetRouters()
	if err != nil {
		return
	}

	for _, r := range routers {
		key := routerIPBookPath(r.Name)
		oldVal, _ := ptr.getKV(key)
		ipBook := bookkeeping.NewIDMap("")

		ports, err := ptr.GetRouterPorts(r)
		if err != nil {
			return err
		}
		for _, p := range ports {
			if !ipBook.OccupyMasked(bookkeeping.IPv4ToU32(p.IP)) {
				return errors.Errorf("%s of %s with others in %s", p.IP, p.Name, r.Name)
			}
		}

		newVal := ipBook.String()
		if newVal != oldVal {
			if oldVal == "" {
				err = ptr.txn([]Cmp{KeyMissing(key)}, []Op{OpPut(key, newVal)})
			} else {
				err = ptr.txn([]Cmp{Compare(Value(key), "=", oldVal)}, []Op{OpPut(key, newVal)})
			}
			if err != nil {
				return err
			}
		}
	}

	switches, err := ptr.GetSwitches()
	if err != nil {
		return
	}

	for _, sw := range switches {
		key := switchIPBookPath(sw.Name)
		oldVal, _ := ptr.getKV(key)
		ipBook := bookkeeping.NewIDMap("")

		ports, err := ptr.GetSwitchPorts(sw)
		if err != nil {
			return err
		}
		for _, p := range ports {
			if !ipBook.OccupyMasked(bookkeeping.IPv4ToU32(p.IP)) {
				return errors.Errorf("%s of %s with others in %s", p.IP, p.Name, sw.Name)
			}
		}

		newVal := ipBook.String()
		if newVal != oldVal {
			if oldVal == "" {
				err = ptr.txn([]Cmp{KeyMissing(key)}, []Op{OpPut(key, newVal)})
			} else {
				err = ptr.txn([]Cmp{Compare(Value(key), "=", oldVal)}, []Op{OpPut(key, newVal)})
			}
			if err != nil {
				return err
			}
		}
	}

	return nil
}

// SyncDeviceID will sync the device id bitmap based on all routers and switches in db
func (ptr *Controller) SyncDeviceID(forceSync bool) error {
	// record old bitmap first before reading devices
	devMap, val, err := ptr.getIDMap(deviceIDsPath)
	if err != nil {
		return errors.Wrap(err, "unable to read device id bitmap from %s")
	}

	if val != "" && !forceSync {
		// neither create nor force sync
		return nil
	}

	routers, err := ptr.GetRouters()
	if err != nil {
		return errors.Wrap(err, "unable to sync device id")
	}

	switches, err := ptr.GetSwitches()
	if err != nil {
		return errors.Wrap(err, "unable to sync device id")
	}

	devMap.Clear()
	for _, r := range routers {
		devMap.Occupy(r.ID)
	}
	for _, s := range switches {
		devMap.Occupy(s.ID)
	}

	// perform a CAS write
	newVal := devMap.String()
	if val == "" {
		err = ptr.txn([]Cmp{KeyMissing(deviceIDsPath)}, []Op{OpPut(deviceIDsPath, newVal)})
	} else {
		err = ptr.txn([]Cmp{Compare(Value(deviceIDsPath), "=", val)}, []Op{OpPut(deviceIDsPath, newVal)})
	}

	if err != nil {
		return errors.Wrap(err, "unable to re-sync device id")
	}

	return nil
}

// getIPMap is a helper function to read id map from db
func (ptr *Controller) getIDMap(key string) (*bookkeeping.IDMap, string, error) {
	value, err := ptr.getKV(key)
	if err != nil && errors.Cause(err) != ErrKeyNotFound {
		return nil, "", err
	}
	return bookkeeping.NewIDMap(value), value, nil
}

// allocate an IP address for switch port
func (ptr *Controller) allocSwitchPortIP(
	switchName string,
	cip string,
	cprefix uint8) (ip string, oldVal string, newVal string, err error) {

	ip = ""
	oldVal = ""
	newVal = ""
	_, err = ptr.GetSwitch(switchName)
	if err != nil {
		err = errors.Errorf("failed to find switch %s: %v", switchName, err)
		return
	}

	ipMap, _, err := ptr.getIDMap(switchIPBookPath(switchName))
	if err != nil {
		err = errors.Errorf("failed to fetch %s's IPBook: %v", switchName, err)
		return
	}

	oldVal = ipMap.String()
	cipInt := bookkeeping.IPv4ToU32(cip)
	cipInt = (cipInt >> (32 - cprefix)) << (32 - cprefix)
	// make sure the max would not above 0xffff
	max := uint32((((1 << (32 - cprefix)) - 1) | cipInt) & 0xffff)
	nextID, err := ipMap.NextIDFrom(uint16(cipInt) + 2) // skip IP like 10.10.1.0 and 10.10.1.1
	if err != nil {
		err = errors.Errorf("failed to allocate new ID, all were occupied")
		return
	}
	ptr.logger.Debugf("max:0x%x, nextID:0x%x", max, nextID)
	if nextID >= max {
		err = errors.Errorf("failed to allocate new IP, all IP were occupied")
		return
	}

	ipInt := cipInt | nextID
	ip = bookkeeping.U32ToIPv4(int64(ipInt))
	ptr.logger.Debugf("allocate a new IP:%s", ip)
	return ip, oldVal, ipMap.String(), nil
}

func (ptr *Controller) SaveSwitchPort(
	sp *SwitchPort, cip string, cprefix uint8) error {
	var prevIP string = ""
	for {
		var (
			cmps []Cmp
			ops  []Op
			k, v string
		)

		ip, oldVal, newVal, err := ptr.allocSwitchPortIP(sp.Owner.Name,
			cip, cprefix)
		if err != nil {
			return err
		}

		sp.IP = ip
		sp.MAC = MacFromIP(ip)
		k = switchPortPath(sp.Owner.Name, sp.Name)
		v = MarshalTuplenet(sp)
		cmps = append(cmps, KeyMissing(k))
		ops = append(ops, OpPut(k, v))
		key := switchIPBookPath(sp.Owner.Name)
		if ipMap, ov, err := ptr.getIDMap(key); err == nil {
			if ov != "" {
				cmps = append(cmps, Compare(Value(key), "=", oldVal))
				ptr.logger.Debugf("try to update %s:%s -> %s", key,
					ipMap.String(), newVal)
			} else {
				cmps = append(cmps, KeyMissing(key))
				ptr.logger.Debugf("try to create %s:%s", key, newVal)
			}
		} else {
			return errors.Wrap(err, "failed to get ipMap from etcd side")
		}
		ops = append(ops, OpPut(key, newVal))

		if prevIP == ip {
			return errors.Errorf("Error, re-generate same IP %s", ip)
		}
		prevIP = ip

		ptr.logger.Debugf("-----start: save lsp transaction-----")
		defer ptr.logger.Debugf("-----end: save lsp transaction-----")
		err = ptr.txn(cmps, ops)
		if err != nil {
			ptr.logger.Debugf("remote side may be change, redo again")
			continue
		} else {
			ptr.logger.Debugf("create a switch port %s[ip:%s]", sp.Name, sp.IP)
			return nil
		}
	}
}

// Save devices into db.
// It also performs the heavy lifting of:
//   1. getting a valid device id for router, switch
//   2. checking if an IP is already used by other port
func (ptr *Controller) Save(devs ...interface{}) error {
	// logging can be removed when it becomes stable
	ptr.logger.Debugf("-----start: save transaction-----")
	defer ptr.logger.Debugf("-----end: save transaction-----")

	var (
		err    error
		idMaps = make(map[string]struct {
			m      *bookkeeping.IDMap
			oldVal string
		})
		cmps []Cmp
		ops  []Op
		k    string
		v    string
	)

	allocateID := func() (uint32, error) {
		idMap, found := idMaps[deviceIDsPath]
		if !found {
			idMap.m, idMap.oldVal, err = ptr.getIDMap(deviceIDsPath)
			if err != nil {
				return 0, err
			}
			idMaps[deviceIDsPath] = idMap
		}
		return idMap.m.NextID()
	}

	markIPUsed := func(key, ip string) error {
		idMap, found := idMaps[key]
		if !found {
			idMap.m, idMap.oldVal, err = ptr.getIDMap(key)
			if err != nil {
				return err
			}
			idMaps[key] = idMap
		}
		ok := idMap.m.OccupyMasked(bookkeeping.IPv4ToU32(ip))
		if !ok {
			return errors.Errorf("lower 16 bits of %s conflict with other IP", ip)
		}
		return nil
	}

	for _, dev := range devs {
		if !reflect.ValueOf(dev).IsValid() {
			return errors.Errorf("unable to save %+v, invalid dev passed ", dev)
		}

		err = nil
		switch t := dev.(type) {
		case *Switch:
			if t.ID == 0 {
				t.ID, err = allocateID()
			}
			k = switchPath(t.Name)
		case *Router:
			if t.ID == 0 {
				t.ID, err = allocateID()
			}
			k = routerPath(t.Name)
		case *SwitchPort:
			err = markIPUsed(switchIPBookPath(t.Owner.Name), t.IP)
			k = switchPortPath(t.Owner.Name, t.Name)
		case *RouterPort:
			err = markIPUsed(routerIPBookPath(t.Owner.Name), t.IP)
			k = routerPortPath(t.Owner.Name, t.Name)
		case *Chassis:
			k = chassisPath(t.Name)
		case *StaticRoute:
			k = routerStaticRoutePath(t.Owner.Name, t.Name)
		case *NAT:
			k = routerNATPath(t.Owner.Name, t.Name)
		default:
			err = errors.New("supported type")
		}

		if err != nil {
			return errors.Wrapf(err, "unable to save %v", dev)
		}

		v = MarshalTuplenet(dev)
		ptr.logger.Debugf("saving %s : %s", k, v)
		cmps = append(cmps, KeyMissing(k))
		ops = append(ops, OpPut(k, v))
	}

	for key, idMap := range idMaps {
		newVal := idMap.m.String()

		if idMap.oldVal == "" { // new switch or router is created
			ptr.logger.Debugf("creating %s: %s", key, newVal)
			cmps = append(cmps, KeyMissing(key))
			ops = append(ops, OpPut(key, newVal))
		} else {
			ptr.logger.Debugf("updating %s: %s -> %s", key, idMap.oldVal, newVal)
			cmps = append(cmps, Compare(Value(key), "=", idMap.oldVal))
			if newVal != idMap.oldVal {
				ops = append(ops, OpPut(key, newVal))
			}
		}
	}

	err = ptr.txn(cmps, ops)
	if err != nil {
		return errors.Wrap(err, "unable to perform save")
	}

	return nil
}

// Delete devices from db, recycle the device id or IP map if neccessary
// if recursive is true, all children devices will be removed as well
func (ptr *Controller) Delete(recursive bool, devs ...interface{}) error {
	// logging can be removed when it becomes stable
	ptr.logger.Debugf("-----start: delete transaction-----")
	defer ptr.logger.Debugf("-----end: delete transaction-----")
	var (
		err    error
		idMaps = make(map[string]struct {
			m      *bookkeeping.IDMap
			oldVal string
		})
		cmps []Cmp
		ops  []Op
		keys = make([]string, 0)
	)

	returnID := func(id uint32) error {
		idMap, found := idMaps[deviceIDsPath]
		if !found {
			idMap.m, idMap.oldVal, err = ptr.getIDMap(deviceIDsPath)
			if err != nil {
				return errors.Wrap(err, "unable to read device map")
			}
			idMaps[deviceIDsPath] = idMap
		}
		idMap.m.Return(id)
		return nil
	}

	returnIP := func(key, ip string) error {
		idMap, found := idMaps[key]
		if !found {
			idMap.m, idMap.oldVal, err = ptr.getIDMap(key)
			if err != nil {
				return err
			}
			idMaps[key] = idMap
		}
		idMap.m.ReturnMasked(bookkeeping.IPv4ToU32(ip))
		return nil
	}

	for _, dev := range devs {
		if !reflect.ValueOf(dev).IsValid() {
			return errors.Errorf("unable to delete %+v, invalid dev passed ", dev)
		}

		keys, err = keys[:0], nil
		switch t := dev.(type) {
		case *Switch:
			err = returnID(t.ID)
			keys = append(keys, switchPath(t.Name))
			if recursive {
				keys = append(keys, switchIPBookPath(t.Name))
			}
		case *Router:
			err = returnID(t.ID)
			keys = append(keys, routerPath(t.Name))
			if recursive {
				keys = append(keys, routerIPBookPath(t.Name))
			}
		case *SwitchPort:
			err = returnIP(switchIPBookPath(t.Owner.Name), t.IP)
			keys = append(keys, switchPortPath(t.Owner.Name, t.Name))
		case *RouterPort:
			err = returnIP(routerIPBookPath(t.Owner.Name), t.IP)
			keys = append(keys, routerPortPath(t.Owner.Name, t.Name))
		case *Chassis:
			keys = append(keys, chassisPath(t.Name))
		case *StaticRoute:
			keys = append(keys, routerStaticRoutePath(t.Owner.Name, t.Name))
		case *NAT:
			keys = append(keys, routerNATPath(t.Owner.Name, t.Name))
		default:
			err = errors.New("supported type")
		}

		if err != nil {
			return errors.Errorf("unable to save %v", dev)
		}

		for _, k := range keys {
			ptr.logger.Debugf("deleting: %s", k)
			if recursive {
				ops = append(ops, OpDelete(k+"/", WithPrefix()))
			}
			ops = append(ops, OpDelete(k))
			cmps = append(cmps, KeyExists(k))
		}
	}

	for key, idMap := range idMaps {
		newVal := idMap.m.String()

		cmps = append(cmps, Compare(Value(key), "=", idMap.oldVal))
		if idMap.m.Size() == 0 {
			ptr.logger.Debugf("deleting: %s", key)
			ops = append(ops, OpDelete(key))
		} else {
			ptr.logger.Debugf("updating: %s %s -> %s", key, idMap.oldVal, newVal)
			if newVal != idMap.oldVal {
				ops = append(ops, OpPut(key, newVal))
			}
		}
	}

	err = ptr.txn(cmps, ops)
	if err != nil {
		return errors.Wrap(err, "unable to perform delete")
	}

	return nil
}

// txn performs a etcd transaction given the predicates and actions
func (ptr *Controller) txn(cmps []Cmp, ops []Op) error {
	retrieveOps := make([]Op, 0, len(cmps))
	for _, cmp := range cmps {
		retrieveOps = append(retrieveOps, OpGet(string(cmp.Key)))
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Second*time.Duration(requestTimeoutSeconds))
	resp, err := ptr.etcdClient.Txn(ctx).
		If(cmps...).
		Then(ops...).
		Else(retrieveOps...).
		Commit()
	cancel()

	if err != nil {
		return errors.Wrap(err, "unable to perform transaction")
	}

	if !resp.Succeeded {
		var reasons []string
		for i := range cmps {
			switch cmps[i].Target {
			case etcdserverpb.Compare_VERSION:
				if len(resp.Responses[i].GetResponseRange().Kvs) == 0 { // deleted case
					reasons = append(reasons, fmt.Sprintf("%s does not exist", string(cmps[i].Key)))
				} else { // create case
					reasons = append(reasons, fmt.Sprintf("%s already exists", string(cmps[i].Key)))
				}
			case etcdserverpb.Compare_VALUE: // update case
				kvs := resp.Responses[i].GetResponseRange().Kvs
				if len(kvs) == 0 {
					reasons = append(reasons, fmt.Sprintf("%s does not exist", string(cmps[i].Key)))
				} else {
					valInDb := kvs[0].Value
					if !bytes.Equal(cmps[i].ValueBytes(), valInDb) {
						reasons = append(reasons,
							fmt.Sprintf(`key %s previous != current: "%s" != "%s"`,
								string(cmps[i].Key), string(cmps[i].ValueBytes()), string(valInDb)))
					}
				}
			}
		}

		return errors.Errorf("transaction fail with comparisons evaluated as false: %s",
			strings.Join(reasons, ";"))
	}

	return nil
}

// getKV retrieves the value of key
func (ptr *Controller) getKV(key string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second*time.Duration(requestTimeoutSeconds))
	resp, err := ptr.etcdClient.Get(ctx, key)
	cancel()

	if err != nil {
		return "", errors.Wrapf(err, "unable to read key %s", key)
	}

	if resp.Count == 0 {
		return "", errors.Wrapf(ErrKeyNotFound, "unable to read key %s", key)
	}

	return string(resp.Kvs[0].Value), nil
}

// getKVs retrieves all kv pairs from a prefix, if the prefix happens to be the a key, that kv pair will be excluded
func (ptr *Controller) getKVs(prefix string) (map[string]string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second*time.Duration(requestTimeoutSeconds))
	resp, err := ptr.etcdClient.Get(ctx, prefix, WithPrefix())
	cancel()

	if err != nil {
		return nil, errors.Wrapf(err, "unable to read keys from %s", prefix)
	}

	result := make(map[string]string)
	for _, kv := range resp.Kvs {
		key := string(kv.Key)
		name := key[len(prefix):]
		if !strings.Contains(name, "/") {
			result[name] = string(kv.Value)
		}
	}

	return result, nil
}

// Close the etcd connection
func (ptr *Controller) Close() {
	ptr.etcdClient.Close()
}
