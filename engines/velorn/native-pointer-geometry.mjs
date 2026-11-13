// SPDX-License-Identifier: GPL-3.0-only
// CI-only: read viewport geometry from the already-running actual Electron
// renderer. Does NOT synthesize a mouse event or mutate application state.
// Only real X11 xdotool button motion drives the native clip edit.
const port = Number(process.argv[2])
const wantedClipId = process.argv[3]
if (process.env.CI !== 'true' ||
    !Number.isInteger(port) || port < 1025 || port > 65535 ||
    !wantedClipId || wantedClipId.length > 240) {
  throw Error('CI pointer geometry requires a bounded port and native clip ID')
}
const targetUrl = `http://127.0.0.1:${port}/json/list`
const deadline = Date.now() + 10000
let page
while (Date.now() < deadline) {
  try {
    const response = await fetch(targetUrl, { signal: AbortSignal.timeout(1400) })
    if (!response.ok) throw Error(`CDP target HTTP ${response.status}`)
    const pages = await response.json()
    page = pages.find(item => item.type === 'page' &&
      (item.url === 'http://127.0.0.1:5173/' ||
       item.url.startsWith('http://127.0.0.1:5173/?')))
    if (page) break
  } catch {}
  await new Promise(resolve => setTimeout(resolve, 150))
}
if (!page || !/^ws:\/\/127\.0\.0\.1:\d+\//.test(page.webSocketDebuggerUrl || '')) {
  throw Error('No loopback Chromium page target from pinned Electron process')
}
const readGeometry = `(() => {
  const id = ${JSON.stringify(wantedClipId)};
  const viewport = document.querySelector('[data-testid="timeline-viewport"]');
  const content = document.querySelector('[data-testid="timeline-track-content"]');
  const clip = [...document.querySelectorAll('[data-clip-id]')]
    .find(el => el.getAttribute('data-clip-id') === id);
  const rect = el => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x:r.x, y:r.y, width:r.width, height:r.height,
            top:r.top, bottom:r.bottom, left:r.left, right:r.right};
  };
  const cr = rect(clip), vr = rect(viewport), tr = rect(content);
  const visible = !!(cr && vr && tr && cr.width >= 24 && cr.height >= 12 &&
    cr.left + 12 < vr.right && cr.right - 12 > vr.left &&
    cr.top + 10 < tr.bottom && cr.bottom - 10 > tr.top);
  return {visible, clip:cr, viewport:vr, content:tr,
          window:{width:innerWidth,height:innerHeight,
                  x:screenX,y:screenY,pixelRatio:devicePixelRatio},
          scrollTop:content?.scrollTop ?? null};
})()`
const ws = new WebSocket(page.webSocketDebuggerUrl)
const payload = await new Promise((resolve, reject) => {
  const timer = setTimeout(() => {
    ws.close()
    reject(Error('Timed out waiting for read-only renderer geometry'))
  }, 7000)
  const fail = error => { clearTimeout(timer); reject(error) }
  ws.addEventListener('error', () => fail(Error('Chromium local devtools connection failed')))
  ws.addEventListener('open', () => {
    ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: {
      expression: readGeometry, returnByValue: true, awaitPromise: false
    }}))
  })
  ws.addEventListener('message', event => {
    try {
      const response = JSON.parse(event.data)
      if (response.id !== 1) return
      if (response.error || response.result?.exceptionDetails) {
        throw Error('Native renderer geometry evaluation failed')
      }
      const value = response.result?.result?.value
      if (!value || typeof value.visible !== 'boolean') {
        throw Error('Native renderer geometry incomplete')
      }
      clearTimeout(timer)
      ws.close()
      resolve(value)
    } catch (error) { fail(error) }
  })
})
process.stdout.write(JSON.stringify(payload) + '\n')
