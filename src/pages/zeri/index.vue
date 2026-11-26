<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import type { ZeRiCategory, ZeRiItem, ZeRiResult } from '@/core/types'
import { BEHAVIOR_LABELS } from '@/core/constants/xieji'
import { ZHI } from '@/core/constants/nayin60'
import { buildZeRi, mergeZeRiResults, schoolTendencyLabel } from '@/core/engines/zeri'
import type { SchoolConflict, SchoolResult } from '@/core/zeri/types'
import { zeriCategoryOf, zeriQueryForArchive } from '@/core/engines/report'
import { addDays, todayYmd } from '@/core/utils/date'
import { useArchiveStore } from '@/stores/archive'
import { modeLabel, sittingFacingText } from '@/utils/display'
import AppHeader from '@/components/AppHeader.vue'

interface CategoryOption {
  value: ZeRiCategory
  label: string
  glyph: string
  hint: string
}

const archiveStore = useArchiveStore()
const archiveId = ref('')
const category = ref<ZeRiCategory>('YANG_RUZHAI')
const startDate = ref(todayYmd())
const days = ref(90)
const displayLimit = ref(20)
const result = ref<ZeRiResult | null>(null)
const running = ref(false)
const pendingRun = ref(false)
const expanded = ref<Record<string, boolean>>({})
const openSchools = ref<Record<string, boolean>>({})
const advancedOpen = ref(false)
const showAllRejections = ref(false)
const notesOpen = ref(false)
const hourBranch = ref('')
const sanShaMode = ref<'year' | 'year_month' | 'all'>('year_month')
const chongSangMode = ref<'reject' | 'warn'>('reject')
const includeConstruction = ref(false)
const jinShenMode = ref<'reject' | 'warn'>('reject')
const folkMode = ref<'reject' | 'warn'>('reject')
const onlyHuangDao = ref(false)
const avoidXiuXiong = ref(false)
let runTimer: ReturnType<typeof setTimeout> | null = null

const categories: CategoryOption[] = [
  { value: 'YANG_RUZHAI', label: '入宅安床', glyph: '宅', hint: '搬移 · 安床' },
  { value: 'YANG_DONGTU', label: '动土修造', glyph: '造', hint: '起基 · 修造' },
  { value: 'YANG_JIAQU', label: '嫁娶订盟', glyph: '娶', hint: '纳采 · 订盟' },
  { value: 'YANG_KAISHI', label: '开市交易', glyph: '市', hint: '立券 · 纳财' },
  { value: 'YIN_ANZANG', label: '安葬破土', glyph: '葬', hint: '破土 · 启攒' },
  { value: 'YIN_XIUFEN', label: '修坟立碑', glyph: '碑', hint: '谢土 · 立碑' },
]
const dayOptions = [30, 60, 90, 180]
const limitOptions = [8, 12, 20]
const sanShaOptions = [
  { value: 'year', label: '仅年家' },
  { value: 'year_month', label: '年 + 月' },
  { value: 'all', label: '四层全排' },
] as const
const hourOptions = [{ value: '', label: '不限时辰' }].concat(
  ZHI.map((item) => ({ value: item, label: `${item}时` }))
)
const orbitChars = ZHI.slice(0, 12)

const archive = computed(() => archiveStore.getById(archiveId.value))
const archiveOptions = computed(() => archiveStore.sorted)
const archiveIndex = computed(() =>
  Math.max(0, archiveOptions.value.findIndex((item) => item.id === archiveId.value))
)
const pair = computed(() => (archive.value ? sittingFacingText(archive.value.reading.facingDeg) : null))
const activeCategory = computed(
  () => categories.find((item) => item.value === category.value) ?? categories[0]
)
const isYin = computed(() => category.value === 'YIN_ANZANG' || category.value === 'YIN_XIUFEN')
const isMove = computed(() => category.value === 'YANG_RUZHAI')
const hourIndex = computed(() =>
  Math.max(0, hourOptions.findIndex((item) => item.value === hourBranch.value))
)
const advancedCount = computed(() => {
  let count = 0
  if (hourBranch.value) count++
  if (displayLimit.value !== 20) count++
  if (includeConstruction.value) count++
  if (sanShaMode.value !== 'year_month') count++
  if (chongSangMode.value !== 'reject') count++
  if (jinShenMode.value !== 'reject') count++
  if (folkMode.value !== 'reject') count++
  if (onlyHuangDao.value) count++
  if (avoidXiuXiong.value) count++
  return count
})
const rangeEnd = computed(() => addDays(startDate.value, days.value - 1))
const rangeShort = computed(() => {
  const start = dateParts(startDate.value)
  const end = dateParts(rangeEnd.value)
  return `${start.month}.${start.day} — ${end.month}.${end.day}`
})
const scanCount = computed(() => result.value?.scanned ?? 0)
const eligibleCount = computed(() => result.value?.eligible ?? 0)
const rejectionCount = computed(() => result.value?.rejected ?? 0)
const categoryStats = computed(() => {
  if (!result.value) return '待排布'
  return result.value.truncated ? `候选池 ${result.value.eligible}` : `候选 ${result.value.items.length}`
})

onLoad((query) => {
  archiveId.value = String(query?.id ?? '') || archiveStore.currentId || ''
  if (!archiveId.value) archiveId.value = archiveStore.sorted[0]?.id ?? ''
  if (archive.value) category.value = zeriCategoryOf(archive.value)
  if (archiveId.value) run()
})

onUnload(() => {
  if (runTimer) clearTimeout(runTimer)
})

