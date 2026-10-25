<template>
  <el-alert type="info" :closable="false" show-icon class="qc-source">
    <template #title>{{ tr('qcSourceOnline') }} <el-button link type="primary" @click="openEvaluationReports">{{ tr('qcSourceOffline') }} →</el-button></template>
  </el-alert>
  <section class="qc-guide" :aria-label="tr('qcGuideTitle')">
    <button v-for="(step, index) in guideSteps" :key="step.key" type="button" class="qc-step" :class="{ active: step.active }" @click="step.go">
      <span class="qc-step-index">{{ index + 1 }}</span>
      <span class="qc-step-body"><strong>{{ tr(step.title) }}</strong><span>{{ tr(step.desc) }}</span></span>
      <span class="qc-step-count"><strong>{{ step.count }}</strong><span>{{ tr(step.countLabel) }}</span></span>
    </button>
  </section>
  <el-tabs v-model="activeTab" class="quality-tabs">
  <el-tab-pane :label="tr('pendingTab')" name="samples">
    <el-card class="quality-card" shadow="never">
      <template #header><div class="panel-heading">
        <div class="queue-toolbar">
          <el-radio-group v-model="queueFilter" size="small"><el-radio-button v-for="filter in queueFilters" :key="filter" :value="filter">{{ tr('qcQueue_' + filter) }} · {{ queue.filter(row => matchesQueue(row, filter)).length }}</el-radio-button></el-radio-group>
          <el-input v-model="queueSearch" clearable :prefix-icon="Search" :placeholder="tr('search')" :aria-label="tr('search')" />
        </div>
        <div class="queue-actions">
          <el-button :icon="Refresh" :loading="loading" :aria-label="tr('refresh')" @click="load" />
          <el-tooltip :content="tr('qcGenerateHint')"><el-button :loading="saving" @click="generateBadcases">{{ tr('qcGenerate') }}</el-button></el-tooltip>
          <el-tooltip :content="tr('sampleHint')"><el-button type="primary" :icon="Plus" :loading="saving" @click="sampleEvents">{{ tr('qcSample') }}</el-button></el-tooltip>
        </div>
      </div></template>
      <el-table :data="filteredQueue" v-loading="loading" row-key="id" class="queue-table" @row-click="openSampleDetail">
        <template #empty><el-empty :image-size="64" :description="tr(queue.length ? 'queueEmpty' : 'qcQueueStart')"><el-button v-if="!queue.length" type="primary" :loading="saving" @click="sampleEvents">{{ tr('qcSample') }}</el-button></el-empty></template>
        <el-table-column prop="event.question" :label="tr('question')" min-width="320" show-overflow-tooltip />
        <el-table-column :label="tr('status')" width="130"><template #default="{ row }"><el-tag :type="stateType(stateOf(row))" effect="light">{{ tr('qcState_' + stateOf(row)) }}</el-tag></template></el-table-column>
        <el-table-column :label="tr('diagPrimary')" min-width="220" show-overflow-tooltip><template #default="{ row }"><template v-if="findingsOf(row).length"><el-tag size="small" effect="dark" :type="AREA_TAG[findingsOf(row)[0].area]">{{ tr('area_' + findingsOf(row)[0].area) }}</el-tag> <span class="queue-reason">{{ t(`views.applicationEvaluation.ux.${findingsOf(row)[0].key}`, findingsOf(row)[0].params) }}</span></template><span v-else class="queue-reason">—</span></template></el-table-column>
        <el-table-column :label="tr('date')" width="180"><template #default="{ row }">{{ date(row.created_at) }}</template></el-table-column>
        <el-table-column :label="tr('actions')" width="100" fixed="right"><template #default="{ row }"><el-button link type="primary" @click.stop="openSampleDetail(row)">{{ tr(stateOf(row) === 'processed' ? 'datasetView' : 'qcHandle') }}</el-button></template></el-table-column>
      </el-table>
    </el-card>
  </el-tab-pane>
  <el-tab-pane :label="tr('improvementsTab')" name="improve" lazy>
    <el-tabs v-model="improvementTab" class="improve-tabs">
      <el-tab-pane :label="tr('qcCandidates')" name="candidates"><CandidatePanel :application-id="props.applicationId" :runs="props.runs" :preset="candidatePreset" @preset-used="consumePreset" /></el-tab-pane>
      <el-tab-pane :label="tr('qcReleases')" name="releases" lazy><ReleasePanel :application-id="props.applicationId" /></el-tab-pane>
    </el-tabs>
  </el-tab-pane>
  <el-tab-pane :label="tr('signalsTab')" name="signals">
  <el-card class="quality-card" shadow="never">
    <template #header><div class="panel-heading"><div><strong>{{ tr('signalsTab') }}</strong><el-text type="info">{{ tr('qcSignalsDesc') }}</el-text></div><el-button :icon="Refresh" :loading="loading" @click="load">{{ tr('refresh') }}</el-button></div></template>
    <div v-loading="loading" class="metrics-dashboard">
      <el-empty v-if="!metricRows.length && !loading" :description="tr('noMetrics')" :image-size="80" />
      <div v-else class="metric-grid">
        <el-card v-for="row in keyMetricRows" :key="row.key" class="metric-card" shadow="never">
          <el-statistic :title="row.label" :value="row.rawValue ?? 0" :formatter="() => row.value" />
          <el-progress v-if="row.percentage != null" :percentage="row.percentage" :show-text="false" :stroke-width="6" :color="row.negative ? 'var(--el-color-warning)' : 'var(--el-color-primary)'" />
        </el-card>
      </div>
      <el-collapse v-if="metricRows.length" class="all-metrics"><el-collapse-item :title="tr('qcAllMetrics')" name="all">
        <section v-for="group in metricGroups" :key="group.key" class="metric-section" :aria-label="tr(group.title)">
          <h3 class="metric-section-title"><el-icon><component :is="group.icon" /></el-icon>{{ tr(group.title) }}</h3>
          <div class="metric-grid">
            <el-card v-for="row in group.rows" :key="row.key" class="metric-card" shadow="never">
              <el-statistic :title="row.label" :value="row.rawValue ?? 0" :formatter="() => row.value" />
              <el-progress v-if="row.percentage != null" :percentage="row.percentage" :show-text="false" :stroke-width="6" :color="row.negative ? 'var(--el-color-warning)' : 'var(--el-color-primary)'" />
            </el-card>
          </div>
        </section>
      </el-collapse-item></el-collapse>
    </div>
  </el-card>
  </el-tab-pane>
  </el-tabs>
  <el-drawer v-model="sampleDetailVisible" :title="tr('sampleDetail')" size="min(960px, 100vw)" class="evaluation-drawer sample-drawer" destroy-on-close>
    <div v-if="sampleDetail" class="sample-detail">
      <section class="sample-question"><el-tag :type="stateType(stateOf(sampleDetail))" round>{{ tr('qcState_' + stateOf(sampleDetail)) }}</el-tag><h3>{{ sampleDetail.event.question }}</h3></section>
      <el-alert :title="tr('qcNext_' + stateOf(sampleDetail))" type="info" show-icon :closable="false" class="sample-next" />
      <section class="sample-diagnosis"><h4>{{ tr('diagTitle') }} <EvaluationHelp :text="tr('diagHelp')" /></h4><DiagnosisPanel :findings="findingsOf(sampleDetail)" :trace="sampleDetail.event?.trace" :allow-candidate="hasOpenBadcase(sampleDetail)" @candidate="createImprovement(sampleDetail, $event)" /></section>
      <div class="sample-answers">
        <section class="sample-answer"><h4>{{ tr('answer') }}</h4><el-scrollbar max-height="320px"><p class="answer-text">{{ sampleDetail.event.answer || '—' }}</p></el-scrollbar></section>
        <section class="sample-answer"><h4>{{ tr('reference') }}</h4><el-scrollbar max-height="320px"><p class="answer-text">{{ sampleDetail.annotation?.gold_answer || '—' }}</p></el-scrollbar></section>
      </div>
      <el-collapse v-model="detailSections" class="sample-sections">
        <el-collapse-item v-if="sampleDetail.badcase" name="badcase">
          <template #title><span class="section-title">{{ tr('badcases') }} <el-tag size="small" :type="qualityStatusType(sampleDetail.badcase.status)">{{ label(sampleDetail.badcase.status) }}</el-tag></span></template>
          <el-descriptions :column="1" border><el-descriptions-item :label="tr('category')">{{ label(sampleDetail.badcase.category) }}</el-descriptions-item><el-descriptions-item :label="tr('reason')">{{ sampleDetail.badcase.reason }}</el-descriptions-item><el-descriptions-item :label="tr('suggestedFix')">{{ sampleDetail.badcase.suggested_fix || '—' }}</el-descriptions-item><el-descriptions-item :label="tr('resolution')">{{ sampleDetail.badcase.resolution || '—' }}</el-descriptions-item></el-descriptions>
        </el-collapse-item>
        <el-collapse-item v-if="sampleDetail.result" name="rules">
          <template #title><span class="section-title">{{ tr('ruleGrading') }} <el-tag size="small" :type="hasRuleSignal(sampleDetail) ? 'warning' : 'success'" effect="plain">{{ tr(hasRuleSignal(sampleDetail) ? 'ruleSignal' : 'evaluatedLabel') }}</el-tag></span></template>
          <div class="metric-grid rule-metric-grid">
            <el-card v-for="metric in ruleRows(sampleDetail.result.scores)" :key="metric.key" class="metric-card" shadow="never">
              <el-statistic :title="metric.label" :value="metric.rawValue ?? 0" :formatter="() => metric.value" />
              <el-progress v-if="metric.percentage != null" :percentage="metric.percentage" :show-text="false" :stroke-width="6" />
            </el-card>
          </div>
          <el-alert v-for="(reason, key) in sampleDetail.result.reasons" :key="key" :title="String(reason)" type="info" :closable="false" show-icon class="rule-reason" />
        </el-collapse-item>
        <el-collapse-item v-if="sampleDetail.annotation" name="review" :title="tr('humanReview')">
          <div class="sample-capabilities"><el-tag v-for="field in reviewFields" :key="field" type="info" effect="plain">{{ tr(field) }}: {{ label(sampleDetail.annotation[field] || 'unknown') }}</el-tag><el-tag type="info" effect="plain">{{ tr('humanScore') }}: {{ score(sampleDetail.annotation.answer_score) }}</el-tag></div>
          <el-descriptions :column="1" border class="sample-annotation">
            <el-descriptions-item :label="tr('reviewNote')">{{ sampleDetail.annotation.review_note || '—' }}</el-descriptions-item>
            <el-descriptions-item :label="tr('attributionConfidence')">{{ sampleDetail.annotation.attribution_confidence ? label(sampleDetail.annotation.attribution_confidence) : '—' }}</el-descriptions-item>
            <el-descriptions-item :label="tr('evidenceNote')">{{ sampleDetail.annotation.evidence_note || '—' }}</el-descriptions-item>
          </el-descriptions>
        </el-collapse-item>
        <el-collapse-item name="evidence" :title="tr('qcEvidence')">
          <div v-if="sampleDetail.event.capabilities" class="sample-capabilities">
            <el-tag size="small" :type="sampleDetail.event.capabilities.memory_enabled ? 'success' : 'info'">{{ sampleDetail.event.capabilities.memory_used ? tr('memoryUsed') : sampleDetail.event.capabilities.memory_enabled ? tr('memoryEnabled') : tr('memoryDisabled') }}</el-tag>
            <el-tag size="small" :type="sampleDetail.event.capabilities.skill_bound ? 'success' : 'info'">{{ sampleDetail.event.capabilities.skill_bound ? `${tr('skillsBound')} ${sampleDetail.event.capabilities.skill_ids.length}` : tr('noSkills') }}</el-tag>
            <el-tag v-if="sampleDetail.event.capabilities.business_branch_configured" size="small" type="warning">{{ sampleDetail.event.capabilities.business_tool_call_present ? tr('businessToolCalled') : tr('businessPromptOnly') }}</el-tag>
          </div>
          <section v-loading="evidenceLoading" class="sample-evidence-section">
            <el-result v-if="evidenceFailed" icon="error" :title="tr('traceLoadError')"><template #extra><el-button @click="loadSampleEvidence">{{ tr('refresh') }}</el-button></template></el-result>
            <SampleEvidence v-else-if="evidenceSample" :key="sampleDetailId" :sample="evidenceSample" />
          </section>
        </el-collapse-item>
      </el-collapse>
    </div>
    <template #footer>
      <div v-if="sampleDetail" class="sample-detail-actions">
        <el-tooltip :content="tr('qcRecheckHint')"><el-button :loading="saving" :disabled="sampleDetail.status === 'archived'" @click="evaluateSample(sampleDetail)">{{ tr('qcRecheck') }}</el-button></el-tooltip>
        <template v-if="hasOpenBadcase(sampleDetail)">
          <el-button :disabled="saving" @click="openResolution(sampleDetail)">{{ tr('resolve') }}</el-button>
          <el-button :disabled="saving || sampleDetail.status === 'archived'" @click="openReview(sampleDetail)">{{ tr(sampleDetail.annotation ? 'qcEditReview' : 'humanReview') }}</el-button>
          <el-button type="primary" @click="createImprovement(sampleDetail)">{{ tr('qcCreateImprovement') }}</el-button>
        </template>
        <el-button v-else type="primary" :disabled="saving || sampleDetail.status === 'archived'" @click="openReview(sampleDetail)">{{ tr(sampleDetail.annotation ? 'qcEditReview' : 'humanReview') }}</el-button>
      </div>
    </template>
  </el-drawer>

  <el-dialog v-model="reviewVisible" :title="tr('review')" width="min(760px, 94vw)" class="evaluation-dialog review-dialog quality-form-dialog">
    <div class="review-context"><h4>{{ selectedSample?.event.question }}</h4><el-scrollbar max-height="200px"><p class="answer-text">{{ selectedSample?.event.answer || '—' }}</p></el-scrollbar></div>
    <el-form label-position="top" class="review-form">
      <div class="review-check-grid">
        <el-form-item v-for="field in reviewFields" :key="field" :label="tr(field)"><el-radio-group v-model="annotation[field]" size="small"><el-radio-button v-for="value in ['yes', 'no', 'unknown']" :key="value" :value="value">{{ label(value) }}</el-radio-button></el-radio-group></el-form-item>
      </div>
      <div class="review-meta-grid">
        <el-form-item :label="tr('answer_score')"><el-input-number v-model="annotation.answer_score" :min="0" :max="1" :step="0.1" :precision="2" /></el-form-item>
        <el-form-item><template #label>{{ tr('category') }} <EvaluationHelp :text="tr('qcCategoryHint')" /></template><el-select v-model="annotation.badcase_category" clearable><el-option v-for="value in categories" :key="value" :value="value" :label="label(value)" /></el-select></el-form-item>
      </div>
      <el-form-item :label="tr('reviewNote')"><el-input v-model="annotation.review_note" type="textarea" :maxlength="40960" /></el-form-item>
      <el-collapse class="review-more"><el-collapse-item :title="tr('qcMoreAnnotation')" name="more">
        <div class="review-meta-grid">
          <el-form-item :label="tr('no_answer_handling')"><el-select v-model="annotation.no_answer_handling"><el-option v-for="value in ['correct', 'incorrect', 'not_applicable']" :key="value" :value="value" :label="label(value)" /></el-select></el-form-item>
          <el-form-item :label="tr('attributionConfidence')"><el-select v-model="annotation.attribution_confidence"><el-option v-for="value in ['high', 'medium', 'low']" :key="value" :value="value" :label="label(value)" /></el-select></el-form-item>
        </div>
        <el-form-item :label="tr('reference')"><el-input v-model="annotation.gold_answer" type="textarea" :maxlength="40960" /></el-form-item>
        <el-form-item :label="tr('goldContextIds')"><el-input v-model="goldContextIds" type="textarea" :placeholder="tr('idsHint')" /></el-form-item>
        <el-form-item :label="tr('evidenceNote')"><el-input v-model="annotation.evidence_note" type="textarea" :maxlength="40960" /></el-form-item>
      </el-collapse-item></el-collapse>
    </el-form>
    <template #footer><el-button @click="reviewVisible = false">{{ tr('cancel') }}</el-button><el-button type="primary" :loading="saving" @click="saveReview">{{ tr('submit') }}</el-button></template>
  </el-dialog>
  <el-dialog v-model="resolutionVisible" :title="tr('resolve')" width="min(560px, 94vw)" class="evaluation-dialog">
    <el-input v-model="resolution" type="textarea" :rows="4" :maxlength="40960" :placeholder="tr('resolution')" />
    <template #footer><el-button @click="resolutionVisible = false">{{ tr('cancel') }}</el-button><el-button type="primary" :loading="saving" @click="resolveBadcase">{{ tr('submit') }}</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataAnalysis, DocumentChecked, Plus, Refresh, Search, Timer, Wallet } from '@element-plus/icons-vue'
