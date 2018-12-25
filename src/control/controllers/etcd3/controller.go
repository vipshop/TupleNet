package etcd3

import (
	"context"
	. "github.com/coreos/etcd/clientv3"
	. "github.com/coreos/etcd/clientv3/clientv3util"
	"github.com/coreos/etcd/clientv3/namespace"
	"github.com/pkg/errors"
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

	// NOTE: enable when needed
	// etcdClient.Watcher = namespace.NewWatcher(etcdClient.Watcher, prefix)
	// etcdClient.Lease = namespace.NewLease(etcdClient.Lease, prefix)

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
			controller.txn([]Cmp{KeyMissing(versionPath)}, []Op{OpPut(versionPath, currentVersion)})
		} else {
			return nil, errors.Wrapf(err, "unable to read version key %s", versionPath)
		}
	} else {
		if currentVersion < v {
			return nil, errors.Errorf("db accessed by higher version controller: %s, local: %s",
				v, currentVersion)
		} else if currentVersion > v {
			controller.txn([]Cmp{Compare(Value(versionPath), "=", v)},
				[]Op{OpPut(versionPath, "")})
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
	return "/entity_view/LS/" + s
}

func switchPortPath(s, p string) string {
	return switchPath(s) + "/lsp/" + p
}

func switchIPBookPath(s string) string {
	return "/ip_book/LS/" + s
}

func routerPath(r string) string {
	return "/entity_view/LR/" + r
}

func routerPortPath(r, p string) string {
	return routerPath(r) + "/lrp/" + p
}

func routerIPBookPath(r string) string {
	return "/ip_book/LR/" + r
}

func routerStaticRoutePath(r, s string) string {
	return routerPath(r) + "/lsr/" + s
}

func chassisPath(c string) string {
	return "/entity_view/chassis/" + c
}

func routerNATPath(r, n string) string {
	return routerPath(r) + "/lnat/" + n
}

// GetSwitch read switch from db given by Name
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

// GetSwitchPort reads a port with Name portName under switch s
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

// GetSwitchPorts reads all ports of switch s
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

// GetRouter read router from db given by Name
func (ptr *Controller) GetRouter(name string) (*Router, error) {
	value, err := ptr.getKV(routerPath(name))
	if err != nil {
		return nil, errors.Wrapf(err, "unable to get router %s", name)
	}

	r := &Router{Name: name}
	UnmarshalTuplenet(r, value)

	return r, nil
}

// GetRouters read all routers from db
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

// GetRouterPort reads a port with Name portName under router
func (ptr *Controller) GetRouterPort(r *Router, portName string) (*RouterPort, error) {
	value, err := ptr.getKV(routerPortPath(r.Name, portName))
	if err != nil {
		return nil, errors.Wrapf(err, "unable to get router port %s", portName)
	}

	rp := &RouterPort{Name: portName, Owner: r}
	UnmarshalTuplenet(rp, value)

	return rp, nil
}

// GetRouterPorts reads all ports of router r
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

// GetRouterStaticRoutes reads all static routes of router r
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

// GetRouterStaticRoute
func (ptr *Controller) GetRouterStaticRoute(r *Router, name string) (*StaticRoute, error) {
	value, err := ptr.getKV(routerStaticRoutePath(r.Name, name))
	if err != nil {
		return nil, errors.Wrapf(err, "unable to get router port %s", name)
	}

	sr := &StaticRoute{Name: name, Owner: r}
	UnmarshalTuplenet(sr, value)

	return sr, nil
}

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

func (ptr *Controller) GetRouterNAT(r *Router, name string) (*NAT, error) {
	value, err := ptr.getKV(routerNATPath(r.Name, name))
	if err != nil {
		return nil, errors.Wrapf(err, "unable to get router nat %s", name)
	}

	nat := &NAT{Name: name, Owner: r}
	UnmarshalTuplenet(nat, value)

	return nat, nil
}

// CreateRouter create a router instance, but it will not be saved to db until you explicitly called Save
func (ptr *Controller) CreateRouter(name string) (*Router, error) {
	_, err := ptr.getKV(routerPath(name))
	if err == nil {
		return nil, errors.Errorf("there already exists a router with the same Name: %s", name)
	} else {
		if errors.Cause(err) != ErrKeyNotFound {
			return nil, err
		}
	}

	return &Router{Name: name}, nil
}

// CreateSwitch create a switch instance, but it will not be saved to db until you explicitly called Save
func (ptr *Controller) CreateSwitch(name string) (*Switch, error) {
	_, err := ptr.getKV(switchPath(name))
	if err == nil {
		return nil, errors.Errorf("there already exists a switch with the same Name: %s", name)
	} else {
		if errors.Cause(err) != ErrKeyNotFound {
			return nil, err
		}
	}

	return &Switch{Name: name}, nil
}

func (ptr *Controller) GetChassis(name string) (*Chassis, error) {
	value, err := ptr.getKV(chassisPath(name))
	if err != nil {
		return nil, errors.Wrapf(err, "unable to get chassis %s", name)
	}

	c := &Chassis{Name: name}
	UnmarshalTuplenet(c, value)

	return c, nil
}

// GetSwitches reads all switches from db
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
func (ptr *Controller) getIDMap(key string) (*IDMap, string, error) {
	value, err := ptr.getKV(key)
	if err != nil && errors.Cause(err) != ErrKeyNotFound {
		return nil, "", err
	}
	return NewIDMap(value), value, nil
}

// Save the object implemented interface{} into db.
// It also performs the heavy lifting of getting a valid device id for router, switch
// checking it an IP is already used by other port
func (ptr *Controller) Save(devs ...interface{}) error {
	// logging can be removed when it becomes stable
	ptr.logger.Debugf("-----start: save transaction-----")
	defer ptr.logger.Debugf("-----end: save transaction-----")

	var (
		err    error
		idMaps = make(map[string]struct {
			m *IDMap
			o string
		}) // o: old value
		cmps []Cmp
		ops  []Op
		k    string
		v    string
	)

	allocateID := func() (uint32, error) {
		idMap, found := idMaps[deviceIDsPath]
		if !found {
			idMap.m, idMap.o, err = ptr.getIDMap(deviceIDsPath)
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
			idMap.m, idMap.o, err = ptr.getIDMap(key)
			if err != nil {
				return err
			}
			idMaps[key] = idMap
		}
		ok := idMap.m.OccupyMasked(ipv4ToU32(ip))
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

	for k, idmap := range idMaps {
		n := idmap.m.String()
		if idmap.o == "" {
			ptr.logger.Debugf("creating %s: %s", k, n)
			cmps = append(cmps, KeyMissing(k))
		} else {
			ptr.logger.Debugf("updating %s: %s -> %s", k, idmap.o, n)
			cmps = append(cmps, Compare(Value(k), "=", idmap.o))
		}
		ops = append(ops, OpPut(k, n))
	}

	err = ptr.txn(cmps, ops)
	if err != nil {
		return errors.Wrap(err, "unable to perform save")
	}

	return nil
}

// Delete any device from db, recycle the device id
// is recursive is true, the provided key is used as a prefix
// It also performs the heavy lifting of reclaim the id for router, switch and ip for port
func (ptr *Controller) Delete(recursive bool, devs ...interface{}) error {
	// logging can be removed when it becomes stable
	ptr.logger.Debugf("-----start: delete transaction-----")
	defer ptr.logger.Debugf("-----end: delete transaction-----")
	var (
		err    error
		idMaps = make(map[string]struct {
			m *IDMap
			o string
		}) // o: old value
		cmps []Cmp
		ops  []Op
		keys = make([]string, 0)
	)

	returnID := func(id uint32) error {
		idMap, found := idMaps[deviceIDsPath]
		if !found {
			idMap.m, idMap.o, err = ptr.getIDMap(deviceIDsPath)
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
			idMap.m, idMap.o, err = ptr.getIDMap(key)
			if err != nil && errors.Cause(err) != ErrKeyNotFound {
				return err
			}
			idMaps[key] = idMap
		}
		idMap.m.ReturnMasked(ipv4ToU32(ip))
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
				ops = append(ops, OpDelete(k, WithPrefix()))
			} else {
				ops = append(ops, OpDelete(k))
			}
		}
	}

	for key, idmap := range idMaps {
		n := idmap.m.String()
		if idmap.o == "" {
			cmps = append(cmps, KeyMissing(key))
		} else {
			cmps = append(cmps, Compare(Value(key), "=", idmap.o))
		}
		if idmap.m.Size() == 0 {
			ptr.logger.Debugf("deleting: %s", key)
			ops = append(ops, OpDelete(key))
		} else {
			ptr.logger.Debugf("updating: %s %s -> %s", key, idmap.o, n)
			ops = append(ops, OpPut(key, n))
		}
	}

	err = ptr.txn(cmps, ops)
	if err != nil {
		return errors.Wrap(err, "unable to perform delete")
	}

	return nil
}

