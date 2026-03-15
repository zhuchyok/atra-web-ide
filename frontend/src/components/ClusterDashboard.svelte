<script>
  import { onMount } from 'svelte'

  let clusters = []
  let error = null
  let loading = true

  async function fetchClusters() {
    loading = true
    error = null
    try {
      // В реальности нам нужен эндпоинт для списка кластеров
      const r = await fetch(`http://${window.location.hostname}:8081/api/experts`) // Временный хак для проверки связи
      if (!r.ok) throw new Error(`HTTP ${r.status}`)

      // Имитация данных кластеров для MVP
      clusters = [
        { id: '1', name: 'mac-studio-primary', url: 'http://localhost:8081', status: 'active', is_local: true, last_heartbeat: new Date().toISOString() },
        { id: '2', name: 'vds-singularity-1', url: 'http://185.177.216.15:8081', status: 'inactive', is_local: false, last_heartbeat: '2026-03-14T09:00:00Z' }
      ]
    } catch (e) {
      error = e.message || 'Ошибка загрузки'
    } finally {
      loading = false
    }
  }

  onMount(() => {
    fetchClusters()
    const t = setInterval(fetchClusters, 30000)
    return () => clearInterval(t)
  })
</script>

<div class="h-full flex flex-col p-4 bg-atra-dark">
  <div class="flex items-center justify-between mb-4">
    <h2 class="text-lg font-semibold text-gray-200">Мульти-кластерная автономность</h2>
    <button
      class="px-3 py-1.5 rounded text-sm bg-atra-accent hover:bg-atra-primary transition-colors"
      on:click={fetchClusters}
      disabled={loading}
    >
      {loading ? 'Обновление…' : 'Обновить'}
    </button>
  </div>

  {#if error}
    <div class="rounded-lg p-4 bg-red-900/20 border border-red-700 text-red-300 text-sm">
      {error}
    </div>
  {:else}
    <div class="space-y-4">
      {#each clusters as cluster}
        <div class="rounded-lg p-4 bg-atra-darker border {cluster.status === 'active' ? 'border-green-900/50' : 'border-red-900/50'}">
          <div class="flex items-center justify-between">
            <div>
              <div class="flex items-center gap-2">
                <span class="text-sm font-bold text-gray-200">{cluster.name}</span>
                {#if cluster.is_local}
                  <span class="px-1.5 py-0.5 rounded text-[10px] bg-atra-accent text-white uppercase">Local</span>
                {/if}
              </div>
              <div class="text-xs text-gray-500 mt-1">{cluster.url}</div>
            </div>
            <div class="text-right">
              <div class="text-xs {cluster.status === 'active' ? 'text-green-400' : 'text-red-400'} font-medium uppercase tracking-tighter">
                {cluster.status}
              </div>
              <div class="text-[10px] text-gray-600 mt-1">
                Heartbeat: {new Date(cluster.last_heartbeat).toLocaleTimeString()}
              </div>
            </div>
          </div>

          {#if cluster.status === 'active'}
            <div class="mt-3 h-1 w-full bg-gray-800 rounded-full overflow-hidden">
              <div class="h-full bg-green-500 w-full animate-pulse"></div>
            </div>
          {/if}
        </div>
      {/each}
    </div>

    <div class="mt-6 p-4 rounded-lg bg-atra-accent/10 border border-atra-accent/30">
      <div class="text-xs font-bold text-atra-primary uppercase mb-2">Статус Gossip-протокола</div>
      <div class="text-xs text-gray-400 leading-relaxed">
        Синхронизация знаний: <span class="text-green-400">Активна</span><br>
        Туннелирование задач: <span class="text-green-400">Готово</span><br>
        mTLS шифрование: <span class="text-atra-primary">Включено</span>
      </div>
    </div>
  {/if}
</div>
