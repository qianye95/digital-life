<template>
  <div class="memory-advisor">
    <header class="advisor-toolbar">
      <div class="toolbar-left">
        <h2>记忆顾问</h2>
        <span class="hint">把零散的意识碎片压缩成「概念」。profile 是模型每次联想直接读到的精华，碎片只是案底。</span>
      </div>
      <div class="toolbar-right">
        <el-button text size="small" @click="loadEntities">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button text size="small" @click="loadHealth" v-loading="healthLoading">
          <el-icon><DataAnalysis /></el-icon>健康审计
        </el-button>
      </div>
    </header>

    <!-- 查找 -->
    <div class="search-row">
      <el-input
        v-model="searchQuery"
        placeholder="搜索实体名（华能蒙电 / sim_stock / ETF...）"
        size="default"
        clearable
        @input="loadEntities"
      />
      <el-checkbox v-model="filterProfileOnly">仅有 profile 的</el-checkbox>
    </div>

    <div class="advisor-grid">
      <!-- 左侧实体列表 -->
      <aside class="entity-list">
        <div v-if="loadingEntities" class="empty">加载中…</div>
        <div v-else-if="!entityRows.length" class="empty">没有匹配的实体</div>
        <button
          v-for="row in entityRows"
          :key="row.name"
          class="entity-item"
          :class="{ active: selectedEntity === row.name }"
          @click="selectEntity(row.name)"
        >
          <div class="entity-row">
            <span class="entity-name">{{ row.name }}</span>
            <el-tag v-if="row.has_profile" size="small" type="success" effect="plain">profile</el-tag>
          </div>
          <div class="entity-meta">
            <span v-if="row.kind" class="kind">{{ row.kind }}</span>
            <span class="count">{{ row.memory_count }} 条碎片</span>
          </div>
        </button>
      </aside>

      <!-- 中间：选中实体的详情 / profile 编辑 -->
      <main class="entity-detail" v-loading="loadingDetail">
        <div v-if="!selectedEntity" class="empty">
          <el-icon><Connection /></el-icon>
          <div>请从左侧选择实体，或新建</div>
        </div>
        <template v-else-if="entityDetail">
          <!-- 头部 -->
          <div class="ent-head">
            <h3>{{ entityDetail.entity }}</h3>
            <span class="kind" v-if="entityDetail.info?.type">{{ entityDetail.info.type }}</span>
            <span class="aliases" v-if="(entityDetail.info?.aliases || []).length">别名: {{ entityDetail.info.aliases.join(', ') }}</span>
          </div>

          <!-- Profile 编辑卡片 -->
          <div class="profile-card">
            <div class="card-head">
              <span class="h">📋 概念 profile</span>
              <el-button text size="small" @click="toggleEditProfile">
                {{ editProfile ? '取消' : '✎ 编辑' }}
              </el-button>
            </div>
            <div v-if="!editProfile" class="profile-view">
              <div v-if="entityDetail.info?.profile?.summary" class="profile-summary">
                {{ entityDetail.info.profile.summary }}
              </div>
              <div v-else class="empty inline">尚未写入 profile — 编辑以把碎片压缩成概念</div>
              <ul v-if="(entityDetail.info?.profile?.facts || []).length" class="profile-facts">
                <li v-for="(f, i) in entityDetail.info.profile.facts" :key="i">{{ f }}</li>
              </ul>
              <div v-if="entityDetail.info?.profile?.extra" class="profile-extra">
                <code>{{ JSON.stringify(entityDetail.info.profile.extra) }}</code>
              </div>
            </div>
            <div v-else class="profile-edit">
              <el-input v-model="profileForm.kind" placeholder="类型 (stock/project/person/thesis/strategy/decision)" size="small" />
              <el-input
                v-model="profileForm.summary"
                type="textarea"
                :rows="3"
                placeholder="1-2 句『这个实体意味着什么』"
              />
              <el-input
                v-model="profileForm.factsText"
                type="textarea"
                :rows="6"
                placeholder="事实列表（每行一条）"
              />
              <el-input
                v-model="profileForm.aliasesText"
                size="small"
                placeholder="别名（逗号分隔），如 600863, 华能"
              />
              <el-input
                v-model="profileForm.extraText"
                type="textarea"
                :rows="3"
                placeholder='extra JSON，如 {"stop_loss": "-12%", "industry": "电力"}'
              />
              <div class="profile-actions">
                <el-button size="small" type="primary" @click="saveProfile" :loading="saving">保存</el-button>
                <el-button v-if="(entityDetail.info?.memories || []).length > 5" size="small" @click="pruneFragments">
                  ✂️ 清理碎片（保留 5 条）
                </el-button>
              </div>
            </div>
          </div>

          <!-- 碎片段 -->
          <div class="fragments">
            <div class="h">📜 碎片（{{ (entityDetail.info?.memories || []).length }} 条）</div>
            <div v-if="!(entityDetail.info?.memories || []).length" class="empty inline">无</div>
            <div
              v-for="(m, i) in (entityDetail.info?.memories || []).slice(-30)"
              :key="i"
              class="frag-item"
            >
              <div class="frag-meta">
                <el-tag size="small" effect="plain" :type="fragTypeTag(m.memory_type)">{{ m.memory_type }}</el-tag>
                <span class="ts">{{ m.timestamp }}</span>
                <span v-if="m.verification_count" class="verify">✓{{ m.verification_count }}</span>
              </div>
              <div class="frag-snippet">{{ m.snippet }}</div>
            </div>
            <div v-if="(entityDetail.info?.memories || []).length > 30" class="frag-more">
              还有 {{ (entityDetail.info?.memories || []).length - 30 }} 条未显示（清理碎片后会精简）
            </div>
          </div>

          <!-- 合并建议区 -->
          <div v-if="mergeSuggestionsForSelected.length" class="merge-card">
            <div class="h">🔗 检测到这些实体可能跟 {{ selectedEntity }} 是别名（同一段碎片）：</div>
            <ul>
              <li v-for="(m, i) in mergeSuggestionsForSelected" :key="i">
                <code>{{ m.primary }}</code> ↔ <code>{{ m.alias }}</code>
                — 共享 {{ m.shared_memory_count }} 条
                <el-button v-if="m.primary === selectedEntity || m.alias === selectedEntity" size="small" @click="doMerge(m)">
                  合并
                </el-button>
              </li>
            </ul>
          </div>
        </template>
        <div v-else class="empty">未找到 {{ selectedEntity }}</div>
      </main>

      <!-- 右侧：审计报告 -->
      <aside class="audit-panel" v-loading="healthLoading">
        <div class="h">🩻 索引健康</div>
        <div v-if="!health" class="empty inline">点 "健康审计"</div>
        <div v-else>
          <div class="health-stat">实体总数：{{ health.total_entities }}</div>
          <div class="health-stat">已有 profile：{{ health.with_profile.length }}</div>
          <div class="health-stat">碎片多但无 profile：{{ health.missing_profile_high_value.length }}</div>
          <div class="health-stat">孤立别名：{{ health.missing_aliases.length }}</div>
          <div class="health-stat">无 type：{{ health.missing_type.length }}</div>
          <div class="health-stat">建议合并：{{ health.suggested_merges.length }}</div>

          <div v-if="health.missing_profile_high_value.length" class="audit-section">
            <div class="h-sm">高碎片实体（建议建 profile）</div>
            <ul class="rec-list">
              <li v-for="e in health.missing_profile_high_value" :key="e.name">
                <a href="#" @click.prevent="selectEntity(e.name)">{{ e.name }}</a> ({{ e.fragment_count }} 碎片)
              </li>
            </ul>
          </div>

          <div v-if="health.suggested_merges.length" class="audit-section">
            <div class="h-sm">建议合并的别名对</div>
            <ul class="rec-list">
              <li v-for="(m, i) in health.suggested_merges.slice(0, 10)" :key="i">
                {{ m.primary }} ← {{ m.alias }}（{{ m.shared_memory_count }}）
              </li>
            </ul>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh, DataAnalysis, Connection } from '@element-plus/icons-vue'

