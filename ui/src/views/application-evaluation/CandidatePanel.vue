<template>
  <el-card class="candidate-panel" shadow="never">
    <template #header>
      <div class="panel-toolbar"><div><strong>{{ tr('title') }}</strong><p>{{ tr('intro') }}</p></div>
        <div><el-button :loading="loading" @click="load">{{ tr('refresh') }}</el-button><el-button type="primary" @click="openEditor()">{{ tr('create') }}</el-button></div>
      </div>
    </template>
    <div class="candidate-filters">
      <el-input v-model="filters.search" :placeholder="tr('search')" clearable @change="load" />
      <el-select v-for="key in ['status']" :key="key" v-model="filters[key]" :placeholder="tr(key)" clearable @change="load">
        <el-option v-for="value in options[key]" :key="value" :value="value" :label="tr(value)" />
      </el-select>
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
    <el-alert v-if="!completedRuns.length" :title="tr('needBaseline')" type="warning" show-icon :closable="false" class="mb-16" />
    <el-form label-position="top" v-loading="saving || editorLoading">
      <div class="form-grid"><el-form-item :label="tr('name')" required><el-input v-model="form.title" maxlength="128" /></el-form-item>
        <el-form-item :label="tr('kind')" required><el-select v-model="form.kind"><el-option v-for="v in options.kind" :key="v" :value="v" :label="tr(v)" /></el-select></el-form-item>
        <el-form-item :label="tr('baseline')" required><el-select v-model="form.baseline_id" @change="selectBaseline"><el-option v-for="run in completedRuns" :key="run.id" :value="run.id" :label="`${run.dataset_name} · ${new Date(run.created_at).toLocaleString()}`" /></el-select></el-form-item>
        <el-form-item :label="tr('target')" required><el-select v-model="form.patch.node_id"><el-option v-for="node in targets" :key="node.id" :value="node.id" :label="node.name" /></el-select></el-form-item>
        <el-form-item :label="tr('category')"><el-select v-model="form.category"><el-option v-for="v in options.category" :key="v" :value="v" :label="tr(v)" /></el-select></el-form-item>
        </div>
      <el-form-item :label="tr('sources')"><el-select v-model="form.badcase_ids" multiple filterable class="full-width"><el-option v-for="b in badcases" :key="b.badcase.id" :value="b.badcase.id" :label="`${b.event.question} · ${b.badcase.reason}`" /></el-select></el-form-item>
      <el-form-item v-if="form.kind === 'prompt_patch'" :label="tr('field')"><el-radio-group v-model="form.patch.field"><el-radio-button value="system">System</el-radio-button><el-radio-button value="prompt">Prompt</el-radio-button></el-radio-group></el-form-item>
      <el-alert v-if="evidenceText" :title="evidenceText" type="info" :closable="false" class="mb-16" />
      <el-form-item :label="tr('originalContent')"><el-input :model-value="originalContent" type="textarea" :rows="8" readonly :placeholder="tr('emptyOriginal')" /></el-form-item>
      <el-button class="mb-16" :disabled="!originalContent" @click="restoreOriginal">{{ tr('restoreOriginal') }}</el-button>
      <el-form-item v-if="form.kind === 'skill_version'" :label="tr('skillId')"><el-input v-model="form.patch.skill_id" :placeholder="tr('skillHint')" /></el-form-item>
      <el-form-item v-if="form.kind === 'knowledge_task'" :label="tr('knowledgeId')" required><el-input v-model="form.patch.knowledge_id" /></el-form-item>
      <el-form-item :label="tr('content')" required><div class="full-width"><el-button size="small" class="mb-8" @click="insertTemplate">{{ tr('template') }}</el-button><el-input v-model="form.patch.content" type="textarea" :rows="9" maxlength="32000" show-word-limit /></div></el-form-item>
      <el-form-item :label="tr('risk')" required><el-input v-model="form.risk" type="textarea" :rows="2" maxlength="4000" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="editorVisible = false">{{ tr('cancel') }}</el-button><el-button type="primary" :loading="saving" :disabled="editorLoading" @click="save">{{ tr('save') }}</el-button></template>
  </el-dialog>

  <el-drawer v-model="detailVisible" :title="detail.title || tr('detail')" size="min(1120px, 100vw)" class="evaluation-drawer candidate-detail-drawer" destroy-on-close>
    <div v-loading="detailLoading" v-if="detail.id" class="candidate-detail-content">
      <el-button v-if="detail.status === 'validating'" @click="reasonAction('cancel_validation')">{{ tr('cancel_validation') }}</el-button>
      <div class="panel-toolbar"><div><el-tag :type="statusType(detail.status)">{{ tr(detail.status) }}</el-tag><span class="ml-12">v{{ detail.revision }} · {{ tr(detail.kind) }}</span></div>
        <div><el-button v-if="editable" @click="openEditor(detail)">{{ tr('edit') }}</el-button><el-button v-if="detail.spec?.draft_only" type="primary" @click="openWorkflow">{{ tr('editWorkflow') }}</el-button><el-button v-if="!['validating', 'verifying', 'approved', 'withdrawn'].includes(detail.status)" @click="reasonAction('reject')">{{ tr('reject') }}</el-button><el-button v-if="!['validating', 'verifying', 'withdrawn'].includes(detail.status)" @click="reasonAction('withdraw')">{{ tr('withdraw') }}</el-button></div>
      </div>
      <section v-if="detail.spec?.draft_only" class="closure">
        <el-steps :active="closureStep" finish-status="success" align-center>
          <el-step :title="tr('stepApply')" :description="tr('stepApplyHelp')" />
          <el-step :title="tr('stepPublish')" :description="tr('stepPublishHelp')" />
          <el-step :title="tr('stepVerify')" :description="tr('stepVerifyHelp')" />
          <el-step :title="tr('stepClose')" :description="tr('stepCloseHelp')" />
        </el-steps>
        <div class="closure-actions">
          <el-button v-if="canApply" type="primary" :loading="saving" @click="applyDraft">{{ tr('applyDraft') }}</el-button>
          <el-button v-if="canVerify" :type="detail.status === 'applied' ? 'primary' : 'default'" :loading="saving" @click="act('verify')">{{ tr('verifyRun') }}</el-button>
          <span v-if="detail.status === 'verifying'" class="secondary">{{ tr('verifyingHint') }} {{ closure.run_id }}</span>
          <span v-else-if="detail.status === 'applied'" class="secondary">{{ tr('publishFirst') }}</span>
        </div>
        <template v-if="closure.result">
          <el-alert :type="detail.status === 'verified' ? 'success' : detail.status === 'needs_review' ? 'warning' : 'error'" :closable="false" show-icon
            :title="closure.result.run_status === 'failed' ? `${tr('verifyRunFailed')} ${closure.result.run_error || ''}` : `${tr(closure.result.regression_passed ? 'regressionOk' : 'regressionBad')}（${closure.result.regressions}）· ${tr('closedCount')} ${closure.result.closed_badcases.length}`" />
          <el-table :data="closure.result.cases" size="small" class="mt-16">
            <el-table-column type="expand"><template #default="{ row }"><pre class="closure-answer">{{ row.answer || '—' }}</pre></template></el-table-column>
            <el-table-column prop="question" :label="tr('question')" min-width="240" show-overflow-tooltip />
            <el-table-column :label="tr('result')" width="120"><template #default="{ row }"><el-tag :type="row.verdict === 'passed' ? 'success' : row.verdict === 'failed' ? 'danger' : 'warning'">{{ tr('verdict_' + row.verdict) }}</el-tag></template></el-table-column>
            <el-table-column :label="tr('samples')" width="100"><template #default="{ row }">{{ row.badcase_ids.length }}</template></el-table-column>
          </el-table>
          <p v-if="detail.status === 'needs_review'" class="secondary">{{ tr('needsReviewHint') }}</p>
        </template>
      </section>
      <el-alert v-else :title="tr('offline')" type="info" :closable="false" class="mt-16" />
      <p v-for="line in detail.spec?.limitations" :key="line" class="secondary">{{ line }}</p>
      <el-descriptions :column="2" border><el-descriptions-item :label="tr('version')">{{ detail.spec?.base_version_id }}</el-descriptions-item><el-descriptions-item :label="tr('baseline')">{{ detail.spec?.baseline_id }}</el-descriptions-item><el-descriptions-item :label="tr('risk')" :span="2">{{ detail.spec?.risk }}</el-descriptions-item></el-descriptions>
      <h4>{{ tr('diff') }}</h4><pre class="diff">{{ detail.spec?.diff }}</pre>
      <h4>{{ tr('sources') }}</h4><el-empty v-if="!detail.spec?.sources?.length" :description="tr('noSources')" /><el-table v-else :data="detail.spec.sources"><el-table-column prop="event.question" :label="tr('question')" /><el-table-column prop="reason" :label="tr('reason')" /><el-table-column width="120"><template #default="{ row }"><el-button link @click="traceSampleId = row.sample_id; traceVisible = true">{{ tr('evidence') }}</el-button></template></el-table-column></el-table>
      <template v-if="!detail.spec?.draft_only">
      <h4>{{ tr('reports') }}</h4><el-empty v-if="!detail.validations?.length" :description="tr('notValidated')" />
      <el-collapse v-else v-model="openReports"><el-collapse-item v-for="v in detail.validations" :key="v.id" :name="v.id" :title="`v${v.revision} · ${tr(v.status)} · ${new Date(v.created_at).toLocaleString()}`">
        <el-alert v-if="v.error" :title="v.error" type="error" :closable="false" />
        <el-table :data="v.report?.checks || []"><el-table-column :label="tr('gate')" min-width="200"><template #default="{ row }">{{ gateLabel(row.key) }}</template></el-table-column><el-table-column prop="value" :label="tr('measured')"><template #default="{ row }">{{ row.value == null ? tr('missing') : Number(row.value).toFixed(4) }}</template></el-table-column><el-table-column prop="threshold" :label="tr('threshold')" /><el-table-column :label="tr('result')"><template #default="{ row }"><el-tag :type="row.passed ? 'success' : 'danger'">{{ tr(row.passed ? 'passed' : row.waivable ? 'waiverRequired' : 'blocked') }}</el-tag></template></el-table-column></el-table>
        <el-table :data="v.report?.results || []"><el-table-column type="expand"><template #default="{ row }"><div class="answer-grid"><div><h4>{{ tr('before') }}</h4><pre>{{ row.before?.answer || '—' }}</pre><p>{{ row.before?.reason }}</p></div><div><h4>{{ tr('after') }}</h4><pre>{{ row.after?.answer || row.error || '—' }}</pre><p>{{ row.after?.reason }}</p></div></div></template></el-table-column><el-table-column prop="question" :label="tr('question')" /><el-table-column prop="before.score" :label="tr('before')" width="100" /><el-table-column prop="after.score" :label="tr('after')" width="100" /></el-table>
      </el-collapse-item></el-collapse>
      <h4>{{ tr('capability') }}</h4><el-empty v-if="!detail.capability_versions?.length" :description="tr('notApproved')" /><div v-for="v in detail.capability_versions" :key="v.id" class="release-info"><el-tag>{{ tr(v.status) }}</el-tag><p>{{ v.id }}</p><p>{{ tr('approver') }}: {{ v.approved_by }}</p><p>{{ tr('impact') }}: {{ v.manifest.impact_scope }}</p><p>{{ tr('rollback') }}: {{ v.manifest.rollback_version.id }}</p><p>{{ tr('noRelease') }}</p></div>
      </template>
      <h4>{{ tr('audit') }}</h4><el-timeline><el-timeline-item v-for="a in detail.audits" :key="a.created_at + a.action" :timestamp="new Date(a.created_at).toLocaleString()"><strong>{{ tr(a.action) }}</strong> · v{{ a.revision }} · {{ a.actor_id }}<p v-if="a.data?.reason">{{ a.data.reason }}</p><p v-if="a.data?.waivers">{{ a.data.waivers }}</p></el-timeline-item></el-timeline>
    </div>
  </el-drawer>
  <el-dialog v-model="approvalVisible" :title="tr('approve')" width="min(600px, 94vw)" class="evaluation-dialog" :close-on-click-modal="false">
    <el-form label-position="top"><el-form-item :label="tr('impact')" required><el-input v-model="approval.impact_scope" type="textarea" maxlength="4000" /></el-form-item><el-form-item :label="tr('rollback')" required><el-select v-model="approval.rollback_version_id"><el-option v-for="v in versions" :key="v.id" :value="v.id" :label="v.name" /></el-select></el-form-item><el-form-item v-for="c in waivableChecks" :key="c.key" :label="`${gateLabel(c.key)} · ${tr('waiverReason')}`" required><el-input v-model="approval.waivers[c.key]" type="textarea" maxlength="4000" /></el-form-item></el-form>
    <template #footer><el-button @click="approvalVisible = false">{{ tr('cancel') }}</el-button><el-button type="primary" :loading="saving" @click="approve">{{ tr('confirmApprove') }}</el-button></template>
  </el-dialog>
  <TraceDrawer v-model="traceVisible" :application-id="props.applicationId" :sample-id="traceSampleId" />
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getImprovementCandidates, getImprovementCandidate, getCandidateOptions, saveImprovementCandidate,
  actionImprovementCandidate, getEvaluationBadcases, getEvaluationRun } from '@/api/application/evaluation'
