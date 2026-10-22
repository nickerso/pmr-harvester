// File type of a URL: its extension (ignoring a trailing /view), or "(none)".
export function urlType(url) {
  let name = (url || '').replace(/\/+$/, '')
  if (name.endsWith('/view')) name = name.slice(0, -5)
  name = name.split('/').pop()
  return name.includes('.') ? name.split('.').pop().toLowerCase() : '(none)'
}

export function countBy(items, keyFn) {
  const m = new Map()
  for (const it of items) {
    const k = keyFn(it)
    m.set(k, (m.get(k) || 0) + 1)
  }
  return [...m.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
}

export function shortUrl(url) {
  return (url || '').replace('https://models.physiomeproject.org', '')
}

export function fmtNum(n, digits = 2) {
  return n === null || n === undefined ? '' : Number(n).toFixed(digits)
}
