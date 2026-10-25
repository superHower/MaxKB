<template>
  <el-tooltip :content="text" placement="top" :show-after="200">
    <button type="button" class="evaluation-help" :aria-label="text"><el-icon><QuestionFilled /></el-icon></button>
  </el-tooltip>
</template>
<script setup lang="ts">
import { QuestionFilled } from '@element-plus/icons-vue'
defineProps<{ text: string }>()
</script>
<style scoped>
.evaluation-help { display: inline-flex; align-items: center; justify-content: center; vertical-align: middle; padding: 3px; border: 0; border-radius: 4px; background: transparent; color: var(--el-text-color-placeholder); cursor: help; font-size: 14px; }
.evaluation-help:hover, .evaluation-help:focus-visible { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
</style>
