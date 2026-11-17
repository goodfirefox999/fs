<script setup lang="ts">
import { computed, ref } from 'vue'
import { buildPaipanReport } from '@core/paipan'
import type { Tendency } from '@core/zeri/types'
import type { WorkbenchState } from '../workbench'

const props = defineProps<{ state: WorkbenchState }>()

/** 元运与年星按用事年份取；默认跟随工作台起始日，可单独改。 */
const year = ref(Number(props.state.startDate.slice(0, 4)))

const TENDENCY_LABEL: Record<Tendency, string> = {
  favorable: '偏合',
  neutral: '中性',
  unfavorable: '偏忌',
  insufficient_data: '数据不足',
}

function tone(tendency: Tendency): string {
  if (tendency === 'favorable') return 'ok'
  if (tendency === 'unfavorable') return 'bad'
  if (tendency === 'insufficient_data') return 'muted'
  return 'warn'
}

const report = computed(() =>
  buildPaipanReport({
    mountShan: props.state.mountShan,
    sittingDeg: props.state.sittingDeg,
    year: year.value,
    members: props.state.subjects
      .filter((person) => person.date)
      .map((person) => ({
        relation: person.label,
        birth: { date: person.date, gender: person.gender },
      })),
    deceased: props.state.deceased
      .filter((person) => person.date)
      .map((person) => ({
        label: person.label,
        birth: { date: person.date, gender: person.gender },
      })),
  }),
)

const filledMembers = computed(() => props.state.subjects.filter((p) => p.date).length)
const filledDeceased = computed(() => props.state.deceased.filter((p) => p.date).length)
</script>

<template>
  <section class="paipan">
    <header class="bar">
      <div class="left">
        <span class="serif title">排盘</span>
        <span class="chip">{{ state.mountShan }}山 {{ state.sittingDeg }}°</span>
        <span class="chip">主命 {{ filledMembers }}</span>
        <span class="chip">仙命 {{ filledDeceased }}</span>
      </div>
      <div class="right">
        <label class="field-inline">
          <span class="muted">用事年份</span>
          <input v-model.number="year" class="input year" type="number" min="1900" max="2100" />
        </label>
        <span v-if="report.needsHumanReview" class="chip warn">含需人工复核项</span>
      </div>
    </header>

    <p class="tip">
      坐向与人员沿用「择日」页的输入，改那边这里会同步。四派并列，不做跨派合并。
    </p>

    <p v-if="report.dataGaps.length" class="alert warn">
      数据缺口：{{ report.dataGaps.join('；') }}
    </p>

    <div class="grid">
      <article v-for="school in report.schools" :key="school.school" class="card school">
        <header class="head">
          <b class="serif">{{ school.schoolLabel }}</b>
          <span class="chip" :class="tone(school.tendency)">
            {{ TENDENCY_LABEL[school.tendency] }}
          </span>
          <span v-if="school.status !== 'FULL'" class="chip warn">
            {{ school.status === 'PARTIAL' ? '数据不足' : '不可用' }}
          </span>
        </header>

        <p v-if="school.partialReason" class="muted small">{{ school.partialReason }}</p>

        <ul class="rules">
          <li v-for="rule in school.subRules" :key="rule.ruleId">
            <div class="rule-head">
              <span class="rule-name">{{ rule.name }}</span>
              <span v-if="rule.needsHumanReview" class="chip mini warn">复核</span>
            </div>
            <div class="verdict">{{ rule.verdict ?? '—' }}</div>
            <p v-for="(reason, index) in rule.reasons" :key="index" class="reason">{{ reason }}</p>
            <p class="src">{{ rule.source.title }}</p>
          </li>
        </ul>

        <p v-for="(flag, index) in school.conflictFlags" :key="index" class="conflict">
          {{ flag }}
        </p>
      </article>
    </div>

    <section class="card notes">
      <div class="card-title"><span>说明</span></div>
      <p v-for="(note, index) in report.notes" :key="index" class="note">· {{ note }}</p>
    </section>
  </section>
</template>

<style scoped>
.paipan {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  overflow: auto;
}

.bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
}

.bar .left,
.bar .right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar .right {
  margin-left: auto;
}

.title {
  font-size: 15px;
}

.field-inline {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.input.year {
  width: 84px;
  padding: 4px 6px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
}

.tip {
  margin: 0;
  color: var(--muted);
  font-size: 11px;
}

.alert {
  margin: 0;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
}

.alert.warn {
  color: var(--gold);
  background: var(--gold-soft);
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.school {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.head b {
  font-size: 14px;
}

.chip {
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  border: 1px solid var(--line);
  color: var(--ink-2);
}

.chip.ok {
  color: var(--jade);
  border-color: var(--jade);
  background: var(--jade-soft);
}

.chip.warn {
  color: var(--gold);
  border-color: var(--gold);
  background: var(--gold-soft);
}

.chip.bad {
  color: var(--clay);
  border-color: var(--clay);
  background: var(--clay-soft);
}

.chip.muted {
  color: var(--muted);
}

.chip.mini {
  padding: 0 5px;
  font-size: 10px;
}

.rules {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rules li {
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--line);
}

.rules li:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.rule-head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.rule-name {
  font-size: 12px;
  color: var(--ink-2);
}

.verdict {
  font-family: var(--serif);
  font-size: 13px;
  margin-top: 2px;
}

.reason {
  margin: 2px 0 0;
  color: var(--muted);
  font-size: 11px;
}

.src {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 10px;
}

.small {
  font-size: 11px;
}

.conflict {
  margin: 0;
  padding: 6px 8px;
  border-radius: 6px;
  background: var(--gold-soft);
  color: var(--gold);
  font-size: 11px;
}

.notes {
  margin-top: 2px;
}

.card-title {
  font-family: var(--serif);
  font-size: 14px;
  margin-bottom: 6px;
}

.note {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.65;
}
</style>
