<script setup>
import { computed, ref, watch } from 'vue'

// columns: [{ key, label, sortable?, value?(row) }]; cells can be customised
// with a slot named `cell-<key>` receiving { row }.
const props = defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, required: true },
  pageSize: { type: Number, default: 50 },
  selectedRow: { type: Object, default: null },
  defaultSort: { type: Object, default: null }, // { key, dir }
})
const emit = defineEmits(['row-click'])

const sortKey = ref(props.defaultSort?.key ?? null)
const sortDir = ref(props.defaultSort?.dir ?? 'asc')
const page = ref(0)

function cellValue(col, row) {
  return col.value ? col.value(row) : row[col.key]
}

function toggleSort(col) {
  if (!col.sortable) return
  if (sortKey.value === col.key) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else {
    sortKey.value = col.key
    sortDir.value = 'asc'
  }
}

const sorted = computed(() => {
  const col = props.columns.find((c) => c.key === sortKey.value)
  if (!col) return props.rows
  const dir = sortDir.value === 'asc' ? 1 : -1
  // Missing values always sort last.
  return [...props.rows].sort((a, b) => {
    const x = cellValue(col, a)
    const y = cellValue(col, b)
    const xn = x === null || x === undefined || x === ''
    const yn = y === null || y === undefined || y === ''
    if (xn || yn) return xn === yn ? 0 : xn ? 1 : -1
    return (x < y ? -1 : x > y ? 1 : 0) * dir
  })
})

const pageCount = computed(() => Math.max(1, Math.ceil(sorted.value.length / props.pageSize)))
const visible = computed(() =>
  sorted.value.slice(page.value * props.pageSize, (page.value + 1) * props.pageSize),
)
watch(() => props.rows, () => (page.value = 0))
</script>

<template>
  <div>
    <table>
      <thead>
        <tr>
          <th
            v-for="c in columns"
            :key="c.key"
            :class="{ sortable: c.sortable }"
            @click="toggleSort(c)"
          >
            {{ c.label }}
            <span v-if="sortKey === c.key">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, i) in visible"
          :key="i"
          :class="{ selected: row === selectedRow }"
          @click="emit('row-click', row)"
        >
          <td v-for="c in columns" :key="c.key">
            <slot :name="'cell-' + c.key" :row="row">{{ cellValue(c, row) }}</slot>
          </td>
        </tr>
        <tr v-if="!visible.length">
          <td :colspan="columns.length" class="muted">No matching rows.</td>
        </tr>
      </tbody>
    </table>
    <div class="pager">
      <button :disabled="page === 0" @click="page--">‹ Prev</button>
      <span>Page {{ page + 1 }} / {{ pageCount }} · {{ rows.length }} rows</span>
      <button :disabled="page >= pageCount - 1" @click="page++">Next ›</button>
    </div>
  </div>
</template>

<style scoped>
table { width: 100%; border-collapse: collapse; background: var(--card); font-size: 0.85rem; }
th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { background: #eef0f3; position: sticky; top: 0; white-space: nowrap; }
th.sortable { cursor: pointer; user-select: none; }
tbody tr:hover { background: #f0f6ff; cursor: pointer; }
tr.selected { background: #dbeafe !important; }
td { word-break: break-word; }
.pager { display: flex; gap: 12px; align-items: center; justify-content: center; margin-top: 10px; font-size: 0.85rem; }
</style>
