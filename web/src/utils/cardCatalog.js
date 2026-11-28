import { useEffect, useState } from 'react'
import { listCards } from '../api.js'

export const ANYTIME_TYPES = ['shufflenow', 'clairvoyance', 'alter3xnow', 'feedthedead', 'godcat']
export const UNPLAYABLE_TYPES = [
  'defuse', 'streakingkitten', 'zombiekitten', 'cat', 'feralcat',
  'explodingkitten', 'implodingkitten',
]
export const TURN_ENDING_TYPES = new Set([
  'skip', 'superskip', 'reverse', 'attack2x', 'targetattack2x',
  'attackofthedead', 'drawfromthebottom', 'digdeeper', 'raisingheck',
  'bury', 'catomicbomb', 'armageddon',
])

export const CARD_ICON = {
  explodingkitten: 'bomb',
  implodingkitten: 'bomb',
  defuse: 'defuse',
  streakingkitten: 'defuse',
  zombiekitten: 'skull',
  godcat: 'crown',
  devilcat: 'bomb',
  barkingkitten: 'dog',
  skip: 'turn',
  superskip: 'turn',
  shuffle: 'sort',
  shufflenow: 'sort',
  attack2x: 'swords',
  targetattack2x: 'swords',
  personalattack3x: 'swords',
  attackofthedead: 'skull',
  reverse: 'sort',
  drawfromthebottom: 'sort',
  digdeeper: 'peek',
  raisingheck: 'bomb',
  bury: 'skull',
  towerofpower: 'crown',
  catomicbomb: 'bomb',
  armageddon: 'bomb',
  feralcat: 'sort',
  seethefuture3x: 'peek',
  seethefuture5x: 'peek',
  revealthefuture3x: 'peek',
  sharethefuture3x: 'peek',
  alter3x: 'peek',
  alter5x: 'peek',
  alter3xnow: 'peek',
  clairvoyance: 'peek',
  cat: 'sort',
  favor: 'trap',
  potluck: 'sort',
  illtakethat: 'trap',
  mark: 'pin',
  curseofthecatbutt: 'blind',
  garbagecollection: 'sort',
  graverobber: 'skull',
  clone: 'sort',
  swaptopandbottom: 'sort',
  nope: 'nope',
  feedthedead: 'skull',
}

export function getCardIcon(type) {
  return CARD_ICON[type] || 'sort'
}

export const CARD_EMOJI = {
  explodingkitten: 'EK', implodingkitten: 'IK', defuse: 'DF', streakingkitten: 'SK',
  zombiekitten: 'ZK', godcat: 'GC', devilcat: 'DC', barkingkitten: 'BK',
  skip: 'SP', superskip: 'SS', shuffle: 'SH', shufflenow: 'SN', attack2x: 'AT',
  targetattack2x: 'TA', personalattack3x: 'PA', attackofthedead: 'AD',
  reverse: 'RV', drawfromthebottom: 'DB', digdeeper: 'DD', raisingheck: 'RH',
  bury: 'BY', towerofpower: 'TP', catomicbomb: 'CB', armageddon: 'AG', feralcat: 'FC',
  seethefuture3x: 'S3', seethefuture5x: 'S5', revealthefuture3x: 'R3',
  sharethefuture3x: 'H3', alter3x: 'A3', alter5x: 'A5', alter3xnow: 'AN',
  clairvoyance: 'CV', cat: 'CT', favor: 'FV', potluck: 'PL', illtakethat: 'IT',
  mark: 'MK', curseofthecatbutt: 'CC', garbagecollection: 'GB', graverobber: 'GR',
  clone: 'CL', swaptopandbottom: 'SW', nope: 'NP', feedthedead: 'FD',
}

const GODCAT_BANNED_DEFAULT = new Set([
  'nope', 'explodingkitten', 'implodingkitten', 'streakingkitten',
  'barkingkitten', 'godcat', 'devilcat', 'towerofpower',
])

