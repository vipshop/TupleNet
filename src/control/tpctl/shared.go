package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"reflect"
	"strconv"
	"strings"
	"unicode/utf8"

	"gopkg.in/urfave/cli.v1"
)

func succeedf(format string, args ...interface{}) {
	fmt.Printf(format+"\n", args...)
	controller.Close()
	os.Exit(0)
}

func fail(args ...interface{}) {
	fmt.Println(args...)
	controller.Close()
	os.Exit(1)
}

func failf(format string, args ...interface{}) {
	fmt.Printf(format+"\n", args...)
	controller.Close()
	os.Exit(1)
}

func checkArgs(ctx *cli.Context, min, max int, usage string) {
	args := ctx.Args()
	if len(args) < min || len(args) > max {
		fail(usage)
	}
	if ctx.BoolT("json") {
		outputFormat = "json"
	}
}

func confirmDelete(ctx *cli.Context) (_ error) {
	if ctx.BoolT("recursive") {
		fmt.Print("all data under this device will be deleted\nconfirm? [yes/no] ")
		r := bufio.NewReader(os.Stdin)
		if input, err := r.ReadString('\n'); err == nil {
			if input == "yes\n" || input == "y\n" {
				return
			}
		}
		fail("operation canceled")
	}

	return
}

func findIPConflict(_ *cli.Context) {
	var errMsgs []string
	if routers, err := controller.GetRouters(); err != nil {
		errMsgs = append(errMsgs, err.Error())
	} else {
		for _, router := range routers {
			if ports, err := controller.GetRouterPorts(router); err != nil {
				errMsgs = append(errMsgs, err.Error())
			} else {
				ips := make(map[string]string)
				for _, port := range ports {
					if name, found := ips[port.IP]; found {
						errMsgs = append(errMsgs, fmt.Sprintf("in %s, %s use the same IP as %s: %s",
							router.Name, name, port.Name, port.IP))
					} else {
						ips[port.IP] = port.Name
					}
				}
			}
		}
	}

	if switches, err := controller.GetSwitches(); err != nil {
		errMsgs = append(errMsgs, err.Error())
	} else {
		for _, swtch := range switches {
			if ports, err := controller.GetSwitchPorts(swtch); err != nil {
				errMsgs = append(errMsgs, err.Error())
			} else {
				ips := make(map[string]string)
				for _, port := range ports {
					if name, found := ips[port.IP]; found {
						errMsgs = append(errMsgs, fmt.Sprintf("in %s, %s use the same IP as %s: %s",
							swtch.Name, name, port.Name, port.IP))
					} else {
						ips[port.IP] = port.Name
					}
				}
			}
		}
	}

	if len(errMsgs) != 0 {
		fail(strings.Join(errMsgs, "\n"))
	}

	fmt.Println("looks good!")
}

func findIDConflict(_ *cli.Context) {
	var (
		errMsgs   []string
		deviceIds map[uint32]string
	)

	routers, err := controller.GetRouters()
	if err != nil {
		fail(errMsgs, err.Error())
	}

	switches, err := controller.GetSwitches()
	if err != nil {
		fail(errMsgs, err.Error())
	}

	deviceIds = make(map[uint32]string, len(routers)+len(switches))

	for _, r := range routers {
		if name, found := deviceIds[r.ID]; found {
			errMsgs = append(errMsgs, fmt.Sprintf("%s has the same id of %s: %d\n",
				r.Name, name, r.ID))
		} else {
			deviceIds[r.ID] = r.Name
		}
	}

	for _, s := range switches {
		if name, found := deviceIds[s.ID]; found {
			errMsgs = append(errMsgs, fmt.Sprintf("%s has the same id of %s: %d\n",
				s.Name, name, s.ID))
		} else {
			deviceIds[s.ID] = s.Name
		}
	}

	if len(errMsgs) != 0 {
		fail(strings.Join(errMsgs, "\n"))
	}

	fmt.Println("looks good!")
}

// parseCIDR parse the input string, returns ip and prefix
func parseCIDR(input string) (string, uint8) {
	i, inet, err := net.ParseCIDR(input)
	if err != nil {
		fail(err)
	}

	ones, _ := inet.Mask.Size()
	return i.String(), uint8(ones)
}

func validateIP(input string) {
	if net.ParseIP(input) == nil {
		fail("invalid IP")
	}
}

func validateMAC(input string) {
	_, err := net.ParseMAC(input)
	if err != nil {
		fail(err)
	}
}

// user of this function shall ensure the ip is valid
func macFromIP(ip string) string {
	parts := strings.Split(ip, ".")

	a, _ := strconv.ParseUint(parts[0], 10, 8)
	b, _ := strconv.ParseUint(parts[1], 10, 8)
	c, _ := strconv.ParseUint(parts[2], 10, 8)
	d, _ := strconv.ParseUint(parts[3], 10, 8)

	return fmt.Sprintf("f2:01:%02x:%02x:%02x:%02x", a, b, c, d)
}

func printStruct(ptr interface{}) {
	switch outputFormat {
	case "plain":
		plainPrint(ptr)
	case "json":
		data, err := json.Marshal(ptr)
		if err != nil {
			fail(err)
		}
		fmt.Println(string(data))
	}
}

func plainPrint(ptr interface{}) {
	theStructValue := reflect.Indirect(reflect.ValueOf(ptr))
	theStructType := theStructValue.Type()
	var maxWidth int
	tags := make([]string, 0, theStructValue.NumField())
	values := make([]interface{}, 0, theStructValue.NumField())
	for i := 0; i < theStructType.NumField(); i++ {
		if key, found := theStructType.Field(i).Tag.Lookup("tn"); found {
			tagName := strings.SplitN(key, ",", 2)[0]
			width := utf8.RuneCountInString(tagName)
			if width > maxWidth {
				maxWidth = width
			}
			tags = append(tags, tagName)
			values = append(values, theStructValue.Field(i).Interface())
		} else {
			if theStructType.Field(i).Name == "Name" {
				fmt.Printf("%s:\n", theStructValue.Field(i).Interface())
			}
		}
	}

	format := fmt.Sprintf("  - %%-%ds: %%v\n", maxWidth)
	for i := range tags {
		fmt.Printf(format, tags[i], values[i])
	}
	fmt.Println()
}

func printDevices(aSlice interface{}) {
	theSlice := reflect.ValueOf(aSlice)
	if theSlice.Kind() != reflect.Slice {
		panic("misuse of printDevice: the input shall be a slice")
	}

	if theSlice.Len() == 0 {
		fmt.Println("empty data set")
		return
	}

	for i := 0; i < theSlice.Len(); i++ {
		printStruct(theSlice.Index(i).Interface())
	}
}

func validateAndTrimSpace(s string) string {
	if strings.Contains(s, "/") {
		fail(`"/" is not allowed`)
	}

	ns := strings.TrimSpace(s)
	if ns == "" {
		fail("string provided contains only spaces")
	}

	return ns
}
