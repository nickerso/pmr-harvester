<script setup>
import { useJson, DATA_HINT } from '../data'
import BarChart from '../components/BarChart.vue'
import StatCard from '../components/StatCard.vue'

const { data, error, loading } = useJson('summary.json')
</script>

<template>
  <section>
    <h2>Exposure summary</h2>
    <p v-if="loading" class="muted">Loading…</p>
    <div v-else-if="error" class="error">{{ error }}. {{ DATA_HINT }}</div>
    <template v-else>
      <p class="muted">Data generated {{ new Date(data.generated).toLocaleString() }}</p>
      <div class="cards">
        <StatCard v-for="m in data.metrics" :key="m.label" :label="m.label" :value="m.value" />
      </div>
      <div class="grid">
        <div class="panel">
          <h3>File kinds</h3>
          <BarChart :items="data.file_kinds" />
        </div>
        <div class="panel">
          <h3>Top file extensions</h3>
          <BarChart :items="data.extensions" />
        </div>
        <div class="panel">
          <h3>Files per exposure (10 = 10 or more)</h3>
          <BarChart :items="data.files_per_exposure" />
        </div>
        <div class="panel">
          <h3>Link relations</h3>
          <BarChart :items="data.link_rels" />
        </div>
      </div>
    </template>
  </section>
</template>
