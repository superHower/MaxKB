import { get, post, postUpload } from '@/request/index'
import type { Ref } from 'vue'
import type { Result } from '@/request/Result'
import useStore from '@/stores'

const prefix = (applicationId: string) => {
  const { user } = useStore()
  return `/workspace/${user.getWorkspaceId()}/application/${applicationId}/evaluation`
}
export const getEvaluationDatasets = (id: string, loading?: Ref<boolean>): Promise<Result<any[]>> =>
  get(`${prefix(id)}/datasets`, {}, loading)
export const uploadEvaluationDataset = (
  id: string,
  name: string,
  file: File,
  loading?: Ref<boolean>,
): Promise<Result<any>> => {
  const form = new FormData()
  form.append('name', name)
  form.append('file', file)
  return postUpload(`${prefix(id)}/datasets`, form, undefined, undefined, loading).request
}
export const getEvaluationRuns = (id: string, loading?: Ref<boolean>): Promise<Result<any[]>> =>
  get(`${prefix(id)}/runs`, {}, loading)
export const startEvaluation = (
  id: string,
  data: any,
  loading?: Ref<boolean>,
): Promise<Result<any>> => post(`${prefix(id)}/runs`, data, undefined, loading)
export const getEvaluationRun = (
  id: string,
  runId: string,
  loading?: Ref<boolean>,
): Promise<Result<any>> => get(`${prefix(id)}/runs/${runId}`, {}, loading)
export const downloadEvaluationReport = (id: string, runId: string, format: 'json' | 'md') =>
  fetch(`${window.MaxKB?.prefix || '/admin'}/api${prefix(id)}/runs/${runId}?format=${format}`, {
    headers: { Authorization: `Bearer ${useStore().login.getToken()}` },
  })

export const getEvaluationEvents = (id: string, params?: any, loading?: Ref<boolean>) =>
  get(`${prefix(id)}/events`, params, loading)
export const getEvaluationSamples = (id: string, params?: any, loading?: Ref<boolean>) =>
  get(`${prefix(id)}/samples`, params, loading)
export const sampleEvaluationEvents = (id: string, data: any, loading?: Ref<boolean>) =>
  post(`${prefix(id)}/samples`, data, undefined, loading)
export const annotateEvaluationSample = (id: string, sampleId: string, data: any, loading?: Ref<boolean>) =>
  post(`${prefix(id)}/samples/${sampleId}/annotation`, data, undefined, loading)
