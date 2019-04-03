package etcd3

import (
	"fmt"
	"github.com/pkg/errors"
	"reflect"
	"strconv"
	"strings"
)

// MarshalTuplenet serializes a struct into a string of the form: a=b,c=d,e=f
// field type of int, uint, float and string is supported
func MarshalTuplenet(ptr interface{}) string {
	theStructValue := reflect.ValueOf(ptr)
	for {
		if theStructValue.Kind() != reflect.Ptr {
			break
		}
		theStructValue = reflect.Indirect(theStructValue)
	}

	kvs := make([]string, 0, theStructValue.NumField())
	theStructType := theStructValue.Type()
	for i := 0; i < theStructValue.NumField(); i++ {
		fieldProp := theStructType.Field(i)
		if key := fieldProp.Tag.Get("tn"); key != "" {
			parts := strings.SplitN(key, ",", 2)

			omitEmpty := len(parts) > 1 && parts[1] == "omitempty"

			fieldValue := theStructValue.Field(i)
			switch fieldValue.Kind() {
			case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
				if fieldValue.Int() == 0 && omitEmpty {
					continue
				}
			case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
				if fieldValue.Uint() == 0 && omitEmpty {
					continue
				}
			case reflect.Float32, reflect.Float64:
				if fieldValue.Float() == 0 && omitEmpty {
					continue
				}
			case reflect.String:
				if fieldValue.String() == "" && omitEmpty {
					continue
				}
			default:
				continue
			}

			kvs = append(kvs, fmt.Sprintf("%s=%v", parts[0], fieldValue.Interface()))
		}
	}

	return strings.Join(kvs, ",")
}

// UnmarshalTuplenet deserializes from a string of the form: a=b,c=d,e=f into a struct
// field type of int, uint, float and string is supported
func UnmarshalTuplenet(ptr interface{}, text string) (err error) {
	theStructValue := reflect.ValueOf(ptr)
	if theStructValue.Kind() != reflect.Ptr {
		return errors.Errorf("expecting ptr to be a pointer to %v not a copy of itself", ptr)
	}
	theStructValue = reflect.Indirect(theStructValue)

	// put a panic handler during reflect operation
	defer func() {
		if r := recover(); r != nil {
			var ok bool
			err, ok = r.(error)
			if !ok {
				err = errors.Errorf("pkg: %v", r)
			} else {
				err = errors.Wrapf(err, "unable to unmarshal: %v", ptr)
			}
		}
	}()

	// if ptr is a pointer to pointer to struct
	if theStructValue.Kind() == reflect.Ptr {
		theStructValue = reflect.Indirect(theStructValue)
	}

	// record what fields tagged with tn
	fieldsToSet := make(map[string]reflect.Value, theStructValue.NumField())
	theStructType := theStructValue.Type()
	for i := 0; i < theStructValue.NumField(); i++ {
		fieldProp := theStructType.Field(i)
		if key := fieldProp.Tag.Get("tn"); len(key) != 0 {
			name := strings.SplitN(key, ",", 2)[0]
			fieldsToSet[name] = theStructValue.Field(i)
		}
	}

	// extract each key and value pair
	kvs := strings.Split(text, ",")
	for _, kv := range kvs {
		parts := strings.SplitN(kv, "=", 2)
		if len(parts) != 2 {
			continue
		}

		if value, found := fieldsToSet[strings.TrimSpace(parts[0])]; found {
			switch value.Kind() {
			case reflect.String:
				value.SetString(strings.TrimSpace(parts[1]))
			case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
				v, _ := strconv.ParseInt(parts[1], 10, 64)
				value.SetInt(v)
			case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
				v, _ := strconv.ParseUint(parts[1], 10, 64)
				value.SetUint(v)
			case reflect.Float32, reflect.Float64:
				v, _ := strconv.ParseFloat(parts[1], 64)
				value.SetFloat(v)
			}
		}
	}

	return
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