import EvaluationHelp from './EvaluationHelp.vue'
import { useEvaluationNavigation } from './useEvaluationNavigation'
import SampleEvidence from './SampleEvidence.vue'
import DiagnosisPanel from './DiagnosisPanel.vue'
import { AREA_TAG, diagnoseSample } from './diagnosis'
import CandidatePanel from './CandidatePanel.vue'
import ReleasePanel from './ReleasePanel.vue'
import './evaluation-detail.scss'
import {
  getEvaluationMetrics,
  getEvaluationSample, getEvaluationSamples, sampleEvaluationEvents, annotateEvaluationSample, evaluateEvaluationSample,
  getEvaluationBadcases, generateEvaluationBadcases, updateEvaluationBadcase,
} from '@/api/application/evaluation'

const props = defineProps<{ applicationId: string; runs: any[] }>()
const { t, te } = useI18n()
const activeTab = useEvaluationNavigation('tab', () => ['samples', 'improve', 'signals'], 'samples')
const improvementTab = useEvaluationNavigation('improvement', () => ['candidates', 'releases'], 'candidates')
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
const date = (value: string) => (value ? new Date(value).toLocaleString() : '—')
const qualityStatusType = (value: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' => {
  if (['completed', 'reviewed', 'resolved'].includes(value)) return 'success'
  if (['running', 'evaluated', 'in_progress'].includes(value)) return 'primary'
  if (['pending_review', 'open'].includes(value)) return 'warning'
  return 'info'
}
const score = (value: any) => value == null ? tr('unscored') : `${(Number(value) * 100).toFixed(1)}%`
const label = (key: string) => te(`views.applicationEvaluation.ux.labels.${key}`) ? tr(`labels.${key}`) : key
const loading = ref(false)
const saving = ref(false)
const metrics = ref<Record<string, any>>({})
const samples = ref<any[]>([])
const sampleDetailVisible = ref(false)
const sampleDetailId = ref('')
const sampleDetail = computed(() => queue.value.find(row => row.id === sampleDetailId.value))
const detailSections = ref<string[]>([])
const evidenceSample = ref<any>()
const evidenceLoading = ref(false)
const evidenceFailed = ref(false)
let evidenceRequestId = 0
const loadSampleEvidence = async () => {
  const current = ++evidenceRequestId
  evidenceLoading.value = true
  evidenceFailed.value = false
  evidenceSample.value = undefined
  try {
    const result = await getEvaluationSample(props.applicationId, sampleDetailId.value)
    if (current === evidenceRequestId) evidenceSample.value = result.data
  } catch { if (current === evidenceRequestId) evidenceFailed.value = true }
  finally { if (current === evidenceRequestId) evidenceLoading.value = false }
}
watch(() => [sampleDetailVisible.value, sampleDetailId.value, props.applicationId], () => {
  if (sampleDetailVisible.value && sampleDetailId.value) void loadSampleEvidence()
  else evidenceRequestId++
})
onBeforeUnmount(() => { evidenceRequestId++ })
const badcases = ref<any[]>([])
const queueSearch = ref('')
const queueFilters = ['todo', 'issue', 'processed', 'all']
const queueFilter = useEvaluationNavigation('queue', () => queueFilters, 'todo')
const queue = computed<any[]>(() => Array.from(new Map([...badcases.value, ...samples.value].map(row => [row.id, row])).values()).sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')))
const hasRuleSignal = (row: any) => ['retrieval_hit', 'context_recall', 'citation_ids_complete', 'confirmation_compliance', 'task_success', 'tool_call_accuracy'].some(key => row.result?.scores?.[key] != null && Number(row.result.scores[key]) < 0.6)
const hasLowScore = (row: any) => row.annotation?.answer_score != null && Number(row.annotation.answer_score) < 0.6
const hasOpenBadcase = (row: any) => !!row.badcase && !['resolved', 'ignored'].includes(row.badcase.status)
const isProcessed = (row: any) => row.status === 'archived' || (row.badcase ? !hasOpenBadcase(row) : !!row.annotation && !hasLowScore(row) && !hasRuleSignal(row))
// One state per row, in priority order, so the list never shows four competing status columns.
const stateOf = (row: any) => {
  if (isProcessed(row)) return 'processed'
  if (row.badcase) return 'badcase'
  if (hasRuleSignal(row)) return 'rule'
  if (hasLowScore(row)) return 'low'
  return 'review'
}
const stateType = (state: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' => state === 'processed' ? 'success' : state === 'badcase' ? 'danger' : state === 'review' ? 'primary' : 'warning'
const matchesQueue = (row: any, filter: string) => {
  const state = stateOf(row)
  if (filter === 'todo') return state !== 'processed'
  if (filter === 'issue') return ['badcase', 'rule', 'low'].includes(state)
  if (filter === 'processed') return state === 'processed'
  return true
}
const filteredQueue = computed(() => queue.value.filter(row => matchesQueue(row, queueFilter.value) && `${row.event?.question || ''} ${row.event?.answer || ''} ${row.badcase?.reason || ''}`.toLowerCase().includes(queueSearch.value.toLowerCase())))
const openQueue = (filter: string) => { queueSearch.value = ''; queueFilter.value = filter; activeTab.value = 'samples' }
const openSampleDetail = (row: any) => {
  sampleDetailId.value = row.id
  detailSections.value = row.badcase ? ['badcase'] : hasRuleSignal(row) ? ['rules'] : []
  sampleDetailVisible.value = true
}
const guideSteps = computed(() => [
  { key: 'collect', title: 'qcStepCollect', desc: 'qcStepCollectDesc', count: queue.value.length, countLabel: 'qcSampled', active: activeTab.value === 'samples' && queueFilter.value === 'all', go: () => openQueue('all') },
  { key: 'review', title: 'qcStepReview', desc: 'qcStepReviewDesc', count: queue.value.filter(row => stateOf(row) !== 'processed').length, countLabel: 'qcQueue_todo', active: activeTab.value === 'samples' && queueFilter.value !== 'all', go: () => openQueue('todo') },
  { key: 'improve', title: 'qcStepImprove', desc: 'qcStepImproveDesc', count: queue.value.filter(hasOpenBadcase).length, countLabel: 'qcOpenBadcases', active: activeTab.value === 'improve', go: () => { activeTab.value = 'improve' } },
])
const improveSteps = ['qcFlowPlan', 'qcFlowValidate', 'qcFlowApprove', 'qcFlowRollout', 'qcFlowPromote']
const route = useRoute()
const router = useRouter()
// A report finding arrives as ?baseline=<run>&node=<node>; an online Badcase is passed directly.
const candidatePreset = ref<{ badcase?: any; baselineId?: string; nodeId?: string; event?: any; finding?: any } | undefined>(route.query.baseline ? { baselineId: String(route.query.baseline), nodeId: String(route.query.node || '') } : undefined)
const consumePreset = () => {
  candidatePreset.value = undefined
  if (route.query.baseline) void router.replace({ query: { ...route.query, baseline: undefined, node: undefined } })
}
const diagnosisCache = new WeakMap<object, ReturnType<typeof diagnoseSample>>()
const findingsOf = (row: any) => {
  if (!diagnosisCache.has(row)) diagnosisCache.set(row, diagnoseSample(row))
  return diagnosisCache.get(row)!
}
const openEvaluationReports = () => router.push({ name: 'ApplicationEvaluation', params: route.params, query: { tab: 'reports' } })
const createImprovement = (row: any, finding?: any) => {
  const evidence = finding || findingsOf(row)[0]
  candidatePreset.value = { badcase: row.badcase, event: row.event, finding: evidence, nodeId: evidence?.nodeId }
  sampleDetailVisible.value = false
  activeTab.value = 'improve'
  improvementTab.value = 'candidates'
}

const isRateMetric = (key: string) => key.endsWith('_rate') || ['tool_call_accuracy', 'has_context', 'retrieval_hit', 'context_recall', 'citation_ids_complete', 'faithfulness_signal', 'no_answer_response'].includes(key)
const formatValue = (key: string, value: any) => {
  if (typeof value === 'boolean') return label(value ? 'yes' : 'no')
  if (value == null || typeof value !== 'number' || !Number.isFinite(value)) return '—'
  if (isRateMetric(key)) return `${(value * 100).toFixed(1)}%`
  if (key.startsWith('latency_ms')) return `${value.toFixed(0)} ms`
  return value.toLocaleString(undefined, { maximumFractionDigits: 6 })
}
const metricRow = (key: string, name: string, value: any, formatKey = key) => {
  const rawValue = typeof value === 'number' && Number.isFinite(value) ? value : null
  return {
    key, label: name, rawValue, value: formatValue(formatKey, value),
    percentage: isRateMetric(key) && rawValue != null ? Math.min(100, Math.max(0, rawValue * 100)) : null,
    negative: ['dislike_rate', 'no_answer_rate', 'human_handoff_rate'].includes(key),
  }
}
const metricRows = computed(() => Object.entries(metrics.value).flatMap(([key, value]) => {
  if (value && typeof value === 'object') return Object.entries(value).map(([part, v]) => metricRow(`${key}.${part}`, `${label(key)} · ${label(part)}`, v, part === 'count' ? part : `${key}.${part}`))
  return [metricRow(key, label(key), value)]
}))
const keyMetrics = ['resolved_rate', 'dislike_rate', 'no_answer_rate', 'human_handoff_rate', 'latency_ms.p95', 'estimated_cost']
const keyMetricRows = computed(() => keyMetrics.map(key => metricRows.value.find(row => row.key === key)).filter(Boolean) as ReturnType<typeof metricRow>[])
const metricGroups = computed(() => [
  { key: 'volume', title: 'qualityVolume', icon: DataAnalysis, rows: metricRows.value.filter(row => ['sample_count', 'effective_count', 'tool_call_count'].includes(row.key)) },
  { key: 'quality', title: 'qualitySignals', icon: DocumentChecked, rows: metricRows.value.filter(row => !['sample_count', 'effective_count', 'tool_call_count', 'estimated_cost'].includes(row.key) && !row.key.startsWith('latency_ms.') && !row.key.startsWith('tokens.')) },
  { key: 'latency', title: 'qualityLatency', icon: Timer, rows: metricRows.value.filter(row => row.key.startsWith('latency_ms.')) },
  { key: 'resources', title: 'qualityResources', icon: Wallet, rows: metricRows.value.filter(row => row.key.startsWith('tokens.') || row.key === 'estimated_cost') },
].filter(group => group.rows.length))
const ruleRows = (scores: Record<string, any> = {}) => Object.entries(scores || {}).map(([key, value]) => metricRow(key, label(key), value))
const load = async () => {
  loading.value = true
  try {
    await Promise.allSettled([
      getEvaluationMetrics(props.applicationId).then(r => { metrics.value = r.data?.metrics || {} }),
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
const categories = ['data', 'retrieval', 'generation', 'prompt', 'model', 'permission', 'user', 'business', 'other']
const reviewVisible = ref(false)
const selectedSample = ref<any>()
const annotation = ref<Record<string, any>>({})
const goldContextIds = ref('')
const openReview = (row: any) => {
  selectedSample.value = row
  annotation.value = { ...Object.fromEntries(reviewFields.map(field => [field, 'unknown'])), no_answer_handling: 'not_applicable', attribution_confidence: 'medium', gold_answer: '', review_note: '', evidence_note: '', ...row.annotation }
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
onMounted(() => { void load() })
</script>

<style scoped>
.qc-source { margin: 4px 0 12px; }
.queue-reason { color: var(--el-text-color-regular); font-size: 13px; }
.sample-diagnosis { margin-bottom: 16px; }
.sample-diagnosis h4 { display: flex; align-items: center; gap: 4px; margin: 0 0 10px; font-size: 14px; }
.qc-guide { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 4px 0 8px; }
.qc-step { display: flex; align-items: center; gap: 12px; min-width: 0; padding: 14px 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 10px; background: var(--el-bg-color); color: var(--el-text-color-regular); text-align: left; cursor: pointer; font: inherit; }
.qc-step:hover, .qc-step:focus-visible, .qc-step.active { border-color: var(--el-color-primary-light-5); background: var(--el-color-primary-light-9); }
.qc-step-index { display: inline-flex; flex: none; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 50%; background: var(--el-color-primary); color: var(--el-color-white); font-size: 13px; font-weight: 600; }
.qc-step-body { display: flex; flex: 1; flex-direction: column; gap: 4px; min-width: 0; }
.qc-step-body strong { color: var(--el-text-color-primary); font-size: 14px; }
.qc-step-body span, .qc-step-count span { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.qc-step-count { display: flex; flex: none; flex-direction: column; align-items: flex-end; }
.qc-step-count strong { color: var(--el-text-color-primary); font-size: 22px; font-variant-numeric: tabular-nums; line-height: 1.2; }
.queue-toolbar, .queue-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.queue-toolbar > .el-input { width: 240px; }
.queue-toolbar > .el-radio-group { flex-wrap: wrap; gap: 4px 0; }
.queue-table :deep(.el-table__row) { cursor: pointer; }
.improve-steps { padding: 10px 16px; }
.improve-tabs :deep(.candidate-panel) { margin-top: 0; }
.all-metrics { margin-top: 20px; border-top: 0; }
.all-metrics :deep(.el-collapse-item__header) { color: var(--el-text-color-secondary); font-size: 13px; }
.sample-next { margin-bottom: 16px; }
.sample-sections { margin-top: 16px; }
.sample-sections :deep(.el-collapse-item__content) { padding-bottom: 16px; }
.section-title { display: inline-flex; align-items: center; gap: 8px; font-weight: 600; }
.review-more { margin-top: 4px; }
.rule-reason { margin-top: 12px; }
.quality-tabs { margin-top: 4px; }
.quality-tabs :deep(.el-tabs__item) { height: 44px; color: var(--el-text-color-secondary); font-weight: 500; }
.quality-tabs :deep(.el-tabs__item.is-active) { color: var(--el-color-primary); font-weight: 650; }
.panel-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.panel-heading > div:not(.queue-actions):not(.queue-toolbar) { display: flex; flex-direction: column; gap: 4px; }
.panel-heading .el-text { font-size: 12px; }
.quality-tabs :deep(.el-tabs__header) { margin-bottom: 16px; }
.quality-tabs :deep(.el-tabs__nav-wrap::after) { background-color: var(--el-border-color-lighter); }
.quality-card { border-radius: 12px; border-color: var(--el-border-color-lighter); box-shadow: none; }
.quality-card :deep(.el-card__header) { padding: 16px 24px; }
.quality-card :deep(.el-card__body) { padding: 0; }
.panel-heading strong { font-size: 16px; line-height: 24px; }
.panel-heading .el-text { align-self: flex-start; line-height: 20px; }
.quality-card :deep(.el-table) { --el-table-header-bg-color: var(--el-fill-color-lighter); border-radius: 0 0 12px 12px; }
.quality-card :deep(th.el-table__cell) { padding: 12px 0; color: var(--el-text-color-secondary); font-size: 12px; font-weight: 500; }
.quality-card :deep(td.el-table__cell) { padding: 14px 0; }
.quality-card :deep(.el-table .cell) { line-height: 24px; }
.metrics-dashboard { min-height: 160px; padding: 24px; }
.metric-section + .metric-section { margin-top: 28px; padding-top: 24px; border-top: 1px solid var(--el-border-color-lighter); }
.metric-section-title { display: flex; align-items: center; gap: 8px; margin: 0 0 16px; color: var(--el-text-color-regular); font-size: 14px; font-weight: 600; }
.metric-section-title .el-icon { color: var(--el-text-color-secondary); font-size: 16px; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr)); gap: 12px; }
.metric-card { min-width: 0; background: var(--el-fill-color-lighter); border-color: var(--el-border-color-lighter); border-radius: 8px; }
.metric-card :deep(.el-card__body) { display: flex; flex-direction: column; gap: 16px; padding: 20px; }
.metric-card :deep(.el-statistic__head) { min-height: 20px; margin-bottom: 12px; color: var(--el-text-color-regular); font-size: 13px; line-height: 20px; }
.metric-card :deep(.el-statistic__content) { color: var(--el-text-color-primary); font-size: 26px; font-weight: 600; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.sample-detail { min-width: 0; }
.sample-question { padding: 20px; margin-bottom: 16px; background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.sample-question h3 { margin: 12px 0 0; font-size: 18px; line-height: 1.6; overflow-wrap: anywhere; }
.sample-detail-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.sample-detail-actions .el-button { margin-left: 0; }
.sample-drawer :deep(.el-drawer__footer) { padding: 16px 24px; border-top: 1px solid var(--el-border-color-lighter); }
.sample-answers { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.sample-answer { min-width: 0; padding: 20px; background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.sample-answer h4 { margin: 0 0 12px; color: var(--el-text-color-secondary); font-size: 13px; font-weight: 500; }
.sample-answer p { margin: 0; line-height: 1.8; }
.sample-annotation :deep(.el-descriptions__label) { width: 140px; font-weight: 500; }
.sample-annotation :deep(.el-descriptions__content) { white-space: pre-wrap; overflow-wrap: anywhere; }
.sample-evidence-section { min-height: 120px; margin-top: 8px; }
.rule-metric-grid { padding-top: 8px; }
.sample-capabilities { display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 12px; }
.answer-text { white-space: pre-wrap; overflow-wrap: anywhere; }
.quality-tabs :deep(.el-table__row:hover > td) { background: var(--el-fill-color-light); }
.quality-form-dialog :deep(.el-select) { width: 100%; }
.review-context { padding: 16px 20px; margin-bottom: 20px; background: var(--el-fill-color-lighter); border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.review-context h4 { margin: 0 0 12px; font-size: 15px; line-height: 1.6; overflow-wrap: anywhere; }
.review-context p { margin: 0; color: var(--el-text-color-regular); line-height: 1.8; }
.review-check-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 20px; padding: 16px 16px 0; margin-bottom: 20px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.review-meta-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 24px; }
.review-meta-grid .el-input-number { width: 100%; }
@media (max-width: 900px) {
  .qc-guide { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .queue-toolbar > .el-input { width: 100%; }
  .panel-heading { align-items: flex-start; flex-direction: column; }
  .quality-card :deep(.el-card__header), .metrics-dashboard { padding: 16px; }
  .metric-grid { grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr)); }
  .metric-card :deep(.el-card__body) { padding: 16px; }
  .sample-answers, .review-meta-grid { grid-template-columns: 1fr; }
  .review-check-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 480px) {
  .metric-grid, .review-check-grid { grid-template-columns: 1fr; }
}
</style>
