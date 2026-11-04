<script>
  let goal = "";
  let planResult = "";
  let loading = false;
  let error = null;

  async function fetchPlan() {
    if (!goal.trim()) return;
    loading = true;
    error = null;
    planResult = "";
    try {
      const base = import.meta.env?.DEV ? "" : "";
      const res = await fetch(`${base}/api/chat/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: goal.trim() }),
      });
      const data = await res.json();
      if (!res.ok)
        throw new Error(data.detail || data.error || "Ошибка запроса плана");
      planResult = data.plan || "";
    } catch (e) {
      error = e.message || String(e);
    } finally {
      loading = false;
    }
  }
</script>

<div class="h-full flex flex-col bg-atra-dark p-4">
  <div
    class="p-2 border-b border-atra-accent/50 text-xs text-gray-400 uppercase tracking-wider mb-4"
  >
    План — только планирование (без выполнения), как в Cursor
  </div>
  <div class="flex flex-col gap-3 flex-1 min-h-0">
    <label class="text-sm text-gray-400">Задача или цель</label>
    <textarea
      bind:value={goal}
      placeholder="Опишите задачу: Виктория составит план без выполнения"
      class="w-full bg-atra-darker border border-atra-accent rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-atra-primary resize-none"
      rows="4"
      disabled={loading}
    />
    <button
      on:click={fetchPlan}
      disabled={loading || !goal.trim()}
      class="px-4 py-2 bg-atra-primary rounded-lg text-sm font-medium hover:bg-opacity-90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed self-start"
    >
      {#if loading}
        <span class="animate-spin">⏳</span> Получаю план…
      {:else}
        📋 Получить план
      {/if}
    </button>
    {#if error}
      <div
        class="bg-red-900/30 border border-red-700 rounded-lg p-3 text-red-300 text-sm"
      >
        {error}
      </div>
    {/if}
    {#if planResult}
      <div
        class="flex-1 min-h-0 flex flex-col border border-atra-accent rounded-lg overflow-hidden"
      >
        <div
          class="p-2 border-b border-atra-accent text-xs text-gray-400 uppercase"
        >
          План Виктории
        </div>
        <div
          class="flex-1 overflow-y-auto p-4 text-sm text-gray-300 whitespace-pre-wrap font-mono"
        >
          {planResult}
        </div>
      </div>
    {/if}
  </div>
</div>
