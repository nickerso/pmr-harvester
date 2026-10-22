<script setup>
defineProps({
  label: String,
  value: [Number, String],
  active: Boolean,
  clickable: Boolean,
  tone: String, // ok | warn | bad
})
</script>

<template>
  <div class="card" :class="{ active, clickable }">
    <div class="value" :class="tone">{{ value }}</div>
    <div class="label">{{ label }}</div>
  </div>
</template>
