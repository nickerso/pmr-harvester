<script setup>
import { computed, ref } from 'vue'
import { useJson, DATA_HINT } from '../data'
import { countBy, fmtNum, shortUrl, urlType } from '../utils'
import StatCard from '../components/StatCard.vue'
import DataTable from '../components/DataTable.vue'

const report = useJson('opencor_run_report.json')
const linksData = useJson('opencor_links.json')

const STATUS = {
  ran: { label: 'Loaded and ran', tone: 'ok' },
  loaded_only: { label: 'Loaded, did not run', tone: 'warn' },
  failed: { label: 'Failed to load', tone: 'bad' },
}

// Errors raised while running (not issues reported by OpenCOR) include
// numbers that differ per model, so normalise them to group equal causes.
const GENERIC_ERRORS = new Set(['simulation is not valid', 'run failed', 'no results produced'])
function errorProblem(error) {
  if (!error || GENERIC_ERRORS.has(error)) return null
  return 'Run error: ' + error.replace(/\d+(\.\d+)?([eE][+-]?\d+)?/g, 'N')
}

const titles = computed(() => {
  const m = new Map()
  for (const l of linksData.data.value || []) {
    if (l.file_url && !m.has(l.file_url)) m.set(l.file_url, l)
  }
  return m
})

const rows = computed(() =>
  (report.data.value?.results || []).map((r) => {
    const link = titles.value.get(r.file_url)
    const errProblem = errorProblem(r.error)
    return {
      ...r,
      status: r.ran ? 'ran' : r.loaded ? 'loaded_only' : 'failed',
      title: link?.exposure_title || '',
      filename: link?.filename || r.file_url.split('/').pop(),
      source_type: link ? urlType(link.source_page) : '',
      file_type: urlType(r.file_url),
      problems: [...r.issues, ...(errProblem ? [errProblem] : [])],
    }
  }),
)

const statusFilter = ref('')
const problemFilter = ref('') // '' | '__any__' | '__none__' | specific problem text
const fileType = ref('')
const search = ref('')
const selected = ref(null)

function matches(r, includeProblem) {
  const q = search.value.trim().toLowerCase()
  if (statusFilter.value && r.status !== statusFilter.value) return false
  if (fileType.value && r.file_type !== fileType.value) return false
  if (includeProblem) {
    const pf = problemFilter.value
    if (pf === '__any__' && !r.problems.length) return false
    if (pf === '__none__' && r.problems.length) return false
    if (pf && !pf.startsWith('__') && !r.problems.includes(pf)) return false
  }
  return !q || [r.title, r.file_url, r.error, ...r.exposure_urls].join(' ').toLowerCase().includes(q)
}

const filtered = computed(() => rows.value.filter((r) => matches(r, true)))

// Problem groups over the rows matching every filter except the problem filter.
const problemGroups = computed(() =>
  countBy(
    rows.value.filter((r) => matches(r, false)).flatMap((r) => r.problems),
    (p) => p,
  ),
)

const count = (status) => rows.value.filter((r) => r.status === status).length
const withProblems = computed(() => rows.value.filter((r) => r.problems.length).length)
const fileTypes = computed(() => [...new Set(rows.value.map((r) => r.file_type))].sort())

const sameProblemRows = (problem) => rows.value.filter((r) => r.problems.includes(problem))

function setStatus(s) {
  statusFilter.value = statusFilter.value === s ? '' : s
}

function reset() {
  statusFilter.value = problemFilter.value = fileType.value = search.value = ''
}

const columns = [
  { key: 'title', label: 'Exposure', sortable: true },
  { key: 'filename', label: 'File', sortable: true },
  { key: 'status', label: 'Status', sortable: true, value: (r) => STATUS[r.status].label },
  { key: 'problems', label: 'Problems', sortable: true, value: (r) => r.problems.length },
  { key: 'load_seconds', label: 'Load (s)', sortable: true },
  { key: 'run_seconds', label: 'Run (s)', sortable: true },
  { key: 'result_points', label: 'Points', sortable: true },
]
</script>