import { useRoute, useRouter } from 'vue-router'
import { isWorkFlow } from '@/utils/application'
import TraceDrawer from './TraceDrawer.vue'
import messages from './candidate-messages'
import './evaluation-detail.scss'

const props = defineProps<{ applicationId: string; runs: any[]; preset?: { badcase?: any; baselineId?: string; nodeId?: string; event?: any; finding?: any } }>()
const emit = defineEmits<{ 'preset-used': [] }>()
const { locale } = useI18n()
const tr = (key: string) => (messages[locale.value.startsWith('zh') ? 'zh' : 'en'] as Record<string, string>)[key] || key
const loading = ref(false), saving = ref(false), detailLoading = ref(false)
const items = ref<any[]>([]), versions = ref<any[]>([]), badcases = ref<any[]>([])
const editorLoading = ref(false)
const evidenceText = ref('')
const route = useRoute(), router = useRouter()
const filters = reactive<Record<string, string>>({ search: '', status: '', kind: '', category: '', source: '', version: '' })
const options: Record<string, string[]> = { status: ['draft', 'applied', 'verifying', 'verified', 'verify_failed', 'needs_review', 'rejected', 'withdrawn'], kind: ['prompt_patch', 'workflow_patch'], category: ['data', 'retrieval', 'generation', 'prompt', 'model', 'permission', 'user', 'business', 'other'], source: ['manual', 'template'] }
const detail = ref<any>({}), detailVisible = ref(false), editorVisible = ref(false), approvalVisible = ref(false)
const editingId = ref(''), traceVisible = ref(false), traceSampleId = ref(''), openReports = ref<string[]>([])
const baseVersions = ref<Record<string, string>>({})
const emptyForm = () => ({ title: '', kind: 'prompt_patch', category: 'prompt', source: 'manual', baseline_id: '', badcase_ids: [] as string[], risk: '', revision: 1, patch: { node_id: '', field: 'system', content: '', skill_id: '', knowledge_id: '' } })
const form = ref(emptyForm())
const selectedTarget = computed(() => targets.value.find((n: any) => n.id === form.value.patch.node_id))
const originalContent = computed(() => {
  if (editingId.value && detail.value.spec?.baseline_id === form.value.baseline_id && detail.value.spec?.patch?.node_id === form.value.patch.node_id && detail.value.spec?.patch?.field === form.value.patch.field) return detail.value.spec.patch.before || ''
  const data = selectedTarget.value?.data || {}
  return form.value.kind === 'workflow_patch' ? JSON.stringify(data, null, 2) : String(data[form.value.patch.field] || '')
})
const restoreOriginal = () => { form.value.patch.content = originalContent.value }
const selectBaseline = () => { form.value.patch.node_id = ''; form.value.patch.content = '' }
const openWorkflow = () => {
  const { from, id, type } = route.params
  window.open(router.resolve(isWorkFlow(String(type)) ? `/application/${from}/${id}/workflow` : `/application/${from}/${id}/${type}/setting`).href, '_blank')
}
const approval = reactive({ impact_scope: '', rollback_version_id: '', waivers: {} as Record<string, string> })
const completedRuns = computed(() => props.runs.filter(r => r.status === 'completed' && r.can_replay))
const targets = computed(() => versions.value.find(v => v.id === baseVersions.value[form.value.baseline_id])?.targets || [])
const editable = computed(() => ['draft', 'validation_failed', 'rejected', 'pending_review', 'verify_failed', 'needs_review'].includes(detail.value.status))
const closure = computed<any>(() => detail.value.spec?.closure || {})
const closureStep = computed(() => ({ applied: 1, verifying: 2, verified: 4, verify_failed: 3, needs_review: 3 } as Record<string, number>)[detail.value.status] ?? 0)
const canApply = computed(() => ['draft', 'rejected', 'verify_failed', 'needs_review'].includes(detail.value.status))
const canVerify = computed(() => ['applied', 'verify_failed', 'needs_review', 'verified'].includes(detail.value.status))
// Writes the reviewed change into the editable workflow only; publishing stays a human step.
const applyDraft = async () => {
  try { await ElMessageBox.confirm(tr('applyConfirm'), tr('applyDraft'), { type: 'warning' }) } catch { return }
  await act('apply')
  ElMessage.success(tr('appliedToast'))
}
const checks = computed<any[]>(() => detail.value.validations?.[0]?.report?.checks || [])
const waivableChecks = computed(() => checks.value.filter(c => !c.passed && c.waivable))
const statusType = (status: string) => ['approved', 'passed', 'verified'].includes(status) ? 'success' : ['validation_failed', 'failed', 'verify_failed'].includes(status) ? 'danger' : ['pending_review', 'needs_review'].includes(status) ? 'warning' : ['applied', 'verifying'].includes(status) ? 'primary' : 'info'
const gateLabel = (key: string) => key.startsWith('category:') ? `${tr('category')}: ${key.slice(9)}` : tr(key)
const load = async () => { loading.value = true; try { items.value = (await getImprovementCandidates(props.applicationId, filters)).data || [] } finally { loading.value = false } }
const show = async (row: any) => { approval.impact_scope = ''; approval.rollback_version_id = ''; approval.waivers = {}; detail.value = {}; detailVisible.value = true; detailLoading.value = true; try { detail.value = (await getImprovementCandidate(props.applicationId, row.id)).data; openReports.value = detail.value.validations?.[0] ? [detail.value.validations[0].id] : [] } finally { detailLoading.value = false } }
const openEditor = async (row?: any) => {
  editorLoading.value = true
  evidenceText.value = ''
  editingId.value = row?.id || ''; form.value = emptyForm()
  if (row) { const s = row.spec; form.value = { ...form.value, title: row.title, kind: row.kind, category: row.category, source: row.source, revision: row.revision, baseline_id: s.baseline_id, badcase_ids: s.sources.map((b: any) => b.id), risk: s.risk, patch: { ...form.value.patch, ...s.patch } } }
  editorVisible.value = true
  try {
    const [o, b] = await Promise.all([getCandidateOptions(props.applicationId), getEvaluationBadcases(props.applicationId)])
    versions.value = o.data.versions; badcases.value = b.data || []
    const pairs = await Promise.all(completedRuns.value.map(async r => { const run = (await getEvaluationRun(props.applicationId, r.id)).data; return [r.id, run.config?.application_version] }))
    baseVersions.value = Object.fromEntries(pairs)
    if (!row) form.value.baseline_id = completedRuns.value[0]?.id || ''
    if (!row && targets.value.length === 1) { form.value.patch.node_id = targets.value[0].id; form.value.patch.content = originalContent.value }
  } catch { editorVisible.value = false } finally { editorLoading.value = false }
}
const insertTemplate = () => { form.value.source = 'template'; form.value.patch.content = form.value.kind === 'skill_version' ? tr('skillTemplate') : form.value.kind === 'knowledge_task' ? tr('knowledgeTemplate') : tr('promptTemplate') }
const save = async () => {
  if (!form.value.title.trim() || !form.value.baseline_id || !selectedTarget.value || !form.value.patch.content.trim() || !form.value.risk.trim()) return ElMessage.warning(tr('required'))
  saving.value = true
  try { const res = await saveImprovementCandidate(props.applicationId, { ...form.value, draft_only: true }, editingId.value || undefined); editorVisible.value = false; await load(); await show(res.data); ElMessage.success(tr('saved')) } finally { saving.value = false }
}
const act = async (action: string, data: any = {}) => { saving.value = true; try { const r = await actionImprovementCandidate(props.applicationId, detail.value.id, { action, revision: detail.value.revision, ...data }); detail.value = r.data; openReports.value = detail.value.validations?.[0] ? [detail.value.validations[0].id] : []; await load() } finally { saving.value = false } }
const reasonAction = async (action: string) => { try { const r = await ElMessageBox.prompt(tr('reason'), tr(action), { inputType: 'textarea', inputValidator: value => Boolean(value?.trim()) || tr('required') }); await act(action, { reason: r.value }) } catch { /* cancellation or API feedback */ } }
const approve = async () => { if (!approval.impact_scope.trim() || !approval.rollback_version_id || waivableChecks.value.some(c => !approval.waivers[c.key]?.trim())) return ElMessage.warning(tr('required')); await act('approve', approval); approvalVisible.value = false; approval.impact_scope = ''; approval.waivers = {} }
// Opened from an online Badcase or an evaluation report finding: start a draft that already cites its source.
watch(() => props.preset, async preset => {
  if (!preset) return
  await openEditor()
  if (!editorVisible.value) return
  const badcase = preset.badcase
  if (badcase) {
    form.value.title = badcase.reason?.slice(0, 128) || ''
    form.value.category = options.category.includes(badcase.category) ? badcase.category : 'other'
    form.value.badcase_ids = [badcase.id]
  }
  const source = badcases.value.find((b: any) => b.badcase.id === badcase?.id)
  const event = preset.event || source?.event || {}
  if (preset.baselineId) form.value.baseline_id = preset.baselineId
  else if (event.application_version) form.value.baseline_id = completedRuns.value.find(r => baseVersions.value[r.id] === event.application_version)?.id || ''
  const nodes: any[] = Object.values(event.node_details || {})
  const nodeId = preset.nodeId || nodes.find(n => n.err_message)?.node_id || nodes.find(n => n.type === 'ai-chat-node')?.node_id
  form.value.patch.node_id = targets.value.some((n: any) => n.id === nodeId) ? nodeId : targets.value.length === 1 ? targets.value[0].id : ''
  if (selectedTarget.value) {
    form.value.kind = selectedTarget.value.type === 'ai-chat-node' ? 'prompt_patch' : 'workflow_patch'
    form.value.patch.field = form.value.kind === 'prompt_patch' ? 'system' : 'node_data'
    form.value.patch.content = originalContent.value
  }
  form.value.risk = badcase?.suggested_fix || badcase?.reason || preset.finding?.evidence || tr('reviewChange')
  evidenceText.value = [badcase?.reason, preset.finding?.nodeName, preset.finding?.evidence, event.question].filter(Boolean).join(' · ')
  if (!form.value.title) form.value.title = (event.question || preset.finding?.nodeName || tr('create')).slice(0, 128)
  emit('preset-used')
}, { immediate: true })
watch(() => [form.value.patch.node_id, form.value.patch.field, form.value.kind, form.value.baseline_id], () => {
  if (editorLoading.value || editingId.value || !selectedTarget.value) return
  if (selectedTarget.value.type !== 'ai-chat-node') form.value.kind = 'workflow_patch'
  if (form.value.kind === 'workflow_patch') form.value.patch.field = 'node_data'
  else if (form.value.kind === 'prompt_patch' && form.value.patch.field === 'node_data') form.value.patch.field = 'system'
  form.value.patch.content = originalContent.value
})
let timer: number | undefined, disposed = false
const poll = async () => { try { if (items.value.some(c => ['validating', 'verifying'].includes(c.status))) { await load(); if (detailVisible.value) { detail.value = (await getImprovementCandidate(props.applicationId, detail.value.id)).data } } } finally { if (!disposed) timer = window.setTimeout(() => { poll().catch(() => {}) }, 5000) } }
onMounted(async () => { try { await load(); versions.value = (await getCandidateOptions(props.applicationId)).data.versions } finally { if (!disposed) timer = window.setTimeout(() => { poll().catch(() => {}) }, 5000) } })
onUnmounted(() => { disposed = true; if (timer) window.clearTimeout(timer) })
</script>

