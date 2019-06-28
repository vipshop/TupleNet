package api

import (
	"encoding/json"
	"github.com/vipshop/tuplenet/control/logger"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"sort"
	"net"
	"net/http"
)

func (b *TuplenetAPI) ShowChassis() {
	var (
		chs []*logicaldev.Chassis
		err error
	)
	name := b.GetString("name")
	logger.Infof("ShowChassis get param %s", name)

	if CheckNilParam(name) { // no name provided show all chassises
		chs, err = controller.GetChassises()
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowChassis get all chassis failed %s ", err)
			return
		}
	} else { // chassis name provided
		chassis, err := controller.GetChassis(name)
		if err != nil {
			b.Response(http.StatusInternalServerError, "ShowChassis get %s chassis failed %s ", err, name)
			return
		}

		chs = []*logicaldev.Chassis{chassis}
	}

	sort.Slice(chs, func(i, j int) bool { return chs[i].Name < chs[j].Name })
	logger.Infof("ShowChassis %s success", name)
	b.NormalResponse(chs)
}

func delChassisByName(name string) error {
	chassis, err := controller.GetChassis(name)
	if err != nil {
		return err
	}
	err = controller.Delete(false, chassis)
	if err != nil {
		return err
	}
	return nil
}

func (b *TuplenetAPI) DelChassis() {
	var (
		m ChassisRequest
	)
	err := json.NewDecoder(b.Ctx.Request.Body).Decode(&m)
	if err != nil {
		b.Response(http.StatusBadRequest, "DelChassis decode get param body failed %s", err)
		return
	}
	logger.Infof("DelChassis get param %s", m.NameOrIP)

	if CheckNilParam(m.NameOrIP) {
		b.Response(http.StatusBadRequest, "DelChassis get param failed namOrIP %s", nil, m.NameOrIP)
		return
	}

	if net.ParseIP(m.NameOrIP) != nil {
		chs, err := controller.GetChassises()
		if err != nil {
			b.Response(http.StatusInternalServerError, "DelChassis ip %s get all chassis failed %s ", err, m.NameOrIP)
			return
		}

		cnt := 0
		for _, ch := range chs {
			if ch.IP == m.NameOrIP {
				cnt++
				err := delChassisByName(ch.Name)
				if err != nil {
					b.Response(http.StatusInternalServerError, "DelChassis ip %s chassis %s failed %s ", err, m.NameOrIP, ch.Name)
					return
				}
			}
		}
		if cnt == 0 {
			b.Response(http.StatusInternalServerError, "DelChassis ip %s chassis failed no such ip in chassises", nil, m.NameOrIP)
			return
		}
	} else {
		chassis, err := controller.GetChassis(m.NameOrIP)
		if err != nil {
			b.Response(http.StatusInternalServerError, "DelChassis get chassis %s failed %s ", err, m.NameOrIP)
			return
		}

		err = controller.Delete(false, chassis)
		if err != nil {
			b.Response(http.StatusInternalServerError, "DelChassis chassis %s failed %s ", err, m.NameOrIP)
			return
		}
	}

	b.Response(http.StatusOK, "DelChassis chassis %s success", nil, m.NameOrIP)
}
