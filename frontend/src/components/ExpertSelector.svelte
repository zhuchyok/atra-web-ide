<script>
  import { experts, selectedExpert } from '../stores/chat.js'
  
  let isOpen = false
  
  function selectExpert(expert) {
    selectedExpert.set(expert)
    isOpen = false
  }
</script>

<div class="relative">
  <button
    class="flex items-center gap-2 px-3 py-1.5 bg-atra-accent rounded text-sm hover:bg-atra-primary/30 transition-colors"
    on:click={() => isOpen = !isOpen}
  >
    <div class="w-5 h-5 rounded-full bg-gradient-to-br from-atra-primary to-atra-secondary flex items-center justify-center text-xs">
      {$selectedExpert?.name?.[0] || 'A'}
    </div>
    <span>{$selectedExpert?.name || 'Выберите эксперта'}</span>
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
    </svg>
  </button>
  
  {#if isOpen}
    <!-- Backdrop -->
    <div 
      class="fixed inset-0 z-40"
      on:click={() => isOpen = false}
    ></div>
    
    <!-- Dropdown -->
    <div class="absolute right-0 mt-2 w-64 bg-atra-darker border border-atra-accent rounded-lg shadow-xl z-50 max-h-80 overflow-y-auto">
      <div class="p-2 border-b border-atra-accent text-xs text-gray-500 uppercase">
        Victoria ({$experts.length})
      </div>
      
      {#each $experts as expert}
        <button
          class="w-full text-left px-3 py-2 hover:bg-atra-accent/50 transition-colors flex items-center gap-3
            {$selectedExpert?.id === expert.id ? 'bg-atra-primary/20' : ''}"
          on:click={() => selectExpert(expert)}
        >
          <div class="w-8 h-8 rounded-full bg-gradient-to-br from-atra-primary to-atra-secondary flex items-center justify-center text-sm font-medium">
            {expert.name[0]}
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-medium text-sm truncate">{expert.name}</div>
            {#if expert.role}
              <div class="text-xs text-gray-500 truncate">{expert.role}</div>
            {/if}
          </div>
          {#if $selectedExpert?.id === expert.id}
            <svg class="w-4 h-4 text-atra-primary" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
          {/if}
        </button>
      {/each}
      
      {#if $experts.length === 0}
        <div class="p-4 text-center text-gray-500 text-sm">
          <div class="animate-pulse">Загрузка экспертов...</div>
        </div>
      {/if}
    </div>
  {/if}
</div>
