<template>
  <div>
    <section class="page-hero">
      <div>
        <h1 class="page-title">{{ instanceName }}</h1>
        <p class="page-subtitle">{{ instanceTagline }}</p>
      </div>
      <div style="display: flex; gap: 16px;">
        <div class="neon-card" style="padding: 8px 16px; min-width: 100px;">
          <div class="brand-sub">Energy</div>
          <div style="font-family: var(--font-display); font-size: 24px; color: var(--neon-cyan);">
            {{ Math.round(Number(energy) || 0) }}%
          </div>
        </div>
        <div class="neon-card" style="padding: 8px 16px; min-width: 100px;">
          <div class="brand-sub">status</div>
          <div style="display: flex; align-items: center; gap: 6px; margin-top: 4px;">
            <span class="status-dot" :class="String(status || 'idle')"></span>
            <strong>{{ statusLabel }}</strong>
          </div>
        </div>
        <div class="neon-card" style="padding: 8px 16px; min-width: 100px;">
          <div class="brand-sub">mode</div>
          <div style="margin-top: 4px; font-family: var(--font-mono); font-size: 13px;"
               :style="{ color: isAbnormal ? 'var(--neon-red)' : 'var(--text-primary)' }">
            {{ modeLabel || (mode || '—') }}
          </div>
        </div>
      </div>
    </section>

    <!-- 异常 banner（仅当 status=error） -->
    <div v-if="isAbnormal" class="blocked-banner">
      <div>
        <strong>⚠ 数字生命异常</strong>
        <div class="brand-sub mono error-reason" v-if="healthReason"
             style="margin-top: 6px;">
          {{ healthReason }}
        </div>
        <div class="brand-sub" style="margin-top: 8px; color: var(--text-muted);">
          异常基于真实事件源判断：
          <code>turn.error</code>（模型调用失败）/ <code>flow_event severity=error</code>（事件流严重错误）。
          <br>
          自动恢复路径：下一次模型调用成功（任意无 error 的 role=assistant turn）自动恢复 ok；
          或者 reset 按钮仅 abort 卡住的 wake（不动 lifecycle RUNNING/BLOCKED，模型继续自治）。
        </div>
      </div>
      <el-button
        type="danger"
        :loading="resettingAffair"
        @click="resetAffair"
      >立即解卡 / reset</el-button>
    </div>

    <!-- 精力曲线（暂时禁用，待专门的 vitals 历史 endpoint） -->
    <div class="neon-card" style="margin-bottom: var(--space-5);">
      <h3 style="font-family: var(--font-display); color: var(--text-secondary); margin: 0 0 var(--space-4);">
        Energy Timeline
      </h3>
      <p class="brand-sub" style="color: var(--text-muted);">
        ⚡ 当前精力 {{ Math.round(Number(energy) || 0) }}%
        —— 详细 24h 曲线需要新增 vitals 历史 endpoint（次迭代再做）。
      </p>
    </div>

    <!-- 三栏快照 -->
    <div class="neon-grid" style="grid-template-columns: repeat(3, 1fr);">
      <div class="neon-card">
        <h3>最近唤醒</h3>
        <template v-if="recentWakes.length">
          <div v-for="w in recentWakes" :key="w.id" class="entity-row wake-row" @click="goSessions">
            <span class="status-dot" :class="String(w.status) === 'running' ? 'live' : 'idle'"></span>
            <div style="flex: 1;">
              <div class="mono" style="font-size: 12px;">
                #{{ w.id }} · {{ wakeTriggerLabel(w) }}
              </div>
              <div class="brand-sub mono" style="color: var(--text-muted); font-size: 11px;">
                {{ safeFmtShort(w.started_at) }}
                · 耗时 {{ wakeDuration(w) }}
                <span v-if="w.message_count"> · {{ w.message_count }} 条</span>
              </div>
            </div>
            <span class="brand-sub" style="color: var(--neon-cyan);">→</span>
          </div>
        </template>
        <div v-else class="brand-sub" style="color: var(--text-muted);">无最近唤醒</div>
        <div style="margin-top: 8px;">
          <RouterLink to="sessions" class="brand-sub" style="font-size: 11px; color: var(--neon-cyan);">
            查看全部 wakes →
          </RouterLink>
        </div>
      </div>

      <div class="neon-card">
        <h3>待办 Top</h3>
        <template v-if="recentTodos.length">
          <div v-for="t in recentTodos" :key="t.id" class="entity-row">
            <span class="mono" style="color: var(--neon-pink);">●</span>
            <span>{{ String(t.title || '(无标题)') }}</span>
            <el-tag v-if="t.priority" size="small" :type="priorityTag(String(t.priority))">
              {{ t.priority }}
            </el-tag>
          </div>
        </template>
        <div v-else class="brand-sub" style="color: var(--text-muted);">无待办</div>
      </div>

      <div class="neon-card">
        <h3>记账 / budget</h3>
        <div v-if="budgetHour" class="entity-row">
          <span>Token / hour</span>
          <span class="mono" style="color: var(--neon-cyan);">
            {{ formatTokens(Number(budgetHour?.used) || 0) }} / {{ formatTokens(Number(budgetHour?.limit) || 0) }}
          </span>
        </div>
        <div v-if="budgetDay" class="entity-row">
          <span>Token / day</span>
          <span class="mono" style="color: var(--neon-cyan);">
            {{ formatTokens(Number(budgetDay?.used) || 0) }} / {{ formatTokens(Number(budgetDay?.limit) || 0) }}
          </span>
        </div>
        <div v-if="budgetEnergy" class="entity-row">
          <span>energy segment</span>
          <span class="mono">{{ String(budgetEnergy?.segment || '—') }}</span>
        </div>
        <div v-if="!budgetHour && !budgetDay && !budgetEnergy"
             class="brand-sub" style="color: var(--text-muted);">
          budget 数据未就绪
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { ElMessage } from 'element-plus'
import { instanceApi, systemApi } from '@/api/client'
import { fmtTs } from '@/composables/useFormat'

