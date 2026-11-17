<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { buildZeRi, categoryLabel, evaluateCategoryTerms } from '@core/engines/zeri'
import { evaluateDay, type DayEvaluation } from '@core/zeri/evaluate'
import { THREE_LUCKY_STARS, dongGongStarOf } from '@core/zeri/tables/donggong'
import type { ZeRiResult } from '@core/types'
import ControlPanel from './components/ControlPanel.vue'
import DayDetail from './components/DayDetail.vue'
import MonthCalendar from './components/MonthCalendar.vue'
import ArchiveView from './views/ArchiveView.vue'
import PaipanView from './views/PaipanView.vue'
import CompassView from './views/CompassView.vue'
import { useArchiveStore } from './archive/store'
import { snapshotOf } from './archive/snapshot'
import { renderReportHtml } from './report/html'
import { renderWindowReportHtml } from './report/window'
import { buildPaipanReport } from '@core/paipan'
import { createState, toEvaluationInput, toQuery, type DayCell, type WorkbenchState } from './workbench'

const state = createState()
const result = ref<ZeRiResult | null>(null)
const elapsed = ref(0)
const selected = ref(state.startDate)
const monthCursor = ref(state.startDate.slice(0, 7))
const cache = new Map<string, DayEvaluation>()

/** 模块切换：四个模块共用一个工作台状态。 */
const module = ref<'zeri' | 'paipan' | 'compass' | 'archive'>('zeri')
// reactive 包装：模板里直接读 archive.archives / archive.errorMessage，不必写 .value
const archive = reactive(useArchiveStore())

/** 自动保存：输入变更后 2s 防抖落盘；载入档案时不触发（避免把刚载入的基准当改动）。 */
let autosaveTimer: ReturnType<typeof setTimeout> | null = null
let suppressAutosave = false
watch(
  state,
  () => {
    if (suppressAutosave || !archive.currentId) return
    if (autosaveTimer) clearTimeout(autosaveTimer)
    autosaveTimer = setTimeout(() => {
      autosaveTimer = null
      void archive.autosave(state)
    }, 2000)
  },
  { deep: true },
)
onUnmounted(() => {
  if (autosaveTimer) {
    clearTimeout(autosaveTimer)
    void archive.autosave(state)   // 退出前把最后一次改动落盘
  }
})

onMounted(() => {
  void archive.load()
})

/** 载入档案：就地覆盖 reactive 状态，保持 ControlPanel 的引用不失效。 */
function applyState(next: WorkbenchState) {
  suppressAutosave = true
  Object.assign(state, next)
  module.value = 'zeri'
  requestScan()
  // state 的 watch 是异步调度，下一个 tick 后解除抑制
  void Promise.resolve().then(() => { suppressAutosave = false })
}

function evalOf(date: string): DayEvaluation {
  const input = toEvaluationInput(state, date)
  // 键直接取评估入参：新增一个影响判定的字段时，不会因为忘了同步 cacheKey 而读到旧结果
  const key = `${date}|${JSON.stringify(input)}`
  const hit = cache.get(key)
  if (hit) return hit
  const created = evaluateDay({ date, ...input })
  cache.set(key, created)
  return created
}

function scan() {
  const started = performance.now()
  cache.clear()
  result.value = buildZeRi(toQuery(state))
  elapsed.value = Math.round(performance.now() - started)
  const first = result.value?.items[0]?.solarDate
  selected.value = first && first >= state.startDate ? first : state.startDate
  monthCursor.value = selected.value.slice(0, 7)
  // 档案已关联且输入一致时，这次结论就是下次 diff 的基准；不一致时 store 会拒绝写入
  if (result.value) void archive.recordEvaluation(snapshotOf(result.value, state))
}

/** 当前扫描的可比对快照；有档案时用于和上次保存的结论对比。 */
const currentSnapshot = computed(() => (result.value ? snapshotOf(result.value, state) : null))

/**
 * 与档案上次结论的归因。
 *
 * 只在「当前档案有 lastEvaluation」时有值：没有基准就不该编造「无变化」。
 * 输入改了但没保存时，归因会是 input_only —— 这正是要告诉用户的。
 */
