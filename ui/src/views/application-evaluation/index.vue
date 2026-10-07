<template>
  <div class="p-16">
    <div class="flex align-center justify-between mb-16">
      <div>
        <h2>{{ tr('title') }}</h2>
        <el-text type="info">{{ tr('intro') }}</el-text>
      </div>
      <el-button type="primary" :disabled="!datasets.length || busy" @click="openRun()">{{
        tr('start')
      }}</el-button>
    </div>
    <el-card class="mb-16">
      <el-steps :active="busy ? 2 : datasets.length ? 1 : 0" simple
        ><el-step :title="tr('prepare')" /><el-step :title="tr('configure')" /><el-step
          :title="tr('results')"
      /></el-steps>
      <el-alert class="mt-16" :title="tr('capability')" type="info" :closable="false" />
    </el-card>
    <el-card class="mb-16">
      <template #header
        ><div class="flex justify-between align-center">
          <strong>{{ tr('prepare') }}</strong>
          <div>
            <el-button @click="templateFile">{{ tr('template') }}</el-button
            ><el-button type="primary" plain @click="datasetDialog = true">{{
              tr('add')
            }}</el-button>
          </div>
        </div></template
      >
      <el-empty v-if="!datasets.length && !loading" :description="tr('empty')"
        ><el-button type="primary" @click="datasetDialog = true">{{
          tr('add')
        }}</el-button></el-empty
      >
      <el-table v-else :data="datasets" v-loading="loading">
        <el-table-column prop="name" :label="tr('dataset')" /><el-table-column
          prop="count"
          :label="tr('cases')"
          width="100"
        />
        <el-table-column :label="tr('version')" width="120"
          ><template #default="{ row }"
            ><el-tooltip :content="row.version"
              ><span>{{ row.version.slice(0, 8) }}</span></el-tooltip
            ></template
          ></el-table-column
        >
        <el-table-column :label="tr('date')"
          ><template #default="{ row }">{{ date(row.created_at) }}</template></el-table-column
        >
        <el-table-column width="130"
          ><template #default="{ row }"
            ><el-button link type="primary" :disabled="busy" @click="openRun(row.id)">{{
              tr('use')
            }}</el-button></template
          ></el-table-column
        >
      </el-table>
    </el-card>
    <el-card>
      <template #header
        ><div class="flex justify-between align-center">
          <strong>{{ tr('history') }}</strong
          ><el-button :loading="loading" @click="load()">{{ tr('refresh') }}</el-button>
        </div></template
      >
      <el-table :data="runs" :empty-text="tr('noRuns')" v-loading="loading">
        <el-table-column :label="tr('date')"
          ><template #default="{ row }">{{ date(row.created_at) }}</template></el-table-column
        >
        <el-table-column prop="dataset_name" :label="tr('dataset')" />
        <el-table-column :label="tr('status')" width="130"
          ><template #default="{ row }"
            ><el-tag :type="statusType(row.status)">{{ status(row.status) }}</el-tag></template
          ></el-table-column
        >
        <el-table-column :label="tr('progress')" min-width="150"
          ><template #default="{ row }"
            ><el-progress :percentage="percentage(row)" :show-text="false" />{{ row.completed }} /
            {{ row.total }} {{ tr('questions') }}</template
          ></el-table-column
        >
        <el-table-column :label="tr('score')" width="120"
          ><template #default="{ row }">{{
            score(row.summary?.total_score?.mean)
          }}</template></el-table-column
        >
        <el-table-column :label="tr('actions')" width="160"
          ><template #default="{ row }"
            ><el-button link type="primary" @click="showRun(row)">{{ tr('view') }}</el-button
            ><el-button link :disabled="!row.summary?.total_score" @click="download(row)">{{
              tr('export')
            }}</el-button></template
          ></el-table-column
        >
      </el-table>
    </el-card>
    <el-dialog v-model="datasetDialog" :title="tr('add')" width="640px">
      <el-form label-position="top">
        <el-form-item :label="tr('name')"
          ><el-input v-model="datasetName" maxlength="128" :placeholder="tr('nameHint')"
        /></el-form-item>
        <el-radio-group v-model="entryMode" class="mb-16"
          ><el-radio-button value="manual">{{ tr('manual') }}</el-radio-button
          ><el-radio-button value="file">{{ tr('import') }}</el-radio-button></el-radio-group
        >
        <template v-if="entryMode === 'manual'">
          <el-text type="info">{{ tr('manualHint') }}</el-text>
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
          <el-button
            :disabled="questions.length >= 1000"
            @click="questions.push({ question: '', ground_truth: '' })"
            >{{ tr('addQuestion') }}</el-button
          >
        </template>
        <template v-else>
          <el-alert :title="tr('fileHint')" type="info" :closable="false" class="mb-16" />
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
    <el-dialog v-model="runDialog" :title="tr('configure')" width="560px">
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
      <p>{{ tr('mode') }}</p>
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
    <el-drawer v-model="detailVisible" size="85%" :title="tr('detail')">
      <div v-loading="detailLoading">
        <div class="flex justify-between align-center mb-16">
          <strong>{{ detail.dataset_name }}</strong
          ><el-tag :type="statusType(detail.status)">{{ status(detail.status) }}</el-tag>
        </div>
        <el-alert
          v-if="detail.error"
          :title="detail.error"
          type="error"
          :closable="false"
          class="mb-16"
        />
        <p>
          {{ tr('progress') }}: {{ detail.completed || 0 }} / {{ detail.total || 0 }} ·
          {{ tr('score') }}: {{ score(detail.summary?.total_score?.mean) }}
        </p>
        <el-alert :title="tr('scoreHint')" type="info" :closable="false" class="mb-16" />
        <el-table :data="metrics" class="mb-16"
          ><el-table-column prop="label" :label="tr('metric')" /><el-table-column
            :label="tr('mean')"
            ><template #default="{ row }">{{
              row.name === 'response_time'
                ? row.mean == null
                  ? '—'
                  : `${Number(row.mean).toFixed(2)} s`
                : score(row.mean)
            }}</template></el-table-column
          ><el-table-column :label="tr('coverage')"
            ><template #default="{ row }"
              >{{ row.count }} / {{ row.total }}</template
            ></el-table-column
          ></el-table
        >
        <div class="flex justify-between align-center mb-16">
          <strong>{{ tr('answers') }}</strong
          ><el-input
            v-model="search"
            clearable
            :placeholder="tr('search')"
            style="max-width: 300px"
          />
        </div>
        <el-table :data="filteredResults" :empty-text="tr('waiting')" row-key="id">
          <el-table-column type="expand"
            ><template #default="{ row }"
              ><div class="answer-comparison">
                <div>
                  <strong>{{ tr('answer') }}</strong>
                  <p class="answer-text">{{ row.answer || '—' }}</p>
                </div>
                <div>
                  <strong>{{ tr('reference') }}</strong>
                  <p class="answer-text">{{ row.ground_truth }}</p>
                </div>
              </div>
              <el-alert
                v-if="row.error || Object.keys(row.metric_errors || {}).length"
                :title="row.error || JSON.stringify(row.metric_errors)"
                type="error"
                :closable="false"
              />
              <div class="p-16">
                <el-tag v-for="(value, name) in row.scores" :key="name" class="metric-tag"
                  >{{ metricName(String(name)) }}: {{ score(value) }}</el-tag
                >
              </div></template
            ></el-table-column
          >
          <el-table-column
            prop="question"
            :label="tr('question')"
            min-width="250"
          /><el-table-column :label="tr('score')" width="120"
            ><template #default="{ row }">{{ score(row.total_score) }}</template></el-table-column
          ><el-table-column :label="tr('responseTime')" width="130"
            ><template #default="{ row }">{{
              row.response_time == null ? '—' : `${Number(row.response_time).toFixed(2)} s`
            }}</template></el-table-column
          >
        </el-table>
        <p>{{ tr('expandHint') }}</p>
        <el-collapse
          ><el-collapse-item :title="tr('technical')" name="technical">
            <pre class="report">{{ JSON.stringify(detail, null, 2) }}</pre>
          </el-collapse-item></el-collapse
        >
      </div>
    </el-drawer>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { ElMessage, type UploadUserFile } from 'element-plus'
