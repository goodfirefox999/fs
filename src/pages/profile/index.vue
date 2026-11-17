<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { CITY_DECLINATIONS, nearestCity } from '@/core/engines/compassMath'
import { callCloudFunction } from '@/services/cloud'
import { useAppStore } from '@/stores/app'
import { useArchiveStore } from '@/stores/archive'
import { useDraftStore } from '@/stores/draft'
import { formatTimestamp } from '@/utils/display'

const appStore = useAppStore()
const archiveStore = useArchiveStore()
const draft = useDraftStore()

const isDevPreview = import.meta.env.DEV

const cityNames = CITY_DECLINATIONS.map((item) => item.city)
const selectedCityIndex = computed(() =>
  Math.max(
    0,
    CITY_DECLINATIONS.findIndex((item) => item.city === appStore.settings.city)
  )
)
const northOptions = [
  { key: 'MAGNETIC', label: '磁北' },
  { key: 'TRUE', label: '真北' },
] as const

const contentState = computed(() => {
  if (appStore.content) return `已加载 ${appStore.content.shuangxing.length} 组内容 · ${appStore.content.version}`
  if (appStore.contentLoading) return '正在加载内容包…'
  if (appStore.contentError) return appStore.contentError
  return '尚未加载内容包'
})

const unlockedList = computed(() =>
  appStore.unlockedIds.map((id) => ({
    id,
    archive: archiveStore.getById(id),
  }))
)

onShow(() => {
  const target = appStore.unlockedIds[0]
  if (target && !appStore.content && !appStore.contentLoading) {
    void appStore.loadContent(target)
  }
})

const feedbackText = ref('')
const feedbackContact = ref('')
const feedbackSending = ref(false)

async function submitFeedback() {
  if (feedbackSending.value) return
  const content = feedbackText.value.trim()
  if (content.length < 4) {
    uni.showToast({ title: '请填写至少 4 个字的反馈', icon: 'none' })
    return
  }
  feedbackSending.value = true
  try {
    await callCloudFunction('feedback', {
      content,
      contact: feedbackContact.value.trim(),
      category: 'APP',
    })
    feedbackText.value = ''
    feedbackContact.value = ''
    uni.showToast({ title: '反馈已提交，感谢', icon: 'none' })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : '提交失败，请稍后再试',
      icon: 'none',
    })
  } finally {
    feedbackSending.value = false
  }
}

function pickCity(event: { detail: { value: number | string } }) {
  const index = Number(event.detail.value)
  const city = CITY_DECLINATIONS[index]
  if (!city) return
  appStore.setSettings({ city: city.city, declination: city.declination })
  draft.setCompass({ city: city.city, declination: city.declination })
}

function autoCity() {
  // #ifdef MP-WEIXIN
  uni.getLocation({
    type: 'wgs84',
    success: (result) => {
      const city = nearestCity(result.latitude, result.longitude)
      appStore.setSettings({ city: city.city, declination: city.declination })
      draft.setCompass({ city: city.city, declination: city.declination })
      uni.showToast({ title: `已选择${city.city}`, icon: 'none' })
    },
    fail: () => {
      uni.showToast({ title: '定位未授权，可手动选择城市', icon: 'none' })
    },
  })
  // #endif
  // #ifndef MP-WEIXIN
  uni.showToast({ title: '请在微信小程序中使用定位', icon: 'none' })
  // #endif
}

function setNorth(type: 'MAGNETIC' | 'TRUE') {
  appStore.setSettings({ northType: type })
  draft.setCompass({ northType: type })
}

function setDeclination(value: string) {
  const dec = Number(value)
  if (!Number.isFinite(dec)) return
  appStore.setSettings({ declination: dec })
  draft.setCompass({ declination: dec })
}

function onDeclinationBlur(event: { detail: { value: string } }) {
  setDeclination(String(event.detail.value ?? ''))
}

async function refreshContent() {
  const target = appStore.unlockedIds[0]
  if (!target) {
    uni.showToast({ title: '解锁一份完整分析后可加载内容包', icon: 'none' })
    return
  }
  await appStore.loadContent(target, true)
  uni.showToast({
    title: appStore.content ? '内容包已更新' : appStore.contentError || '加载失败',
    icon: 'none',
  })
}

