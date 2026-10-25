<template>
  <div class="diagnosis-panel">
    <div v-if="steps.length" class="diagnosis-path" :aria-label="tr('tracePath')">
      <span class="diagnosis-path-label">{{ tr('tracePath') }}<template v-if="trace?.turn?.total > 1"> · {{ tr('traceTurn') }} {{ trace.turn.index }}/{{ trace.turn.total }}</template></span>
      <template v-for="(step, index) in steps" :key="step.runtime_node_id || index">
        <span v-if="index" class="diagnosis-path-arrow" aria-hidden="true">→</span>
        <el-tooltip :content="stepTip(step)" placement="top" :show-after="200">
          <span class="diagnosis-step" :class="{ failed: step.status === 'failed', located: located.has(step.node_id) }">
            {{ step.name }}<em v-if="step.branch"> · {{ step.branch.name ?? step.branch.id }}</em><em v-else-if="step.retrieval?.hit_count != null"> · {{ step.retrieval.hit_count }}</em>
          </span>
        </el-tooltip>
      </template>
    </div>
    <el-empty v-if="!findings.length" :image-size="48" :description="tr('diagNone')" />
    <article v-for="(finding, index) in findings" :key="index" class="diagnosis-item">
      <div class="diagnosis-head">
        <el-tag :type="AREA_TAG[finding.area]" effect="dark" size="small">{{ tr('area_' + finding.area) }}</el-tag>
        <strong>{{ t(`views.applicationEvaluation.ux.${finding.key}`, finding.params) }}</strong>
        <span v-if="finding.nodeName" class="diagnosis-node">{{ tr('diagNode') }} · {{ finding.nodeName }}</span>
      </div>
      <p class="diagnosis-fix">{{ tr(({ diagSearchSkipped: 'fixSearchSkipped', diagStaleLabel: 'fixStaleLabel' } as Record<string, string>)[finding.key] || 'fix_' + finding.area) }}</p>
      <pre v-if="finding.evidence" class="diagnosis-evidence">{{ finding.evidence }}</pre>
      <div class="diagnosis-actions">
        <el-button v-for="action in actionsOf(finding)" :key="action.label" size="small" :type="action.primary ? 'primary' : 'default'" @click="action.go">{{ tr(action.label) }}</el-button>
      </div>
    </article>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { isWorkFlow } from '@/utils/application'
import { AREA_TAG, type DiagnosisFinding } from './diagnosis'

const props = defineProps<{ findings: DiagnosisFinding[]; allowCandidate?: boolean; trace?: any }>()
const emit = defineEmits<{ candidate: [finding: DiagnosisFinding] }>()
const { t } = useI18n()
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
const route = useRoute()
const steps = computed<any[]>(() => Array.isArray(props.trace?.steps) ? props.trace.steps : [])
const located = computed(() => new Set(props.findings.map(f => f.nodeId).filter(Boolean)))
const stepTip = (step: any) => [step.type, step.status === 'failed' ? step.error : '', step.run_time != null ? `${Number(step.run_time).toFixed(2)}s` : '',
  step.retrieval ? `top_n ${step.retrieval.top_n ?? '—'} · similarity ${step.retrieval.similarity ?? '—'} · ${step.retrieval.search_mode ?? '—'}` : '',
  step.tool ? `${step.tool.name || step.tool.id || ''}` : ''].filter(Boolean).join(' · ')
const router = useRouter()
const open = (path: string) => window.open(router.resolve(path).href, '_blank')
const appConfig = () => {
  const { from, id, type } = route.params as Record<string, string>
  open(isWorkFlow(type) ? `/application/${from}/${id}/workflow` : `/application/${from}/${id}/${type}/setting`)
}
const actionsOf = (finding: DiagnosisFinding) => {
  const editNode = { label: isWorkFlow(String(route.params.type)) ? 'goWorkflowNode' : 'goAppSetting', go: appConfig, primary: true }
  if (finding.area === 'tool') return finding.nodeType === 'tool-lib-node' ? [{ label: 'goTool', go: () => open('/tool'), primary: true }, { ...editNode, primary: false }] : [editNode]
  const candidateAction = props.allowCandidate ? [{ label: 'goCandidate', go: () => emit('candidate', finding), primary: false }] : []
  if (finding.key === 'diagStaleLabel') return [{ label: 'goKnowledge', go: () => open('/knowledge'), primary: true }]
  if (finding.area === 'retrieval') return [editNode, { label: 'goKnowledge', go: () => open('/knowledge'), primary: false }, ...candidateAction]
  if (finding.area === 'prompt') return [editNode, ...(props.allowCandidate ? [{ label: 'goCandidate', go: () => emit('candidate', finding), primary: false }] : [])]
  if (finding.area === 'model') return [{ label: 'goModel', go: () => open('/model'), primary: true }, { ...editNode, primary: false }]
  return []
}
</script>
<style scoped>
.diagnosis-panel { display: flex; flex-direction: column; gap: 12px; }
.diagnosis-item { padding: 14px 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; background: var(--el-bg-color); }
.diagnosis-head { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.diagnosis-head strong { color: var(--el-text-color-primary); font-size: 14px; }
.diagnosis-node { color: var(--el-text-color-secondary); font-size: 12px; }
.diagnosis-fix { margin: 8px 0 0; color: var(--el-text-color-regular); font-size: 13px; line-height: 1.6; }
.diagnosis-evidence { max-height: 160px; margin: 10px 0 0; padding: 10px 12px; overflow: auto; border-radius: 6px; background: var(--el-fill-color-lighter); color: var(--el-text-color-regular); font-size: 12px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.diagnosis-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.diagnosis-actions .el-button { margin-left: 0; }
.diagnosis-path { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 10px 12px; border-radius: 8px; background: var(--el-fill-color-lighter); font-size: 12px; }
.diagnosis-path-label { margin-right: 4px; color: var(--el-text-color-secondary); }
.diagnosis-path-arrow { color: var(--el-text-color-placeholder); }
.diagnosis-step { padding: 2px 8px; border: 1px solid var(--el-border-color); border-radius: 4px; background: var(--el-bg-color); color: var(--el-text-color-regular); }
.diagnosis-step em { font-style: normal; color: var(--el-text-color-secondary); }
.diagnosis-step.located { border-color: var(--el-color-warning); }
.diagnosis-step.failed { border-color: var(--el-color-danger); color: var(--el-color-danger); }
</style>
