export interface MergeConflict {
  key: string
  label: string
  kind: 'field' | 'task' | 'task-field'
  local: any
  remote: any
}

export interface MergeResult {
  merged: any
  conflicts: MergeConflict[]
}

const PROJECT_FIELDS: Array<[string, string]> = [
  ['title', 'Title'],
  ['description', 'Description'],
  ['origin', 'Start date'],
  ['ddl', 'Target date'],
  ['wsid', 'Workspace'],
  ['workers', 'Team members'],
  ['worker_mode', 'Worker mode'],
  ['worker_count', 'Worker count'],
  ['active_worker_ids', 'Active team members'],
  ['capability_mode', 'Capability enforcement'],
  ['deadline_mode', 'Deadline enforcement'],
  ['timezone_mode', 'Timezone mode'],
  ['timezone', 'Timezone'],
  ['utc_offset_minutes', 'UTC offset'],
  ['skip_weekends', 'Skip weekends'],
  ['holidays', 'Holiday dates'],
  ['holiday_ranges', 'Holiday periods'],
  ['default_holidays', 'Default holidays']
]

const stable = (value: any): any => {
  if (Array.isArray(value)) return value.map(stable)
  if (value && typeof value === 'object') {
    return Object.keys(value).sort().reduce((acc: any, key) => {
      acc[key] = stable(value[key])
      return acc
    }, {})
  }
  return value
}

const same = (a: any, b: any) =>
  JSON.stringify(stable(a ?? null)) === JSON.stringify(stable(b ?? null))

const TASK_FIELDS: Array<[string, string]> = [
  ['description', 'Description'],
  ['details', 'Details'],
  ['duration', 'Duration'],
  ['priority', 'Priority'],
  ['start', 'Start'],
  ['deadline', 'Deadline'],
  ['dependencies', 'Dependencies'],
  ['capable_workers', 'Capable workers'],
  ['capable_workers_generic', 'Generic capable workers']
]

const taskMap = (tasks: any[] | undefined) => {
  const map = new Map<string, any>()
  for (const task of tasks || []) {
    if (task?.eid) map.set(task.eid, task)
  }
  return map
}

export const mergeProjectState = (
  base: any,
  local: any,
  remote: any
): MergeResult => {
  const merged: any = { ...remote }
  const conflicts: MergeConflict[] = []

  for (const [key, label] of PROJECT_FIELDS) {
    const baseValue = base?.[key]
    const localValue = local?.[key]
    const remoteValue = remote?.[key]

    if (same(localValue, baseValue)) {
      merged[key] = remoteValue
    } else if (same(remoteValue, baseValue) || same(localValue, remoteValue)) {
      merged[key] = localValue
    } else {
      merged[key] = remoteValue
      conflicts.push({
        key: `field:${key}`,
        label,
        kind: 'field',
        local: localValue,
        remote: remoteValue
      })
    }
  }

  const baseTasks = taskMap(base?.events)
  const localTasks = taskMap(local?.events)
  const remoteTasks = taskMap(remote?.events)
  const chosen = new Map<string, any>()

  const eids = new Set<string>([
    ...baseTasks.keys(),
    ...localTasks.keys(),
    ...remoteTasks.keys()
  ])

  for (const eid of eids) {
    const b = baseTasks.get(eid)
    const l = localTasks.get(eid)
    const r = remoteTasks.get(eid)

    const localChanged = !same(l, b)
    const remoteChanged = !same(r, b)

    if (!localChanged) {
      if (r) chosen.set(eid, r)
      continue
    }
    if (!remoteChanged || same(l, r)) {
      if (l) chosen.set(eid, l)
      continue
    }

    if (l && r) {
      const mergedTask: any = { ...r }
      for (const [field, label] of TASK_FIELDS) {
        const baseValue = b?.[field]
        const localValue = l[field]
        const remoteValue = r[field]
        if (same(localValue, baseValue)) {
          mergedTask[field] = remoteValue
        } else if (same(remoteValue, baseValue) || same(localValue, remoteValue)) {
          mergedTask[field] = localValue
        } else {
          mergedTask[field] = remoteValue
          conflicts.push({
            key: `task-field:${eid}:${field}`,
            label: `Task ${eid} · ${label}`,
            kind: 'task-field',
            local: localValue,
            remote: remoteValue
          })
        }
      }
      chosen.set(eid, mergedTask)
      continue
    }

    if (!b) {
      if (l) chosen.set(eid, l)
      else if (r) chosen.set(eid, r)
      continue
    }

    conflicts.push({
      key: `task:${eid}`,
      label: `Task ${eid} (deleted on one side)`,
      kind: 'task',
      local: l,
      remote: r
    })
    if (r) chosen.set(eid, r)
  }

  const order: string[] = []
  const seen = new Set<string>()
  const push = (tasks: any[] | undefined) => {
    for (const task of tasks || []) {
      if (task?.eid && !seen.has(task.eid)) {
        seen.add(task.eid)
        order.push(task.eid)
      }
    }
  }
  push(base?.events)
  push(local?.events)
  push(remote?.events)
  merged.events = order
    .filter(eid => chosen.has(eid))
    .map(eid => chosen.get(eid))

  return { merged, conflicts }
}

export const applyMergeChoices = (
  result: MergeResult,
  choices: Record<string, 'mine' | 'theirs'>
): any => {
  const merged = JSON.parse(JSON.stringify(result.merged))

  for (const conflict of result.conflicts) {
    if (choices[conflict.key] !== 'mine') continue
    if (conflict.kind === 'field') {
      merged[conflict.key.substring('field:'.length)] = conflict.local
      continue
    }
    if (conflict.kind === 'task-field') {
      const [, eid, field] = conflict.key.split(':')
      const task = merged.events.find((item: any) => item.eid === eid)
      if (task) task[field] = conflict.local
      continue
    }
    const eid = conflict.key.substring('task:'.length)
    const index = merged.events.findIndex((task: any) => task.eid === eid)
    if (conflict.local) {
      if (index >= 0) merged.events[index] = conflict.local
      else merged.events.push(conflict.local)
    } else if (index >= 0) {
      merged.events.splice(index, 1)
    }
  }
  return merged
}
