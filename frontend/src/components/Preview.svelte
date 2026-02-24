<script>
  import { currentFile } from '../stores/files.js'

  let iframeRef
  let previewUrl = `http://${window.location.hostname}:8081/api/preview`

  function refreshPreview() {
    if (iframeRef) {
      iframeRef.src = previewUrl + (previewUrl.includes('?') ? '&' : '?') + 't=' + Date.now()
    }
  }

  // Обновлять preview при изменении HTML файла
  $: if ($currentFile?.name?.endsWith('.html')) {
    previewUrl = `http://${window.location.hostname}:8081/api/preview/file?path=${encodeURIComponent($currentFile.path)}`
    refreshPreview()
  }
</script>

<div class="h-full flex flex-col bg-atra-darker">
  <!-- Toolbar -->
  <div class="h-9 px-3 flex items-center justify-between border-b border-atra-accent">
    <span class="text-xs text-gray-400">Live Preview</span>
    <div class="flex items-center gap-2">
      <button
        class="p-1 hover:bg-atra-accent rounded transition-colors text-xs"
        title="Refresh"
        on:click={refreshPreview}
      >
        🔄
      </button>
      <button
        class="p-1 hover:bg-atra-accent rounded transition-colors text-xs"
        title="Open in new tab"
        on:click={() => window.open(previewUrl, '_blank')}
      >
        ↗️
      </button>
    </div>
  </div>

  <!-- iframe -->
  <div class="flex-1 bg-white">
    <iframe
      bind:this={iframeRef}
      src={previewUrl}
      class="w-full h-full border-0"
      title="Preview"
      sandbox="allow-scripts allow-same-origin"
    ></iframe>
  </div>
</div>
