<script setup lang="ts">
import { computed } from 'vue'
import AppHeader from '@/components/AppHeader.vue'
import { useArchiveStore } from '@/stores/archive'
import { useDraftStore } from '@/stores/draft'
import type { SceneMode } from '@/core/types'
import {
  formatTimestamp,
  modeLabel,
  sittingFacingText,
} from '@/utils/display'

const archiveStore = useArchiveStore()
const draft = useDraftStore()

const recent = computed(() => archiveStore.recent)
const yangCount = computed(() => archiveStore.byMode('YANG').length)
const yinCount = computed(() => archiveStore.byMode('YIN').length)

function start(mode: SceneMode) {
  draft.setSceneMode(mode)
  uni.navigateTo({ url: `/pages/wizard/index?mode=${mode}` })
}

function openCompass() {
  uni.navigateTo({ url: `/pages/compass/index?mode=${draft.sceneMode}` })
}

function openReport(id: string) {
  uni.navigateTo({ url: `/pages/report/index?id=${id}` })
}

function openArchive() {
  uni.switchTab({ url: '/pages/archive/index' })
}

function openZeri() {
  uni.navigateTo({ url: '/pages/zeri/index' })
}

function openGuide() {
  uni.navigateTo({ url: '/pages/guide/index' })
}

function summaryOf(id: string) {
  const archive = archiveStore.getById(id)
  return archive ? sittingFacingText(archive.reading.facingDeg) : null
}
</script>

