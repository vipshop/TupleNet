package etcd3

import (
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
		output := ipv4ToU32(ip)
		if output != expected {
			t.Fatalf("%s shall be converted to %d, but got %d", ip, expected, output)
		}
	}
}

func TestIDMap(t *testing.T) {
	idmap := NewIDMap("")

	idmap.OccupyMasked(4294902017) // 255.255.1.1

	if idmap.OccupyMasked(257) { // 0.0.1.1
		t.Fatal("OccupyMasked() expected to fail")
	}

	if !idmap.OccupyMasked(513) { // 0.0.2.1
		t.Fatal("OccupyMasked() expected to succeed")
	}
}
