<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    eyebrow?: string
    actionText?: string
  }>(),
  { title: '', eyebrow: '', actionText: '' }
)

const emit = defineEmits<{ (event: 'action'): void }>()
</script>

<template>
  <view class="section-card">
    <view v-if="title || eyebrow || actionText" class="head">
      <view class="head-text">
        <text v-if="eyebrow" class="eyebrow">{{ eyebrow }}</text>
        <text v-if="title" class="section-title serif">{{ title }}</text>
      </view>
      <button v-if="actionText" class="plain-button action" @click="emit('action')">
        {{ actionText }}
      </button>
    </view>
    <slot />
  </view>
</template>

<style scoped>
.section-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 30rpx;
  margin-top: 24rpx;
}
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
  margin-bottom: 20rpx;
}
.section-title {
  display: block;
  margin-top: 4rpx;
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 0.03em;
}
.action {
  flex-shrink: 0;
  color: var(--accent);
  font-size: 24rpx;
  padding-top: 8rpx;
}
</style>