const props = defineProps({
  apiBase: { type: String, required: true },
})

const entityRows = ref([])
const loadingEntities = ref(false)
const searchQuery = ref('')
const filterProfileOnly = ref(false)

const selectedEntity = ref(null)
const entityDetail = ref(null)
const loadingDetail = ref(false)

const editProfile = ref(false)
const profileForm = reactive({
  summary: '',
  factsText: '',
  aliasesText: '',
  kind: '',
  extraText: '',
})
const saving = ref(false)

const health = ref(null)
const healthLoading = ref(false)

onMounted(() => {
  loadEntities()
})

async function loadEntities() {
  loadingEntities.value = true
  try {
    const q = new URLSearchParams()
    if (searchQuery.value) q.set('q', searchQuery.value)
    if (filterProfileOnly.value) q.set('need_profile', 'true')
    const r = await fetch(`${props.apiBase}/entities?${q.toString()}`)
    const d = await r.json()
    entityRows.value = d.entities || []
  } catch (e) {
    entityRows.value = []
  } finally {
    loadingEntities.value = false
  }
}

async function selectEntity(name) {
  selectedEntity.value = name
  await fetchEntityDetail()
}

async function fetchEntityDetail() {
  if (!selectedEntity.value) return
  loadingDetail.value = true
  editProfile.value = false
  try {
    const r = await fetch(`${props.apiBase}/entities/${encodeURIComponent(selectedEntity.value)}`)
    if (r.status === 404) {
      entityDetail.value = null
      return
    }
    const d = await r.json()
    entityDetail.value = d
    // sync profile form
    const prof = d?.info?.profile || {}
    profileForm.summary = prof.summary || ''
    profileForm.factsText = (prof.facts || []).join('\n')
    profileForm.aliasesText = (d?.info?.aliases || []).join(', ')
    profileForm.kind = d?.info?.type || ''
    profileForm.extraText = prof.extra ? JSON.stringify(prof.extra, null, 2) : ''
  } catch (e) {
    entityDetail.value = null
  } finally {
    loadingDetail.value = false
  }
}

