<template>
  <div>
    <section class="page-hero">
      <h1 class="page-title">Calendar</h1>
      <p class="page-subtitle">本周日程视图</p>
    </section>
    <div class="neon-card">
      <p class="brand-sub" style="color: var(--text-muted);">
        本视图是实例页面缩简版；查看完整日历请用
        <RouterLink :to="`/legacy/employee/${iid}/`">旧版控制台</RouterLink>。
      </p>
      <div v-for="c in calendar" :key="c.id || c.started_at" class="row">
        <span class="mono" style="color: var(--neon-cyan);">{{ fmtTs(c.started_at || c.fire_at) }}</span>
        <span>{{ c.title || c.kind || '—' }}</span>
      </div>
      <div v-if="!calendar.length" class="dev-placeholder"><span class="mono">本周无日程</span></div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { instanceApi } from '@/api/client'
import { fmtTs } from '@/composables/useFormat'

const route = useRoute()
const iid = computed(() => route.params.iid)
const calendar = ref([])

async function load() {
  const d = await instanceApi(iid.value).calendar()
  if (!d.error) calendar.value = d.events || d.items || []
}
onMounted(load)
</script>

<style scoped>
.row { display: flex; gap: 16px; padding: 8px 0; border-bottom: 1px solid var(--border-divider); }
</style>
