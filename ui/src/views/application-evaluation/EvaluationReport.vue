<template>
  <el-card class="report-card" shadow="never">
    <template #header>
      <div class="report-heading">
        <strong>{{ tr('reportsTab') }} <EvaluationHelp :text="tr('reportsHelp')" /></strong>
        <div class="report-actions">
          <el-select v-model="reportId" filterable :placeholder="tr('selectReport')" :aria-label="tr('selectReport')" class="report-select">
            <el-option v-for="run in reportRuns" :key="run.id" :label="`${run.dataset_name} · ${date(run.created_at)}`" :value="run.id" />
          </el-select>
          <el-button :icon="Refresh" :loading="loading || detailLoading" @click="refresh">{{ tr('refresh') }}</el-button>
          <el-dropdown :disabled="!detail.id" @command="exportReport">
            <el-button type="primary" :disabled="!detail.id">{{ tr('export') }}<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
            <template #dropdown><el-dropdown-menu>
              <el-dropdown-item command="md">{{ tr('exportMarkdown') }}</el-dropdown-item>
              <el-dropdown-item command="json">{{ tr('exportJson') }}</el-dropdown-item>
              <el-dropdown-item command="csv">{{ tr('exportCsv') }}</el-dropdown-item>
            </el-dropdown-menu></template>
          </el-dropdown>
        </div>
      </div>
    </template>
    <el-empty v-if="!reportRuns.length && !loading" :description="tr('noReports')" :image-size="64" />
    <div v-else v-loading="detailLoading" class="report-body">
      <div class="report-meta">
        <span>{{ tr('dataset') }} · <strong>{{ detail.dataset_name || '—' }}</strong></span>
        <span>{{ tr('version') }} · {{ detail.dataset_version?.slice(0, 8) || '—' }}</span>
        <span>{{ tr('date') }} · {{ date(detail.created_at) }}</span>
        <el-tag v-if="detail.status" size="small" :type="detail.status === 'completed' ? 'success' : 'warning'">{{ tr(detail.status) }}</el-tag>
        <el-button link type="primary" :disabled="!detail.id" @click="$emit('view', detail)">{{ tr('viewRunDetail') }}</el-button>
        <el-popover v-if="detail.config?.judge_model" placement="bottom-start" :width="520" trigger="click">
          <template #reference><el-button link type="primary">{{ tr('viewJudgePrompt') }}</el-button></template>
          <pre class="judge-prompt-text">{{ detail.config.judge_prompt || tr('judgePromptLegacy') }}</pre>
        </el-popover>
        <el-tooltip :content="tr(detail.can_replay ? 'rerunAfterFixHint' : 'replayUnavailable')"><span><el-button size="small" :disabled="!detail.can_replay || replayBusy" @click="$emit('replay', detail)">{{ tr('rerunAfterFix') }}</el-button></span></el-tooltip>
      </div>
      <div class="report-kpis">
        <div class="report-kpi"><span>{{ tr('rulePassRate') }} <EvaluationHelp :text="tr('rulePassRateHelp')" /></span><strong>{{ rate(stats.passed, stats.scored) }}</strong><small>{{ stats.passed }} / {{ stats.scored }} {{ tr('scoredCases') }}</small></div>
        <div class="report-kpi"><span>{{ tr('judge_score') }}</span><strong>{{ score(summary.judge_score?.mean) }}</strong><small>{{ tr('coverage') }} · {{ summary.judge_score?.count || 0 }} / {{ stats.total }}</small></div>
        <div class="report-kpi"><span>{{ tr('executionSuccessRate') }}</span><strong>{{ rate(stats.total - stats.errors, stats.total) }}</strong><small>{{ tr('failedCases') }} · {{ stats.errors }}</small></div>
        <div class="report-kpi"><span>{{ tr('responseP90') }}</span><strong>{{ seconds(quantile(responseTimes, 0.9)) }}</strong><small>P50 · {{ seconds(quantile(responseTimes, 0.5)) }}</small></div>
        <div class="report-kpi report-kpi-muted"><span>{{ tr('total_score') }}</span><strong>{{ score(summary.total_score?.mean) }}</strong><small>{{ tr('coverage') }} · {{ summary.total_score?.count || 0 }} / {{ stats.total }}</small></div>
      </div>
      <section v-if="zeroTotal" class="report-panel">
        <h4>{{ tr('zeroTitle') }} · {{ zeroTotal }} / {{ labeledTotal }} <EvaluationHelp :text="tr('zeroHelp')" /></h4>
        <div class="zero-causes">
          <button v-for="cause in zeroCauses" :key="cause.key" type="button" class="zero-cause" @click="areaFilter = 'retrieval'">
            <strong>{{ cause.count }}</strong><span>{{ tr('zero_' + cause.key) }}</span><small>{{ tr('zeroFix_' + cause.key) }}</small>
          </button>
        </div>
        <p v-if="unlabeledTotal" class="zero-note">{{ t('views.applicationEvaluation.ux.zeroUnlabeled', { count: unlabeledTotal }) }}</p>
      </section>
      <section class="report-panel">
        <div class="diagnosis-heading">
          <h4>{{ tr('diagTitle') }} <EvaluationHelp :text="tr('diagHelp')" /></h4>
          <el-radio-group v-model="areaFilter" size="small">
            <el-radio-button value="all">{{ tr('all') }} · {{ diagnosed.length }}</el-radio-button>
            <el-radio-button v-for="area in activeAreas" :key="area" :value="area">{{ tr('area_' + area) }} · {{ areaCounts[area] }}</el-radio-button>
          </el-radio-group>
        </div>
        <div class="diagnosis-layout">
          <EvaluationChart v-if="activeAreas.length" :option="areaOption" height="220px" :label="tr('diagTitle')" @select="areaFilter = activeAreas[$event] || 'all'" />
          <el-table :data="filteredDiagnosed" :row-key="(item: any) => item.key" size="small" :empty-text="tr('diagNoneRun')">
            <el-table-column type="expand" width="40"><template #default="{ row }"><div class="diagnosis-expand">
              <div v-if="row.row.conversation?.history?.length" class="diagnosis-answer"><span>{{ tr('traceHistory') }}</span><p v-for="(turn, i) in row.row.conversation.history" :key="i">{{ i + 1 }}. {{ turn.question }} → {{ turn.answer || '—' }}</p></div>
              <div class="diagnosis-answer"><span>{{ tr('answer') }}</span><p>{{ row.row.answer || '—' }}</p></div>
              <div class="diagnosis-answer"><span>{{ tr('reference') }}</span><p>{{ row.row.ground_truth || '—' }}</p></div>
              <DiagnosisPanel :findings="row.findings" :trace="row.row.trace" :allow-candidate="canCandidate" @candidate="$emit('candidate', { run: detail, finding: $event })" />
            </div></template></el-table-column>
            <el-table-column :label="tr('question')" min-width="240" show-overflow-tooltip><template #default="{ row }">{{ row.row.question }}</template></el-table-column>
            <el-table-column :label="tr('diagPrimary')" width="100"><template #default="{ row }"><el-tag size="small" effect="dark" :type="AREA_TAG[row.findings[0].area]">{{ tr('area_' + row.findings[0].area) }}</el-tag></template></el-table-column>
            <el-table-column :label="tr('diagReason')" min-width="260" show-overflow-tooltip><template #default="{ row }">{{ t(`views.applicationEvaluation.ux.${row.findings[0].key}`, row.findings[0].params) }}<span v-if="row.findings.length > 1" class="diagnosis-more"> +{{ row.findings.length - 1 }}</span></template></el-table-column>
            <el-table-column :label="tr('total_score')" width="110" align="right"><template #default="{ row }">{{ score(row.row.total_score) }}</template></el-table-column>
            <el-table-column :label="tr('judge_score')" width="110" align="right"><template #default="{ row }">{{ score(row.row.scores?.judge_score) }}</template></el-table-column>
          </el-table>
        </div>
      </section>
      <div class="report-charts">
        <section class="report-panel"><h4>{{ tr('scoreDistribution') }}</h4><EvaluationChart :option="distributionOption" :label="tr('scoreDistribution')" /></section>
        <section class="report-panel"><h4>{{ tr('issueDistribution') }}</h4><EvaluationChart :option="issueOption" :label="tr('issueDistribution')" /></section>
        <section class="report-panel"><h4>{{ tr('metricMeans') }}</h4><EvaluationChart :option="metricOption" :height="`${Math.max(220, metricRows.length * 34 + 40)}px`" :label="tr('metricMeans')" /></section>
        <section class="report-panel"><h4>{{ tr('responseDistribution') }}</h4><EvaluationChart :option="responseOption" :label="tr('responseDistribution')" /></section>
        <section v-if="categoryRows.length > 1" class="report-panel report-panel-wide"><h4>{{ tr('categoryScores') }}</h4><EvaluationChart :option="categoryOption" :label="tr('categoryScores')" /></section>
      </div>
      <section class="report-panel">
        <h4>{{ tr('statisticsTable') }}</h4>
        <el-table :data="metricRows" size="small">
          <el-table-column prop="label" :label="tr('metric')" min-width="180" />
          <el-table-column :label="tr('mean')" align="right"><template #default="{ row }">{{ score(row.mean) }}</template></el-table-column>
          <el-table-column :label="tr('median')" align="right"><template #default="{ row }">{{ score(row.median) }}</template></el-table-column>
          <el-table-column :label="tr('min')" align="right"><template #default="{ row }">{{ score(row.min) }}</template></el-table-column>
          <el-table-column :label="tr('max')" align="right"><template #default="{ row }">{{ score(row.max) }}</template></el-table-column>
          <el-table-column :label="tr('stdDev')" align="right"><template #default="{ row }">{{ score(row.std) }}</template></el-table-column>
          <el-table-column :label="tr('coverage')" align="right"><template #default="{ row }">{{ row.count }} / {{ stats.total }}</template></el-table-column>
        </el-table>
      </section>
    </div>
  </el-card>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { ArrowDown, Refresh } from '@element-plus/icons-vue'
