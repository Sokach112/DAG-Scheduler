export interface ProjectTimezone {
  mode: 'iana' | 'fixed'
  timezone: string
  offsetMinutes?: number | null
}

export const projectTimezone = (project: any): ProjectTimezone => {
  if (project?.timezone_mode === 'fixed') {
    return {
      mode: 'fixed',
      timezone: project?.timezone || 'UTC',
      offsetMinutes: Number(project?.utc_offset_minutes) || 0
    }
  }
  return {
    mode: 'iana',
    timezone: project?.timezone || 'Asia/Shanghai'
  }
}

const pad = (value: number) => String(value).padStart(2, '0')

export const offsetLabel = (minutes: number) => {
  const sign = minutes >= 0 ? '+' : '-'
  const abs = Math.abs(Math.round(minutes))
  return `UTC${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
}

export const timezoneLabel = (tz: ProjectTimezone) => {
  if (tz.mode === 'fixed') {
    return offsetLabel(tz.offsetMinutes || 0)
  }
  return `${tz.timezone} (${offsetLabel(currentOffsetMinutes(tz))})`
}

const zoneParts = (date: Date, zone: string) => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: zone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23'
  }).formatToParts(date)
  const get = (type: string) =>
    parts.find(part => part.type === type)?.value || '00'
  return {
    year: Number(get('year')),
    month: Number(get('month')),
    day: Number(get('day')),
    hour: Number(get('hour')),
    minute: Number(get('minute')),
    second: Number(get('second'))
  }
}

export const getZoneOffsetMinutes = (date: Date, zone: string) => {
  const parts = zoneParts(date, zone)
  const asUtc = Date.UTC(
    parts.year, parts.month - 1, parts.day,
    parts.hour, parts.minute, parts.second)
  return Math.round((asUtc - date.getTime()) / 60000)
}

export const currentOffsetMinutes = (tz: ProjectTimezone) => {
  if (tz.mode === 'fixed') return tz.offsetMinutes || 0
  return getZoneOffsetMinutes(new Date(), tz.timezone)
}

export const wallTimeInTimezone = (value: string | null | undefined,
                                   tz: ProjectTimezone) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  if (tz.mode === 'fixed') {
    const shifted = new Date(
      date.getTime() + (tz.offsetMinutes || 0) * 60000)
    return `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-`
      + `${pad(shifted.getUTCDate())}T${pad(shifted.getUTCHours())}:`
      + `${pad(shifted.getUTCMinutes())}`
  }
  const parts = zoneParts(date, tz.timezone)
  return `${parts.year}-${pad(parts.month)}-${pad(parts.day)}T`
    + `${pad(parts.hour)}:${pad(parts.minute)}`
}

const isoWithOffset = (epochMs: number, offsetMinutes: number) => {
  const shifted = new Date(epochMs + offsetMinutes * 60000)
  const sign = offsetMinutes >= 0 ? '+' : '-'
  const abs = Math.abs(offsetMinutes)
  return `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-`
    + `${pad(shifted.getUTCDate())}T${pad(shifted.getUTCHours())}:`
    + `${pad(shifted.getUTCMinutes())}:00${sign}`
    + `${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
}

export const isoFromWallTime = (wall: string | null | undefined,
                                tz: ProjectTimezone) => {
  if (!wall) return ''
  const match = wall.match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  if (!match) return ''
  const [, year, month, day, hour, minute] = match.map(Number)
  const target = Date.UTC(year, month - 1, day, hour, minute, 0)

  if (tz.mode === 'fixed') {
    const offset = tz.offsetMinutes || 0
    return isoWithOffset(target - offset * 60000, offset)
  }

  let epoch = target
  for (let i = 0; i < 3; i++) {
    const offset = getZoneOffsetMinutes(new Date(epoch), tz.timezone)
    const next = target - offset * 60000
    if (next === epoch) break
    epoch = next
  }
  const offset = getZoneOffsetMinutes(new Date(epoch), tz.timezone)
  return isoWithOffset(target - offset * 60000, offset)
}

export const timeInTimezone = (value: string | null | undefined,
                               tz: ProjectTimezone) => {
  const wall = wallTimeInTimezone(value, tz)
  return wall ? wall.substring(11, 16) : ''
}
