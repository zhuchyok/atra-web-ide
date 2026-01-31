<script>
  import { onMount } from 'svelte'
  import { Terminal } from 'xterm'
  import { FitAddon } from '@xterm/addon-fit'
  import 'xterm/css/xterm.css'

  let container
  let term
  let fitAddon
  let currentLine = ''

  function writeln(t, msg) {
    t.writeln('\x1b[32m' + msg + '\x1b[0m')
  }

  let ws = null
  let isConnected = false
  let connectionTimeoutId = null
  const PTY_CONNECT_TIMEOUT_MS = 10000

  function clearConnectionTimeout() {
    if (connectionTimeoutId != null) {
      clearTimeout(connectionTimeoutId)
      connectionTimeoutId = null
    }
  }

  async function connectPTY() {
    clearConnectionTimeout()
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/api/terminal/pty`
      ws = new WebSocket(wsUrl)

      connectionTimeoutId = setTimeout(() => {
        if (ws && ws.readyState === WebSocket.CONNECTING) {
          ws.close()
          connectionTimeoutId = null
          term.writeln('\r\n\x1b[31m❌ Подключение к PTY превысило время ожидания\x1b[0m')
          term.writeln('\x1b[90mПроверьте, что бэкенд запущен (порт 8080). Повторить: введите help и Enter.\x1b[0m\r\n')
          term.write('$ ')
        }
      }, PTY_CONNECT_TIMEOUT_MS)

      ws.onopen = () => {
        clearConnectionTimeout()
        isConnected = true
        term.writeln('\r\n\x1b[32m✅ Подключено к PTY терминалу\x1b[0m\r\n')
        term.write('$ ')
      }

      ws.onmessage = (event) => {
        term.write(event.data)
      }

      ws.onerror = () => {
        clearConnectionTimeout()
        if (!isConnected) {
          term.writeln('\r\n\x1b[31m❌ Ошибка подключения к PTY\x1b[0m')
          term.writeln('\x1b[90mПовторить: введите help и Enter\x1b[0m\r\n')
        }
        isConnected = false
      }

      ws.onclose = () => {
        clearConnectionTimeout()
        isConnected = false
        if (ws && ws.readyState !== WebSocket.CLOSING) {
          term.writeln('\r\n\x1b[33m⚠️ Соединение закрыто\x1b[0m\r\n')
        }
      }
    } catch (e) {
      clearConnectionTimeout()
      console.error('PTY connection error:', e)
      term.writeln('\r\n\x1b[31m❌ Ошибка: ' + (e.message || 'подключение к PTY') + '\x1b[0m\r\n')
      isConnected = false
    }
  }
  
  function runCommand(t, cmd) {
    if (isConnected && ws && ws.readyState === WebSocket.OPEN) {
      // Отправляем команду через PTY
      ws.send(cmd + '\r')
    } else {
      // Локальный режим (fallback)
      const c = cmd.trim().toLowerCase()
      if (c === 'clear' || c === 'cls') {
        t.clear()
        return
      }
      if (c === 'help' || c === '') {
        writeln(t, 'ATRA Web IDE Terminal (xterm.js)')
        writeln(t, '  help, clear — доступные команды')
        writeln(t, '  Подключение к PTY...')
        connectPTY()
        return
      }
      writeln(t, `\x1b[33m$\x1b[0m ${cmd}`)
      writeln(t, `\x1b[90mПодключение к PTY...\x1b[0m`)
      connectPTY()
    }
  }

  onMount(() => {
    if (!container) return
    term = new Terminal({
      cursorBlink: true,
      theme: {
        background: '#16213e',
        foreground: '#e0e0e0',
        cursor: '#667eea',
        cursorAccent: '#667eea',
      },
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      fontSize: 13,
    })
    fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(container)
    fitAddon.fit()

    term.writeln('')
    writeln(term, 'ATRA Web IDE — Terminal (xterm.js)')
    writeln(term, 'Подключение к PTY...')
    
    // Подключаемся к PTY
    connectPTY()
    
    // Отправляем resize при изменении размера
    const ro = new ResizeObserver(() => {
      fitAddon?.fit()
      if (ws && ws.readyState === WebSocket.OPEN) {
        const cols = term.cols
        const rows = term.rows
        ws.send(JSON.stringify({ type: 'resize', cols, rows }))
      }
    })
    ro.observe(container)

    term.onData((data) => {
      if (isConnected && ws && ws.readyState === WebSocket.OPEN) {
        // Отправляем данные напрямую в PTY
        ws.send(data)
      } else {
        // Локальный режим (fallback)
        const key = data
        if (key === '\r' || key === '\n') {
          runCommand(term, currentLine)
          currentLine = ''
          if (!isConnected) {
            term.write('\r\n$ ')
          }
          return
        }
        if (key === '\u007F' || key === '\b') {
          if (currentLine.length > 0) {
            currentLine = currentLine.slice(0, -1)
            term.write('\b \b')
          }
          return
        }
        if (key >= ' ' && key <= '~' || key.length > 1) {
          currentLine += key
          term.write(key)
        }
      }
    })
    
    return () => {
      if (ws) {
        ws.close()
      }
      ro.disconnect()
      term.dispose()
    }
  })
</script>

<div class="terminal-wrap h-full w-full bg-atra-darker rounded overflow-hidden" bind:this={container}></div>

<style>
  .terminal-wrap :global(.xterm) {
    padding: 8px;
    height: 100%;
  }
  .terminal-wrap :global(.xterm-viewport) {
    overflow-y: auto !important;
  }
</style>
