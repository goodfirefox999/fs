<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import type { SceneMode } from '@/core/types'
import { useArchiveStore } from '@/stores/archive'
import { useDraftStore } from '@/stores/draft'
import {
  formatTimestamp,
  modeLabel,
  sittingFacingText,
} from '@/utils/display'

type Filter = 'ALL' | SceneMode

const archiveStore = useArchiveStore()
const draft = useDraftStore()
const filter = ref<Filter>('ALL')

const filters: Array<{ key: Filter; label: string }> = [
  { key: 'ALL', label: '全部' },
  { key: 'YANG', label: '阳宅' },
  { key: 'YIN', label: '纪念地' },
]

const list = computed(() => {
  if (filter.value === 'ALL') return archiveStore.sorted
  return archiveStore.byMode(filter.value)
})

const counts = computed(() => ({
  ALL: archiveStore.archives.length,
  YANG: archiveStore.byMode('YANG').length,
  YIN: archiveStore.byMode('YIN').length,
}))

onShow(() => {
  if (filter.value !== 'ALL' && !list.value.length) filter.value = 'ALL'
})

function create() {
  draft.setSceneMode(filter.value === 'YIN' ? 'YIN' : 'YANG')
  uni.navigateTo({
    url: `/pages/wizard/index?mode=${filter.value === 'YIN' ? 'YIN' : 'YANG'}`,
  })
}

function openReport(id: string) {
  archiveStore.setCurrent(id)
  uni.navigateTo({ url: `/pages/report/index?id=${id}` })
}

function openZeri(id: string) {
  uni.navigateTo({ url: `/pages/zeri/index?id=${id}` })
}

function remove(id: string) {
  const target = archiveStore.getById(id)
  if (!target) return
  uni.showModal({
    title: '删除档案',
    content: `确定删除「${target.title}」？删除后本机记录不可恢复。`,
    confirmText: '删除',
    confirmColor: '#8E3B2F',
    success: (result) => {
      if (!result.confirm) return
      archiveStore.remove(id)
      uni.showToast({ title: '已删除', icon: 'none' })
    },
  })
}

function summary(facingDeg: number) {
  return sittingFacingText(facingDeg)
}
</script>

<template>
  <view class="page with-tab">
    <view class="shell">
      <view class="page-head">
        <view>
          <text class="eyebrow">ARCHIVE</text>
          <text class="head-title serif">我的档案</text>
          <text class="head-sub">共 {{ archiveStore.archives.length }} 份，均保存在本机。</text>
        </view>
        <button class="btn btn-primary btn-sm create" @click="create">新建</button>
      </view>

      <view class="segmented">
        <button
          v-for="item in filters"
          :key="item.key"
          class="seg-item"
          :class="{ active: filter === item.key }"
          @click="filter = item.key"
        >
          {{ item.label }}
          <text class="seg-count">{{ counts[item.key] }}</text>
        </button>
      </view>

      <view v-if="list.length" class="archive-list">
        <view v-for="item in list" :key="item.id" class="archive card">
          <view class="archive-top">
            <view class="row">
              <text class="chip" :class="item.mode === 'YANG' ? 'accent' : 'jade'">
                {{ modeLabel(item.mode) }}
              </text>
              <text class="archive-period">运{{ item.period }}</text>
            </view>
            <text class="archive-date tiny muted">{{ formatTimestamp(item.updatedAt) }}</text>
          </view>

          <text class="archive-title serif" @click="openReport(item.id)">{{ item.title }}</text>

          <view class="archive-readout" @click="openReport(item.id)">
            <view class="readout-main">
              <text class="readout-name">{{ summary(item.reading.facingDeg).text }}</text>
              <text class="readout-deg">{{ summary(item.reading.facingDeg).deg }}</text>
            </view>
            <view class="readout-side">
              <text v-if="summary(item.reading.facingDeg).isJianXiang" class="badge caution">兼向</text>
              <text v-else class="badge info">正向</text>
              <text class="tiny muted">
                稳定性 {{ Math.round(item.reading.stability) }}%
              </text>
            </view>
          </view>

          <view class="divider" />

          <view class="archive-actions">
            <button class="btn btn-ghost btn-sm" @click="openReport(item.id)">查看分析</button>
            <button class="btn btn-ghost btn-sm" @click="openZeri(item.id)">择日</button>
            <button class="btn btn-ghost btn-sm danger-text" @click="remove(item.id)">删除</button>
          </view>
        </view>
      </view>

      <view v-else class="card empty-card">
        <text class="empty-mark serif">空</text>
        <text class="empty-title serif">
          {{ filter === 'ALL' ? '还没有环境档案' : '该分类下暂无档案' }}
        </text>
        <text class="hint">
          档案包含坐向、年份与人员信息，可随时回看九宫、空间分区与择日参考。
        </text>
        <button class="btn btn-primary btn-sm" @click="create">新建档案</button>
      </view>

      <view class="footnote">
        <text>删除档案仅影响本机记录；云端购买记录不会自动恢复本机档案，请谨慎删除。</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  --bg: #f7f3ec;
  --surface: #fdfaf4;
  --surface-2: #f0eadc;
  --surface-warm: #faf5eb;
  --ink: #1c1a17;
  --ink-2: #3d3630;
  --ink-3: #6b5e52;
  --muted: #8c8074;
  --accent: #b03a2e;
  --accent-soft: rgba(176, 58, 46, 0.08);
  --jade: #2d5a4a;
  --jade-soft: rgba(45, 90, 74, 0.08);
  --gold: #a08048;
  --gold-soft: rgba(160, 128, 72, 0.12);
  --line-gold: rgba(160, 128, 72, 0.25);
  --danger: #8e3b2f;
  --line: rgba(28, 26, 23, 0.08);
  --radius: 16rpx;
  --radius-lg: 24rpx;
  --radius-sm: 8rpx;
  --shadow-card: 0 2rpx 16rpx rgba(28, 26, 23, 0.04);
  --page-padding: 36rpx;

  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
}

