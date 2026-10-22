<template>
  <el-drawer v-model="visible" :title="tr('traceDetail')" size="75%">
    <div v-loading="loading" class="trace-detail">
      <el-result v-if="failed" icon="error" :title="tr('traceLoadError')">
        <template #extra><el-button @click="load">{{ tr('refresh') }}</el-button></template>
      </el-result>
      <template v-else-if="sample">
        <el-descriptions :column="2" border>
          <el-descriptions-item :label="tr('traceId')">{{ sample.event.chat_record_id }}</el-descriptions-item>
          <el-descriptions-item :label="tr('applicationVersion')">
            {{ sample.event.application_version || '—' }}
            <el-tag v-if="sample.event.application_version" size="small" :type="sample.event.version_inferred ? 'warning' : 'info'">
              {{ tr(sample.event.version_inferred ? 'versionInferred' : 'versionExact') }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <section><h4>{{ tr('question') }}</h4><p>{{ sample.event.question }}</p></section>
        <section><h4>{{ tr('answer') }}</h4><p>{{ sample.event.answer || '—' }}</p></section>
        <section v-if="sample.annotation"><h4>{{ tr('evidenceNote') }}</h4>
          <p>{{ sample.annotation.evidence_note || '—' }}</p>
          <el-text type="info">{{ tr('attributionConfidence') }}：{{ sample.annotation.attribution_confidence ? tr(sample.annotation.attribution_confidence) : '—' }}</el-text>
        </section>
        <el-collapse>
          <el-collapse-item :title="tr('retrievedEvidence')" name="retrieval">
            <el-empty v-if="!sample.event.retrieval_candidates?.length" :description="tr('noEvidence')" />
            <div v-for="(context, index) in sample.event.retrieval_candidates || []" :key="context.id || index" class="context-evidence">
              <el-text type="info">{{ context.document_name || context.document_id || context.id }}</el-text>
              <p>{{ context.content || '—' }}</p>
            </div>
          </el-collapse-item>
          <el-collapse-item :title="tr('citationEvidence')" name="citations">
            <el-text v-if="!sample.event.citation_ids_available" type="info">{{ tr('citationUnavailable') }}</el-text>
            <p v-else>{{ sample.event.citation_ids?.join(', ') || '—' }}</p>
          </el-collapse-item>
          <el-collapse-item :title="tr('nodeEvidence')" name="nodes">
            <el-alert v-if="sample.event.node_evidence_source === 'chat_record'" :title="tr('historicalNodeEvidence')" type="info" :closable="false" />
            <pre v-if="Object.keys(sample.event.node_details || {}).length">{{ JSON.stringify(sample.event.node_details, null, 2) }}</pre>
            <el-empty v-else :description="tr('noEvidence')" />
          </el-collapse-item>
        </el-collapse>
      </template>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getEvaluationSample } from '@/api/application/evaluation'

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
.trace-detail section { margin: 20px 0; }
.trace-detail h4 { margin: 0 0 8px; }
.trace-detail p, .trace-detail pre { white-space: pre-wrap; overflow-wrap: anywhere; }
.trace-detail pre { max-height: 480px; overflow-y: auto; padding: 16px; background: var(--el-fill-color-lighter); }
.context-evidence { padding: 12px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
</style>