function openGuide() {
  uni.navigateTo({ url: '/pages/guide/index' })
}

function openReport(id: string) {
  uni.navigateTo({ url: `/pages/report/index?id=${id}` })
}

function clearArchives() {
  uni.showModal({
    title: '清空档案',
    content: '将删除本机全部环境档案与当前选择，已购权益不受影响。',
    confirmText: '清空',
    confirmColor: '#8E3B2F',
    success: (result) => {
      if (!result.confirm) return
      archiveStore.clear()
      uni.showToast({ title: '已清空档案', icon: 'none' })
    },
  })
}

function clearAll() {
  uni.showModal({
    title: '清空本地数据',
    content: '将删除档案、权益缓存与个性化设置；云端购买记录不会随本机数据删除。',
    confirmText: '全部清空',
    confirmColor: '#8E3B2F',
    success: (result) => {
      if (!result.confirm) return
      appStore.clearLocal()
      archiveStore.clear()
      draft.reset()
      uni.showToast({ title: '已清空本地数据', icon: 'none' })
    },
  })
}

function grantDev() {
  appStore.grantEntitlement('__dev_all__')
  uni.showToast({ title: '已开启本地内容预览', icon: 'none' })
}

function resetDev() {
  appStore.resetEntitlements()
  uni.showToast({ title: '已重置权益缓存', icon: 'none' })
}
</script>

