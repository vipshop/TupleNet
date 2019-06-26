package api

import (
	"fmt"
	"encoding/json"
	"github.com/vipshop/tuplenet/control/logger"
	"github.com/vipshop/tuplenet/control/logicaldev"
	"sort"
	"net"
)

type Chassis interface {
	ShowChassis()
	DelChassis()
}

func (b *TuplenetAPI) ShowChassis() {
	var (
		chs []*logicaldev.Chassis
		err error
	)
	name := b.GetString("name")
	logger.Infof("ShowChassis get param %s", name)

	if name  == "" { // no name provided show all chassises
		chs, err = controller.GetChassises()
		if err != nil {
			showStr := fmt.Sprintf("ShowChassis get all chassis failed %s ", err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
			return
		}
	} else { // chassis name provided
		chassis, err := controller.GetChassis(name)
		if err != nil {
			showStr := fmt.Sprintf("ShowChassis get %s chassis failed %s ", name, err)
			logger.Errorf(showStr)
			b.InternalServerErrorResponse(showStr)
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
		logger.Infof("DelChassis decode body failed %s", err)
		b.BadResponse("DelChassis decode body failed please check param")
		return
	}
	logger.Infof("DelChassis get param %s", m.NameOrIP)

	if m.NameOrIP == "" {
		logger.Infof("DelChassis get param failed namOrIP %s", m.NameOrIP)
		b.BadResponse("request nameOrIP param")
		return
	}

	if net.ParseIP(m.NameOrIP) != nil {
		chs, err := controller.GetChassises()
		if err != nil {
			delStr := fmt.Sprintf("DelChassis ip %s get all chassis failed %s ", m.NameOrIP, err)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}

		cnt := 0
		for _, ch := range chs {
			if ch.IP == m.NameOrIP {
				cnt++
				err := delChassisByName(ch.Name)
				if err != nil {
					delStr := fmt.Sprintf("DelChassis ip %s chassis %s failed %s ", m.NameOrIP, ch.Name, err)
					logger.Errorf(delStr)
					b.InternalServerErrorResponse(delStr)
					return
				}
			}
		}
		if cnt == 0 {
			delStr := fmt.Sprintf("DelChassis ip %s chassis failed no such ip in chassises", m.NameOrIP)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}
	} else {
		chassis, err := controller.GetChassis(m.NameOrIP)
		if err != nil {
			delStr := fmt.Sprintf("DelChassis get chassis %s failed %s ", m.NameOrIP, err)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}

		err = controller.Delete(false, chassis)
		if err != nil {
			delStr := fmt.Sprintf("DelChassis chassis %s failed %s ", m.NameOrIP, err)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}
	}

	logger.Infof("DelChassis chassis %s success", m.NameOrIP)
	b.NormalResponse("DelChassis chassis success")
}
