package bookkeeping

import (
	"fmt"
	"github.com/RoaringBitmap/roaring"
	"testing"
)

func BenchmarkNextID(b *testing.B) {
	bitmap := roaring.NewBitmap()

	oldValue, err := bitmap.ToBase64()
	if err != nil {
		b.Fatal(err)
	}

	deviceIDs := NewIDMap(oldValue)
	for i := 0; i < roaring.MaxUint16+1; i++ {
		deviceIDs.NextID()
	}
}

func TestIP4ToU32(t *testing.T) {
	data := map[string]uint32{
		"183.6.129.98":    3070656866,
		"255.255.255.255": 4294967295,
	}
	for ip, expected := range data {
		output := IPv4ToU32(ip)
		if output != expected {
			t.Fatalf("%s shall be converted to %d, but got %d", ip, expected, output)
		}
	}
}

func TestIDMap(t *testing.T) {

	idmap := NewIDMap("")

	bookkeeping := make(map[uint16]string)
	for i := 0; i < 256; i++ {
		for j := 0; j < 256; j++ {
			ip := fmt.Sprintf("10.0.%d.%d", i, j)
			id := IPv4ToU32(ip)
			if !idmap.OccupyMasked(id) {
				t.Fatalf("unable to add %s, previous added: %s\n", ip, bookkeeping[uint16(id)])
			}
			bookkeeping[uint16(id)] = ip
		}
	}

	ip := "10.1.0.1"
	if idmap.OccupyMasked(IPv4ToU32(ip)) {
		t.Fatalf("shall not allow to add %s\n", ip)
	}
}
