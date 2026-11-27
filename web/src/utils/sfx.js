// sfx.js: âm thanh tổng hợp nhẹ bằng Web Audio API (tái sử dụng cached buffer, không giật frame đầu)
import { store } from '../api.js'

const MUTE_KEY = 'ek_sfx_muted'
let ctx = null
let cachedNoiseBuf = null
let cachedNoiseCtx = null

function getCtx() {
  if (typeof window === 'undefined') return null
  const AC = window.AudioContext || window.webkitAudioContext
  if (!AC) return null
  if (!ctx) {
    try { ctx = new AC() } catch { return null }
  }
  if (ctx.state === 'suspended') {
    ctx.resume().catch(() => {})
  }
  return ctx
}

function getNoiseBuffer(ac) {
  if (cachedNoiseBuf && cachedNoiseCtx === ac) return cachedNoiseBuf
  const sampleRate = ac.sampleRate || 44100
  const frames = Math.max(1, sampleRate) // 1.0s reusable white noise buffer
  const buffer = ac.createBuffer(1, frames, sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < frames; i += 1) {
    data[i] = Math.random() * 2 - 1
  }
  cachedNoiseBuf = buffer
  cachedNoiseCtx = ac
  return buffer
}

export function warmUpSfx() {
  if (isMuted()) return
  const ac = getCtx()
  if (!ac) return
  try {
    getNoiseBuffer(ac)
  } catch { /* bỏ qua nếu trình duyệt chưa cho phép audio */ }
}

export function isMuted() {
  return store.get(MUTE_KEY) === '1'
}

export function setMuted(muted) {
  store.set(MUTE_KEY, muted ? '1' : '0')
}

function tone(ac, { freq = 440, endFreq = null, type = 'sine', dur = 0.12, gain = 0.08, delay = 0 }) {
  const t0 = ac.currentTime + delay
  const osc = ac.createOscillator()
  const g = ac.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, t0)
  if (endFreq !== null) {
    osc.frequency.exponentialRampToValueAtTime(Math.max(20, endFreq), t0 + dur)
  }
  g.gain.setValueAtTime(0.0001, t0)
  g.gain.linearRampToValueAtTime(gain, t0 + 0.012)
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)
  osc.connect(g)
  g.connect(ac.destination)
  osc.start(t0)
  osc.stop(t0 + dur + 0.02)
}

function noiseBurst(
  ac,
  {
    dur = 0.25,
    gain = 0.15,
    delay = 0,
    filterFreq = 1800,
    endFreq = 140,
    filterType = 'lowpass',
    q = 1,
  } = {},
) {
  const sampleRate = ac.sampleRate || 44100
  const t0 = ac.currentTime + delay
  const nyquist = sampleRate * 0.48
  const startF = Math.min(nyquist, Math.max(20, filterFreq))
  const targetF = endFreq !== null && endFreq !== undefined
    ? Math.min(nyquist, Math.max(20, endFreq))
    : null

  const src = ac.createBufferSource()
  src.buffer = getNoiseBuffer(ac)
  if (dur > 1.0) src.loop = true

  const filter = ac.createBiquadFilter()
  filter.type = filterType
  filter.Q.setValueAtTime(q, t0)
  filter.frequency.setValueAtTime(startF, t0)
  if (targetF !== null) {
    filter.frequency.exponentialRampToValueAtTime(targetF, t0 + dur)
  }

  const g = ac.createGain()
  const attack = Math.min(0.012, dur * 0.16)
  g.gain.setValueAtTime(0.0001, t0)
  g.gain.linearRampToValueAtTime(gain, t0 + attack)
  g.gain.exponentialRampToValueAtTime(Math.max(0.0002, gain * 0.28), t0 + dur * 0.45)
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)

  src.connect(filter)
  filter.connect(g)
  g.connect(ac.destination)

  src.start(t0)
  src.stop(t0 + dur + 0.03)
}