const route = useRoute()
const router = useRouter()
const iid = computed(() => String(route.params.iid || ''))

const meta = ref({})
const energy = ref(0)
const status = ref('idle')
const mode = ref('')
const modeLabel = ref('')
const affairStatus = ref('')
const affairGoal = ref('')
const healthReason = ref('')
const resettingAffair = ref(false)
const wakes = ref([])
const todos = ref([])
const budget = ref({})
let poller = null

const instanceName = computed(() => {
  const m = meta.value || {}
  return String(m.display_name || '').trim() || String(iid.value || '').slice(0, 8) || '—'
})
const instanceTagline = computed(() => String((meta.value || {}).tagline || ''))

const recentWakes = computed(() => (Array.isArray(wakes.value) ? wakes.value : []).slice(0, 5))
const recentTodos = computed(() => (Array.isArray(todos.value) ? todos.value : []).slice(0, 5))

const budgetHour = computed(() => (budget.value && budget.value.hour) || null)
const budgetDay = computed(() => (budget.value && budget.value.day) || null)
const budgetEnergy = computed(() => (budget.value && budget.value.energy) || null)

const statusLabel = computed(() => {
  // 与后端 5 复合状态对齐：offline / error / resting / working / idle
  // BLOCKED affair 不算异常——它是数字生命主动 wait（休息中），由后端映射成 resting
  const map = {
    offline: '离线',
    error: '异常',
    resting: '休息中',
    working: '工作中',
    idle: '待命',
    // 向后兼容老字段
    blocked: '休息中',
    low_energy: '休息中',
    live: '工作中',
    down: '离线',
  }
  return map[String(status.value)] || String(status.value || '—')
})
// 只前端真异常（心跳死/wake 卡住）才显示 reset 按钮；resting 不显示
const isAbnormal = computed(() =>
  String(status.value).toLowerCase() === 'error'
)

function safeFmtShort(iso) {
  try {
    if (!iso) return '—'
    return fmtTs(String(iso)).slice(5, 16)
  } catch {
    return '—'
  }
}

