<script>
  import { onMount, afterUpdate, createEventDispatcher } from 'svelte'
  import { fly } from 'svelte/transition'
  import { marked } from 'marked'
  import hljs from 'highlight.js'
  import { messages, isLoading, isStreaming, error, sendMessage, loadExperts, selectedExpert, clearMessages, chatMode } from '../stores/chat.js'

  const dispatch = createEventDispatcher()

  /** Вкладка центральной панели: 'chat' | 'agent' | 'plan'. Режим задаётся вкладкой: Чат = ask, Агент = agent (без дублирования кнопок). */
  export let centerTab = 'chat'

  let inputValue = ''
  let messagesContainer
  $: if (centerTab === 'agent') { chatMode.set('agent') }
  $: if (centerTab === 'chat') { chatMode.set('ask') }
  $: lastMessage = $messages.length > 0 ? $messages[$messages.length - 1] : null
  // Показывать курсор только у того сообщения, которое сейчас стримится (последнее по id)
  $: isStreamingLast = $isStreaming && lastMessage && lastMessage.role === 'assistant'

  // Настройка marked
  marked.setOptions({
    breaks: true,
    gfm: true
  })

  onMount(() => {
    loadExperts()
    // Debug: подписка на изменения сообщений
    messages.subscribe(msgs => {
      console.log('Messages updated:', msgs.length, msgs.map(m => m.content?.slice(0, 50)))
    })
  })

  afterUpdate(() => {
    // Автоскролл к последнему сообщению
    if (messagesContainer) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight
    }
  })

  function handleSubmit() {
    if (!inputValue.trim() || $isLoading) return

    sendMessage(inputValue.trim())
    inputValue = ''
  }

  function handleKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSubmit()
    }
  }

  function renderMarkdown(content) {
    if (!content) return ''
    try {
      return marked.parse(content)
    } catch (e) {
      console.error('Markdown error:', e)
      return content
    }
  }
</script>

