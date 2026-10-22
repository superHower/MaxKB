<template>
  <el-card class="candidate-panel" shadow="never">
    <template #header>
      <div class="panel-toolbar"><div><strong>{{ tr('title') }}</strong><p>{{ tr('intro') }}</p></div>
        <div><el-button :loading="loading" @click="load">{{ tr('refresh') }}</el-button><el-button type="primary" @click="openEditor()">{{ tr('create') }}</el-button></div>
      </div>
    </template>
    <div class="candidate-filters">
      <el-input v-model="filters.search" :placeholder="tr('search')" clearable @change="load" />
      <el-select v-for="key in ['status', 'kind', 'category', 'source']" :key="key" v-model="filters[key]" :placeholder="tr(key)" clearable @change="load">
        <el-option v-for="value in options[key]" :key="value" :value="value" :label="tr(value)" />
      </el-select>
      <el-select v-model="filters.version" :placeholder="tr('version')" clearable @change="load"><el-option v-for="v in versions" :key="v.id" :value="v.id" :label="v.name" /></el-select>
    </div>
    <el-table :data="items" v-loading="loading" :empty-text="tr('empty')" @row-click="show">
      <el-table-column prop="title" :label="tr('name')" min-width="220" show-overflow-tooltip />
      <el-table-column :label="tr('kind')" width="150"><template #default="{ row }">{{ tr(row.kind) }}</template></el-table-column>
      <el-table-column :label="tr('category')" width="130"><template #default="{ row }">{{ tr(row.category) }}</template></el-table-column>
      <el-table-column :label="tr('status')" width="150"><template #default="{ row }"><el-tag :type="statusType(row.status)">{{ tr(row.status) }}</el-tag></template></el-table-column>
      <el-table-column prop="sample_count" :label="tr('samples')" width="110" />
      <el-table-column :label="tr('revision')" width="90"><template #default="{ row }">v{{ row.revision }}</template></el-table-column>
      <el-table-column width="100"><template #default="{ row }"><el-button link type="primary" @click.stop="show(row)">{{ tr('detail') }}</el-button></template></el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="editorVisible" :title="tr(editingId ? 'edit' : 'create')" width="min(880px, 95vw)" :close-on-click-modal="false">
    <el-form label-position="top" v-loading="saving">
      <div class="form-grid"><el-form-item :label="tr('name')" required><el-input v-model="form.title" maxlength="128" /></el-form-item>
        <el-form-item :label="tr('kind')" required><el-select v-model="form.kind"><el-option v-for="v in options.kind" :key="v" :value="v" :label="tr(v)" /></el-select></el-form-item>
        <el-form-item :label="tr('baseline')" required><el-select v-model="form.baseline_id" @change="form.patch.node_id = ''"><el-option v-for="run in completedRuns" :key="run.id" :value="run.id" :label="`${run.dataset_name} · ${new Date(run.created_at).toLocaleString()}`" /></el-select></el-form-item>
        <el-form-item :label="tr('target')" required><el-select v-model="form.patch.node_id"><el-option v-for="node in targets" :key="node.id" :value="node.id" :label="node.name" /></el-select></el-form-item>
        <el-form-item :label="tr('category')"><el-select v-model="form.category"><el-option v-for="v in options.category" :key="v" :value="v" :label="tr(v)" /></el-select></el-form-item>
        <el-form-item :label="tr('judge')" required><el-select v-model="form.judge_model_id"><el-option v-for="m in models" :key="m.id" :value="m.id" :label="m.name" /></el-select></el-form-item></div>
      <el-form-item :label="tr('sources')"><el-select v-model="form.badcase_ids" multiple filterable class="full-width"><el-option v-for="b in badcases" :key="b.badcase.id" :value="b.badcase.id" :label="`${b.event.question} · ${b.badcase.reason}`" /></el-select></el-form-item>
      <el-form-item v-if="form.kind === 'prompt_patch'" :label="tr('field')"><el-radio-group v-model="form.patch.field"><el-radio-button value="system">System</el-radio-button><el-radio-button value="prompt">Prompt</el-radio-button></el-radio-group></el-form-item>
      <el-form-item v-if="form.kind === 'skill_version'" :label="tr('skillId')"><el-input v-model="form.patch.skill_id" :placeholder="tr('skillHint')" /></el-form-item>
      <el-form-item v-if="form.kind === 'knowledge_task'" :label="tr('knowledgeId')" required><el-input v-model="form.patch.knowledge_id" /></el-form-item>
      <el-form-item :label="tr('content')" required><div class="full-width"><el-button size="small" class="mb-8" @click="insertTemplate">{{ tr('template') }}</el-button><el-input v-model="form.patch.content" type="textarea" :rows="9" maxlength="32000" show-word-limit /></div></el-form-item>
      <el-form-item :label="tr('risk')" required><el-input v-model="form.risk" type="textarea" :rows="2" maxlength="4000" /></el-form-item>
      <el-collapse><el-collapse-item :title="tr('gates')" name="gates"><p>{{ tr('gateHint') }}</p><div class="form-grid"><el-form-item v-for="key in Object.keys(form.gates)" :key="key" :label="tr(key)"><el-input-number v-model="form.gates[key]" :min="0" :max="key.endsWith('ratio') ? 100 : 1" :step="0.01" /></el-form-item></div></el-collapse-item></el-collapse>
      <p>{{ tr('pricingHint') }}</p><div class="form-grid"><el-form-item :label="tr('inputPrice')" required><el-input-number v-model="form.pricing.input" :min="0" :precision="4" /></el-form-item><el-form-item :label="tr('outputPrice')" required><el-input-number v-model="form.pricing.output" :min="0" :precision="4" /></el-form-item></div>
    </el-form>
    <template #footer><el-button @click="editorVisible = false">{{ tr('cancel') }}</el-button><el-button type="primary" :loading="saving" @click="save">{{ tr('save') }}</el-button></template>
  </el-dialog>

  <el-drawer v-model="detailVisible" :title="detail.title || tr('detail')" size="78%" destroy-on-close>
    <div v-loading="detailLoading" v-if="detail.id">
      <el-button v-if="detail.status === 'validating'" @click="reasonAction('cancel_validation')">{{ tr('cancel_validation') }}</el-button>
      <div class="panel-toolbar"><div><el-tag :type="statusType(detail.status)">{{ tr(detail.status) }}</el-tag><span class="ml-12">v{{ detail.revision }} · {{ tr(detail.kind) }}</span></div>
        <div><el-button v-if="editable" @click="openEditor(detail)">{{ tr('edit') }}</el-button><el-button v-if="editable" type="primary" :loading="saving" @click="act('validate')">{{ tr('validate') }}</el-button><el-button v-if="['pending_review', 'validation_failed'].includes(detail.status)" :disabled="!canApprove" type="success" @click="approvalVisible = true">{{ tr('approve') }}</el-button><el-button v-if="!['validating', 'approved', 'withdrawn'].includes(detail.status)" @click="reasonAction('reject')">{{ tr('reject') }}</el-button><el-button v-if="!['validating', 'withdrawn'].includes(detail.status)" @click="reasonAction('withdraw')">{{ tr('withdraw') }}</el-button></div>
      </div>
      <el-alert :title="tr('offline')" type="info" :closable="false" class="mt-16" />
      <p v-for="line in detail.spec?.limitations" :key="line" class="secondary">{{ line }}</p>
      <el-descriptions :column="2" border><el-descriptions-item :label="tr('version')">{{ detail.spec?.base_version_id }}</el-descriptions-item><el-descriptions-item :label="tr('baseline')">{{ detail.spec?.baseline_id }}</el-descriptions-item><el-descriptions-item :label="tr('risk')" :span="2">{{ detail.spec?.risk }}</el-descriptions-item></el-descriptions>
      <h4>{{ tr('diff') }}</h4><pre class="diff">{{ detail.spec?.diff }}</pre>
      <h4>{{ tr('sources') }}</h4><el-empty v-if="!detail.spec?.sources?.length" :description="tr('noSources')" /><el-table v-else :data="detail.spec.sources"><el-table-column prop="event.question" :label="tr('question')" /><el-table-column prop="reason" :label="tr('reason')" /><el-table-column width="120"><template #default="{ row }"><el-button link @click="traceSampleId = row.sample_id; traceVisible = true">{{ tr('evidence') }}</el-button></template></el-table-column></el-table>
      <h4>{{ tr('reports') }}</h4><el-empty v-if="!detail.validations?.length" :description="tr('notValidated')" />
      <el-collapse v-else v-model="openReports"><el-collapse-item v-for="v in detail.validations" :key="v.id" :name="v.id" :title="`v${v.revision} · ${tr(v.status)} · ${new Date(v.created_at).toLocaleString()}`">
        <el-alert v-if="v.error" :title="v.error" type="error" :closable="false" />
        <el-table :data="v.report?.checks || []"><el-table-column :label="tr('gate')" min-width="200"><template #default="{ row }">{{ gateLabel(row.key) }}</template></el-table-column><el-table-column prop="value" :label="tr('measured')"><template #default="{ row }">{{ row.value == null ? tr('missing') : Number(row.value).toFixed(4) }}</template></el-table-column><el-table-column prop="threshold" :label="tr('threshold')" /><el-table-column :label="tr('result')"><template #default="{ row }"><el-tag :type="row.passed ? 'success' : 'danger'">{{ tr(row.passed ? 'passed' : row.waivable ? 'waiverRequired' : 'blocked') }}</el-tag></template></el-table-column></el-table>
        <el-table :data="v.report?.results || []"><el-table-column type="expand"><template #default="{ row }"><div class="answer-grid"><div><h4>{{ tr('before') }}</h4><pre>{{ row.before?.answer || '—' }}</pre><p>{{ row.before?.reason }}</p></div><div><h4>{{ tr('after') }}</h4><pre>{{ row.after?.answer || row.error || '—' }}</pre><p>{{ row.after?.reason }}</p></div></div></template></el-table-column><el-table-column prop="question" :label="tr('question')" /><el-table-column prop="before.score" :label="tr('before')" width="100" /><el-table-column prop="after.score" :label="tr('after')" width="100" /></el-table>
      </el-collapse-item></el-collapse>
      <h4>{{ tr('capability') }}</h4><el-empty v-if="!detail.capability_versions?.length" :description="tr('notApproved')" /><div v-for="v in detail.capability_versions" :key="v.id" class="release-info"><el-tag>{{ tr(v.status) }}</el-tag><p>{{ v.id }}</p><p>{{ tr('approver') }}: {{ v.approved_by }}</p><p>{{ tr('impact') }}: {{ v.manifest.impact_scope }}</p><p>{{ tr('rollback') }}: {{ v.manifest.rollback_version.id }}</p><p>{{ tr('noRelease') }}</p></div>
      <h4>{{ tr('audit') }}</h4><el-timeline><el-timeline-item v-for="a in detail.audits" :key="a.created_at + a.action" :timestamp="new Date(a.created_at).toLocaleString()"><strong>{{ tr(a.action) }}</strong> · v{{ a.revision }} · {{ a.actor_id }}<p v-if="a.data?.reason">{{ a.data.reason }}</p><p v-if="a.data?.waivers">{{ a.data.waivers }}</p></el-timeline-item></el-timeline>
    </div>
  </el-drawer>
  <el-dialog v-model="approvalVisible" :title="tr('approve')" width="600px" :close-on-click-modal="false">
    <el-form label-position="top"><el-form-item :label="tr('impact')" required><el-input v-model="approval.impact_scope" type="textarea" maxlength="4000" /></el-form-item><el-form-item :label="tr('rollback')" required><el-select v-model="approval.rollback_version_id"><el-option v-for="v in versions" :key="v.id" :value="v.id" :label="v.name" /></el-select></el-form-item><el-form-item v-for="c in waivableChecks" :key="c.key" :label="`${gateLabel(c.key)} · ${tr('waiverReason')}`" required><el-input v-model="approval.waivers[c.key]" type="textarea" maxlength="4000" /></el-form-item></el-form>
    <template #footer><el-button @click="approvalVisible = false">{{ tr('cancel') }}</el-button><el-button type="primary" :loading="saving" @click="approve">{{ tr('confirmApprove') }}</el-button></template>
  </el-dialog>
  <TraceDrawer v-model="traceVisible" :application-id="props.applicationId" :sample-id="traceSampleId" />
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getImprovementCandidates, getImprovementCandidate, getCandidateOptions, saveImprovementCandidate,
  actionImprovementCandidate, getEvaluationBadcases, getEvaluationRun } from '@/api/application/evaluation'
