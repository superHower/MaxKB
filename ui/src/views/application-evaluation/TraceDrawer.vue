<template>
  <el-drawer v-model="visible" :title="tr('traceDetail')" size="min(1040px, 100vw)" class="evaluation-drawer trace-drawer">
    <div v-loading="loading" class="trace-detail">
      <el-result v-if="failed" icon="error" :title="tr('traceLoadError')">
        <template #extra><el-button @click="load">{{ tr('refresh') }}</el-button></template>
      </el-result>
      <template v-else-if="sample">
        <dl class="eval-meta eval-section">
          <div><dt>{{ tr('traceId') }}</dt><dd class="eval-id">{{ sample.event.chat_record_id }}</dd></div>
          <div><dt>{{ tr('applicationVersion') }}</dt><dd class="eval-tags">
            <span class="eval-id">{{ sample.event.application_version || '—' }}</span>
            <el-tag v-if="sample.event.application_version" size="small" :type="sample.event.version_inferred ? 'warning' : 'info'">
              {{ tr(sample.event.version_inferred ? 'versionInferred' : 'versionExact') }}
            </el-tag>
          </dd></div>
        </dl>
        <section class="eval-section eval-question"><h4 class="eval-section-title">{{ tr('question') }}</h4><p class="eval-copy">{{ sample.event.question }}</p></section>
        <section class="eval-section"><h4 class="eval-section-title">{{ tr('answer') }}</h4><p class="eval-copy">{{ sample.event.answer || '—' }}</p></section>
        <section v-if="sample.annotation" class="eval-section"><h4 class="eval-section-title">{{ tr('evidenceNote') }}
          <el-tag type="info" effect="plain">{{ tr('attributionConfidence') }}：{{ sample.annotation.attribution_confidence ? tr(sample.annotation.attribution_confidence) : '—' }}</el-tag>
        </h4><p class="eval-copy">{{ sample.annotation.evidence_note || '—' }}</p>
        </section>
        <section class="eval-section">
        <el-tabs v-model="activeEvidence" class="eval-tabs">
          <el-tab-pane :label="tr('retrievedEvidence')" name="retrieval">
            <el-empty v-if="!sample.event.retrieval_candidates?.length" :description="tr('noEvidence')" />
            <div v-for="(context, index) in sample.event.retrieval_candidates || []" :key="context.id || index" class="context-evidence">
              <div class="eval-section-title"><span class="evidence-index">{{ index + 1 }}</span><span>{{ context.document_name || context.document_id || context.id || '—' }}</span></div>
              <p class="eval-copy">{{ context.content || '—' }}</p>
            </div>
          </el-tab-pane>
          <el-tab-pane :label="tr('citationEvidence')" name="citations">
            <el-text v-if="!sample.event.citation_ids_available" type="info">{{ tr('citationUnavailable') }}</el-text>
            <p v-else class="eval-copy eval-id">{{ sample.event.citation_ids?.join(', ') || '—' }}</p>
          </el-tab-pane>
          <el-tab-pane :label="tr('nodeEvidence')" name="nodes">
            <el-alert v-if="sample.event.node_evidence_source === 'chat_record'" :title="tr('historicalNodeEvidence')" type="info" :closable="false" />
            <pre v-if="Object.keys(sample.event.node_details || {}).length" class="eval-code">{{ JSON.stringify(sample.event.node_details, null, 2) }}</pre>
            <el-empty v-else :description="tr('noEvidence')" />
          </el-tab-pane>
        </el-tabs>
        </section>
      </template>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getEvaluationSample } from '@/api/application/evaluation'
import './evaluation-detail.scss'

const props = defineProps<{ applicationId: string; sampleId: string }>()
const visible = defineModel<boolean>({ default: false })
const { t } = useI18n()
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
const sample = ref<any>()
const loading = ref(false)
const failed = ref(false)
const activeEvidence = ref('retrieval')
let requestId = 0
const load = async () => {
  const current = ++requestId
  loading.value = true
  failed.value = false
  sample.value = undefined
  activeEvidence.value = 'retrieval'
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
.context-evidence { padding: 16px; margin-bottom: 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.context-evidence:last-child { margin-bottom: 0; }
.context-evidence .eval-section-title { justify-content: flex-start; overflow-wrap: anywhere; }
.evidence-index { display: inline-flex; flex: 0 0 24px; align-items: center; justify-content: center; height: 24px; border-radius: 4px; color: var(--el-color-primary); background: var(--el-color-primary-light-9); font-size: 12px; }
</style>
