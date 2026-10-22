<script setup>
import { computed, ref } from 'vue'
import { useJson, DATA_HINT } from '../data'
import { urlType, countBy, shortUrl } from '../utils'
import BarChart from '../components/BarChart.vue'
import StatCard from '../components/StatCard.vue'
import DataTable from '../components/DataTable.vue'

const { data, error, loading } = useJson('opencor_links.json')

const links = computed(() =>
  (data.value || []).map((l) => ({
    ...l,
    source_type: urlType(l.source_page),
    target_type: urlType(l.opencor_url),
  })),
)

const presets = {
  all: { label: 'All links', test: () => true },
  cellml_other: {
    label: 'CellML source, different file type in opencor_url',
    test: (l) => l.source_type === 'cellml' && l.target_type !== 'cellml',
  },
  cellml_sedml: {
    label: 'CellML source, SED-ML in opencor_url',
    test: (l) => l.source_type === 'cellml' && l.target_type === 'sedml',
  },
  cellml_cellml: {
    label: 'CellML source, CellML in opencor_url',
    test: (l) => l.source_type === 'cellml' && l.target_type === 'cellml',
  },
  non_cellml: { label: 'Non-CellML source', test: (l) => l.source_type !== 'cellml' },
}

const preset = ref('all')
const sourceType = ref('')
const targetType = ref('')
const search = ref('')

const filtered = computed(() => {
  const test = presets[preset.value].test
  const q = search.value.trim().toLowerCase()
  return links.value.filter(
    (l) =>
      test(l) &&
      (!sourceType.value || l.source_type === sourceType.value) &&
      (!targetType.value || l.target_type === targetType.value) &&
      (!q ||
        [l.exposure_title, l.filename, l.source_page, l.opencor_url]
          .join(' ')
          .toLowerCase()
          .includes(q)),
  )
})

const sourceCounts = computed(() => countBy(links.value, (l) => l.source_type))
const targetForCellml = computed(() =>
  countBy(
    links.value.filter((l) => l.source_type === 'cellml'),
    (l) => l.target_type,
  ),
)
const uniqueUrls = computed(() => new Set(links.value.map((l) => l.opencor_url)).size)
const typeOptions = (counts) => counts.map((c) => c.name).sort()

function pick(kind, name) {
  if (kind === 'source') sourceType.value = sourceType.value === name ? '' : name
  else {
    preset.value = 'cellml_other'
    targetType.value = targetType.value === name ? '' : name
    if (!targetType.value) preset.value = 'all'
  }
}

function reset() {
  preset.value = 'all'
  sourceType.value = targetType.value = search.value = ''
}

const columns = [
  { key: 'exposure_title', label: 'Exposure', sortable: true },
  { key: 'filename', label: 'Source file', sortable: true },
  { key: 'source_type', label: 'Source type', sortable: true },
  { key: 'target_type', label: 'opencor_url type', sortable: true },
  { key: 'opencor_url', label: 'Links' },
]
</script>

<template>
  <section>
    <h2>OpenCOR links</h2>
    <p v-if="loading" class="muted">Loading…</p>
    <div v-else-if="error" class="error">{{ error }}. {{ DATA_HINT }}</div>
    <template v-else>
      <div class="cards">
        <StatCard label="Total links" :value="links.length" />
        <StatCard label="Unique opencor_url" :value="uniqueUrls" />
        <StatCard
          label="CellML source, non-CellML opencor_url"
          :value="links.filter(presets.cellml_other.test).length"
          clickable
          :active="preset === 'cellml_other'"
          @click="preset = 'cellml_other'"
        />
        <StatCard
          label="Non-CellML source"
          :value="links.filter(presets.non_cellml.test).length"
          clickable
          :active="preset === 'non_cellml'"
          @click="preset = 'non_cellml'"
        />
      </div>

      <div class="grid">
        <div class="panel">
          <h3>source_page types <span class="muted">(click to filter)</span></h3>
          <BarChart :items="sourceCounts" clickable :selected="sourceType" @select="pick('source', $event)" />
        </div>
        <div class="panel">
          <h3>opencor_url types for CellML sources <span class="muted">(click to filter)</span></h3>
          <BarChart :items="targetForCellml" clickable :selected="targetType" @select="pick('target', $event)" />
        </div>
      </div>

      <div class="filters">
        <label>
          Show
          <select v-model="preset">
            <option v-for="(p, k) in presets" :key="k" :value="k">{{ p.label }}</option>
          </select>
        </label>
        <label>
          Source type
          <select v-model="sourceType">
            <option value="">any</option>
            <option v-for="t in typeOptions(sourceCounts)" :key="t">{{ t }}</option>
          </select>
        </label>
        <label>
          opencor_url type
          <select v-model="targetType">
            <option value="">any</option>
            <option v-for="t in typeOptions(countBy(links, (l) => l.target_type))" :key="t">{{ t }}</option>
          </select>
        </label>
        <input v-model="search" type="search" placeholder="Search title, file or URL…" size="32" />
        <button @click="reset">Reset</button>
      </div>

      <DataTable :columns="columns" :rows="filtered">
        <template #cell-opencor_url="{ row }">
          <a :href="row.source_page" target="_blank" rel="noopener" title="PMR source page">page</a>
          ·
          <a :href="row.file_url" target="_blank" rel="noopener" :title="shortUrl(row.file_url)">file</a>
          ·
          <a :href="row.opencor_url" title="Open in OpenCOR">OpenCOR</a>
        </template>
      </DataTable>
    </template>
  </section>
</template>