function addDays(ymd: string, offset: number): string {
  const date = new Date(`${ymd}T00:00:00`)
  date.setDate(date.getDate() + offset)
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

function execute() {
  if (!archive.value) return
  if (running.value) {
    pendingRun.value = true
    return
  }
  running.value = true
  // 分片计算（P1-6）：90 天全量同步计算在低端安卓上会冻结主线程 7~11s。
  // 每 15 天一片，片间 setTimeout(0) 让出主线程；首片完成即可渲染，
  // 后续片用 mergeZeRiResults 合并（合并语义有单测锁定）。
  // 分片只改「何时出结果」，不改任何判定口径——合并函数在核心层且有测试。
  const CHUNK_DAYS = 15
  setTimeout(() => {
    const totalDays = days.value
    const parts: ZeRiResult[] = []
    let chunkIndex = 0
    const step = () => {
      let finished = false
      try {
        const chunkDays = Math.min(CHUNK_DAYS, totalDays - chunkIndex * CHUNK_DAYS)
        const query = zeriQueryForArchive(
          archive.value!,
          addDays(startDate.value, chunkIndex * CHUNK_DAYS),
          chunkDays,
          displayLimit.value
        )
        query.category = category.value
        query.hourBranch = hourBranch.value || null
        query.sanShaMode = sanShaMode.value
        query.chongSangMode = isYin.value ? chongSangMode.value : 'reject'
        query.includesConstruction = isMove.value && includeConstruction.value
        query.jinShenMode = jinShenMode.value
        query.folkMode = folkMode.value
        query.onlyHuangDao = onlyHuangDao.value
        query.avoidXiuXiong = avoidXiuXiong.value
        parts.push(buildZeRi(query))
        chunkIndex++
        result.value = mergeZeRiResults(parts, {
          displayLimit: displayLimit.value,
          startDate: startDate.value,
          daysCount: totalDays,
          category: category.value,
        })
        finished = chunkIndex * CHUNK_DAYS >= totalDays
        if (!finished) {
          expanded.value = {}
          openSchools.value = {}
          showAllRejections.value = false
          setTimeout(step, 0)
        } else {
          expanded.value = {}
          openSchools.value = {}
          showAllRejections.value = false
        }
      } catch (error) {
        uni.showToast({
          title: error instanceof Error ? error.message : '筛选失败',
          icon: 'none',
        })
        finished = true
      } finally {
        if (finished) {
          running.value = false
          if (pendingRun.value) {
            pendingRun.value = false
            scheduleRun(60)
          }
        }
      }
    }
    step()
  }, 24)
}

function run() {
  if (!archive.value || running.value) return
  execute()
}

function scheduleRun(delay = 160) {
  if (runTimer) clearTimeout(runTimer)
  runTimer = setTimeout(() => {
    runTimer = null
    if (running.value) {
      pendingRun.value = true
      return
    }
    execute()
  }, delay)
}

function pickArchive(event: { detail: { value: number | string } }) {
  const item = archiveOptions.value[Number(event.detail.value)]
  if (!item) return
  archiveId.value = item.id
  archiveStore.setCurrent(item.id)
  category.value = zeriCategoryOf(item)
  scheduleRun(20)
}

function chooseCategory(value: ZeRiCategory) {
  if (category.value === value) return
  category.value = value
  scheduleRun()
}

function pickStart(event: { detail: { value: string } }) {
  startDate.value = String(event.detail.value)
  scheduleRun()
}

function setDays(value: number) {
  days.value = value
  scheduleRun()
}

function pickHour(event: { detail: { value: number | string } }) {
  hourBranch.value = hourOptions[Number(event.detail.value)]?.value ?? ''
  scheduleRun()
}

function setLimit(value: number) {
  displayLimit.value = value
  scheduleRun()
}

function setSanSha(value: 'year' | 'year_month' | 'all') {
  sanShaMode.value = value
  scheduleRun()
}

function setMode(key: 'jinShen' | 'folk' | 'chongSang') {
  if (key === 'jinShen') jinShenMode.value = jinShenMode.value === 'reject' ? 'warn' : 'reject'
  else if (key === 'folk') folkMode.value = folkMode.value === 'reject' ? 'warn' : 'reject'
  else chongSangMode.value = chongSangMode.value === 'reject' ? 'warn' : 'reject'
  scheduleRun()
}

function setFlag(key: 'onlyHuangDao' | 'avoidXiuXiong' | 'includeConstruction') {
  if (key === 'onlyHuangDao') onlyHuangDao.value = !onlyHuangDao.value
  else if (key === 'avoidXiuXiong') avoidXiuXiong.value = !avoidXiuXiong.value
  else includeConstruction.value = !includeConstruction.value
  scheduleRun()
}

function toggleDetail(date: string) {
  expanded.value = { ...expanded.value, [date]: !expanded.value[date] }
}

function schoolKey(date: string, school: string) {
  return `${date}:${school}`
}

function toggleSchool(date: string, school: string) {
  const key = schoolKey(date, school)
  openSchools.value = { ...openSchools.value, [key]: !openSchools.value[key] }
}

function schoolTone(school: SchoolResult): string {
  if (school.status !== 'FULL') return 'is-partial'
  if (school.tendency === 'favorable') return 'is-favorable'
  if (school.tendency === 'unfavorable') return 'is-cautious'
  return 'is-neutral'
}

function schoolState(school: SchoolResult): string {
  if (school.status === 'UNAVAILABLE') return '未启'
  if (school.status === 'PARTIAL') return '部分'
  return schoolTendencyLabel(school.tendency)
}

function evidenceOf(item: ZeRiItem) {
  const sources = new Set<string>()
  let gaps = 0
  let reviews = 0
  for (const school of item.schools) {
    if (school.needsHumanReview) reviews++
    for (const rule of school.subRules) {
      sources.add(rule.source.id)
      if (rule.dataGap) gaps++
      if (rule.needsHumanReview) reviews++
    }
  }
  return { sources: sources.size, gaps, reviews }
}

function favorableSchools(item: ZeRiItem): number {
  return item.schools.filter(
    (school) => school.status === 'FULL' && school.tendency === 'favorable'
  ).length
}

function dateParts(date: string) {
  const [year, month, day] = date.split('-')
  return { year, month, day }
}

function rejectionWidth(count: number): string {
  if (!scanCount.value) return '0%'
  return `${Math.min(100, Math.max(4, Math.round((count / scanCount.value) * 100)))}%`
}

function behaviorLabel(item: ZeRiItem): string {
  return BEHAVIOR_LABELS[item.behavior] ?? item.levelName
}

function factsOf(item: ZeRiItem) {
  const xiuState = item.xiuLuck === '吉' ? '协' : item.xiuLuck === '凶' ? '不协' : item.xiuLuck
  return [
    { label: '值神', value: item.tianShen },
    { label: '建除', value: item.zhiXing },
    { label: '星宿', value: `${item.xiu} · ${xiuState}` },
    { label: '冲煞', value: `冲${item.chongShengXiao} · 煞${item.sha}` },
    { label: '喜方', value: item.positions.xi },
    { label: '贵方', value: item.positions.yangGui },
  ]
}

function openReport() {
  if (!archive.value) return
  uni.navigateTo({ url: `/pages/report/index?id=${archive.value.id}` })
}

function conflictSchools(item: ZeRiItem, conflict: SchoolConflict): string {
  return conflict.schools
    .map((id) => item.schools.find((school) => school.school === id)?.schoolLabel ?? id)
    .join(' · ')
}

function createArchive() {
  uni.navigateTo({ url: '/pages/wizard/index?mode=YANG' })
}
</script>

<template>
  <view class="page zeri-page">
    <AppHeader
      title="择日参考"
      eyebrow="CELESTIAL TIMING"
      back
    />

    <view class="shell zeri-shell">
      <view class="timing-hero">
        <view class="hero-grain" />
        <view class="hero-copy">
          <text class="hero-kicker">观天时 · 察地利 · 参人和</text>
          <text class="hero-title serif">取时</text>
          <text class="hero-desc">
            以坐山为轴，合家人生肖与用事类别，完整扫描所选时间窗；五派依据并列，不合成单一结论。
          </text>
        </view>

        <view class="orbit" aria-hidden="true">
          <view
            v-for="(char, index) in orbitChars"
            :key="char"
            class="orbit-mark"
            :style="{ transform: `rotate(${index * 30}deg)` }"
          >
            <text class="orbit-char" :style="{ transform: `rotate(${-index * 30}deg)` }">
              {{ char }}
            </text>
          </view>
          <view class="orbit-ring orbit-ring-inner" />
          <view class="orbit-core">
            <text class="core-glyph serif">{{ activeCategory.glyph }}</text>
            <text class="core-label">{{ categoryStats }}</text>
          </view>
        </view>

        <view class="hero-readout">
          <view class="readout-item">
            <text class="readout-value serif">{{ scanCount || '—' }}</text>
            <text class="readout-label">扫描天数</text>
          </view>
          <view class="readout-divider" />
          <view class="readout-item">
            <text class="readout-value serif">{{ rejectionCount || '—' }}</text>
            <text class="readout-label">前置排除</text>
          </view>
          <view class="readout-divider" />
          <view class="readout-item">
            <text class="readout-value serif is-gold">{{ eligibleCount || '—' }}</text>
            <text class="readout-label">条件候选</text>
          </view>
          <view class="hero-range">
            <text>{{ days }} 日窗</text>
            <text>{{ rangeShort }}</text>
          </view>
        </view>
      </view>

      <view v-if="!archiveOptions.length" class="paper-card empty-card">
        <view class="empty-orbit">
          <text class="empty-glyph serif">时</text>
        </view>
        <text class="empty-title serif">先立一份环境档案</text>
        <text class="empty-copy">
          择日需要坐山、朝向与家人信息。建立档案后，本页会自动带入方位与生肖条件。
        </text>
        <button class="primary-action" @click="createArchive">建立第一份档案</button>
      </view>

      <template v-else>
        <view class="paper-card setup-card">
          <view class="section-head">
            <text class="section-no serif">01</text>
            <view class="section-copy">
              <text class="section-title serif">场址与用事</text>
              <text class="section-sub">先确定山向，再落入具体事项</text>
            </view>
            <text class="section-side">本机演算</text>
          </view>

          <picker
            mode="selector"
            :range="archiveOptions"
            range-key="title"
            :value="archiveIndex"
            @change="pickArchive"
          >
            <view class="archive-select">
              <view class="archive-mark serif">{{ modeLabel(archive?.mode ?? 'YANG').slice(0, 1) }}</view>
              <view class="archive-copy">
                <text class="field-label">当前档案</text>
                <text class="archive-name">{{ archive?.title || '请选择档案' }}</text>
                <text class="archive-meta">
                  {{ modeLabel(archive?.mode ?? 'YANG') }}
                  <template v-if="pair"> · {{ pair.text }} · {{ pair.deg }}</template>
                </text>
              </view>
              <text class="select-arrow">⌄</text>
            </view>
          </picker>

          <view class="field-group">
            <view class="field-heading">
              <text class="field-label">用事类别</text>
              <text class="field-hint">每一类使用独立的通书词条与权重</text>
            </view>
            <view class="category-grid">
              <view
                v-for="item in categories"
                :key="item.value"
                class="category-tile"
                :class="{ 'is-active': category === item.value }"
                @click="chooseCategory(item.value)"
              >
                <text class="category-glyph serif">{{ item.glyph }}</text>
                <view class="category-copy">
                  <text class="category-name">{{ item.label }}</text>
                  <text class="category-hint">{{ item.hint }}</text>
                </view>
                <view class="category-corner" />
              </view>
            </view>
          </view>

          <view class="section-rule" />

          <view class="section-head is-compact">
            <text class="section-no serif">02</text>
            <view class="section-copy">
              <text class="section-title serif">时间窗口</text>
              <text class="section-sub">从起始日向后完整遍历，不提前截断统计</text>
            </view>
          </view>

          <view class="range-grid">
            <picker mode="date" :value="startDate" @change="pickStart">
              <view class="date-field">
                <text class="field-label">起始日期</text>
                <text class="date-value serif">{{ startDate }}</text>
                <text class="field-hint">点击更改</text>
              </view>
            </picker>
            <view class="duration-field">
              <text class="field-label">扫描范围</text>
              <view class="segment">
                <text
                  v-for="item in dayOptions"
                  :key="item"
                  class="segment-item"
                  :class="{ 'is-active': days === item }"
                  @click="setDays(item)"
                >
                  {{ item }}天
                </text>
              </view>
            </view>
          </view>

          <view class="section-rule" />

          <view class="section-head is-compact">
            <text class="section-no serif">03</text>
            <view class="section-copy">
              <text class="section-title serif">筛选口径</text>
              <text class="section-sub">默认口径较稳妥，进阶选项会单独标明影响</text>
            </view>
            <view class="advanced-toggle" @click.stop="advancedOpen = !advancedOpen">
              <text>{{ advancedOpen ? '收起' : '进阶' }}</text>
              <text v-if="advancedCount" class="toggle-count">{{ advancedCount }}</text>
              <text class="toggle-arrow" :class="{ 'is-open': advancedOpen }">⌄</text>
            </view>
          </view>

          <view class="default-rules">
            <view class="rule-pill">
              <text class="rule-dot is-red" />
              <text>前置排查先行</text>
            </view>
            <view class="rule-pill">
              <text class="rule-dot is-gold" />
              <text>五派并列呈现</text>
            </view>
            <view class="rule-pill">
              <text class="rule-dot is-jade" />
              <text>逐条保留出处</text>
            </view>
          </view>

          <view v-if="advancedOpen" class="advanced-panel">
            <view class="advanced-row">
              <view class="advanced-copy">
                <text class="advanced-title">指定时辰</text>
                <text class="advanced-hint">默认遍历全部时辰</text>
              </view>
              <picker
                mode="selector"
                :range="hourOptions"
                range-key="label"
                :value="hourIndex"
                @change="pickHour"
              >
                <view class="mini-select">{{ hourOptions[hourIndex]?.label }}<text class="mini-select-arrow">⌄</text></view>
              </picker>
            </view>

            <view class="advanced-row">
              <view class="advanced-copy">
                <text class="advanced-title">展示条数</text>
                <text class="advanced-hint">只影响列表，不影响完整扫描统计</text>
              </view>
              <view class="mini-segment">
                <text
                  v-for="item in limitOptions"
                  :key="item"
                  class="mini-item"
                  :class="{ 'is-active': displayLimit === item }"
                  @click="setLimit(item)"
                >
                  {{ item }}
                </text>
              </view>
            </view>

            <view class="advanced-row is-stacked">
              <view class="advanced-copy">
                <text class="advanced-title">三煞层级</text>
                <text class="advanced-hint">不同场景采用不同排查范围</text>
              </view>
              <view class="mini-segment is-wide">
                <text
                  v-for="item in sanShaOptions"
                  :key="item.value"
                  class="mini-item"
                  :class="{ 'is-active': sanShaMode === item.value }"
                  @click="setSanSha(item.value)"
                >
                  {{ item.label }}
                </text>
              </view>
            </view>

            <view v-if="isMove" class="advanced-row is-tappable" @click="setFlag('includeConstruction')">
              <view class="advanced-copy">
                <text class="advanced-title">入宅伴随动土</text>
                <text class="advanced-hint">开启后按兴工类追加山家排查</text>
              </view>
              <view class="switch" :class="{ 'is-on': includeConstruction }">
                <view class="switch-knob" />
              </view>
            </view>

            <view v-if="isYin" class="advanced-row is-tappable" @click="setMode('chongSang')">
              <view class="advanced-copy">
                <text class="advanced-title">重丧提示</text>
                <text class="advanced-hint">可改为保留提示，不直接排除</text>
              </view>
              <view class="switch" :class="{ 'is-on': chongSangMode === 'warn' }">
                <view class="switch-knob" />
              </view>
            </view>

            <view class="advanced-row is-tappable" @click="setMode('jinShen')">
              <view class="advanced-copy">
                <text class="advanced-title">金神七煞</text>
                <text class="advanced-hint">当前：{{ jinShenMode === 'reject' ? '命中即排除' : '只作提示' }}</text>
              </view>
              <view class="mode-toggle">
                {{ jinShenMode === 'reject' ? '排除' : '提示' }}
              </view>
            </view>

            <view class="advanced-row is-tappable" @click="setMode('folk')">
              <view class="advanced-copy">
                <text class="advanced-title">民俗口径项</text>
                <text class="advanced-hint">当前：{{ folkMode === 'reject' ? '命中即排除' : '只作提示' }}</text>
              </view>
              <view class="mode-toggle">
                {{ folkMode === 'reject' ? '排除' : '提示' }}
              </view>
            </view>

            <view class="advanced-row is-tappable" @click="setFlag('onlyHuangDao')">
              <view class="advanced-copy">
                <text class="advanced-title">仅看黄道</text>
                <text class="advanced-hint">缩小候选范围，不改变前置判断</text>
              </view>
              <view class="switch" :class="{ 'is-on': onlyHuangDao }">
                <view class="switch-knob" />
              </view>
            </view>

            <view class="advanced-row is-tappable" @click="setFlag('avoidXiuXiong')">
              <view class="advanced-copy">
                <text class="advanced-title">避开宿值不协</text>
                <text class="advanced-hint">只保留二十八宿状态为协和的日期</text>
              </view>
              <view class="switch" :class="{ 'is-on': avoidXiuXiong }">
                <view class="switch-knob" />
              </view>
            </view>
          </view>

          <button class="primary-action run-action" :disabled="running" @click="run">
            <text class="run-glyph serif">{{ running ? '演' : '排' }}</text>
            <text>{{ running ? '正在排布…' : result ? '重新排布' : '开始排布' }}</text>
            <text class="run-meta">{{ days }} 日 · {{ activeCategory.label }}</text>
          </button>
          <text class="privacy-note">全部规则在本机运算，档案与出生信息不上传云端。</text>
        </view>

        <view v-if="result" class="results">
          <view class="results-head">
            <view>
              <text class="section-no serif">04</text>
              <text class="results-title serif">候选日程</text>
              <text class="results-sub">
                {{ result.eligible }} 天通过当前条件
                <template v-if="result.truncated">，按日期展示前 {{ result.items.length }} 天</template>
              </text>
            </view>
            <view class="live-mark">
              <text class="live-dot" />
              <text>已排布</text>
            </view>
          </view>

          <view v-if="result.truncated" class="truncate-note">
            <text class="truncate-mark">＋</text>
            <text>候选池共 {{ result.eligible }} 天，当前仅展示 {{ result.items.length }} 天，未按「好坏」排序。</text>
          </view>

          <view v-if="result.rejections.length" class="paper-card rejection-card">
            <view class="rejection-head" @click="showAllRejections = !showAllRejections">
              <view>
                <text class="rejection-title serif">前置排除概览</text>
                <text class="rejection-sub">
                  {{ result.rejected }} 天因下列规则未进入候选；同一日可命中多项
                </text>
              </view>
              <text class="rejection-more">
                {{ showAllRejections ? '收起' : '全部' }}
                <text class="toggle-arrow" :class="{ 'is-open': showAllRejections }">⌄</text>
              </text>
            </view>
            <view class="rejection-list">
              <view
                v-for="item in result.rejections.slice(0, showAllRejections ? result.rejections.length : 5)"
                :key="item.name"
                class="rejection-row"
              >
                <view class="rejection-row-top">
                  <text class="rejection-name">{{ item.name }}</text>
                  <text class="rejection-count">{{ item.count }} 天</text>
                </view>
                <view class="rejection-track">
                  <view class="rejection-fill" :style="{ width: rejectionWidth(item.count) }" />
                </view>
                <view class="rejection-meta">
                  <text>{{ item.review ? '进阶设置可放宽' : '当前口径不可放宽' }}</text>
                  <text v-if="item.luckyStarDays" class="rejection-lucky">
                    其中 {{ item.luckyStarDays }} 天值三德
                  </text>
                </view>
              </view>
            </view>
          </view>

          <view v-if="!result.items.length" class="paper-card empty-result">
            <view class="empty-orbit is-small">
              <text class="empty-glyph serif">候</text>
            </view>
            <text class="empty-title serif">这一组条件下没有留下候选</text>
            <text class="empty-copy">
              可以先缩窄用事类别、调整起始日，或在进阶设置中把「命中即排除」改为「只作提示」。
            </text>
            <view class="empty-actions">
              <text class="ghost-link" @click="advancedOpen = true">展开进阶设置</text>
              <text class="ghost-link" @click="openReport">查看原档案</text>
            </view>
          </view>

          <view
            v-for="item in result.items"
            :key="item.solarDate"
            class="candidate-card"
            :class="{ 'is-open': expanded[item.solarDate] }"
          >
                  <text class="card-watermark serif">时</text>
            <view class="candidate-top">
              <view class="date-lockup">
                <text class="date-month">{{ Number(dateParts(item.solarDate).month) }}月</text>
                <text class="date-day serif">{{ dateParts(item.solarDate).day }}</text>
                <text class="date-year">{{ dateParts(item.solarDate).year }}</text>
              </view>
              <view class="date-copy">
                <view class="date-flags">
                  <text class="weekday">{{ item.weekDay }}</text>
                  <text v-if="item.huangDao" class="mini-badge is-gold">黄道</text>
                  <text v-if="item.levelName && item.levelName !== '等第未注'" class="mini-badge">{{ item.levelName }}</text>
                </view>
                <text class="lunar-line">{{ item.lunarDate }} · {{ item.ganZhi }}日</text>
                <text class="season-line">
                  {{ item.zhiXing }}日 · {{ item.xiu }}宿 · {{ item.tianShen }}值
                </text>
              </view>
              <view class="ganzhi-seal">
                <text>{{ item.ganZhi }}</text>
              </view>
            </view>

            <view class="candidate-body">
              <view class="match-line">
                <text class="match-label">通书并注</text>
                <text v-if="item.matchedYi.length" class="match-terms">
                  {{ item.matchedYi.join(' · ') }}
                </text>
                <text v-else class="match-terms is-muted">按附加条件纳入</text>
                <text class="match-more">词条匹配</text>
              </view>

              <view class="school-grid">
                <view
                  v-for="school in item.schools"
                  :key="school.school"
                  class="school-cell"
                  :class="schoolTone(school)"
                >
                  <text class="school-name">{{ school.schoolLabel }}</text>
                  <view class="school-state-line">
                    <text class="school-dot" />
                    <text class="school-state">{{ schoolState(school) }}</text>
                  </view>
                </view>
              </view>

              <view class="evidence-strip">
                <view class="evidence-item">
                  <text class="evidence-value serif">{{ evidenceOf(item).sources }}</text>
                  <text class="evidence-label">规则出处</text>
                </view>
                <view class="evidence-item">
                  <text class="evidence-value serif">{{ item.conflicts.length }}</text>
                  <text class="evidence-label">流派分歧</text>
                </view>
                <view class="evidence-item">
                  <text class="evidence-value serif">{{ evidenceOf(item).reviews }}</text>
                  <text class="evidence-label">待人工核</text>
                </view>
                <view class="evidence-item">
                  <text class="evidence-value serif is-warn">{{ evidenceOf(item).gaps }}</text>
                  <text class="evidence-label">数据缺口</text>
                </view>
                <view class="consensus-tag">
                  <text class="consensus-small">同向</text>
                  <text class="consensus-main">{{ favorableSchools(item) }}/5</text>
                </view>
              </view>

              <view class="candidate-foot">
                <view class="risk-summary">
                  <text>冲{{ item.chongShengXiao }}</text>
                  <text>煞{{ item.sha }}</text>
                  <text v-if="item.dashaWarnings.length">{{ item.dashaWarnings.length }} 项提示</text>
                </view>
                <view class="detail-trigger" @click="toggleDetail(item.solarDate)">
                  <text>{{ expanded[item.solarDate] ? '收起依据' : '查看依据' }}</text>
                  <text class="detail-arrow" :class="{ 'is-open': expanded[item.solarDate] }">↓</text>
                </view>
              </view>
            </view>

            <view v-if="expanded[item.solarDate]" class="candidate-detail">
              <view class="detail-block">
                <view class="detail-block-head">
                  <text class="detail-title serif">日历与通书</text>
                  <text class="detail-note">事实层</text>
                </view>
                <view class="facts-grid">
                  <view v-for="fact in factsOf(item)" :key="fact.label" class="fact-cell">
                    <text class="fact-label">{{ fact.label }}</text>
                    <text class="fact-value">{{ fact.value }}</text>
                  </view>
                </view>
                <view class="text-row">
                  <text class="text-row-label">通书并注</text>
                  <text class="text-row-value">{{ item.dayYi.join(' · ') || '无记录' }}</text>
                </view>
                <view class="text-row">
                  <text class="text-row-label">通书关系</text>
                  <text class="text-row-value">{{ behaviorLabel(item) }}</text>
                </view>
                <view class="text-row">
                  <text class="text-row-label">通书避项</text>
                  <text class="text-row-value">{{ item.dayJi.join(' · ') || '无记录' }}</text>
                </view>
                <view class="text-row">
                  <text class="text-row-label">贵人方位</text>
                  <text class="text-row-value">
                    喜 {{ item.positions.xi }} · 财 {{ item.positions.cai }} · 福 {{ item.positions.fu }} · 阳贵 {{ item.positions.yangGui }} · 阴贵 {{ item.positions.yinGui }}
                  </text>
                </view>
                <view v-if="item.luckyHours.length" class="text-row">
                  <text class="text-row-label">参考时辰</text>
                  <text class="text-row-value">{{ item.luckyHours.join(' · ') }}</text>
                </view>
              </view>

              <view class="detail-block">
                <view class="detail-block-head">
                  <text class="detail-title serif">五派依据</text>
                  <text class="detail-note">并列呈现 · 不合并为单一结论</text>
                </view>
                <view class="school-detail-list">
                  <view
                    v-for="school in item.schools"
                    :key="school.school"
                    class="school-detail"
                    :class="schoolTone(school)"
                  >
                    <view class="school-detail-head" @click="toggleSchool(item.solarDate, school.school)">
                      <view class="school-detail-name">
                        <text class="school-index">{{ school.schoolLabel.slice(0, 1) }}</text>
                        <view>
                          <text class="school-full-name">{{ school.schoolLabel }}</text>
                          <text class="school-verdict">{{ schoolState(school) }}</text>
                        </view>
                      </view>
                      <view class="school-detail-right">
                        <text class="school-score">规则计数 {{ school.scoreDelta > 0 ? '+' : '' }}{{ school.scoreDelta }}</text>
                        <text
                          class="school-chevron"
                          :class="{ 'is-open': openSchools[schoolKey(item.solarDate, school.school)] }"
                        >⌄</text>
                      </view>
                    </view>
                    <view v-if="openSchools[schoolKey(item.solarDate, school.school)]" class="school-detail-body">
                      <text v-if="school.partialReason" class="partial-reason">{{ school.partialReason }}</text>
                      <view
                        v-for="rule in school.subRules"
                        :key="rule.ruleId"
                        class="rule-row"
                      >
                        <view class="rule-row-head">
                          <text class="rule-name">{{ rule.name }}</text>
                          <text class="rule-delta" :class="{ 'is-negative': rule.scoreDelta < 0 }">
                            {{ rule.scoreDelta > 0 ? '+' : '' }}{{ rule.scoreDelta }}
                          </text>
                        </view>
                        <text v-if="rule.verdict" class="rule-verdict">{{ rule.verdict }}</text>
                        <text v-for="reason in rule.reasons" :key="reason" class="rule-reason">{{ reason }}</text>
                        <text v-if="rule.dataGap" class="rule-gap">缺口：{{ rule.dataGap }}</text>
                        <view class="rule-source">
                          <text>{{ rule.source.title }}<template v-if="rule.source.locus"> · {{ rule.source.locus }}</template></text>
                          <text class="rule-verify">{{ rule.verification === 'verified_by_human' ? '已人工核' : '待考证' }}</text>
                        </view>
                        <text v-if="rule.source.lineageNote" class="lineage-note">流派说明：{{ rule.source.lineageNote }}</text>
                      </view>
                      <view v-if="school.conflictFlags.length" class="conflict-box">
                        <text class="conflict-label">本派内部提示</text>
                        <text v-for="flag in school.conflictFlags" :key="flag" class="conflict-copy">{{ flag }}</text>
                      </view>
                    </view>
                  </view>
                </view>
              </view>

              <view v-if="item.conflicts.length" class="detail-block">
                <view class="detail-block-head">
                  <text class="detail-title serif">流派分歧</text>
                  <text class="detail-note">只标记，不裁定</text>
                </view>
                <view v-for="conflict in item.conflicts" :key="conflict.issue" class="conflict-line">
                  <text class="conflict-school">{{ conflictSchools(item, conflict) }}</text>
                  <text class="conflict-text">{{ conflict.issue }}</text>
                </view>
              </view>

              <view v-if="item.warnings.length || item.dashaWarnings.length" class="detail-block is-warm">
                <view class="detail-block-head">
                  <text class="detail-title serif">提示项</text>
                  <text class="detail-note">需结合现场与师承复核</text>
                </view>
                <text v-for="warning in item.warnings" :key="warning" class="warning-line">{{ warning }}</text>
                <text v-for="warning in item.dashaWarnings" :key="warning" class="warning-line">{{ warning }}</text>
              </view>

              <view class="detail-footer">
                <text>本页只呈现规则命中与出处，不构成单一结论。</text>
                <text class="link-text" @click="openReport">回到原档案</text>
              </view>
            </view>
          </view>

          <view class="paper-card notes-card">
            <view class="notes-head" @click="notesOpen = !notesOpen">
              <view>
                <text class="notes-title serif">口径与计算说明</text>
                <text class="notes-sub">完整时间窗统计 · 规则版本 · 数据缺口</text>
              </view>
              <text class="toggle-arrow" :class="{ 'is-open': notesOpen }">⌄</text>
            </view>
            <view v-if="notesOpen" class="notes-body">
              <text v-for="note in result.notes" :key="note" class="note-line">{{ note }}</text>
              <view class="data-gap-summary">
                <text>附加条件跳过：通书 {{ result.excludedByAlmanac }} 天 · 黄道 {{ result.excludedByHuangDao }} 天 · 宿吉 {{ result.excludedByXiu }} 天</text>
              </view>
            </view>
          </view>
        </view>
      </template>

      <view class="page-foot">
        <text class="foot-mark serif">居境</text>
        <text class="foot-copy">传统民俗规则演算，仅供人居环境记录与日程参考。不替代现场勘验与专业判断。</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.zeri-page {
  background:
    radial-gradient(ellipse at 100% 0%, rgba(160, 128, 72, 0.08), transparent 38%),
    var(--bg);
}

.zeri-shell {
  padding-bottom: 16rpx;
}

/* ── 天时主视觉 ─────────────────────────────────────────── */

.timing-hero {
  position: relative;
  overflow: hidden;
  min-height: 420rpx;
  padding: 42rpx 36rpx 0;
  border: 1rpx solid rgba(196, 164, 106, 0.34);
  border-radius: 30rpx;
  color: #f7f0df;
  background:
    radial-gradient(circle at 84% 18%, rgba(196, 164, 106, 0.26), transparent 34%),
    radial-gradient(circle at 8% 110%, rgba(45, 90, 74, 0.4), transparent 42%),
    linear-gradient(135deg, #1d2924 0%, #101714 56%, #221e17 100%);
  box-shadow: 0 20rpx 56rpx rgba(20, 26, 22, 0.24);
}

.hero-grain {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(rgba(255, 255, 255, 0.055) 0.7rpx, transparent 0.8rpx),
    radial-gradient(rgba(0, 0, 0, 0.16) 0.7rpx, transparent 0.8rpx);
  background-position: 0 0, 5rpx 7rpx;
  background-size: 10rpx 10rpx, 13rpx 13rpx;
  opacity: 0.42;
  pointer-events: none;
}

.hero-copy {
  position: relative;
  z-index: 2;
  width: 68%;
}

.hero-kicker {
  display: block;
  color: #c8ad78;
  font-size: 24rpx;
  letter-spacing: 0.16em;
}

.hero-title {
  display: block;
  margin-top: 14rpx;
  color: #fff8e8;
  font-size: 82rpx;
  line-height: 1.05;
  letter-spacing: 0.1em;
  text-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.24);
}

.hero-desc {
  display: block;
  margin-top: 18rpx;
  color: rgba(247, 240, 223, 0.7);
  font-size: 27rpx;
  line-height: 1.78;
  letter-spacing: 0.02em;
}

.orbit {
  position: absolute;
  z-index: 1;
  top: 34rpx;
  right: -82rpx;
  width: 292rpx;
  height: 292rpx;
  border: 1rpx solid rgba(196, 164, 106, 0.3);
  border-radius: 50%;
  box-shadow:
    inset 0 0 0 20rpx rgba(196, 164, 106, 0.025),
    0 0 70rpx rgba(196, 164, 106, 0.08);
}

.orbit::before,
.orbit::after {
  content: '';
  position: absolute;
  border-radius: 50%;
}

.orbit::before {
  inset: 30rpx;
  border: 1rpx solid rgba(196, 164, 106, 0.22);
}

.orbit::after {
  inset: 72rpx;
  border: 1rpx dashed rgba(196, 164, 106, 0.2);
}

.orbit-ring-inner {
  position: absolute;
  inset: 112rpx;
  border: 1rpx solid rgba(196, 164, 106, 0.22);
  border-radius: 50%;
}

.orbit-mark {
  position: absolute;
  left: 50%;
  top: 9rpx;
  width: 26rpx;
  height: 50%;
  margin-left: -13rpx;
  transform-origin: 50% 100%;
}

.orbit-char {
  display: block;
  width: 26rpx;
  color: rgba(226, 202, 153, 0.7);
  font-family: 'Songti SC', 'STSong', serif;
  font-size: 21rpx;
  line-height: 1;
  text-align: center;
}

.orbit-core {
  position: absolute;
  z-index: 2;
  left: 50%;
  top: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  width: 108rpx;
  height: 108rpx;
  border: 1rpx solid rgba(196, 164, 106, 0.5);
  border-radius: 50%;
  background: rgba(20, 27, 23, 0.9);
  transform: translate(-50%, -50%);
  box-shadow: 0 0 30rpx rgba(196, 164, 106, 0.12);
}

.core-glyph {
  color: #e7cd98;
  font-size: 36rpx;
  line-height: 1.1;
}

.core-label {
  margin-top: 4rpx;
  color: rgba(247, 240, 223, 0.56);
  font-size: 20rpx;
  letter-spacing: 0.06em;
}

.hero-readout {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: flex-end;
  margin: 34rpx -36rpx 0;
  padding: 26rpx 32rpx 28rpx;
  border-top: 1rpx solid rgba(196, 164, 106, 0.18);
  background: rgba(8, 12, 10, 0.22);
}

.readout-item {
  min-width: 112rpx;
}

.readout-value {
  display: block;
  color: #f5ebd6;
  font-size: 40rpx;
  line-height: 1.1;
}

.readout-value.is-gold {
  color: #d6b97c;
}

.readout-label {
  display: block;
  margin-top: 6rpx;
  color: rgba(247, 240, 223, 0.48);
  font-size: 22rpx;
  letter-spacing: 0.06em;
}

.readout-divider {
  width: 1rpx;
  height: 48rpx;
  margin: 0 20rpx 2rpx;
  background: rgba(196, 164, 106, 0.18);
}

.hero-range {
  display: flex;
  flex: 1;
  align-items: flex-end;
  flex-direction: column;
  gap: 4rpx;
  min-width: 0;
  color: rgba(247, 240, 223, 0.44);
  font-size: 21rpx;
  line-height: 1.5;
  text-align: right;
  white-space: nowrap;
}

/* ── 设置区 ─────────────────────────────────────────────── */

.paper-card {
  position: relative;
  margin-top: 24rpx;
  padding: 34rpx;
  border: 1rpx solid var(--line);
  border-radius: 26rpx;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}

.setup-card {
  overflow: hidden;
}

.setup-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 34rpx;
  width: 84rpx;
  height: 3rpx;
  background: linear-gradient(90deg, var(--gold), transparent);
}

