<template>
  <el-card class="release-panel" shadow="never">
    <template #header><div class="panel-heading"><div><strong>{{ tr('releaseTitle') }}</strong><el-text type="info">{{ tr('releaseHint') }}</el-text></div><el-button :loading="loading" @click="load">{{ tr('refresh') }}</el-button></div></template>
    <el-alert v-if="state.frozen" type="warning" :title="tr('releaseFrozen')" show-icon />
    <div class="release-summary">
      <el-tag type="success">{{ tr('currentVersion') }}: {{ state.current_version_id || '—' }}</el-tag>
      <el-tag v-if="state.rollout_id" type="warning">{{ tr('rolloutActive') }}</el-tag>
      <el-button v-if="!state.frozen" size="small" @click="mutate({ action: 'freeze', reason: tr('manualFreeze') })">{{ tr('freeze') }}</el-button>
      <el-button v-else size="small" @click="mutate({ action: 'unfreeze', reason: tr('manualUnfreeze') })">{{ tr('unfreeze') }}</el-button>
    </div>
    <el-table :data="state.releases || []" v-loading="loading" class="release-table">
      <el-table-column prop="version_id" :label="tr('version')" min-width="230" />
      <el-table-column prop="status" :label="tr('status')" width="130" />
      <el-table-column prop="percentage" :label="tr('trafficPercent')" width="110" />
      <el-table-column :label="tr('trafficMetrics')" min-width="240"><template #default="{ row }">{{ row.metrics?.count || 0 }} / {{ row.metrics?.latency_ms || '—' }} ms</template></el-table-column>
      <el-table-column :label="tr('actions')" width="230"><template #default="{ row }"><el-button v-if="row.status === 'prepared'" link type="primary" @click="mutate({ action: 'start', deployment_id: row.id, percentage: 10, subject_type: 'session', reason: tr('startReason') })">{{ tr('startRollout') }}</el-button><el-button v-if="row.status === 'running'" link @click="mutate({ action: 'stop', deployment_id: row.id, reason: tr('stopReason') })">{{ tr('stopRollout') }}</el-button><el-button v-if="row.status === 'promoted'" link type="danger" @click="mutate({ action: 'rollback', deployment_id: row.id, reason: tr('rollbackReason') })">{{ tr('rollback') }}</el-button></template></el-table-column>
    </el-table>
    <el-empty v-if="!loading && !(state.releases || []).length" :description="tr('noReleases')" />
    <el-divider />
    <strong>{{ tr('approvedCapabilities') }}</strong>
    <el-table :data="state.capabilities || []" v-loading="loading" class="release-table">
      <el-table-column prop="title" :label="tr('name')" min-width="220" />
      <el-table-column prop="kind" :label="tr('kind')" width="150" />
      <el-table-column prop="approved_by" :label="tr('approvedBy')" min-width="220" />
      <el-table-column :label="tr('actions')" width="150"><template #default="{ row }"><el-button link type="primary" @click="mutate({ action: 'prepare', capability_id: row.id, policy: {}, reason: tr('prepareReason') })">{{ tr('prepareRelease') }}</el-button></template></el-table-column>
    </el-table>
    <el-divider />
    <el-timeline><el-timeline-item v-for="audit in (state.audits || []).slice(0, 8)" :key="audit.id" :timestamp="new Date(audit.created_at).toLocaleString()">{{ audit.action }} · {{ audit.reason || '—' }}</el-timeline-item></el-timeline>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { actionEvaluationRelease, getEvaluationReleases } from '@/api/application/evaluation'
const props = defineProps<{ applicationId: string }>()
const { t } = useI18n()
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
const loading = ref(false)
const state = ref<any>({ releases: [], audits: [] })
const load = async () => { loading.value = true; try { state.value = (await getEvaluationReleases(props.applicationId)).data || state.value } finally { loading.value = false } }
const mutate = async (data: any) => { if (loading.value) return; loading.value = true; try { await actionEvaluationRelease(props.applicationId, { ...data, revision: state.value.revision }); ElMessage.success(tr('releaseUpdated')); await load() } catch { /* interceptor reports */ } finally { loading.value = false } }
onMounted(load)
</script>
<style scoped>
.release-panel { margin-top: 16px; }
.release-summary { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 16px 0; }
.release-table { margin-top: 12px; }
</style>
