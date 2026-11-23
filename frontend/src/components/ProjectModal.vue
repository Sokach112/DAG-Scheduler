<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
    <div class="bg-white rounded-xl shadow-xl w-[480px] flex flex-col max-h-[90vh]">
      <div class="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
        <h3 class="text-lg font-semibold text-gray-800">{{ isEditing ? 'Edit Project' : 'New Project' }}</h3>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600"><X class="w-5 h-5"/></button>
      </div>

      <div class="p-6 flex flex-col gap-4 overflow-y-auto" @keydown.enter="onEnter">
        <!-- Workspace -->
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Workspace</label>
          <WorkspaceSelect
            ref="workspaceSelect"
            v-model="form.workspaceWsid"
            :workspaces="workspaces || []"
            placeholder="Type or select a workspace"
          />
        </div>

        <!-- Title -->
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Project Title</label>
          <input v-model="form.title" type="text" class="w-full px-3 py-2 border border-gray-300 rounded-md sm:text-sm focus:ring-blue-500" placeholder="e.g. Website Redesign" />
          <p v-if="error" class="text-xs text-red-500 mt-1">{{ error }}</p>
        </div>

        <!-- Description -->
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Description (Optional)</label>
          <textarea v-model="form.description" rows="3" class="w-full px-3 py-2 border border-gray-300 rounded-md sm:text-sm focus:ring-blue-500" placeholder="Add some details about this project..."></textarea>
        </div>

        <!-- Time Bounds -->
        <div class="flex gap-4">
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">Start Date</label>
            <input v-model="form.origin" type="datetime-local" class="w-full px-3 py-2 border border-gray-300 rounded-md sm:text-sm focus:ring-blue-500" />
          </div>
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-700 mb-1">Target Date</label>
            <input v-model="form.ddl" type="datetime-local" class="w-full px-3 py-2 border border-gray-300 rounded-md sm:text-sm focus:ring-blue-500" />
          </div>
        </div>

        <!-- Timezone -->
        <div class="border-t border-gray-100 pt-3">
          <label class="block text-xs font-medium text-gray-700 mb-1">Timezone</label>
          <div class="grid grid-cols-2 gap-3">
            <select v-model="form.timezone_mode" class="w-full px-2 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500">
              <option value="iana">Named timezone</option>
              <option value="fixed">Fixed UTC offset</option>
            </select>

            <select v-if="form.timezone_mode === 'iana'" v-model="form.timezone" class="w-full px-2 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500">
              <option v-for="zone in timezoneOptions" :key="zone.value" :value="zone.value">
                {{ zone.label }}
              </option>
            </select>

            <select v-else v-model.number="form.utc_offset_minutes" class="w-full px-2 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500">
              <option v-for="offset in fixedOffsetOptions" :key="offset" :value="offset">
                {{ offsetLabel(offset) }}
              </option>
            </select>
          </div>
          <p class="text-[11px] text-gray-400 mt-1">
            Effective: {{ timezoneLabel(timezoneConfig) }}.
            <span v-if="form.timezone_mode === 'iana'">Daylight saving is handled automatically.</span>
            <span v-else>Fixed offsets do not apply daylight saving automatically.</span>
          </p>
        </div>

        <!-- Working calendar -->
        <div class="border-t border-gray-100 pt-3">
          <label class="flex items-center gap-2 text-xs font-medium text-gray-700 cursor-pointer">
            <input v-model="form.skip_weekends" type="checkbox" class="rounded text-blue-600 focus:ring-blue-500" />
            Skip weekends and holidays
          </label>
          <p class="text-[11px] text-gray-400 mt-1">
            Task durations consume working days only. Weekdays are full working days.
          </p>

          <div v-if="form.skip_weekends" class="mt-3 flex flex-col gap-3">
            <label class="flex items-start gap-2 text-xs text-gray-700 cursor-pointer">
              <input v-model="form.default_holidays" type="checkbox" class="mt-0.5 rounded text-blue-600 focus:ring-blue-500" />
              <span>
                Use default holidays (China statutory, 2025–2027)
                <span class="block text-[10px] text-gray-400 font-normal">
                  Includes official holiday periods and weekend make-up workdays.
                </span>
                <span class="block text-[10px] text-gray-400 font-normal">
                  Coverage: {{ coverageLabel }}
                </span>
              </span>
            </label>

            <p v-if="uncoveredHolidayYears.length" class="text-[11px] text-amber-600 bg-amber-50 border border-amber-100 rounded-md px-2 py-1.5">
              Default holidays cover {{ coverageLabel }}. {{ uncoveredHolidayYears.join(', ') }}
              has no official data yet; only weekends and custom periods are skipped.
            </p>

            <div>
              <label class="block text-[11px] text-gray-500 mb-1">Holiday periods</label>
              <div class="flex items-center gap-2">
                <input v-model="holidayStart" type="date" class="flex-1 px-2 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-blue-500" @keydown.enter.prevent.stop="addHolidayRange" />
                <span class="text-gray-400 text-xs">→</span>
                <input v-model="holidayEnd" type="date" class="flex-1 px-2 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-blue-500" @keydown.enter.prevent.stop="addHolidayRange" />
                <button type="button" @click="addHolidayRange" class="px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-md hover:bg-blue-50">
                  Add
                </button>
              </div>
              <p class="text-[10px] text-gray-400 mt-1">End date is optional; leave it empty for a single day.</p>
              <p v-if="holidayError" class="text-[11px] text-red-500 mt-1">{{ holidayError }}</p>

              <div v-if="form.holiday_ranges.length" class="flex flex-wrap gap-1.5 mt-2">
                <span
                  v-for="range in form.holiday_ranges"
                  :key="range.start + range.end"
                  class="inline-flex items-center gap-1 text-[11px] text-gray-600 bg-gray-100 px-2 py-1 rounded"
                >
                  {{ range.start === range.end ? range.start : `${range.start} → ${range.end}` }}
                  <button type="button" @click="removeHolidayRange(range)" class="text-gray-400 hover:text-red-500" title="Remove holiday period">×</button>
                </span>
              </div>
              <p v-else class="text-[11px] text-gray-400 italic mt-2">No custom holiday periods.</p>
            </div>
          </div>
        </div>

        <!-- Enforcement -->
        <div class="border-t border-gray-100 pt-3">
          <label class="block text-xs font-medium text-gray-700 mb-2">Scheduling constraints</label>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-[11px] text-gray-500 mb-1">Project deadline</label>
              <select v-model="form.deadline_mode" class="w-full px-2 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500">
                <option value="soft">Soft — warn when late</option>
                <option value="hard">Hard — infeasible when late</option>
              </select>
            </div>
            <div>
              <label class="block text-[11px] text-gray-500 mb-1">Capabilities</label>
              <select v-model="form.capability_mode" class="w-full px-2 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500">
                <option value="fallback">Fallback — assign anyway</option>
                <option value="strict">Strict — do not assign</option>
              </select>
            </div>
          </div>
          <p v-if="form.deadline_mode === 'hard' && !form.ddl" class="text-[11px] text-amber-600 mt-2">
            Hard deadlines require a Target Date.
          </p>
          <p v-else class="text-[11px] text-gray-400 mt-2">
            Hard projects become infeasible when the schedule finishes after the target date.
            Strict capabilities reject schedules with tasks no active worker can perform.
          </p>
          <p v-if="constraintError" class="text-xs text-red-500 mt-1">{{ constraintError }}</p>
        </div>

      </div>

      <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-end gap-3">
        <button @click="$emit('close')" class="px-4 py-2 text-sm text-gray-700 bg-white border rounded-md hover:bg-gray-50">Cancel</button>
        <button @click="submit" class="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700">{{ isEditing ? 'Save Changes' : 'Create Project' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import WorkspaceSelect from './WorkspaceSelect.vue'
import { isSubmitEnter } from '../utils/keyboard'
import {
  isoFromWallTime, offsetLabel, projectTimezone,
  timezoneLabel, wallTimeInTimezone
} from '../utils/timezone'
import type { ProjectTimezone } from '../utils/timezone'

const props = defineProps<{
  isOpen: boolean
  isEditing?: boolean
  initialData?: any
  workspaces?: any[]
  wsid?: string | null
  holidayCoverage?: any
}>()

const emit = defineEmits(['close', 'save'])

const error = ref('')
const workspaceSelect = ref<any>(null)

const getToday = () => {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}
const today = getToday()

const form = ref<any>({
  workspaceWsid: '',
  title: '',
  description: '',
  origin: `${today}T00:00`,
  ddl: `${today}T23:59`,
  capability_mode: 'fallback',
  deadline_mode: 'soft',
  timezone_mode: 'iana',
  timezone: 'Asia/Shanghai',
  utc_offset_minutes: 480,
  skip_weekends: false,
  default_holidays: false,
  holiday_ranges: []
})
const constraintError = ref('')
const holidayStart = ref('')
const majorTimezoneOptions = [
  { value: 'Asia/Shanghai', label: 'Shanghai — Asia/Shanghai' },
  { value: 'Asia/Tokyo', label: 'Tokyo — Asia/Tokyo' },
  { value: 'Asia/Singapore', label: 'Singapore — Asia/Singapore' },
  { value: 'Asia/Kolkata', label: 'India — Asia/Kolkata' },
  { value: 'Asia/Dubai', label: 'Dubai — Asia/Dubai' },
  { value: 'Asia/Hong_Kong', label: 'Hong Kong — Asia/Hong_Kong' },
  { value: 'Asia/Seoul', label: 'Seoul — Asia/Seoul' },
  { value: 'Asia/Bangkok', label: 'Bangkok — Asia/Bangkok' },
  { value: 'Asia/Jakarta', label: 'Jakarta — Asia/Jakarta' },
  { value: 'Europe/London', label: 'London — Europe/London' },
  { value: 'Europe/Berlin', label: 'Berlin — Europe/Berlin' },
  { value: 'Europe/Paris', label: 'Paris — Europe/Paris' },
  { value: 'Europe/Moscow', label: 'Moscow — Europe/Moscow' },
  { value: 'Africa/Cairo', label: 'Cairo — Africa/Cairo' },
  { value: 'Africa/Johannesburg', label: 'Johannesburg — Africa/Johannesburg' },
  { value: 'America/New_York', label: 'New York — America/New_York' },
  { value: 'America/Chicago', label: 'Chicago — America/Chicago' },
  { value: 'America/Denver', label: 'Denver — America/Denver' },
  { value: 'America/Los_Angeles', label: 'Los Angeles — America/Los_Angeles' },
  { value: 'America/Toronto', label: 'Toronto — America/Toronto' },
  { value: 'America/Sao_Paulo', label: 'São Paulo — America/Sao_Paulo' },
  { value: 'Australia/Sydney', label: 'Sydney — Australia/Sydney' },
  { value: 'Pacific/Auckland', label: 'Auckland — Pacific/Auckland' },
  { value: 'UTC', label: 'UTC' }
]
const timezoneOptions = computed(() => {
  const current = form.value.timezone
  if (current && !majorTimezoneOptions.some(zone => zone.value === current)) {
    return [...majorTimezoneOptions, { value: current, label: current }]
  }
  return majorTimezoneOptions
})
const fixedOffsetOptions = Array.from(
  { length: (840 + 600) / 15 + 1 },
  (_, index) => -600 + index * 15
)
const timezoneConfig = computed<ProjectTimezone>(() => ({
  mode: form.value.timezone_mode === 'fixed' ? 'fixed' : 'iana',
  timezone: form.value.timezone || 'Asia/Shanghai',
  offsetMinutes: form.value.utc_offset_minutes
}))
const holidayEnd = ref('')
const holidayError = ref('')

const coverageLabel = computed(() => {
  const years = props.holidayCoverage?.years || []
  return years.length ? `${years[0]}–${years[years.length - 1]}` : 'none'
})

const uncoveredHolidayYears = computed(() => {
  if (!form.value.default_holidays) return []
  const covered = props.holidayCoverage?.years || []
  if (!covered.length) return []
  const years = new Set<number>()
  const addYear = (value: string | null | undefined) => {
    if (!value) return
    const parsed = new Date(value)
    if (!Number.isNaN(parsed.getTime())) years.add(parsed.getFullYear())
  }
  addYear(form.value.origin)
  addYear(form.value.ddl)
  for (const event of props.initialData?.events || []) {
    addYear(event.start)
    addYear(event.deadline)
  }
  return [...years]
    .filter(year => !covered.includes(year))
    .sort((a, b) => a - b)
})

const addHolidayRange = () => {
  if (!holidayStart.value) {
    holidayError.value = 'Select a start date.'
    return
  }
  const end = holidayEnd.value || holidayStart.value
  if (end < holidayStart.value) {
    holidayError.value = 'End date must be on or after start date.'
    return
  }
  holidayError.value = ''
  const exists = form.value.holiday_ranges.some(
    (range: any) => range.start === holidayStart.value && range.end === end)
  if (!exists) {
    form.value.holiday_ranges = [
      ...form.value.holiday_ranges,
      { start: holidayStart.value, end }
    ].sort((a: any, b: any) => a.start.localeCompare(b.start))
  }
  holidayStart.value = ''
  holidayEnd.value = ''
}

const removeHolidayRange = (range: any) => {
  form.value.holiday_ranges = form.value.holiday_ranges.filter(
    (item: any) => !(item.start === range.start && item.end === range.end))
}

watch([
  () => props.isOpen,
  () => props.initialData,
  () => props.wsid,
  () => (props.workspaces || []).map(
    w => `${w.wsid}:${w.name}`).join('|')
], () => {
  if (!props.isOpen) return

  error.value = ''
  constraintError.value = ''
  holidayStart.value = ''
  holidayEnd.value = ''
  holidayError.value = ''
  const targetWsid = props.isEditing && props.initialData
    ? props.initialData.wsid
    : (props.wsid || props.initialData?.wsid || props.workspaces?.[0]?.wsid)

  if (props.isEditing && props.initialData) {
    const initialTimezone = projectTimezone(props.initialData)

    form.value = {
      workspaceWsid: targetWsid || '',
      title: props.initialData.title,
      description: props.initialData.description || '',
      origin: wallTimeInTimezone(props.initialData.origin, initialTimezone)
        || `${today}T00:00`,
      ddl: wallTimeInTimezone(props.initialData.ddl, initialTimezone)
        || `${today}T23:59`,
      capability_mode: props.initialData.capability_mode || 'fallback',
      deadline_mode: props.initialData.deadline_mode || 'soft',
      timezone_mode: props.initialData.timezone_mode || 'iana',
      timezone: props.initialData.timezone || 'Asia/Shanghai',
      utc_offset_minutes: props.initialData.utc_offset_minutes ?? 480,
      skip_weekends: Boolean(props.initialData.skip_weekends),
      default_holidays: Boolean(props.initialData.default_holidays),
      holiday_ranges: (() => {
        const ranges = (props.initialData.holiday_ranges || []).map(
          (range: any) => ({ start: range.start, end: range.end }))
        for (const holiday of (props.initialData.holidays || [])) {
          if (!ranges.some(
            (range: any) => range.start <= holiday && holiday <= range.end)) {
            ranges.push({ start: holiday, end: holiday })
          }
        }
        return ranges.sort(
          (a: any, b: any) => a.start.localeCompare(b.start))
      })()
    }
  } else {
    form.value = {
      workspaceWsid: targetWsid || '',
      title: '',
      description: '',
      origin: `${today}T00:00`,
      ddl: `${today}T23:59`,
      capability_mode: 'fallback',
      deadline_mode: 'soft',
      timezone_mode: 'iana',
      timezone: 'Asia/Shanghai',
      utc_offset_minutes: 480,
      skip_weekends: false,
      default_holidays: false,
      holiday_ranges: []
    }
  }
}, { immediate: true })

const onEnter = (event: KeyboardEvent) => {
  if (!isSubmitEnter(event)) return
  event.preventDefault()
  submit()
}

const submit = () => {
  if (!form.value.title.trim()) {
    error.value = 'Title is required'
    return
  }
  if (form.value.deadline_mode === 'hard' && !form.value.ddl) {
    constraintError.value = 'Hard deadlines require a Target Date.'
    return
  }
  constraintError.value = ''

  const wsid = workspaceSelect.value?.validate()
  if (!wsid) return

  const payload: any = {
    title: form.value.title,
    description: form.value.description,
    wsid,
    capability_mode: form.value.capability_mode,
    deadline_mode: form.value.deadline_mode,
    timezone_mode: form.value.timezone_mode,
    timezone: form.value.timezone || 'Asia/Shanghai',
    utc_offset_minutes: form.value.utc_offset_minutes,
    skip_weekends: form.value.skip_weekends,
    holidays: [],
    holiday_ranges: form.value.holiday_ranges,
    default_holidays: form.value.default_holidays
  }

  if (form.value.origin) {
    payload.origin = isoFromWallTime(
      form.value.origin, timezoneConfig.value) || form.value.origin
  }
  if (form.value.ddl) {
    payload.ddl = isoFromWallTime(
      form.value.ddl, timezoneConfig.value) || form.value.ddl
  }

  emit('save', payload)
}
</script>