<style scoped>
.candidate-panel { margin-top: 20px; border-radius: 8px; }
.candidate-detail-content { max-width: 1120px; margin: 0 auto; }
.candidate-detail-content > .panel-toolbar { padding: 16px; margin-bottom: 16px; background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.candidate-detail-content > h4 { padding-top: 18px; margin: 24px 0 12px; border-top: 1px solid var(--el-border-color-lighter); color: var(--el-text-color-primary); font-size: 14px; }
.candidate-detail-content > h4:first-of-type { border-top: 0; }
.candidate-detail-content > .el-descriptions { margin-bottom: 18px; }
.candidate-detail-content > .el-table { margin: 12px 0 20px; }
.candidate-detail-content > .diff, .candidate-detail-content > .release-info { margin: 12px 0 20px; }
.closure { margin: 16px 0; padding: 20px 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; background: var(--el-bg-color); }
.closure-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 18px 0 12px; justify-content: center; }
.closure-actions .el-button { margin-left: 0; }
.closure-answer { margin: 0; padding: 12px 16px; }
.panel-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.panel-toolbar p, .secondary { color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; }
.panel-toolbar p { margin: 6px 0 0; }
.candidate-filters { display: grid; grid-template-columns: minmax(0, 320px) 180px; gap: 10px; margin-bottom: 16px; }
.form-grid, .answer-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.answer-grid { padding: 16px; }
.full-width { width: 100%; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; }
.diff, .release-info { padding: 16px; background: var(--el-fill-color-lighter); border-radius: 6px; }
@media (max-width: 900px) { .candidate-filters, .form-grid, .answer-grid { grid-template-columns: 1fr; } }
</style>