.section-head {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
}

.section-head.is-compact {
  align-items: center;
}

.section-no {
  flex-shrink: 0;
  margin-top: 2rpx;
  color: var(--gold);
  font-size: 26rpx;
  line-height: 1.3;
  letter-spacing: 0.04em;
}

.section-copy {
  flex: 1;
  min-width: 0;
}

.section-title {
  display: block;
  color: var(--ink);
  font-size: 34rpx;
  line-height: 1.35;
  letter-spacing: 0.06em;
}

.section-sub {
  display: block;
  margin-top: 5rpx;
  color: var(--muted);
  font-size: 25rpx;
  line-height: 1.55;
}

.section-side {
  flex-shrink: 0;
  margin-top: 8rpx;
  padding: 5rpx 12rpx;
  border: 1rpx solid var(--line-gold);
  border-radius: 999rpx;
  color: var(--gold);
  font-size: 22rpx;
  letter-spacing: 0.06em;
}

.section-rule {
  height: 1rpx;
  margin: 30rpx 0 28rpx;
  background: linear-gradient(90deg, var(--line-gold), var(--line), transparent);
}

.archive-select {
  display: flex;
  align-items: center;
  gap: 18rpx;
  margin-top: 26rpx;
  padding: 22rpx 20rpx;
  border: 1rpx solid var(--line-gold);
  border-radius: 18rpx;
  background:
    linear-gradient(112deg, rgba(160, 128, 72, 0.07), transparent 46%),
    var(--surface-warm);
}

