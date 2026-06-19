<template>
  <div>
    <section class="page-hero">
      <div>
        <h1 class="page-title">System Overview</h1>
        <p class="page-subtitle">{{ subtitle || '所有实例运行状态聚合 · 数字生命的全貌' }}</p>
      </div>
      <div class="brand-sub mono">{{ nowTs }}</div>
    </section>

    <!-- 顶部 stats -->
    <div class="neon-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: var(--space-5);">
      <div class="neon-card" v-for="stat in stats" :key="stat.label">
        <div class="brand-sub">{{ stat.label }}</div>
        <div style="font-family: var(--font-display); font-size: 28px; color: var(--neon-cyan); margin-top: 4px;">
          {{ stat.value }}
        </div>
        <div class="brand-sub" style="margin-top: 4px; color: var(--text-muted);">{{ stat.hint }}</div>
      </div>
    </div>

    <!-- 双栏：实时实例 + 项目列表 -->
    <div class="neon-grid" style="grid-template-columns: 1.4fr 1fr; gap: var(--space-5);">
      <div>
        <h2 class="page-title" style="font-size: 18px; margin-bottom: var(--space-3);">Instances · 运行中</h2>
        <div class="neon-grid" style="grid-template-columns: repeat(2, 1fr);">
          <div
            v-for="inst in instances"
            :key="inst.id"
            class="neon-card accent-override instance-card"
            :style="{ '--instance-accent': inst.accent_color || '#00f0ff' }"
            @click="enter(inst.id)"
          >
            <div class="instance-header">
              <span class="avatar-glyph" :style="{ background: inst.accent_color || '#00f0ff' }">
                {{ (inst.display_name || '?').slice(0, 1).toUpperCase() }}
              </span>
              <div>
                <div class="display-name" :style="{ color: inst.accent_color || 'var(--neon-cyan)' }">
                  {{ inst.display_name }}
                </div>
                <div class="brand-sub">{{ inst.tagline || '—' }}</div>
              </div>
              <span class="status-dot" :class="inst.status"></span>
            </div>

            <div class="energy-bar">
              <div class="energy-fill" :style="{ width: inst.energy + '%', background: inst.accent_color || 'var(--neon-cyan)' }"></div>
              <span class="energy-label">{{ Math.round(inst.energy) }}% energy</span>
            </div>

            <div class="mono id-line">{{ safeSlice(inst.id, 0, 8) }}…</div>
          </div>
        </div>
      </div>

      <div>
        <h2 class="page-title" style="font-size: 18px; margin-bottom: var(--space-3);">Active Projects</h2>
        <div
          v-for="p in projects"
          :key="p.id"
          class="neon-card project-row"
        >
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong>{{ p.name }}</strong>
            <el-tag size="small" effect="plain">{{ p.status }}</el-tag>
          </div>
          <div class="brand-sub" style="margin-top: 4px;">{{ p.description || '—' }}</div>
          <div class="tag-row" style="margin-top: 8px;">
            <el-tag v-for="pos in p.positions" :key="pos.id" size="small" type="info" effect="plain">
              {{ pos.name }} ({{ pos.assignees.length }})
            </el-tag>
          </div>
        </div>
        <div v-if="!projects.length" class="dev-placeholder">
          <span class="mono">No projects</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { systemApi } from '@/api/client'
import { fmtTs } from '@/composables/useFormat'
// template 用 safeSlice 通过 app.config.globalProperties 注入；script 内用 fmtTs import

const router = useRouter()
const subtitle = computed(() => '')

const instances = ref([])
const projects = ref([])
const refreshTimer = ref(null)
const now = ref(Date.now())
const nowTs = computed(() => fmtTs(new Date(now.value).toISOString()))

const stats = computed(() => [
  { label: '总实例数', value: instances.value.length, hint: 'registered' },
  { label: '运行中', value: instances.value.filter(i => i.process_state === 'online').length, hint: 'process online' },
  { label: '健康实例', value: instances.value.filter(i => i.health_state === 'ok' && i.process_state === 'online').length, hint: 'health ok' },
  { label: '异常实例', value: instances.value.filter(i => i.health_state === 'error').length, hint: 'health error' },
  { label: '活跃项目', value: projects.value.length, hint: 'ongoing' },
])

function enter(iid) {
  router.push(`/instance/${iid}/overview`)
}

async function load() {
  const d = await systemApi.overview()
  if (d.error) return
  instances.value = d.instances || []
  projects.value = d.projects || []
}

onMounted(() => {
  load()
  refreshTimer.value = setInterval(load, 10000)
  setInterval(() => { now.value = Date.now() }, 30000)
})

onUnmounted(() => clearInterval(refreshTimer.value))
</script>

<style scoped>
.instance-card {
  cursor: pointer;
  transition: all 200ms;
}
.instance-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-glow-cyan);
}

.instance-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: var(--space-3);
}
.avatar-glyph {
  width: 36px;
  height: 36px;
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-weight: 700;
  color: #050714;
  font-size: 18px;
  box-shadow: 0 0 12px currentColor;
}
.display-name {
  font-family: var(--font-display);
  letter-spacing: 0.06em;
  font-weight: 700;
}

.energy-bar {
  position: relative;
  height: 6px;
  background: var(--bg-elevated);
  border-radius: 3px;
  margin: var(--space-3) 0;
  overflow: hidden;
}
.energy-fill {
  height: 100%;
  border-radius: 3px;
  box-shadow: 0 0 8px currentColor;
  transition: width 800ms ease;
}
.energy-label {
  position: absolute;
  right: 0;
  top: -16px;
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.id-line {
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.7;
}

.project-row {
  margin-bottom: var(--space-3);
  padding: var(--space-4);
}
</style>
