/**
 * SSE (Server-Sent Events) утилиты
 */

/**
 * Подключение к SSE endpoint
 * @param {string} url - URL для подключения
 * @param {Object} options - Опции
 * @returns {EventSource}
 */
export function connectSSE(url, options = {}) {
  const { onMessage, onError, onOpen } = options
  
  const eventSource = new EventSource(url)
  
  if (onOpen) {
    eventSource.onopen = onOpen
  }
  
  if (onMessage) {
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
      } catch (e) {
        onMessage({ raw: event.data })
      }
    }
  }
  
  if (onError) {
    eventSource.onerror = onError
  }
  
  return eventSource
}

/**
 * POST запрос с SSE ответом
 * @param {string} url - URL
 * @param {Object} body - Тело запроса
 * @param {Function} onChunk - Callback для каждого chunk
 * @returns {Promise}
 */
export async function fetchSSE(url, body, onChunk) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream'
    },
    body: JSON.stringify(body)
  })
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }
  
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  
  let buffer = ''
  
  while (true) {
    const { done, value } = await reader.read()
    
    if (done) break
    
    buffer += decoder.decode(value, { stream: true })
    
    // Обработка SSE формата
    const lines = buffer.split('\n')
    buffer = lines.pop() || '' // Сохраняем неполную строку
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        try {
          const parsed = JSON.parse(data)
          onChunk(parsed)
        } catch (e) {
          onChunk({ raw: data })
        }
      }
    }
  }
  
  // Обработка оставшегося буфера
  if (buffer.startsWith('data: ')) {
    const data = buffer.slice(6)
    try {
      const parsed = JSON.parse(data)
      onChunk(parsed)
    } catch (e) {
      onChunk({ raw: data })
    }
  }
}

/**
 * Создание EventSource с retry логикой
 * @param {string} url - URL
 * @param {Object} options - Опции
 * @returns {Object} - Объект с методами connect/disconnect
 */
export function createReconnectingSSE(url, options = {}) {
  const { 
    onMessage, 
    onError, 
    onConnect,
    maxRetries = 5,
    retryDelay = 1000 
  } = options
  
  let eventSource = null
  let retries = 0
  let connected = false
  
  function connect() {
    eventSource = new EventSource(url)
    
    eventSource.onopen = () => {
      connected = true
      retries = 0
      if (onConnect) onConnect()
    }
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (onMessage) onMessage(data)
      } catch (e) {
        if (onMessage) onMessage({ raw: event.data })
      }
    }
    
    eventSource.onerror = (error) => {
      connected = false
      eventSource.close()
      
      if (retries < maxRetries) {
        retries++
        setTimeout(connect, retryDelay * retries)
      } else {
        if (onError) onError(error)
      }
    }
  }
  
  function disconnect() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    connected = false
  }
  
  return {
    connect,
    disconnect,
    isConnected: () => connected
  }
}