<div class="h-full flex flex-col bg-atra-dark">
  <!-- Режим задаётся вкладками: Чат = Ask, Агент = Агент, План = отдельная вкладка (кнопки «Режим» убраны, дублирования нет) -->

  <!-- Шаги агента (панель во время стриминга — как в Cursor, с анимацией появления) -->
  {#if $isStreaming && lastMessage && lastMessage.role === 'assistant' && lastMessage.steps && lastMessage.steps.length > 0}
    <div class="agent-steps-panel shrink-0 border-b border-atra-accent/50 bg-atra-darker/80 px-4 py-3 cursor-style-panel">
      <div class="text-xs font-semibold text-atra-primary uppercase tracking-wider mb-2 flex items-center gap-2">
        <span class="cursor-thinking-dots">
          <span></span><span></span><span></span>
        </span>
        Шаги агента
      </div>
      <div class="agent-steps-timeline flex flex-col gap-1">
        {#each lastMessage.steps as step, i (step.stepType + step.title + i)}
          <div
            class="agent-step-badge step-{step.stepType}"
            in:fly={{ y: -8, duration: 200, delay: i * 60 }}
            out:fly={{ y: -4, duration: 150 }}
          >
            <span class="step-icon">{#if step.stepType === 'thought'}💭{:else if step.stepType === 'exploration'}🔍{:else if step.stepType === 'action'}⚡{:else}•{/if}</span>
            <span class="step-title">{step.title}</span>
            {#if step.content}
              <span class="step-desc">— {step.content}</span>
            {/if}
            {#if step.title === 'Рекомендация'}
              <button
                type="button"
                class="agent-suggestion-btn"
                on:click|stopPropagation={() => dispatch('switchToAgent')}
              >
                Перейти в Агент
              </button>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Messages -->
  <div
    class="flex-1 overflow-y-auto p-4 space-y-4"
    bind:this={messagesContainer}
  >
    {#if $messages.length === 0}
      <div class="text-center text-gray-500 mt-8">
        <div class="text-4xl mb-4">👋</div>
        <p class="text-lg">Привет! Я {$selectedExpert?.name || 'ассистент'}.</p>
        <p class="text-sm mt-2">Спросите меня что-нибудь о коде или проекте.</p>
        {#if $selectedExpert?.role}
          <p class="text-xs mt-1 text-gray-600">{$selectedExpert.role}</p>
        {/if}
      </div>
    {/if}

    {#each $messages as message, idx (message.id + '-' + (message.content?.length || 0) + '-' + (message.steps?.length || 0))}
      <div class="chat-message {message.role === 'user' ? 'ml-8' : 'mr-8'}">
        <div class="flex items-start gap-3 {message.role === 'user' ? 'flex-row-reverse' : ''}">
          <!-- Avatar -->
          <div class="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm font-medium
            {message.role === 'user'
              ? 'bg-atra-primary'
              : 'bg-gradient-to-br from-atra-primary to-atra-secondary'}
          ">
            {message.role === 'user' ? 'У' : message.expertName?.[0] || 'A'}
          </div>

          <!-- Content -->
          <div class="flex-1 min-w-0">
            {#if message.role === 'assistant' && message.expertName}
              <div class="text-xs text-atra-primary mb-1">{message.expertName}</div>
            {/if}

            <!-- Шаги агента (как в Cursor): вертикальная линия, появление по одному -->
            {#if message.role === 'assistant' && message.steps && message.steps.length > 0}
              <div class="agent-steps cursor-style-steps mb-3">
                {#each message.steps as step, i (message.id + '-step-' + i)}
                  <div
                    class="agent-step step-{step.stepType}"
                    data-step-type={step.stepType}
                    in:fly={{ x: -12, duration: 220, delay: i * 50 }}
                  >
                    <div class="step-dot"></div>
                    <div class="step-body">
                      <div class="step-header">
                        <span class="step-icon">
                          {#if step.stepType === 'thought'}💭
                          {:else if step.stepType === 'exploration'}🔍
                          {:else if step.stepType === 'action'}⚡
                          {:else if step.stepType === 'clarification'}❓
                          {:else}•
                          {/if}
                        </span>
                        <span class="step-title">{step.title}{#if step.duration} <span class="step-duration">({step.duration})</span>{/if}</span>
                      </div>
                      {#if step.content}
                        <div class="step-content">{step.content}</div>
                      {/if}
                      {#if step.title === 'Рекомендация'}
                        <button
                          type="button"
                          class="agent-suggestion-btn"
                          on:click|stopPropagation={() => dispatch('switchToAgent')}
                        >
                          Перейти в Агент
                        </button>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}

            <!-- Блок ответа + мигающий курсор при стриминге (как в Cursor) -->
            <div class="rounded-lg p-3
              {message.role === 'user'
                ? 'bg-atra-primary text-white'
                : 'bg-atra-darker border border-atra-accent'}
            ">
              {#if message.role === 'assistant'}
                {#key message.id}
                  <div class="prose prose-invert prose-sm max-w-none relative break-words">
                    {#if message.content}
                      {@html renderMarkdown(message.content)}
                      {#if isStreamingLast && lastMessage && message.id === lastMessage.id}
                        <span class="streaming-cursor" aria-hidden="true">▌</span>
                      {/if}
                    {:else}
                      <span class="text-gray-500">Агент думает</span>
                      <span class="cursor-thinking-inline">
                        <span>.</span><span>.</span><span>.</span>
                      </span>
                    {/if}
                  </div>
                {/key}
              {:else}
                <p class="whitespace-pre-wrap">{message.content}</p>
              {/if}
            </div>

            <div class="text-xs text-gray-500 mt-1">
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          </div>
        </div>
      </div>
    {/each}

    <!-- Индикатор «агент работает» — как в Cursor (плавные точки) -->
    {#if $isStreaming}
      <div class="cursor-agent-working ml-8 flex items-center gap-2 text-gray-400 text-sm py-2">
        <span class="cursor-thinking-dots large">
          <span></span><span></span><span></span>
        </span>
        <span>Агент работает…</span>
      </div>
    {/if}

    {#if $error}
      <div class="bg-red-900/30 border border-red-700 rounded-lg p-3 text-red-300 text-sm flex items-center justify-between">
        <span>{$error}</span>
        <button
          class="text-red-400 hover:text-red-200 ml-2"
          on:click={() => error.set(null)}
        >
          ×
        </button>
      </div>
    {/if}
  </div>

  <!-- Input -->
  <div class="p-4 border-t border-atra-accent">
    <form on:submit|preventDefault={handleSubmit} class="flex gap-2">
      <textarea
        bind:value={inputValue}
        on:keydown={handleKeydown}
        placeholder="Напишите сообщение..."
        class="flex-1 bg-atra-darker border border-atra-accent rounded-lg px-4 py-2 text-sm resize-none focus:outline-none focus:border-atra-primary transition-colors"
        rows="2"
        disabled={$isLoading}
      ></textarea>

      <button
        type="submit"
        class="px-4 py-2 bg-atra-primary rounded-lg text-sm font-medium hover:bg-opacity-90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        disabled={$isLoading || !inputValue.trim()}
      >
        {#if $isLoading}
          <span class="animate-spin">⏳</span>
        {:else}
          Отправить
        {/if}
      </button>
    </form>
  </div>
</div>

<style>
  /* ——— Стиль Cursor: вертикальная линия шагов, точки «думает», курсор ——— */

  /* Точки «думает» (как в Cursor) */
  .cursor-thinking-dots {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .cursor-thinking-dots span {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: var(--atra-primary, #6366f1);
    animation: cursor-dot 1.2s ease-in-out infinite both;
  }
  .cursor-thinking-dots span:nth-child(1) { animation-delay: 0s; }
  .cursor-thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
  .cursor-thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
  .cursor-thinking-dots.large span {
    width: 6px;
    height: 6px;
  }
  @keyframes cursor-dot {
    0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
    40% { opacity: 1; transform: scale(1); }
  }
  .cursor-thinking-inline span {
    animation: cursor-dot 1.2s ease-in-out infinite both;
  }
  .cursor-thinking-inline span:nth-child(2) { animation-delay: 0.2s; }
  .cursor-thinking-inline span:nth-child(3) { animation-delay: 0.4s; }

  /* Мигающий курсор в конце стрима (как в Cursor) */
  .streaming-cursor {
    display: inline-block;
    width: 2px;
    height: 1em;
    margin-left: 2px;
    vertical-align: text-bottom;
    background: var(--atra-primary, #6366f1);
    animation: cursor-blink 0.8s step-end infinite;
  }
  @keyframes cursor-blink {
    50% { opacity: 0; }
  }

  /* Шаги агента в сообщении: вертикальная линия + точки (как в Cursor) */
  .agent-steps.cursor-style-steps {
    font-size: 0.8125rem;
    position: relative;
    padding-left: 0.5rem;
    margin-left: 0.25rem;
    border-left: 2px solid rgba(99, 102, 241, 0.5);
  }
  .agent-steps.cursor-style-steps .agent-step {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    position: relative;
  }
  .agent-steps.cursor-style-steps .agent-step:last-child {
    margin-bottom: 0;
  }
  .agent-steps.cursor-style-steps .step-dot {
    position: absolute;
    left: 0;
    top: 0.35rem;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--atra-primary, #6366f1);
    transform: translateX(calc(-50% - 1px));
    flex-shrink: 0;
  }
  .agent-steps.cursor-style-steps .step-body {
    flex: 1;
    min-width: 0;
  }
  .agent-steps.cursor-style-steps .step-header {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }
  .agent-steps.cursor-style-steps .step-icon {
    opacity: 0.9;
    flex-shrink: 0;
  }
  .agent-steps.cursor-style-steps .step-title {
    font-weight: 500;
  }
  .agent-steps.cursor-style-steps .step-duration {
    color: var(--atra-accent, #64748b);
    font-weight: 400;
  }
  .agent-steps.cursor-style-steps .step-content {
    color: #94a3b8;
    margin-left: 1.25rem;
    margin-top: 0.25rem;
    line-height: 1.4;
    font-size: 0.75rem;
  }
  .agent-steps.cursor-style-steps .agent-step.step-thought .step-dot,
  .agent-steps.cursor-style-steps .agent-step.step-thought .step-title { color: #a78bfa; }
  .agent-steps.cursor-style-steps .agent-step.step-thought .step-dot { background: #a78bfa; }
  .agent-steps.cursor-style-steps .agent-step.step-exploration .step-dot,
  .agent-steps.cursor-style-steps .agent-step.step-exploration .step-title { color: #38bdf8; }
  .agent-steps.cursor-style-steps .agent-step.step-exploration .step-dot { background: #38bdf8; }
  .agent-steps.cursor-style-steps .agent-step.step-action .step-dot,
  .agent-steps.cursor-style-steps .agent-step.step-action .step-title { color: #34d399; }
  .agent-steps.cursor-style-steps .agent-step.step-action .step-dot { background: #34d399; }
  .agent-steps.cursor-style-steps .agent-step.step-clarification .step-dot,
  .agent-steps.cursor-style-steps .agent-step.step-clarification .step-title { color: #fbbf24; }
  .agent-steps.cursor-style-steps .agent-step.step-clarification .step-dot { background: #fbbf24; }

  /* Панель шагов во время стриминга: вертикальный список (как в Cursor) */
  .agent-steps-panel.cursor-style-panel {
    font-size: 0.8125rem;
  }
  .agent-steps-timeline {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }
  .agent-step-badge {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.375rem 0.75rem;
    border-radius: 6px;
    background: rgba(30, 30, 46, 0.8);
    border: 1px solid rgba(99, 102, 241, 0.25);
    transition: border-color 0.15s, background 0.15s;
  }
  .agent-step-badge:hover {
    background: rgba(99, 102, 241, 0.08);
    border-color: rgba(99, 102, 241, 0.4);
  }
  .agent-step-badge .step-icon { opacity: 0.95; flex-shrink: 0; }
  .agent-step-badge .step-title { font-weight: 600; color: #e2e8f0; }
  .agent-step-badge .step-desc { color: #94a3b8; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 400; }
  .agent-step-badge.step-thought .step-title { color: #a78bfa; }
  .agent-step-badge.step-exploration .step-title { color: #38bdf8; }
  .agent-step-badge.step-action .step-title { color: #34d399; }
  .agent-suggestion-btn {
    margin-left: auto;
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: #a78bfa;
    background: rgba(167, 139, 250, 0.15);
    border: 1px solid rgba(167, 139, 250, 0.4);
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .agent-suggestion-btn:hover {
    background: rgba(167, 139, 250, 0.25);
    border-color: #a78bfa;
  }
  .agent-steps.cursor-style-steps .agent-suggestion-btn {
    margin-top: 0.5rem;
    margin-left: 1.25rem;
  }

  .cursor-agent-working {
    animation: cursor-fade-in 0.2s ease-out;
  }
  @keyframes cursor-fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  /* Highlight.js тема */
  :global(.hljs) {
    background: var(--atra-darker) !important;
    border-radius: 0.5rem;
    padding: 1rem;
  }

  :global(.prose code) {
    background: var(--atra-accent);
    padding: 0.125rem 0.375rem;
    border-radius: 0.25rem;
    font-size: 0.875em;
  }

  :global(.prose pre code) {
    background: transparent;
    padding: 0;
  }
</style>