.archive-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 74rpx;
  height: 74rpx;
  border: 1rpx solid rgba(160, 128, 72, 0.42);
  border-radius: 50%;
  color: var(--accent);
  font-size: 30rpx;
  background: rgba(253, 250, 244, 0.78);
}

.archive-copy {
  flex: 1;
  min-width: 0;
}

.field-label {
  display: block;
  color: var(--muted);
  font-size: 23rpx;
  line-height: 1.4;
  letter-spacing: 0.08em;
}

.archive-name {
  display: block;
  overflow: hidden;
  margin-top: 2rpx;
  color: var(--ink);
  font-size: 29rpx;
  font-weight: 600;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.archive-meta {
  display: block;
  overflow: hidden;
  margin-top: 2rpx;
  color: var(--ink-3);
  font-size: 24rpx;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.select-arrow {
  flex-shrink: 0;
  color: var(--gold);
  font-size: 30rpx;
}

.field-group {
  margin-top: 30rpx;
}

.field-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12rpx;
}

.field-hint {
  color: var(--muted);
  font-size: 23rpx;
  line-height: 1.5;
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12rpx;
  margin-top: 15rpx;
}

.category-tile {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10rpx;
  overflow: hidden;
  min-height: 92rpx;
  padding: 14rpx 12rpx;
  border: 1rpx solid var(--line);
  border-radius: 16rpx;
  background: var(--surface-warm);
  transition: border-color 0.2s ease, background 0.2s ease;
}

.category-tile.is-active {
  border-color: rgba(176, 58, 46, 0.3);
  background:
    linear-gradient(135deg, rgba(176, 58, 46, 0.08), transparent 70%),
    var(--surface);
}

.category-glyph {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 38rpx;
  height: 52rpx;
  border-radius: 4rpx;
  color: var(--ink-3);
  font-size: 25rpx;
  line-height: 1;
}

.category-tile.is-active .category-glyph {
  color: var(--accent);
  background: var(--accent-soft);
}

.category-copy {
  min-width: 0;
}

.category-name {
  display: block;
  color: var(--ink-2);
  font-size: 26rpx;
  line-height: 1.4;
  white-space: nowrap;
}

.category-tile.is-active .category-name {
  color: var(--accent-deep);
  font-weight: 600;
}

.category-hint {
  display: block;
  overflow: hidden;
  margin-top: 1rpx;
  color: var(--muted);
  font-size: 21rpx;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.category-corner {
  position: absolute;
  right: -12rpx;
  bottom: -12rpx;
  width: 34rpx;
  height: 34rpx;
  border: 1rpx solid transparent;
  border-radius: 50%;
}

.category-tile.is-active .category-corner {
  border-color: rgba(176, 58, 46, 0.18);
}

.range-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr);
  gap: 14rpx;
  margin-top: 22rpx;
}

