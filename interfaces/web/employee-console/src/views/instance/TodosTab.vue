<template>
  <div>
    <section class="page-hero">
      <div>
        <h1 class="page-title">Todos</h1>
        <p class="page-subtitle">{{ iid.slice(0,8) }} 数字生命的待办 · 按 project / type / status 分组</p>
      </div>
      <div style="display: flex; gap: 8px;">
        <el-button @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建</el-button>
      </div>
    </section>

    <!-- 顶部分类筛选 -->
    <div class="filter-row">
      <el-radio-group v-model="filterStatus" @change="filterChange">
        <el-radio-button label="all">全部 ({{ allCount }})</el-radio-button>
        <el-radio-button label="active">进行中 ({{ activeCount }})</el-radio-button>
        <el-radio-button label="done">已完成 ({{ doneCount }})</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 按 source / project 分组 -->
    <div v-if="loading" class="dev-placeholder"><span class="mono">loading…</span></div>
    <template v-else>
      <div v-for="(group, sourceKey) in groupedTodos" :key="sourceKey" class="group-section">
        <h3 class="group-title">
          {{ sourceLabel(sourceKey) }}
          <span class="brand-sub" style="font-size: 11px; color: var(--text-muted);">
            ({{ group.length }})
          </span>
        </h3>
        <div class="neon-card">
          <div v-for="t in group" :key="t.id" class="todo-row">
            <el-checkbox
              :model-value="t.status === 'done' || t.status === 'completed'"
              @change="() => toggle(t)"
            />
            <div style="flex: 1;">
              <div :class="{ 'todo-done': t.status === 'done' || t.status === 'completed' }">
                {{ t.title || '(无标题)' }}
              </div>
              <div class="brand-sub mono" style="color: var(--text-muted); font-size: 11px;">
                #{{ t.id?.slice(0, 8) }} · {{ t.priority || 'med' }}
                <span v-if="t.type"> · {{ t.type }}</span>
                <span v-if="t.deadline"> · 截止 {{ String(t.deadline).slice(0, 10) }}</span>
                <span v-if="t.assignee_kind === 'human'"> · 人类</span>
              </div>
            </div>
            <el-tag v-if="t.status" size="small" :type="statusTag(t.status)">{{ statusLabel(t.status) }}</el-tag>
            <el-button size="small" type="danger" plain @click="remove(t)">×</el-button>
          </div>
        </div>
      </div>
      <div v-if="!filteredTodos.length" class="dev-placeholder">
        <span class="mono">// 暂无待办</span>
      </div>
    </template>

    <el-dialog v-model="dlg.open" title="新建待办" width="500px">
      <el-form label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="dlg.title" placeholder="任务标题" @keyup.enter="create" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="dlg.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="dlg.priority" style="width: 100%;">
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="dlg.source" placeholder="personal / project:xxx（可空）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">取消</el-button>
        <el-button type="primary" :loading="dlg.loading" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { instanceApi } from '@/api/client'

const route = useRoute()
const iid = computed(() => String(route.params.iid || ''))
const todos = ref([])
const loading = ref(false)
const filterStatus = ref('all')

const dlg = reactive({
  open: false, loading: false, title: '', description: '',
  priority: 'medium', source: '',
})

const allCount = computed(() => todos.value.length)
const activeCount = computed(() => todos.value.filter(t => !['done', 'completed', 'cancelled'].includes(t.status)).length)
const doneCount = computed(() => todos.value.filter(t => ['done', 'completed'].includes(t.status)).length)

const filteredTodos = computed(() => {
  if (filterStatus.value === 'active') {
    return todos.value.filter(t => !['done', 'completed', 'cancelled'].includes(t.status))
  }
  if (filterStatus.value === 'done') {
    return todos.value.filter(t => ['done', 'completed'].includes(t.status))
  }
  return todos.value
})

// 按 source 分组（personal / project:xxx / null）
const groupedTodos = computed(() => {
  const groups = {}
  for (const t of filteredTodos.value) {
    const key = t.source || 'personal'
    if (!groups[key]) groups[key] = []
    groups[key].push(t)
  }
  return groups
})

function sourceLabel(source) {
  if (!source || source === 'personal') return '📋 Personal'
  if (source.startsWith('project:')) {
    const pid = source.slice('project:'.length)
    return `📁 Project ${shortId(pid, 12)}`
  }
  return `📁 ${source}`
}

function shortId(value, n) {
  try { return String(value || '').slice(0, n) } catch { return String(value) }
}

function statusLabel(s) {
  return {
    planned: '计划',
    in_progress: '执行',
    idea: '构思',
    done: '完成',
    completed: '完成',
    cancelled: '取消',
    pending: '待定',
  }[String(s)] || s
}
function statusTag(s) {
  return {
    planned: 'info',
    in_progress: 'warning',
    idea: 'info',
    done: 'success',
    completed: 'success',
    cancelled: 'danger',
    pending: '',
  }[String(s)] || ''
}

async function load() {
  loading.value = true
  try {
    const d = await instanceApi(iid.value).todos()
    if (!d.error) todos.value = d.todos || []
  } finally { loading.value = false }
}

function filterChange() {}

function openCreate() {
  dlg.open = true
  dlg.title = ''
  dlg.description = ''
  dlg.priority = 'medium'
  dlg.source = ''
}

async function create() {
  if (!dlg.title) return ElMessage.error('请填标题')
  dlg.loading = true
  try {
    const body = {
      title: dlg.title,
      description: dlg.description,
      priority: dlg.priority,
    }
    if (dlg.source) body.source = dlg.source
    const d = await instanceApi(iid.value).createTodo(body)
    if (d.error) {
      ElMessage.error(d.error)
      return
    }
    dlg.open = false
    await load()
  } finally { dlg.loading = false }
}

async function toggle(t) {
  // 勾选切换 active <-> done
  const isDone = t.status === 'done' || t.status === 'completed'
  const nextStatus = isDone ? 'planned' : 'done'
  try {
    const d = await instanceApi(iid.value).updateTodo(t.id, { status: nextStatus })
    if (d.error) {
      ElMessage.error(`切换失败：${d.error}`)
      return
    }
    // 就地更新避免重新拉取
    t.status = nextStatus
  } catch (e) {
    ElMessage.error(String(e.message || e))
  }
}

async function remove(t) {
  const d = await instanceApi(iid.value).deleteTodo(t.id)
  if (d.error) return ElMessage.error(`删除失败：${d.error}`)
  todos.value = todos.value.filter(x => x.id !== t.id)
}

onMounted(load)
</script>

<style scoped>
.filter-row { margin-bottom: var(--space-4); }
.todo-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-divider);
}
.todo-row:last-child { border: none; }
.todo-done { text-decoration: line-through; opacity: 0.5; }
.group-section { margin-bottom: var(--space-5); }
.group-title {
  font-family: var(--font-display);
  font-size: 14px;
  color: var(--neon-cyan);
  letter-spacing: 0.05em;
  margin: 0 0 var(--space-2);
}
</style>
