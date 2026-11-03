// Relative hue shifts, in signed Q14 turns. No resource enablement is inferred here.
const SCALE = 16384;
const TAU = 2 * Math.PI;

function bounds(min, max) {
  if (!Number.isInteger(min) || !Number.isInteger(max) || min < -8192 || max > 8192 || min > max) {
    throw new RangeError('Invalid signed-Q14 hue bounds');
  }
}
function valueInBounds(value, min, max) {
  bounds(min, max);
  if (!Number.isInteger(value) || value < min || value > max) {
    throw new RangeError('Hue value outside bounds');
  }
}
function rawAngle(dx, dy) {
  if (!Number.isFinite(dx) || !Number.isFinite(dy)) throw new TypeError('Finite pointer coordinates required');
  return dx === 0 && dy === 0 ? null : Math.atan2(dx, -dy);
}
function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }

export function quantizeHue(turns, min = -8192, max = 8192) {
  bounds(min, max);
  if (!Number.isFinite(turns)) throw new TypeError('Finite hue turns required');
  // Clamp before multiplying to avoid overflow; match Rust round's negative ties.
  const scaled = clamp(turns, min / SCALE, max / SCALE) * SCALE;
  const rounded = Math.sign(scaled) * Math.floor(Math.abs(scaled) + 0.5);
  return rounded === 0 ? 0 : rounded;
}

export function huePosition(value) {
  valueInBounds(value, -8192, 8192);
  const angle = value / SCALE * TAU;
  // Both signed endpoints occupy precisely the same marker position.
  if (Math.abs(value) === 8192) return { x: 0, y: 1 };
  return { x: Math.sin(angle), y: -Math.cos(angle) };
}

export function beginHueGesture({ value, min, max }, dx, dy) {
  valueInBounds(value, min, max);
  let angle = rawAngle(dx, dy);
  if (angle === null) return null;
  // atan2 distinguishes signed zero; the seam choice instead follows the old lane.
  if (dx === 0 && dy > 0) angle = value < 0 ? -Math.PI : Math.PI;
  return {
    original: value, min, max, lastRawAngle: angle, accumulatedAngle: angle,
    value: quantizeHue(angle / TAU, min, max),
  };
}

function validateState(state) {
  if (!state || typeof state !== 'object') throw new TypeError('Hue gesture state required');
  valueInBounds(state.original, state.min, state.max);
  valueInBounds(state.value, state.min, state.max);
  if (!Number.isFinite(state.lastRawAngle) || Math.abs(state.lastRawAngle) > Math.PI || !Number.isFinite(state.accumulatedAngle)) {
    throw new RangeError('Invalid hue gesture angles');
  }
  if (quantizeHue(state.accumulatedAngle / TAU, state.min, state.max) !== state.value) {
    throw new RangeError('Inconsistent hue gesture value');
  }
}

export function advanceHueGesture(state, dx, dy) {
  validateState(state);
  const angle = rawAngle(dx, dy);
  if (angle === null) return state;
  let delta = angle - state.lastRawAngle;
  if (delta > Math.PI) delta -= TAU;
  if (delta < -Math.PI) delta += TAU;
  const accumulatedAngle = state.accumulatedAngle + delta;
  if (!Number.isFinite(accumulatedAngle)) throw new RangeError('Hue gesture angle overflow');
  return { ...state, lastRawAngle: angle, accumulatedAngle,
    value: quantizeHue(accumulatedAngle / TAU, state.min, state.max) };
}