function reverseNoiseSweep(
  ac,
  {
    dur = 0.85,
    gain = 0.16,
    delay = 0,
    startFreq = 140,
    endFreq = 2400,
    q = 2.2,
  } = {},
) {
  const sampleRate = ac.sampleRate || 44100
  const t0 = ac.currentTime + delay
  const nyquist = sampleRate * 0.48
  const f0 = Math.min(nyquist, Math.max(20, startFreq))
  const f1 = Math.min(nyquist, Math.max(20, endFreq))

  const src = ac.createBufferSource()
  src.buffer = getNoiseBuffer(ac)
  if (dur > 1.0) src.loop = true

  const filter = ac.createBiquadFilter()
  filter.type = 'bandpass'
  filter.Q.setValueAtTime(q, t0)
  filter.frequency.setValueAtTime(f0, t0)
  filter.frequency.exponentialRampToValueAtTime(f1, t0 + dur)

  const g = ac.createGain()
  g.gain.setValueAtTime(0.0001, t0)
  g.gain.exponentialRampToValueAtTime(Math.max(0.001, gain * 0.22), t0 + dur * 0.45)
  g.gain.linearRampToValueAtTime(gain, t0 + dur * 0.86)
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)

  src.connect(filter)
  filter.connect(g)
  g.connect(ac.destination)

  src.start(t0)
  src.stop(t0 + dur + 0.03)
}

function filteredTone(
  ac,
  {
    freq = 110,
    endFreq = 92,
    type = 'sawtooth',
    dur = 0.9,
    gain = 0.08,
    delay = 0,
    filterFreq = 620,
    endFilterFreq = 150,
  } = {},
) {
  const t0 = ac.currentTime + delay
  const osc = ac.createOscillator()
  const filter = ac.createBiquadFilter()
  const g = ac.createGain()

  osc.type = type
  osc.frequency.setValueAtTime(freq, t0)
  if (endFreq !== null) {
    osc.frequency.exponentialRampToValueAtTime(Math.max(20, endFreq), t0 + dur)
  }

  filter.type = 'lowpass'
  filter.frequency.setValueAtTime(filterFreq, t0)
  filter.frequency.exponentialRampToValueAtTime(Math.max(20, endFilterFreq), t0 + dur)

  g.gain.setValueAtTime(0.0001, t0)
  g.gain.linearRampToValueAtTime(gain, t0 + 0.04)
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)

  osc.connect(filter)
  filter.connect(g)
  g.connect(ac.destination)

  osc.start(t0)
  osc.stop(t0 + dur + 0.03)
}