import ModelApi from '@/api/model/model'
import TraceDrawer from './TraceDrawer.vue'
import messages from './candidate-messages'

const props = defineProps<{ applicationId: string; runs: any[] }>()
const { locale } = useI18n()
const tr = (key: string) => (messages[locale.value.startsWith('zh') ? 'zh' : 'en'] as Record<string, string>)[key] || key
const loading = ref(false), saving = ref(false), detailLoading = ref(false)
const items = ref<any[]>([]), versions = ref<any[]>([]), badcases = ref<any[]>([]), models = ref<any[]>([])
const filters = reactive<Record<string, string>>({ search: '', status: '', kind: '', category: '', source: '', version: '' })
const options: Record<string, string[]> = { status: ['draft', 'validating', 'validation_failed', 'pending_review', 'approved', 'rejected', 'withdrawn'], kind: ['prompt_patch', 'skill_version', 'knowledge_task'], category: ['data', 'retrieval', 'generation', 'prompt', 'model', 'permission', 'user', 'business', 'other'], source: ['manual', 'template'] }
const detail = ref<any>({}), detailVisible = ref(false), editorVisible = ref(false), approvalVisible = ref(false)
const editingId = ref(''), traceVisible = ref(false), traceSampleId = ref(''), openReports = ref<string[]>([])
const baseVersions = ref<Record<string, string>>({})
const emptyForm = () => ({ title: '', kind: 'prompt_patch', category: 'prompt', source: 'manual', baseline_id: '', judge_model_id: '', badcase_ids: [] as string[], risk: '', revision: 1, patch: { node_id: '', field: 'system', content: '', skill_id: '', knowledge_id: '' }, gates: { min_score: .8, max_score_drop: .02, max_category_drop: 0, min_safety: 1, max_latency_ratio: 1.5, max_cost_ratio: 1.2, max_tool_error_rate: 0 } as Record<string, number>, pricing: { input: undefined as number | undefined, output: undefined as number | undefined } })
const form = ref(emptyForm())
const approval = reactive({ impact_scope: '', rollback_version_id: '', waivers: {} as Record<string, string> })
const completedRuns = computed(() => props.runs.filter(r => r.status === 'completed' && r.can_replay))
const targets = computed(() => versions.value.find(v => v.id === baseVersions.value[form.value.baseline_id])?.targets || [])
const editable = computed(() => ['draft', 'validation_failed', 'rejected', 'pending_review'].includes(detail.value.status))
const checks = computed<any[]>(() => detail.value.validations?.[0]?.report?.checks || [])
const canApprove = computed(() => checks.value.length > 0 && checks.value.every(c => c.passed || c.waivable))
const waivableChecks = computed(() => checks.value.filter(c => !c.passed && c.waivable))
const statusType = (status: string) => status === 'approved' || status === 'passed' ? 'success' : status === 'validation_failed' || status === 'failed' ? 'danger' : status === 'pending_review' ? 'warning' : 'info'
const gateLabel = (key: string) => key.startsWith('category:') ? `${tr('category')}: ${key.slice(9)}` : tr(key)
const load = async () => { loading.value = true; try { items.value = (await getImprovementCandidates(props.applicationId, filters)).data || [] } finally { loading.value = false } }
const show = async (row: any) => { approval.impact_scope = ''; approval.rollback_version_id = ''; approval.waivers = {}; detail.value = {}; detailVisible.value = true; detailLoading.value = true; try { detail.value = (await getImprovementCandidate(props.applicationId, row.id)).data; openReports.value = detail.value.validations?.[0] ? [detail.value.validations[0].id] : [] } finally { detailLoading.value = false } }
const openEditor = async (row?: any) => {
  editingId.value = row?.id || ''; form.value = emptyForm()
  if (row) { const s = row.spec; form.value = { ...form.value, title: row.title, kind: row.kind, category: row.category, source: row.source, revision: row.revision, baseline_id: s.baseline_id, judge_model_id: s.judge_model_id, badcase_ids: s.sources.map((b: any) => b.id), risk: s.risk, patch: { ...form.value.patch, ...s.patch }, gates: { ...s.gates }, pricing: { ...s.pricing } } }
  editorVisible.value = true
  try {
    const [o, b, m] = await Promise.all([getCandidateOptions(props.applicationId), getEvaluationBadcases(props.applicationId), ModelApi.getModelList({ model_type: 'LLM' })])
    versions.value = o.data.versions; badcases.value = b.data || []; models.value = m.data || []
    const pairs = await Promise.all(completedRuns.value.map(async r => { const run = (await getEvaluationRun(props.applicationId, r.id)).data; return [r.id, run.config?.application_version] }))
    baseVersions.value = Object.fromEntries(pairs)
  } catch { editorVisible.value = false }
}
const insertTemplate = () => { form.value.source = 'template'; form.value.patch.content = form.value.kind === 'skill_version' ? tr('skillTemplate') : form.value.kind === 'knowledge_task' ? tr('knowledgeTemplate') : tr('promptTemplate') }
const save = async () => {
  if (!form.value.title.trim() || !form.value.baseline_id || !form.value.judge_model_id || !form.value.patch.content.trim() || !form.value.risk.trim()) return ElMessage.warning(tr('required'))
  saving.value = true
  try { const res = await saveImprovementCandidate(props.applicationId, form.value, editingId.value || undefined); editorVisible.value = false; await load(); await show(res.data); ElMessage.success(tr('saved')) } finally { saving.value = false }
}
const act = async (action: string, data: any = {}) => { saving.value = true; try { const r = await actionImprovementCandidate(props.applicationId, detail.value.id, { action, revision: detail.value.revision, ...data }); detail.value = r.data; openReports.value = detail.value.validations?.[0] ? [detail.value.validations[0].id] : []; await load() } finally { saving.value = false } }
const reasonAction = async (action: string) => { try { const r = await ElMessageBox.prompt(tr('reason'), tr(action), { inputType: 'textarea', inputValidator: value => Boolean(value?.trim()) || tr('required') }); await act(action, { reason: r.value }) } catch { /* cancellation or API feedback */ } }
const approve = async () => { if (!approval.impact_scope.trim() || !approval.rollback_version_id || waivableChecks.value.some(c => !approval.waivers[c.key]?.trim())) return ElMessage.warning(tr('required')); await act('approve', approval); approvalVisible.value = false; approval.impact_scope = ''; approval.waivers = {} }
let timer: number | undefined, disposed = false
const poll = async () => { try { if (items.value.some(c => c.status === 'validating')) { await load(); if (detailVisible.value) { detail.value = (await getImprovementCandidate(props.applicationId, detail.value.id)).data } } } finally { if (!disposed) timer = window.setTimeout(() => { poll().catch(() => {}) }, 5000) } }
onMounted(async () => { try { await load(); versions.value = (await getCandidateOptions(props.applicationId)).data.versions } finally { if (!disposed) timer = window.setTimeout(() => { poll().catch(() => {}) }, 5000) } })
onUnmounted(() => { disposed = true; if (timer) window.clearTimeout(timer) })
</script>

<style scoped>
.candidate-panel { margin-top: 20px; border-radius: 8px; }
.panel-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.panel-toolbar p, .secondary { color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; }
.panel-toolbar p { margin: 6px 0 0; }
.candidate-filters { display: grid; grid-template-columns: 1.5fr repeat(5, 1fr); gap: 10px; margin-bottom: 16px; }
.form-grid, .answer-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.answer-grid { padding: 16px; }
.full-width { width: 100%; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; }
.diff, .release-info { padding: 16px; background: var(--el-fill-color-lighter); border-radius: 6px; }
@media (max-width: 900px) { .candidate-filters, .form-grid, .answer-grid { grid-template-columns: 1fr; } }
</style>