const FALLBACK_NAMES = {
  explodingkitten: 'Exploding Kitten',
  implodingkitten: 'Imploding Kitten',
  defuse: 'Defuse',
  streakingkitten: 'Streaking Kitten',
  zombiekitten: 'Zombie Kitten',
  godcat: 'Godcat',
  devilcat: 'Devilcat',
  barkingkitten: 'Barking Kitten',
  skip: 'Skip',
  superskip: 'Super Skip',
  shuffle: 'Shuffle',
  shufflenow: 'Shuffle NOW',
  attack2x: 'Attack 2x',
  targetattack2x: 'Targeted Attack 2x',
  personalattack3x: 'Personal Attack 3x',
  attackofthedead: 'Attack of the Dead',
  reverse: 'Reverse',
  drawfromthebottom: 'Draw From the Bottom',
  digdeeper: 'Dig Deeper',
  raisingheck: 'Raising Heck',
  bury: 'Bury',
  towerofpower: 'Tower of Power',
  catomicbomb: 'Catomic Bomb',
  armageddon: 'Armageddon',
  feralcat: 'Feral Cat',
  seethefuture3x: 'See the Future 3x',
  seethefuture5x: 'See the Future 5x',
  revealthefuture3x: 'Reveal the Future 3x',
  sharethefuture3x: 'Share the Future 3x',
  alter3x: 'Alter the Future 3x',
  alter5x: 'Alter the Future 5x',
  alter3xnow: 'Alter the Future 3x NOW',
  clairvoyance: 'Clairvoyance',
  cat: 'Cat',
  favor: 'Favor',
  potluck: 'Potluck',
  illtakethat: "I'll Take That",
  mark: 'Mark',
  curseofthecatbutt: 'Curse of the Cat Butt',
  garbagecollection: 'Garbage Collection',
  graverobber: 'Grave Robber',
  clone: 'Clone',
  swaptopandbottom: 'Swap Top and Bottom',
  nope: 'Nope',
  feedthedead: 'Feed the Dead',
}

export const FALLBACK_VARIANT_NAMES = {
  curseofthecatbutt: {
    0: 'Curse of the Cat Butt',
    1: 'Blind As A Bat',
  },
}

export const CATEGORY_LABELS = {
  bomb: 'Bom',
  rescue: 'Cứu nguy',
  action: 'Hành động',
  attack: 'Tấn công',
  future: 'Tiên tri',
  combo: 'Combo',
  steal: 'Trộm / Phá',
  revive: 'Hồi sinh',
  special: 'Đặc biệt',
}

function buildFallbackCatalog() {
  const out = {}
  for (const [type, name] of Object.entries(FALLBACK_NAMES)) {
    out[type] = {
      type,
      name,
      is_action: !UNPLAYABLE_TYPES.includes(type),
      anytime: ANYTIME_TYPES.includes(type),
      nopeable: !['explodingkitten', 'implodingkitten', 'defuse', 'streakingkitten',
        'zombiekitten', 'devilcat', 'barkingkitten', 'illtakethat', 'nope'].includes(type),
      godcat_banned: GODCAT_BANNED_DEFAULT.has(type),
      image: `/static/cards/${type}/0.jpg`,
      description: '',
      category: '',
      variants: [0],
      ...(FALLBACK_VARIANT_NAMES[type] ? { variant_names: FALLBACK_VARIANT_NAMES[type] } : {}),
    }
  }
  return out
}

const FALLBACK_CATALOG = buildFallbackCatalog()
let cachedCatalog = null
let catalogPromise = null

