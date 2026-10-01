// Plotly serialises numpy arrays as {dtype, bdata} (base64 of the raw bytes)
// instead of a plain list. The browser renders them, so the export must read
// them too (#217).

const TYPED = {
  i1: Int8Array, u1: Uint8Array, i2: Int16Array, u2: Uint16Array,
  i4: Int32Array, u4: Uint32Array, f4: Float32Array, f8: Float64Array,
}

const isBinary = v => v && typeof v === 'object' && typeof v.bdata === 'string' && typeof v.dtype === 'string'

function decodeBinary({ dtype, bdata }) {
  const Typed = TYPED[dtype]
  if (!Typed) return null
  const bytes = Uint8Array.from(atob(bdata), c => c.charCodeAt(0))
  if (bytes.length % Typed.BYTES_PER_ELEMENT) return null
  return Array.from(new Typed(bytes.buffer))
}

// A plain array, a decoded binary array, or null when the value is neither.
export function plotlyArray(value) {
  if (Array.isArray(value)) return value
  return isBinary(value) ? decodeBinary(value) : null
}
