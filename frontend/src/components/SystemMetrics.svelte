<script>
  import { onMount } from 'svelte'

  let data = null
  let error = null
  let loading = true

  async function fetchMetrics() {
    loading = true
    error = null
    try {
      const r = await fetch('/api/system-metrics')
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      data = await r.json()
    } catch (e) {
      error = e.message || 'Ошибка загрузки'
      data = null
    } finally {
      loading = false
    }
  }

  onMount(() => {
    fetchMetrics()
    const t = setInterval(fetchMetrics, 15000)
    return () => clearInterval(t)
  })
</script>

<div class="h-full flex flex-col p-4 bg-atra-dark">
  <div class="flex items-center justify-between mb-4">
    <h2 class="text-lg font-semibold text-gray-200">Мониторинг системы (Mac Studio)</h2>
    <button
      class="px-3 py-1.5 rounded text-sm bg-atra-accent hover:bg-atra-primary transition-colors"
      on:click={fetchMetrics}
      disabled={loading}
    >
      {loading ? 'Загрузка…' : 'Обновить'}
    </button>
  </div>

  {#if error}
    <div class="rounded-lg p-4 bg-red-900/20 border border-red-700 text-red-300 text-sm">
      {error}
    </div>
  {:else if data && data.success}
    <div class="grid gap-4 sm:grid-cols-3">
      <div class="rounded-lg p-4 bg-atra-darker border border-atra-accent">
        <div class="text-xs text-gray-500 uppercase tracking-wider mb-2">CPU</div>
        <div class="text-2xl font-bold text-atra-primary">{data.cpu?.percent ?? '—'}%</div>
        <div class="text-xs text-gray-400 mt-1">{data.cpu?.count ?? '—'} ядер</div>
      </div>
      <div class="rounded-lg p-4 bg-atra-darker border border-atra-accent">
        <div class="text-xs text-gray-500 uppercase tracking-wider mb-2">Память (RAM)</div>
        <div class="text-2xl font-bold text-atra-primary">{data.ram?.percent ?? '—'}%</div>
        <div class="text-xs text-gray-400 mt-1">
          {data.ram?.used_gb ?? '—'} / {data.ram?.total_gb ?? '—'} ГБ
        </div>
      </div>
      <div class="rounded-lg p-4 bg-atra-darker border border-atra-accent">
        <div class="text-xs text-gray-500 uppercase tracking-wider mb-2">Диск</div>
        <div class="text-2xl font-bold text-atra-primary">{data.disk?.percent ?? '—'}%</div>
        <div class="text-xs text-gray-400 mt-1">
          {data.disk?.used_gb ?? '—'} / {data.disk?.total_gb ?? '—'} ГБ
        </div>
      </div>
    </div>
    <p class="mt-4 text-xs text-gray-500">
      Если бэкенд в Docker — показаны метрики контейнера. Обновление каждые 15 сек.
    </p>
  {:else if loading}
    <div class="text-gray-400">Загрузка метрик…</div>
  {:else}
    <div class="text-gray-500">Метрики недоступны</div>
  {/if}
</div>
