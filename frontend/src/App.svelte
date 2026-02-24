<script>
  import { onMount } from 'svelte'
  import Chat from './components/Chat.svelte'
  import PlanPanel from './components/PlanPanel.svelte'
  import SystemMetrics from './components/SystemMetrics.svelte'
  import Editor from './components/Editor.svelte'
  import FileTree from './components/FileTree.svelte'
  import Preview from './components/Preview.svelte'
  import Terminal from './components/Terminal.svelte'
  import Git from './components/Git.svelte'
  // ExpertSelector убран - используется только Виктория

  import { currentFile, openFiles, unsavedChanges, loadFile } from './stores/files.js'
  import { selectedExpert, messages, clearMessages, chatMode } from './stores/chat.js'

  let showPreview = false
  let showTerminal = false
  let leftPanelWidth = 250
  let rightPanelWidth = 400
  /** Вкладки как в Cursor: Чат | Агент | План, затем открытые файлы */
  let activeCenterTab = 'chat'
  let victoriaStatus = 'checking'
  let mlxStatus = 'checking'
  let isResizingLeft = false
  let isResizingRight = false
  let isResizingPreview = false

    onMount(async () => {
    // Проверка статуса Victoria и MLX
    async function checkStatus() {
      try {
        // Используем порт 8081 для Rust Gateway
        const response = await fetch(`http://${window.location.hostname}:8081/api/chat/status`)
        if (response.ok) {
          const data = await response.json()
          console.log('Status data:', data);
          // Статус Victoria: проверяем все возможные варианты ответа
          // 1. data.status === 'ok' (прямой ответ от бэкенда)
          // 2. data.victoria.status === 'ok' (вложенный ответ)
          const status = data.status || data.victoria?.status || 'unknown';

          if (status === 'healthy' || status === 'online' || status === 'ok') {
            victoriaStatus = 'healthy';
          } else {
            victoriaStatus = status;
          }
          // Статус MLX (fallback)
          mlxStatus = data.mlx?.status || 'unknown'
        }
      } catch (e) {
        victoriaStatus = 'offline'
        mlxStatus = 'unknown'
        console.error('Failed to check status:', e)
      }
    }

    await checkStatus()
    // Обновляем статус каждые 30 секунд
    setInterval(checkStatus, 30000)

    // Обработка изменения размера панелей
    function handleMouseMove(e) {
      if (isResizingLeft) {
        leftPanelWidth = Math.max(150, Math.min(500, e.clientX))
      } else if (isResizingRight) {
        const newWidth = window.innerWidth - e.clientX
        rightPanelWidth = Math.max(200, Math.min(600, newWidth))
      } else if (isResizingPreview) {
        rightPanelWidth = Math.max(200, Math.min(800, window.innerWidth - e.clientX))
      }
    }

    function handleMouseUp() {
      isResizingLeft = false
      isResizingRight = false
      isResizingPreview = false
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  })
</script>

<div class="h-screen flex flex-col bg-atra-dark">
  <!-- Header -->
  <header class="h-12 bg-atra-darker border-b border-atra-accent flex items-center px-4 justify-between">
    <div class="flex items-center gap-3">
      <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-atra-primary to-atra-secondary flex items-center justify-center font-bold text-sm">
        A
      </div>
      <h1 class="text-lg font-semibold">ATRA Web IDE</h1>
      <span class="text-xs text-gray-500 bg-atra-accent px-2 py-0.5 rounded">Singularity 14.0</span>
    </div>

    <div class="flex items-center gap-4">
      <!-- ExpertSelector скрыт - используется только Виктория -->

      <button
        class="px-3 py-1.5 rounded text-sm transition-colors hover:bg-opacity-80"
        class:bg-atra-primary={showPreview}
        class:bg-atra-accent={!showPreview}
        on:click={() => showPreview = !showPreview}
        title={showPreview ? 'Скрыть предпросмотр' : 'Показать предпросмотр'}
      >
        {showPreview ? '👁️ Скрыть' : '👁️ Показать'}
      </button>
      <button
        class="px-3 py-1.5 rounded text-sm transition-colors hover:bg-opacity-80"
        class:bg-atra-primary={showTerminal}
        class:bg-atra-accent={!showTerminal}
        on:click={() => showTerminal = !showTerminal}
        title={showTerminal ? 'Скрыть терминал' : 'Показать терминал'}
      >
        {showTerminal ? '⌨️ Скрыть' : '⌨️ Терминал'}
      </button>
    </div>
  </header>

  <!-- Main content -->
  <main class="flex-1 flex overflow-hidden">
    <!-- Left panel: File Tree -->
    <aside
      class="bg-atra-darker border-r border-atra-accent flex flex-col relative select-none"
      style="width: {leftPanelWidth}px"
    >
      <div class="p-2 border-b border-atra-accent text-xs text-gray-400 uppercase tracking-wider">
        Explorer
      </div>
      <div class="flex-1 overflow-auto">
        <FileTree />
      </div>
      <div
        class="absolute top-0 right-0 w-1 h-full cursor-col-resize hover:bg-atra-primary transition-colors bg-atra-accent"
        on:mousedown={(e) => {
          isResizingLeft = true
          e.preventDefault()
        }}
      ></div>
    </aside>

    <!-- Center: вкладки как в Cursor — Чат | Агент | План + файлы -->
    <section class="flex-1 flex flex-col min-w-0">
      <div class="h-9 bg-atra-darker border-b border-atra-accent flex items-center px-2 gap-1 overflow-x-auto">
        <div
          class="px-3 py-1 rounded-t text-sm flex items-center gap-2 transition-colors cursor-pointer shrink-0 {activeCenterTab === 'chat' ? 'bg-atra-dark border-b-2 border-atra-primary' : 'bg-atra-darker hover:bg-atra-accent/30'}"
          on:click={() => { activeCenterTab = 'chat'; chatMode.set('ask'); }}
          title="Чат (Ask: быстрый ответ)"
        >
          <span class="text-gray-300">💬</span>
          <span class="font-medium">Чат</span>
        </div>
        <div
          class="px-3 py-1 rounded-t text-sm flex items-center gap-2 transition-colors cursor-pointer shrink-0 {activeCenterTab === 'agent' ? 'bg-atra-dark border-b-2 border-atra-primary' : 'bg-atra-darker hover:bg-atra-accent/30'}"
          on:click={() => { activeCenterTab = 'agent'; chatMode.set('agent'); }}
          title="Агент с шагами (мысли, действия)"
        >
          <span class="text-gray-300">∞</span>
          <span class="font-medium">Агент</span>
        </div>
        <div
          class="px-3 py-1 rounded-t text-sm flex items-center gap-2 transition-colors cursor-pointer shrink-0 {activeCenterTab === 'plan' ? 'bg-atra-dark border-b-2 border-atra-primary' : 'bg-atra-darker hover:bg-atra-accent/30'}"
          on:click={() => activeCenterTab = 'plan'}
          title="Только план (без выполнения)"
        >
          <span class="text-gray-300">📋</span>
          <span class="font-medium">План</span>
        </div>
        <div
          class="px-3 py-1 rounded-t text-sm flex items-center gap-2 transition-colors cursor-pointer shrink-0 {activeCenterTab === 'monitoring' ? 'bg-atra-dark border-b-2 border-atra-primary' : 'bg-atra-darker hover:bg-atra-accent/30'}"
          on:click={() => activeCenterTab = 'monitoring'}
          title="Мониторинг системы (CPU, память, диск)"
        >
          <span class="text-gray-300">📊</span>
          <span class="font-medium">Мониторинг</span>
        </div>
        <div
          class="px-3 py-1 rounded-t text-sm flex items-center gap-2 transition-colors cursor-pointer shrink-0 {activeCenterTab === 'git' ? 'bg-atra-dark border-b-2 border-atra-primary' : 'bg-atra-darker hover:bg-atra-accent/30'}"
          on:click={() => activeCenterTab = 'git'}
          title="Git: status, diff, log, commit"
        >
          <span class="text-gray-300">📂</span>
          <span class="font-medium">Git</span>
        </div>
        {#each $openFiles as file}
          <div
            class="px-3 py-1 rounded-t text-sm flex items-center gap-2 transition-colors cursor-pointer shrink-0 {activeCenterTab === file.path ? 'bg-atra-dark' : 'bg-atra-darker hover:bg-atra-accent/30'}"
            on:click={() => { activeCenterTab = file.path; loadFile(file.path); }}
            title={file.path}
          >
            <span class="text-gray-300 truncate max-w-[200px]">{file.name}</span>
            {#if $unsavedChanges[file.path]}
              <span class="w-2 h-2 rounded-full bg-yellow-500" title="Несохраненные изменения"></span>
            {/if}
            <button
              class="text-gray-500 hover:text-white text-xs ml-1"
              on:click|stopPropagation={() => {
                import('./stores/files.js').then(m => m.closeFile(file.path))
                if (activeCenterTab === file.path) activeCenterTab = 'chat'
              }}
              title="Закрыть файл"
            >
              ×
            </button>
          </div>
        {/each}
      </div>

      <div class="flex-1 overflow-hidden flex flex-col">
        {#if activeCenterTab === 'chat'}
          <div class="h-full flex flex-col border-b border-atra-accent/50">
            <div class="p-2 border-b border-atra-accent/50 text-xs text-gray-400 uppercase tracking-wider flex justify-between items-center shrink-0">
              <span>Чат — Виктория</span>
              <div class="flex items-center gap-2">
                {#if $selectedExpert}
                  <span class="text-atra-primary">{$selectedExpert.name}</span>
                {/if}
                {#if $messages.length > 0}
                  <button
                    class="text-gray-500 hover:text-white transition-colors text-xs"
                    on:click={() => clearMessages()}
                    title="Очистить чат"
                  >
                    🗑️
                  </button>
                {/if}
              </div>
            </div>
            <div class="flex-1 min-h-0">
              <Chat centerTab="chat" on:switchToAgent={() => { activeCenterTab = 'agent'; chatMode.set('agent'); }} />
            </div>
          </div>
        {:else if activeCenterTab === 'agent'}
          <div class="h-full flex flex-col border-b border-atra-accent/50">
            <div class="p-2 border-b border-atra-accent/50 text-xs text-gray-400 uppercase tracking-wider flex justify-between items-center shrink-0">
              <span>Агент — Виктория (шаги: мысли, действия)</span>
              <div class="flex items-center gap-2">
                {#if $selectedExpert}
                  <span class="text-atra-primary">{$selectedExpert.name}</span>
                {/if}
                {#if $messages.length > 0}
                  <button
                    class="text-gray-500 hover:text-white transition-colors text-xs"
                    on:click={() => clearMessages()}
                    title="Очистить чат"
                  >
                    🗑️
                  </button>
                {/if}
              </div>
            </div>
            <div class="flex-1 min-h-0">
              <Chat centerTab="agent" />
            </div>
          </div>
        {:else if activeCenterTab === 'plan'}
          <PlanPanel />
        {:else if activeCenterTab === 'monitoring'}
          <SystemMetrics />
        {:else if activeCenterTab === 'git'}
          <Git />
        {:else}
          <div class="flex-1 min-h-0">
            <Editor />
          </div>
        {/if}
      </div>
    </section>
    <!-- Панель предпросмотра справа: открывается по кнопке «Показать» при любом табе -->
    {#if showPreview}
      <div
        class="w-1 flex-shrink-0 bg-atra-accent cursor-col-resize hover:bg-atra-primary transition-colors"
        role="separator"
        aria-label="Изменить ширину предпросмотра"
        on:mousedown={(e) => {
          isResizingPreview = true
          e.preventDefault()
        }}
      ></div>
      <div class="flex flex-col min-w-0" style="width: {rightPanelWidth}px; max-width: 60%;">
        <div class="p-2 border-b border-atra-accent text-xs text-gray-400 uppercase tracking-wider shrink-0">Предпросмотр</div>
        <div class="flex-1 min-h-0 overflow-auto">
          <Preview />
        </div>
      </div>
    {/if}
  </main>

  <!-- Terminal panel (xterm.js) -->
  {#if showTerminal}
    <div class="h-48 flex-shrink-0 border-t border-atra-accent flex flex-col bg-atra-darker">
      <div class="px-2 py-1 border-b border-atra-accent text-xs text-gray-400 uppercase tracking-wider">
        Terminal
      </div>
      <div class="flex-1 min-h-0">
        <Terminal />
      </div>
    </div>
  {/if}

  <!-- Status bar -->
  <footer class="h-6 bg-atra-darker border-t border-atra-accent flex items-center px-4 text-xs text-gray-500 justify-between">
    <div class="flex items-center gap-4">
      <span id="status-ready">Ready</span>
      {#if $currentFile}
        <span class="truncate max-w-[300px]" title={$currentFile.path}>{$currentFile.path}</span>
        {#if $unsavedChanges[$currentFile.path]}
          <span class="text-yellow-500">●</span>
          <span class="text-yellow-500">Несохранено</span>
        {/if}
      {/if}
    </div>
    <div class="flex items-center gap-4">
      {#if $currentFile}
        <span>UTF-8</span>
        <span>Ln 1, Col 1</span>
      {/if}
      <span id="victoria-status" class="flex items-center gap-1">
        {#if victoriaStatus === 'healthy' || victoriaStatus === 'online' || victoriaStatus === 'ok'}
          <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
          <span>Victoria: Online</span>
        {:else if victoriaStatus === 'checking'}
          <span class="w-2 h-2 rounded-full bg-yellow-500 animate-pulse"></span>
          <span>Victoria: Checking...</span>
        {:else if mlxStatus === 'healthy'}
          <span class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
          <span>AI: MLX (Victoria Offline)</span>
        {:else}
          <span class="w-2 h-2 rounded-full bg-orange-500"></span>
          <span>Victoria: Offline</span>
        {/if}
      </span>
    </div>
  </footer>
</div>
