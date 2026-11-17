<script setup lang="ts">
import { computed } from 'vue'
import type { DayEvaluation } from '@core/zeri/evaluate'
import { STANCE_LABELS, guidanceFor, partitionDasha } from '@core/zeri/dasha'
import { SCHOOL_LABELS, type DashaHit, type SchoolResult } from '@core/zeri/types'
import { THREE_LUCKY_STARS, dongGongStarOf } from '@core/zeri/tables/donggong'
import { douShouSummary } from '@core/zeri/packs/doushou'

const props = defineProps<{ evaluation: DayEvaluation | null }>()

/** 占山与日课相犯是两类问题，列表里显式标出来，不让相犯条冒充山家排除。 */
const FAMILY_LABEL: Record<DashaHit['family'], string> = {
  SAN_SHA_MOUNTAIN: '山家三煞',
  SAN_SHA_COURSE: '日课相犯',
  GENERAL: '前置大煞',
}

/**
 * 分区只算一次：卡片与摘要计数同源于 partitionDasha，
 * 新增 family 或 stance 时不会出现「摘要 3 条、卡片 2 条」。
 */
const groups = computed(() =>
  partitionDasha(props.evaluation?.dasha ?? { hits: [], warned: [] }),
)
const blocks = computed(() => groups.value.blocks)
const divergeRows = computed(() => groups.value.diverge)
const folkRows = computed(() => groups.value.folk)

/** 说明文案随用事口径变化，与排除统计走同一个函数，避免两处各写一套说法。 */
const dashaScope = computed(() => ({
  category: props.evaluation?.context.category ?? ('YANG_RUZHAI' as const),
  includesConstruction: props.evaluation?.context.includesConstruction ?? false,
}))

const TENDENCY: Record<string, string> = {
  favorable: '宜',
  neutral: '平',
  unfavorable: '忌',
  insufficient_data: '据不足',
}

const CONSUSUS: Record<string, string> = {
  favorable: '多数流派并宜',
  mixed: '流派分歧',
  unfavorable: '多数流派并忌',
  rejected: '已被大煞前置排除',
  insufficient: '可判依据不足',
}

const facts = computed(() => props.evaluation?.facts ?? null)
const dasha = computed(() => props.evaluation?.dasha ?? null)
const schools = computed(() => props.evaluation?.schools ?? [])
const doushou = computed(() => props.evaluation?.doushou ?? null)
const conflicts = computed(() => props.evaluation?.arbitration.conflicts ?? [])
const luckyStar = computed(() => {
  if (!facts.value) return ''
  const star = dongGongStarOf(facts.value.monthBranch, facts.value.pillars.day.ganZhi)
  return THREE_LUCKY_STARS.includes(star) ? star : ''
})

/**
 * 四柱列表在 script 里成型，模板只负责渲染。
 *
 * 原来模板里写的是 `(entry[1] as never as { ganZhi: string })?.ganZhi` —— 双重断言绕类型，
 * 且 vue-tsc 解析不了 `as { ... }` 这种对象类型字面量，整个 SFC 直接语法报错。
 */
const pillarList = computed(() => {
  const p = facts.value?.pillars
  if (!p) return []
  return [
    { label: '年', ganZhi: p.year.ganZhi, nayin: p.year.nayin },
    { label: '月', ganZhi: p.month.ganZhi, nayin: p.month.nayin },
    { label: '日', ganZhi: p.day.ganZhi, nayin: p.day.nayin },
    { label: '时', ganZhi: p.hour?.ganZhi ?? '—', nayin: p.hour?.nayin ?? '未定时支' },
  ]
})

/** 卡片顺序由代码决定，用户应先看到全貌；计数与卡片同源于 groups。 */
const sectionCounts = computed(() => {
  const { blocks: b, diverge, folk } = groups.value
  if (!b.length && !diverge.length && !folk.length) return null
  return { hits: b.length, diverge: diverge.length, folk: folk.length }
})

function sign(value: number): string {
  return value > 0 ? `+${value}` : `${value}`
}

function tone(school: SchoolResult): string {
  if (school.status !== 'FULL') return 'warn'
  if (school.tendency === 'favorable') return 'candidate'
  if (school.tendency === 'unfavorable') return 'bad'
  return ''
}
</script>

