// SPDX-License-Identifier: GPL-3.0-only
// Isolated CI only: read exact BottomBar menu/project-selection button rectangles.
// NEVER dispatch a DOM click, invoke store methods or mutate React state.
// The actual action is a real X11 pointer click from native_close_proof.py.
const port = Number(process.argv[2])
const target = process.argv[3]
if (process.env.CI !== 'true' || process.env.ZX7_POINTER_E2E_CDP_PORT !== '19393' ||
    port !== 19393 || !['menu', 'project-selection'].includes(target)) {
  throw Error('Native project-close geometry only available in isolated source CI')
}
const deadline = Date.now() + 10000
let page
while (Date.now() < deadline) {
  try {
    const response = await fetch('http://127.0.0.1:19393/json/list', {
      signal: AbortSignal.timeout(1200),
    })
    if (!response.ok) throw Error('No bound Chromium target')
    const pages = await response.json()
    page = pages.find(item => item.type === 'page' &&
      (item.url === 'http://127.0.0.1:5173/' ||
       item.url.startsWith('http://127.0.0.1:5173/?')))
    if (page) break
  } catch {}
  await new Promise(resolve => setTimeout(resolve, 150))
}
if (!page || !/^ws:\/\/127\.0\.0\.1:\d+\//.test(page.webSocketDebuggerUrl || '')) {
  throw Error('No isolated pinned Electron renderer page')
}
const expression = `(() => {
  const target = ${JSON.stringify(target)};
  const elements = target === 'menu'
    ? [...document.querySelectorAll('button[title="Velorn"]')]
    : [...document.querySelectorAll('button')].filter(
        el => el.textContent?.trim() === 'Project Selection');
  if (elements.length !== 1) return {visible:false, unique:false};
  const r = elements[0].getBoundingClientRect();
  return {
    unique:true,
    visible:r.width >= 20 && r.height >= 12 &&
      r.left >= 0 && r.top >= 0 &&
      r.right <= innerWidth && r.bottom <= innerHeight,
    rect:{left:r.left,top:r.top,right:r.right,bottom:r.bottom,
          width:r.width,height:r.height},
    window:{width:innerWidth,height:innerHeight,pixelRatio:devicePixelRatio}
  };
})()`
const ws = new WebSocket(page.webSocketDebuggerUrl)
const value = await new Promise((resolve, reject) => {
  const timer = setTimeout(() => { ws.close(); reject(Error('Geometry timeout')) }, 7000)
  const fail = error => { clearTimeout(timer); reject(error) }
  ws.addEventListener('error', () => fail(Error('Read-only CDP connection failed')))
  ws.addEventListener('open', () => {
    ws.send(JSON.stringify({ id:1, method:'Runtime.evaluate', params: {
      expression, returnByValue:true, awaitPromise:false,
    }}))
  })
  ws.addEventListener('message', event => {
    try {
      const reply = JSON.parse(event.data)
      if (reply.id !== 1) return
      if (reply.error || reply.result?.exceptionDetails) throw Error('Read-only geometry exception')
      const data = reply.result?.result?.value
      if (!data || typeof data.visible !== 'boolean') throw Error('Malformed geometry')
      clearTimeout(timer)
      ws.close()
      resolve(data)
    } catch (error) { fail(error) }
  })
})
process.stdout.write(JSON.stringify(value) + '\n')
