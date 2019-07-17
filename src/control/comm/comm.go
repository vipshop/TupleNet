package comm

import (
	"fmt"
	"strings"
	"net"
	"strconv"
)

// parseCIDR parse the input string, returns ip and prefix
func ParseCIDR(input string) (string, uint8, error) {
	i, inet, err := net.ParseCIDR(input)
	if err != nil {
		return "", 0, err
	}

	ones, _ := inet.Mask.Size()
	return i.String(), uint8(ones), nil
}

// user of this function shall ensure the ip is valid
func MacFromIP(ip string) string {
	parts := strings.Split(ip, ".")

	a, _ := strconv.ParseUint(parts[0], 10, 8)
	b, _ := strconv.ParseUint(parts[1], 10, 8)
	c, _ := strconv.ParseUint(parts[2], 10, 8)
	d, _ := strconv.ParseUint(parts[3], 10, 8)

	return fmt.Sprintf("f2:01:%02x:%02x:%02x:%02x", a, b, c, d)
}

func ValidateMAC(input string) error {
	_, err := net.ParseMAC(input)
	if err != nil {
		return err
	}
	return nil
}
