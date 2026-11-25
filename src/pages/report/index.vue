<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import AppHeader from '@/components/AppHeader.vue'
import PalaceGrid from '@/components/PalaceGrid.vue'
import type { Archive, PalaceId, PalaceInsight, Report } from '@/core/types'
import { PALACES, STARS } from '@/core/constants/luoshu'
import { BEHAVIOR_LABELS } from '@/core/constants/xieji'
import { relationText } from '@/core/engines/xianming'
import {
  buildReport,
  reportModeLabel,
  verdictLabel,
} from '@/core/engines/report'
import { useArchiveStore } from '@/stores/archive'
import { useAppStore } from '@/stores/app'
import { trackEvent, checkEntitlement } from '@/services/cloud'
import { purchaseReport, waitForEntitlement } from '@/services/purchase'
import {
  formatTimestamp,
  modeLabel,
  riskLabel,
  sittingFacingText,
  verdictTone,
} from '@/utils/display'

type TabKey = 'overview' | 'palaces' | 'insights' | 'bazhai' | 'xianming' | 'zeri'

const archiveStore = useArchiveStore()
const appStore = useAppStore()

const id = ref('')
const archive = ref<Archive | null>(null)
const report = ref<Report | null>(null)
const selectedPalace = ref<PalaceId | null>(null)
const activeTab = ref<TabKey>('overview')
const unlocked = ref(false)
const purchasing = ref(false)
const loading = ref(true)

let h5DevPreview = false
let isH5 = false
// #ifdef H5
h5DevPreview = import.meta.env.DEV
isH5 = true
// #endif

const tabs = computed<Array<{ key: TabKey; label: string }>>(() => {
  const list: Array<{ key: TabKey; label: string }> = [
    { key: 'overview', label: '总览' },
    { key: 'palaces', label: '九宫' },
    { key: 'insights', label: '分析' },
  ]
  if (archive.value?.mode === 'YIN') list.push({ key: 'xianming', label: '仙命' })
  else list.push({ key: 'bazhai', label: '八宅' })
  list.push({ key: 'zeri', label: '择日' })
  return list
})

const pair = computed(() =>
  archive.value ? sittingFacingText(archive.value.reading.facingDeg) : null
)
const selectedCell = computed(() =>
  report.value?.chart.palaces.find((item) => item.palace === selectedPalace.value) ?? null
)
const selectedInsight = computed(() =>
  report.value?.insights.find((item) => item.palace === selectedPalace.value) ?? null
)
const selectedMeta = computed(() =>
  selectedPalace.value ? PALACES[selectedPalace.value] : null
)
const patternName = computed(() => report.value?.chart.patternLabel ?? '')
const jianKindLabel = computed(() => {
  const chart = report.value?.chart
  if (!chart) return ''
  if (!chart.isJianXiang) return '下卦'
  return chart.tiGuaUsed ? (chart.jianKind === 'CHU_GUA' ? '出卦·替卦' : '替卦') : '兼而不上替'
})
const hasFullContent = computed(() => Boolean(appStore.content) || !unlocked.value)
const unlockLabel = computed(() =>
  h5DevPreview ? '本地预览解锁' : '¥9.90 解锁本份'
)

const propertyLabels: Record<string, string> = {
  RESIDENTIAL: '住宅',
  OFFICE: '办公',
  SHOP: '商铺',
}
const monumentLabels: Record<string, string> = {
  SINGLE: '单人纪念位',
  COUPLE: '双人合葬位',
  ANCESTRAL: '家族纪念地',
}
const terrainLabels: Record<string, Record<string, string>> = {
  backSupport: { STRONG: '后有依托', FLAT: '后方平坦', HOLLOW: '后方低洼空缺' },
  frontView: { OPEN: '前方开阔', BLOCKED: '前方遮挡', TILTED: '前方倾斜' },
  leftRight: { BALANCED: '左右均衡', LEFT_MISS: '左侧低矮', RIGHT_MISS: '右侧低矮' },
}

onLoad((query) => {
  id.value = String(query?.id ?? '')
  if (!id.value) id.value = archiveStore.currentId
})

onShow(() => {
  void refresh()
})

async function refresh() {
  loading.value = true
  const found =
    archiveStore.getById(id.value) ||
    (archiveStore.currentId ? archiveStore.getById(archiveStore.currentId) : undefined)
  if (!found) {
    archive.value = null
    report.value = null
    loading.value = false
    return
  }
  archive.value = found
  id.value = found.id
  archiveStore.setCurrent(found.id)
  unlocked.value = appStore.isUnlocked(found.id)
  if (!unlocked.value) {
    // #ifdef MP-WEIXIN
    if (await checkEntitlement(found.id)) {
      appStore.grantEntitlement(found.id)
      unlocked.value = true
    }
    // #endif
  }
  if (unlocked.value && !appStore.content) {
    await appStore.loadContent(found.id)
  }
  report.value = buildReport(found, {
    contents: appStore.content,
    unlocked: unlocked.value,
  })
  if (!selectedPalace.value) {
    selectedPalace.value = report.value.chart.facing.gong
  }
  loading.value = false
}

function selectPalace(palace: PalaceId) {
  selectedPalace.value = palace
}

function openInsight(insight: PalaceInsight) {
  if (insight.locked) return
  selectedPalace.value = insight.palace
  activeTab.value = 'palaces'
}

function starName(num: number) {
  return STARS[num]?.name ?? String(num)
}

function starTheme(num: number) {
  return STARS[num]?.theme ?? ''
}

function warningClass(level: string) {
  if (level === 'DANGER') return 'danger'
  if (level === 'CAUTION') return 'caution'
  return 'info'
}

function warningLabel(level: string) {
  if (level === 'DANGER') return '需回避'
  if (level === 'CAUTION') return '需留意'
  return '提示'
}