.date-field,
.duration-field {
  padding: 18rpx 18rpx 16rpx;
  border: 1rpx solid var(--line);
  border-radius: 16rpx;
  background: var(--surface-warm);
}

.date-value {
  display: block;
  margin-top: 5rpx;
  color: var(--ink);
  font-size: 28rpx;
  line-height: 1.4;
  letter-spacing: 0.03em;
}

.duration-field .segment {
  margin-top: 8rpx;
}

.segment {
  display: flex;
  padding: 4rpx;
  border-radius: 12rpx;
  background: rgba(28, 26, 23, 0.045);
}

.segment-item {
  flex: 1;
  padding: 8rpx 2rpx;
  border-radius: 9rpx;
  color: var(--muted);
  font-size: 23rpx;
  line-height: 1.4;
  text-align: center;
  transition: color 0.2s ease, background 0.2s ease;
}

.segment-item.is-active {
  color: var(--accent-deep);
  font-weight: 600;
  background: var(--surface);
  box-shadow: 0 2rpx 8rpx rgba(28, 26, 23, 0.06);
}

.advanced-toggle {
  display: flex;
  align-items: center;
  gap: 7rpx;
  flex-shrink: 0;
  min-height: 68rpx;
  padding: 8rpx 12rpx;
  border: 1rpx solid var(--line);
  border-radius: 999rpx;
  color: var(--ink-3);
  font-size: 24rpx;
}