const diff = computed(() => {
  const snapshot = currentSnapshot.value
  if (!snapshot) return null
  return archive.diffAgainstCurrent(snapshot)
})

const diffTitle = computed(() => {
  switch (diff.value?.kind) {
    case 'input_only':
      return '输入已改（尚未保存）'
    case 'rules_only':
      return '规则包已更新'
    case 'both':
      return '输入与规则包都变了'
    case 'unstable':
      return '结论不稳定'
    default:
      return ''
  }
})

const exporting = ref(false)
const exportMessage = ref('')

/** 导出当前选中日期的复核报告（自包含 HTML，可用浏览器打印为 PDF）。 */
async function exportReport() {
  const evaluation = detail.value
  if (!evaluation) return
  const bridge = window.desktop
  if (!bridge?.exportReport) {
    exportMessage.value = '浏览器预览模式不支持导出，请用桌面端'
    return
  }
  exporting.value = true
  exportMessage.value = ''
  try {
    const html = renderReportHtml(evaluation, {
      generatedAt: new Date().toLocaleString('zh-CN'),
      taskLabel: categoryLabel(state.category),
      mountShan: state.mountShan,
      sittingDeg: state.sittingDeg,
      inputHash: currentSnapshot.value?.inputHash,
      attribution: diff.value,
      windowNote: `${state.startDate} 起 ${state.daysCount} 天`,
    })
    const result = await bridge.exportReport({
      html,
      suggestedName: `择日复核-${evaluation.date}.html`,
    })
    exportMessage.value = result.ok ? `已导出到 ${result.file}` : '已取消导出'
  } catch (error) {
    exportMessage.value = `导出失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    exporting.value = false
  }
}

const SAN_SHA_LABEL: Record<string, string> = {
  year: '仅年家占山硬排',
  year_month: '年家＋月家占山硬排',
  all: '四家占山＋日课相犯全排',
}

/** 导出整个扫描窗口的报告：概览 + 候选清单 + 排除统计 + 排盘四派。 */
async function exportWindowReport() {
  const current = result.value
  if (!current) return
  const bridge = window.desktop
  if (!bridge?.exportReport) {
    exportMessage.value = '浏览器预览模式不支持导出，请用桌面端'
    return
  }
  exporting.value = true
  exportMessage.value = ''
  try {
    const paipan = buildPaipanReport({
      mountShan: state.mountShan,
      sittingDeg: state.sittingDeg,
      year: Number(state.startDate.slice(0, 4)),
      members: state.subjects
        .filter((person) => person.date)
        .map((person) => ({
          relation: person.label,
          birth: { date: person.date, gender: person.gender },
        })),
      deceased: state.deceased
        .filter((person) => person.date)
        .map((person) => ({
          label: person.label,
          birth: { date: person.date, gender: person.gender },
        })),
    })

    const html = renderWindowReportHtml(current, {
      generatedAt: new Date().toLocaleString('zh-CN'),
      taskLabel: categoryLabel(state.category),
      mountShan: state.mountShan,
      sittingDeg: state.sittingDeg,
      startDate: state.startDate,
      daysCount: state.daysCount,
      inputHash: currentSnapshot.value?.inputHash,
      attribution: diff.value,
      paipan,
      policyNotes: [
        `三煞口径：${SAN_SHA_LABEL[state.sanShaMode] ?? state.sanShaMode}`,
        `金神七煞：${state.jinShenMode === 'reject' ? '硬排除' : '仅提示'}`,
        `民俗神煞：${state.folkMode === 'reject' ? '硬排除' : '仅提示'}`,
        `重丧日：${state.chongSangMode === 'reject' ? '硬排除' : '仅提示'}`,
        `只取黄道日：${state.onlyHuangDao ? '是' : '否'}`,
        `避开二十八宿凶日：${state.avoidXiuXiong ? '是' : '否'}`,
        `大卦爻位：${state.yaoOrder === 'ASC' ? '顺排' : '逆排'}`,
      ],
    })
    const res = await bridge.exportReport({
      html,
      suggestedName: `择日窗口-${state.startDate}-${state.daysCount}天.html`,
    })
    exportMessage.value = res.ok ? `已导出到 ${res.file}` : '已取消导出'
  } catch (error) {
    exportMessage.value = `导出失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    exporting.value = false
  }
}