function goBack() {
  uni.navigateBack({
    fail: () => uni.switchTab({ url: '/pages/archive/index' }),
  })
}

function openZeri() {
  if (!archive.value) return
  uni.navigateTo({ url: `/pages/zeri/index?id=${archive.value.id}` })
}

function openPoster() {
  if (!archive.value) return
  uni.navigateTo({ url: `/pages/poster/index?id=${archive.value.id}` })
}

function openGuide() {
  uni.navigateTo({ url: '/pages/guide/index' })
}

function openCompass() {
  if (!archive.value) return
  uni.navigateTo({ url: `/pages/compass/index?mode=${archive.value.mode}&id=${archive.value.id}` })
}

async function unlock() {
  if (!archive.value || purchasing.value) return
  purchasing.value = true
  // #ifdef H5
  if (h5DevPreview) {
    appStore.grantEntitlement(archive.value.id)
    await refresh()
    purchasing.value = false
    uni.showToast({ title: '已开启本地内容预览', icon: 'none' })
    return
  }
  // #endif
  const result = await purchaseReport(archive.value.id)
  if (!result.ok) {
    purchasing.value = false
    uni.showToast({ title: result.message, icon: 'none' })
    return
  }
  const confirmed = await waitForEntitlement(archive.value.id)
  purchasing.value = false
  if (confirmed) {
    appStore.grantEntitlement(archive.value.id)
    trackEvent('report_unlock', { mode: archive.value.mode, period: archive.value.period })
    await refresh()
    uni.showToast({ title: '已解锁完整分析', icon: 'none' })
  } else {
    uni.showToast({
      title: '支付已完成，权益确认中，请稍后重新进入本页',
      icon: 'none',
    })
  }
}

async function retryContent() {
  if (!archive.value) return
  await appStore.loadContent(archive.value.id, true)
  await refresh()
}
</script>

