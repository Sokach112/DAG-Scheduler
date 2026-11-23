/** Enter submits modal forms; textareas keep newline unless Cmd/Ctrl+Enter. */
export const isSubmitEnter = (event: KeyboardEvent): boolean => {
  if (event.key !== 'Enter' || event.shiftKey || event.altKey) return false
  const target = event.target as HTMLElement | null
  if (!target) return true

  if (target.tagName === 'TEXTAREA') {
    return event.metaKey || event.ctrlKey
  }

  if (target.tagName === 'SELECT') return false

  if (target instanceof HTMLInputElement) {
    if (['checkbox', 'radio', 'button', 'file'].includes(target.type)) {
      return false
    }
  }

  if (target.closest('button')) return false
  return true
}