<template>
  <section>
    <h2>OpenCOR run results</h2>
    <p v-if="report.loading.value" class="muted">Loading…</p>
    <div v-else-if="report.error.value" class="error">
      {{ report.error.value }}. {{ DATA_HINT }}
    </div>
    <template v-else>
      <p class="muted">Report generated {{ new Date(report.data.value.generated).toLocaleString() }}</p>
      <div class="cards">
        <StatCard label="Distinct files run" :value="rows.length" />
        <StatCard
          v-for="(s, key) in STATUS"
          :key="key"
          :label="s.label"
          :value="count(key)"
          :tone="s.tone"
          clickable
          :active="statusFilter === key"
          @click="setStatus(key)"
        />
        <StatCard
          label="With reported problems"
          :value="withProblems"
          clickable
          :active="problemFilter === '__any__'"
          @click="problemFilter = problemFilter === '__any__' ? '' : '__any__'"
        />
      </div>

      <div class="panel">
        <h3 style="margin-top: 0">
          Problems <span class="muted">({{ problemGroups.length }} distinct — click one to list every file affected)</span>
        </h3>
        <div class="problems">
          <div
            v-for="g in problemGroups"
            :key="g.name"
            class="problem"
            :class="{ active: problemFilter === g.name }"
            @click="problemFilter = problemFilter === g.name ? '' : g.name"
          >
            <span class="n">{{ g.count }}</span>
            <span>{{ g.name }}</span>
          </div>
          <div v-if="!problemGroups.length" class="muted">No problems in the current selection.</div>
        </div>
      </div>

      <div class="filters">
        <label>
          Status
          <select v-model="statusFilter">
            <option value="">any</option>
            <option v-for="(s, key) in STATUS" :key="key" :value="key">{{ s.label }}</option>
          </select>
        </label>
        <label>
          Problems
          <select v-model="problemFilter">
            <option value="">any</option>
            <option value="__any__">has problems</option>
            <option value="__none__">no problems</option>
            <option v-if="problemFilter && !problemFilter.startsWith('__')" :value="problemFilter">
              (selected problem)
            </option>
          </select>
        </label>
        <label>
          File type
          <select v-model="fileType">
            <option value="">any</option>
            <option v-for="t in fileTypes" :key="t">{{ t }}</option>
          </select>
        </label>
        <input v-model="search" type="search" placeholder="Search title, URL or error…" size="32" />
        <button @click="reset">Reset</button>
      </div>

      <div v-if="selected" class="panel detail">
        <button style="float: right" @click="selected = null">Close</button>
        <h3 style="margin-top: 0">{{ selected.title || selected.filename }}</h3>
        <p>
          <span :class="STATUS[selected.status].tone">{{ STATUS[selected.status].label }}</span>
          · <a :href="selected.file_url" target="_blank" rel="noopener">{{ shortUrl(selected.file_url) }}</a>
        </p>
        <p>
          Exposure:
          <span v-for="e in selected.exposure_urls" :key="e">
            <a :href="e" target="_blank" rel="noopener">{{ shortUrl(e) }}</a>{{ ' ' }}
          </span>
        </p>
        <template v-if="selected.problems.length">
          <strong>Problems</strong>
          <ul>
            <li v-for="p in selected.problems" :key="p">
              {{ p }}
              <button class="link" @click="problemFilter = p">
                → all {{ sameProblemRows(p).length }} files with this problem
              </button>
            </li>
          </ul>
        </template>
        <p v-else class="muted">No problems reported.</p>
        <template v-if="selected.error">
          <strong>Error</strong>
          <pre>{{ selected.error }}</pre>
        </template>
        <details v-if="selected.traceback">
          <summary>Traceback</summary>
          <pre>{{ selected.traceback }}</pre>
        </details>
      </div>

      <DataTable
        :columns="columns"
        :rows="filtered"
        :selected-row="selected"
        @row-click="selected = $event"
      >
        <template #cell-status="{ row }">
          <span :class="STATUS[row.status].tone">{{ STATUS[row.status].label }}</span>
        </template>
        <template #cell-load_seconds="{ row }">{{ fmtNum(row.load_seconds) }}</template>
        <template #cell-run_seconds="{ row }">{{ fmtNum(row.run_seconds) }}</template>
      </DataTable>
    </template>
  </section>
</template>

<style scoped>
.problems { max-height: 220px; overflow: auto; }
.problem { display: flex; gap: 10px; padding: 3px 6px; border-radius: 4px; font-size: 0.85rem; cursor: pointer; }
.problem:hover, .problem.active { background: #e8f0fe; }
.problem .n { min-width: 34px; text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }
.detail { margin: 12px 0; overflow-wrap: anywhere; }
</style>
