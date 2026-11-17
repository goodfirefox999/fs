<script setup lang="ts">
import { computed } from 'vue'
import type { PalaceId, XuanKongChart } from '@/core/types'
import { GRID_ORDER, PALACES } from '@/core/constants/luoshu'

const props = withDefaults(
  defineProps<{
    chart: XuanKongChart
    selected?: PalaceId | null
    showAnnual?: boolean
    showMonthly?: boolean
  }>(),
  { selected: null, showAnnual: true, showMonthly: true }
)

const emit = defineEmits<{ (event: 'select', palace: PalaceId): void }>()

const cells = computed(() =>
  GRID_ORDER.map((palace) => {
    const cell = props.chart.palaces.find((item) => item.palace === palace)
    if (!cell) throw new Error(`缺少宫位 ${palace}`)
    return { ...cell, meta: PALACES[palace] }
  })
)

function tone(star: number): string {
  if (star === 5) return 'gold'
  if (star === 2 || star === 7) return 'caution'
  if (star === 8 || star === 9) return 'good'
  return 'plain'
}
</script>

<template>
  <view class="palace-grid">
    <view
      v-for="cell in cells"
      :key="cell.palace"
      class="palace"
      :class="{
        center: cell.palace === 5,
        selected: selected === cell.palace,
      }"
      @click="emit('select', cell.palace)"
    >
      <!-- 宫位方位 -->
      <view class="palace-head">
        <text class="direction">{{ cell.direction }}</text>
        <text class="trigram serif">{{ cell.meta.trigram }}</text>
      </view>

      <!-- 山星 · 向星 -->
      <view class="stars">
        <view class="star" :class="tone(cell.shan)">
          <text class="star-label">山</text>
          <text class="star-num serif">{{ cell.shan }}</text>
        </view>
        <view class="star" :class="tone(cell.xiang)">
          <text class="star-label">向</text>
          <text class="star-num serif">{{ cell.xiang }}</text>
        </view>
      </view>

      <!-- 运 / 年 / 月 -->
      <view class="palace-foot">
        <text class="foot-item">运{{ cell.yun }}</text>
        <text v-if="showAnnual && cell.annual" class="foot-item">年{{ cell.annual }}</text>
        <text v-if="showMonthly && cell.monthly" class="foot-item">月{{ cell.monthly }}</text>
      </view>

      <!-- 中宫格局标签 -->
      <text v-if="cell.palace === 5" class="center-pattern serif">{{ chart.patternLabel }}</text>
    </view>
  </view>
</template>

<style scoped>
.palace-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6rpx;
  padding: 6rpx;
  background: #E8DFCE;
  border-radius: var(--radius);
  border: 1rpx solid var(--line-gold);
}
.palace {
  position: relative;
  min-height: 180rpx;
  padding: 14rpx 12rpx;
  background: #FDFAF4;
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: all 0.15s ease;
}
.palace:active {
  background: #F5EFE3;
}
.palace.center {
  background: #F0EADC;
}
.palace.selected {
  outline: 2rpx solid var(--accent);
  outline-offset: -2rpx;
  background: #FDF5F0;
}

/* 方位行 */
.palace-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 6rpx;
}
.direction {
  color: var(--ink-3);
  font-size: 20rpx;
  letter-spacing: 0.06em;
}
.trigram {
  color: var(--gold);
  font-size: 28rpx;
  line-height: 1;
  opacity: 0.7;
}

/* 山向星 */
.stars {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  margin: 6rpx 0;
}
.star {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  border: 1rpx solid var(--line);
  background: #FFFDF8;
}
.star-label {
  font-size: 16rpx;
  line-height: 1;
  color: var(--muted);
}
.star-num {
  font-size: 30rpx;
  line-height: 1.15;
  font-weight: 600;
  color: var(--ink);
}
.star.good {
  background: var(--jade-soft);
  border-color: rgba(45, 90, 74, 0.2);
}
.star.good .star-num {
  color: var(--jade);
}
.star.gold {
  background: var(--gold-soft);
  border-color: rgba(160, 128, 72, 0.25);
}
.star.gold .star-num {
  color: #7D6332;
}
.star.caution {
  background: var(--danger-soft);
  border-color: rgba(142, 59, 47, 0.15);
}
.star.caution .star-num {
  color: var(--danger);
}

/* 运/年/月 */
.palace-foot {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
}
.foot-item {
  color: var(--muted);
  font-size: 18rpx;
  line-height: 1.2;
}

/* 中宫格局 */
.center-pattern {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 28rpx;
  text-align: center;
  color: var(--accent);
  font-size: 16rpx;
  letter-spacing: 0.06em;
  opacity: 0.8;
}
</style>
