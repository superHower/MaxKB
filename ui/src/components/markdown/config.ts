import {getDefaultWhiteList} from 'xss'
import {config, XSSPlugin} from 'md-editor-v3'
import screenfull from 'screenfull'
import katex from 'katex'
import 'katex/dist/katex.min.css'

import Cropper from 'cropperjs'
import 'cropperjs/dist/cropper.css'

import mermaid from 'mermaid'

import highlight from 'highlight.js'
import 'highlight.js/styles/atom-one-dark.css'

config({
  editorExtensions: {
    highlight: {
      instance: highlight,
    },
    screenfull: {
      instance: screenfull,
    },
    katex: {
      instance: katex,
    },
    cropper: {
      instance: Cropper,
    },
    mermaid: {
      instance: mermaid,
    },
  },
  markdownItPlugins(plugins) {
    return [
      ...plugins,
      {
        type: 'xss',
        plugin: XSSPlugin,
        options: {
          xss() {
            return {
              whiteList: Object.assign({}, getDefaultWhiteList(), {
                video: ['src', 'controls', 'width', 'height', 'preload', 'playsinline'],
                source: ['src', 'type'],
                a: ['href', 'style'],
                input: ['class', 'disabled', 'type', 'checked'],
                sup: ['data-title'],
                iframe: [
                  'class',
                  'width',
                  'height',
                  'src',
                  'title',
                  'border',
                  'frameborder',
                  'framespacing',
                  'allow',
                  'allowfullscreen',
                ],
              }),
              onTagAttr: (tag: string, name: any, value: any) => {
                if (tag === 'video') {
                  // 禁止自动播放
                  if (name === 'autoplay') return ''

                  // 限制 preload
                  if (name === 'preload' && !['none', 'metadata'].includes(value)) {
                    return 'preload="metadata"'
                  }
                }
                return undefined
              },
            }
          },
        },
      },
    ]
  },
})
