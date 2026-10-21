<template>
  <el-tabs v-model="activeTab" class="quality-tabs">
  <el-tab-pane :label="tr('onlineQuality')" name="quality">
  <el-card>
    <template #header><div class="flex justify-between align-center"><strong>{{ tr('onlineQuality') }}</strong><el-button :loading="loading" @click="load">{{ tr('refresh') }}</el-button></div></template>
    <div v-loading="loading" class="metric-grid">
      <el-empty v-if="!metricRows.length && !loading" :description="tr('noMetrics')" />
      <el-card v-for="row in metricRows" :key="row.key" class="metric-card" shadow="never">
        <el-statistic :title="row.label" :value="row.value" />
      </el-card>
    </div>
  </el-card>
  </el-tab-pane>
  <el-tab-pane :label="tr('experiments')" name="experiments">
  <el-card>
    <template #header><div class="flex justify-between align-center"><strong>{{ tr('experiments') }}</strong><el-button @click="openExperiment">{{ tr('newExperiment') }}</el-button></div></template>
    <el-alert :title="tr('experimentHint')" type="info" :closable="false" class="mb-16" />
    <el-table :data="experiments" v-loading="loading">
      <el-table-column prop="name" :label="tr('experimentName')" />
      <el-table-column :label="tr('subjectType')"><template #default="{ row }">{{ label(row.subject_type) }}</template></el-table-column>
      <el-table-column :label="tr('variants')"><template #default="{ row }">{{ row.variants.map((v: any) => `${v.key}: ${v.weight / 100}%`).join(' / ') }}</template></el-table-column>
      <el-table-column :label="tr('status')"><template #default="{ row }">{{ label(row.status) }}</template></el-table-column>
      <el-table-column :label="tr('actions')"><template #default="{ row }"><el-button link type="primary" :disabled="saving" @click="toggleExperiment(row)">{{ row.status === 'running' ? tr('stop') : tr('startExperiment') }}</el-button></template></el-table-column>
    </el-table>
  </el-card>
  </el-tab-pane>
  <el-tab-pane :label="tr('samples')" name="samples">
  <el-card>
    <template #header><div class="flex justify-between align-center"><strong>{{ tr('samples') }}</strong><el-button :loading="saving" @click="sampleEvents">{{ tr('sample') }}</el-button></div></template>
    <el-text type="info">{{ tr('sampleHint') }}</el-text>
    <el-table :data="samples" v-loading="loading">
      <el-table-column type="expand"><template #default="{ row }"><div class="sample-detail">
        <p><strong>{{ tr('answer') }}</strong></p><p class="answer-text">{{ row.event.answer || '—' }}</p>
        <p><strong>{{ tr('reference') }}</strong></p><p class="answer-text">{{ row.annotation?.gold_answer || '—' }}</p>
        <p>{{ tr('reviewNote') }}: {{ row.annotation?.review_note || '—' }}</p>
        <el-table v-if="row.result" :data="ruleRows(row.result.scores)"><el-table-column prop="label" :label="tr('metric')" /><el-table-column prop="value" :label="tr('value')" /></el-table>
        <p v-for="(reason, key) in row.result?.reasons" :key="key">{{ reason }}</p>
      </div></template></el-table-column>
      <el-table-column prop="event.question" :label="tr('question')" min-width="220" />
      <el-table-column :label="tr('reason')"><template #default="{ row }">{{ label(row.sampling_reason) }}</template></el-table-column>
      <el-table-column :label="tr('status')"><template #default="{ row }">{{ label(row.status) }}</template></el-table-column>
      <el-table-column :label="tr('actions')" width="180"><template #default="{ row }"><el-button link type="primary" :disabled="saving || row.status === 'archived'" @click="openReview(row)">{{ tr('review') }}</el-button><el-button link :disabled="saving || row.status === 'archived'" @click="evaluateSample(row)">{{ tr('evaluate') }}</el-button></template></el-table-column>
    </el-table>
  </el-card>
  </el-tab-pane>
  <el-tab-pane :label="tr('badcases')" name="badcases">
  <el-card>
    <template #header><div class="flex justify-between align-center"><strong>{{ tr('badcases') }}</strong><el-button :loading="saving" @click="generateBadcases">{{ tr('generate') }}</el-button></div></template>
    <el-table :data="badcases" v-loading="loading">
      <el-table-column prop="event.question" :label="tr('question')" min-width="200" />
      <el-table-column :label="tr('category')"><template #default="{ row }">{{ label(row.badcase.category) }}</template></el-table-column>
      <el-table-column :label="tr('status')"><template #default="{ row }">{{ label(row.badcase.status) }}</template></el-table-column>
      <el-table-column prop="badcase.reason" :label="tr('reason')" />
      <el-table-column prop="badcase.suggested_fix" :label="tr('suggestedFix')" />
      <el-table-column prop="badcase.resolution" :label="tr('resolution')" />
      <el-table-column :label="tr('actions')"><template #default="{ row }"><el-button link type="primary" :disabled="saving || row.badcase.status === 'resolved'" @click="openResolution(row)">{{ tr('resolve') }}</el-button></template></el-table-column>
    </el-table>
  </el-card>
  </el-tab-pane>
  </el-tabs>
  <el-dialog v-model="experimentVisible" :title="tr('newExperiment')" width="560px">
    <el-form label-position="top">
      <el-form-item :label="tr('experimentName')" required><el-input v-model="experiment.name" maxlength="128" /></el-form-item>
      <el-form-item :label="tr('subjectType')"><el-select v-model="experiment.subject_type"><el-option v-for="key in ['session', 'user']" :key="key" :label="label(key)" :value="key" /></el-select></el-form-item>
      <el-form-item :label="tr('variants')" required><div v-for="(variant, index) in experiment.variants" :key="index" class="variant-row"><el-input v-model="variant.key" :placeholder="tr('variantKey')" /><el-input-number v-model="variant.percent" :min="1" :max="99" :precision="0" /> %</div></el-form-item>
      <el-text type="info">{{ tr('weightHint') }}</el-text>
    </el-form>
    <template #footer><el-button @click="experimentVisible = false">{{ tr('cancel') }}</el-button><el-button type="primary" :loading="saving" @click="createExperiment">{{ tr('submit') }}</el-button></template>
  </el-dialog>
  <el-dialog v-model="reviewVisible" :title="tr('review')" width="720px">
    <p><strong>{{ selectedSample?.event.question }}</strong></p><p class="answer-text">{{ selectedSample?.event.answer || '—' }}</p>
    <el-form label-position="top">
      <el-form-item v-for="field in reviewFields" :key="field" :label="tr(field)"><el-select v-model="annotation[field]"><el-option v-for="value in ['yes', 'no', 'unknown']" :key="value" :value="value" :label="label(value)" /></el-select></el-form-item>
      <el-form-item :label="tr('answer_score')"><el-input-number v-model="annotation.answer_score" :min="0" :max="1" :step="0.1" :precision="2" /></el-form-item>
      <el-form-item :label="tr('no_answer_handling')"><el-select v-model="annotation.no_answer_handling"><el-option v-for="value in ['correct', 'incorrect', 'not_applicable']" :key="value" :value="value" :label="label(value)" /></el-select></el-form-item>
      <el-form-item :label="tr('category')"><el-select v-model="annotation.badcase_category" clearable><el-option v-for="value in categories" :key="value" :value="value" :label="label(value)" /></el-select></el-form-item>
      <el-form-item :label="tr('reference')"><el-input v-model="annotation.gold_answer" type="textarea" :maxlength="40960" /></el-form-item>
      <el-form-item :label="tr('goldContextIds')"><el-input v-model="goldContextIds" type="textarea" :placeholder="tr('idsHint')" /></el-form-item>
      <el-form-item :label="tr('reviewNote')"><el-input v-model="annotation.review_note" type="textarea" :maxlength="40960" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="reviewVisible = false">{{ tr('cancel') }}</el-button><el-button type="primary" :loading="saving" @click="saveReview">{{ tr('submit') }}</el-button></template>
  </el-dialog>
  <el-dialog v-model="resolutionVisible" :title="tr('resolve')" width="560px">
    <el-input v-model="resolution" type="textarea" :rows="4" :maxlength="40960" :placeholder="tr('resolution')" />
    <template #footer><el-button @click="resolutionVisible = false">{{ tr('cancel') }}</el-button><el-button type="primary" :loading="saving" @click="resolveBadcase">{{ tr('submit') }}</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import {
  getEvaluationMetrics, getEvaluationExperiments, createEvaluationExperiment, actionEvaluationExperiment,
  getEvaluationSamples, sampleEvaluationEvents, annotateEvaluationSample, evaluateEvaluationSample,
  getEvaluationBadcases, generateEvaluationBadcases, updateEvaluationBadcase,
} from '@/api/application/evaluation'