.toggle-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28rpx;
  height: 28rpx;
  padding: 0 6rpx;
  border-radius: 999rpx;
  color: #fff8ee;
  font-size: 20rpx;
  line-height: 1;
  background: var(--accent);
}

.toggle-arrow {
  display: inline-block;
  color: var(--gold);
  font-size: 26rpx;
  line-height: 1;
  transition: transform 0.22s ease;
}

.toggle-arrow.is-open,
.detail-arrow.is-open {
  transform: rotate(180deg);
}

.default-rules {
  display: flex;
  gap: 8rpx;
  margin-top: 18rpx;
}

.rule-pill {
  display: flex;
  align-items: center;
  gap: 7rpx;
  flex: 1;
  padding: 10rpx 8rpx;
  border-radius: 10rpx;
  color: var(--ink-3);
  font-size: 22rpx;
  line-height: 1.4;
  background: rgba(28, 26, 23, 0.035);
}

.rule-dot {
  width: 7rpx;
  height: 7rpx;
  border-radius: 50%;
  background: var(--gold);
}

.rule-dot.is-red {
  background: var(--accent);
}

.rule-dot.is-jade {
  background: var(--jade);
}

.advanced-panel {
  overflow: hidden;
  margin-top: 18rpx;
  border: 1rpx solid var(--line);
  border-radius: 18rpx;
  background: var(--surface-warm);
}

.advanced-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
  min-height: 96rpx;
  padding: 18rpx 20rpx;
  border-bottom: 1rpx solid var(--line);
  transition: background 0.18s ease;
}

.advanced-row.is-tappable:active {
  background: rgba(160, 128, 72, 0.08);
}

.advanced-row:last-child {
  border-bottom: none;
}

.advanced-row.is-stacked {
  align-items: flex-start;
  flex-direction: column;
  gap: 12rpx;
}

.advanced-copy {
  flex: 1;
  min-width: 0;
}

.advanced-title {
  display: block;
  color: var(--ink-2);
  font-size: 27rpx;
  line-height: 1.45;
}

.advanced-hint {
  display: block;
  margin-top: 2rpx;
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.4;
}

.mini-select {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 10rpx 14rpx;
  border: 1rpx solid var(--line-gold);
  border-radius: 10rpx;
  color: var(--ink-2);
  font-size: 24rpx;
  background: var(--surface);
}

.mini-select-arrow {
  color: var(--gold);
}

.mini-segment {
  display: flex;
  padding: 3rpx;
  border-radius: 10rpx;
  background: rgba(28, 26, 23, 0.055);
}

.mini-segment.is-wide {
  width: 100%;
}

.mini-item {
  min-width: 44rpx;
  padding: 7rpx 10rpx;
  border-radius: 8rpx;
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.4;
  text-align: center;
}

.mini-segment.is-wide .mini-item {
  flex: 1;
}

.mini-item.is-active {
  color: var(--accent-deep);
  background: var(--surface);
  box-shadow: 0 2rpx 6rpx rgba(28, 26, 23, 0.06);
}

.switch {
  position: relative;
  flex-shrink: 0;
  width: 76rpx;
  height: 42rpx;
  border-radius: 999rpx;
  background: rgba(28, 26, 23, 0.12);
  transition: background 0.2s ease;
}

.switch.is-on {
  background: var(--jade);
}

.switch-knob {
  position: absolute;
  top: 4rpx;
  left: 4rpx;
  width: 34rpx;
  height: 34rpx;
  border-radius: 50%;
  background: #fffdf7;
  box-shadow: 0 2rpx 6rpx rgba(28, 26, 23, 0.18);
  transition: transform 0.2s ease;
}

.switch.is-on .switch-knob {
  transform: translateX(34rpx);
}

.mode-toggle {
  flex-shrink: 0;
  min-width: 76rpx;
  padding: 9rpx 16rpx;
  border: 1rpx solid rgba(176, 58, 46, 0.22);
  border-radius: 999rpx;
  color: var(--accent-deep);
  font-size: 23rpx;
  line-height: 1.4;
  text-align: center;
  background: var(--accent-faint);
}

.primary-action {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14rpx;
  width: 100%;
  height: 96rpx;
  margin-top: 28rpx;
  padding: 0 24rpx;
  border: none;
  border-radius: 16rpx;
  color: #fff9ed;
  font-size: 27rpx;
  letter-spacing: 0.08em;
  background: linear-gradient(112deg, var(--accent-deep), var(--accent));
  box-shadow: 0 10rpx 24rpx rgba(142, 43, 32, 0.18);
}

.primary-action::after {
  border: none;
}

.primary-action[disabled] {
  opacity: 0.64;
}

.run-glyph {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44rpx;
  height: 44rpx;
  border: 1rpx solid rgba(255, 249, 237, 0.42);
  border-radius: 50%;
  font-size: 27rpx;
  line-height: 1;
}

.run-meta {
  position: absolute;
  right: 30rpx;
  color: rgba(255, 249, 237, 0.54);
  font-size: 21rpx;
  letter-spacing: 0.02em;
}

.privacy-note {
  display: block;
  margin-top: 13rpx;
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.5;
  text-align: center;
}

/* ── 结果与日期卡 ─────────────────────────────────────────── */

.results {
  margin-top: 44rpx;
}

.results-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 18rpx;
}

.results-title {
  display: inline;
  margin-left: 12rpx;
  color: var(--ink);
  font-size: 38rpx;
  letter-spacing: 0.06em;
}

.results-sub {
  display: block;
  margin-top: 5rpx;
  color: var(--muted);
  font-size: 24rpx;
  line-height: 1.5;
}

.live-mark {
  display: flex;
  align-items: center;
  gap: 7rpx;
  flex-shrink: 0;
  color: var(--jade);
  font-size: 22rpx;
}

.live-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  background: var(--jade);
  box-shadow: 0 0 0 5rpx rgba(45, 90, 74, 0.08);
}

.truncate-note {
  display: flex;
  align-items: flex-start;
  gap: 10rpx;
  margin-bottom: 16rpx;
  padding: 14rpx 16rpx;
  border: 1rpx solid rgba(160, 128, 72, 0.18);
  border-radius: 12rpx;
  color: var(--ink-3);
  font-size: 23rpx;
  line-height: 1.55;
  background: rgba(160, 128, 72, 0.06);
}

