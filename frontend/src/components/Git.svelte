<script>
  import { onMount } from 'svelte';
  const GATEWAY = `http://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:8081`;

  let status = { lines: [], error: null };
  let diff = '';
  let branch = { current: '', branches: [] };
  let log = { commits: [] };
  let commitMessage = '';
  let loading = true;
  let activeTab = 'status';

  async function fetchStatus() {
    loading = true;
    status = { lines: [], error: null };
    try {
      const r = await fetch(`${GATEWAY}/api/git/status`);
      const data = await r.json();
      if (!r.ok) {
        status.error = data.error || r.statusText;
        return;
      }
      status.lines = data.lines || [];
    } catch (e) {
      status.error = e.message;
    } finally {
      loading = false;
    }
  }

  async function fetchDiff() {
    loading = true;
    diff = '';
    try {
      const r = await fetch(`${GATEWAY}/api/git/diff`);
      const data = await r.json();
      if (r.ok) diff = data.stdout || '';
      else diff = data.error || 'Not a git repo';
    } catch (e) {
      diff = e.message;
    } finally {
      loading = false;
    }
  }

  async function fetchBranch() {
    loading = true;
    branch = { current: '', branches: [] };
    try {
      const r = await fetch(`${GATEWAY}/api/git/branch`);
      const data = await r.json();
      if (r.ok) {
        branch.current = data.current || '';
        branch.branches = data.branches || [];
      } else {
        branch.current = data.error || '—';
      }
    } catch (e) {
      branch.current = e.message;
    } finally {
      loading = false;
    }
  }

  async function fetchLog() {
    loading = true;
    log = { commits: [] };
    try {
      const r = await fetch(`${GATEWAY}/api/git/log?n=30`);
      const data = await r.json();
      if (r.ok) log.commits = data.commits || [];
    } catch (e) {
      log.commits = [];
    } finally {
      loading = false;
    }
  }

  async function doCommit() {
    if (!commitMessage.trim()) return;
    try {
      const r = await fetch(`${GATEWAY}/api/git/commit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: commitMessage.trim(), paths: null }),
      });
      const data = await r.json();
      if (r.ok && data.success) {
        commitMessage = '';
        fetchStatus();
        fetchLog();
      } else {
        alert(data.error || data.stderr || 'Commit failed');
      }
    } catch (e) {
      alert(e.message);
    }
  }

  function onTab(tab) {
    activeTab = tab;
    if (tab === 'status') fetchStatus();
    else if (tab === 'diff') fetchDiff();
    else if (tab === 'branch') fetchBranch();
    else if (tab === 'log') fetchLog();
  }

  onMount(() => onTab('status'));
</script>

<div class="git-panel p-4 h-full flex flex-col bg-atra-dark text-gray-200">
  <h2 class="text-lg font-semibold mb-3 flex items-center gap-2">
    <span>📂</span> Git
  </h2>

  <div class="flex gap-2 mb-3 flex-wrap">
    <button
      class="px-3 py-1.5 rounded text-sm transition-colors {activeTab === 'status' ? 'bg-atra-primary text-white' : 'bg-atra-accent/30 hover:bg-atra-accent/50'}"
      on:click={() => onTab('status')}
    >Status</button>
    <button
      class="px-3 py-1.5 rounded text-sm transition-colors {activeTab === 'diff' ? 'bg-atra-primary text-white' : 'bg-atra-accent/30 hover:bg-atra-accent/50'}"
      on:click={() => onTab('diff')}
    >Diff</button>
    <button
      class="px-3 py-1.5 rounded text-sm transition-colors {activeTab === 'branch' ? 'bg-atra-primary text-white' : 'bg-atra-accent/30 hover:bg-atra-accent/50'}"
      on:click={() => onTab('branch')}
    >Branches</button>
    <button
      class="px-3 py-1.5 rounded text-sm transition-colors {activeTab === 'log' ? 'bg-atra-primary text-white' : 'bg-atra-accent/30 hover:bg-atra-accent/50'}"
      on:click={() => onTab('log')}
    >Log</button>
  </div>

  {#if loading}
    <p class="text-sm text-gray-500">Loading…</p>
  {:else if activeTab === 'status'}
    {#if status.error}
      <p class="text-red-400 text-sm">{status.error}</p>
    {:else}
      <pre class="text-xs font-mono overflow-auto flex-1 whitespace-pre-wrap border border-atra-accent rounded p-2 min-h-[120px]">{status.lines.length ? status.lines.join('\n') : 'working tree clean'}</pre>
    {/if}
  {:else if activeTab === 'diff'}
    <pre class="text-xs font-mono overflow-auto flex-1 whitespace-pre-wrap border border-atra-accent rounded p-2 min-h-[120px]">{diff || 'No changes'}</pre>
  {:else if activeTab === 'branch'}
    <p class="text-sm mb-2">Current: <strong>{branch.current}</strong></p>
    <ul class="text-sm list-disc list-inside space-y-1">
      {#each branch.branches as b}
        <li>{b}</li>
      {/each}
    </ul>
  {:else if activeTab === 'log'}
    <ul class="text-xs font-mono overflow-auto space-y-1 min-h-[120px]">
      {#each log.commits as c}
        <li class="flex gap-2 flex-wrap">
          <span class="text-yellow-500">{c.hash}</span>
          <span class="text-gray-500">{c.date}</span>
          <span>{c.author}</span>
          <span class="text-gray-300">{c.subject}</span>
        </li>
      {/each}
    </ul>
  {/if}

  <div class="mt-4 pt-3 border-t border-atra-accent">
    <label class="block text-sm text-gray-400 mb-1">Commit</label>
    <div class="flex gap-2">
      <input
        type="text"
        class="flex-1 bg-atra-darker border border-atra-accent rounded px-2 py-1.5 text-sm"
        placeholder="Commit message..."
        bind:value={commitMessage}
      />
      <button
        class="px-3 py-1.5 rounded text-sm bg-atra-primary hover:opacity-90 disabled:opacity-50"
        on:click={doCommit}
        disabled={!commitMessage.trim()}
      >Commit</button>
    </div>
  </div>
</div>