<template>
  <view class="page with-tab">
    <view class="shell">

      <!-- ═══ 印章 · 品牌区 ═══ -->
      <view class="brand">
        <view class="brand-seal">
          <text class="seal-char serif">居</text>
        </view>
        <view class="brand-text">
          <text class="brand-title serif">居境罗盘</text>
          <text class="brand-sub">传统人居环境 · 方位档案</text>
        </view>
        <view class="brand-badge chip jade">本地优先</view>
      </view>

      <!-- ═══ 主视觉 · 卷轴 ═══ -->
      <view class="hero">
        <view class="hero-inner">
          <text class="hero-kicker">记录 · 复核 · 留档</text>
          <text class="hero-title serif">一方坐向，一份可追溯的环境档案。</text>
          <text class="hero-desc">
            以罗盘读数为起点，结合九宫、空间分区与日程信息，输出可回看的结构化记录。
          </text>
          <view class="hero-stats">
            <text class="hero-stat">
              <text class="hero-stat-num serif">{{ archiveStore.archives.length }}</text>
              <text class="hero-stat-label">份档案</text>
            </text>
            <view class="hero-stat-line" />
            <text class="hero-stat">
              <text class="hero-stat-num serif">{{ yangCount }}</text>
              <text class="hero-stat-label">阳宅</text>
            </text>
            <view class="hero-stat-line" />
            <text class="hero-stat">
              <text class="hero-stat-num serif">{{ yinCount }}</text>
              <text class="hero-stat-label">纪念地</text>
            </text>
          </view>
        </view>
      </view>

      <!-- ═══ 建档入口 ═══ -->
      <view class="mode-section">
        <view class="mode-card yang" @click="start('YANG')">
          <view class="mode-top">
            <view class="mode-seal yang-seal">
              <text class="mode-seal-char serif">宅</text>
            </view>
            <text class="mode-tag">YANG ZHAI</text>
          </view>
          <text class="mode-title serif">阳宅环境建档</text>
          <text class="mode-desc">居住、办公与商铺的坐向记录、九宫分区与居住者命卦参考。</text>
          <view class="mode-tags">
            <text class="mode-tag-item">坐向</text>
            <text class="mode-tag-item">九宫</text>
            <text class="mode-tag-item">八宅</text>
            <text class="mode-tag-item">择日</text>
          </view>
          <view class="mode-action">
            <text class="mode-action-text">新建档案</text>
            <text class="mode-action-arrow">→</text>
          </view>
        </view>

        <view class="mode-card yin" @click="start('YIN')">
          <view class="mode-top">
            <view class="mode-seal yin-seal">
              <text class="mode-seal-char serif">纪</text>
            </view>
            <text class="mode-tag">MEMORIAL</text>
          </view>
          <text class="mode-title serif">先人纪念地建档</text>
          <text class="mode-desc">为纪念地记录坐向、地形与家族信息，形成以便现场核对的环境档案。</text>
          <view class="mode-tags">
            <text class="mode-tag-item">坐向</text>
            <text class="mode-tag-item">分金</text>
            <text class="mode-tag-item">仙命</text>
            <text class="mode-tag-item">地形</text>
          </view>
          <view class="mode-action">
            <text class="mode-action-text">新建档案</text>
            <text class="mode-action-arrow">→</text>
          </view>
        </view>
      </view>

      <!-- ═══ 快捷工具 ═══ -->
      <view class="tools">
        <view class="tool" @click="openCompass">
          <view class="tool-icon">
            <text class="tool-icon-char serif">罗</text>
          </view>
          <text class="tool-name">罗盘定向</text>
          <text class="tool-hint">采样或手动读数</text>
        </view>
        <view class="tool" @click="openZeri">
          <view class="tool-icon">
            <text class="tool-icon-char serif">日</text>
          </view>
          <text class="tool-name">择日参考</text>
          <text class="tool-hint">按用途筛选候选日</text>
        </view>
        <view class="tool" @click="openGuide">
          <view class="tool-icon">
            <text class="tool-icon-char serif">阅</text>
          </view>
          <text class="tool-name">使用说明</text>
          <text class="tool-hint">边界与口径</text>
        </view>
      </view>

      <!-- ═══ 最近档案 ═══ -->
      <view class="section-head">
        <view class="section-left">
          <text class="section-eyebrow">RECENT</text>
          <text class="section-title serif">最近档案</text>
        </view>
        <button class="section-link" @click="openArchive">全部档案 ›</button>
      </view>

      <view v-if="recent.length" class="recent-list">
        <view
          v-for="item in recent"
          :key="item.id"
          class="recent-item"
          @click="openReport(item.id)"
        >
          <view class="recent-indicator" :class="item.mode === 'YANG' ? 'yang-dot' : 'yin-dot'" />
          <view class="recent-body">
            <view class="recent-row">
              <text class="recent-title">{{ item.title }}</text>
              <text class="recent-badge" :class="item.mode === 'YANG' ? 'yang-badge' : 'yin-badge'">
                {{ modeLabel(item.mode) }}
              </text>
            </view>
            <text class="recent-meta">
              {{ summaryOf(item.id)?.text }} · {{ summaryOf(item.id)?.deg }}
            </text>
            <text class="recent-time">
              {{ formatTimestamp(item.updatedAt) }} · 运{{ item.period }}
            </text>
          </view>
          <text class="recent-arrow">›</text>
        </view>
      </view>

      <view v-else class="empty-state">
        <view class="empty-seal">
          <text class="empty-seal-char serif">空</text>
        </view>
        <text class="empty-title serif">还没有档案</text>
        <text class="empty-hint">先完成一次罗盘定向，或手动输入坐向度数，再建立第一份环境档案。</text>
        <button class="btn btn-primary btn-sm" @click="start('YANG')">开始第一份建档</button>
      </view>

      <!-- ═══ 边界声明 ═══ -->
      <view class="boundary">
        <view class="boundary-line" />
        <text class="boundary-text">
          本工具用于传统人居环境与方位信息的记录和整理，仅提供文化与环境安排参考，不构成医疗、投资、法律或施工安全建议。罗盘读数请结合现场复核。
        </text>
      </view>

    </view>
  </view>
</template>

<style scoped>
/* ═══ 印章品牌区 ═══ */
.brand {
  display: flex;
  align-items: center;
  gap: 24rpx;
  padding: 36rpx 0 28rpx;
}
.brand-seal {
  width: 96rpx;
  height: 96rpx;
  border-radius: 16rpx;
  background: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(176, 58, 46, 0.25);
  flex-shrink: 0;
}
.seal-char {
  color: #FFF8EE;
  font-size: 52rpx;
  line-height: 1;
}
.brand-text {
  flex: 1;
  min-width: 0;
}
.brand-title {
  display: block;
  font-size: 48rpx;
  line-height: 1.3;
  color: var(--ink);
}
.brand-sub {
  display: block;
  margin-top: 6rpx;
  color: var(--muted);
  font-size: 22rpx;
  letter-spacing: 0.08em;
}
.brand-badge {
  flex-shrink: 0;
}

