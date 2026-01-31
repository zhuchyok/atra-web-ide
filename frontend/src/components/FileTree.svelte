<script>
  import { onMount } from 'svelte'
  import { fileTree, loadFileTree, loadFile, createFile, deleteFile } from '../stores/files.js'
  
  let expandedDirs = new Set()
  let contextMenu = null
  let showNewFileInput = false
  let newFileName = ''
  let newFileType = 'file'
  
  onMount(() => {
    loadFileTree()
  })
  
  async function toggleDir(path) {
    if (expandedDirs.has(path)) {
      expandedDirs.delete(path)
    } else {
      expandedDirs.add(path)
      // Загрузить содержимое директории
      const children = await loadFileTree(path)
      // Обновить дерево файлов с детьми
      fileTree.update(tree => {
        function updateTree(items) {
          return items.map(item => {
            if (item.path === path && item.type === 'directory') {
              return { ...item, children: children || [] }
            }
            if (item.children) {
              return { ...item, children: updateTree(item.children) }
            }
            return item
          })
        }
        return updateTree(tree)
      })
    }
    expandedDirs = expandedDirs // Trigger reactivity
  }
  
  async function handleFileClick(file) {
    if (file.type === 'directory') {
      toggleDir(file.path)
    } else {
      await loadFile(file.path)
    }
  }
  
  function handleContextMenu(event, file) {
    event.preventDefault()
    contextMenu = {
      x: event.clientX,
      y: event.clientY,
      file
    }
  }
  
  function closeContextMenu() {
    contextMenu = null
  }
  
  async function handleDelete(file) {
    if (confirm(`Delete ${file.name}?`)) {
      await deleteFile(file.path)
    }
    closeContextMenu()
  }
  
  function handleNewFile(type) {
    newFileType = type
    showNewFileInput = true
    closeContextMenu()
  }
  
  async function createNewFile() {
    if (!newFileName.trim()) return
    
    const path = newFileName.trim()
    const success = await createFile(path, newFileType, newFileType === 'file' ? '' : null)
    
    if (success) {
      showNewFileInput = false
      newFileName = ''
    }
  }
  
  function getFileIcon(file) {
    if (file.type === 'directory') {
      return expandedDirs.has(file.path) ? '📂' : '📁'
    }
    
    const ext = file.name.split('.').pop()?.toLowerCase()
    
    switch (ext) {
      case 'js':
      case 'jsx':
        return '🟨'
      case 'ts':
      case 'tsx':
        return '🔷'
      case 'py':
        return '🐍'
      case 'html':
        return '🌐'
      case 'css':
      case 'scss':
        return '🎨'
      case 'json':
        return '📋'
      case 'md':
        return '📝'
      case 'svelte':
        return '🔶'
      default:
        return '📄'
    }
  }
</script>

<svelte:window on:click={closeContextMenu} />

<div class="h-full overflow-y-auto text-sm">
  <!-- New file input -->
  {#if showNewFileInput}
    <div class="px-2 py-2 border-b border-atra-accent">
      <input
        type="text"
        bind:value={newFileName}
        placeholder={newFileType === 'file' ? 'filename.js' : 'folder name'}
        class="w-full bg-atra-dark border border-atra-accent rounded px-2 py-1 text-sm focus:outline-none focus:border-atra-primary"
        on:keydown={(e) => e.key === 'Enter' && createNewFile()}
        on:blur={() => { showNewFileInput = false; newFileName = '' }}
      />
    </div>
  {/if}
  
  <!-- Toolbar -->
  <div class="px-2 py-2 flex items-center gap-1 border-b border-atra-accent">
    <button 
      class="p-1 hover:bg-atra-accent rounded transition-colors text-xs"
      title="New File"
      on:click={() => handleNewFile('file')}
    >
      📄+
    </button>
    <button 
      class="p-1 hover:bg-atra-accent rounded transition-colors text-xs"
      title="New Folder"
      on:click={() => handleNewFile('directory')}
    >
      📁+
    </button>
    <button 
      class="p-1 hover:bg-atra-accent rounded transition-colors text-xs"
      title="Refresh"
      on:click={() => loadFileTree()}
    >
      🔄
    </button>
  </div>
  
  <!-- File tree -->
  <div class="py-1">
    {#each $fileTree as file}
      <div>
        <button
          class="file-item w-full text-left px-2 py-1 flex items-center gap-2 hover:bg-atra-accent/30 transition-colors {expandedDirs.has(file.path) ? 'bg-atra-accent/20' : ''}"
          on:click={() => handleFileClick(file)}
          on:contextmenu={(e) => handleContextMenu(e, file)}
        >
          <span class="text-sm">{getFileIcon(file)}</span>
          <span class="truncate flex-1">{file.name}</span>
          {#if file.type === 'directory'}
            <span class="text-gray-500 text-xs">
              {expandedDirs.has(file.path) ? '▼' : '▶'}
            </span>
          {/if}
        </button>
        
        {#if file.type === 'directory' && expandedDirs.has(file.path) && file.children}
          <div class="ml-4 border-l border-atra-accent/30">
            {#each file.children as child}
              <div>
                <button
                  class="file-item w-full text-left px-2 py-1 flex items-center gap-2 hover:bg-atra-accent/30 transition-colors pl-6 {expandedDirs.has(child.path) ? 'bg-atra-accent/20' : ''}"
                  on:click={() => handleFileClick(child)}
                  on:contextmenu={(e) => handleContextMenu(e, child)}
                >
                  <span class="text-sm">{getFileIcon(child)}</span>
                  <span class="truncate flex-1">{child.name}</span>
                  {#if child.type === 'directory'}
                    <span class="text-gray-500 text-xs">
                      {expandedDirs.has(child.path) ? '▼' : '▶'}
                    </span>
                  {/if}
                </button>
                
                {#if child.type === 'directory' && expandedDirs.has(child.path) && child.children}
                  <div class="ml-4 border-l border-atra-accent/30">
                    {#each child.children as grandchild}
                      <button
                        class="file-item w-full text-left px-2 py-1 flex items-center gap-2 hover:bg-atra-accent/30 transition-colors pl-10"
                        on:click={() => handleFileClick(grandchild)}
                        on:contextmenu={(e) => handleContextMenu(e, grandchild)}
                      >
                        <span class="text-sm">{getFileIcon(grandchild)}</span>
                        <span class="truncate flex-1">{grandchild.name}</span>
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
    
    {#if $fileTree.length === 0}
      <div class="px-4 py-8 text-center text-gray-500">
        <p>No files yet</p>
        <p class="text-xs mt-1">Create a new file to get started</p>
      </div>
    {/if}
  </div>
</div>

<!-- Context menu -->
{#if contextMenu}
  <div 
    class="fixed bg-atra-darker border border-atra-accent rounded-lg shadow-xl py-1 z-50"
    style="left: {contextMenu.x}px; top: {contextMenu.y}px"
  >
    <button 
      class="w-full text-left px-4 py-1.5 hover:bg-atra-accent/50 text-sm"
      on:click={() => handleNewFile('file')}
    >
      New File
    </button>
    <button 
      class="w-full text-left px-4 py-1.5 hover:bg-atra-accent/50 text-sm"
      on:click={() => handleNewFile('directory')}
    >
      New Folder
    </button>
    <div class="border-t border-atra-accent my-1"></div>
    <button 
      class="w-full text-left px-4 py-1.5 hover:bg-red-900/50 text-red-400 text-sm"
      on:click={() => handleDelete(contextMenu.file)}
    >
      Delete
    </button>
  </div>
{/if}