import EvaluationHelp from './EvaluationHelp.vue'
import EvaluationChart from './EvaluationChart.vue'
import DiagnosisPanel from './DiagnosisPanel.vue'
import { AREA_TAG, DIAGNOSIS_AREAS, diagnoseResult, retrievalZeroCause } from './diagnosis'
import { useEvaluationNavigation } from './useEvaluationNavigation'
import { downloadEvaluationReport, getEvaluationRun } from '@/api/application/evaluation'

const props = defineProps<{ applicationId: string; runs: any[]; loading: boolean; replayBusy?: boolean }>()
const emit = defineEmits<{ refresh: []; view: [row: any]; replay: [row: any]; candidate: [payload: { run: any; finding: any }] }>()
const { t, te } = useI18n()
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
const PASS_THRESHOLD = 0.6
const SERIES = ['#2a78d6', '#eb6834']
const STATUS = { passed: '#0ca30c', low: '#fab219', judgeError: '#ec835a', error: '#d03b3b', unscored: '#a8abb2' }
const issueLabels: Record<string, string> = { passed: 'passed', low: 'lowScore', unscored: 'unscored', judgeError: 'judgeFailed', error: 'hasError' }
const AXIS = { axisLine: { lineStyle: { color: '#dee0e3' } }, axisTick: { show: false }, axisLabel: { color: '#646a73' } }
const SPLIT = { splitLine: { lineStyle: { color: '#eff0f1' } } }
const reportRuns = computed(() => props.runs.filter(run => ['completed', 'partial'].includes(run.status)))
const reportId = useEvaluationNavigation('report', () => reportRuns.value.map(run => run.id), '')
const detail = ref<any>({})
const detailLoading = ref(false)
const summary = computed(() => detail.value.summary || {})
const results = computed<any[]>(() => detail.value.results || [])
const date = (value: string) => value ? new Date(value).toLocaleString() : '—'
const score = (value: any) => value == null ? '—' : `${(Number(value) * 100).toFixed(1)}%`
const rate = (part: number, whole: number) => whole ? `${(part / whole * 100).toFixed(1)}%` : '—'
const seconds = (value: any) => value == null ? '—' : `${Number(value).toFixed(2)} s`
const metricName = (name: string) => te(`views.applicationEvaluation.ux.${name}`) ? tr(name) : name
const quantile = (values: number[], q: number) => {
  if (!values.length) return null
  const sorted = [...values].sort((a, b) => a - b)
  const index = (sorted.length - 1) * q
  const low = Math.floor(index)
  return sorted[low] + (sorted[Math.ceil(index)] - sorted[low]) * (index - low)
}
const issueOf = (row: any) => {
  if (row.error) return 'error'
  if (Object.keys(row.metric_errors || {}).length) return 'judgeError'
  if (row.total_score == null) return 'unscored'
  return Number(row.total_score) < PASS_THRESHOLD ? 'low' : 'passed'
}
const stats = computed(() => {
  const issues = results.value.map(issueOf)
  const scored = results.value.filter(row => row.total_score != null)
  return { total: results.value.length, scored: scored.length, passed: scored.filter(row => !row.error && Number(row.total_score) >= PASS_THRESHOLD).length, errors: issues.filter(item => item === 'error').length }
})
const responseTimes = computed(() => results.value.map(row => row.response_time).filter(value => value != null).map(Number))
const valuesOf = (name: string) => results.value.map(row => name === 'total_score' ? row.total_score : row.scores?.[name]).filter(value => value != null).map(Number)
const metricRows = computed(() => Object.keys(summary.value).filter(name => name !== 'response_time').map(name => {
  const values = valuesOf(name)
  const mean = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
  return {
    name, label: metricName(name), mean, count: values.length, median: quantile(values, 0.5),
    min: values.length ? Math.min(...values) : null, max: values.length ? Math.max(...values) : null,
    std: mean == null ? null : Math.sqrt(values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length),
  }
}))
const categoryRows = computed(() => Object.entries(detail.value.report?.groups || {}).filter(([key]) => key.startsWith('category:')).map(([key, value]: [string, any]) => ({ name: key.slice(9), total: value.total_score?.mean, judge: value.judge_score?.mean, count: value.total_score?.total || 0 })))
const diagnosed = computed(() => results.value.map((row, index) => ({ key: row.id ?? index, row, findings: diagnoseResult(row) })).filter(item => item.findings.length))
const areaCounts = computed(() => Object.fromEntries(DIAGNOSIS_AREAS.map(area => [area, diagnosed.value.filter(item => item.findings[0].area === area).length])) as Record<string, number>)
const activeAreas = computed(() => DIAGNOSIS_AREAS.filter(area => areaCounts.value[area]))
const areaFilter = ref('all')
const labeledTotal = computed(() => results.value.filter(row => row.relevant_doc_ids?.length).length)
const unlabeledTotal = computed(() => results.value.length - labeledTotal.value)
const zeroCauses = computed(() => (['skipped', 'empty', 'mismatch', 'stale'] as const).map(key => ({ key, count: results.value.filter(row => retrievalZeroCause(row) === key).length })).filter(cause => cause.count))
const zeroTotal = computed(() => zeroCauses.value.reduce((sum, cause) => sum + cause.count, 0))
const filteredDiagnosed = computed(() => areaFilter.value === 'all' ? diagnosed.value : diagnosed.value.filter(item => item.findings[0].area === areaFilter.value))
const canCandidate = computed(() => detail.value.status === 'completed' && !!detail.value.can_replay)
const areaOption = computed(() => ({
  grid: { left: 64, right: 40, top: 8, bottom: 8 },
  tooltip: tooltip((params: any) => `${params[0].name}: ${params[0].value} ${tr('questions')}`),
  xAxis: { type: 'value', show: false },
  yAxis: { type: 'category', inverse: true, data: activeAreas.value.map(area => tr('area_' + area)), ...AXIS },
  series: [{ type: 'bar', barMaxWidth: 18, cursor: 'pointer', itemStyle: { color: SERIES[0], borderRadius: [0, 4, 4, 0] }, data: activeAreas.value.map(area => areaCounts.value[area]), label: { show: true, position: 'right', color: '#1f2329' } }],
}))
const tooltip = (formatter: (params: any) => string, trigger = 'axis') => ({ trigger, axisPointer: { type: 'shadow' }, confine: true, formatter })
const percentAxis = { type: 'value', min: 0, max: 100, axisLabel: { color: '#646a73', formatter: '{value}%' }, ...SPLIT }
const bar = (color: string) => ({ type: 'bar', barMaxWidth: 24, barGap: '10%', itemStyle: { color, borderRadius: [4, 4, 0, 0] }, emphasis: { focus: 'series' } })
const buckets = ['0–20%', '20–40%', '40–60%', '60–80%', '80–100%']
const histogram = (values: number[]) => buckets.map((_, index) => values.filter(value => Math.min(4, Math.floor(value * 5)) === index).length)
const distributionOption = computed(() => {
  const series = [{ name: tr('total_score'), values: valuesOf('total_score') }, { name: tr('judge_score'), values: valuesOf('judge_score') }].filter(item => item.values.length)
  return {
    grid: { left: 40, right: 16, top: 36, bottom: 28 },
    legend: { show: series.length > 1, top: 0, textStyle: { color: '#646a73' } },
    tooltip: tooltip((params: any) => `${params[0].axisValue}<br/>${params.map((item: any) => `${item.marker}${item.seriesName}: ${item.value} ${tr('questions')}`).join('<br/>')}`),
    xAxis: { type: 'category', data: buckets, ...AXIS },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { color: '#646a73' }, ...SPLIT },
    series: series.map((item, index) => ({ ...bar(SERIES[index]), name: item.name, data: histogram(item.values) })),
  }
})
const issueOption = computed(() => {
  const keys = ['passed', 'low', 'unscored', 'judgeError', 'error'] as const
  const counts = keys.map(key => results.value.filter(row => issueOf(row) === key).length)
  return {
    grid: { left: 96, right: 48, top: 8, bottom: 8 },
    tooltip: tooltip((params: any) => `${params[0].name}: ${params[0].value} (${rate(params[0].value, stats.value.total)})`),
    xAxis: { type: 'value', show: false },
    yAxis: { type: 'category', inverse: true, data: keys.map(key => tr(issueLabels[key])), ...AXIS },
    series: [{ type: 'bar', barMaxWidth: 20, data: counts.map((value, index) => ({ value, itemStyle: { color: STATUS[keys[index]], borderRadius: [0, 4, 4, 0] } })), label: { show: true, position: 'right', color: '#1f2329' } }],
  }
})
const metricOption = computed(() => ({
  grid: { left: 150, right: 56, top: 8, bottom: 24 },
  tooltip: tooltip((params: any) => { const row = metricRows.value[params[0].dataIndex]; return `${row.label}: ${score(row.mean)}<br/>${tr('coverage')}: ${row.count} / ${stats.value.total}` }),
  xAxis: percentAxis,
  yAxis: { type: 'category', inverse: true, data: metricRows.value.map(row => row.label), ...AXIS },
  series: [{ type: 'bar', barMaxWidth: 16, itemStyle: { color: SERIES[0], borderRadius: [0, 4, 4, 0] }, data: metricRows.value.map(row => row.mean == null ? null : +(row.mean * 100).toFixed(1)), label: { show: true, position: 'right', color: '#1f2329', formatter: (item: any) => item.value == null ? '—' : `${item.value}%` } }],
}))
const responseBuckets = [[0, 1, '<1s'], [1, 3, '1–3s'], [3, 5, '3–5s'], [5, 10, '5–10s'], [10, 30, '10–30s'], [30, Infinity, '≥30s']] as const
const responseOption = computed(() => ({
  grid: { left: 40, right: 16, top: 16, bottom: 28 },
  tooltip: tooltip((params: any) => `${params[0].axisValue}: ${params[0].value} ${tr('questions')}`),
  xAxis: { type: 'category', data: responseBuckets.map(item => item[2]), ...AXIS },
  yAxis: { type: 'value', minInterval: 1, axisLabel: { color: '#646a73' }, ...SPLIT },
  series: [{ ...bar(SERIES[0]), data: responseBuckets.map(([low, high]) => responseTimes.value.filter(value => value >= low && value < high).length) }],
}))
const categoryOption = computed(() => {
  const hasJudge = categoryRows.value.some(row => row.judge != null)
  return {
    grid: { left: 48, right: 16, top: 36, bottom: 28 },
    legend: { show: hasJudge, top: 0, textStyle: { color: '#646a73' } },
    tooltip: tooltip((params: any) => `${params[0].axisValue} (${categoryRows.value[params[0].dataIndex].count} ${tr('questions')})<br/>${params.map((item: any) => `${item.marker}${item.seriesName}: ${item.value == null ? '—' : `${item.value}%`}`).join('<br/>')}`),
    xAxis: { type: 'category', data: categoryRows.value.map(row => row.name), ...AXIS },
    yAxis: percentAxis,
    series: [
      { ...bar(SERIES[0]), name: tr('total_score'), data: categoryRows.value.map(row => row.total == null ? null : +(row.total * 100).toFixed(1)) },
      ...(hasJudge ? [{ ...bar(SERIES[1]), name: tr('judge_score'), data: categoryRows.value.map(row => row.judge == null ? null : +(row.judge * 100).toFixed(1)) }] : []),
    ],
  }
})
const loadDetail = async () => {
  const run = reportRuns.value.find(item => item.id === reportId.value) || reportRuns.value[0]
  if (!run) { detail.value = {}; return }
  if (detail.value.id === run.id && detail.value.results) return
  detail.value = run
  detailLoading.value = true
  try { detail.value = (await getEvaluationRun(props.applicationId, run.id)).data } finally { detailLoading.value = false }
}
const refresh = () => {
  detail.value = {}
  emit('refresh')
  void loadDetail()
}
watch(() => [reportId.value, reportRuns.value.map(run => run.id).join()], loadDetail, { immediate: true })
watch(() => detail.value.id, () => { areaFilter.value = 'all' })
const saveBlob = (blob: Blob, name: string) => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
const csvCell = (value: any) => `"${String(value ?? '').replace(/"/g, '""')}"`
const exportReport = async (format: string) => {
  const run = detail.value
  if (format === 'csv') {
    const metrics = metricRows.value.map(row => row.name).filter(name => name !== 'total_score')
    const header = ['id', 'category', 'question', 'ground_truth', 'answer', 'total_score', ...metrics, 'response_time', 'status', 'error']
    const lines = results.value.map(row => [row.id, row.category, row.question, row.ground_truth, row.answer, row.total_score, ...metrics.map(name => row.scores?.[name]), row.response_time, issueOf(row), row.error || (Object.keys(row.metric_errors || {}).length ? JSON.stringify(row.metric_errors) : '')].map(csvCell).join(','))
    return saveBlob(new Blob(['﻿' + [header.join(','), ...lines].join('\n')], { type: 'text/csv' }), `evaluation-${run.id}.csv`)
  }
  try {
    const response = await downloadEvaluationReport(props.applicationId, run.id, format as 'md' | 'json')
    if (!response.ok) throw new Error(tr('downloadFailed'))
    saveBlob(await response.blob(), `evaluation-${run.id}.${format}`)
  } catch {
    ElMessage.error(tr('downloadFailed'))
  }
}
</script>
<style scoped>
.report-card { border-radius: 10px; border-color: var(--el-border-color-lighter); }
.report-heading, .report-actions, .report-meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.report-heading { justify-content: space-between; }
.report-select { width: 320px; }
.report-body { display: flex; flex-direction: column; gap: 16px; min-height: 200px; }
.report-meta { color: var(--el-text-color-secondary); font-size: 13px; }
.report-meta strong { color: var(--el-text-color-primary); }
.report-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.report-kpi { display: flex; flex-direction: column; gap: 4px; padding: 14px 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.report-kpi span, .report-kpi small { color: var(--el-text-color-secondary); font-size: 12px; }
.report-kpi strong { color: var(--el-text-color-primary); font-size: 22px; line-height: 1.3; }
.report-kpi-muted { background: var(--el-fill-color-lighter); }
.report-charts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.report-panel { min-width: 0; padding: 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.report-panel h4 { margin: 0 0 12px; font-size: 14px; }
.judge-prompt-text { margin: 0; max-height: 320px; overflow: auto; font-family: inherit; font-size: 13px; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
.report-panel-wide { grid-column: 1 / -1; }
.diagnosis-heading { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; }
.diagnosis-heading h4 { margin: 0; }
.diagnosis-layout { display: grid; grid-template-columns: minmax(220px, 280px) minmax(0, 1fr); gap: 16px; align-items: start; }
.diagnosis-layout > .el-table:only-child { grid-column: 1 / -1; }
.diagnosis-expand { display: flex; flex-direction: column; gap: 12px; padding: 12px 16px 16px 48px; }
.diagnosis-answer span { color: var(--el-text-color-secondary); font-size: 12px; }
.diagnosis-answer p { margin: 4px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; }
.diagnosis-more { color: var(--el-text-color-secondary); font-size: 12px; }
@media (max-width: 1024px) {
  .report-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .report-charts, .diagnosis-layout { grid-template-columns: 1fr; }
}
.zero-causes { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.zero-cause { display: flex; flex-direction: column; gap: 4px; padding: 12px 14px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; background: var(--el-bg-color); text-align: left; cursor: pointer; }
.zero-cause:hover, .zero-cause:focus-visible { border-color: var(--el-color-primary); }
.zero-cause strong { color: var(--el-text-color-primary); font-size: 20px; }
.zero-cause span { color: var(--el-text-color-primary); font-size: 13px; }
.zero-cause small { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.zero-note { margin: 10px 0 0; color: var(--el-text-color-secondary); font-size: 12px; }
</style>
