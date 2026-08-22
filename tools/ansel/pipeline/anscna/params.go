package anscna

import (
	"encoding/binary"
	"fmt"
	"math"
)

// ParamsSize is sizeof(AnsCnaParams), the window 0x10132070 copies out of
// impl+0x0c.
const ParamsSize = 0x7C

// ParamsFromBytes decodes a 0x7c-byte AnsCnaParams image — the same field table
// as pakon_cna.PARAM_FIELDS, which comes from
// pakon_autotone.AUTOTONE_WORK_LAYOUT["AnsCnaParams"] (Phase 1, DPI
// cross-checked). Only the four slots the vendor dumper leaves unnamed get
// local names.
//
// The harness passes the real image over the wire rather than trusting
// DefaultParams(), so a drift between the two sides' defaults cannot pass
// silently.
func ParamsFromBytes(buf []byte) (Params, error) {
	var p Params
	if len(buf) < ParamsSize {
		return p, fmt.Errorf("AnsCnaParams needs %d bytes, got %d",
			ParamsSize, len(buf))
	}
	i16at := func(off int) int64 {
		return int64(int16(binary.LittleEndian.Uint16(buf[off:])))
	}
	i32at := func(off int) int64 {
		return int64(int32(binary.LittleEndian.Uint32(buf[off:])))
	}
	f32at := func(off int) float64 {
		return float64(math.Float32frombits(binary.LittleEndian.Uint32(buf[off:])))
	}
	p.RedShift = i16at(0x00)
	p.GreenShift = i16at(0x02)
	p.BlueShift = i16at(0x04)
	p.HistSize = i32at(0x08)
	p.BucketSize = i32at(0x0C)
	p.LowClamp = f32at(0x10)
	p.HighClamp = f32at(0x14)
	p.Blend = f32at(0x18)
	p.Pivot = i16at(0x1C)
	p.MinPivotPercentile = f32at(0x20)
	p.MaxPivotPercentile = f32at(0x24)
	p.ThresholdMultiplier = f32at(0x28)
	p.ThresholdReductionFactor = f32at(0x2C)
	p.MinPosThreshold = i16at(0x30)
	p.MinLapPixelRatio = f32at(0x34)
	p.SmoothingSizeFactor = f32at(0x38)
	p.LaplacianHistSmoothingSigma = f32at(0x3C)
	p.CoarseHistSmoothingSigma = f32at(0x40)
	p.ToneScaleSmoothingSigma = f32at(0x44)
	p.DarkMaxContrastGain = f32at(0x48)
	p.LightMaxContrastGain = f32at(0x4C)
	p.DarkScale = f32at(0x50)
	p.LightScale = f32at(0x54)
	p.Unk58 = f32at(0x58)
	p.Unk5c = f32at(0x5C)
	p.MinGaussSigma = f32at(0x60)
	p.MaxGaussSigma = f32at(0x64)
	p.ElmoNeutralLimit = i16at(0x68)
	p.ElmoRedLimit = i16at(0x6A)
	p.ElmoGreenLimit = i16at(0x6C)
	p.ElmoBlueLimit = i16at(0x6E)
	p.ElmoSatThreshold = i16at(0x70)
	p.ElmoCriticalPercent = f32at(0x74)
	p.ElmoAggressiveness = i32at(0x78)
	return p, nil
}