<template>
  <view class="page report-page">
    <AppHeader
      eyebrow="ENVIRONMENT REPORT"
      :title="archive?.title || '环境分析'"
      :subtitle="archive ? `${reportModeLabel(archive.mode)} · ${archive.eventYear} 年 · 运${archive.period}` : ''"
      back
    >
      <template #right>
        <view v-if="archive" class="chip" @click="openPoster">分享图</view>
      </template>
    </AppHeader>

    <view class="shell">
      <view v-if="loading && !report" class="card empty-card">
        <text class="empty-title serif">正在生成环境档案…</text>
        <text class="hint">九宫排盘、分金与择日筛选需要少量计算时间。</text>
      </view>

      <view v-else-if="!report || !archive" class="card empty-card">
        <text class="empty-title serif">未找到档案</text>
        <text class="hint">档案可能已被删除，或当前链接来自其他设备。</text>
        <button class="btn btn-primary btn-sm" @click="goBack">返回档案列表</button>
      </view>

      <template v-else>
        <view class="report-head">
          <view class="row wrap">
            <text class="chip" :class="archive.mode === 'YANG' ? 'accent' : 'jade'">
              {{ modeLabel(archive.mode) }}
            </text>
            <text v-if="pair" class="chip">{{ pair.text }}</text>
            <text v-if="pair?.isJianXiang" class="chip gold">兼向</text>
            <text class="chip" :class="unlocked ? 'jade' : 'gold'">
              {{ unlocked ? '完整分析' : '预览模式' }}
            </text>
          </view>
          <text class="report-sub">
            {{ archive.eventYear }} 年 · {{ report.annual.yearGanZhi }} · {{ patternName }}
          </text>
        </view>

        <scroll-view class="tabs" scroll-x :show-scrollbar="false">
          <view class="tabs-inner">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              class="tab"
              :class="{ active: activeTab === tab.key }"
              @click="activeTab = tab.key"
            >
              {{ tab.label }}
            </button>
          </view>
        </scroll-view>

        <view v-if="activeTab === 'overview'" class="tab-body">
          <view class="card pattern-card">
            <view class="pattern-head">
              <view>
                <text class="eyebrow">PATTERN</text>
                <text class="pattern-title serif">{{ report.chart.patternLabel }}</text>
              </view>
              <text class="chip" :class="report.chart.tiGuaUsed ? 'gold' : 'jade'">
                {{ jianKindLabel }}
              </text>
            </view>
            <text class="pattern-traditional">{{ report.chart.patternTraditional }}</text>
            <view class="metric-grid">
              <view class="metric">
                <text class="metric-label">坐山</text>
                <text class="metric-value serif">{{ report.chart.sitting.shan }}山</text>
              </view>
              <view class="metric">
                <text class="metric-label">朝向</text>
                <text class="metric-value serif">{{ report.chart.facing.shan }}向</text>
              </view>
              <view class="metric">
                <text class="metric-label">运盘</text>
                <text class="metric-value serif">{{ report.chart.period }}运</text>
              </view>
              <view class="metric">
                <text class="metric-label">年星入中</text>
                <text class="metric-value serif">{{ starName(report.annual.centerStar) }}</text>
              </view>
              <view class="metric">
                <text class="metric-label">月星入中</text>
                <text class="metric-value serif">
                  {{ report.monthly ? starName(report.monthly.centerStar) : '—' }}
                </text>
              </view>
              <view class="metric">
                <text class="metric-label">罗盘稳定性</text>
                <text class="metric-value serif">{{ Math.round(archive.reading.stability) }}%</text>
              </view>
            </view>
            <view class="divider" />
            <view class="annual-info">
              <view class="annual-row">
                <text class="annual-label">太岁</text>
                <text>{{ report.annual.taiSui }}</text>
                <text class="annual-label">岁破</text>
                <text>{{ report.annual.suiPo }}</text>
                <text class="annual-label">三煞</text>
                <text>{{ report.annual.sanShaDirection }}</text>
              </view>
              <text v-if="report.monthly" class="tiny muted">
                当前月：{{ report.monthly.monthGanZhi }}月 · {{ starName(report.monthly.centerStar) }}入中
              </text>
            </view>
          </view>

          <view v-if="report.warnings.length" class="card warnings-card">
            <view class="card-title"><text>需要注意</text></view>
            <view
              v-for="(warning, index) in report.warnings"
              :key="warning.code + index"
              class="warning-row"
            >
              <text class="badge" :class="warningClass(warning.level)">
                {{ warningLabel(warning.level) }}
              </text>
              <text class="warning-text">{{ warning.text }}</text>
            </view>
          </view>

          <view class="card info-card">
            <view class="card-title"><text>档案摘要</text></view>
            <view class="summary-row">
              <text class="summary-label">类型</text>
              <text>{{ reportModeLabel(archive.mode) }}</text>
            </view>
            <view v-if="archive.mode === 'YANG' && archive.yang" class="summary-row">
              <text class="summary-label">空间</text>
              <text>{{ propertyLabels[archive.yang.propertyType] }}</text>
            </view>
            <view v-if="archive.mode === 'YANG' && archive.yang" class="summary-row">
              <text class="summary-label">居住者</text>
              <text>{{ archive.yang.members.length }} 人</text>
            </view>
            <view v-if="archive.mode === 'YIN' && archive.yin" class="summary-row">
              <text class="summary-label">纪念位</text>
              <text>{{ monumentLabels[archive.yin.monumentType] }}</text>
            </view>
            <view v-if="archive.mode === 'YIN' && archive.yin" class="summary-row">
              <text class="summary-label">仙命</text>
              <text>{{ archive.yin.deceased.length }} 位</text>
            </view>
            <view v-if="archive.mode === 'YIN' && archive.yin" class="summary-row">
              <text class="summary-label">地形</text>
              <text class="summary-text">
                {{ terrainLabels.backSupport[archive.yin.terrain.backSupport] }} ·
                {{ terrainLabels.frontView[archive.yin.terrain.frontView] }} ·
                {{ terrainLabels.leftRight[archive.yin.terrain.leftRight] }}
              </text>
            </view>
            <view v-if="report.fenjin" class="summary-row">
              <text class="summary-label">分金</text>
              <text>
                {{ report.fenjin.slot.mount }}山 {{ report.fenjin.slot.ganZhi }} ·
                {{ report.fenjin.slot.slotNote }}
              </text>
            </view>
            <view class="summary-row">
              <text class="summary-label">报告生成</text>
              <text>{{ formatTimestamp(report.generatedAt) }}</text>
            </view>
            <view class="summary-row">
              <text class="summary-label">内容版本</text>
              <text>{{ report.contentVersion }}</text>
            </view>
          </view>

          <view v-if="!unlocked" class="card unlock-card">
            <text class="eyebrow">FULL ANALYSIS</text>
            <text class="unlock-title serif">解锁九宫完整分析与行动建议</text>
            <text class="unlock-desc">
              当前可查看中宫与向首两个宫位的预览。解锁后可查看其余宫位、逐宫行动建议、八宅或仙命明细。
            </text>
            <view class="unlock-points">
              <text>· 九个宫位逐一分析</text>
              <text>· 山向组合的完整正文</text>
              <text>· 八宅分区 / 仙命比对明细</text>
            </view>
            <button class="btn btn-primary" :disabled="purchasing" @click="unlock">
              {{ purchasing ? '正在处理…' : unlockLabel }}
            </button>
            <text class="hint unlock-hint">
              按档案单独解锁，不自动续费。{{ isH5 && !h5DevPreview ? '网页版仅支持浏览，请在小程序内完成支付。' : '' }}
            </text>
          </view>

          <view v-else-if="!hasFullContent" class="card unlock-card">
            <text class="unlock-title serif">完整内容尚未加载</text>
            <text class="unlock-desc">{{ appStore.contentError || '请检查网络后重试。' }}</text>
            <button class="btn btn-ghost" :disabled="appStore.contentLoading" @click="retryContent">
              重新加载内容
            </button>
          </view>

          <view class="report-footnote">
            <text>
              本报告依据已录入的坐向、年份与人员信息，按传统人居环境规则整理，仅作文化与环境安排参考。涉及结构、施工、地质、消防与纪念地事项时，请由相应专业人士现场复核。
            </text>
            <button class="plain-button link tiny" @click="openGuide">查看完整使用边界 ›</button>
          </view>
        </view>

        <view v-else-if="activeTab === 'palaces'" class="tab-body">
          <view class="card">
            <view class="card-title">
              <text>九宫飞星</text>
              <text class="tiny muted">点击宫位查看</text>
            </view>
            <PalaceGrid
              :chart="report.chart"
              :selected="selectedPalace"
              @select="selectPalace"
            />
            <view class="legend">
              <text class="legend-item"><text class="dot gold-dot" />五黄</text>
              <text class="legend-item"><text class="dot caution-dot" />二黑 / 七赤</text>
              <text class="legend-item"><text class="dot good-dot" />八白 / 九紫</text>
              <text class="legend-item">运 / 年 / 月</text>
            </view>
          </view>

          <view v-if="selectedCell && selectedMeta && selectedInsight" class="card detail-card">
            <view class="detail-head">
              <view>
                <text class="detail-direction serif">{{ selectedMeta.direction }}</text>
                <text class="detail-trigram">{{ selectedMeta.trigram }}宫 · {{ selectedMeta.element }}</text>
              </view>
              <view class="detail-stars">
                <view class="star-pill">
                  <text class="tiny muted">山星</text>
                  <text class="star-pill-num serif">{{ starName(selectedCell.shan) }}</text>
                </view>
                <view class="star-pill">
                  <text class="tiny muted">向星</text>
                  <text class="star-pill-num serif">{{ starName(selectedCell.xiang) }}</text>
                </view>
              </view>
            </view>

            <view class="detail-meta">
              <text class="chip">运星 {{ starName(selectedCell.yun) }}</text>
              <text v-if="selectedCell.annual" class="chip">年星 {{ starName(selectedCell.annual) }}</text>
              <text v-if="selectedCell.monthly" class="chip">月星 {{ starName(selectedCell.monthly) }}</text>
              <text class="chip" :class="selectedInsight.riskLevel === 'active' ? 'gold' : 'jade'">
                {{ riskLabel(selectedInsight.riskLevel) }}
              </text>
            </view>

            <view class="divider" />

            <text class="detail-title serif">{{ selectedInsight.title }}</text>
            <text class="detail-analysis">{{ selectedInsight.analysis }}</text>

            <template v-if="selectedInsight.actions.length">
              <view class="divider" />
              <text class="detail-subtitle">空间安排参考</text>
              <view class="action-list">
                <text
                  v-for="(action, index) in selectedInsight.actions"
                  :key="index"
                  class="action-item"
                >
                  {{ index + 1 }}. {{ action }}
                </text>
              </view>
            </template>

            <view v-else-if="selectedInsight.locked" class="locked-inline">
              <text class="hint">该宫位的完整分析与建议需解锁后查看。</text>
              <button class="btn btn-primary btn-sm" :disabled="purchasing" @click="unlock">
                {{ purchasing ? '正在处理…' : unlockLabel }}
              </button>
            </view>

            <view class="divider" />
            <text class="detail-subtitle">星性提示</text>
            <text class="detail-analysis">
              山星{{ starName(selectedCell.shan) }}：{{ starTheme(selectedCell.shan) }}；向星{{ starName(selectedCell.xiang) }}：{{ starTheme(selectedCell.xiang) }}。
            </text>
          </view>
        </view>

        <view v-else-if="activeTab === 'insights'" class="tab-body">
          <view v-if="!unlocked" class="insight-banner">
            <view>
              <text class="insight-banner-title serif">完整分析待解锁</text>
              <text class="hint">预览仅展示中宫与向首；解锁后可见全部宫位。</text>
            </view>
            <button class="btn btn-primary btn-sm" :disabled="purchasing" @click="unlock">
              {{ purchasing ? '处理中…' : unlockLabel }}
            </button>
          </view>

          <view
            v-for="insight in report.insights"
            :key="insight.palace"
            class="card insight-card"
            :class="{ locked: insight.locked }"
            @click="openInsight(insight)"
          >
            <view class="insight-head">
              <view class="row">
                <text class="insight-palace serif">{{ PALACES[insight.palace].trigram }}宫</text>
                <text class="tiny muted">{{ PALACES[insight.palace].direction }}</text>
              </view>
              <text class="badge" :class="insight.locked ? 'caution' : insight.riskLevel === 'active' ? 'caution' : 'info'">
                {{ insight.locked ? '待解锁' : riskLabel(insight.riskLevel) }}
              </text>
            </view>
            <text class="insight-title serif">{{ insight.title }}</text>
            <text class="insight-text">{{ insight.analysis }}</text>
            <view v-if="insight.actions.length" class="action-list">
              <text v-for="(action, index) in insight.actions" :key="index" class="action-item">
                · {{ action }}
              </text>
            </view>
            <text v-if="insight.locked" class="lock-hint">解锁后查看完整正文与建议 ›</text>
          </view>
        </view>

        <view v-else-if="activeTab === 'bazhai'" class="tab-body">
          <template v-if="report.bazhai">
            <view class="card">
              <view class="card-title"><text>宅卦</text></view>
              <view class="house-row">
                <view class="house-main">
                  <text class="house-name serif">{{ report.bazhai.house.name }}宅</text>
                  <text class="house-meta">
                    坐{{ report.bazhai.house.sittingShan }}山 · 五行{{ report.bazhai.house.element }} ·
                    {{ report.bazhai.house.groupLabel }}
                  </text>
                </view>
                <text class="badge info">{{ report.bazhai.house.groupLabel }}</text>
              </view>
            </view>

            <view
              v-for="(member, index) in report.bazhai.members"
              :key="index"
              class="card member-card"
            >
              <view class="member-head">
                <view>
                  <text class="member-name serif">{{ member.relation }}</text>
                  <text class="member-meta">
                    命卦 {{ member.mingGua.name }} · {{ member.mingGua.element }} ·
                    {{ member.mingGua.groupLabel }} · 按 {{ member.effectiveYear }} 年计
                  </text>
                </view>
                <text class="badge" :class="member.match === 'MATCH' ? 'info' : 'caution'">
                  {{ member.match === 'MATCH' ? '命宅同组' : '命宅异组' }}
                </text>
              </view>

              <view class="palace-stars">
                <view
                  v-for="palace in member.palaces"
                  :key="palace.palace"
                  class="palace-star"
                  :class="palace.star.level === 'GOOD' ? 'good' : 'caution'"
                >
                  <text class="palace-star-dir">{{ palace.direction }}</text>
                  <text class="palace-star-name serif">{{ palace.star.name }}</text>
                  <text class="palace-star-modern">{{ palace.star.modernLabel }}</text>
                </view>
              </view>
              <text class="hint member-suggestion">
                分区只作房间功能与动线安排的参考，不替代采光、通风、结构与消防安全判断。
              </text>
            </view>

            <view v-if="!report.bazhai.members.length" class="card">
              <text class="hint">尚未录入可计算的居住者出生信息，命卦与八宅分区未生成。</text>
            </view>

            <view class="card notes-card">
              <text v-for="(note, index) in report.bazhai.notes" :key="index" class="hint note-line">
                · {{ note }}
              </text>
            </view>
          </template>
          <view v-else class="card empty-card">
            <text class="hint">本档案暂未生成八宅分区。</text>
          </view>
        </view>

        <view v-else-if="activeTab === 'xianming'" class="tab-body">
          <template v-if="report.yinMatch">
            <view class="card verdict-card" :class="`tone-${verdictTone(report.yinMatch.verdict)}`">
              <text class="eyebrow">VERDICT</text>
              <text class="verdict-title serif">{{ verdictLabel(report.yinMatch.verdict) }}</text>
              <text class="verdict-summary">{{ report.yinMatch.summary }}</text>
            </view>

            <view v-if="report.fenjin" class="card">
              <view class="card-title">
                <text>当前分金</text>
                <text class="badge info">
                  {{ report.fenjin.slot.slotNote }}
                </text>
              </view>
              <view class="fenjin-row">
                <text class="fenjin-name serif">
                  {{ report.fenjin.slot.mount }}山 {{ report.fenjin.slot.ganZhi }}
                </text>
                <text class="fenjin-nayin">{{ report.fenjin.slot.nayin }} · {{ report.fenjin.slot.element }}</text>
              </view>
              <text class="tiny muted">
                线度 {{ report.fenjin.slot.startDeg.toFixed(1) }}° – {{ report.fenjin.slot.endDeg.toFixed(1) }}° ·
                偏移 {{ report.fenjin.offset.toFixed(1) }}° ·
                {{ report.fenjin.isJianXiang ? '兼向线度' : '正向线度' }}
              </text>
              <text v-if="report.fenjin.warning" class="hint warn fenjin-warning">
                {{ report.fenjin.warning }}
              </text>

              <template v-if="report.yinMatch.suggestedSlots.length">
                <view class="divider" />
                <text class="detail-subtitle">同山可参考分金</text>
                <view class="slot-list">
                  <text
                    v-for="slot in report.yinMatch.suggestedSlots"
                    :key="slot.index"
                    class="chip jade"
                  >
                    {{ slot.ganZhi }} · {{ slot.nayin }}
                  </text>
                </view>
              </template>
            </view>

            <view
              v-for="(person, index) in report.yinMatch.deceased"
              :key="index"
              class="card person-detail"
            >
              <view class="person-detail-head">
                <view>
                  <text class="person-detail-name serif">{{ person.label }}</text>
                  <text class="person-detail-meta">
                    {{ person.effectiveYear }} 年 {{ person.ganZhi }} · {{ person.nayin }}（{{ person.element }}）
                  </text>
                </view>
                <text class="badge" :class="verdictTone(person.verdict)">
                  {{ verdictLabel(person.verdict) }}
                </text>
              </view>

              <view class="relation-grid">
                <view class="relation-item">
                  <text class="tiny muted">坐山关系</text>
                  <text class="relation-text">{{ relationText(person.mountRelation) }}</text>
                </view>
                <view class="relation-item">
                  <text class="tiny muted">分金关系</text>
                  <text class="relation-text">{{ relationText(person.fenJinRelation) }}</text>
                </view>
              </view>

              <view v-if="person.tabooHits.length" class="taboo-list">
                <view
                  v-for="hit in person.tabooHits"
                  :key="hit.code"
                  class="taboo-row"
                >
                  <text class="badge" :class="hit.severity === 'AVOID' ? 'danger' : 'caution'">
                    {{ hit.severity === 'AVOID' ? '回避项' : '留意项' }}
                  </text>
                  <view class="taboo-main">
                    <text class="taboo-name">{{ hit.name }}</text>
                    <text class="taboo-detail">{{ hit.detail }}</text>
                  </view>
                </view>
              </view>
              <text v-else class="hint">未发现可自动核验的冲山、三煞或五行相克项。</text>
            </view>

            <view class="card notes-card">
              <text v-for="(note, index) in report.yinMatch.notes" :key="index" class="hint note-line">
                · {{ note }}
              </text>
            </view>
            <view v-if="report.yinMatch.deceased.length" class="card notes-card">
              <text
                v-for="(note, index) in report.yinMatch.deceased[0].notes"
                :key="index"
                class="hint note-line"
              >
                · {{ note }}
              </text>
            </view>
          </template>
          <view v-else class="card empty-card">
            <text class="hint">尚未录入可计算的仙命出生信息，仙命比对未生成。</text>
          </view>
        </view>

        <view v-else-if="activeTab === 'zeri'" class="tab-body">
          <view class="card">
            <view class="card-title">
              <text>近期候选日</text>
              <button class="plain-button link tiny" @click="openZeri">更多 ›</button>
            </view>
            <text class="hint zeri-intro">
              以下日期先经岁破、月破、三煞、冲山冲命等大煞前置排除，再由正五行、三合、董公、玄空大卦、天星五派并列复核；五派原始结论不合并，分歧只标记不裁决，「条件分」不构成优劣结论。施工、安葬等事项仍需结合现场与专业人士意见。
            </text>
            <view v-if="report.zeri.length" class="zeri-list">
              <view v-for="item in report.zeri" :key="item.solarDate" class="zeri-item">
                <view class="zeri-date">
                  <text class="zeri-day serif">{{ item.solarDate.slice(5) }}</text>
                  <text class="tiny muted">{{ item.weekDay }}</text>
                </view>
                <view class="zeri-main">
                  <text class="zeri-ganzhi">{{ item.ganZhi }}日 · {{ item.zhiXing }} · {{ item.xiu }}宿</text>
                  <text class="zeri-yi">宜：{{ item.matchedYi.join('、') }}</text>
                  <text class="tiny muted">
                    吉时{{ item.luckyHours.join('、') || '未注' }} · 条件分{{ item.score }}
                    <template v-if="item.level >= 0"> · 等第{{ BEHAVIOR_LABELS[item.behavior] }}</template>
                  </text>
                  <view class="zeri-schools">
                    <text
                      v-for="school in item.schools"
                      :key="school.school"
                      class="chip tiny-chip"
                      :class="{ gold: school.tendency === 'unfavorable', jade: school.tendency === 'favorable' }"
                    >
                      {{ school.schoolLabel }}{{ school.tendency === 'favorable' ? '宜' : school.tendency === 'unfavorable' ? '忌' : school.tendency === 'neutral' ? '平' : '据不足' }}
                    </text>
                    <text v-if="item.conflicts.length" class="chip gold tiny-chip">
                      流派分歧 {{ item.conflicts.length }} 处
                    </text>
                  </view>
                  <text v-if="item.warnings.length" class="zeri-warning">
                    {{ item.warnings.join('；') }}
                  </text>
                </view>
                <text v-if="item.huangDao" class="badge info">黄道</text>
              </view>
            </view>
            <text v-else class="hint">未来范围内暂未筛出符合条件且未冲家属的候选日。</text>
          </view>
        </view>
      </template>

      <view v-if="report" class="bottom-actions">
        <button class="btn btn-ghost" @click="openCompass">重新定向</button>
        <button class="btn btn-primary" @click="openPoster">生成分享图</button>
      </view>

      <view class="footer-space" />
    </view>
  </view>
