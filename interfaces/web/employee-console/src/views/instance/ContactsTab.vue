<template>
  <div>
    <section class="page-hero">
      <h1 class="page-title">Social Relations</h1>
      <p class="page-subtitle">我认识的人 + bot · 联系人元数据</p>
    </section>
    <div class="neon-grid" style="grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));">
      <div v-for="c in contacts" :key="c.id" class="neon-card">
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="circle" :style="{ background: kindColor(String(c.kind)) }">{{ shortId(String(c.name || '?'), 1) }}</div>
          <div style="flex: 1;">
            <strong>{{ c.name || '(未命名 stub)' }}</strong>
            <div class="brand-sub mono" style="color: var(--text-muted); font-size: 11px;">
              {{ shortId(c.id, 8) }} · {{ c.kind }}
              <el-tag v-if="c.blocked" size="small" type="danger">blocked</el-tag>
            </div>
          </div>
          <el-tag v-for="pid in (c.platform_ids || [])" :key="safeSlice(pid.platform_id, 0, 16)" size="small" effect="plain">
            {{ pid.platform }}: {{ shortId(pid.platform_id, 10) }}…
          </el-tag>
        </div>
        <p v-if="c.notes" class="brand-sub" style="color: var(--text-secondary); margin-top: 8px;">{{ c.notes }}</p>
      </div>
      <div v-if="!contacts.length" class="dev-placeholder"><span class="mono">// 暂无联系人</span></div>
    </div>
    <p class="brand-sub" style="margin-top: 16px;">
      <RouterLink :to="`/legacy/employee/${iid}/`">编辑联系人 →</RouterLink>
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { instanceApi } from '@/api/client'
import { safeSlice, shortId } from '@/composables/useFormat'

const route = useRoute()
const iid = computed(() => String(route.params.iid || ''))
const contacts = ref([])

function kindColor(kind) {
  return { human: 'var(--neon-cyan)', bot: 'var(--neon-pink)', system: 'var(--text-muted)' }[kind] || 'var(--text-muted)'
}

async function load() {
  const d = await instanceApi(iid.value).contacts()
  if (!d.error) contacts.value = Array.isArray(d.contacts) ? d.contacts : []
}
onMounted(load)
</script>

<style scoped>
.circle {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-weight: bold; color: #050714;
  box-shadow: 0 0 12px currentColor;
}
</style>