.truncate-mark {
  flex-shrink: 0;
  color: var(--gold);
  font-size: 26rpx;
  line-height: 1.3;
}

.rejection-card {
  margin-top: 0;
  padding: 26rpx 28rpx;
}

.rejection-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16rpx;
}

.rejection-title {
  display: block;
  color: var(--ink);
  font-size: 29rpx;
  letter-spacing: 0.05em;
}

.rejection-sub {
  display: block;
  margin-top: 4rpx;
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.5;
}

.rejection-more {
  flex-shrink: 0;
  color: var(--gold);
  font-size: 23rpx;
  line-height: 1.5;
}

.rejection-list {
  margin-top: 18rpx;
}

.rejection-row {
  margin-top: 16rpx;
}

.rejection-row-top {
  display: flex;
  justify-content: space-between;
  gap: 10rpx;
  color: var(--ink-3);
  font-size: 24rpx;
  line-height: 1.45;
}

.rejection-count {
  flex-shrink: 0;
  color: var(--accent-deep);
  font-variant-numeric: tabular-nums;
}

.rejection-track {
  overflow: hidden;
  height: 6rpx;
  margin-top: 7rpx;
  border-radius: 999rpx;
  background: rgba(28, 26, 23, 0.06);
}

.rejection-fill {
  height: 100%;
  border-radius: 999rpx;
  background: linear-gradient(90deg, rgba(176, 58, 46, 0.45), rgba(160, 128, 72, 0.6));
}

.rejection-meta {
  display: flex;
  justify-content: space-between;
  gap: 10rpx;
  margin-top: 4rpx;
  color: var(--muted);
  font-size: 21rpx;
  line-height: 1.45;
}

.rejection-lucky {
  color: var(--gold);
}

.candidate-card {
  position: relative;
  overflow: hidden;
  margin-top: 18rpx;
  border: 1rpx solid var(--line);
  border-radius: 24rpx;
  background:
    linear-gradient(120deg, rgba(160, 128, 72, 0.04), transparent 35%),
    var(--surface);
  box-shadow: var(--shadow-card);
}

.candidate-card::before {
  content: '';
  position: absolute;
  z-index: 1;
  top: 0;
  left: 28rpx;
  width: 58rpx;
  height: 3rpx;
  background: linear-gradient(90deg, var(--gold), transparent);
}

.candidate-card.is-open {
  border-color: var(--line-gold);
}

.card-watermark {
  position: absolute;
  top: 40rpx;
  right: 22rpx;
  color: rgba(160, 128, 72, 0.055);
  font-size: 150rpx;
  line-height: 0.8;
  pointer-events: none;
}

.candidate-top {
  display: flex;
  align-items: flex-start;
  gap: 20rpx;
  padding: 28rpx 28rpx 22rpx;
}

.date-lockup {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  width: 94rpx;
  padding-right: 16rpx;
  border-right: 1rpx solid var(--line);
}

.date-month {
  color: var(--gold);
  font-size: 22rpx;
  line-height: 1.3;
  letter-spacing: 0.08em;
}

.date-day {
  color: var(--ink);
  font-size: 56rpx;
  line-height: 1.02;
  letter-spacing: 0.02em;
}

.date-year {
  margin-top: 2rpx;
  color: var(--muted);
  font-size: 20rpx;
  line-height: 1.3;
  letter-spacing: 0.04em;
}

.date-copy {
  flex: 1;
  min-width: 0;
  padding-top: 2rpx;
}

.date-flags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7rpx;
}

.weekday {
  color: var(--ink);
  font-size: 27rpx;
  font-weight: 600;
  line-height: 1.4;
}

.mini-badge {
  padding: 3rpx 8rpx;
  border: 1rpx solid var(--line);
  border-radius: 5rpx;
  color: var(--ink-3);
  font-size: 20rpx;
  line-height: 1.35;
  background: rgba(28, 26, 23, 0.025);
}

.mini-badge.is-gold {
  border-color: rgba(160, 128, 72, 0.25);
  color: var(--gold);
  background: var(--gold-soft);
}

.lunar-line {
  display: block;
  margin-top: 8rpx;
  color: var(--ink-2);
  font-size: 26rpx;
  line-height: 1.5;
}

.season-line {
  display: block;
  margin-top: 3rpx;
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.5;
}

.ganzhi-seal {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 54rpx;
  height: 54rpx;
  margin-top: 2rpx;
  border: 1rpx solid rgba(176, 58, 46, 0.32);
  border-radius: 5rpx;
  color: var(--accent);
  font-family: 'Songti SC', 'STSong', serif;
  font-size: 22rpx;
  line-height: 1.2;
  text-align: center;
  padding: 5rpx 6rpx;
  background: rgba(176, 58, 46, 0.04);
}

.candidate-body {
  padding: 0 28rpx 22rpx;
}

.match-line {
  display: flex;
  align-items: center;
  gap: 9rpx;
  overflow: hidden;
  padding: 12rpx 0;
  border-top: 1rpx solid var(--line);
  border-bottom: 1rpx solid var(--line);
}

.match-label {
  flex-shrink: 0;
  color: var(--gold);
  font-size: 21rpx;
  letter-spacing: 0.04em;
}

.match-terms {
  flex: 1;
  overflow: hidden;
  color: var(--ink-2);
  font-size: 23rpx;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.match-terms.is-muted {
  color: var(--muted);
}

.match-more {
  flex-shrink: 0;
  color: var(--muted);
  font-size: 20rpx;
  line-height: 1.4;
}

.school-grid {
  display: flex;
  gap: 6rpx;
  margin-top: 14rpx;
}

.school-cell {
  flex: 1;
  min-width: 0;
  padding: 9rpx 4rpx 8rpx;
  border: 1rpx solid var(--line);
  border-radius: 8rpx;
  text-align: center;
  background: rgba(28, 26, 23, 0.018);
}

.school-cell.is-favorable {
  border-color: rgba(45, 90, 74, 0.16);
  background: rgba(45, 90, 74, 0.045);
}

.school-cell.is-cautious {
  border-color: rgba(160, 128, 72, 0.18);
  background: rgba(160, 128, 72, 0.045);
}

.school-cell.is-partial {
  opacity: 0.66;
}

.school-name {
  display: block;
  overflow: hidden;
  color: var(--ink-3);
  font-size: 21rpx;
  line-height: 1.35;
  white-space: nowrap;
}

.school-state-line {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4rpx;
  margin-top: 3rpx;
}

.school-dot {
  width: 5rpx;
  height: 5rpx;
  border-radius: 50%;
  background: var(--muted);
}

.is-favorable .school-dot {
  background: var(--jade);
}

.is-cautious .school-dot {
  background: var(--gold);
}

.school-state {
  color: var(--muted);
  font-size: 20rpx;
  line-height: 1.3;
}

.is-favorable .school-state {
  color: var(--jade);
}

.is-cautious .school-state {
  color: var(--gold);
}

.evidence-strip {
  display: flex;
  align-items: center;
  margin-top: 16rpx;
  padding: 12rpx 14rpx;
  border-radius: 10rpx;
  background: rgba(28, 26, 23, 0.032);
}

.evidence-item {
  flex: 1;
  min-width: 0;
  text-align: center;
}

.evidence-value {
  display: block;
  color: var(--ink-2);
  font-size: 26rpx;
  line-height: 1.1;
}

.evidence-value.is-warn {
  color: var(--gold);
}

.evidence-label {
  display: block;
  margin-top: 2rpx;
  color: var(--muted);
  font-size: 19rpx;
  line-height: 1.3;
  white-space: nowrap;
}

.consensus-tag {
  display: flex;
  align-items: baseline;
  flex-shrink: 0;
  gap: 3rpx;
  padding-left: 12rpx;
  border-left: 1rpx solid var(--line);
}

.consensus-small {
  color: var(--muted);
  font-size: 19rpx;
}

.consensus-main {
  color: var(--jade);
  font-family: 'Songti SC', 'STSong', serif;
  font-size: 28rpx;
}

.candidate-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14rpx;
  margin-top: 15rpx;
}

.risk-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  color: var(--muted);
  font-size: 21rpx;
  line-height: 1.45;
}

.detail-trigger {
  display: flex;
  align-items: center;
  gap: 7rpx;
  flex-shrink: 0;
  min-height: 54rpx;
  padding: 0 4rpx;
  color: var(--accent-deep);
  font-size: 24rpx;
}

.detail-arrow {
  color: var(--gold);
  font-size: 23rpx;
  transition: transform 0.22s ease;
}

/* ── 展开依据 ───────────────────────────────────────────── */

.candidate-detail {
  border-top: 1rpx solid var(--line-gold);
  background: rgba(240, 234, 220, 0.34);
}

.detail-block {
  padding: 26rpx 28rpx;
  border-bottom: 1rpx solid var(--line);
}

.detail-block:last-child {
  border-bottom: none;
}

.detail-block.is-warm {
  background: rgba(160, 128, 72, 0.045);
}

.detail-block-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12rpx;
  margin-bottom: 16rpx;
}

.detail-title {
  color: var(--ink);
  font-size: 27rpx;
  letter-spacing: 0.05em;
}

