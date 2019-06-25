package api

import (
	"fmt"
	"io/ioutil"
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
		m   ChassisRequest
		chs []*logicaldev.Chassis
		err error
	)

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Name

	if name == "" { // no name provided show all chassises
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
	logger.Debugf("ShowChassis %s success", name)
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

	body, _ := ioutil.ReadAll(b.Ctx.Request.Body)
	json.Unmarshal(body, &m)
	name := m.Name

	if name == "" {
		logger.Errorf("DelChassis get param failed name %s", name)
		b.BadResponse("request name param")
		return
	}

	if net.ParseIP(name) != nil {
		chs, err := controller.GetChassises()
		if err != nil {
			delStr := fmt.Sprintf("DelChassis ip %s get all chassis failed %s ", name, err)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}

		cnt := 0
		for _, ch := range chs {
			if ch.IP == name {
				cnt++
				err := delChassisByName(ch.Name)
				if err != nil {
					delStr := fmt.Sprintf("DelChassis ip %s chassis %s failed %s ", name, ch.Name, err)
					logger.Errorf(delStr)
					b.InternalServerErrorResponse(delStr)
					return
				}
			}
		}
		if cnt == 0 {
			delStr := fmt.Sprintf("DelChassis ip %s chassis failed no such ip in chassises", name)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}
	} else {
		chassis, err := controller.GetChassis(name)
		if err != nil {
			delStr := fmt.Sprintf("DelChassis get chassis %s failed %s ", name, err)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}

		err = controller.Delete(false, chassis)
		if err != nil {
			delStr := fmt.Sprintf("DelChassis chassis %s failed %s ", name, err)
			logger.Errorf(delStr)
			b.InternalServerErrorResponse(delStr)
			return
		}
	}

	logger.Infof("DelChassis chassis %s success", name)
	b.NormalResponse("DelChassis chassis success")
}