// txn perform a transaction given the predicated and actions
func (ptr *Controller) txn(cmps []Cmp, ops []Op) error {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second*time.Duration(requestTimeoutSeconds))
	resp, err := ptr.etcdClient.Txn(ctx).
		If(cmps...).
		Then(ops...).
		Commit()
	cancel()

	if err != nil {
		return errors.Wrap(err, "unable to transaction %v")
	}

	if !resp.Succeeded {
		return errors.Errorf("put fail with comparisons evaluated as false")
	}

	return nil
}

// getKV retrieves the value from Controller.keyPrefix + halfPath
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

// getKVs retrieves all key,value from a prefix as: Controller.keyPrefix + halfPrefix
func (ptr *Controller) getKVs(prefix string) (map[string]string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second*time.Duration(requestTimeoutSeconds))
	resp, err := ptr.etcdClient.Get(ctx, prefix, WithPrefix(), WithSort(SortByKey, SortAscend))
	cancel()

	if err != nil {
		return nil, errors.Wrapf(err, "unable to read keys from %s", prefix)
	}

	result := make(map[string]string)
	for _, kv := range resp.Kvs {
		key := string(kv.Key)
		name := key[len(prefix):]
		if !strings.Contains(name, "/") { // "sub-folder" skipped
			result[name] = string(kv.Value)
		}
	}

	return result, nil
}

func (ptr *Controller) Close() {
	ptr.etcdClient.Close()
}
