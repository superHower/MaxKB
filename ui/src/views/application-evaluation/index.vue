<template>
  <div class="evaluation-page p-16">
    <template v-if="mode === 'evaluation'">
    <section class="page-hero">
      <div>
        <div class="eyebrow">{{ tr('evaluationLabel') }}</div>
        <h2>{{ tr('title') }}</h2>
        <el-text type="info">{{ tr('intro') }}</el-text>
      </div>
      <el-button type="primary" size="large" :disabled="!datasets.length || busy" @click="openRun()">
        {{ tr('start') }}
      </el-button>
    </section>
    <div class="summary-grid">
      <div class="summary-item">
        <el-text type="info">{{ tr('latestScore') }}</el-text>
        <strong>{{ latestScore }}</strong>
        <span>{{ latestRun ? date(latestRun.created_at) : tr('noRuns') }}</span>
      </div>
      <div class="summary-item">
        <el-text type="info">{{ tr('datasetsSummary') }}</el-text>
        <strong>{{ datasets.length }}</strong>
        <span>{{ tr('dataset') }}</span>
      </div>
      <div class="summary-item">
        <el-text type="info">{{ tr('completedSummary') }}</el-text>
        <strong>{{ completedRuns }}</strong>
        <span>{{ tr('completed') }}</span>
      </div>
      <div class="summary-item" :class="{ active: busy }">
        <el-text type="info">{{ tr('currentStatus') }}</el-text>
        <strong>{{ busy ? tr('running') : tr('ready') }}</strong>
        <span>{{ busy ? tr('progressHint') : tr('readyHint') }}</span>
      </div>
    </div>
    <el-alert class="capability-alert" :title="tr('capability')" type="info" :closable="false" />
    <div class="workspace-grid">
    <el-card class="content-card">
      <template #header
        ><div class="flex justify-between align-center">
          <strong>{{ tr('datasetSection') }}</strong>
          <div class="section-actions">
            <el-button @click="templateFile">{{ tr('template') }}</el-button
            ><el-button type="primary" plain @click="openDatasetDialog">{{
              tr('add')
            }}</el-button>
          </div>
        </div></template
      >
      <el-empty v-if="!datasets.length && !loading" :description="tr('empty')"
        ><el-button type="primary" @click="openDatasetDialog">{{
          tr('add')
        }}</el-button></el-empty
      >
      <el-table v-else :data="datasets" v-loading="loading" class="dataset-table">
        <el-table-column :label="tr('dataset')" min-width="320"><template #default="{ row }"><div class="dataset-name-cell"><strong>{{ row.name }}</strong></div></template></el-table-column><el-table-column
          prop="count"
          :label="tr('cases')"
          width="92"
        />
        <el-table-column :label="tr('version')" width="145"
          ><template #default="{ row }"
            ><el-tooltip :content="row.version"><el-tag size="small" effect="plain">{{ row.version.slice(0, 8) }}</el-tag></el-tooltip
            ></template
          ></el-table-column
        >
        <el-table-column :label="tr('date')" width="180"
          ><template #default="{ row }">{{ date(row.created_at) }}</template></el-table-column
        >
        <el-table-column :label="tr('actions')" width="300"
          ><template #default="{ row }"
            ><el-button native-type="button" link @click.prevent.stop="showDataset(row)">{{ tr('datasetView') }}</el-button>
            <el-button native-type="button" link @click.prevent.stop="editDataset(row)">{{ tr('edit') }}</el-button>
            <el-button native-type="button" link type="danger" @click.prevent.stop="removeDataset(row)">{{ tr('delete') }}</el-button>
            <el-button link type="primary" :disabled="busy" @click="openRun(row.id)">{{
              tr('use')
            }}</el-button></template
          ></el-table-column
        >
      </el-table>
    </el-card>
    <el-dialog v-model="datasetDialog" :title="tr('add')" width="720px" class="dataset-dialog" @closed="resetDatasetForm">
      <div class="dialog-intro"><div class="eyebrow">{{ tr('datasetSection') }}</div><p>{{ tr('datasetDialogHint') }}</p></div>
      <el-form label-position="top" class="dataset-form">
        <el-form-item :label="tr('name')"
          ><el-input v-model="datasetName" maxlength="128" :placeholder="tr('nameHint')"
        /></el-form-item>
        <el-radio-group v-model="entryMode" class="entry-mode mb-16"
          ><el-radio-button value="manual">{{ tr('manual') }}</el-radio-button
          ><el-radio-button value="file">{{ tr('import') }}</el-radio-button></el-radio-group
        >
        <template v-if="entryMode === 'manual'">
          <div class="manual-hint"><el-icon><InfoFilled /></el-icon><span>{{ tr('manualHint') }}</span><strong>{{ questions.length }} / 1000</strong></div>
          <div v-for="(item, index) in questions" :key="index" class="question-editor">
            <div class="flex justify-between">
              <strong>{{ tr('question') }} {{ index + 1 }}</strong
              ><el-button
                link
                type="danger"
                :disabled="questions.length === 1"
                @click="questions.splice(index, 1)"
                >{{ tr('remove') }}</el-button
              >
            </div>
            <el-input
              v-model="item.question"
              type="textarea"
              :rows="2"
              :placeholder="tr('question')"
              class="mb-8"
            />
            <el-input
              v-model="item.ground_truth"
              type="textarea"
              :rows="2"
              :placeholder="tr('reference')"
            />
          </div>
          <el-button class="add-question-button"
            :disabled="questions.length >= 1000"
            @click="questions.push({ question: '', ground_truth: '' })"
            >{{ tr('addQuestion') }}</el-button
          >
        </template>
        <template v-else>
          <el-alert :title="tr('fileHint')" type="info" :closable="false" class="mb-16 file-hint" />
          <el-button link type="primary" @click="templateFile">{{ tr('template') }}</el-button>
          <el-upload
            v-model:file-list="files"
            :auto-upload="false"
            :limit="1"
            accept=".json,.csv"
            :on-exceed="fileExceeded"
            ><el-button>{{ tr('chooseFile') }}</el-button></el-upload
          >
        </template>
      </el-form>
      <template #footer
        ><el-button @click="datasetDialog = false">{{ tr('cancel') }}</el-button
        ><el-button type="primary" :loading="submitting" @click="importDataset">{{
          tr('save')
        }}</el-button></template
      >
    </el-dialog>
    <el-dialog v-model="runDialog" :title="tr('configureDataset')" width="560px">
      <el-alert :title="tr('published')" type="warning" :closable="false" class="mb-16" />
      <el-form label-position="top"
        ><el-form-item :label="tr('dataset')"
          ><el-select v-model="datasetId" class="w-full"
            ><el-option
              v-for="item in datasets"
              :key="item.id"
              :label="`${item.name} (${item.count})`"
              :value="item.id" /></el-select></el-form-item
      ></el-form>
      <el-form label-position="top">
        <el-form-item :label="tr('judgeModel')"><el-select v-model="judgeModelId" clearable class="w-full"><el-option v-for="model in models.filter(m => m.model_type === 'LLM')" :key="model.id" :label="model.name" :value="model.id" /></el-select></el-form-item>
        <el-form-item v-if="judgeModelId" :label="tr('embeddingModel')" required><el-select v-model="embeddingModelId" class="w-full"><el-option v-for="model in models.filter(m => m.model_type === 'EMBEDDING')" :key="model.id" :label="model.name" :value="model.id" /></el-select></el-form-item>
        <el-form-item :label="tr('baseline')"><el-select v-model="baselineId" clearable class="w-full"><el-option v-for="run in availableBaselines" :key="run.id" :label="`${run.dataset_name} · ${date(run.created_at)}`" :value="run.id" /></el-select></el-form-item>
        <el-form-item :label="tr('regression')"><el-switch v-model="regression" /></el-form-item>
        <el-form-item v-if="regression" :label="tr('regressionThreshold')"><el-input-number v-model="regressionThreshold" :min="0.01" :max="1" :step="0.01" :precision="2" /></el-form-item>
      </el-form>
      <p>{{ tr(judgeModelId ? 'judgeMode' : 'mode') }}</p>
      <el-alert :title="tr('capability')" type="info" :closable="false" />
      <p>{{ tr('runHint') }}</p>
      <template #footer
        ><el-button @click="runDialog = false">{{ tr('cancel') }}</el-button
        ><el-button
          type="primary"
          :loading="submitting"
          :disabled="!datasetId || busy"
          @click="start"
          >{{ tr('start') }}</el-button
        ></template
      >
    </el-dialog>
    <el-drawer v-model="datasetDetailVisible" size="72%" :title="tr('datasetDetail')" class="evaluation-drawer dataset-drawer">
      <div v-loading="datasetDetailLoading" class="dataset-detail">
        <div class="detail-heading">
          <div><div class="eyebrow">{{ tr('datasetPreview') }}</div><h3>{{ datasetDetail.name || '—' }}</h3><p>{{ tr('datasetDetailHint') }}</p></div>
          <div class="detail-actions"><el-button plain @click="editDataset(datasetDetail)">{{ tr('edit') }}</el-button><el-button type="primary" plain :disabled="busy" @click="openRun(datasetDetail.id)">{{ tr('use') }}</el-button></div>
        </div>
        <div class="dataset-meta">
          <div><span>{{ tr('cases') }}</span><strong>{{ datasetDetail.cases?.length || 0 }}</strong></div>
          <div><span>{{ tr('version') }}</span><strong>{{ datasetDetail.version?.slice(0, 8) || '—' }}</strong></div>
          <div><span>{{ tr('date') }}</span><strong>{{ date(datasetDetail.created_at) }}</strong></div>
        </div>
        <div class="table-toolbar"><div><strong>{{ tr('caseList') }}</strong><el-text type="info">{{ filteredDatasetCases.length }} / {{ datasetDetail.cases?.length || 0 }}</el-text></div><el-input v-model="datasetSearch" clearable :placeholder="tr('searchDataset')" class="toolbar-search" /></div>
        <el-table :data="filteredDatasetCases" row-key="id" class="detail-table">
          <el-table-column type="index" width="60" />
          <el-table-column prop="category" :label="tr('category')" width="130"><template #default="{ row }"><el-tag v-if="row.category" size="small" effect="plain">{{ row.category }}</el-tag><span v-else>—</span></template></el-table-column>
          <el-table-column prop="question" :label="tr('question')" min-width="260" show-overflow-tooltip />
          <el-table-column :label="tr('reference')" min-width="280"><template #default="{ row }"><div class="clamp-text">{{ row.ground_truth || '—' }}</div></template></el-table-column>
          <el-table-column :label="tr('relatedDocs')" width="120"><template #default="{ row }">{{ row.relevant_doc_ids?.length || 0 }}</template></el-table-column>
        </el-table>
      </div>
    </el-drawer>
    <el-drawer v-model="detailVisible" size="min(1280px, 100vw)" :title="tr('detail')" class="evaluation-drawer run-drawer">
      <div v-loading="detailLoading" class="run-result">
        <div class="run-overview">
        <div class="detail-heading run-heading">
          <div><h3>{{ detail.dataset_name || '—' }}</h3><p>{{ tr('date') }} · {{ date(detail.created_at) }}</p></div>
          <div class="run-heading-meta"><el-tag :type="statusType(detail.status)" effect="light">{{ status(detail.status) }}</el-tag><el-tag type="info" effect="plain">{{ tr('version') }} · {{ detail.dataset_version?.slice(0, 8) || '—' }}</el-tag></div>
        </div>
        <el-alert
          v-if="detail.error"
          :title="detail.error"
          type="error"
          :closable="false"
          class="mb-16"
        />
        <div class="run-progress"><div><span>{{ tr('progress') }}</span><strong>{{ detail.completed || 0 }} / {{ detail.total || 0 }} {{ tr('questions') }}</strong></div><el-progress :percentage="percentage(detail)" :stroke-width="8" /></div>
        <div class="result-stat-grid"><div class="result-stat result-stat-primary"><span>{{ tr('score') }}</span><strong>{{ score(detail.summary?.total_score?.mean) }}</strong></div><div class="result-stat"><span>{{ tr('avgResponseTime') }}</span><strong>{{ formatSeconds(detail.summary?.response_time?.mean) }}</strong></div><div class="result-stat"><span>{{ tr('scoredCases') }}</span><strong>{{ detail.summary?.total_score?.count || 0 }} <small>/ {{ detail.completed || 0 }}</small></strong></div><div class="result-stat" :class="{ 'result-stat-error': failedCases > 0 }"><span>{{ tr('failedCases') }}</span><strong>{{ failedCases }}</strong></div></div>
        <p class="run-score-hint"><el-icon><InfoFilled /></el-icon>{{ tr('scoreHint') }}</p>
        <el-collapse v-if="metrics.length" class="run-metrics">
          <el-collapse-item :title="tr('metricDetails')" name="metrics">
            <div class="metric-strip"><div v-for="row in metrics" :key="row.name" class="metric-chip"><span>{{ row.label }}</span><strong>{{ row.name === 'response_time' ? formatSeconds(row.mean) : score(row.mean) }}</strong><small>{{ tr('scoredCases') }} · {{ row.count || 0 }} / {{ row.total || detail.completed || 0 }}</small></div></div>
          </el-collapse-item>
        </el-collapse>
        </div>
        <section class="run-answers">
        <div class="table-toolbar results-toolbar"><div><strong>{{ tr('answers') }}</strong><el-tag type="info" effect="plain" round>{{ filteredResults.length }} / {{ detail.results?.length || 0 }}</el-tag></div><el-input v-model="search" clearable :placeholder="tr('search')" :prefix-icon="Search" class="toolbar-search" :aria-label="tr('search')" /></div>
        <div class="results-filter-row"><el-radio-group v-model="resultFilter" size="small" :aria-label="tr('status')"><el-radio-button value="all">{{ tr('all') }}</el-radio-button><el-radio-button value="low">{{ tr('lowScore') }}</el-radio-button><el-radio-button value="unscored">{{ tr('unscored') }}</el-radio-button><el-radio-button value="error">{{ tr('hasError') }}</el-radio-button></el-radio-group><span class="table-hint">{{ tr('expandHint') }}</span></div>
        <el-table :data="filteredResults" :empty-text="tr('waiting')" row-key="id" class="run-results-table">
          <el-table-column type="expand" width="44">
            <template #default="{ row }">
              <div class="result-expanded">
                <div class="result-question"><span>{{ tr('question') }}</span><p>{{ row.question }}</p></div>
                <div class="answer-comparison">
                  <section class="answer-panel"><h4>{{ tr('answer') }}</h4><p class="answer-text">{{ row.answer || '—' }}</p></section>
                  <section class="answer-panel reference-panel"><h4>{{ tr('reference') }}</h4><p class="answer-text">{{ row.ground_truth || '—' }}</p></section>
                </div>
                <div v-if="Object.keys(row.scores || {}).length" class="result-scores"><el-tag v-for="(value, name) in row.scores" :key="name" type="info" effect="plain">{{ metricName(String(name)) }} <strong>{{ score(value) }}</strong></el-tag></div>
                <el-alert v-if="row.error || Object.keys(row.metric_errors || {}).length" :title="row.error || JSON.stringify(row.metric_errors)" type="error" :closable="false" />
                <el-collapse v-if="row.contexts?.length || Object.keys(row.node_details || {}).length" class="result-evidence">
                  <el-collapse-item v-if="row.contexts?.length" name="retrieval">
                    <template #title><span>{{ tr('retrievedEvidence') }}</span><el-tag size="small" type="info" effect="plain" round>{{ row.contexts.length }}</el-tag></template>
                    <article v-for="(context, index) in row.contexts" :key="index" class="evidence-item"><div class="evidence-item-heading"><el-tag size="small" type="info" effect="plain">{{ index + 1 }}</el-tag><strong>{{ context.document_name || context.title || context.id || '—' }}</strong></div><p>{{ context.content || context.title || context.id || '—' }}</p></article>
                  </el-collapse-item>
                  <el-collapse-item v-if="Object.keys(row.node_details || {}).length" :title="tr('nodeEvidence')" name="nodes"><pre class="eval-code">{{ JSON.stringify(row.node_details, null, 2) }}</pre></el-collapse-item>
                </el-collapse>
              </div>
            </template>
          </el-table-column>
          <el-table-column type="index" :label="tr('caseNumber')" width="68" />
          <el-table-column prop="question" :label="tr('question')" min-width="260"><template #default="{ row }"><div class="result-question-cell">{{ row.question }}</div></template></el-table-column>
          <el-table-column :label="tr('status')" width="112"><template #default="{ row }"><el-tag size="small" :type="row.error || Object.keys(row.metric_errors || {}).length ? 'danger' : row.total_score == null ? 'info' : 'success'">{{ row.error || Object.keys(row.metric_errors || {}).length ? tr('hasError') : row.total_score == null ? tr('unscored') : tr('scored') }}</el-tag></template></el-table-column>
          <el-table-column :label="tr('score')" width="136" align="right"><template #default="{ row }"><span class="result-score" :class="{ 'is-low': row.total_score != null && Number(row.total_score) < 0.6 }">{{ score(row.total_score) }}</span></template></el-table-column>
          <el-table-column :label="tr('responseTime')" width="124" align="right"><template #default="{ row }">{{ formatSeconds(row.response_time) }}</template></el-table-column>
        </el-table>
        </section>
        <el-collapse class="run-technical">
          <el-collapse-item :title="tr('runInformation')" name="snapshot">
        <div v-if="detail.config?.capabilities" class="capability-strip">
          <span class="capability-label">{{ tr('capabilitySnapshot') }}</span>
          <el-tag size="small" :type="detail.config.capabilities.memory_enabled ? 'success' : 'info'">{{ detail.config.capabilities.memory_enabled ? tr('memoryEnabled') : tr('memoryDisabled') }}</el-tag>
          <el-tag size="small" :type="detail.config.capabilities.skill_bound ? 'success' : 'info'">{{ detail.config.capabilities.skill_bound ? `${tr('skillsBound')} ${detail.config.capabilities.skill_ids.length}` : tr('noSkills') }}</el-tag>
          <el-tag v-if="detail.config.capabilities.business_branches?.length" size="small" type="warning">{{ tr('businessBranchesConfigured') }}</el-tag>
          <el-text type="info">{{ tr('businessBranchHint') }}</el-text>
        </div>
        <el-descriptions v-if="detail.config?.dataset_snapshot" :column="1" border class="snapshot-descriptions">
          <el-descriptions-item :label="tr('datasetSnapshot')">{{ detail.config.dataset_snapshot.name }} · {{ detail.config.dataset_snapshot.version?.slice(0, 8) }}</el-descriptions-item>
          <el-descriptions-item :label="tr('applicationVersion')">{{ detail.config.application_version?.slice(0, 8) || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="tr('resourceHash')">{{ detail.config.resource_snapshot?.workflow_sha256?.slice(0, 12) || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="tr('promptHash')">{{ detail.config.resource_snapshot?.prompt_sha256?.slice(0, 12) || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="tr('resourceModels')"><span class="resource-ids">{{ detail.config.resource_snapshot?.model_ids?.join(', ') || '—' }}</span></el-descriptions-item>
          <el-descriptions-item :label="tr('resourceKnowledge')"><span class="resource-ids">{{ detail.config.resource_snapshot?.knowledge_ids?.join(', ') || '—' }}</span></el-descriptions-item>
          <el-descriptions-item :label="tr('resourceSkills')">
            <div v-for="(skill, skillId) in detail.config.resource_snapshot?.skills || {}" :key="skillId">{{ skill.name }} · {{ skill.version || '—' }}</div>
            <span v-if="!detail.config.resource_snapshot?.skill_ids?.length">—</span>
          </el-descriptions-item>
          <el-descriptions-item :label="tr('resourceTools')"><span class="resource-ids">{{ detail.config.resource_snapshot?.tool_ids?.join(', ') || '—' }}</span></el-descriptions-item>
        </el-descriptions>
          </el-collapse-item>
          <el-collapse-item :title="tr('technical')" name="technical"><pre class="eval-code">{{ JSON.stringify(detail, null, 2) }}</pre></el-collapse-item>
        </el-collapse>
      </div>
    </el-drawer>
    </div>
    </template>
    <QualityPanel :application-id="id" :runs="runs" :history-loading="loading" :on-refresh="load" :on-view="showRun" :on-export="download" :on-replay="replayRun" :replay-busy="busy || submitting" :visible-tabs="visibleTabs" />
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type UploadUserFile } from 'element-plus'
import { InfoFilled, Search } from '@element-plus/icons-vue'
import './evaluation-detail.scss'
import './run-result.scss'
import QualityPanel from './QualityPanel.vue'
import modelApi from '@/api/model/model'
import {
  getEvaluationDatasets,
  getEvaluationDataset,
  getEvaluationRuns,
  getEvaluationRun,
  startEvaluation,
  uploadEvaluationDataset,
  updateEvaluationDataset,
  deleteEvaluationDataset,
  downloadEvaluationReport,
  replayEvaluationRun,
} from '@/api/application/evaluation'

const { t, te } = useI18n()
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
const route = useRoute()
const id = String(route.params.id)
const mode = computed(() => String(route.meta.evaluationMode || 'evaluation'))
const visibleTabs = computed(() => mode.value === 'evaluation' ? ['history'] : mode.value === 'quality' ? ['quality', 'experiments', 'samples', 'badcases'] : mode.value === 'candidates' ? ['candidates'] : ['releases'])
const datasets = ref<any[]>([])
const runs = ref<any[]>([])
const loading = ref(false)
const submitting = ref(false)
const detailLoading = ref(false)
const datasetDialog = ref(false)
const runDialog = ref(false)
const detailVisible = ref(false)
const datasetDetailVisible = ref(false)
const datasetDetailLoading = ref(false)
const datasetDetail = ref<any>({})
const datasetSearch = ref('')
const resultFilter = ref('all')
const detail = ref<any>({})
const datasetName = ref('')
const editingDatasetId = ref('')
const datasetId = ref('')
const entryMode = ref('manual')
const questions = ref([{ question: '', ground_truth: '' }])
const files = ref<UploadUserFile[]>([])
const search = ref('')
const models = ref<any[]>([])
const judgeModelId = ref('')
const embeddingModelId = ref('')
const baselineId = ref('')
const regression = ref(false)
const regressionThreshold = ref(0.05)
const availableBaselines = computed(() => runs.value.filter(run => ['completed', 'partial'].includes(run.status)))
const latestRun = computed(() => runs.value[0])
const latestScore = computed(() => score(latestRun.value?.summary?.total_score?.mean))
const completedRuns = computed(() => runs.value.filter(run => run.status === 'completed').length)
let timer: number | undefined
let disposed = false
const busy = computed(() => runs.value.some((run) => ['queued', 'running'].includes(run.status)))
const score = (value: any) =>
  value == null ? tr('unscored') : `${(Number(value) * 100).toFixed(1)}%`
const date = (value: string) => (value ? new Date(value).toLocaleString() : '—')
const status = (value: string) => (value ? tr(value) : '—')
const statusType = (value: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' => {
  if (value === 'completed') return 'success'
  if (value === 'failed') return 'danger'
  if (value === 'partial') return 'warning'
  return value === 'running' ? 'primary' : 'info'
}
const percentage = (row: any) =>
  row.total ? Math.min(100, Math.round((row.completed / row.total) * 100)) : 0
const metricName = (name: string) =>
  te(`views.applicationEvaluation.ux.${name}`) ? tr(name) : name
const metrics = computed(() =>
  Object.entries(detail.value.summary || {}).map(([name, value]) => ({
    name,
    label: metricName(name),
    ...(value as any),
  })),
)
const formatSeconds = (value: any) => value == null ? '—' : `${Number(value).toFixed(2)} s`
const failedCases = computed(() => (detail.value.results || []).filter((row: any) => row.error || Object.keys(row.metric_errors || {}).length).length)
const filteredDatasetCases = computed(() => (datasetDetail.value.cases || []).filter((row: any) => `${row.category || ''} ${row.question || ''} ${row.ground_truth || ''}`.toLowerCase().includes(datasetSearch.value.toLowerCase())))
const filteredResults = computed(() =>
  (detail.value.results || []).filter((row: any) => {
    const textMatch = `${row.question} ${row.answer} ${row.ground_truth}`.toLowerCase().includes(search.value.toLowerCase())
    const hasError = row.error || Object.keys(row.metric_errors || {}).length
    const filterMatch = resultFilter.value === 'all' || (resultFilter.value === 'error' && hasError) || (resultFilter.value === 'unscored' && row.total_score == null) || (resultFilter.value === 'low' && row.total_score != null && Number(row.total_score) < 0.6)
    return textMatch && filterMatch
  }),
)
const showDataset = async (row: any) => {
  datasetSearch.value = ''
  datasetDetail.value = row
  datasetDetailVisible.value = true
  datasetDetailLoading.value = true
  try { datasetDetail.value = (await getEvaluationDataset(id, row.id)).data } finally { datasetDetailLoading.value = false }
}
const openRun = (selected?: string) => {
  datasetId.value = selected || datasets.value[0]?.id || ''
  judgeModelId.value = ''
  embeddingModelId.value = ''
  baselineId.value = ''
  regression.value = false
  runDialog.value = true
  modelApi.getModelList().then(result => { models.value = result.data.filter(model => model.status === 'SUCCESS') }).catch(() => {})
}
const resetDatasetForm = () => {
  datasetName.value = ''
  editingDatasetId.value = ''
  entryMode.value = 'manual'
  questions.value = [{ question: '', ground_truth: '' }]
  files.value = []
}
const openDatasetDialog = () => {
  resetDatasetForm()
  datasetDialog.value = true
}
const editDataset = async (row: any) => {
  const detailResult = row.cases ? { data: row } : await getEvaluationDataset(id, row.id)
  const item = detailResult.data
  datasetName.value = item.name
  editingDatasetId.value = item.id
  entryMode.value = 'manual'
  questions.value = (item.cases || []).map((question: any) => ({ question: question.question || '', ground_truth: question.ground_truth || '' }))
  files.value = []
  datasetDetailVisible.value = false
  datasetDialog.value = true
}
const removeDataset = async (row: any) => {
  try {
    await ElMessageBox.confirm(tr('deleteConfirm'), tr('deleteDataset'), { type: 'warning', confirmButtonText: tr('delete'), cancelButtonText: tr('cancel') })
    await deleteEvaluationDataset(id, row.id)
    await load()
    ElMessage.success(tr('deleted'))
  } catch {
    // Cancelled by the user or rejected by the API.
  }
}
const fileExceeded = () => ElMessage.warning(tr('oneFile'))
const saveBlob = (blob: Blob, name: string) => {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
const templateFile = () =>
  saveBlob(
    new Blob(
      [
        JSON.stringify(
          [{ id: '1', question: tr('sampleQuestion'), ground_truth: tr('sampleAnswer') }],
          null,
          2,
        ),
      ],
      { type: 'application/json' },
    ),
    'evaluation-template.json',
  )
const load = async (silent = false) => {
  if (!silent) loading.value = true
  try {
    const [datasetResult, runResult] = await Promise.all([
      getEvaluationDatasets(id),
      getEvaluationRuns(id),
    ])
    datasets.value = datasetResult.data || []
    runs.value = runResult.data || []
    if (detailVisible.value && ['queued', 'running'].includes(detail.value.status))
      detail.value = (await getEvaluationRun(id, detail.value.id)).data
  } finally {
    if (!silent) loading.value = false
  }
}
const importDataset = async () => {
  if (!datasetName.value.trim()) return ElMessage.warning(tr('nameRequired'))
  let file: File | undefined
  if (entryMode.value === 'manual') {
    if (questions.value.some((item) => !item.question.trim() || !item.ground_truth.trim()))
      return ElMessage.warning(tr('questionRequired'))
    file = new File(
      [
        JSON.stringify(
          questions.value.map((item, index) => ({
            id: String(index + 1),
            question: item.question.trim(),
            ground_truth: item.ground_truth.trim(),
          })),
        ),
      ],
      'questions.json',
      { type: 'application/json' },
    )
  } else file = files.value[0]?.raw
  if (!file) return ElMessage.warning(tr('fileRequired'))
  if (!/\.(json|csv)$/i.test(file.name) || file.size > 5 * 1024 * 1024)
    return ElMessage.warning(tr('fileHint'))
  submitting.value = true
  try {
    const isEditing = Boolean(editingDatasetId.value)
    const result = isEditing
      ? await updateEvaluationDataset(id, editingDatasetId.value, datasetName.value.trim(), file)
      : await uploadEvaluationDataset(id, datasetName.value.trim(), file)
    datasetDialog.value = false
    datasetName.value = ''
    questions.value = [{ question: '', ground_truth: '' }]
    files.value = []
    await load()
    ElMessage.success(tr(isEditing ? 'updated' : 'saved'))
    if (!isEditing) openRun(result.data.id)
  } finally {
    submitting.value = false
  }
}
const start = async () => {
  if (!datasetId.value || busy.value) return
  if (judgeModelId.value && !embeddingModelId.value) return ElMessage.warning(tr('embeddingRequired'))
  if (regression.value && !baselineId.value) return ElMessage.warning(tr('baselineRequired'))
  submitting.value = true
  try {
    const result = await startEvaluation(id, {
      dataset_id: datasetId.value,
      ...(judgeModelId.value ? { judge_model_id: judgeModelId.value, embedding_model_id: embeddingModelId.value } : {}),
      ...(baselineId.value ? { baseline_id: baselineId.value } : {}),
      regression: regression.value,
      regression_threshold: regressionThreshold.value,
    })
    runDialog.value = false
    await load()
    ElMessage.success(tr('started'))
    await showRun(result.data)
  } finally {
    submitting.value = false
  }
}
const replayRun = async (row: any) => {
  if (busy.value || submitting.value || !row.can_replay) return
  try {
    await ElMessageBox.confirm(tr('replayConfirm'), tr('replay'), { type: 'info' })
  } catch { return }
  submitting.value = true
  try {
    const result = await replayEvaluationRun(id, row.id)
    ElMessage.success(tr('replayStarted'))
    await load()
    await showRun(result.data)
  } finally { submitting.value = false }
}
const showRun = async (row: any) => {
  search.value = ''
  resultFilter.value = 'all'
  detail.value = row
  detailVisible.value = true
  detailLoading.value = true
  try {
    detail.value = (await getEvaluationRun(id, row.id)).data
  } finally {
    detailLoading.value = false
  }
}
const download = async (row: any) => {
  try {
    const response = await downloadEvaluationReport(id, row.id, 'md')
    if (!response.ok || !response.headers.get('content-type')?.includes('text/markdown'))
      throw new Error(tr('downloadFailed'))
    saveBlob(await response.blob(), `evaluation-${row.id}.md`)
  } catch {
    ElMessage.error(tr('downloadFailed'))
  }
}
const poll = async () => {
  try {
    if (busy.value) await load(true)
  } catch {
    /* Retry on the next scheduled refresh. */
  } finally {
    if (!disposed) timer = window.setTimeout(poll, 5000)
  }
}
onMounted(async () => {
  try {
    await load()
  } finally {
    if (!disposed) timer = window.setTimeout(poll, 5000)
  }
})
onUnmounted(() => {
  disposed = true
  if (timer) window.clearTimeout(timer)
})
</script>
<style scoped>
.evaluation-page {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  box-sizing: border-box;
  background: var(--el-fill-color-lighter);
}
.page-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 4px 20px;
}
.page-hero h2 { margin: 4px 0 6px; font-size: 26px; letter-spacing: -.02em; }
.detail-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.detail-heading h3 { margin: 4px 0 6px; font-size: 22px; }
.detail-heading p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.dataset-meta, .result-stat-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 20px; }
.dataset-meta > div, .result-stat { display: flex; flex-direction: column; gap: 5px; padding: 14px 16px; background: var(--el-fill-color-lighter); border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.dataset-meta span, .result-stat span, .metric-chip span, .metric-chip small { color: var(--el-text-color-secondary); font-size: 12px; }
.dataset-meta strong, .result-stat strong { color: var(--el-text-color-primary); font-size: 18px; }
.table-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 20px 0 12px; }
.table-toolbar > div:first-child { display: flex; align-items: center; gap: 10px; }
.toolbar-search { width: 240px; }
.clamp-text { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-height: 1.5; }
.run-progress { padding: 14px 16px; margin-bottom: 14px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.run-progress > div { display: flex; justify-content: space-between; margin-bottom: 10px; }
.run-progress span { color: var(--el-text-color-secondary); }
.metric-strip { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; margin-bottom: 20px; }
.metric-chip { display: flex; flex-direction: column; gap: 5px; padding: 13px 14px; background: var(--el-fill-color-lighter); border-radius: 8px; }
.metric-chip strong { font-size: 19px; }
.metric-chip small { font-size: 11px; }
.results-toolbar { margin-top: 12px; }
.toolbar-controls { display: flex; align-items: center; gap: 10px; }
.table-hint { color: var(--el-text-color-secondary); font-size: 12px; }
.eyebrow { color: var(--el-color-primary); font-size: 12px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.summary-item { display: flex; flex-direction: column; gap: 4px; min-height: 92px; padding: 16px 18px; background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter); border-radius: 10px; box-shadow: 0 4px 14px rgba(var(--el-text-color-primary-rgb), .04); }
.summary-item strong { color: var(--el-text-color-primary); font-size: 24px; line-height: 1.2; }
.summary-item span { color: var(--el-text-color-secondary); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.summary-item.active { border-color: var(--el-color-primary-light-5); background: var(--el-color-primary-light-9); }
.capability-alert { margin-bottom: 16px; border: 0; }
.workspace-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; align-items: start; }
.content-card { min-width: 0; border: 1px solid var(--el-border-color-lighter); border-radius: 10px; box-shadow: 0 4px 14px rgba(var(--el-text-color-primary-rgb), .04); }
.content-card :deep(.el-card__header) { padding: 14px 18px; }
.content-card :deep(.el-card__body) { padding: 0; }
.content-card :deep(.el-table) { border-radius: 0 0 10px 10px; }
.content-card :deep(.el-table__header-wrapper th) { height: 46px; background: var(--el-fill-color-lighter); color: var(--el-text-color-secondary); font-size: 12px; font-weight: 600; }
.content-card :deep(.el-table__body-wrapper td) { padding: 14px 0; vertical-align: middle; }
.dataset-name-cell { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.dataset-name-cell strong { overflow: hidden; color: var(--el-text-color-primary); font-size: 13px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.dataset-name-cell span { color: var(--el-text-color-secondary); font-size: 12px; }
.progress-cell { display: flex; flex-direction: column; gap: 7px; min-width: 130px; }
.progress-cell span { color: var(--el-text-color-secondary); font-size: 12px; }
.section-actions { display: flex; align-items: center; gap: 8px; }
.dialog-intro { padding: 12px 14px; margin-bottom: 18px; background: var(--el-color-primary-light-9); border: 1px solid var(--el-color-primary-light-8); border-radius: 8px; }
.dialog-intro p { margin: 5px 0 0; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; }
.dataset-form :deep(.el-form-item) { margin-bottom: 18px; }
.entry-mode { display: flex; width: 100%; }
.entry-mode :deep(.el-radio-button) { flex: 1; }
.entry-mode :deep(.el-radio-button__inner) { width: 100%; }
.manual-hint { display: flex; align-items: center; gap: 7px; padding: 10px 12px; margin-bottom: 12px; color: var(--el-text-color-secondary); background: var(--el-fill-color-lighter); border-radius: 6px; font-size: 12px; line-height: 1.5; }
.manual-hint .el-icon { color: var(--el-color-primary); }
.manual-hint strong { margin-left: auto; color: var(--el-text-color-primary); font-weight: 500; white-space: nowrap; }
.w-full {
  width: 100%;
}
.mt-16 {
  margin-top: 16px;
}
.question-editor {
  padding: 16px;
  margin: 12px 0;
  background: var(--el-bg-color-page);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
.resource-ids { overflow-wrap: anywhere; }
.question-editor :deep(.el-textarea__inner) { min-height: 72px !important; resize: vertical; }
.add-question-button { width: 100%; border-style: dashed; }
.file-hint { line-height: 1.55; }
.answer-comparison {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  padding: 16px;
}
.answer-text,
.report {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.metric-tag {
  margin: 0 8px 8px 0;
}
@media (max-width: 768px) {
  .page-hero { align-items: flex-start; flex-direction: column; gap: 14px; }
  .summary-grid, .workspace-grid, .dataset-meta, .result-stat-grid { grid-template-columns: 1fr; }
  .table-toolbar, .toolbar-controls { align-items: stretch; flex-direction: column; }
  .toolbar-search { width: 100%; }
  .section-actions { width: 100%; }
  .section-actions .el-button { flex: 1; }
  .answer-comparison {
    grid-template-columns: 1fr;
  }
}
</style>
