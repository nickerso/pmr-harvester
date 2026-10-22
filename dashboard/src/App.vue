<script setup>
import { shallowRef } from 'vue'
import SummaryView from './views/SummaryView.vue'
import LinksView from './views/LinksView.vue'
import RunResultsView from './views/RunResultsView.vue'

const tabs = [
  { id: 'summary', label: 'Exposure summary', component: SummaryView },
  { id: 'links', label: 'OpenCOR links', component: LinksView },
  { id: 'runs', label: 'OpenCOR run results', component: RunResultsView },
]
const initial = tabs.find((t) => t.id === location.hash.slice(1)) ?? tabs[0]
const active = shallowRef(initial)

function select(tab) {
  active.value = tab
  location.hash = tab.id
}
</script>

<template>
  <header>
    <h1>PMR Harvester Dashboard</h1>
    <nav>
      <button v-for="t in tabs" :key="t.id" :class="{ on: active.id === t.id }" @click="select(t)">
        {{ t.label }}
      </button>
    </nav>
  </header>
  <main class="page">
    <KeepAlive>
      <component :is="active.component" />
    </KeepAlive>
  </main>
</template>

<style scoped>
header { background: #1e293b; color: #fff; padding: 12px 20px 0; }
h1 { margin: 0 0 10px; font-size: 1.2rem; }
nav { display: flex; gap: 4px; }
nav button { border: none; border-radius: 6px 6px 0 0; background: transparent; color: #cbd5e1; padding: 8px 14px; }
nav button.on { background: var(--bg); color: var(--text); font-weight: 600; }
</style>
