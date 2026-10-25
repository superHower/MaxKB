<template>
  <div class="judge-settings">
    <el-form-item :label="tr('judgeMaxTokens')"><el-input-number v-model="value.max_tokens" :min="256" :max="32768" :step="256" :precision="0" /></el-form-item>
    <el-form-item :label="tr('judgeTemperature')"><el-input-number v-model="value.temperature" :min="0" :max="1" :step="0.1" :precision="2" /></el-form-item>
    <el-form-item :label="tr('judgeThinking')"><el-select v-model="value.thinking"><el-option v-for="mode in ['auto', 'disabled', 'enabled']" :key="mode" :value="mode" :label="tr('judgeThinking_' + mode)" /></el-select></el-form-item>
    <el-form-item :label="tr('judgeJsonMode')"><el-switch v-model="value.json_mode" /></el-form-item>
    <el-alert :title="tr('judgeSettingsHelp')" type="info" :closable="false" />
  </div>
</template>
<script setup lang="ts">
import { useI18n } from 'vue-i18n'
export interface JudgeOptions { max_tokens: number; temperature: number; thinking: string; json_mode: boolean }
const value = defineModel<JudgeOptions>({ required: true })
const { t } = useI18n()
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
</script>
