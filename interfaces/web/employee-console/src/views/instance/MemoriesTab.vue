<template>
  <div>
    <section class="page-hero">
      <div>
        <h1 class="page-title">Memory</h1>
        <p class="page-subtitle">数字生命的记忆沉淀 · 8 个文件 + 联想图谱</p>
      </div>
      <el-button @click="reloadAll"><el-icon><Refresh /></el-icon></el-button>
    </section>

    <!-- 顶栏 tabs -->
    <div class="kind-tabs">
      <button
        v-for="k in kinds"
        :key="k.key"
        class="kind-tab"
        :class="{ active: active === k.key }"
        @click="active = k.key"
      >
        <span class="kind-icon">{{ k.icon }}</span>
        <span>{{ k.label }}</span>
        <span class="kind-count" v-if="counts[k.key] != null">{{ counts[k.key] }}</span>
        <span class="kind-empty" v-else-if="loaded[k.key] === true && counts[k.key] === 0">0</span>
      </button>
    </div>

    <!-- 文件型记忆 (按 ## 标题拆分, 折叠显示) -->
    <template v-if="active !== 'assoc'">
      <div v-if="loading" class="dev-placeholder"><span class="mono">loading…</span></div>
      <div v-else-if="!segments.length" class="dev-placeholder">
        <span class="mono">// 当前 {{ activeLabel }} 为空</span>
      </div>
      <div v-else class="segments-list">
        <!-- 总字数 / 章节统计 -->
        <div class="kind-summary brand-sub">
          {{ activeLabel }} · 共 {{ segments.length }} 段 · {{ totalChars }} 字 · 文件
          <code class="mono">{{ activeMeta.file }}</code>
        </div>

        <!-- 折叠 / 展开切换 -->
        <div class="seg-toolbar">
          <el-button size="small" text @click="collapseAll">全部折叠</el-button>
          <el-button size="small" text @click="expandAll">全部展开</el-button>
        </div>

        <details
          v-for="(seg, idx) in segments"
          :key="idx"
          class="segment-card"
          :open="idx < 3"
          :ref="el => segRefs[idx] = el"
        >
          <summary class="segment-head">
            <span class="segment-title mono" v-if="seg.title">{{ seg.title }}</span>
            <span class="segment-title-untagged" v-else>概览</span>
            <span class="brand-sub mono segment-size">{{ seg.body.length }} 字</span>
            <el-button size="small" text @click.prevent.stop="copyText(seg.body)">copy</el-button>
          </summary>
          <div class="segment-body" v-html="renderMarkdown(seg.body)"></div>
        </details>
      </div>
    </template>

    <!-- 联想:实际关联 + reason,统计移底 -->
    <template v-else>
      <div v-if="loadingAssoc" class="dev-placeholder"><span class="mono">loading associations…</span></div>
      <div v-else-if="!assoc.chunks" class="dev-placeholder"><span class="mono">// 无联想数据</span></div>
      <div v-else>
        <!-- 摘要 -->
        <div class="kind-summary brand-sub">
          联想图谱 · {{ assoc.chunks }} chunks / {{ assoc.associations }} 关联 / {{ assoc.sourceCount }} 来源
        </div>

        <!-- TOP 关联:显示实际 chunk_a → chunk_b 文本 + reason -->
        <h3 class="section-title">关联详情 ({{ topLinks.length }})</h3>
        <p v-if="!topLinks.length" class="brand-sub mono" style="color: var(--text-muted);">// 暂无关联</p>
        <div class="assoc-list">
          <div v-for="(link, i) in topLinks" :key="i" class="assoc-card">
            <div class="assoc-head">
              <span class="assoc-weight" :title="'weight ' + link.weight">
                w {{ Number(link.weight).toFixed(2) }}
              </span>
              <span class="assoc-sources mono">
                {{ sourceLabel(link.source_source) }} → {{ sourceLabel(link.target_source) }}
              </span>
              <span class="assoc-reason" v-if="link.reason">{{ link.reason }}</span>
            </div>
            <div class="assoc-pair">
              <div class="assoc-side from-side">
                <div class="side-label">FROM #{{ link.source_chunk_id }}</div>
                <div class="side-body mono">{{ trimText(link.source_text, 200) }}</div>
              </div>
              <div class="assoc-arrow">→</div>
              <div class="assoc-side to-side">
                <div class="side-label">TO #{{ link.target_chunk_id }}</div>
                <div class="side-body mono">{{ trimText(link.target_text, 200) }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 来源分布(折叠到底,统计 curious 时看) -->
        <details class="source-dist">
          <summary>来源分布 ({{ assoc.sourceCount }})</summary>
          <div class="neon-grid" style="grid-template-columns: repeat(2, 1fr);">
            <div v-for="(src, i) in sources" :key="i" class="source-row">
              <span class="mono source-name">{{ sourceLabel(src.source) }}</span>
              <div class="source-bar-wrap">
                <div class="source-bar" :style="{ width: barWidth(src.count) + '%' }"></div>
              </div>
              <span class="mono source-count">{{ src.count }}</span>
            </div>
          </div>
        </details>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { instanceApi } from '@/api/client'
import { renderMarkdown } from '@/composables/useMarkdown'

const route = useRoute()
const iid = computed(() => String(route.params.iid || ''))

// 9 个 kind,顺序按重要性:意识流 / 联想 / 日记 / 教训 / 草稿 / 上下文 / 目标 / 洞察 / 关于他
const kinds = [
  { key: 'consciousness', label: '意识流', icon: '🌀', file: 'CONSCIOUSNESS.md' },
  { key: 'assoc',         label: '联想',   icon: '🔗', file: 'associations API' },
  { key: 'diary',         label: '日记',   icon: '📔', file: 'diary/' },
  { key: 'lessons',       label: '教训',   icon: '⚠️', file: 'LESSONS.md' },
  { key: 'scratchpad',    label: '草稿',   icon: '📝', file: 'SCRATCHPAD.md' },
  { key: 'context',       label: '上下文', icon: '🔗', file: 'CONTEXT.md' },
  { key: 'goals',         label: '目标',   icon: '🎯', file: 'GOALS.md' },
  { key: 'insights',      label: '洞察',   icon: '💡', file: 'INSIGHTS.md' },
  { key: 'him',           label: '关于他', icon: '👤', file: 'HIM.md' },
]
const active = ref('consciousness')

const loading = ref(false)
const loadingAssoc = ref(false)
const currentContent = ref('')
const segments = ref([])
const loaded = ref({})  // {kind: bool} 哪些已加载

const assoc = ref({
  chunks: 0,
  associations: 0,
  top_links: [],
  sources: [],
  sourceCount: 0,
})
const counts = ref({})
const segRefs = ref([])

const topLinks = computed(() => Array.isArray(assoc.value.top_links) ? assoc.value.top_links : [])
const sources = computed(() => Array.isArray(assoc.value.sources) ? assoc.value.sources : [])
const activeLabel = computed(() => kinds.find(k => k.key === active.value)?.label || '—')
const activeMeta = computed(() => kinds.find(k => k.key === active.value) || {})
const totalChars = computed(() => segments.value.reduce((a, s) => a + (s.body || '').length, 0))

function copyText(text) {
  navigator.clipboard.writeText(String(text || '')).then(
    () => ElMessage.success('已复制'),
    () => ElMessage.warning('复制失败'),
  )
}

function barWidth(count) {
  const max = Math.max(1, ...sources.value.map(s => s.count))
  return Math.max(2, (count / max) * 100)
}

function trimText(text, n) {
  if (!text) return '(空)'
  text = String(text).replace(/\s+/g, ' ').trim()
  return text.length > n ? text.slice(0, n) + '…' : text
}

const SOURCE_LABELS = {
  digest_session: '会话摘要',
  identity: '身份',
  lessons: '教训',
  notes: '笔记',
  rules: '规则',
  work: '工作',
  context: '上下文',
  plans: '计划',
  goals: '目标',
  him: '关于他',
}
function sourceLabel(s) {
  return SOURCE_LABELS[s] || s || '?'
}

// 把 ## 标题分段:返回 [{title, body}]
function splitByChapters(content) {
  if (!content) return []
  const lines = String(content).split('\n')
  const out = []
  let current = null
  for (const line of lines) {
    if (/^##\s/.test(line)) {
      if (current) out.push(current)
      current = { title: line.replace(/^##\s*/, '').trim(), body: '' }
    } else if (current) {
      current.body += line + '\n'
    } else if (line.trim() && !line.startsWith('# ')) {
      current = { title: '', body: line + '\n' }
    }
  }
  if (current) out.push(current)
  return out.map(s => ({ ...s, body: s.body.replace(/^\n+/, '').replace(/\n+$/, '') }))
    .filter(s => s.title || s.body.trim())
    .reverse()
}

async function loadMemory(kind) {
  loading.value = true
  segments.value = []
  try {
    const d = await instanceApi(iid.value).memories(kind)
    if (d && !d.error) {
      currentContent.value = String(d.content || '')
      const segs = splitByChapters(currentContent.value)
      segments.value = segs
      counts.value = { ...counts.value, [kind]: segs.length }
    } else {
      counts.value = { ...counts.value, [kind]: 0 }
    }
    loaded.value[kind] = true
  } finally {
    loading.value = false
  }
}

async function loadAssoc() {
  loadingAssoc.value = true
  try {
    const d = await instanceApi(iid.value).associations()
    if (d && !d.error) {
      assoc.value = {
        chunks: d.chunks || 0,
        associations: d.associations || 0,
        top_links: Array.isArray(d.top_links) ? d.top_links : [],
        sources: Array.isArray(d.sources) ? d.sources : [],
        sourceCount: (Array.isArray(d.sources) ? d.sources.length : 0),
      }
      counts.value = { ...counts.value, assoc: d.associations || 0 }
    }
    loaded.value.assoc = true
  } finally {
    loadingAssoc.value = false
  }
}

function collapseAll() {
  segRefs.value.forEach(r => { if (r) r.removeAttribute('open') })
}
function expandAll() {
  segRefs.value.forEach(r => { if (r) r.setAttribute('open', '') })
}

async function reloadAll() {
  // 预加载 consciousness + assoc (默认两个最常用)
  // 其他按需加载 (切 tab 时)
  await Promise.all([loadMemory('consciousness'), loadAssoc()])
}

watch(active, (v) => {
  if (v === 'assoc') {
    if (!loaded.value.assoc) loadAssoc()
  } else {
    if (!loaded.value[v]) loadMemory(v)
  }
})

onMounted(() => {
  reloadAll()
})
</script>

<style scoped>
.kind-tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-line);
  padding-bottom: 8px;
}
.kind-tab {
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-secondary);
  padding: 8px 14px;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 160ms ease;
}
.kind-tab:hover { color: var(--text-primary); background: var(--bg-overlay); }
.kind-tab.active {
  color: var(--neon-cyan);
  border-color: var(--border-line-strong);
  background: var(--neon-cyan-soft);
  box-shadow: var(--shadow-glow-cyan);
}
.kind-icon { font-size: 16px; }
.kind-count {
  background: var(--bg-elevated);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--neon-cyan);
}
.kind-empty {
  background: var(--bg-elevated);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
  opacity: 0.6;
}

