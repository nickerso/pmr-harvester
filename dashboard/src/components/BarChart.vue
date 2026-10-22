<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: { type: Array, required: true }, // [{ name, count }]
  selected: { type: String, default: null },
  clickable: { type: Boolean, default: false },
})
const emit = defineEmits(['select'])
const max = computed(() => Math.max(1, ...props.items.map((i) => i.count)))
</script>

<template>
  <div class="bars">
    <div
      v-for="it in items"
      :key="it.name"
      class="row"
      :class="{ clickable, active: selected === it.name }"
      @click="clickable && emit('select', it.name)"
    >
      <span class="name" :title="it.name">{{ it.name }}</span>
      <span class="track"><span class="fill" :style="{ width: (it.count / max) * 100 + '%' }" /></span>
      <span class="count">{{ it.count }}</span>
    </div>
  </div>
</template>

<style scoped>
.row { display: grid; grid-template-columns: minmax(70px, 30%) 1fr 56px; gap: 8px; align-items: center; padding: 2px 4px; border-radius: 4px; }
.row.clickable { cursor: pointer; }
.row.clickable:hover, .row.active { background: #e8f0fe; }
.name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.85rem; }
.track { background: #eef0f3; height: 14px; border-radius: 3px; overflow: hidden; }
.fill { display: block; height: 100%; background: var(--accent); }
.count { text-align: right; font-variant-numeric: tabular-nums; font-size: 0.85rem; }
</style>
