<script setup lang="ts">
import type { DayCell } from '../workbench'

defineProps<{
  monthLabel: string
  cells: DayCell[]
  selected: string
}>()

const emit = defineEmits<{ select: [date: string]; page: [delta: number] }>()

const STATUS_TEXT: Record<DayCell['status'], string> = {
  candidate: '候选',
  rejected: '大煞排除',
  unmatched: '宜忌不符',
  outside: '超出范围',
}
</script>

<template>
  <section class="card calendar">
    <div class="cal-head">
      <button class="btn" @click="emit('page', -1)">‹ 上月</button>
      <div class="cal-title serif">{{ monthLabel }}</div>
      <button class="btn" @click="emit('page', 1)">下月 ›</button>
    </div>
    <div class="week">
      <span v-for="name in ['日', '一', '二', '三', '四', '五', '六']" :key="name">{{ name }}</span>
    </div>
    <div class="grid">
      <button
        v-for="cell in cells"
        :key="cell.date"
        class="day"
        :class="[cell.status, { lead: cell.lead, on: cell.date === selected }]"
        :disabled="cell.status === 'outside'"
        @click="emit('select', cell.date)"
      >
        <span class="num">{{ cell.day }}</span>
        <span class="gz">{{ cell.ganZhi }}</span>
        <span class="meta">{{ cell.zhiXing }}·{{ cell.xiu }}</span>
        <span v-if="cell.luckyStar" class="star">吉星值日</span>
      </button>
    </div>
    <div class="legend">
      <span v-for="(text, key) in STATUS_TEXT" :key="key" class="chip" :class="key">
        {{ text }}
      </span>
      <span class="muted" style="margin-left: auto">点任意日期查看五派并列依据</span>
    </div>
  </section>
</template>

<style scoped>
.calendar {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cal-title {
  font-size: 17px;
  letter-spacing: 0.06em;
}

.week,
.grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
}

.week span {
  text-align: center;
  color: var(--muted);
  font-size: 11px;
}

.day {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  min-height: 66px;
  padding: 6px 7px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  text-align: left;
}

.day:disabled {
  opacity: 0.4;
  cursor: default;
}

.day .num {
  font-family: var(--serif);
  font-size: 15px;
}

.day .gz {
  font-size: 11px;
  color: var(--ink-2);
}

.day .meta {
  font-size: 10px;
  color: var(--muted);
}

.day .star {
  position: absolute;
  top: 5px;
  right: 6px;
  font-size: 9px;
  color: var(--gold);
}

.day.lead {
  background: #fffdf9;
}

.day.candidate {
  border-color: rgba(63, 107, 90, 0.45);
  background: var(--jade-soft);
}

.day.rejected {
  border-color: rgba(168, 68, 42, 0.35);
  background: var(--clay-soft);
}

.day.unmatched {
  color: var(--ink-2);
}

.day.on {
  outline: 2px solid var(--jade);
  outline-offset: 1px;
}

.legend {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 11px;
}

.chip.candidate {
  border-color: rgba(63, 107, 90, 0.45);
  color: var(--jade);
}

.chip.rejected {
  border-color: rgba(168, 68, 42, 0.4);
  color: var(--clay);
}

.chip.unmatched,
.chip.outside {
  color: var(--muted);
}
</style>