.segments-list { display: flex; flex-direction: column; gap: var(--space-3); }
.kind-summary {
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 0.04em;
  margin-bottom: var(--space-2);
}
.seg-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  margin-bottom: 4px;
}

.segment-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-line);
  border-left: 3px solid var(--neon-cyan);
  border-radius: var(--radius);
  padding: 0;
  overflow: hidden;
}
.segment-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-deep);
  border-bottom: 1px solid var(--border-divider);
  cursor: pointer;
  list-style: none;
}
.segment-head::-webkit-details-marker { display: none; }
.segment-title {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--neon-cyan);
  letter-spacing: 0.04em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.segment-title-untagged {
  flex: 1;
  font-family: var(--font-display);
  font-size: 12px;
  color: var(--text-muted);
}
.segment-size {
  color: var(--text-muted);
  font-size: 10px;
  opacity: 0.7;
}
.segment-body {
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
}
.segment-body :deep(h1),
.segment-body :deep(h2),
.segment-body :deep(h3) {
  font-family: var(--font-display);
  color: var(--neon-cyan);
  font-size: 14px;
  margin: 6px 0;
}
.segment-body :deep(pre) {
  background: var(--bg-deep);
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 12px;
  overflow-x: auto;
}
.segment-body :deep(code) {
  background: var(--bg-deep);
  padding: 1px 4px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 12px;
}
.segment-body :deep(ul),
.segment-body :deep(ol) { margin: 6px 0; padding-left: 22px; }
.segment-body :deep(li) { margin: 3px 0; }