function toggleEditProfile() {
  editProfile.value = !editProfile.value
}

async function saveProfile() {
  if (!selectedEntity.value) return
  saving.value = true
  try {
    const body = {
      summary: profileForm.summary,
      facts: profileForm.factsText.split('\n').map(s => s.trim()).filter(Boolean),
      aliases: profileForm.aliasesText.split(',').map(s => s.trim()).filter(Boolean),
      kind: profileForm.kind || undefined,
      extra: profileForm.extraText || '{}',
    }
    const r = await fetch(`${props.apiBase}/entities/${encodeURIComponent(selectedEntity.value)}/profile`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const d = await r.json()
    if (d.ok) {
      editProfile.value = false
      await fetchEntityDetail()
      await loadEntities()
    } else {
      alert(d.error || '保存失败')
    }
  } catch (e) {
    alert(`保存失败: ${e.message}`)
  } finally {
    saving.value = false
  }
}

async function pruneFragments() {
  if (!selectedEntity.value) return
  try {
    const r = await fetch(`${props.apiBase}/entities/${encodeURIComponent(selectedEntity.value)}/prune`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keep: 5 }),
    })
    const d = await r.json()
    if (d.ok !== undefined) {
      alert(`清理：保留 ${d.kept} 条，删除 ${d.removed} 条`)
      await fetchEntityDetail()
      await loadEntities()
    } else {
      alert(d.error || '清理失败')
    }
  } catch (e) {
    alert(`清理失败: ${e.message}`)
  }
}

async function loadHealth() {
  healthLoading.value = true
  try {
    const r = await fetch(`${props.apiBase}/entity-health`)
    health.value = await r.json()
  } catch (e) {
    health.value = null
  } finally {
    healthLoading.value = false
  }
}

