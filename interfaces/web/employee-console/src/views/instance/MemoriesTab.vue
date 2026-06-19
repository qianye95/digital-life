<template>
  <div>
    <section class="page-hero">
      <div>
        <h1 class="page-title">Memory</h1>
        <p class="page-subtitle">数字生命的记忆沉淀 · 意识流 / 草稿 / 每日 / 联想</p>
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
        <span class="kind-count" v-if="counts[k.key]">{{ counts[k.key] }}</span>
      </button>
    </div>

    <!-- 意识流 / 草稿 / 每日 (按 ## 标题拆分) -->
    <template v-if="active !== 'assoc'">
      <div v-if="loading" class="dev-placeholder"><span class="mono">loading…</span></div>
      <div v-else-if="!segments.length" class="dev-placeholder">
        <span class="mono">// 当前 {{ activeLabel }} 为空</span>
      </div>
      <div v-else class="segments-list">
        <div v-for="(seg, idx) in segments" :key="idx" class="segment-card">
          <div class="segment-head">
            <strong v-if="seg.title" class="segment-title mono">
              {{ seg.title }}
            </strong>
            <strong v-else class="segment-title-untagged">概览</strong>
            <el-button size="small" text @click="copyText(seg.body)">copy</el-button>
          </div>
          <div class="segment-body" v-html="renderMarkdown(seg.body)"></div>
        </div>
      </div>
    </template>

    <!-- 联想：chunks + top_links + sources -->
    <template v-else>
      <div v-if="loadingAssoc" class="dev-placeholder"><span class="mono">loading associations…</span></div>
      <div v-else-if="!assoc.chunks" class="dev-placeholder"><span class="mono">// 无联想数据</span></div>
      <div v-else>
        <div class="neon-grid assoc-stats" style="grid-template-columns: repeat(3, 1fr);">
          <div class="neon-card">
            <div class="brand-sub">CHUNKS</div>
            <div class="stat-num">{{ assoc.chunks }}</div>
          </div>
          <div class="neon-card">
            <div class="brand-sub">ASSOCIATIONS</div>
            <div class="stat-num" style="color: var(--neon-pink);">{{ assoc.associations }}</div>
          </div>
          <div class="neon-card">
            <div class="brand-sub">SOURCES</div>
            <div class="stat-num" style="color: var(--neon-magenta);">{{ assoc.sourceCount }}</div>
          </div>
        </div>

        <h3 class="page-title" style="font-size: 16px; margin: var(--space-5) 0 var(--space-3);">TOP LINKS</h3>
        <div class="neon-card" v-if="topLinks.length">
          <div v-for="(link, i) in topLinks" :key="i" class="link-row">
            <span class="mono link-id">#{{ link.source_chunk_id }}</span>
            <span style="color: var(--text-muted);">→</span>
            <span class="mono link-id">#{{ link.target_chunk_id }}</span>
            <span class="brand-sub mono" style="margin-left: auto; color: var(--neon-cyan);">
              weight {{ Number(link.weight).toFixed(3) }}
            </span>
            <span class="brand-sub mono" style="color: var(--text-muted); margin-left: 8px;">
              · {{ link.reason || '—' }}
            </span>
          </div>
        </div>
        <div v-else class="dev-placeholder"><span class="mono">// top_links 为空</span></div>

        <h3 class="page-title" style="font-size: 16px; margin: var(--space-5) 0 var(--space-3);">SOURCES 分布</h3>
        <div class="neon-grid" style="grid-template-columns: repeat(2, 1fr);">
          <div v-for="(src, i) in sources" :key="i" class="source-row">
            <span class="mono source-name">{{ src.source }}</span>
            <div class="source-bar-wrap">
              <div class="source-bar" :style="{ width: barWidth(src.count) + '%' }"></div>
            </div>
            <span class="mono source-count">{{ src.count }}</span>
          </div>
        </div>
      </div>
    </template>

    <p class="brand-sub" style="margin-top: 16px;">
      <RouterLink :to="`/legacy/employee/${iid}/`">Memory Advisor（entity profile 编辑） →</RouterLink>
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { instanceApi } from '@/api/client'
import { renderMarkdown } from '@/composables/useMarkdown'

const route = useRoute()
const iid = computed(() => String(route.params.iid || ''))

const kinds = [
  { key: 'consciousness', label: '意识流', icon: '🌀' },
  { key: 'diary',         label: '日记',   icon: '📔' },
  { key: 'assoc',         label: '联想',   icon: '🔗' },
]
const active = ref('consciousness')

const loading = ref(false)
const loadingAssoc = ref(false)
const currentContent = ref('')
const segments = ref([])

const assoc = ref({
  chunks: 0,
  associations: 0,
  top_links: [],
  sources: [],
  sourceCount: 0,
})
const counts = ref({})

const topLinks = computed(() => Array.isArray(assoc.value.top_links) ? assoc.value.top_links : [])
const sources = computed(() => Array.isArray(assoc.value.sources) ? assoc.value.sources : [])
const activeLabel = computed(() => kinds.find(k => k.key === active.value)?.label || '—')

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

// 把 ## 标题分段：返回 [{title, body}]
function splitByChapters(content) {
  if (!content) return []
  // 用行首 ## 匹配（含日期时间戳的章节标题）
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
      // 还没遇到 ## 之前的内容（H1 / 介绍段）也算一段
      if (!current) current = { title: '', body: line + '\n' }
      else current.body += line + '\n'
    } else if (current) {
      current.body += line + '\n'
    }
  }
  if (current) out.push(current)
  // 清理 body 末尾空行
  return out.map(s => ({ ...s, body: s.body.replace(/^\n+/, '').replace(/\n+$/, '') }))
    .filter(s => s.title || s.body.trim())
    .reverse()  // 最新在上
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
    }
  } finally {
    loadingAssoc.value = false
  }
}

async function reloadAll() {
  await Promise.all([loadMemory('consciousness'), loadMemory('diary'), loadAssoc()])
}

watch(active, (v) => {
  if (v === 'assoc') {
    if (!assoc.value.chunks) loadAssoc()
  } else {
    loadMemory(v)
  }
})

onMounted(() => {
  // 预加载所有 kind counts（让 tab 上看到数字）
  reloadAll()
})
</script>

<style scoped>
.kind-tabs {
  display: flex;
  gap: 4px;
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

.segments-list { display: flex; flex-direction: column; gap: var(--space-3); }
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
  padding: 8px 12px;
  background: var(--bg-deep);
  border-bottom: 1px solid var(--border-divider);
}
.segment-title {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--neon-cyan);
  letter-spacing: 0.04em;
}
.segment-title-untagged {
  font-family: var(--font-display);
  font-size: 12px;
  color: var(--text-muted);
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

.assoc-stats .neon-card { padding: 14px 18px; }
.stat-num {
  font-family: var(--font-display);
  font-size: 28px;
  color: var(--neon-cyan);
  margin-top: 4px;
}

.link-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border-divider);
}
.link-id {
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  color: var(--neon-cyan);
  font-size: 11px;
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
  width: 180px;
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
  width: 60px;
  text-align: right;
  color: var(--neon-cyan);
  font-size: 12px;
}
</style>