/**
 * 200ms 防抖：兼向度数、起始日、主命生日都是逐字符输入的，
 * 一次整窗扫描实测 478ms（180 天，本机），逐字符重扫会把渲染线程钉死。
 * 单次扫描若将来因排盘/罗盘接入超过 1s，再改走 Web Worker 而不是继续加大防抖。
 */
const SCAN_DEBOUNCE_MS = 200
let scanTimer: ReturnType<typeof setTimeout> | undefined
const scanning = ref(false)

function requestScan() {
  if (scanTimer) clearTimeout(scanTimer)
  scanning.value = true
  scanTimer = setTimeout(() => {
    scanTimer = undefined
    scanning.value = false
    scan()
  }, SCAN_DEBOUNCE_MS)
}

// 任何进入查询条件的改动都走同一条防抖路径，控件上的 @change 只负责提前触发。
watch(() => JSON.stringify(toQuery(state)), requestScan)
onUnmounted(() => {
  if (scanTimer) clearTimeout(scanTimer)
})

const scannedEnd = computed(() => {
  const [year, month, day] = state.startDate.split('-').map(Number)
  const end = new Date(Date.UTC(year, month - 1, day + state.daysCount - 1))
  return end.toISOString().slice(0, 10)
})

const candidateDates = computed(() => new Set((result.value?.items ?? []).map((item) => item.solarDate)))

const monthLabel = computed(() => {
  const [year, month] = monthCursor.value.split('-')
  return `${year} 年 ${Number(month)} 月`
})

const cells = computed<DayCell[]>(() => {
  const [year, month] = monthCursor.value.split('-').map(Number)
  const first = new Date(Date.UTC(year, month - 1, 1))
  const lead = first.getUTCDay()
  const total = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const list: DayCell[] = []
  for (let offset = 0; offset < 42; offset++) {
    const shifted = offset - lead + 1
    const date = new Date(Date.UTC(year, month - 1, shifted)).toISOString().slice(0, 10)
    const inMonth = shifted >= 1 && shifted <= total
    const inRange = date >= state.startDate && date <= scannedEnd.value && !!result.value
    let status: DayCell['status'] = 'outside'
    let ganZhi = ''
    let zhiXing = ''
    let xiu = ''
    let luckyStar = false
    let reasons: string[] = []
    let consensus = ''
    if (inRange) {
      const evaluation = evalOf(date)
      const facts = evaluation.facts
      ganZhi = facts.pillars.day.ganZhi
      zhiXing = facts.zhiXing
      xiu = facts.xiu
      luckyStar = THREE_LUCKY_STARS.includes(
        dongGongStarOf(facts.monthBranch, facts.pillars.day.ganZhi),
      )
      consensus = evaluation.arbitration.consensus
      if (candidateDates.value.has(date)) {
        status = 'candidate'
      } else if (evaluation.dasha.rejected) {
        status = 'rejected'
        reasons = evaluation.dasha.hits.map((hit) => hit.name)
      } else {
        const { matchedYi, termInJi } = evaluateCategoryTerms(
          state.category,
          facts.almanacYi,
          facts.almanacJi,
        )
        const flagged =
          (!matchedYi.length || termInJi.length) ||
          (state.onlyHuangDao && facts.tianShenLuck !== '吉') ||
          (state.avoidXiuXiong && facts.xiuLuck !== '吉')
        status = flagged ? 'unmatched' : 'outside'
      }
    }
    list.push({
      date,
      day: Number(date.slice(8, 10)),
      lead: !inMonth,
      status,
      ganZhi,
      zhiXing,
      xiu,
      luckyStar,
      reasons,
      consensus,
    })
  }
  return list
})

const detail = computed(() => (result.value ? evalOf(selected.value) : null))

function page(delta: number) {
  const [year, month] = monthCursor.value.split('-').map(Number)
  const next = new Date(Date.UTC(year, month - 1 + delta, 1))
  monthCursor.value = next.toISOString().slice(0, 7)
}

function pick(date: string) {
  selected.value = date
}

const blocking = computed(() => {
  if (!result.value || result.value.items.length > 0) return null
  const list = result.value.rejections
  if (!list.length) return null
  const top = [...list].sort((a, b) => b.count - a.count)[0]
  if (top.count < Math.max(1, result.value.scanned * 0.5)) return null
  return top
})