</template>

<style scoped>
.report-page {
  min-height: 100vh;
  padding-bottom: calc(48rpx + env(safe-area-inset-bottom));
  background: var(--bg);
  color: var(--ink);
}

.report-page .card {
  border: 1rpx solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-card);
}

.report-head {
  margin: 12rpx 0 24rpx;
}

.report-head .row {
  gap: 10rpx;
}

.report-head .chip {
  border-color: var(--line-gold);
  background: var(--surface-warm);
  color: var(--ink-3);
}

.report-head .chip.accent {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
}

.report-head .chip.jade {
  border-color: var(--jade);
  background: var(--jade-soft);
  color: var(--jade);
}

.report-head .chip.gold {
  background: var(--gold-soft);
  color: var(--gold);
}

.report-sub {
  display: block;
  margin-top: 14rpx;
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.6;
  letter-spacing: 0.08em;
}

.tabs {
  margin: 0 calc(-1 * var(--page-padding)) 30rpx;
  white-space: nowrap;
}

.tabs-inner {
  display: inline-flex;
  gap: 12rpx;
  padding: 6rpx var(--page-padding) 10rpx;
}

.tab {
  position: relative;
  flex-shrink: 0;
  min-width: 104rpx;
  min-height: 68rpx;
  margin: 0;
  padding: 0 30rpx;
  border: 1rpx solid var(--line-gold);
  border-radius: 999rpx;
  background: var(--surface-warm);
  box-shadow: none;
  color: var(--ink-3);
  font-size: 24rpx;
  font-weight: 500;
  line-height: 66rpx;
  letter-spacing: 0.12em;
}

