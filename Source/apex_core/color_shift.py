"""Exact Sims CAS color lanes, independently implemented from format facts.

uint64 stores brightness/saturation/hue/opacity as four signed 16-bit Q14 lanes
from least to most significant. SimRipper's reader establishes the lane layout;
the authorized Color Sliders UI corroborates neutral H/S/B=0, opacity=1.
CASP resource metadata supplies each selected part's actual editing ranges.
"""
import math
from .dresser_parts import uint

CHANNELS = ('brightness', 'saturation', 'hue', 'opacity')
SCALE = 16384


def decode(raw):
    uint(raw, 64)
    values = {}
    for index, name in enumerate(CHANNELS):
        lane = (raw >> (16 * index)) & 65535
        signed = lane if lane < 32768 else lane - 65536
        values[name] = signed / float(SCALE)
    return values


def replace(raw, edits, ranges):
    uint(raw, 64)
    if not isinstance(edits, dict) or not edits or set(edits) - set(CHANNELS):
        raise ValueError('Provide explicit hue/saturation/brightness/opacity edits.')
    result = raw
    for name, value in edits.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Color values must be finite numbers.')
        bounds = ranges.get(name)
        if not bounds or not bounds.get('enabled'):
            raise ValueError('{} is disabled by the effective CAS part resource.'.format(name))
        low, high = bounds['min'], bounds['max']
        if value < low or value > high:
            raise ValueError('{} must be within the CAS part range [{}, {}].'.format(name, low, high))
        # Nearest representable Q14. Unedited lanes keep their exact bits.
        scaled = float(value) * SCALE
        signed = int(math.floor(scaled + 0.5) if scaled >= 0 else math.ceil(scaled - 0.5))
        if not -32768 <= signed <= 32767:
            raise ValueError('Color value cannot be represented by the signed Q14 lane.')
        quantized = signed / float(SCALE)
        if quantized < low - 0.5 / SCALE or quantized > high + 0.5 / SCALE:
            raise ValueError('Quantized color exceeds its CAS part range.')
        index = CHANNELS.index(name)
        result = (result & ~(65535 << (index * 16))) | ((signed & 65535) << (index * 16))
    return result
