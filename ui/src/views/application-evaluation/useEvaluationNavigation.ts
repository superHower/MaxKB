import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export function useEvaluationNavigation(key: string, options: () => string[], fallback: string) {
  const route = useRoute()
  const router = useRouter()
  return computed({
    get: () => {
      const value = String(route.query[key] || '')
      return options().includes(value) ? value : fallback
    },
    set: (value: string) => {
      void router.replace({ query: { ...route.query, [key]: value } })
    },
  })
}