/* ═══ 主视觉卷轴 ═══ */
.hero {
  margin-top: 8rpx;
  border-radius: var(--radius-lg);
  background: linear-gradient(155deg, #FDFAF4 0%, #F5EEE2 60%, #F0E6D5 100%);
  border: 1rpx solid var(--line-gold);
  overflow: hidden;
  position: relative;
  box-shadow: var(--shadow-hero);
}
.hero::before {
  content: '';
  position: absolute;
  right: -60rpx;
  top: -60rpx;
  width: 240rpx;
  height: 240rpx;
  border: 1rpx solid rgba(160, 128, 72, 0.15);
  border-radius: 50%;
}
.hero::after {
  content: '';
  position: absolute;
  right: -20rpx;
  top: -20rpx;
  width: 140rpx;
  height: 140rpx;
  border: 1rpx solid rgba(160, 128, 72, 0.1);
  border-radius: 50%;
}
.hero-inner {
  padding: 44rpx 40rpx;
  position: relative;
  z-index: 1;
}
.hero-kicker {
  display: block;
  color: var(--gold);
  font-size: 20rpx;
  letter-spacing: 0.28em;
  margin-bottom: 12rpx;
}
.hero-title {
  display: block;
  font-size: 38rpx;
  line-height: 1.45;
  color: var(--ink);
  letter-spacing: 0.04em;
}
.hero-desc {
  display: block;
  margin-top: 14rpx;
  color: var(--ink-3);
  font-size: 24rpx;
  line-height: 1.8;
}
.hero-stats {
  display: flex;
  align-items: center;
  gap: 24rpx;
  margin-top: 28rpx;
  padding-top: 24rpx;
  border-top: 1rpx solid var(--line-gold);
}
.hero-stat {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
}
.hero-stat-num {
  font-size: 36rpx;
  color: var(--accent);
}
.hero-stat-label {
  font-size: 22rpx;
  color: var(--muted);
}
.hero-stat-line {
  width: 1rpx;
  height: 32rpx;
  background: var(--line-gold);
}

/* ═══ 建档入口 ═══ */
.mode-section {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20rpx;
  margin-top: 28rpx;
}
.mode-card {
  display: flex;
  flex-direction: column;
  padding: 32rpx 28rpx;
  border-radius: var(--radius);
  border: 1rpx solid var(--line);
  min-height: 420rpx;
  transition: all 0.2s ease;
  cursor: pointer;
}
.mode-card:active {
  transform: scale(0.98);
}
.mode-card.yang {
  background: linear-gradient(165deg, #FDFAF4 0%, #F5EDE0 100%);
}
.mode-card.yin {
  background: linear-gradient(165deg, #F8F7F0 0%, #EBF0E8 100%);
}
.mode-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.mode-seal {
  width: 64rpx;
  height: 64rpx;
  border-radius: 12rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.yang-seal {
  background: var(--accent);
  box-shadow: 0 4rpx 12rpx rgba(176, 58, 46, 0.2);
}
.yin-seal {
  background: var(--jade);
  box-shadow: 0 4rpx 12rpx rgba(45, 90, 74, 0.2);
}
.mode-seal-char {
  color: #FFF8EE;
  font-size: 32rpx;
  line-height: 1;
}
.mode-tag {
  color: var(--ink-faint);
  font-size: 16rpx;
  letter-spacing: 0.18em;
}
.mode-title {
  display: block;
  margin-top: 20rpx;
  font-size: 32rpx;
  line-height: 1.4;
  color: var(--ink);
}
.mode-desc {
  display: block;
  margin-top: 10rpx;
  color: var(--ink-3);
  font-size: 22rpx;
  line-height: 1.75;
  flex: 1;
}
.mode-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
  margin: 16rpx 0;
}
.mode-tag-item {
  padding: 4rpx 14rpx;
  border-radius: var(--radius-sm);
  background: rgba(28, 26, 23, 0.04);
  color: var(--ink-3);
  font-size: 18rpx;
}
.mode-action {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid var(--line);
}
.mode-action-text {
  color: var(--accent);
  font-size: 24rpx;
  font-weight: 500;
}
.mode-action-arrow {
  color: var(--accent);
  font-size: 28rpx;
}

/* ═══ 快捷工具 ═══ */
.tools {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16rpx;
  margin-top: 24rpx;
}
.tool {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 28rpx 16rpx;
  border-radius: var(--radius);
  border: 1rpx solid var(--line);
  background: var(--surface);
  text-align: center;
  transition: all 0.2s ease;
}
.tool:active {
  transform: scale(0.96);
  background: var(--surface-warm);
}
.tool-icon {
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-2);
  border: 1rpx solid var(--line-gold);
}
.tool-icon-char {
  color: var(--accent);
  font-size: 28rpx;
}
.tool-name {
  margin-top: 14rpx;
  font-size: 26rpx;
  color: var(--ink);
  font-weight: 500;
}
.tool-hint {
  margin-top: 4rpx;
  color: var(--muted);
  font-size: 18rpx;
  line-height: 1.5;
}

/* ═══ 区域标题 ═══ */
.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin: 48rpx 0 24rpx;
}
.section-eyebrow {
  display: block;
  color: var(--gold);
  font-size: 18rpx;
  letter-spacing: 0.24em;
}
.section-title {
  display: block;
  margin-top: 6rpx;
  font-size: 36rpx;
  color: var(--ink);
}
.section-link {
  color: var(--accent);
  font-size: 24rpx;
  padding: 8rpx 0;
}

/* ═══ 最近档案 ═══ */
.recent-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.recent-item {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 28rpx 32rpx;
  border-radius: var(--radius);
  border: 1rpx solid var(--line);
  background: var(--surface);
  box-shadow: var(--shadow-card);
  transition: all 0.2s ease;
}
.recent-item:active {
  transform: scale(0.98);
  background: var(--surface-warm);
}
.recent-indicator {
  width: 6rpx;
  height: 48rpx;
  border-radius: 3rpx;
  flex-shrink: 0;
}
.yang-dot {
  background: var(--accent);
}
.yin-dot {
  background: var(--jade);
}
.recent-body {
  flex: 1;
  min-width: 0;
}
.recent-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.recent-title {
  font-size: 28rpx;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.recent-badge {
  flex-shrink: 0;
  padding: 2rpx 12rpx;
  border-radius: var(--radius-sm);
  font-size: 18rpx;
}
.yang-badge {
  background: var(--accent-soft);
  color: var(--accent);
}
.yin-badge {
  background: var(--jade-soft);
  color: var(--jade);
}
.recent-meta {
  display: block;
  margin-top: 8rpx;
  color: var(--ink-3);
  font-size: 23rpx;
}
.recent-time {
  display: block;
  margin-top: 4rpx;
  color: var(--muted);
  font-size: 20rpx;
}
.recent-arrow {
  color: var(--gold);
  font-size: 40rpx;
  flex-shrink: 0;
}

/* ═══ 空状态 ═══ */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
  padding: 64rpx 40rpx;
  text-align: center;
  border-radius: var(--radius);
  border: 1rpx solid var(--line);
  background: var(--surface);
}
.empty-seal {
  width: 88rpx;
  height: 88rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-2);
  border: 1rpx solid var(--line-gold);
}
.empty-seal-char {
  color: var(--gold);
  font-size: 36rpx;
}
.empty-title {
  font-size: 32rpx;
  color: var(--ink);
}
.empty-hint {
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.7;
}

/* ═══ 边界声明 ═══ */
.boundary {
  margin-top: 48rpx;
  padding: 0 8rpx;
}
.boundary-line {
  width: 48rpx;
  height: 2rpx;
  background: var(--gold);
  opacity: 0.4;
  margin-bottom: 16rpx;
}
.boundary-text {
  display: block;
  color: var(--muted);
  font-size: 21rpx;
  line-height: 1.8;
}
</style>
