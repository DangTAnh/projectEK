import { store } from '../api.js'

export const FUR_OPTIONS = [
  { id: 'ginger', label: 'Cam tăng động', fill: '#f39649', shade: '#d47024', stripe: '#b24f14', ear: '#f7b2a6' },
  { id: 'potato', label: 'Khoai tây lông', fill: '#c89b66', shade: '#9e7242', stripe: '#694623', ear: '#d9a482' },
  { id: 'sphynx', label: 'Trụi nhăn nheo', fill: '#efb9b1', shade: '#d48f87', stripe: '#a6635b', ear: '#f59fa2' },
  { id: 'cream', label: 'Cục bột', fill: '#f6e4c4', shade: '#dec59a', stripe: '#b59260', ear: '#f5b0a8' },
  { id: 'gray', label: 'Xám vô tri', fill: '#a2aab5', shade: '#7d8694', stripe: '#565e6b', ear: '#eba7ab' },
  { id: 'charcoal', label: 'Mèo bóng đêm', fill: '#433d3a', shade: '#2d2826', stripe: '#1e1a18', ear: '#d98a8e' },
  { id: 'calico', label: 'Tam thể báo', fill: '#f8efe0', shade: '#e2d2ba', stripe: '#3b2d26', ear: '#f5ada8' },
  { id: 'pink', label: 'Hồng ảo giác', fill: '#f5a3be', shade: '#db7c9c', stripe: '#b85678', ear: '#ffd1df' },
  { id: 'mint', label: 'Xanh phóng xạ', fill: '#88d8b0', shade: '#5eb88d', stripe: '#3d8f68', ear: '#f6b3b3' },
  { id: 'sky', label: 'Xanh ngáo', fill: '#8bc4f0', shade: '#61a0d1', stripe: '#3d79ab', ear: '#f5b3bc' },
]

export const PATTERN_OPTIONS = [
  { id: 'none', label: 'Trơn' },
  { id: 'hairy', label: 'Lông lởm chởm' },
  { id: 'bandaid', label: 'Bầm mặt + băng' },
  { id: 'sweat', label: 'Vã mồ hôi hột' },
  { id: 'tabby', label: 'Sọc mướp' },
  { id: 'tuxedo', label: 'Yếm trắng' },
  { id: 'calico', label: 'Đốm tam thể' },
  { id: 'siamese', label: 'Mặt nạ Xiêm' },
  { id: 'cow', label: 'Bò sữa' },
]

export const EYES_OPTIONS = [
  { id: 'derp', label: 'Lác 2 bên' },
  { id: 'wide', label: 'Ngáo trợn trừng' },
  { id: 'lasers', label: 'Mắt bắn Laser' },
  { id: 'spiral', label: 'Tiền đình @_@' },
  { id: 'angry', label: 'Sắp cắn người' },
  { id: 'chill', label: 'Chán đời 3h sáng' },
  { id: 'happy', label: 'Cười giả trân' },
  { id: 'star', label: 'Thấy tiền $$$' },
]

export const MOUTH_OPTIONS = [
  { id: 'rainbow', label: 'Nôn cầu vồng' },
  { id: 'drool', label: 'Chảy dãi lênh láng' },
  { id: 'scream', label: 'Gào thét điên dại' },
  { id: 'beard', label: 'Râu xồm kẹt xương' },
  { id: 'blep', label: 'Lè lưỡi dài ngoẵng' },
  { id: 'fangs', label: 'Răng sún khịa' },
  { id: 'smug', label: 'Cười đểu' },
  { id: 'cat', label: 'Miệng vô tri :3' },
]

export const HAT_OPTIONS = [
  { id: 'none', label: 'Đầu trần' },
  { id: 'underwear', label: 'Đội sịp siêu nhân' },
  { id: 'cone', label: 'Loa chống liếm' },
  { id: 'toast', label: 'Kẹp bánh mì' },
  { id: 'poop', label: 'Cục kem nâu' },
  { id: 'tin', label: 'Mũ giấy bạc' },
  { id: 'taco', label: 'Mũ Taco' },
  { id: 'bomb', label: 'Bom cháy ngòi' },
  { id: 'melon', label: 'Vỏ dưa hấu' },
  { id: 'wizard', label: 'Phù thủy ngáo' },
  { id: 'crown', label: 'Vương miện lệch' },
  { id: 'party', label: 'Mũ tiệc' },
  { id: 'beanie', label: 'Mũ len' },
]

export const ACC_OPTIONS = [
  { id: 'none', label: 'Không có' },
  { id: 'knife', label: 'Cầm dao thái thịt' },
  { id: 'stink', label: 'Bốc mùi + ruồi' },
  { id: 'fish', label: 'Ngậm xương cá' },
  { id: 'shades', label: 'Kính Thug Life' },
  { id: 'monocle', label: 'Kính quý tộc rởm' },
  { id: 'bowtie', label: 'Nơ đỏ' },
  { id: 'scarf', label: 'Khăn choàng' },
  { id: 'collar', label: 'Vòng chuông' },
]