.tab::after {
  border: none;
}

.tab.active {
  border-color: var(--accent);
  background: var(--accent);
  box-shadow: 0 4rpx 14rpx var(--accent-soft);
  color: var(--surface);
  font-weight: 600;
}

.tab-body {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.tab-body .card {
  padding: 32rpx;
}

.tab-body .card + .card {
  margin-top: 0;
}

.tab-body .card-title {
  margin-bottom: 20rpx;
  color: var(--ink);
  font-size: 28rpx;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.tab-body .divider {
  height: 1rpx;
  margin: 26rpx 0;
  background: var(--line);
}

.pattern-card {
  position: relative;
  overflow: hidden;
  padding-top: 40rpx !important;
  border-color: var(--line-gold) !important;
  background: linear-gradient(155deg, var(--surface) 0%, var(--surface-warm) 100%) !important;
}

.pattern-card::before {
  position: absolute;
  top: 0;
  right: 32rpx;
  left: 32rpx;
  height: 4rpx;
  background: var(--gold);
  content: '';
  opacity: 0.65;
}

.pattern-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
  padding-bottom: 24rpx;
  border-bottom: 1rpx solid var(--line-gold);
}

.pattern-head .eyebrow {
  color: var(--gold);
  letter-spacing: 0.2em;
}

.pattern-title {
  display: block;
  margin-top: 10rpx;
  color: var(--ink);
  font-size: 44rpx;
  font-weight: 600;
  line-height: 1.3;
  letter-spacing: 0.08em;
}

.pattern-traditional {
  display: block;
  margin-top: 22rpx;
  color: var(--ink-3);
  font-size: 24rpx;
  line-height: 1.8;
  letter-spacing: 0.04em;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12rpx;
  margin-top: 28rpx;
}

.metric {
  min-width: 0;
  padding: 22rpx 10rpx 20rpx;
  border: 1rpx solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  text-align: center;
}

.metric-label {
  display: block;
  color: var(--muted);
  font-size: 20rpx;
  line-height: 1.4;
  letter-spacing: 0.04em;
}

.metric-value {
  display: block;
  margin-top: 10rpx;
  color: var(--ink);
  font-size: 30rpx;
  font-weight: 600;
  line-height: 1.35;
}

.annual-info {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.annual-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10rpx 16rpx;
  color: var(--ink-2);
  font-size: 24rpx;
  line-height: 1.6;
}

.annual-label {
  color: var(--gold);
  font-size: 21rpx;
  font-weight: 600;
}

.warnings-card {
  border-left: 5rpx solid var(--gold) !important;
  background: var(--surface-warm) !important;
}

.warning-row {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding: 18rpx 0;
  border-top: 1rpx solid var(--line);
}

.warning-text {
  flex: 1;
  color: var(--ink-2);
  font-size: 24rpx;
  line-height: 1.75;
}

.summary-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 28rpx;
  padding: 18rpx 0;
  border-top: 1rpx solid var(--line);
  color: var(--ink-2);
  font-size: 24rpx;
  line-height: 1.65;
}

