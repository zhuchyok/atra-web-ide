<script>
  import { onMount, onDestroy } from 'svelte'
  import { EditorState } from '@codemirror/state'
  import { EditorView, keymap, lineNumbers, highlightActiveLineGutter, highlightSpecialChars, drawSelection, dropCursor, rectangularSelection, crosshairCursor, highlightActiveLine } from '@codemirror/view'
  import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
  import { javascript } from '@codemirror/lang-javascript'
  import { python } from '@codemirror/lang-python'
  import { html } from '@codemirror/lang-html'
  import { css } from '@codemirror/lang-css'
  import { json, jsonParseLinter } from '@codemirror/lang-json'
  import { markdown } from '@codemirror/lang-markdown'
  import { autocompletion, completionKeymap, closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'
  import { lintGutter, lintKeymap } from '@codemirror/lint'
  import { currentFile, saveFile, markUnsaved } from '../stores/files.js'
  
  let editorContainer
  let editorView
  
  // AI автодополнение через Victoria API
  async function aiAutocomplete(context) {
    const { state, pos } = context
    const code = state.doc.toString()
    const line = state.doc.lineAt(pos)
    const filename = $currentFile?.name || 'untitled'
    
    try {
      const response = await fetch('/api/editor/autocomplete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: code.substring(0, pos),
          filename: filename,
          line: line.number,
          column: pos - line.from
        })
      })
      
      if (response.ok) {
        const data = await response.json()
        return {
          from: pos,
          options: data.completions.map(c => ({
            label: c.label,
            type: c.type,
            detail: c.detail,
            apply: (view, completion, from, to) => {
              view.dispatch({
                changes: { from, to, insert: c.insert || c.label }
              })
            }
          }))
        }
      }
    } catch (e) {
      console.error('Autocomplete error:', e)
    }
    
    return null
  }
  
  // Linting через backend
  function getLinter(filename) {
    return async (view) => {
      const code = view.state.doc.toString()
      if (!code.trim()) return []
      
      try {
        const response = await fetch('/api/editor/lint', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code: code,
            filename: filename || 'untitled'
          })
        })
        
        if (response.ok) {
          const data = await response.json()
          return data.errors.map(err => {
            const line = view.state.doc.line(Math.min(err.line, view.state.doc.lines))
            return {
              from: line.from + Math.max(0, (err.column - 1)),
              to: line.from + Math.max(1, err.column),
              message: err.message,
              severity: err.severity === 'error' ? 'error' : err.severity === 'warning' ? 'warning' : 'info'
            }
          })
        }
      } catch (e) {
        console.error('Lint error:', e)
      }
      
      return []
    }
  }
  
  // Определение языка по расширению
  function getLanguageExtension(filename) {
    if (!filename) return []
    
    const parts = filename.split('.')
    const ext = parts.length > 1 ? parts[parts.length - 1].toLowerCase() : ''
    const extensions = []
    
    switch (ext) {
      case 'js':
      case 'jsx':
      case 'ts':
      case 'tsx':
        extensions.push(javascript())
        break
      case 'py':
        extensions.push(python())
        break
      case 'html':
      case 'svelte':
        extensions.push(html())
        break
      case 'css':
      case 'scss':
        extensions.push(css())
        break
      case 'json':
        extensions.push(json())
        extensions.push(jsonParseLinter()) // Встроенный JSON linter
        break
      case 'md':
        extensions.push(markdown())
        break
    }
    
    // Добавляем AI автодополнение для всех языков
    extensions.push(autocompletion({
      override: [aiAutocomplete]
    }))
    
    // Добавляем linting
    if (filename) {
      extensions.push(lintGutter())
      extensions.push(getLinter(filename))
    }
    
    return extensions
  }
  
  // Тёмная тема
  const darkTheme = EditorView.theme({
    '&': {
      height: '100%',
      backgroundColor: '#16213e'
    },
    '.cm-content': {
      caretColor: '#667eea',
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      fontSize: '14px'
    },
    '.cm-cursor': {
      borderLeftColor: '#667eea'
    },
    '&.cm-focused .cm-selectionBackground, ::selection': {
      backgroundColor: 'rgba(102, 126, 234, 0.3)'
    },
    '.cm-activeLine': {
      backgroundColor: 'rgba(102, 126, 234, 0.1)'
    },
    '.cm-gutters': {
      backgroundColor: '#1a1a2e',
      color: '#666',
      border: 'none',
      borderRight: '1px solid #0f3460'
    },
    '.cm-activeLineGutter': {
      backgroundColor: 'rgba(102, 126, 234, 0.2)'
    }
  }, { dark: true })
  
  function initEditor(content = '', filename = '') {
    if (editorView) {
      editorView.destroy()
    }
    
    const state = EditorState.create({
      doc: content,
      extensions: [
        lineNumbers(),
        highlightActiveLineGutter(),
        highlightSpecialChars(),
        history(),
        drawSelection(),
        dropCursor(),
        rectangularSelection(),
        crosshairCursor(),
        highlightActiveLine(),
        keymap.of([
          ...defaultKeymap,
          ...historyKeymap,
          ...completionKeymap,
          ...closeBracketsKeymap,
          ...lintKeymap,
          {
            key: 'Mod-s',
            run: () => {
              handleSave()
              return true
            }
          }
        ]),
        closeBrackets(), // Автозакрытие скобок
        ...getLanguageExtension(filename),
        darkTheme,
        EditorView.updateListener.of((update) => {
          if (update.docChanged && $currentFile) {
            markUnsaved($currentFile.path, update.state.doc.toString())
          }
        })
      ]
    })
    
    editorView = new EditorView({
      state,
      parent: editorContainer
    })
  }
  
  async function handleSave() {
    if (!$currentFile) return
    
    const content = editorView.state.doc.toString()
    const success = await saveFile($currentFile.path, content)
    
    if (success) {
      // Показываем уведомление о сохранении
      const notification = document.createElement('div')
      notification.className = 'fixed top-4 right-4 bg-green-600 text-white px-4 py-2 rounded-lg shadow-lg z-50'
      notification.textContent = '✅ Файл сохранен'
      document.body.appendChild(notification)
      setTimeout(() => notification.remove(), 2000)
    } else {
      const notification = document.createElement('div')
      notification.className = 'fixed top-4 right-4 bg-red-600 text-white px-4 py-2 rounded-lg shadow-lg z-50'
      notification.textContent = '❌ Ошибка сохранения'
      document.body.appendChild(notification)
      setTimeout(() => notification.remove(), 3000)
    }
  }
  
  onMount(() => {
    if ($currentFile) {
      initEditor($currentFile.content, $currentFile.name)
    } else {
      initEditor('// Welcome to ATRA Web IDE\n// Open a file to start editing', '')
    }
  })
  
  onDestroy(() => {
    if (editorView) {
      editorView.destroy()
    }
  })
  
  // Реакция на изменение файла
  $: if ($currentFile) {
    if (editorView) {
      const currentContent = editorView.state.doc.toString()
      // Обновляем только если содержимое действительно изменилось
      if (currentContent !== $currentFile.content) {
        initEditor($currentFile.content, $currentFile.name)
      }
    } else {
      // Инициализируем редактор при первом открытии файла
      initEditor($currentFile.content, $currentFile.name)
    }
  } else if (editorView) {
    // Если файл закрыт, показываем welcome message
    initEditor('// Welcome to ATRA Web IDE\n// Open a file to start editing', '')
  }
</script>

<div class="h-full w-full bg-atra-darker" bind:this={editorContainer}>
  {#if !$currentFile}
    <div class="h-full flex items-center justify-center text-gray-500">
      <div class="text-center">
        <div class="text-6xl mb-4 opacity-30">📄</div>
        <p class="text-lg">No file open</p>
        <p class="text-sm mt-2">Select a file from the explorer to edit</p>
      </div>
    </div>
  {/if}
</div>

<style>
  :global(.cm-editor) {
    height: 100%;
  }
</style>
