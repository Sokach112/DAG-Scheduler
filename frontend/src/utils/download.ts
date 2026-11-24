export const filenameFromDisposition = (
  header: string | null,
  fallback: string
) => {
  if (!header) return fallback
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(header)
  if (utf8?.[1]) {
    try { return decodeURIComponent(utf8[1]) } catch { /* ignore */ }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header)
  return plain?.[1] || fallback
}

export const downloadFromUrl = async (url: string, fallbackName: string) => {
  const response = await fetch(url)
  if (!response.ok) {
    let message = `Download failed (${response.status})`
    try {
      const body = await response.json()
      if (typeof body?.error?.detail === 'string') message = body.error.detail
    } catch { /* keep default */ }
    throw new Error(message)
  }
  const blob = await response.blob()
  const filename = filenameFromDisposition(
    response.headers.get('content-disposition'), fallbackName)
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