async function doMerge(m) {
  if (!confirm(`确认把 "${m.alias}" 合并进 "${m.primary}"？合并后别名移除，碎片全部归属 primary。`)) return
  try {
    const r = await fetch(`${props.apiBase}/entities/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ primary: m.primary, alias: m.alias }),
    })
    const d = await r.json()
    if (d.ok || d.merged) {
      alert('合并成功')
      await loadHealth()
      await loadEntities()
      if (selectedEntity.value === m.alias) {
        await selectEntity(m.primary)
      } else {
        await fetchEntityDetail()
      }
    } else {
      alert(d.reason || '合并失败')
    }
  } catch (e) {
    alert(`合并失败: ${e.message}`)
  }
}

const mergeSuggestionsForSelected = computed(() => {
  if (!health.value || !selectedEntity.value) return []
  return (health.value.suggested_merges || []).filter(m =>
    m.primary === selectedEntity.value || m.alias === selectedEntity.value,
  )
})

function fragTypeTag(t) {
  if (t === 'rule') return 'danger'
  if (t === 'lesson') return 'warning'
  if (t === 'consciousness') return 'info'
  return ''
}
</script>

<style scoped>
.memory-advisor {
  height: 100%;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}

.advisor-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.toolbar-left h2 {
  margin: 0;
  font-size: 16px;
}
.toolbar-left .hint {
  font-size: 11px;
  color: #909399;
}
.toolbar-right {
  display: inline-flex;
  gap: 4px;
}

.search-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.advisor-grid {
  flex: 1;
  display: grid;
  grid-template-columns: 240px 1fr 240px;
  gap: 12px;
  min-height: 0;
}

.entity-list {
  overflow-y: auto;
  background: #fafbfc;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  padding: 8px;
}
.entity-item {
  display: block;
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 4px;
  cursor: pointer;
  font: inherit;
  color: inherit;
}
.entity-item:hover { background: #f5f7fa; }
.entity-item.active { background: rgba(64, 158, 255, 0.08); border-left: 3px solid #409eff; }
.entity-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.entity-name { font-weight: 500; font-size: 13px; }
.entity-meta {
  font-size: 11px;
  color: #909399;
  display: flex;
  gap: 8px;
}
.entity-meta .kind {
  background: rgba(64, 158, 255, 0.1);
  padding: 1px 5px;
  border-radius: 3px;
}

.entity-detail {
  overflow-y: auto;
}
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #c0c4cc;
  padding: 36px;
  font-size: 13px;
}
.empty.inline { padding: 8px; font-size: 12px; }

.ent-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 8px;
}
.ent-head h3 { margin: 0; font-size: 16px; font-weight: 600; }
.ent-head .kind {
  font-size: 11px;
  background: rgba(64, 158, 255, 0.1);
  padding: 1px 6px;
  border-radius: 3px;
  color: #2e80d8;
}
.ent-head .aliases { font-size: 11px; color: #606266; }

.profile-card {
  background: linear-gradient(180deg, #f6fafe, #fff);
  border: 1px solid #d6e8f9;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.card-head .h {
  font-weight: 500;
  font-size: 13px;
  color: #2e80d8;
}
.profile-summary {
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
  background: #fff;
  padding: 8px 10px;
  border-radius: 4px;
  margin-bottom: 6px;
}
.profile-facts {
  margin: 4px 0 0;
  padding-left: 20px;
  font-size: 12px;
  color: #606266;
  line-height: 1.6;
}
.profile-extra {
  margin-top: 4px;
  font-size: 11px;
  font-family: 'Menlo', monospace;
}
.profile-edit {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.profile-actions {
  margin-top: 4px;
  display: inline-flex;
  gap: 8px;
}

.fragments .h, .audit-panel .h {
  font-weight: 500;
  font-size: 12px;
  color: #909399;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}
.frag-item {
  border-left: 2px solid #ebeef5;
  padding: 4px 8px;
  margin: 4px 0;
  font-size: 11px;
  background: #fafbfc;
  border-radius: 0 4px 4px 0;
}
.frag-meta {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 10px;
  color: #909399;
}
.frag-snippet {
  white-space: pre-wrap;
  word-break: break-word;
  color: #606266;
  line-height: 1.5;
  margin-top: 2px;
}
.frag-more {
  font-size: 10px;
  color: #c0c4cc;
  text-align: center;
  margin-top: 8px;
}

.merge-card {
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 6px;
  padding: 8px 10px;
  margin-top: 12px;
  font-size: 12px;
}
.merge-card ul {
  margin: 4px 0 0;
  padding-left: 16px;
}
.merge-card li {
  font-family: 'Menlo', monospace;
  font-size: 11px;
  margin: 2px 0;
}

.audit-panel {
  background: #fafbfc;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px;
  overflow-y: auto;
  font-size: 12px;
}
.health-stat {
  font-size: 11px;
  color: #606266;
  padding: 2px 0;
  border-bottom: 1px dotted #ebeef5;
}
.audit-section {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid #ebeef5;
}
.h-sm {
  font-size: 11px;
  color: #909399;
  margin-bottom: 4px;
}
.rec-list {
  margin: 0;
  padding-left: 16px;
  font-size: 11px;
}
.rec-list a { color: #409eff; text-decoration: none; }
.rec-list a:hover { text-decoration: underline; }
</style>
