/**
 * Smoke/unit tests for chat store (PROJECT_GAPS §2, QA).
 * Run: npm run test
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { get } from 'svelte/store'
import { messages, chatMode, addMessage, clearMessages } from './chat.js'

describe('chat store', () => {
  beforeEach(() => {
    clearMessages()
  })

  it('messages initial state is empty array', () => {
    expect(get(messages)).toEqual([])
  })

  it('chatMode initial state is agent', () => {
    expect(get(chatMode)).toBe('agent')
  })

  it('addMessage adds one message', () => {
    addMessage('user', 'Hello')
    const msgs = get(messages)
    expect(msgs).toHaveLength(1)
    expect(msgs[0].role).toBe('user')
    expect(msgs[0].content).toBe('Hello')
  })

  it('clearMessages resets messages', () => {
    addMessage('user', 'Hi')
    clearMessages()
    expect(get(messages)).toEqual([])
  })
})
