/** Сопоставление названия полигона OSM с муниципалитетом из API/demo. */

/** Муниципалитеты без полигона на карте — показываем маркером */
export const CITY_MARKERS = [
  {
    match: (name) => /омск\s*г\.?\s*о\.?/iu.test(String(name || '')),
    lat: 54.9893,
    lng: 73.3682,
    label: 'Омск г.о.',
  },
]

export function normalizeDistrictName(name) {
  if (!name) return ''
  return String(name)
    .toLowerCase()
    .replace(/\([^)]*\)/g, '')
    .replace(/,\s*другое$/u, '')
    .replace(/\s+(район|округ)\s*$/u, '')
    .replace(/\s+г\.?\s*о\.?\s*$/u, '')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Первое значимое слово (корень топонима). */
function rootToken(norm) {
  const token = norm.split(/\s+/)[0] || ''
  return token.replace(/ский$|ской$|ский$/u, '').replace(/цев$/u, 'цев')
}

function rootsCompatible(osmNorm, apiNorm) {
  if (osmNorm === apiNorm) return true
  const osmRoot = rootToken(osmNorm)
  const apiRoot = rootToken(apiNorm)
  if (osmRoot.length < 5 || apiRoot.length < 5) return false
  return osmRoot === apiRoot
}

/** Явные соответствия API → OSM (после normalize). */
const OSM_ALIASES = new Map([
  ['омский', 'омский'],
])

export function matchDistrict(osmName, districts) {
  if (!osmName || !districts?.length) return null

  const osmNorm = normalizeDistrictName(osmName)
  if (!osmNorm) return null

  let hit = districts.find((d) => normalizeDistrictName(d.name) === osmNorm)
  if (hit) return hit

  const alias = OSM_ALIASES.get(osmNorm)
  if (alias) {
    hit = districts.find((d) => normalizeDistrictName(d.name) === alias)
    if (hit) return hit
  }

  hit = districts.find((d) => rootsCompatible(osmNorm, normalizeDistrictName(d.name)))
  if (hit) return hit

  return null
}

export function findCityMarkerDistrict(districts) {
  if (!districts?.length) return null
  for (const rule of CITY_MARKERS) {
    const hit = districts.find((d) => rule.match(d.name))
    if (hit) return { district: hit, ...rule }
  }
  return null
}