import {
  getEvaluationDatasets,
  getEvaluationRuns,
  getEvaluationRun,
  startEvaluation,
  uploadEvaluationDataset,
  downloadEvaluationReport,
} from '@/api/application/evaluation'

const { t } = useI18n()
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
const id = String(useRoute().params.id)
const datasets = ref<any[]>([])
const runs = ref<any[]>([])
const loading = ref(false)
const submitting = ref(false)
const detailLoading = ref(false)
const datasetDialog = ref(false)
const runDialog = ref(false)
const detailVisible = ref(false)
const detail = ref<any>({})
const datasetName = ref('')
const datasetId = ref('')
const entryMode = ref('manual')
const questions = ref([{ question: '', ground_truth: '' }])
const files = ref<UploadUserFile[]>([])
const search = ref('')
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
  [
    'context_precision',
    'context_recall',
    'hit_rate',
    'mrr',
    'precision_at_k',
    'total_score',
    'response_time',
  ].includes(name)
    ? tr(name)
    : name
const metrics = computed(() =>
  Object.entries(detail.value.summary || {}).map(([name, value]) => ({
    name,
    label: metricName(name),
    ...(value as any),
  })),
)
const filteredResults = computed(() =>
  (detail.value.results || []).filter((row: any) =>
    `${row.question} ${row.answer} ${row.ground_truth}`
      .toLowerCase()
      .includes(search.value.toLowerCase()),
  ),
)
const openRun = (selected?: string) => {
  datasetId.value = selected || datasets.value[0]?.id || ''
  runDialog.value = true
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
    const result = await uploadEvaluationDataset(id, datasetName.value.trim(), file)
    datasetDialog.value = false
    datasetName.value = ''
    questions.value = [{ question: '', ground_truth: '' }]
    files.value = []
    await load()
    ElMessage.success(tr('saved'))
    openRun(result.data.id)
  } finally {
    submitting.value = false
  }
}
const start = async () => {
  if (!datasetId.value || busy.value) return
  submitting.value = true
  try {
    const result = await startEvaluation(id, { dataset_id: datasetId.value })
    runDialog.value = false
    await load()
    ElMessage.success(tr('started'))
    await showRun(result.data)
  } finally {
    submitting.value = false
  }
}
const showRun = async (row: any) => {
  search.value = ''
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
.w-full {
  width: 100%;
}
.mt-16 {
  margin-top: 16px;
}
.question-editor {
  padding: 16px;
  margin: 12px 0;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
}
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
  .answer-comparison {
    grid-template-columns: 1fr;
  }
}
</style>
