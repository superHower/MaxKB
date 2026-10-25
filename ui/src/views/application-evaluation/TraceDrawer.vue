<template>
  <el-drawer v-model="visible" :title="tr('traceDetail')" size="min(1040px, 100vw)" class="evaluation-drawer trace-drawer">
    <div v-loading="loading" class="trace-detail">
      <el-result v-if="failed" icon="error" :title="tr('traceLoadError')">
        <template #extra><el-button @click="load">{{ tr('refresh') }}</el-button></template>
      </el-result>
      <template v-else-if="sample">
        <section class="eval-section eval-question"><h4 class="eval-section-title">{{ tr('question') }}</h4><p class="eval-copy">{{ sample.event.question }}</p></section>
        <section class="eval-section"><h4 class="eval-section-title">{{ tr('answer') }}</h4><p class="eval-copy">{{ sample.event.answer || '—' }}</p></section>
        <section v-if="sample.annotation" class="eval-section"><h4 class="eval-section-title">{{ tr('evidenceNote') }}
          <el-tag type="info" effect="plain">{{ tr('attributionConfidence') }}：{{ sample.annotation.attribution_confidence ? tr(sample.annotation.attribution_confidence) : '—' }}</el-tag>
        </h4><p class="eval-copy">{{ sample.annotation.evidence_note || '—' }}</p>
        </section>
        <SampleEvidence :sample="sample" />
      </template>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getEvaluationSample } from '@/api/application/evaluation'
import SampleEvidence from './SampleEvidence.vue'
import './evaluation-detail.scss'

const props = defineProps<{ applicationId: string; sampleId: string }>()
const visible = defineModel<boolean>({ default: false })
const { t } = useI18n()
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
const sample = ref<any>()
const loading = ref(false)
const failed = ref(false)
let requestId = 0
const load = async () => {
  const current = ++requestId
  loading.value = true
  failed.value = false
  sample.value = undefined
  try {
    const result = await getEvaluationSample(props.applicationId, props.sampleId)
    if (current === requestId) sample.value = result.data
  } catch { if (current === requestId) failed.value = true }
  finally { if (current === requestId) loading.value = false }
}
watch(() => [visible.value, props.sampleId], () => {
  if (visible.value && props.sampleId) void load()
  else requestId++
})
</script>

<style scoped>
.trace-detail { min-height: 160px; }
</style>