export const CAT_PRESETS = [
  {
    id: 'rainbowralph',
    label: 'Nôn Cầu Vồng',
    avatar: { fur: 'cream', pattern: 'sweat', eyes: 'spiral', mouth: 'rainbow', hat: 'none', acc: 'none' },
  },
  {
    id: 'hairypotato',
    label: 'Khoai Tây Lông',
    avatar: { fur: 'potato', pattern: 'hairy', eyes: 'derp', mouth: 'drool', hat: 'none', acc: 'stink' },
  },
  {
    id: 'captainbriefs',
    label: 'Đội Sịp Laser',
    avatar: { fur: 'ginger', pattern: 'none', eyes: 'lasers', mouth: 'scream', hat: 'underwear', acc: 'knife' },
  },
  {
    id: 'coneofshame',
    label: 'Loa Chống Liếm',
    avatar: { fur: 'sphynx', pattern: 'bandaid', eyes: 'angry', mouth: 'fangs', hat: 'cone', acc: 'none' },
  },
  {
    id: 'knifecat',
    label: 'Mèo Cầm Dao',
    avatar: { fur: 'charcoal', pattern: 'tuxedo', eyes: 'wide', mouth: 'smug', hat: 'tin', acc: 'knife' },
  },
  {
    id: 'inbread',
    label: 'Kẹp Bánh Mì',
    avatar: { fur: 'ginger', pattern: 'tabby', eyes: 'chill', mouth: 'blep', hat: 'toast', acc: 'none' },
  },
  {
    id: 'poophead',
    label: 'Đầu Kem Nâu',
    avatar: { fur: 'gray', pattern: 'sweat', eyes: 'derp', mouth: 'drool', hat: 'poop', acc: 'stink' },
  },
  {
    id: 'beardcat',
    label: 'Beard Cat',
    avatar: { fur: 'cream', pattern: 'hairy', eyes: 'chill', mouth: 'beard', hat: 'taco', acc: 'fish' },
  },
]

const VALID_SETS = {
  fur: new Set(FUR_OPTIONS.map((o) => o.id)),
  pattern: new Set(PATTERN_OPTIONS.map((o) => o.id)),
  eyes: new Set(EYES_OPTIONS.map((o) => o.id)),
  mouth: new Set(MOUTH_OPTIONS.map((o) => o.id)),
  hat: new Set(HAT_OPTIONS.map((o) => o.id)),
  acc: new Set(ACC_OPTIONS.map((o) => o.id)),
}

export const FUR_MAP = Object.fromEntries(FUR_OPTIONS.map((f) => [f.id, f]))

const AVATAR_STORAGE_KEY = 'ek_cat_avatar_v1'

function hashName(name) {
  let h = 2166136261
  const str = String(name || 'kitty')
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return (h >>> 0)
}

export function defaultAvatarForName(name) {
  const h = hashName(name)
  const fur = FUR_OPTIONS[h % FUR_OPTIONS.length].id
  const patternPool = ['none', 'hairy', 'bandaid', 'sweat', 'tabby', 'tuxedo', 'calico', 'cow']
  const eyesPool = ['derp', 'wide', 'spiral', 'angry', 'chill', 'lasers', 'star']
  const mouthPool = ['rainbow', 'drool', 'scream', 'blep', 'fangs', 'smug', 'beard']
  const hatPool = ['none', 'underwear', 'cone', 'toast', 'poop', 'tin', 'taco', 'bomb', 'melon']
  const accPool = ['none', 'none', 'knife', 'stink', 'fish', 'shades', 'monocle']
  return {
    fur,
    pattern: patternPool[(h >>> 4) % patternPool.length],
    eyes: eyesPool[(h >>> 8) % eyesPool.length],
    mouth: mouthPool[(h >>> 12) % mouthPool.length],
    hat: hatPool[(h >>> 16) % hatPool.length],
    acc: accPool[(h >>> 20) % accPool.length],
  }
}

export function normalizeAvatar(raw, fallbackName = '') {
  const base = defaultAvatarForName(fallbackName)
  if (!raw || typeof raw !== 'object') return base
  return {
    fur: VALID_SETS.fur.has(raw.fur) ? raw.fur : base.fur,
    pattern: VALID_SETS.pattern.has(raw.pattern) ? raw.pattern : base.pattern,
    eyes: VALID_SETS.eyes.has(raw.eyes) ? raw.eyes : base.eyes,
    mouth: VALID_SETS.mouth.has(raw.mouth) ? raw.mouth : base.mouth,
    hat: VALID_SETS.hat.has(raw.hat) ? raw.hat : base.hat,
    acc: VALID_SETS.acc.has(raw.acc) ? raw.acc : base.acc,
  }
}

export function randomAvatar() {
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)].id
  return {
    fur: pick(FUR_OPTIONS),
    pattern: pick(PATTERN_OPTIONS),
    eyes: pick(EYES_OPTIONS),
    mouth: pick(MOUTH_OPTIONS),
    hat: pick(HAT_OPTIONS),
    acc: pick(ACC_OPTIONS),
  }
}

export function loadSavedAvatar(fallbackName = '') {
  let rawStr = ''
  try {
    rawStr = localStorage.getItem(AVATAR_STORAGE_KEY) || ''
  } catch { /* fallback sang sessionStorage */ }
  if (!rawStr) {
    rawStr = store.get(AVATAR_STORAGE_KEY)
  }
  if (!rawStr) return defaultAvatarForName(fallbackName)
  try {
    return normalizeAvatar(JSON.parse(rawStr), fallbackName)
  } catch {
    return defaultAvatarForName(fallbackName)
  }
}

export function saveAvatar(avatar) {
  const clean = normalizeAvatar(avatar)
  const serialized = JSON.stringify(clean)
  try {
    localStorage.setItem(AVATAR_STORAGE_KEY, serialized)
  } catch { /* bỏ qua nếu bị chặn */ }
  store.set(AVATAR_STORAGE_KEY, serialized)
  return clean
}