<template>
  <aside class="panel scroll">
    <div v-if="!evaluation" class="card empty">选择左侧日历中的日期查看依据</div>

    <template v-else>
      <section class="card">
        <div class="head">
          <div>
            <div class="date serif">{{ evaluation.date }}</div>
            <div class="muted">{{ facts!.weekDay }} · {{ facts!.lunarText }}</div>
          </div>
          <div class="chips">
            <span class="chip" :class="dasha!.rejected ? 'bad' : 'candidate'">
              {{ CONSUSUS[evaluation.arbitration.consensus] }}
            </span>
            <span v-if="luckyStar" class="chip warn">{{ luckyStar }}值日</span>
            <span v-if="evaluation.arbitration.consensusFavorable" class="chip candidate">
              三派以上并宜
            </span>
          </div>
        </div>
        <div class="pillars">
          <div v-for="entry in pillarList" :key="entry.label" class="pillar">
            <em>{{ entry.label }}</em>
            <b class="serif">{{ entry.ganZhi }}</b>
            <i>{{ entry.nayin }}</i>
          </div>
        </div>
        <div class="rows">
          <span class="chip">建除 {{ facts!.zhiXing }}</span>
          <span class="chip">值神 {{ facts!.tianShen }}（{{ facts!.tianShenType }}{{ facts!.tianShenLuck }}）</span>
          <span class="chip">宿 {{ facts!.xiu }}（{{ facts!.xiuLuck }}）</span>
          <span class="chip">{{ facts!.solarTerm ? `节气 ${facts!.solarTerm}` : '非交接日' }}</span>
          <span class="chip">冲 {{ facts!.chongShengXiao }}</span>
          <span class="chip">煞 {{ facts!.sha }}</span>
        </div>
        <p v-if="sectionCounts" class="src">
          本结果包含 {{ sectionCounts.hits }} 条大煞前置排除、{{ sectionCounts.diverge }} 条口径分歧提示、{{ sectionCounts.folk }} 条民俗口径提示。
        </p>
      </section>

      <section v-if="blocks.length" class="card block">
        <div class="card-title"><span>大煞前置排除（{{ blocks.length }}）</span><em>吉星不可解</em></div>
        <div v-for="hit in blocks" :key="hit.ruleId" class="hit">
          <div class="hit-head">
            <b>{{ hit.name }}</b>
            <span class="chip tiny">{{ FAMILY_LABEL[hit.family] }}</span>
            <span v-if="hit.shaGrade" class="chip bad tiny">{{ hit.shaGrade }}</span>
            <span v-if="hit.stance" class="chip warn tiny">{{ STANCE_LABELS[hit.stance] }}</span>
            <span class="id">{{ hit.ruleId }}</span>
            <span v-if="!hit.negotiable" class="chip bad tiny">不可放宽</span>
            <span v-else class="chip warn tiny">可改设置或人工复核</span>
            <span v-if="hit.needsHumanReview" class="chip tiny">出处待核对</span>
          </div>
          <p>{{ hit.reason }}</p>
          <p class="guidance">{{ guidanceFor(hit.ruleId, dashaScope) }}</p>
          <p class="src">出处：{{ hit.source.title }}{{ hit.source.locus ? ` · ${hit.source.locus}` : '' }}</p>
        </div>
        <p v-if="luckyStar" class="override">
          本日为{{ luckyStar }}值日，按《金符经》系统属三吉星，仍被上述大煞排除——
          原文即「能解诸凶，唯不能解金神七煞」，故吉星不改写前置结论。
        </p>
      </section>

      <section v-if="divergeRows.length" class="card diverge">
        <div class="card-title"><span>口径分歧（按层级或流派立场降为提示）</span><em>非已权衡的轻微风险</em></div>
        <div v-for="warn in divergeRows" :key="warn.ruleId" class="hit">
          <div class="hit-head">
            <b>{{ warn.name }}</b>
            <span class="chip tiny">{{ FAMILY_LABEL[warn.family] }}</span>
            <span class="id">{{ warn.ruleId }}</span>
          </div>
          <p>{{ warn.reason }}</p>
          <p class="guidance">{{ guidanceFor(warn.ruleId, dashaScope) }}</p>
          <p class="src">出处：{{ warn.source.title }}</p>
        </div>
      </section>

      <section v-if="folkRows.length" class="card folk">
        <div class="card-title">
          <span>民俗口径提示</span>
          <em>本区条目按出处立场分档，严重度并不等同</em>
        </div>
        <div v-for="warn in folkRows" :key="warn.ruleId" class="hit">
          <div class="hit-head">
            <b>{{ warn.name }}</b>
            <span v-if="warn.stance" class="chip warn tiny">{{ STANCE_LABELS[warn.stance] }}</span>
            <span class="id">{{ warn.ruleId }}</span>
            <span v-if="warn.needsHumanReview" class="chip tiny">出处待核对</span>
          </div>
          <p>{{ warn.reason }}</p>
          <p class="guidance">{{ guidanceFor(warn.ruleId, dashaScope) }}</p>
          <p class="src">出处：{{ warn.source.title }}{{ warn.source.lineageNote ? ` · ${warn.source.lineageNote}` : '' }}</p>
        </div>
      </section>

      <section class="card">
        <div class="card-title">
          <span>五派并列</span>
          <em class="muted">仲裁层不合并原始结论</em>
        </div>
        <div v-if="!schools.length" class="empty small">
          该日已被前置层排除，按规格不进入流派评分。上方保留排除依据与吉星标记。
        </div>
        <div v-for="school in schools" :key="school.school" class="school">
          <div class="school-head">
            <b class="serif">{{ SCHOOL_LABELS[school.school] }}</b>
            <span class="chip" :class="tone(school)">
              {{ TENDENCY[school.tendency] }} {{ sign(school.scoreDelta) }}
            </span>
            <span v-if="school.status !== 'FULL'" class="chip warn">{{ school.status }}</span>
          </div>
          <p v-if="school.partialReason" class="src">部分计算：{{ school.partialReason }}</p>
          <div v-for="rule in school.subRules" :key="rule.ruleId" class="rule">
            <div class="rule-head">
              <b>{{ rule.name }}</b>
              <span v-if="rule.verdict" class="verdict">{{ rule.verdict }}</span>
              <span v-if="rule.scoreDelta" class="chip" :class="rule.scoreDelta > 0 ? 'candidate' : 'bad'">
                {{ sign(rule.scoreDelta) }}
              </span>
              <span v-if="rule.needsHumanReview" class="chip warn tiny">待人工复核</span>
              <span class="id">{{ rule.ruleId }}</span>
            </div>
            <p v-for="(reason, index) in rule.reasons" :key="index" class="reason">· {{ reason }}</p>
            <p v-if="rule.dataGap" class="gap">数据缺口：{{ rule.dataGap }}</p>
            <p class="src">
              出处：{{ rule.source.title }}{{ rule.source.locus ? `（${rule.source.locus}）` : '' }}
              · 校验状态 {{ rule.verification }}
            </p>
            <p v-if="rule.source.lineageNote" class="src">流派提示：{{ rule.source.lineageNote }}</p>
          </div>
        </div>
      </section>

      <section v-if="doushou" class="card">
        <div class="card-title">
          <span>斗首（参考层）</span>
          <em class="muted">不参与五派仲裁</em>
        </div>
        <p class="src">{{ douShouSummary(doushou) }}</p>
        <table class="doushou">
          <thead>
            <tr><th>柱</th><th>天干</th><th>化气</th><th>生克</th><th>星</th><th>番化</th><th>月令</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in doushou.stems" :key="item.position">
              <td>{{ item.position }}</td>
              <td class="serif">{{ item.gan || '—' }}</td>
              <td>{{ item.huaqi ?? '—' }}</td>
              <td>{{ item.relation ?? '—' }}</td>
              <td>{{ item.star ?? '—' }}<span v-if="item.alias && item.alias !== item.star" class="muted">（{{ item.alias }}）</span></td>
              <td>{{ item.fanhua ?? '—' }}</td>
              <td>
                {{ item.stage ?? '—' }}
                <span v-if="item.dewei" class="chip candidate tiny">得位</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="src">
          山家斗首{{ doushou.shanElement ?? '—' }}，月令{{ doushou.shanStage ?? '—' }}
          <span v-if="doushou.shanDewei" class="chip candidate tiny">山家得位</span>
        </p>
        <p v-for="(note, index) in doushou.reviewNotes" :key="index" class="src">· {{ note }}</p>
      </section>

      <section class="card">
        <div class="card-title"><span>冲突决议表</span><em class="muted">只标记，不裁决</em></div>
        <div v-if="!conflicts.length" class="empty small">本日五派之间没有相反的判定。</div>
        <div v-for="(conflict, index) in conflicts" :key="index" class="conflict">
          <div class="hit-head">
            <b>{{ conflict.schools.map((id) => SCHOOL_LABELS[id]).join(' × ') }}</b>
          </div>
          <p>{{ conflict.issue }}</p>
          <p class="src">涉及规则：{{ conflict.ruleIds.join('、') || '未列出计分项' }}</p>
        </div>
        <div class="weights">
          <span class="muted">用事权重：</span>
          <span v-for="weight in evaluation.arbitration.weights" :key="weight.school" class="chip tiny">
            {{ SCHOOL_LABELS[weight.school] }} × {{ weight.weight }}
          </span>
        </div>
      </section>

      <section class="card">
        <div class="card-title"><span>通书与神煞明细</span></div>
        <div class="rows">
          <span class="chip">吉神宜趋 {{ facts!.jiShen.join('、') || '未注' }}</span>
          <span class="chip">凶煞宜忌 {{ facts!.xiongSha.join('、') || '未注' }}</span>
        </div>
        <p class="src">宜：{{ facts!.almanacYi.join('、') }}</p>
        <p class="src">忌：{{ facts!.almanacJi.join('、') }}</p>
        <p class="src">彭祖：{{ facts!.pengZu.join('；') }}</p>
        <p class="src">
          方位：喜{{ facts!.positions.xi }} 财{{ facts!.positions.cai }} 福{{ facts!.positions.fu }}
          阳贵{{ facts!.positions.yangGui }} 阴贵{{ facts!.positions.yinGui }} 胎{{ facts!.positions.tai }}
        </p>
        <p class="src">吉时：{{ facts!.luckyHours.join('、') || '未注' }}</p>
        <p class="note">
          民俗日程参考，不替代施工、地质、消防、审批与安全评估；涉及立向与安葬事项请用实体罗盘与专业人士现场复核。
        </p>
      </section>
    </template>
  </aside>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 460px;
  flex-shrink: 0;
  max-height: 100%;
}

