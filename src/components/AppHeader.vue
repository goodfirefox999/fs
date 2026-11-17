<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    title: string
    eyebrow?: string
    back?: boolean
    subtitle?: string
  }>(),
  { eyebrow: '', back: false, subtitle: '' }
)

const statusBar = computed(() => {
  try {
    return uni.getSystemInfoSync().statusBarHeight || 0
  } catch {
    return 0
  }
})

function goBack() {
  uni.navigateBack({
    fail: () => {
      uni.switchTab({ url: '/pages/index/index' })
    },
  })
}
</script>

<template>
  <view class="app-header" :style="{ paddingTop: statusBar + 'px' }">
    <view class="inner">
      <button v-if="back" class="back plain-button" @click="goBack">‹</button>
      <view class="titles">
        <text v-if="eyebrow" class="eyebrow">{{ eyebrow }}</text>
        <text class="display serif">{{ title }}</text>
        <text v-if="subtitle" class="subtitle">{{ subtitle }}</text>
      </view>
      <view class="right">
        <slot name="right" />
      </view>
    </view>
  </view>
</template>

<style scoped>
.app-header {
  padding-bottom: 24rpx;
}
.inner {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding: 28rpx var(--page-padding) 0;
  max-width: 1040rpx;
  margin: 0 auto;
}
.titles {
  flex: 1;
  min-width: 0;
}
.display {
  display: block;
  margin-top: 8rpx;
}
.subtitle {
  display: block;
  margin-top: 10rpx;
}
.back {
  width: 56rpx;
  height: 80rpx;
  line-height: 72rpx;
  font-size: 52rpx;
  color: var(--ink-3);
  padding: 0;
  background: transparent;
}
.right {
  flex-shrink: 0;
}
</style>
