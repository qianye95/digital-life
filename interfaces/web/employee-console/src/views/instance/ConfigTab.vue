<template>
  <div>
    <section class="page-hero">
      <h1 class="page-title">Instance Config</h1>
      <p class="page-subtitle">{{ shortId(iid, 8) }} 实例专属配置（messenger / 群聊 / 员工实例）</p>
    </section>

    <div v-if="loading" class="dev-placeholder"><span class="mono">loading…</span></div>
    <div v-else>
      <div v-for="section in instanceSections" :key="section.key" class="neon-card" style="margin-bottom: var(--space-4);">
        <h3 class="page-title" style="font-size: 16px; margin: 0 0 var(--space-3);">
          {{ section.label }}
        </h3>
        <p class="brand-sub" style="color: var(--text-muted); margin-top: -8px; margin-bottom: var(--space-4);">
          {{ section.description }}
        </p>

        <div class="config-row" v-for="field in section.fields" :key="field.key">
          <div class="field-meta">
            <div class="field-title">{{ field.label }}</div>
            <div class="brand-sub mono" style="font-size: 11px; color: var(--text-muted);">{{ field.key }} · {{ field.origin }}</div>
            <p v-if="field.description" class="brand-sub" style="margin-top: 2px; color: var(--text-secondary); font-size: 12px;">{{ field.description }}</p>
          </div>
          <div class="field-control">
            <el-switch v-if="field.type === 'boolean'" v-model="draft[field.key]" />
            <el-input-number v-else-if="field.type === 'number'" v-model="draft[field.key]" />
            <el-select v-else-if="field.type === 'array'" v-model="draft[field.key]" multiple filterable allow-create />
            <el-select v-else-if="field.options && field.options.length" v-model="draft[field.key]" filterable>
              <el-option v-for="o in field.options" :key="o" :label="o" :value="o" />
            </el-select>
            <el-input v-else v-model="draft[field.key]"
                      :type="field.secret ? 'password' : 'text'"
                      :show-password="field.secret"
                      :placeholder="field.secret && field.configured ? '留空保留当前密钥' : ''" />
          </div>
        </div>
      </div>

      <!-- 微信扫码登录（仅 wechat section 显示） -->
      <div v-if="section.key === 'wechat'" class="neon-card"
           style="margin-bottom: var(--space-4); padding: var(--space-5); border-left: 3px solid var(--neon-lime);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <strong style="font-family: var(--font-display); color: var(--neon-lime);">
              微信 ClawBot 扫码登录
            </strong>
            <p class="brand-sub" style="margin-top: 4px; color: var(--text-muted);">
              扫码后自动写入 WECHAT_BOT_TOKEN。ClawBot 仅支持私聊。
            </p>
          </div>
          <el-button type="success" :loading="wechatLoading" @click="doWechatLogin">
            {{ wechatLoading ? '等待扫码…(最多120s)' : '扫码登录' }}
          </el-button>
        </div>
      </div>

      <div style="display: flex; gap: 8px;">
        <el-button @click="load">还原</el-button>
        <el-button type="primary" :disabled="!dirty" :loading="saving" @click="save">
          保存 {{ dirty ? `(${Object.keys(changes).length})` : '' }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { instanceApi, systemApi } from '@/api/client'

const route = useRoute()
const iid = computed(() => String(route.params.iid || ''))
const loading = ref(true)
const saving = ref(false)
const wechatLoading = ref(false)
const allSections = ref([])
const draft = ref({})
const baseline = ref({})

async function doWechatLogin() {
  if (wechatLoading.value) return
  wechatLoading.value = true
  ElMessage.info('请在终端查看二维码并扫码（最多 120s）…')
  try {
    const d = await systemApi.wechatLogin(iid.value)
    if (d.error) {
      ElMessage.error(`登录失败：${d.error}`)
      return
    }
    ElMessage.success(`✓ 微信登录成功（bot_id=${d.bot_id}），WECHAT_BOT_TOKEN 已写入。重启网关后生效。`)
    await load()
  } catch (e) {
    ElMessage.error(`网络错误：${e.message || e}`)
  } finally {
    wechatLoading.value = false
  }
}

// 实例私有：身份 / 飞书凭证 / 模型 / 任务策略
// runtime（token 上限 / 精力系数）是全局共享的，在 /system/config 编辑
const INSTANCE_SECTIONS = ['employee', 'messenger', 'model', 'tasks']

const instanceSections = computed(() =>
  allSections.value.filter(s => INSTANCE_SECTIONS.includes(s.key))
)

const changes = computed(() => {
  const out = {}
  for (const section of instanceSections.value) {
    for (const f of section.fields || []) {
      if (f.readonly) continue
      const a = draft.value[f.key]
      const b = baseline.value[f.key]
      if (f.secret && !a) continue
      if (JSON.stringify(a) !== JSON.stringify(b)) out[f.key] = a
    }
  }
  return out
})

const dirty = computed(() => Object.keys(changes.value).length > 0)

async function load() {
  loading.value = true
  const d = await instanceApi(iid.value).config()
  loading.value = false
  if (d.error) return ElMessage.error(d.error)
  allSections.value = d.sections || []
  const next = {}
  for (const s of instanceSections.value) {
    for (const f of s.fields || []) {
      if (f.readonly) continue
      next[f.key] = f.secret ? '' : (f.value ?? (f.type === 'array' ? [] : ''))
    }
  }
  draft.value = next
  baseline.value = { ...next }
}

async function save() {
  saving.value = true
  try {
    const d = await instanceApi(iid.value).updateConfig(changes.value)
    if (d.error) return ElMessage.error(d.error)
    ElMessage.success('实例配置已保存 · 重启网关后生效')
    await load()
  } finally { saving.value = false }
}

onMounted(load)
</script>

<style scoped>
.config-row {
  display: grid;
  grid-template-columns: 1fr 240px;
  gap: var(--space-4);
  padding: var(--space-3) 0;
  border-top: 1px solid var(--border-divider);
  align-items: center;
}
.field-title { color: var(--text-primary); font-size: 14px; }
</style>
