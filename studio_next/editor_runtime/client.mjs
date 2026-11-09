// SPDX-License-Identifier: GPL-3.0-only
// Trusted local engine transport; model permission checks belong in BODY.
import fs from 'node:fs/promises'
import path from 'node:path'

const NETWORK_OR_HOST_TOOLS = new Set([
  'search_stock_media', 'import_stock_media', 'diagnose_comfyui_connection',
  'set_comfyui_connection', 'repair_comfyui_connection', 'guide_comfyui_setup',
  'control_comfyui_launcher', 'get_comfyui_launcher_logs', 'validate_comfyui_nodes',
  'list_velorn_workflows', 'inspect_velorn_workflow', 'list_comfyui_templates',
  'import_comfyui_workflow', 'install_workflow_setup', 'get_workflow_install_status',
  'generate_music', 'generate_captions', 'list_recent_projects', 'duplicate_project',
  'run_mcp_action_plan', 'export_delivery_batch',
])
export function blockedReason(name) {
  if (NETWORK_OR_HOST_TOOLS.has(name) || /^(queue_|regenerate_|transcribe_)/.test(name))
    return 'Network, generation, launcher, cross-project, nested or batch host authority needs separate review.'
  return null
}
function contained(root, candidate) {
  const relative = path.relative(root, candidate)
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative))
}
export async function scopedPath(value, roots) {
  if (typeof value !== 'string' || !path.isAbsolute(value)) throw Error('An absolute scoped path is required.')
  const candidate = path.resolve(value)
  let ancestor = candidate
  const suffix = []
  while (true) {
    try { ancestor = await fs.realpath(ancestor); break }
    catch (error) {
      if (error.code !== 'ENOENT') throw error
      const entry = await fs.lstat(ancestor).catch(() => null)
      if (entry?.isSymbolicLink()) throw Error(`Dangling symlink is not a scoped output: ${value}`)
      if (path.dirname(ancestor) === ancestor) throw error
      suffix.unshift(path.basename(ancestor)); ancestor = path.dirname(ancestor)
    }
  }
  const resolved = path.join(ancestor, ...suffix)
  const canonicalRoots = await Promise.all(roots.map(root => fs.realpath(root)))
  if (!canonicalRoots.some(root => contained(root, resolved))) throw Error(`Path is outside allocated roots: ${value}`)
  return resolved
}
export class VelornClient {
  constructor({ url = 'http://127.0.0.1:19790/mcp', projectsRoot, stagingRoot, outputRoot, timeoutMs = 65000 }) {
    const endpoint = new URL(url)
    if (endpoint.protocol !== 'http:' || endpoint.hostname !== '127.0.0.1' || endpoint.port !== '19790' || endpoint.pathname !== '/mcp' || endpoint.search || endpoint.hash || endpoint.username || endpoint.password)
      throw Error('This pinned upstream client only supports the local fixed MCP endpoint.')
    this.url = url; this.roots = { projectsRoot, stagingRoot, outputRoot }
    if (Object.values(this.roots).some(root => !root || !path.isAbsolute(root))) throw Error('Explicit absolute project, staging and output roots are required.')
    this.timeoutMs = timeoutMs; this.tools = new Map(); this.sequence = 0
  }
  async request(method, params) {
    const id = ++this.sequence
    const response = await fetch(this.url, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, redirect: 'error',
      body: JSON.stringify({ jsonrpc: '2.0', id, method, params }),
      signal: AbortSignal.timeout(this.timeoutMs),
    })
    if (!response.ok) throw Error(`Velorn HTTP ${response.status}`)
    const message = await response.json()
    if (message.jsonrpc !== '2.0' || message.id !== id) throw Error('Invalid native RPC correlation.')
    if (message.error) throw Error(message.error.message)
    return message.result
  }
  async discover() {
    const { tools } = await this.request('tools/list', {})
    if (!Array.isArray(tools)) throw Error('Invalid native tool catalog.')
    this.tools = new Map(tools.map(tool => [tool.name, tool]))
    return tools.map(tool => ({ ...tool, bodyPolicy: { blocked: !!blockedReason(tool.name), reason: blockedReason(tool.name) } }))
  }
  async call(name, args = {}) {
    if (!this.tools.size) await this.discover()
    if (!this.tools.has(name)) throw Error(`Tool was not discovered from the pinned upstream: ${name}`)
    const denied = blockedReason(name)
    if (denied) throw Error(`${name} blocked: ${denied}`)
    const payload = structuredClone(args)
    const { projectsRoot, stagingRoot, outputRoot } = this.roots
    if (name === 'create_project') {
      const projectName = payload.name || payload.projectName || payload.title
      if (typeof projectName !== 'string' || !projectName.trim() || /[\/\\]/.test(projectName) || ['.', '..'].includes(projectName)) throw Error('Project name must be one nonempty path component.')
    }
    if (name === 'open_project' && !payload.projectPath) throw Error('Use a scoped projectPath, not global recent-project lookup.')
    for (const key of ['path', 'filePath', 'sourcePath', 'projectPath', 'sourceProjectPath', 'outputPath', 'rendersDir']) {
      if (payload[key] == null) continue
      const roots = name === 'import_asset_from_path' || name === 'relink_asset'
        ? [projectsRoot, stagingRoot]
        : key === 'outputPath' || name === 'inspect_export_file' ? [projectsRoot, outputRoot] : [projectsRoot]
      payload[key] = await scopedPath(payload[key], roots)
    }
    const result = await this.request('tools/call', { name, arguments: payload })
    if (result.isError) throw Error(result.content?.filter(item => item.type === 'text').map(item => item.text).join('\n') || `${name} failed`)
    const texts = result.content?.filter(item => item.type === 'text') || []
    let data
    if (texts.length === 1) { try { data = JSON.parse(texts[0].text) } catch { /* Retain text content. */ } }
    if (data?.success === false && payload.previewOnly !== true) throw Error(`${name}: ${data.message || JSON.stringify(data)}`)
    return { ...result, data }
  }
  async waitForState(predicate, { timeoutMs = 15000, intervalMs = 150 } = {}) {
    const deadline = Date.now() + timeoutMs
    do {
      const state = (await this.call('get_project')).data
      if (predicate(state)) return state
      await new Promise(resolve => setTimeout(resolve, intervalMs))
    } while (Date.now() < deadline)
    throw Error('Timed out waiting for upstream debounced project snapshot.')
  }
}
