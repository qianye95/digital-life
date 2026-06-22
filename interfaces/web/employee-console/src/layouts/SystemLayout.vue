<template>
  <div class="app-shell">
    <!-- 顶部栏 -->
    <header class="app-topbar">
      <div class="topbar-brand" @click="goSystem" style="cursor: pointer">
        <span class="brand-glyph">◇</span>
        <span>DIGITAL LIFE</span>
        <span class="brand-sub">数字生命控制台</span>
      </div>
      <nav class="topbar-nav">
        <RouterLink class="topbar-link" :class="{ active: !isInstanceScope }" to="/system">
          全局台
        </RouterLink>
        <el-divider direction="vertical" />
        <el-select
          v-model="currentIid"
          placeholder="进入实例…"
          filterable
          style="width: 200px"
          @change="enterInstance"
        >
          <el-option
            v-for="inst in instanceList"
            :key="inst.id"
            :label="inst.display_name"
            :value="inst.id"
            @click="enterInstance(inst.id)"
          >
            <span>
              <span class="status-dot" :class="statusClass(inst.status)"></span>
              {{ inst.display_name }}
              <span class="brand-sub" style="font-size: 11px">{{ inst.tagline }}</span>
            </span>
          </el-option>
        </el-select>
        <el-divider direction="vertical" />
        <el-button
          type="warning"
          plain
          size="small"
          :icon="RefreshRight"
          :loading="restarting"
          @click="confirmRestart"
          title="重启 gateway master 进程（含所有实例子进程）"
        >重启</el-button>
      </nav>
    </header>

    <div class="app-body">
      <!-- 侧栏 -->
      <aside class="app-sidebar">
        <template v-if="isSystemRoute">
          <div class="sidebar-section">
            <div class="sidebar-section-title">SYSTEM</div>
            <RouterLink
              v-for="item in systemNav"
              :key="item.path"
              :to="item.path"
              class="sidebar-link"
              active-class="active"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </RouterLink>
          </div>
        </template>
        <template v-else>
          <div class="sidebar-section">
            <div class="sidebar-section-title">返回</div>
            <RouterLink to="/system" class="sidebar-link">
              <el-icon><Back /></el-icon>
              <span>全局台</span>
            </RouterLink>
          </div>
          <div class="sidebar-section" v-if="currentInstance">
            <div class="sidebar-section-title">{{ currentInstance.display_name }}</div>
            <RouterLink
              v-for="item in instanceNav"
              :key="item.path"
              :to="`/instance/${iid}${item.path}`"
              class="sidebar-link"
              active-class="active"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </RouterLink>
          </div>
        </template>

        <div class="sidebar-section" style="margin-top: auto">
          <div class="sidebar-section-title">LEGACY</div>
          <RouterLink v-if="iid" :to="`/legacy/employee/${iid}/`" class="sidebar-link">
            <el-icon><Back /></el-icon>
            <span>旧版控制台</span>
          </RouterLink>
        </div>
      </aside>

      <!-- 主内容 + 路由出口 -->
      <main class="app-main">
        <RouterView v-slot="{ Component }">
          <transition name="route" mode="out-in">
            <component :is="Component" />
          </transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Back, Odometer, ChatDotRound, List, Calendar, Folder, MagicStick,
  Collection, User, Document, Setting, DataAnalysis, Cpu, Bell, RefreshRight,
} from '@element-plus/icons-vue'
import { systemApi } from '../api/client'

const route = useRoute()
const router = useRouter()

const instanceList = ref([])
const currentIid = ref('')
const restarting = ref(false)

const iid = computed(() => route.params.iid || '')
const isSystemRoute = computed(() => route.path.startsWith('/system'))
const isInstanceScope = computed(() => route.path.startsWith('/instance'))

const currentInstance = computed(() =>
  instanceList.value.find((i) => i.id === iid.value)
)

const systemNav = [
  { path: '/system/overview', label: '系统实况', icon: DataAnalysis },
  { path: '/system/instances', label: '实例管理', icon: Cpu },
  { path: '/system/projects', label: '项目', icon: Folder },
  { path: '/system/skills', label: '技能市场', icon: MagicStick },
  { path: '/system/events', label: '事件类型', icon: Bell },
]

const instanceNav = [
  { path: '/overview', label: '概览', icon: Odometer },
  { path: '/sessions', label: '会话', icon: ChatDotRound },
  { path: '/todos', label: '待办', icon: List },
  { path: '/calendar', label: '日程', icon: Calendar },
  { path: '/projects', label: '参与项目', icon: Folder },
  { path: '/skills', label: '能力订阅', icon: MagicStick },
  { path: '/memories', label: '记忆 / 联想', icon: Collection },
  { path: '/contacts', label: '社交关系', icon: User },
  { path: '/persona', label: '人设 / 提示词', icon: Document },
  { path: '/config', label: '实例配置', icon: Setting },
]

function goSystem() {
  router.push('/system')
}

function enterInstance(selectedIid) {
  router.push(`/instance/${selectedIid}/overview`)
}

async function confirmRestart() {
  if (restarting.value) return
  try {
    await ElMessageBox.confirm(
      '重启 gateway master 进程？所有实例子进程会被回收 + 重启。\n'
      + '需要外部 wrapper（launchd / systemd / `digital-life start`）才能自动拉起，'
      + '否则 gateway 直接退出，需手动 digital-life start。',
      '重启网关',
      { type: 'warning', confirmButtonText: '立即重启', cancelButtonText: '取消' },
    )
  } catch { return }

  restarting.value = true
  try {
    const d = await systemApi.gatewayRestart('console manual reset')
    if (d.error) {
      ElMessage.error(`重启失败：${d.error}`)
      return
    }
    ElMessage.success('重启请求已发出，gateway 数秒后退出 + 由外部 wrapper 拉起')
    // gateway 退出后 connection 会断 —— 5s 后给个 reload 提示
    setTimeout(() => {
      ElMessage.warning('若 5 秒后页面无响应，请刷新浏览器（或 digital-life start）')
    }, 5000)
  } finally {
    setTimeout(() => { restarting.value = false }, 8000)
  }
}

function statusClass(status) {
  return status || 'idle'
}

async function loadInstances() {
  const d = await systemApi.instances()
  if (!d.error) {
    instanceList.value = d.instances || []
    // 默认选第一个 active
    if (!currentIid.value && instanceList.value.length) {
      const firstActive = instanceList.value.find((i) => i.active) || instanceList.value[0]
      currentIid.value = firstActive.id
    }
  }
}

watch(iid, (v) => { if (v) currentIid.value = v })

onMounted(loadInstances)
</script>
