// A WebSocket that closes the way a browser's does (#522): close() only starts the closing
// handshake, so readyState is CLOSING at once and onclose comes later, when the test calls
// finishClose(). A fake that fired onclose inside close() hid the race between a late onclose
// and the socket that replaced it. Shared by the connection tests; not a test file itself.
export class FakeWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  static instances = []
  static last = null

  static reset() {
    FakeWebSocket.instances = []
    FakeWebSocket.last = null
  }

  // The sockets a hook still counts on: open or opening.
  static live() {
    return FakeWebSocket.instances.filter(ws => ws.readyState <= FakeWebSocket.OPEN)
  }

  constructor() {
    this.readyState = FakeWebSocket.CONNECTING
    this.sent = []
    FakeWebSocket.instances.push(this)
    FakeWebSocket.last = this
  }

  send(data) { this.sent.push(JSON.parse(data)) }

  close() {
    if (this.readyState < FakeWebSocket.CLOSING) this.readyState = FakeWebSocket.CLOSING
  }

  open() {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.()
  }

  // The closing handshake is over (or the server closed the line): only now does onclose fire.
  finishClose(code = 1006) {
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.({ code })
  }

  emit(event) { this.onmessage?.({ data: JSON.stringify(event) }) }

  pings() { return this.sent.filter(m => m.action === 'ping').length }
}