.summary-label {
  flex-shrink: 0;
  color: var(--muted);
  letter-spacing: 0.06em;
}

.summary-text {
  text-align: right;
}

.unlock-card {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
  border-color: var(--line-gold) !important;
  background: linear-gradient(150deg, var(--surface-warm), var(--surface-2)) !important;
}

.unlock-card .eyebrow {
  color: var(--gold);
}

.unlock-title {
  color: var(--ink);
  font-size: 36rpx;
  line-height: 1.45;
}

.unlock-desc {
  color: var(--ink-2);
  font-size: 24rpx;
  line-height: 1.8;
}

.unlock-points {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
  padding: 20rpx 24rpx;
  border-left: 3rpx solid var(--gold);
  border-radius: var(--radius-sm);
  background: var(--gold-soft);
  color: var(--ink-2);
  font-size: 23rpx;
  line-height: 1.6;
}

.unlock-hint {
  display: block;
  color: var(--muted);
  line-height: 1.7;
  text-align: center;
}

.report-footnote {
  padding: 20rpx 12rpx 8rpx;
  color: var(--muted);
  font-size: 21rpx;
  line-height: 1.85;
}

.report-footnote .tiny {
  display: inline-block;
  margin-top: 14rpx;
  color: var(--accent);
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx 20rpx;
  margin-top: 24rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid var(--line);
  color: var(--muted);
  font-size: 20rpx;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
}