/* === 联想 === */
.section-title {
  font-family: var(--font-display);
  font-size: 14px;
  color: var(--neon-cyan);
  letter-spacing: 0.05em;
  margin: var(--space-4) 0 var(--space-2);
}

.assoc-list { display: flex; flex-direction: column; gap: var(--space-3); }
.assoc-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-line);
  border-radius: var(--radius);
  padding: 10px 12px;
}
.assoc-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.assoc-weight {
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: var(--neon-cyan-soft);
  color: var(--neon-cyan);
  font-weight: 600;
}
.assoc-sources {
  font-size: 11px;
  color: var(--text-muted);
}
.assoc-reason {
  margin-left: auto;
  font-size: 11px;
  font-style: italic;
  color: var(--neon-magenta);
  max-width: 50%;
  text-align: right;
}

.assoc-pair {
  display: grid;
  grid-template-columns: 1fr 24px 1fr;
  gap: 8px;
  align-items: stretch;
}
.assoc-side {
  background: var(--bg-deep);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  min-height: 60px;
}
.from-side { border-left: 2px solid var(--neon-pink); }
.to-side { border-left: 2px solid var(--neon-cyan); }
.side-label {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.side-body {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.assoc-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 16px;
}

.source-dist {
  margin-top: var(--space-4);
  padding: 10px 12px;
  background: var(--bg-deep);
  border: 1px dashed var(--border-line);
  border-radius: var(--radius);
}
.source-dist summary {
  cursor: pointer;
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}
.source-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  background: var(--bg-panel);
  border: 1px solid var(--border-line);
  border-radius: var(--radius);
  margin-bottom: 6px;
}
.source-name {
  width: 100px;
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.source-bar-wrap {
  flex: 1;
  height: 6px;
  background: var(--bg-elevated);
  border-radius: 3px;
  overflow: hidden;
}
.source-bar {
  height: 100%;
  background: var(--neon-cyan);
  box-shadow: 0 0 8px var(--neon-cyan);
  transition: width 800ms;
}
.source-count {
  width: 50px;
  text-align: right;
  color: var(--neon-cyan);
  font-size: 12px;
}
</style>