.shell {
  padding-right: var(--page-padding);
  padding-left: var(--page-padding);
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24rpx;
  padding: 32rpx 0 26rpx;
}

.head-title {
  display: block;
  margin-top: 6rpx;
  color: var(--ink);
  font-size: 44rpx;
  line-height: 1.25;
  letter-spacing: 0.06em;
}

.head-sub {
  display: block;
  margin-top: 10rpx;
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.5;
}

.create {
  flex-shrink: 0;
  margin-bottom: 4rpx;
}

.segmented {
  display: flex;
  gap: 8rpx;
  margin-bottom: 28rpx;
  padding: 8rpx;
  border: 1rpx solid var(--line);
  border-radius: 999rpx;
  background: var(--surface-2);
  box-shadow: inset 0 1rpx 4rpx rgba(28, 26, 23, 0.03);
}

.seg-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  min-height: 66rpx;
  padding: 0 16rpx;
  border: 1rpx solid transparent;
  border-radius: 999rpx;
  background: transparent;
  color: var(--ink-3);
  font-size: 24rpx;
  line-height: 1;
  transition: color 0.22s ease, background-color 0.22s ease, border-color 0.22s ease,
    box-shadow 0.22s ease;
}

.seg-item::after {
  border: none;
}

.seg-item.active {
  border-color: var(--line-gold);
  background: var(--surface);
  color: var(--accent);
  box-shadow: 0 4rpx 14rpx rgba(28, 26, 23, 0.07);
}

.seg-count {
  min-width: 28rpx;
  color: var(--muted);
  font-size: 20rpx;
  text-align: center;
  transition: color 0.22s ease;
}

.seg-item.active .seg-count {
  color: var(--accent);
}

.archive-list {
  display: flex;
  flex-direction: column;
  gap: 22rpx;
}

.archive {
  position: relative;
  overflow: hidden;
  padding: 28rpx 28rpx 24rpx 34rpx;
  border: 1rpx solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-card);
}

.archive::before {
  position: absolute;
  top: 28rpx;
  bottom: 28rpx;
  left: 0;
  width: 6rpx;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--gold);
  content: '';
}

.archive-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.archive-period {
  color: var(--gold);
  font-size: 20rpx;
  letter-spacing: 0.12em;
}

.archive-date {
  flex-shrink: 0;
  color: var(--muted);
}

.archive-title {
  display: block;
  margin: 20rpx 0 16rpx;
  color: var(--ink);
  font-size: 34rpx;
  line-height: 1.4;
  letter-spacing: 0.02em;
}

.archive-readout {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  padding: 22rpx 24rpx;
  border: 1rpx solid var(--line-gold);
  border-radius: var(--radius);
  background: var(--surface-warm);
}

.readout-main {
  min-width: 0;
}

.readout-name {
  display: block;
  color: var(--ink-2);
  font-size: 28rpx;
  line-height: 1.35;
}

.readout-deg {
  display: block;
  margin-top: 6rpx;
  color: var(--muted);
  font-size: 21rpx;
  letter-spacing: 0.04em;
}

.readout-side {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8rpx;
}

.archive .divider {
  margin: 22rpx 0 16rpx;
  background: var(--line);
}

.archive-actions {
  display: flex;
  gap: 12rpx;
}

.archive-actions .btn {
  flex: 1;
  color: var(--ink-3);
  transition: color 0.2s ease, background-color 0.2s ease;
}

.archive-actions .btn:first-child {
  color: var(--accent);
}

.danger-text,
.archive-actions .danger-text {
  color: var(--danger);
}

.empty-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
  padding: 72rpx 44rpx 64rpx;
  border: 1rpx solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-card);
  text-align: center;
}

.empty-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 104rpx;
  height: 104rpx;
  margin-bottom: 8rpx;
  border: 2rpx solid var(--accent);
  border-radius: 50%;
  background: var(--accent-soft);
  box-shadow: inset 0 0 0 7rpx var(--surface), inset 0 0 0 9rpx var(--line-gold);
  color: var(--accent);
  font-size: 40rpx;
  line-height: 1;
}

.empty-title {
  color: var(--ink);
  font-size: 32rpx;
  line-height: 1.4;
}

.empty-card .hint {
  max-width: 520rpx;
  margin-bottom: 12rpx;
  color: var(--muted);
  line-height: 1.75;
}

.footnote {
  margin-top: 36rpx;
  padding: 24rpx 8rpx 0;
  border-top: 1rpx solid var(--line);
  color: var(--muted);
  font-size: 21rpx;
  line-height: 1.7;
}
</style>