.dot {
  display: inline-block;
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
}

.gold-dot {
  background: var(--gold);
}

.caution-dot {
  background: var(--danger);
}

.good-dot {
  background: var(--jade);
}

.detail-card {
  border-top: 4rpx solid var(--jade) !important;
}

.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
}

.detail-direction {
  display: block;
  color: var(--ink);
  font-size: 42rpx;
  font-weight: 600;
  line-height: 1.3;
  letter-spacing: 0.08em;
}

.detail-trigram {
  display: block;
  margin-top: 8rpx;
  color: var(--jade);
  font-size: 22rpx;
  line-height: 1.5;
  letter-spacing: 0.08em;
}

.detail-stars {
  display: flex;
  flex-shrink: 0;
  gap: 12rpx;
}

.star-pill {
  display: flex;
  min-width: 88rpx;
  flex-direction: column;
  align-items: center;
  gap: 6rpx;
  padding: 14rpx 16rpx;
  border: 1rpx solid var(--line-gold);
  border-radius: var(--radius);
  background: var(--surface-warm);
}

.star-pill-num {
  color: var(--ink);
  font-size: 30rpx;
  font-weight: 600;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 24rpx;
}

.detail-meta .chip {
  background: var(--surface-2);
  color: var(--ink-3);
}

.detail-meta .chip.jade {
  background: var(--jade-soft);
  color: var(--jade);
}

.detail-meta .chip.gold {
  background: var(--gold-soft);
  color: var(--gold);
}

.detail-title {
  display: block;
  color: var(--ink);
  font-size: 34rpx;
  font-weight: 600;
  line-height: 1.5;
  letter-spacing: 0.04em;
}

.detail-analysis {
  display: block;
  margin-top: 14rpx;
  color: var(--ink-2);
  font-size: 25rpx;
  line-height: 1.9;
}

.detail-subtitle {
  display: block;
  margin-bottom: 14rpx;
  color: var(--gold);
  font-size: 24rpx;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.action-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.action-item {
  color: var(--ink-2);
  font-size: 24rpx;
  line-height: 1.8;
}

.locked-inline {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 16rpx;
  margin-top: 18rpx;
  padding: 22rpx;
  border-radius: var(--radius);
  background: var(--surface-2);
}

.insight-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  padding: 26rpx 28rpx;
  border: 1rpx solid var(--line-gold);
  border-radius: var(--radius-lg);
  background: var(--accent-soft);
}

.insight-banner-title {
  display: block;
  margin-bottom: 6rpx;
  color: var(--accent);
  font-size: 29rpx;
  line-height: 1.4;
}

.insight-card {
  position: relative;
  overflow: hidden;
  padding: 32rpx 32rpx 32rpx 40rpx !important;
  border-color: var(--line-gold) !important;
  background: linear-gradient(105deg, var(--surface-warm), var(--surface)) !important;
  box-shadow: var(--shadow-card) !important;
}

.insight-card::before {
  position: absolute;
  top: 24rpx;
  bottom: 24rpx;
  left: 18rpx;
  width: 3rpx;
  border-radius: 999rpx;
  background: var(--gold);
  content: '';
  opacity: 0.55;
}

.insight-card.locked {
  background: var(--surface-2) !important;
  opacity: 0.88;
}

.insight-card.locked::before {
  background: var(--ink-faint);
}

.insight-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  padding-bottom: 18rpx;
  border-bottom: 1rpx solid var(--line);
}

.insight-head .row {
  gap: 14rpx;
}

.insight-palace {
  color: var(--jade);
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.insight-title {
  display: block;
  margin-top: 22rpx;
  color: var(--ink);
  font-size: 32rpx;
  font-weight: 600;
  line-height: 1.5;
}

.insight-text {
  display: block;
  margin-top: 12rpx;
  color: var(--ink-2);
  font-size: 24rpx;
  line-height: 1.85;
}

.insight-card .action-list {
  margin-top: 20rpx;
  padding: 18rpx 20rpx;
  border-radius: var(--radius-sm);
  background: var(--surface-warm);
}

.lock-hint {
  display: block;
  margin-top: 18rpx;
  color: var(--gold);
  font-size: 22rpx;
  letter-spacing: 0.04em;
}

.house-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}