const rejectionTotal = computed(
  () => (result.value?.rejections ?? []).reduce((sum, item) => sum + item.count, 0),
)

const luckyExcluded = computed(() => {
  const hits = (result.value?.rejections ?? []).filter((item) => item.luckyStarDays > 0)
  return { samples: hits.flatMap((item) => item.luckyStarSamples).slice(0, 4) }
})

scan()
</script>

<template>
  <div class="app">
    <header class="top">
      <div class="brand">
        <span class="brand-mark serif">居境罗盘</span>
        <span class="brand-sub">桌面工作台 · 确定性引擎 + 五派并列</span>
      </div>
      <nav class="modules">
        <button class="mod" :class="{ on: module === 'zeri' }" @click="module = 'zeri'">择日</button>
        <button class="mod" :class="{ on: module === 'paipan' }" @click="module = 'paipan'">
          排盘
        </button>
        <button class="mod" :class="{ on: module === 'compass' }" @click="module = 'compass'">
          罗盘
        </button>
        <button class="mod" :class="{ on: module === 'archive' }" @click="module = 'archive'">
          档案
        </button>
      </nav>
      <div v-if="result && module === 'zeri'" class="stats">
        <span>扫描 <b>{{ result.scanned }}</b> 天</span>
        <span>大煞排除 <b>{{ result.rejected }}</b> 天</span>
        <span>宜忌不符 <b>{{ result.unmatched }}</b> 天</span>
        <span>候选 <b>{{ result.items.length }}</b> 天</span>
        <span v-if="scanning" class="muted">重扫中…</span>
        <span v-else class="muted">{{ elapsed }}ms</span>
      </div>
      <button
        v-if="module === 'zeri' && result"
        class="export-btn"
        :disabled="exporting"
        @click="exportWindowReport"
      >
        窗口报告
      </button>
      <button
        v-if="detail && module === 'zeri'"
        class="export-btn"
        :disabled="exporting"
        @click="exportReport"
      >
        {{ exporting ? '导出中…' : '本日报告' }}
      </button>
    </header>

    <div v-if="archive.warning" class="app-alert" role="alert">
      <span>{{ archive.warning }}</span>
      <button class="linkbtn" @click="archive.dismissWarning()">知道了</button>
    </div>

    <main class="body">
      <template v-if="module === 'zeri'">
      <ControlPanel :state="state" @scan="requestScan" />
      <section class="center scroll">
        <section
          v-if="diff && diff.kind !== 'none'"
          class="diff"
          :class="{ danger: diff.kind === 'unstable' }"
        >
          <b>{{ diffTitle }}</b>
          <span>{{ diff.narrative }}</span>
        </section>
        <p v-if="exportMessage" class="export-msg">{{ exportMessage }}</p>
        <section v-if="blocking" class="banner">
          <b class="serif">当前条件下没有候选日：主因「{{ blocking.name }}」排除 {{ blocking.count }}/{{ result?.scanned }} 天。</b>
          <p>{{ blocking.guidance }}</p>
          <p class="src">出处：{{ blocking.source }} · {{ blocking.review ? '可人工复核后放宽' : '属不可放宽的硬排除项' }}</p>
        </section>
        <MonthCalendar
          :month-label="monthLabel"
          :cells="cells"
          :selected="selected"
          @select="pick"
          @page="page"
        />
        <section v-if="result?.rejections.length" class="card">
          <div class="card-title">
            <span>前置层排除统计</span>
            <em class="muted">累计命中 {{ rejectionTotal }} 次（同一日可犯多条）</em>
          </div>
          <table class="rej">
            <thead>
              <tr>
                <th>大煞</th>
                <th>天数</th>
                <th>三吉星仍被排除</th>
                <th>出处</th>
                <th>口径</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rej in result.rejections" :key="rej.name">
                <td>
                  {{ rej.name }}
                  <div class="src">{{ rej.guidance }}</div>
                </td>
                <td>{{ rej.count }}</td>
                <td>
                  <template v-if="rej.luckyStarDays">
                    {{ rej.luckyStarDays }} 天 · {{ rej.luckyStarSamples.join('，') }}
                  </template>
                  <span v-else class="muted">—</span>
                </td>
                <td class="muted">{{ rej.source }}</td>
                <td>
                  <span class="chip" :class="rej.review ? 'warn' : 'bad'">
                    {{ rej.review ? '可人工复核' : '不可放宽' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="luckyExcluded.samples.length" class="note">
            例：{{ luckyExcluded.samples.join('；') }} —— 吉星值日仍被大煞排除，符合「能解诸凶，唯不能解金神七煞」。
          </p>
        </section>
        <section class="card">
          <div class="card-title"><span>筛选说明</span></div>
          <p v-for="(note, index) in (result?.notes ?? [])" :key="index" class="note">· {{ note }}</p>
        </section>
      </section>
      <DayDetail :evaluation="detail" />
      </template>
      <PaipanView v-else-if="module === 'paipan'" :state="state" />
      <CompassView v-else-if="module === 'compass'" :state="state" @scan="requestScan" />
      <ArchiveView
        v-else
        :state="state"
        :snapshot="currentSnapshot"
        @open="applyState"
        @scan="requestScan"
      />
    </main>
  </div>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.top {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--line);
  background: var(--surface);
}

.brand {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.brand-mark {
  font-size: 19px;
  letter-spacing: 0.08em;
}

.brand-sub {
  color: var(--muted);
  font-size: 11px;
}

.modules {
  display: flex;
  gap: 6px;
}

.mod {
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px solid transparent;
  background: none;
  color: var(--muted);
  font-size: 12px;
}

.mod.on {
  border-color: var(--jade);
  background: var(--jade-soft);
  color: var(--jade);
}

.mod:disabled {
  opacity: 0.5;
  cursor: default;
}

.stats {
  margin-left: auto;
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--ink-2);
}

.stats b {
  font-family: var(--serif);
  font-size: 14px;
  color: var(--ink);
}

.export-btn {
  flex-shrink: 0;
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px solid var(--jade);
  background: var(--jade-soft);
  color: var(--jade);
  font-size: 12px;
}

.export-btn:disabled {
  opacity: 0.6;
}

.export-msg {
  margin: 0;
  color: var(--jade);
  font-size: 11px;
}

.app-alert {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 18px;
  border-bottom: 1px solid rgba(176, 138, 79, 0.55);
  background: var(--gold-soft);
  color: #7d5a20;
  font-size: 12px;
}

.app-alert span {
  flex: 1;
}

.linkbtn {
  border: none;
  background: none;
  color: var(--jade);
  padding: 2px 4px;
  font-size: 12px;
}

.body {
  flex: 1;
  display: flex;
  gap: 14px;
  padding: 14px 18px 18px;
  min-height: 0;
}

.center {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  max-height: 100%;
  padding-right: 2px;
}

.card-title {
  font-family: var(--serif);
  font-size: 14px;
  margin-bottom: 8px;
  display: flex;
  gap: 8px;
  align-items: baseline;
}

.rej {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.rej th {
  text-align: left;
  color: var(--muted);
  font-weight: 500;
  padding: 4px 8px 6px 0;
  border-bottom: 1px solid var(--line);
}

.rej td {
  padding: 6px 8px 6px 0;
  border-bottom: 1px dashed var(--line);
  vertical-align: top;
}

.diff {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-left: 3px solid var(--gold);
  border-radius: 8px;
  background: var(--gold-soft);
  font-size: 12px;
  color: var(--ink-2);
}

.diff b {
  font-family: var(--serif);
  color: var(--ink);
  flex-shrink: 0;
}

.diff.danger {
  border-left-color: var(--clay);
  background: var(--clay-soft);
  color: var(--clay);
}

.banner {
  padding: 12px 14px;
  border: 1px solid rgba(176, 138, 79, 0.55);
  border-radius: 10px;
  background: linear-gradient(0deg, var(--gold-soft), #fffdf8);
}

.banner p {
  margin: 6px 0 0;
  color: var(--ink-2);
}

.banner .src {
  margin-top: 4px;
  color: var(--muted);
  font-size: 11px;
}

.src {
  color: var(--muted);
  font-size: 11px;
}

.note {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.65;
}
</style>