.detail-note {
  color: var(--muted);
  font-size: 20rpx;
  line-height: 1.4;
  text-align: right;
}

.facts-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8rpx;
}

.fact-cell {
  min-width: 0;
  padding: 10rpx 10rpx 9rpx;
  border: 1rpx solid var(--line);
  border-radius: 8rpx;
  background: rgba(253, 250, 244, 0.7);
}

.fact-label {
  display: block;
  color: var(--muted);
  font-size: 19rpx;
  line-height: 1.35;
}

.fact-value {
  display: block;
  overflow: hidden;
  margin-top: 2rpx;
  color: var(--ink-2);
  font-size: 22rpx;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text-row {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  margin-top: 12rpx;
}

.text-row-label {
  flex-shrink: 0;
  width: 92rpx;
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.6;
}

.text-row-value {
  flex: 1;
  color: var(--ink-2);
  font-size: 23rpx;
  line-height: 1.65;
}

.school-detail-list {
  overflow: hidden;
  border: 1rpx solid var(--line);
  border-radius: 14rpx;
  background: rgba(253, 250, 244, 0.68);
}

.school-detail {
  border-bottom: 1rpx solid var(--line);
}

.school-detail:last-child {
  border-bottom: none;
}

.school-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  min-height: 92rpx;
  padding: 14rpx 16rpx;
}

.school-detail-name {
  display: flex;
  align-items: center;
  gap: 11rpx;
  min-width: 0;
}

.school-index {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 38rpx;
  height: 38rpx;
  border: 1rpx solid var(--line-gold);
  border-radius: 50%;
  color: var(--gold);
  font-family: 'Songti SC', 'STSong', serif;
  font-size: 23rpx;
  line-height: 1;
}

.school-full-name {
  display: block;
  color: var(--ink-2);
  font-size: 25rpx;
  line-height: 1.35;
}

.school-verdict {
  display: block;
  margin-top: 1rpx;
  color: var(--muted);
  font-size: 20rpx;
  line-height: 1.35;
}

.is-favorable .school-verdict {
  color: var(--jade);
}

.is-cautious .school-verdict {
  color: var(--gold);
}

.school-detail-right {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex-shrink: 0;
}

.school-score {
  color: var(--muted);
  font-size: 19rpx;
}

.school-chevron {
  color: var(--gold);
  font-size: 25rpx;
  transition: transform 0.2s ease;
}

.school-chevron.is-open {
  transform: rotate(180deg);
}

.school-detail-body {
  padding: 0 16rpx 16rpx;
}

.partial-reason {
  display: block;
  margin-bottom: 10rpx;
  padding: 9rpx 11rpx;
  border-radius: 7rpx;
  color: var(--gold);
  font-size: 21rpx;
  line-height: 1.55;
  background: var(--gold-soft);
}

.rule-row {
  padding: 13rpx 0;
  border-top: 1rpx solid var(--line);
}

.rule-row-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10rpx;
}

.rule-name {
  color: var(--ink-2);
  font-size: 24rpx;
  line-height: 1.45;
}

.rule-delta {
  flex-shrink: 0;
  color: var(--jade);
  font-family: Georgia, serif;
  font-size: 22rpx;
  line-height: 1.4;
}

.rule-delta.is-negative {
  color: var(--accent);
}

.rule-verdict {
  display: inline-block;
  margin-top: 3rpx;
  padding: 2rpx 7rpx;
  border-radius: 4rpx;
  color: var(--ink-3);
  font-size: 19rpx;
  line-height: 1.4;
  background: rgba(28, 26, 23, 0.045);
}

.rule-reason {
  display: block;
  margin-top: 4rpx;
  color: var(--ink-3);
  font-size: 21rpx;
  line-height: 1.65;
}

.rule-gap {
  display: block;
  margin-top: 5rpx;
  color: var(--gold);
  font-size: 20rpx;
  line-height: 1.55;
}

.rule-source {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12rpx;
  margin-top: 7rpx;
  color: var(--muted);
  font-size: 18rpx;
  line-height: 1.45;
}

.rule-verify {
  flex-shrink: 0;
  color: var(--gold);
}

.lineage-note {
  display: block;
  margin-top: 5rpx;
  color: var(--muted);
  font-size: 19rpx;
  line-height: 1.55;
}

.conflict-box {
  margin-top: 8rpx;
  padding: 10rpx 12rpx;
  border-left: 2rpx solid var(--gold);
  border-radius: 0 6rpx 6rpx 0;
  background: var(--gold-soft);
}

.conflict-label {
  display: block;
  color: var(--gold);
  font-size: 20rpx;
}

.conflict-copy {
  display: block;
  margin-top: 2rpx;
  color: var(--ink-3);
  font-size: 21rpx;
  line-height: 1.55;
}

.conflict-line {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  margin-top: 9rpx;
}

.conflict-school {
  flex-shrink: 0;
  padding: 2rpx 7rpx;
  border-radius: 4rpx;
  color: var(--accent-deep);
  font-size: 19rpx;
  line-height: 1.4;
  background: var(--accent-faint);
}

.conflict-text {
  flex: 1;
  color: var(--ink-3);
  font-size: 22rpx;
  line-height: 1.6;
}

.warning-line {
  display: block;
  margin-top: 5rpx;
  color: var(--ink-3);
  font-size: 21rpx;
  line-height: 1.6;
}

.detail-footer {
  display: flex;
  justify-content: space-between;
  gap: 14rpx;
  padding: 17rpx 28rpx;
  color: var(--muted);
  font-size: 19rpx;
  line-height: 1.5;
}

.link-text {
  flex-shrink: 0;
  color: var(--accent-deep);
}

/* ── 空态与说明 ───────────────────────────────────────────── */

.empty-card,
.empty-result {
  display: flex;
  align-items: center;
  flex-direction: column;
  padding: 48rpx 42rpx 42rpx;
  text-align: center;
}

.empty-orbit {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 128rpx;
  height: 128rpx;
  border: 1rpx solid var(--line-gold);
  border-radius: 50%;
  background: radial-gradient(circle, var(--surface) 0 32%, transparent 33%);
  box-shadow: 0 0 0 16rpx rgba(160, 128, 72, 0.04);
}

.empty-orbit.is-small {
  width: 96rpx;
  height: 96rpx;
}

.empty-glyph {
  color: var(--gold);
  font-size: 38rpx;
}

.empty-orbit.is-small .empty-glyph {
  font-size: 30rpx;
}

.empty-title {
  display: block;
  margin-top: 25rpx;
  color: var(--ink);
  font-size: 34rpx;
  letter-spacing: 0.05em;
}

.empty-copy {
  display: block;
  max-width: 520rpx;
  margin-top: 9rpx;
  color: var(--ink-3);
  font-size: 25rpx;
  line-height: 1.7;
}

.empty-card .primary-action {
  max-width: 360rpx;
  margin-top: 24rpx;
}

.empty-result {
  margin-top: 18rpx;
}

.empty-actions {
  display: flex;
  gap: 30rpx;
  margin-top: 20rpx;
}

.ghost-link {
  color: var(--accent-deep);
  font-size: 24rpx;
  line-height: 1.5;
}

.notes-card {
  padding: 25rpx 28rpx;
}

.notes-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14rpx;
}

.notes-title {
  display: block;
  color: var(--ink);
  font-size: 27rpx;
  letter-spacing: 0.04em;
}

.notes-sub {
  display: block;
  margin-top: 3rpx;
  color: var(--muted);
  font-size: 21rpx;
  line-height: 1.45;
}

.notes-body {
  margin-top: 16rpx;
  padding-top: 14rpx;
  border-top: 1rpx solid var(--line);
}

.note-line {
  display: block;
  margin-top: 7rpx;
  color: var(--ink-3);
  font-size: 22rpx;
  line-height: 1.7;
}

.data-gap-summary {
  margin-top: 12rpx;
  padding: 10rpx 12rpx;
  border-radius: 7rpx;
  color: var(--gold);
  font-size: 21rpx;
  line-height: 1.55;
  background: var(--gold-soft);
}

.page-foot {
  display: flex;
  align-items: flex-start;
  gap: 13rpx;
  margin-top: 34rpx;
  padding: 24rpx 4rpx 10rpx;
  border-top: 1rpx solid var(--line);
}

.foot-mark {
  flex-shrink: 0;
  color: var(--gold);
  font-size: 28rpx;
  letter-spacing: 0.1em;
}

.foot-copy {
  color: var(--muted);
  font-size: 21rpx;
  line-height: 1.65;
}

@media (max-width: 360px) {
  .hero-copy {
    width: 72%;
  }

  .orbit {
    right: -116rpx;
    opacity: 0.78;
  }

  .hero-desc {
    font-size: 25rpx;
  }

  .category-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .range-grid {
    grid-template-columns: 1fr;
  }

  .default-rules {
    flex-wrap: wrap;
  }

  .rule-pill {
    flex: 0 0 calc(50% - 4rpx);
  }

  .hero-range {
    display: none;
  }
}
</style>