.empty {
  color: var(--muted);
  text-align: center;
  padding: 40px 12px;
}

.empty.small {
  padding: 12px;
  text-align: left;
  font-size: 12px;
}

.head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}

.date {
  font-size: 20px;
}

.chips {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-end;
}

.pillars {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin: 12px 0 10px;
}

.pillar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  padding: 6px 2px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-2);
}

.pillar em {
  font-style: normal;
  color: var(--muted);
  font-size: 11px;
}

.pillar b {
  font-size: 16px;
  letter-spacing: 0.06em;
}

.pillar i {
  font-style: normal;
  font-size: 10px;
  color: var(--ink-2);
}

.rows {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.card-title {
  font-family: var(--serif);
  font-size: 14px;
}

.card-title em {
  font-style: normal;
  font-size: 11px;
  color: var(--muted);
  font-family: var(--sans);
}

.hit,
.rule,
.conflict {
  padding: 8px 0;
  border-top: 1px dashed var(--line);
}

.hit-head,
.rule-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.hit p,
.rule p,
.conflict p {
  margin: 4px 0 0;
}

.id {
  font-family: ui-monospace, monospace;
  font-size: 10px;
  color: var(--muted);
}

.verdict {
  font-family: var(--serif);
  color: var(--jade);
}

.tiny {
  font-size: 10px;
  padding: 1px 6px;
}

.src {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.6;
}

.guidance {
  color: var(--ink-2);
  font-size: 11px;
  line-height: 1.7;
  border-left: 2px solid var(--line);
  padding-left: 8px;
  margin: 4px 0;
}

.reason {
  color: var(--ink-2);
  font-size: 12px;
}

.gap {
  color: var(--clay);
  font-size: 11px;
}

.block {
  border-color: rgba(168, 68, 42, 0.4);
}

.diverge,
.folk {
  border-color: rgba(176, 138, 79, 0.5);
  background: linear-gradient(0deg, var(--gold-soft), var(--surface));
}

.override {
  margin: 8px 0 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--gold-soft);
  color: #7d5a20;
  font-size: 12px;
}

.school {
  padding: 8px 0;
  border-top: 1px dashed var(--line);
}

.school-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.school-head b {
  font-size: 15px;
}

.weights {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  align-items: center;
  margin-top: 10px;
  font-size: 11px;
}

.chip.candidate {
  border-color: rgba(63, 107, 90, 0.45);
  color: var(--jade);
}

.chip.bad {
  border-color: rgba(168, 68, 42, 0.4);
  color: var(--clay);
}

.chip.warn {
  border-color: rgba(176, 138, 79, 0.55);
  color: #8a6524;
}

.note {
  margin: 10px 0 0;
  color: var(--muted);
  font-size: 11px;
}

/* 斗首参考层：表格只承载查表结果，不加吉凶着色，避免被读成"结论" */
.doushou {
  width: 100%;
  margin: 8px 0 6px;
  border-collapse: collapse;
  font-size: 12px;
}

.doushou th,
.doushou td {
  padding: 4px 6px;
  text-align: left;
  border-bottom: 1px dashed var(--line);
  white-space: nowrap;
}

.doushou th {
  color: var(--muted);
  font-weight: 500;
}
</style>