function formatTokens(n) {
  if (!n) return '0'
  if (n > 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (n > 1e3) return (n / 1e3).toFixed(1) + 'K'
  return String(n)
}
function priorityTag(p) {
  return { high: 'danger', medium: 'warning', low: 'info' }[p] || ''
}

function goSessions() {
  router.push(`/instance/${iid.value}/sessions`)
}

function wakeTriggerLabel(w) {
  // wake meta_json.trigger_type 字段 —— 从 /wakes 列表项里抽取
  const meta = w.meta_json || {}
  const type = typeof meta === 'string' ? (() => { try { return JSON.parse(meta) } catch { return {} } })() : meta
  const t = type.trigger_type || w.trigger_type || ''
  return ({
    message: '💬 消息',
    awaiting_reply: '⏰ 等回复',
    routine: '🕐 例行',
    timer: '⏲️ 定时',
    condition: '⚙️ 条件',
    initiative: '✨ 主动',
    external: '📨 外部',
    project_created: '📁 项目',
  })[String(t)] || (t ? `#${t}` : '—')
}

function wakeDuration(w) {
  const s = Number(w.started_at)
  const e = Number(w.ended_at)
  if (!s || !e || e < s) return '—'
  const sec = e - s
  if (sec < 60) return sec.toFixed(1) + 's'
  const m = Math.floor(sec / 60), r = Math.round(sec % 60)
  return `${m}m${r}s`
}

async function loadMeta() {
  try {
    const d = await systemApi.instances()
    if (d && !d.error) {
      const list = Array.isArray(d.instances) ? d.instances : []
      meta.value = (list.find(i => i && String(i.id) === String(iid.value)) || {})
      energy.value = Number(meta.value?.energy) || 0
      status.value = String(meta.value?.status || 'idle')
      healthReason.value = String(meta.value?.health_reason || '')
    }
  } catch {}
}

async function loadStatus() {
  try {
    const d = await instanceApi(iid.value).status()
    if (!d || d.error) return
    const e = (d.runtime && d.runtime.energy) ?? (d.vitals && d.vitals.energy)
    if (e != null) energy.value = Math.round(Number(e) || 0)
    const rt = d.runtime || {}
    mode.value = String(rt.mode || '')
    modeLabel.value = String(rt.mode_label || rt.mode || '')
    const aff = d.affair || {}
    affairStatus.value = String(aff.status || '')
    affairGoal.value = String(aff.goal || '')
  } catch {}
}

async function resetAffair() {
  if (resettingAffair.value) return
  resettingAffair.value = true
  try {
    // 默认只 abort stuck wakes，不动 lifecycle affairs.status（模型保留 BLOCKED 自决策）
    const d = await systemApi.resetAffair(iid.value, { abort_stuck_wakes: true })
    if (d && d.error) {
      ElMessage.error(`reset 失败：${d.error}`)
      return
    }
    ElMessage.success(`✓ abort ${d.wakes_aborted} 个卡住的 wake（不动 lifecycle RUNNING/BLOCKED）`)
    await loadStatus()
    await loadSummary()
  } finally {
    resettingAffair.value = false
  }
}

async function loadSummary() {
  try {
    const [w, t, b] = await Promise.all([
      instanceApi(iid.value).wakeSnapshot(),
      instanceApi(iid.value).todos(),
      instanceApi(iid.value).budget(),
    ])
    if (w && !w.error) wakes.value = Array.isArray(w.wakes) ? w.wakes : (Array.isArray(w.sessions) ? w.sessions : [])
    if (t && !t.error) todos.value = Array.isArray(t.todos) ? t.todos : []
    if (b && !b.error) budget.value = b || {}
  } catch {}
}

async function loadAll() {
  await Promise.all([loadMeta(), loadStatus(), loadSummary()])
}

onMounted(() => {
  loadAll()
  poller = setInterval(() => { loadStatus(); loadSummary() }, 15000)
})
onUnmounted(() => {
  if (poller) { clearInterval(poller); poller = null }
})
watch(iid, loadAll)
</script>

<style scoped>
.entity-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border-divider);
  font-size: 13px;
}
.entity-row:last-child { border: none; }
h3 { margin: 0 0 var(--space-3); font-size: 14px; }
.blocked-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  margin-bottom: var(--space-5);
  background: rgba(255, 77, 106, 0.08);
  border: 1px solid rgba(255, 77, 106, 0.4);
  border-left: 4px solid var(--neon-red);
  border-radius: var(--radius);
  box-shadow: 0 0 24px rgba(255, 77, 106, 0.12);
}
.blocked-banner strong { color: var(--neon-red); font-family: var(--font-display); }
.error-reason {
  color: var(--neon-red);
  background: rgba(255,77,106,0.06);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  border-left: 2px solid var(--neon-red);
}
</style>