<template>
  <view class="page with-tab">
    <view class="shell">
      <view class="page-head">
        <text class="eyebrow">PROFILE</text>
        <text class="head-title serif">我的</text>
        <text class="head-sub">设置、权益与数据管理。</text>
      </view>

      <view class="card summary-card">
        <view class="summary-item">
          <text class="summary-num serif">{{ archiveStore.archives.length }}</text>
          <text class="summary-label">本机档案</text>
        </view>
        <view class="summary-line" />
        <view class="summary-item">
          <text class="summary-num serif">{{ appStore.unlockedIds.length }}</text>
          <text class="summary-label">已解锁报告</text>
        </view>
        <view class="summary-line" />
        <view class="summary-item">
          <text class="summary-num serif">{{ appStore.content ? '81' : '—' }}</text>
          <text class="summary-label">内容组合</text>
        </view>
      </view>

      <view class="section-label">方位设置</view>
      <view class="card">
        <view class="setting-row">
          <view class="setting-main">
            <text class="setting-title">所在城市</text>
            <text class="setting-desc">用于填入参考磁偏角，可在罗盘页单独调整。</text>
          </view>
          <picker
            mode="selector"
            :range="cityNames"
            :value="selectedCityIndex"
            @change="pickCity"
          >
            <view class="picker-value">
              {{ appStore.settings.city || '未选择' }}
              <text class="picker-arrow">›</text>
            </view>
          </picker>
        </view>
        <view class="divider" />
        <view class="setting-row">
          <view class="setting-main">
            <text class="setting-title">磁偏角</text>
            <text class="setting-desc">东偏为正，西偏为负。仅作为读数记录，不自动换算。</text>
          </view>
          <input
            class="mini-input"
            type="digit"
            :value="String(appStore.settings.declination)"
            @blur="onDeclinationBlur"
          />
        </view>
        <view class="divider" />
        <view class="setting-row">
          <view class="setting-main">
            <text class="setting-title">北向口径</text>
            <text class="setting-desc">记录当前档案采用磁北还是真北读数。</text>
          </view>
          <view class="mini-seg">
            <button
              v-for="item in northOptions"
              :key="item.key"
              class="mini-seg-item"
              :class="{ active: appStore.settings.northType === item.key }"
              @click="setNorth(item.key)"
            >
              {{ item.label }}
            </button>
          </view>
        </view>
        <button class="btn btn-ghost btn-sm locate" @click="autoCity">按当前位置推荐城市</button>
      </view>

      <view class="section-label">内容与权益</view>
      <view class="card">
        <view class="row-between">
          <view class="setting-main">
            <text class="setting-title">完整内容包</text>
            <text class="setting-desc">{{ contentState }}</text>
          </view>
          <button class="btn btn-ghost btn-sm" :disabled="appStore.contentLoading" @click="refreshContent">
            刷新
          </button>
        </view>
        <view class="divider" />
        <view v-if="unlockedList.length" class="unlock-list">
          <view
            v-for="item in unlockedList"
            :key="item.id"
            class="unlock-item"
            @click="item.archive ? openReport(item.archive.id) : null"
          >
            <view class="unlock-main">
              <text class="unlock-title">{{ item.archive?.title || '已删除的档案' }}</text>
              <text class="unlock-meta tiny muted">
                {{ item.archive ? `更新于 ${formatTimestamp(item.archive.updatedAt)}` : item.id }}
              </text>
            </view>
            <text class="chip jade">已解锁</text>
          </view>
        </view>
        <text v-else class="hint">尚未解锁完整分析。每份档案可单独解锁，不自动续费。</text>
      </view>

      <view class="section-label">数据与支持</view>
      <view class="card menu-card">
        <button class="menu-item" @click="openGuide">
          <text>使用说明与边界</text>
          <text class="menu-arrow">›</text>
        </button>
        <button class="menu-item" @click="clearArchives">
          <text>清空本机档案</text>
          <text class="menu-arrow">›</text>
        </button>
        <button class="menu-item danger-text" @click="clearAll">
          <text>清空全部本地数据</text>
          <text class="menu-arrow">›</text>
        </button>
      </view>

      <view class="card feedback-card">
        <view class="card-title"><text>意见反馈</text></view>
        <textarea
          v-model="feedbackText"
          class="textarea"
          maxlength="500"
          placeholder="遇到问题或有建议，可以写在这里"
        />
        <input
          v-model="feedbackContact"
          class="input feedback-contact"
          type="text"
          placeholder="联系方式（选填）"
        />
        <button class="btn btn-primary feedback-submit" :disabled="feedbackSending" @click="submitFeedback">
          {{ feedbackSending ? '提交中…' : '提交反馈' }}
        </button>
        <text class="hint">反馈会附带当前微信身份，仅用于问题排查。</text>
      </view>

      <!-- #ifdef H5 -->
      <view v-if="isDevPreview" class="dev-card">
        <text class="dev-title">开发预览（仅 H5 本地开发可见）</text>
        <text class="dev-desc">
          用于在浏览器中检查完整内容与报告排版，不会出现在小程序正式版本中。
        </text>
        <view class="row">
          <button class="btn btn-ghost btn-sm" @click="grantDev">开启内容预览</button>
          <button class="btn btn-ghost btn-sm" @click="resetDev">重置权益缓存</button>
        </view>
      </view>
      <!-- #endif -->

      <view class="version">
        <text>居境罗盘 · 传统人居环境方位参考工具</text>
        <text>档案格式 v1 · 内容包 {{ appStore.content?.version || '待加载' }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page-head {
  padding: 30rpx 4rpx 26rpx;
  border-bottom: 1rpx solid var(--line-gold);
}
.head-title {
  display: block;
  margin-top: 6rpx;
  color: var(--ink);
  font-size: 44rpx;
  letter-spacing: 0.1em;
}
.head-sub {
  display: block;
  margin-top: 8rpx;
  color: var(--ink-3);
  font-size: 22rpx;
  line-height: 1.7;
}
.card {
  border: 1rpx solid var(--line);
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.summary-card {
  display: flex;
  align-items: center;
  padding: 34rpx 20rpx;
  border: 1rpx solid var(--line-gold);
  border-top: 4rpx solid var(--gold);
  background: linear-gradient(135deg, var(--surface-warm) 0%, var(--surface-2) 100%);
  box-shadow: var(--shadow-card);
}
.summary-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
}
.summary-num {
  color: var(--accent-deep);
  font-size: 46rpx;
  line-height: 1.2;
}
.summary-label {
  color: var(--ink-3);
  font-size: 21rpx;
  letter-spacing: 0.08em;
}
.summary-line {
  width: 1rpx;
  height: 62rpx;
  background: var(--line-gold);
}
.section-label {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin: 40rpx 6rpx 16rpx;
  color: var(--ink-3);
  font-size: 22rpx;
  letter-spacing: 0.18em;
}
.section-label::before {
  width: 5rpx;
  height: 24rpx;
  border-radius: 2rpx;
  background: var(--accent);
  content: '';
}
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  min-height: 112rpx;
}
.setting-main {
  flex: 1;
  min-width: 0;
}
.setting-title {
  display: block;
  color: var(--ink);
  font-size: 27rpx;
  font-weight: 500;
  letter-spacing: 0.03em;
}
.setting-desc {
  display: block;
  margin-top: 7rpx;
  color: var(--muted);
  font-size: 21rpx;
  line-height: 1.7;
}
.picker-value {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8rpx;
  min-width: 150rpx;
  color: var(--accent-deep);
  font-size: 25rpx;
}
.picker-arrow {
  color: var(--gold);
  font-size: 32rpx;
  line-height: 1;
}
.mini-input {
  width: 150rpx;
  height: 64rpx;
  padding: 0 16rpx;
  border: 1rpx solid var(--line-gold);
  border-radius: var(--radius-sm);
  background: var(--surface-warm);
  color: var(--ink);
  font-size: 25rpx;
  text-align: right;
}
.mini-seg {
  display: flex;
  flex-shrink: 0;
  padding: 4rpx;
  border: 1rpx solid var(--line);
  border-radius: 999rpx;
  background: var(--surface-2);
}
.mini-seg-item {
  min-height: 52rpx;
  padding: 0 20rpx;
  border-radius: 999rpx;
  background: transparent;
  color: var(--ink-3);
  font-size: 22rpx;
  line-height: 52rpx;
}
.mini-seg-item::after {
  border: none;
}
.mini-seg-item.active {
  background: var(--surface);
  color: var(--accent-deep);
  box-shadow: 0 2rpx 10rpx var(--line-strong);
}
.locate {
  width: 100%;
  margin-top: 24rpx;
  color: var(--jade);
}
.divider {
  height: 1rpx;
  background: var(--line);
}
.row-between {
  gap: 20rpx;
}
.unlock-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.unlock-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
  padding: 20rpx;
  border: 1rpx solid var(--line);
  border-left: 3rpx solid var(--jade);
  border-radius: var(--radius-sm);
  background: var(--surface-warm);
}
.unlock-main {
  min-width: 0;
}
.unlock-title {
  display: block;
  overflow: hidden;
  color: var(--ink);
  font-size: 25rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.unlock-meta {
  display: block;
  margin-top: 5rpx;
}
.menu-card {
  padding: 0 28rpx;
  border: 1rpx solid var(--line-gold);
  background: var(--surface);
}
.menu-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 100rpx;
  padding: 0 4rpx;
  background: transparent;
  color: var(--ink);
  font-size: 27rpx;
  line-height: 1.4;
  text-align: left;
  letter-spacing: 0.03em;
}
.menu-item::after {
  border: none;
}
.menu-item + .menu-item {
  border-top: 1rpx solid var(--line);
}
.menu-arrow {
  color: var(--gold);
  font-size: 34rpx;
  font-weight: 300;
}
.danger-text {
  color: var(--danger);
}
.feedback-card {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
  margin-top: 30rpx;
  border: 1rpx solid var(--line-gold);
  border-top: 4rpx solid var(--gold);
  background: var(--surface-warm);
  box-shadow: var(--shadow-card);
}
.feedback-card .card-title {
  color: var(--accent-deep);
  letter-spacing: 0.08em;
}
.feedback-card .textarea,
.feedback-card .input {
  border: 1rpx solid var(--line-gold);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--ink);
}
.feedback-contact {
  height: 76rpx;
}
.feedback-submit {
  width: 100%;
  letter-spacing: 0.1em;
}
.feedback-card .hint {
  color: var(--muted);
  line-height: 1.7;
}
.dev-card {
  margin-top: 32rpx;
  padding: 24rpx 28rpx;
  border: 1rpx dashed var(--line-gold);
  border-radius: var(--radius);
  background: var(--gold-soft);
}
.dev-title {
  display: block;
  color: var(--gold);
  font-size: 23rpx;
  font-weight: 600;
}
.dev-desc {
  display: block;
  margin: 8rpx 0 16rpx;
  color: var(--ink-2);
  font-size: 21rpx;
  line-height: 1.7;
}
.version {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  margin-top: 44rpx;
  padding: 24rpx 0 20rpx;
  border-top: 1rpx solid var(--line);
  color: var(--muted);
  font-size: 20rpx;
  line-height: 1.7;
  text-align: center;
}
</style>