.house-name {
  display: block;
  color: var(--ink);
  font-size: 38rpx;
  font-weight: 600;
}

.house-meta {
  display: block;
  margin-top: 10rpx;
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.7;
}

.member-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
}

.member-name {
  display: block;
  color: var(--ink);
  font-size: 32rpx;
  font-weight: 600;
}

.member-meta {
  display: block;
  margin-top: 8rpx;
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.7;
}

.palace-stars {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12rpx;
  margin-top: 24rpx;
}

.palace-star {
  padding: 18rpx 8rpx;
  border: 1rpx solid var(--line);
  border-radius: var(--radius);
  background: var(--surface-warm);
  text-align: center;
}

.palace-star.good {
  border-color: var(--jade);
  background: var(--jade-soft);
}

.palace-star.caution {
  border-color: var(--line-gold);
  background: var(--gold-soft);
}

.palace-star-dir {
  display: block;
  color: var(--muted);
  font-size: 19rpx;
}

.palace-star-name {
  display: block;
  margin-top: 6rpx;
  color: var(--ink);
  font-size: 26rpx;
}

.palace-star-modern {
  display: block;
  margin-top: 4rpx;
  color: var(--muted);
  font-size: 18rpx;
}

.member-suggestion {
  display: block;
  margin-top: 20rpx;
  line-height: 1.75;
}

.notes-card {
  border-color: var(--line-gold) !important;
  background: var(--surface-2) !important;
}

.note-line {
  display: block;
  line-height: 1.75;
}

.note-line + .note-line {
  margin-top: 12rpx;
}

.verdict-card {
  border-left: 5rpx solid var(--jade) !important;
  background: var(--jade-soft) !important;
}

.verdict-card.tone-caution {
  border-left-color: var(--gold) !important;
  background: var(--gold-soft) !important;
}

.verdict-card.tone-danger {
  border-left-color: var(--danger) !important;
  background: var(--accent-soft) !important;
}

.verdict-title {
  display: block;
  margin-top: 8rpx;
  color: var(--ink);
  font-size: 40rpx;
  font-weight: 600;
}

.verdict-summary {
  display: block;
  margin-top: 14rpx;
  color: var(--ink-2);
  font-size: 25rpx;
  line-height: 1.85;
}

.fenjin-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 20rpx;
  margin-bottom: 12rpx;
}

.fenjin-name {
  color: var(--ink);
  font-size: 36rpx;
  font-weight: 600;
}

.fenjin-nayin {
  color: var(--jade);
  font-size: 24rpx;
}

.fenjin-warning {
  display: block;
  margin-top: 16rpx;
  color: var(--danger);
  line-height: 1.7;
}

.slot-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.slot-list .chip.jade {
  background: var(--jade-soft);
  color: var(--jade);
}

.person-detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
}

.person-detail-name {
  display: block;
  color: var(--ink);
  font-size: 32rpx;
  font-weight: 600;
}

.person-detail-meta {
  display: block;
  margin-top: 8rpx;
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.65;
}

.relation-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14rpx;
  margin-top: 24rpx;
}

.relation-item {
  padding: 20rpx;
  border: 1rpx solid var(--line);
  border-radius: var(--radius);
  background: var(--surface-warm);
}

.relation-text {
  display: block;
  margin-top: 8rpx;
  color: var(--ink-2);
  font-size: 24rpx;
}

.taboo-list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
  margin-top: 24rpx;
}

.taboo-row {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding-top: 18rpx;
  border-top: 1rpx solid var(--line);
}

.taboo-main {
  flex: 1;
}

.taboo-name {
  display: block;
  color: var(--ink);
  font-size: 24rpx;
  font-weight: 600;
}

.taboo-detail {
  display: block;
  margin-top: 6rpx;
  color: var(--ink-2);
  font-size: 23rpx;
  line-height: 1.75;
}

.zeri-schools {
  display: flex;
  flex-wrap: wrap;
  gap: 6rpx;
  margin-top: 8rpx;
}
.tiny-chip {
  font-size: 18rpx;
}
.zeri-intro {
  display: block;
  margin-bottom: 18rpx;
  line-height: 1.8;
}

.zeri-list {
  display: flex;
  flex-direction: column;
}

.zeri-item {
  display: flex;
  align-items: flex-start;
  gap: 20rpx;
  padding: 24rpx 0;
  border-top: 1rpx solid var(--line);
}

.zeri-date {
  flex-shrink: 0;
  width: 96rpx;
  padding-right: 16rpx;
  border-right: 1rpx solid var(--line-gold);
}

.zeri-day {
  display: block;
  color: var(--ink);
  font-size: 30rpx;
  font-weight: 600;
}

.zeri-main {
  flex: 1;
  min-width: 0;
}

.zeri-ganzhi {
  display: block;
  color: var(--ink-2);
  font-size: 24rpx;
}

.zeri-yi {
  display: block;
  margin-top: 6rpx;
  color: var(--jade);
  font-size: 22rpx;
  line-height: 1.65;
}

.zeri-warning {
  display: block;
  margin-top: 8rpx;
  color: var(--danger);
  font-size: 21rpx;
  line-height: 1.7;
}

.bottom-actions {
  display: flex;
  gap: 18rpx;
  margin-top: 36rpx;
}

.bottom-actions .btn {
  flex: 1;
  border-radius: 999rpx;
}

.footer-space {
  height: calc(32rpx + env(safe-area-inset-bottom));
}

.empty-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20rpx;
  padding: 72rpx 40rpx !important;
  text-align: center;
}

.empty-title {
  color: var(--ink);
  font-size: 34rpx;
}
</style>
