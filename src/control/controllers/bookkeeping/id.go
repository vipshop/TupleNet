package bookkeeping

import (
	"github.com/RoaringBitmap/roaring"
	"github.com/pkg/errors"
	"strconv"
	"strings"
)

// IDMap is a helper type for handling device ids
type IDMap struct {
	*roaring.Bitmap
}

// NewIDMap creates a IDMap from a given roaring bitmap represented by a base64 string
func NewIDMap(value string) *IDMap {
	bitmap := roaring.NewBitmap()
	bitmap.FromBase64(value)

	return &IDMap{bitmap}
}

// NextID return a available id
func (ptr *IDMap) NextID() (uint32, error) {
	// loop to find a available ID
	for i := 1; i <= roaring.MaxUint16; i++ {
		id := uint32(i)
		if found := ptr.CheckedAdd(id); found {
			return id, nil
		}
	}

	return 0, errors.New("device id exhausted")
}

func (ptr *IDMap) Occupy(x uint32) bool {
	return ptr.CheckedAdd(x)
}

func (ptr *IDMap) OccupyMasked(x uint32) bool {
	masked := uint16(x)
	return ptr.CheckedAdd(uint32(masked))
}

func (ptr *IDMap) Return(x uint32) {
	ptr.Remove(x)
}

func (ptr *IDMap) ReturnMasked(x uint32) {
	masked := uint16(x)
	ptr.Remove(uint32(masked))
}

func (ptr *IDMap) Size() uint64 {
	return ptr.GetCardinality()
}

func (ptr *IDMap) String() string {
	// in what situation shall an error be returned? just ignore it for now
	value, _ := ptr.ToBase64()
	return value
}


// the function assume ip address in xxx.xxx.xxx.xxx pattern
func IPv4ToU32(ip string) uint32 {
	parts := strings.Split(ip, ".")
	a, _ := strconv.ParseUint(parts[0], 10, 8)
	b, _ := strconv.ParseUint(parts[1], 10, 8)
	c, _ := strconv.ParseUint(parts[2], 10, 8)
	d, _ := strconv.ParseUint(parts[3], 10, 8)

	r := a<<24 | b<<16 | c<<8 | d

	return uint32(r)
}