function mergeCatalog(remote) {
  const merged = { ...FALLBACK_CATALOG }
  if (!remote || typeof remote !== 'object') return merged
  for (const [type, info] of Object.entries(remote)) {
    const base = merged[type] || {
      type,
      name: type,
      is_action: !UNPLAYABLE_TYPES.includes(type),
      anytime: ANYTIME_TYPES.includes(type),
      nopeable: true,
      godcat_banned: GODCAT_BANNED_DEFAULT.has(type),
      image: `/static/cards/${type}/0.jpg`,
      description: '',
      category: '',
      variants: [0],
      ...(FALLBACK_VARIANT_NAMES[type] ? { variant_names: FALLBACK_VARIANT_NAMES[type] } : {}),
    }
    merged[type] = {
      ...base,
      ...info,
      type: info.type || type,
      name: info.name || base.name,
      godcat_banned: typeof info.godcat_banned === 'boolean'
        ? info.godcat_banned
        : base.godcat_banned,
    }
  }
  return merged
}

export function fetchCardCatalog() {
  if (cachedCatalog) return Promise.resolve(cachedCatalog)
  if (!catalogPromise) {
    catalogPromise = listCards()
      .then((data) => {
        cachedCatalog = mergeCatalog(data)
        return cachedCatalog
      })
      .catch(() => FALLBACK_CATALOG)
  }
  return catalogPromise
}

export function useCardCatalog() {
  const [catalog, setCatalog] = useState(() => cachedCatalog || FALLBACK_CATALOG)
  useEffect(() => {
    let active = true
    fetchCardCatalog().then((cat) => {
      if (active) setCatalog(cat)
    })
    return () => { active = false }
  }, [])
  return catalog
}

export function getCardMeta(catalog, type) {
  if (!type) return null
  return (catalog && catalog[type]) || FALLBACK_CATALOG[type] || {
    type,
    name: type,
    is_action: !UNPLAYABLE_TYPES.includes(type),
    anytime: ANYTIME_TYPES.includes(type),
    nopeable: true,
    godcat_banned: GODCAT_BANNED_DEFAULT.has(type),
    image: `/static/cards/${type}/0.jpg`,
    description: '',
    category: '',
    variants: [0],
  }
}

export function getCardName(catalog, typeOrCard, variant = null) {
  const isCardObj = typeOrCard && typeof typeOrCard === 'object'
  const type = isCardObj ? typeOrCard.type : typeOrCard
  const resolvedVariant = variant ?? (isCardObj ? typeOrCard.variant : null)
  const meta = getCardMeta(catalog, type)
  if (meta?.variant_names && resolvedVariant !== null && resolvedVariant !== undefined) {
    const vname = meta.variant_names[String(resolvedVariant)] ?? meta.variant_names[resolvedVariant]
    if (vname) return vname
  }
  return meta?.name || type || ''
}

export function getCategoryLabel(category) {
  if (!category) return ''
  return CATEGORY_LABELS[category.toLowerCase()] || category
}

// Kiểm tra combo 2/3 lá (hỗ trợ cả feralcat và clone làm wildcard cho lá Cat)
export function validateCombo(cards) {
  if (!cards || cards.length < 2) {
    return { valid: false, combo: null, hint: '', error: '' }
  }
  if (cards.length > 3) {
    return {
      valid: false,
      combo: null,
      hint: '',
      error: 'Combo chỉ hỗ trợ tối đa 3 lá — hãy bỏ bớt rồi thử lại.',
    }
  }
  const hasWild = cards.some((c) => c.type === 'feralcat' || c.type === 'clone')
  const core = cards.map((c) => c.type).filter((t) => t !== 'feralcat' && t !== 'clone')
  const same = new Set(core).size <= 1
  const wildOk = !hasWild || core.length === 0 || core[0] === 'cat'
  if (same && wildOk) {
    const combo = cards.length === 2 ? 'pair' : 'three'
    const hint = combo === 'pair'
      ? 'Bộ đôi: trộm ngẫu nhiên 1 lá úp'
      : 'Bộ ba: gọi tên thẻ muốn lấy'
    return { valid: true, combo, hint, error: '' }
  }
  return {
    valid: false,
    combo: null,
    hint: '',
    error: 'Combo cần các lá cùng loại (Feral Cat / Clone chỉ thay thế lá Cat).',
  }
}
