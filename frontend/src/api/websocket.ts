type MessageHandler = (data: any) => void

interface WebSocketHandlers {
  onOpen?: () => void
  onClose?: () => void
  onError?: (event: Event) => void
}

export function createWebSocket(
  path: string,
  onMessage: MessageHandler,
  handlers: WebSocketHandlers = {},
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const ws = new WebSocket(`${protocol}//${host}${path}`)

  ws.onopen = () => {
    handlers.onOpen?.()
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onMessage(data)
    } catch {
      console.error('Failed to parse WS message:', event.data)
    }
  }

  ws.onerror = (event) => {
    console.error('WebSocket error:', event)
    handlers.onError?.(event)
  }

  ws.onclose = () => {
    handlers.onClose?.()
  }

  return ws
}
