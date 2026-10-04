// Tolerant text comparison for checking OCR-read details against what the user typed.

// Letters and digits only, upper-case: "Pulonan, Ellen Joy A." → "PULONANELLENJOYA"
export const normalize = (s = '') => s.toUpperCase().replace(/[^A-Z0-9Ñ]/g, '')

function editDistance(a, b) {
  const row = Array.from({ length: b.length + 1 }, (_, j) => j)
  for (let i = 1; i <= a.length; i++) {
    let prev = row[0]
    row[0] = i
    for (let j = 1; j <= b.length; j++) {
      const temp = row[j]
      row[j] = Math.min(row[j] + 1, row[j - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1))
      prev = temp
    }
  }
  return row[b.length]
}

// 1 = identical after normalizing; tolerates OCR slips like "BONIFAGIO" or a merged "ELLENJOY"
export function similarity(a, b) {
  const x = normalize(a), y = normalize(b)
  if (!x || !y) return 0
  return 1 - editDistance(x, y) / Math.max(x.length, y.length)
}

export const roughlyEqual = (a, b, threshold = 0.85) => similarity(a, b) >= threshold
