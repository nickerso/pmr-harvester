import { ref, shallowRef } from 'vue'

const base = import.meta.env.BASE_URL + 'data/'

// Loads a JSON file from public/data, exposing reactive data/error/loading refs.
export function useJson(name) {
  const data = shallowRef(null)
  const error = ref(null)
  const loading = ref(true)
  fetch(base + name)
    .then((r) => {
      if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`)
      return r.json()
    })
    .then((d) => (data.value = d))
    .catch((e) => (error.value = e.message))
    .finally(() => (loading.value = false))
  return { data, error, loading }
}

export const DATA_HINT =
  'Run `uv run pmr-cache dashboard-data` from the project folder to generate the data files.'