export function playSfx(kind) {
  if (isMuted()) return
  const ac = getCtx()
  if (!ac) return
  try {
    switch (kind) {
      case 'play':
        tone(ac, { freq: 340, endFreq: 580, type: 'triangle', dur: 0.09, gain: 0.08 })
        break
      case 'draw':
        tone(ac, { freq: 480, endFreq: 320, type: 'sine', dur: 0.08, gain: 0.07 })
        break
      case 'turn':
        tone(ac, { freq: 523.25, type: 'triangle', dur: 0.1, gain: 0.07, delay: 0 })
        tone(ac, { freq: 659.25, type: 'triangle', dur: 0.14, gain: 0.07, delay: 0.09 })
        break
      case 'nope':
        tone(ac, { freq: 240, endFreq: 160, type: 'sawtooth', dur: 0.14, gain: 0.06, delay: 0 })
        tone(ac, { freq: 170, endFreq: 110, type: 'sawtooth', dur: 0.18, gain: 0.06, delay: 0.12 })
        break
      case 'boom':
        // 1. Initial sharp crack / ignition transient
        noiseBurst(ac, {
          dur: 0.08,
          gain: 0.22,
          delay: 0,
          filterType: 'highpass',
          filterFreq: 900,
          endFreq: 2600,
          q: 0.7,
        })
        // 2. Deep cinematic sub-bass impact drop
        tone(ac, { freq: 135, endFreq: 24, type: 'sine', dur: 0.65, gain: 0.28, delay: 0.01 })
        tone(ac, { freq: 88, endFreq: 28, type: 'triangle', dur: 0.45, gain: 0.16, delay: 0.03 })
        // 3. Rolling low-pass filtered explosion roar
        noiseBurst(ac, {
          dur: 0.75,
          gain: 0.24,
          delay: 0.02,
          filterType: 'lowpass',
          filterFreq: 1800,
          endFreq: 140,
          q: 1.2,
        })
        break
      case 'implode':
        // 1. Rising cosmic vacuum suction whoosh
        reverseNoiseSweep(ac, {
          dur: 0.85,
          gain: 0.16,
          delay: 0,
          startFreq: 140,
          endFreq: 2400,
          q: 2.2,
        })
        // 2. Eerie cosmic harmonic whine bending inward
        tone(ac, { freq: 720, endFreq: 140, type: 'sine', dur: 0.7, gain: 0.09, delay: 0.15 })
        // 3. Deep gravitational singularity collapse drop
        tone(ac, { freq: 380, endFreq: 22, type: 'sine', dur: 0.85, gain: 0.28, delay: 0.78 })
        tone(ac, { freq: 150, endFreq: 26, type: 'triangle', dur: 0.55, gain: 0.16, delay: 0.78 })
        noiseBurst(ac, {
          dur: 0.35,
          gain: 0.2,
          delay: 0.78,
          filterType: 'lowpass',
          filterFreq: 650,
          endFreq: 80,
          q: 1.0,
        })
        break
      case 'hellfire':
        // 1. Ominous tritone underworld doom brass chord
        filteredTone(ac, {
          freq: 110,
          endFreq: 92,
          type: 'sawtooth',
          dur: 0.95,
          gain: 0.09,
          delay: 0,
          filterFreq: 620,
          endFilterFreq: 150,
        })
        filteredTone(ac, {
          freq: 155.56,
          endFreq: 130,
          type: 'sawtooth',
          dur: 0.95,
          gain: 0.075,
          delay: 0.02,
          filterFreq: 680,
          endFilterFreq: 160,
        })
        // 2. Deep infernal sub-bass quake
        tone(ac, { freq: 72, endFreq: 24, type: 'sine', dur: 0.9, gain: 0.26, delay: 0 })
        // 3. Surging roaring furnace flames + crackle
        noiseBurst(ac, {
          dur: 0.95,
          gain: 0.22,
          delay: 0.02,
          filterType: 'bandpass',
          filterFreq: 320,
          endFreq: 1350,
          q: 0.9,
        })
        noiseBurst(ac, {
          dur: 0.35,
          gain: 0.14,
          delay: 0.05,
          filterType: 'highpass',
          filterFreq: 1400,
          endFreq: 3200,
          q: 0.8,
        })
        break
      case 'armageddon':
        // 1. Shimmering heavenly major-7th chord
        tone(ac, { freq: 523.25, type: 'triangle', dur: 0.45, gain: 0.065, delay: 0 })
        tone(ac, { freq: 659.25, type: 'triangle', dur: 0.48, gain: 0.06, delay: 0.03 })
        tone(ac, { freq: 783.99, type: 'sine', dur: 0.52, gain: 0.06, delay: 0.06 })
        tone(ac, { freq: 987.77, type: 'sine', dur: 0.55, gain: 0.055, delay: 0.09 })
        // 2. Deep sub impact drop at dual-fate clash
        tone(ac, { freq: 145, endFreq: 24, type: 'sine', dur: 0.82, gain: 0.28, delay: 0.14 })
        tone(ac, { freq: 92, endFreq: 28, type: 'triangle', dur: 0.6, gain: 0.16, delay: 0.14 })
        // 3. Rolling thunder noise roar
        noiseBurst(ac, {
          dur: 0.95,
          gain: 0.24,
          delay: 0.14,
          filterType: 'lowpass',
          filterFreq: 1700,
          endFreq: 115,
          q: 1.1,
        })
        break
      case 'tower':
        // Royal brass triad fanfare (C5 - E5 - G5 - C6)
        filteredTone(ac, { freq: 523.25, endFreq: 523.25, type: 'sawtooth', dur: 0.18, gain: 0.065, delay: 0, filterFreq: 1900, endFilterFreq: 1200 })
        tone(ac, { freq: 523.25, type: 'triangle', dur: 0.18, gain: 0.065, delay: 0 })
        filteredTone(ac, { freq: 659.25, endFreq: 659.25, type: 'sawtooth', dur: 0.18, gain: 0.065, delay: 0.1, filterFreq: 2100, endFilterFreq: 1400 })
        tone(ac, { freq: 659.25, type: 'triangle', dur: 0.18, gain: 0.065, delay: 0.1 })
        filteredTone(ac, { freq: 783.99, endFreq: 783.99, type: 'sawtooth', dur: 0.2, gain: 0.07, delay: 0.2, filterFreq: 2400, endFilterFreq: 1600 })
        tone(ac, { freq: 783.99, type: 'triangle', dur: 0.2, gain: 0.07, delay: 0.2 })
        filteredTone(ac, { freq: 1046.5, endFreq: 1046.5, type: 'sawtooth', dur: 0.48, gain: 0.075, delay: 0.31, filterFreq: 2800, endFilterFreq: 1500 })
        tone(ac, { freq: 1046.5, type: 'triangle', dur: 0.5, gain: 0.085, delay: 0.31 })
        break
      case 'catomic':
        // 1. Rising nuclear siren sweep
        tone(ac, { freq: 260, endFreq: 880, type: 'sawtooth', dur: 0.42, gain: 0.075, delay: 0 })
        reverseNoiseSweep(ac, {
          dur: 0.4,
          gain: 0.14,
          delay: 0,
          startFreq: 220,
          endFreq: 2200,
          q: 2.0,
        })
        // 2. Deep sub drop + blast roar
        tone(ac, { freq: 140, endFreq: 24, type: 'sine', dur: 0.72, gain: 0.28, delay: 0.36 })
        tone(ac, { freq: 90, endFreq: 28, type: 'triangle', dur: 0.5, gain: 0.16, delay: 0.36 })
        noiseBurst(ac, {
          dur: 0.78,
          gain: 0.24,
          delay: 0.36,
          filterType: 'lowpass',
          filterFreq: 2100,
          endFreq: 130,
          q: 1.15,
        })
        break
      case 'epic':
        // Dramatic shimmering chord + deep low impact hit
        tone(ac, { freq: 440, type: 'triangle', dur: 0.42, gain: 0.075, delay: 0 })
        tone(ac, { freq: 554.37, type: 'triangle', dur: 0.44, gain: 0.07, delay: 0.04 })
        tone(ac, { freq: 659.25, type: 'sine', dur: 0.48, gain: 0.07, delay: 0.08 })
        tone(ac, { freq: 880, type: 'sine', dur: 0.52, gain: 0.065, delay: 0.12 })
        tone(ac, { freq: 118, endFreq: 26, type: 'sine', dur: 0.58, gain: 0.24, delay: 0.02 })
        noiseBurst(ac, {
          dur: 0.42,
          gain: 0.16,
          delay: 0.02,
          filterType: 'lowpass',
          filterFreq: 1200,
          endFreq: 110,
          q: 1.0,
        })
        break
      case 'win':
        tone(ac, { freq: 523.25, type: 'triangle', dur: 0.12, gain: 0.08, delay: 0 })
        tone(ac, { freq: 659.25, type: 'triangle', dur: 0.12, gain: 0.08, delay: 0.1 })
        tone(ac, { freq: 783.99, type: 'triangle', dur: 0.14, gain: 0.08, delay: 0.2 })
        tone(ac, { freq: 1046.5, type: 'triangle', dur: 0.28, gain: 0.09, delay: 0.32 })
        break
      default:
        break
    }
  } catch { /* không để lỗi audio ảnh hưởng gameplay */ }
}
