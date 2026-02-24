import { writable, derived, get } from 'svelte/store'

// Сообщения чата
export const messages = writable([])

// Текущий выбранный эксперт
export const selectedExpert = writable(null)

// Список экспертов
export const experts = writable([])

// Статус загрузки
export const isLoading = writable(false)

// Статус стриминга
export const isStreaming = writable(false)

// Ошибка
export const error = writable(null)

// Режим чата (как в Cursor): agent | plan | ask
export const chatMode = writable('agent')

// Добавить сообщение (assistant может иметь steps — шаги агента как в Cursor)
export function addMessage(role, content, expertName = null) {
  messages.update(msgs => [
    ...msgs,
    {
      id: Date.now(),
      role,
      content: content ?? '',
      expertName,
      steps: role === 'assistant' ? [] : undefined,
      timestamp: new Date().toISOString()
    }
  ])
}

// Добавить шаг агента к последнему сообщению (thought, exploration, action, clarification)
export function appendStep(step) {
  messages.update(msgs => {
    if (msgs.length === 0) return msgs
    const last = msgs[msgs.length - 1]
    if (last.role !== 'assistant' || !Array.isArray(last.steps)) return msgs
    return [
      ...msgs.slice(0, -1),
      { ...last, steps: [...last.steps, step] }
    ]
  })
}

// Обновить последнее сообщение (для стриминга)
export function updateLastMessage(content) {
  console.log('updateLastMessage called with:', content?.slice(0, 50))
  messages.update(msgs => {
    if (msgs.length === 0) {
      console.warn('No messages to update!')
      return msgs
    }
    const last = msgs[msgs.length - 1]
    const newContent = (last.content || '') + content
    console.log('Updated content length:', newContent.length)
    return [
      ...msgs.slice(0, -1),
      { ...last, content: newContent }
    ]
  })
}

// Очистить чат
export function clearMessages() {
  messages.set([])
}

// Загрузить экспертов с API (только Виктория)
export async function loadExperts() {
  try {
    // Используем порт 8081 для Rust Gateway
    const response = await fetch(`http://${window.location.hostname}:8081/api/experts`)
    if (response.ok) {
      const data = await response.json()
      // Фильтруем - оставляем только Викторию
      const victoriaOnly = data.filter(e =>
        e.name.includes('Виктория') ||
        e.name.includes('Victoria') ||
        e.name.toLowerCase().includes('victoria')
      )

      // Если Виктории нет в списке, создаем её
      if (victoriaOnly.length === 0) {
        const victoria = { id: '1', name: 'Виктория', role: 'Team Lead' }
        experts.set([victoria])
        selectedExpert.set(victoria)
      } else {
        experts.set(victoriaOnly)
        selectedExpert.set(victoriaOnly[0])
      }
    } else {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
  } catch (e) {
    console.error('Failed to load experts:', e)
    // Fallback - только Виктория
    const victoria = { id: '1', name: 'Виктория', role: 'Team Lead' }
    experts.set([victoria])
    selectedExpert.set(victoria)
  }
}

// Отправить сообщение через SSE
export async function sendMessage(content, mode = null) {
  const expertValue = get(selectedExpert)
  const modeValue = mode ?? get(chatMode)

  addMessage('user', content)
  isStreaming.set(true)
  isLoading.set(true)
  error.set(null)
  addMessage('assistant', '', expertValue?.name)

  try {
    // Используем порт 8081 для Rust Gateway
    const response = await fetch(`http://${window.location.hostname}:8081/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        messages: [
          { role: 'user', content: content }
        ],
        model: "victoria-wisdom-30b:latest",
        stream: false, // Наш Rust Gateway пока не поддерживает SSE стриминг напрямую в OpenAI формате
        use_rag: true
      })
    })

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Неизвестная ошибка')
      throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`)
    }

    const data = await response.json()
    const assistantContent = data.choices?.[0]?.message?.content || 'Нет ответа'
    updateLastMessage(assistantContent)

  } catch (e) {
          } catch (e) {
            console.warn('SSE parse error:', e, line)
          }
        }
      }
    }
  } catch (e) {
    let errorMessage = e.message || 'Ошибка при отправке сообщения.'
    if (e.message?.includes('503') || e.message?.includes('service_busy')) {
      errorMessage = 'Сервер перегружен. Подождите и попробуйте снова.'
    } else if (e.message?.includes('Failed to fetch') || e.message?.includes('NetworkError')) {
      errorMessage = 'Нет связи с сервером. Проверьте, что бэкенд запущен (порт 8080).'
    }
    error.set(errorMessage)
    console.error('Chat error:', e)

    // Удаляем пустое сообщение ассистента при ошибке
    messages.update(msgs => {
      if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant' && !msgs[msgs.length - 1].content) {
        return msgs.slice(0, -1)
      }
      return msgs
    })
  } finally {
    isStreaming.set(false)
    isLoading.set(false)
  }
}