const props = defineProps<{ applicationId: string }>()
const { t, te } = useI18n()
const activeTab = ref('quality')
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
const label = (key: string) => te(`views.applicationEvaluation.ux.labels.${key}`) ? tr(`labels.${key}`) : key
const loading = ref(false)
const saving = ref(false)
const metrics = ref<Record<string, any>>({})
const experiments = ref<any[]>([])
const samples = ref<any[]>([])
const badcases = ref<any[]>([])
const formatValue = (key: string, value: any) => {
  if (value == null || typeof value !== 'number' || !Number.isFinite(value)) return '—'
  if (key.endsWith('_rate') || ['has_context', 'retrieval_hit', 'context_recall', 'citation_ids_complete', 'faithfulness_signal', 'no_answer_response'].includes(key)) return `${(value * 100).toFixed(1)}%`
  if (key.startsWith('latency_ms')) return `${value.toFixed(0)} ms`
  return value.toLocaleString(undefined, { maximumFractionDigits: 6 })
}
const metricRows = computed(() => Object.entries(metrics.value).flatMap(([key, value]) => {
  if (value && typeof value === 'object') return Object.entries(value).map(([part, v]) => ({ key: `${key}.${part}`, label: `${label(key)} · ${label(part)}`, value: formatValue(part === 'count' ? part : `${key}.${part}`, v) }))
  return [{ key, label: label(key), value: formatValue(key, value) }]
}))
const ruleRows = (scores: Record<string, any>) => Object.entries(scores).map(([key, value]) => ({ label: label(key), value: formatValue(key, value) }))
const load = async () => {
  loading.value = true
  try {
    await Promise.allSettled([
      getEvaluationMetrics(props.applicationId).then(r => { metrics.value = r.data?.metrics || {} }),
      getEvaluationExperiments(props.applicationId).then(r => { experiments.value = r.data || [] }),
      getEvaluationSamples(props.applicationId).then(r => { samples.value = r.data || [] }),
      getEvaluationBadcases(props.applicationId).then(r => { badcases.value = r.data || [] }),
    ])
  } finally { loading.value = false }
}
const mutate = async (action: () => Promise<unknown>, done?: () => void) => {
  if (saving.value) return
  saving.value = true
  try {
    await action()
    done?.()
    await load()
  } catch { /* The request interceptor displays API errors. */ }
  finally { saving.value = false }
}
const experimentVisible = ref(false)
const experiment = ref({ name: '', subject_type: 'session', variants: [{ key: 'control', percent: 50 }, { key: 'treatment', percent: 50 }] })
const openExperiment = () => {
  experiment.value = { name: '', subject_type: 'session', variants: [{ key: 'control', percent: 50 }, { key: 'treatment', percent: 50 }] }
  experimentVisible.value = true
}
const createExperiment = () => {
  const form = experiment.value
  if (!form.name.trim() || form.variants.some(v => !v.key.trim() || !Number.isInteger(v.percent) || v.percent <= 0) || new Set(form.variants.map(v => v.key.trim())).size !== form.variants.length || form.variants.reduce((sum, v) => sum + v.percent, 0) !== 100) return ElMessage.warning(tr('experimentInvalid'))
  return mutate(() => createEvaluationExperiment(props.applicationId, { name: form.name.trim(), subject_type: form.subject_type, variants: form.variants.map(v => ({ key: v.key.trim(), weight: v.percent * 100 })) }), () => { experimentVisible.value = false })
}
const toggleExperiment = (row: any) => mutate(() => actionEvaluationExperiment(props.applicationId, row.id, row.status === 'running' ? 'stop' : 'start'))
const sampleEvents = () => mutate(async () => {
  const result = await sampleEvaluationEvents(props.applicationId, { sampling_reason: 'manual', limit: 50 })
  ElMessage.success(tr(result.data?.length ? 'sampled' : 'noNewSamples'))
})
const evaluateSample = (row: any) => mutate(() => evaluateEvaluationSample(props.applicationId, row.id))
const generateBadcases = () => mutate(async () => {
  const result = await generateEvaluationBadcases(props.applicationId)
  ElMessage.success(tr(result.data?.length ? 'badcasesGenerated' : 'noNewBadcases'))
})
const reviewFields = ['answer_correct', 'citation_relevant', 'should_answer', 'faithful', 'needs_handoff']
const categories = ['data', 'retrieval', 'generation', 'prompt', 'model', 'permission', 'user', 'other']
const reviewVisible = ref(false)
const selectedSample = ref<any>()
const annotation = ref<Record<string, any>>({})
const goldContextIds = ref('')
const openReview = (row: any) => {
  selectedSample.value = row
  annotation.value = { ...Object.fromEntries(reviewFields.map(field => [field, 'unknown'])), no_answer_handling: 'not_applicable', gold_answer: '', review_note: '', ...row.annotation }
  goldContextIds.value = (row.annotation?.gold_context_ids || []).join('\n')
  reviewVisible.value = true
}
const saveReview = () => {
  const data: Record<string, any> = { ...annotation.value, gold_context_ids: goldContextIds.value.split(/[\n,，]/).map(v => v.trim()).filter(Boolean) }
  if (data.answer_score == null) delete data.answer_score
  if (!data.badcase_category) delete data.badcase_category
  return mutate(() => annotateEvaluationSample(props.applicationId, selectedSample.value.id, data), () => { reviewVisible.value = false })
}
const resolutionVisible = ref(false)
const selectedBadcase = ref<any>()
const resolution = ref('')
const openResolution = (row: any) => {
  selectedBadcase.value = row.badcase
  resolution.value = row.badcase.resolution || ''
  resolutionVisible.value = true
}
const resolveBadcase = () => mutate(() => updateEvaluationBadcase(props.applicationId, selectedBadcase.value.id, { status: 'resolved', resolution: resolution.value }), () => { resolutionVisible.value = false })
onMounted(load)
</script>

<style scoped>
.quality-tabs { margin-top: 16px; }
.quality-tabs :deep(.el-tabs__header) { margin-bottom: 16px; }
.quality-tabs :deep(.el-tabs__nav-wrap::after) { background-color: var(--el-border-color-lighter); }
.quality-tabs :deep(.el-card) { border-radius: 10px; border-color: var(--el-border-color-lighter); box-shadow: 0 4px 14px rgba(var(--el-text-color-primary-rgb), .04); }
.quality-tabs :deep(.el-card__header) { padding: 14px 18px; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px; min-height: 120px; }
.metric-card { min-width: 0; background: var(--el-fill-color-lighter); }
.metric-card :deep(.el-card__body) { padding: 16px; }
.metric-card :deep(.el-statistic__head) { min-height: 34px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 17px; }
.metric-card :deep(.el-statistic__content) { color: var(--el-text-color-primary); font-size: 24px; font-weight: 600; }
.sample-detail { padding: 16px; }
.answer-text { white-space: pre-wrap; overflow-wrap: anywhere; }
.variant-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
</style>
