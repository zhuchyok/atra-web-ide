import { writable, derived } from 'svelte/store'

// Дерево файлов
export const fileTree = writable([])

// Текущий открытый файл
export const currentFile = writable(null)

// Открытые файлы (табы)
export const openFiles = writable([])

// Содержимое файлов (кэш)
export const fileContents = writable({})

// Несохранённые изменения
export const unsavedChanges = writable({})

// Загрузить дерево файлов
export async function loadFileTree(path = '') {
  try {
    const response = await fetch(`/api/files/list?path=${encodeURIComponent(path)}`)
    if (response.ok) {
      const data = await response.json()
      if (path === '') {
        // Корневой уровень - обновляем всё дерево
        fileTree.set(data)
      }
      // Возвращаем данные для вложенных директорий
      return data
    }
  } catch (e) {
    console.error('Failed to load file tree:', e)
  }
  return []
}

// Загрузить файл
export async function loadFile(filePath) {
  try {
    const response = await fetch(`/api/files/read?path=${encodeURIComponent(filePath)}`)
    if (response.ok) {
      const data = await response.json()
      
      // Обновить кэш
      fileContents.update(cache => ({
        ...cache,
        [filePath]: data.content
      }))
      
      // Установить текущий файл
      const fileName = filePath.split('/').pop()
      currentFile.set({
        name: fileName,
        path: filePath,
        content: data.content
      })
      
      // Добавить в открытые файлы
      openFiles.update(files => {
        if (!files.find(f => f.path === filePath)) {
          return [...files, { name: fileName, path: filePath }]
        }
        return files
      })
      
      return data.content
    }
  } catch (e) {
    console.error('Failed to load file:', e)
  }
  return null
}

// Сохранить файл
export async function saveFile(filePath, content) {
  try {
    const response = await fetch(`/api/files/write?path=${encodeURIComponent(filePath)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ content })
    })
    
    if (response.ok) {
      // Убрать из несохранённых
      unsavedChanges.update(changes => {
        const { [filePath]: _, ...rest } = changes
        return rest
      })
      
      // Обновить кэш
      fileContents.update(cache => ({
        ...cache,
        [filePath]: content
      }))
      
      return true
    }
  } catch (e) {
    console.error('Failed to save file:', e)
  }
  return false
}

// Создать файл
export async function createFile(path, type = 'file', content = '') {
  try {
    const response = await fetch(`/api/files/create?path=${encodeURIComponent(path)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ type, content })
    })
    
    if (response.ok) {
      // Перезагрузить дерево
      await loadFileTree()
      return true
    }
  } catch (e) {
    console.error('Failed to create file:', e)
  }
  return false
}

// Удалить файл
export async function deleteFile(path) {
  try {
    const response = await fetch(`/api/files/delete?path=${encodeURIComponent(path)}`, {
      method: 'DELETE'
    })
    
    if (response.ok) {
      // Убрать из открытых
      openFiles.update(files => files.filter(f => f.path !== path))
      
      // Если это текущий файл, сбросить
      currentFile.update(file => file?.path === path ? null : file)
      
      // Перезагрузить дерево
      await loadFileTree()
      return true
    }
  } catch (e) {
    console.error('Failed to delete file:', e)
  }
  return false
}

// Отметить изменения
export function markUnsaved(filePath, content) {
  unsavedChanges.update(changes => ({
    ...changes,
    [filePath]: content
  }))
}

// Закрыть файл
export function closeFile(filePath) {
  openFiles.update(files => files.filter(f => f.path !== filePath))
  currentFile.update(file => file?.path === filePath ? null : file)
}
