import { defineAsyncComponent, type App } from 'vue'
import type { Dict } from '@/api/type/common'
const DynamicsForm = defineAsyncComponent(() => import('@/components/dynamics-form/index.vue'))
let components: Dict<any> = import.meta.glob('@/components/dynamics-form/**/**.vue', {
  import: 'default',
})
components = {
  ...components,
  ...import.meta.glob('@/components/dynamics-form/**/**/**.vue', {
    import: 'default',
  }),
}

const install = (app: App) => {
  Object.keys(components).forEach((key: string) => {
    const commentName: string = key
      .substring(key.lastIndexOf('/') + 1, key.length)
      .replace('.vue', '')
    if (key !== '/src/components/dynamics-form/constructor/index.vue') {
      app.component(commentName, defineAsyncComponent(components[key]))
    }
  })
  app.component('DynamicsForm', DynamicsForm)
}
export default { install }
