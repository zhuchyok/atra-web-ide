<script>
  import { onMount } from 'svelte'

  let agents = []
  let error = null
  let loading = true

  async function fetchAgentStatus() {
    loading = true
    error = null
    try {
      const r = await fetch(`http://${window.location.hostname}:8002/api/health/all`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const data = await r.json()
      agents = Object.entries(data.services || {}).map(([name, status]) => ({
        name,
        status: status.status === 'ok' ? 'active' : 'error',
        detail: status.error || `${status.code || 'ok'}`,
      }))
    } catch (e) {
      error = e.message || 'Ошибка загрузки'
    } finally {
      loading = false
    }
  }

  onMount(() => {
    fetchAgentStatus()
    const t = setInterval(fetchAgentStatus, 15000)
    return () => clearInterval(t)
  })
</script>

<div class="h-full flex flex-col p-4 bg-atra-dark">
  <div class="flex items-center justify-between mb-4">
    <h2 class="text-lg font-semibold text-gray-200">Статус агентов</h2>
    <button
      class="px-3 py-1.5 rounded text-sm bg-atra-accent hover:bg-atra-primary transition-colors"
      on:click={fetchAgentStatus}
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
    <div class="space-y-2">
      {#each agents as agent}
        <div
          class="rounded-lg p-3 bg-atra-darker border {agent.status === 'active' ? 'border-green-900/50' : 'border-red-900/50'} flex items-center justify-between"
        >
          <div class="flex items-center gap-3">
            <span
              class="w-2.5 h-2.5 rounded-full {agent.status === 'active' ? 'bg-green-400' : 'bg-red-400'}"
            ></span>
            <span class="text-sm font-medium text-gray-200 capitalize">{agent.name}</span>
          </div>
          <div class="text-xs {agent.status === 'active' ? 'text-green-400' : 'text-red-400'}">
            {agent.status === 'active' ? 'Online' : agent.detail}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
