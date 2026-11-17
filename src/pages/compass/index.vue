<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import AppHeader from '@/components/AppHeader.vue'
import CompassDial from '@/components/CompassDial.vue'
import {
  CITY_DECLINATIONS,
  CompassSampler,
} from '@/core/engines/compassMath'
import { SHAN_24_LIST } from '@/core/constants/shan24'
import type { InputMethod, NorthType, SceneMode } from '@/core/types'
import { normalizeDeg, resolveMountain, mountainOffset } from '@/core/constants/shan24'
import { useArchiveStore } from '@/stores/archive'
import { useDraftStore } from '@/stores/draft'
import { degreeText, offsetText, sittingFacingText } from '@/utils/display'

const archiveStore = useArchiveStore()
const draft = useDraftStore()
const archiveId = ref('')
const fromArchive = ref(false)
const mode = ref<SceneMode>('YANG')
const heading = ref(draft.compass.facingDeg)
const inputMethod = ref<InputMethod>(draft.compass.inputMethod)
const stability = ref(draft.compass.stability)
const samples = ref(0)
const locked = ref(false)
const sampling = ref(false)
const sensorError = ref('')
const manualValue = ref(draft.compass.facingDeg.toFixed(1))
const northType = ref<NorthType>(draft.compass.northType)
const declination = ref(draft.compass.declination)
const city = ref(draft.compass.city)
const cityNames = CITY_DECLINATIONS.map((item) => item.city)
const shanNames = SHAN_24_LIST.map((item) => item.name)
const cityIndex = computed(() =>
  Math.max(0, CITY_DECLINATIONS.findIndex((item) => item.city === city.value))
)
const shanIndex = computed(() => resolveMountain(heading.value).index)

const sampler = new CompassSampler(20)
const showBagua = ref(true)
const showFenJin = ref(false)

const size = computed(() => {
  try {
    const width = uni.getSystemInfoSync().windowWidth || 375
    return Math.min(Math.floor(width - 48), 360)
  } catch {
    return 320
  }
})

const current = computed(() => resolveMountain(heading.value))
const offset = computed(() => mountainOffset(heading.value, current.value))
const pair = computed(() => sittingFacingText(heading.value))
const sensorLabel = computed(() => {
  if (sampling.value) return `采样中 ${samples.value}/20`
  if (locked.value) return '读数已稳定'
  return '尚未采样'
})
const statusLabel = computed(() => {
  if (sampling.value) return '采样中'
  if (locked.value) return '可保存'
  return '待采样'
})

const northOptions = [
  { key: 'MAGNETIC', label: '磁北' },
  { key: 'TRUE', label: '真北' },
] as const

onLoad((query) => {
  archiveId.value = String(query?.id ?? '')
  if (query?.mode === 'YIN') mode.value = 'YIN'
  const archive = archiveId.value ? archiveStore.getById(archiveId.value) : undefined
  if (archive) {
    fromArchive.value = true
    mode.value = archive.mode
    const reading = archive.reading
    draft.setCompass({
      facingDeg: reading.facingDeg,
      inputMethod: reading.inputMethod,
      stability: reading.stability,
      uncertainty: reading.uncertainty,
      northType: reading.northType,
      declination: reading.declination,
      city: reading.city ?? '',
      confirmed: true,
    })
  }
  draft.setSceneMode(mode.value)
  heading.value = draft.compass.facingDeg
  inputMethod.value = draft.compass.inputMethod
  stability.value = draft.compass.stability
  northType.value = draft.compass.northType
  declination.value = draft.compass.declination
  city.value = draft.compass.city
  manualValue.value = draft.compass.facingDeg.toFixed(1)
  locked.value = fromArchive.value || draft.compass.inputMethod !== 'SENSOR'
})

onUnload(() => { stopSensor() })
onBeforeUnmount(() => { stopSensor() })

function pushSample(value: number) {
  if (!Number.isFinite(value)) return
  const result = sampler.push(value)
  heading.value = result.smoothDeg
  stability.value = result.stability
  samples.value = result.samples
  locked.value = result.isLocked
  inputMethod.value = 'SENSOR'
  manualValue.value = result.smoothDeg.toFixed(1)
}

// #ifdef MP-WEIXIN
function handleCompass(result: { direction: number }) {
  pushSample(result.direction)
}

function startSensor() {
  if (sampling.value) return
  sensorError.value = ''
  uni.startCompass({
    success: () => {
      sampling.value = true
      uni.onCompassChange(handleCompass)
    },
    fail: () => {
      sampling.value = false
      sensorError.value = '当前设备未提供方向传感器，请使用手动输入。'
    },
  })
}

function stopSensor() {
  if (sampling.value) {
    uni.stopCompass({})
    uni.offCompassChange(handleCompass)
  }
  sampling.value = false
}
// #endif

// #ifdef H5
type CompassHeadingEvent = DeviceOrientationEvent & { webkitCompassHeading?: number }
let h5Handler: ((event: Event) => void) | null = null

function startSensor() {
  if (sampling.value) return
  sensorError.value = ''
  if (typeof window === 'undefined' || typeof DeviceOrientationEvent === 'undefined') {
    sensorError.value = '当前浏览器未提供方向传感器，请使用手动输入。'
    return
  }
  const attach = () => {
    h5Handler = (event: Event) => {
      const orientation = event as CompassHeadingEvent
      let value: number | null = null
      if (typeof orientation.webkitCompassHeading === 'number') {
        value = orientation.webkitCompassHeading
      } else if (orientation.alpha !== null) {
        value = 360 - orientation.alpha
      }
      if (value === null) return
      pushSample(value)
    }
    window.addEventListener('deviceorientationabsolute', h5Handler, true)
    window.addEventListener('deviceorientation', h5Handler, true)
    sampling.value = true
  }
  const requestPermission = (
    DeviceOrientationEvent as unknown as { requestPermission?: () => Promise<string> }
  ).requestPermission
  if (typeof requestPermission === 'function') {
    requestPermission()
      .then((state) => {
        if (state === 'granted') attach()
        else sensorError.value = '方向权限未开启，请使用手动输入。'
      })
      .catch(() => {
        sensorError.value = '方向权限未开启，请使用手动输入。'
      })
  } else {
    attach()
  }
}

function stopSensor() {
  if (h5Handler) {
    window.removeEventListener('deviceorientationabsolute', h5Handler, true)
    window.removeEventListener('deviceorientation', h5Handler, true)
    h5Handler = null
  }
  sampling.value = false
}
// #endif

function toggleSensor() {
  if (sampling.value) stopSensor()
  else startSensor()
}

function applyManual() {
  const value = Number(manualValue.value)
  if (!Number.isFinite(value)) {
    uni.showToast({ title: '请输入有效的度数', icon: 'none' })
    return
  }
  stopSensor()
  sampler.reset()
  heading.value = normalizeDeg(value)
  stability.value = 100
  samples.value = 0
  locked.value = true
  inputMethod.value = 'MANUAL_DEG'
}

function pickMountain(event: { detail: { value: number | string } }) {
  const meta = SHAN_24_LIST[Number(event.detail.value)]
  if (!meta) return
  stopSensor()
  sampler.reset()
  heading.value = meta.centerDeg
  manualValue.value = meta.centerDeg.toFixed(1)
  stability.value = 100
  samples.value = 0
  locked.value = true
  inputMethod.value = 'MANUAL_SHAN'
}

function pickCity(event: { detail: { value: number | string } }) {
  const item = CITY_DECLINATIONS[Number(event.detail.value)]
  if (!item) return
  city.value = item.city
  declination.value = item.declination
}

function setNorth(type: NorthType) {
  northType.value = type
}

function onDeclinationBlur(event: { detail: { value: string } }) {
  const value = Number(event.detail.value)
  if (Number.isFinite(value)) declination.value = value
}

function save(openWizard = false) {
  if (inputMethod.value === 'SENSOR' && samples.value === 0 && !fromArchive.value) {
    uni.showToast({ title: '请先完成一次采样或手动输入', icon: 'none' })
    return
  }
  stopSensor()
  const effectiveStability = inputMethod.value === 'SENSOR' ? stability.value : 100
  draft.setCompass({
    facingDeg: normalizeDeg(heading.value),
    inputMethod: inputMethod.value,
    stability: effectiveStability,
    uncertainty:
      inputMethod.value === 'SENSOR'
        ? Number(Math.max(0.5, (100 - effectiveStability) / 10).toFixed(1))
        : 0.5,
    northType: northType.value,
    declination: declination.value,
    city: city.value,
    confirmed: true,
  })
  draft.setSceneMode(mode.value)
  if (archiveId.value) {
    archiveStore.update(archiveId.value, { reading: draft.toReading() })
  }
  if (openWizard) {
    uni.redirectTo({ url: `/pages/wizard/index?mode=${mode.value}` })
  } else {
    uni.navigateBack({
      fail: () => uni.switchTab({ url: '/pages/index/index' }),
    })
  }
}
</script>

<template>
  <view class="page">
    <AppHeader
      eyebrow="方位采样"
      title="罗盘定向"
      subtitle="将手机水平放置，顶部指向房屋正面，待读数稳定后保存。"
      back
    >
      <template #right>
        <view class="chip" :class="locked ? 'jade' : 'gold'">{{ statusLabel }}</view>
      </template>
    </AppHeader>

    <view class="shell">

      <!-- ═══ 罗盘主体 ═══ -->
      <view class="dial-section">
        <view class="layer-row">
          <button class="layer-chip" :class="{ active: showBagua }" @click="showBagua = !showBagua">后天八卦</button>
          <button class="layer-chip" :class="{ active: showFenJin }" @click="showFenJin = !showFenJin">一百二十分金</button>
          <text class="tiny muted">
            {{ showFenJin ? '绿线为旺相分金，红为龟甲空亡，黄为孤虚；仅作线度参考。' : '叠加分金层可核对旺相与空亡线位。' }}
          </text>
        </view>
        <CompassDial
          :size="size"
          :heading="heading"
          :locked-deg="locked ? heading : null"
          :show-bagua="showBagua"
          :show-fen-jin="showFenJin"
        />

        <!-- 读数面板 -->
        <view class="readout">
          <view class="readout-main">
            <text class="readout-shan serif">{{ current.name }}山</text>
            <text class="readout-deg serif">{{ degreeText(heading) }}</text>
          </view>
          <view class="readout-pair">
            <text class="readout-pair-text serif">{{ pair.text }}</text>
            <text class="readout-offset" :class="{ warn: Math.abs(offset) > 4.5 }">
              {{ offsetText(heading) }}
            </text>
          </view>
        </view>

        <!-- 稳定性 -->
        <view class="stability">
          <view class="stability-row">
            <text class="stability-label">{{ sensorLabel }}</text>
            <text class="stability-value" :class="{ good: stability >= 92, mid: stability >= 85 && stability < 92 }">
              {{ Math.round(stability) }}%
            </text>
          </view>
          <view class="stability-track">
            <view
              class="stability-fill"
              :class="{ good: stability >= 92, mid: stability >= 85 && stability < 92 }"
              :style="{ width: Math.max(2, Math.min(100, stability)) + '%' }"
            />
          </view>
          <text v-if="Math.abs(offset) > 4.5" class="hint warn stability-hint">
            偏离{{ current.name }}山中线 {{ Math.abs(offset).toFixed(1) }}°，属于兼向范围，排盘将按替卦处理。
          </text>
        </view>
      </view>

      <!-- ═══ 采样控制 ═══ -->
      <view class="card">
        <view class="card-title">
          <text>传感器采样</text>
          <text class="badge" :class="sampling ? 'info' : ''">{{ samples }}/20</text>
        </view>
        <text class="hint">
          站在开阔处，远离金属门窗与电子设备，手机保持水平。取最近 20 个读数的圆均值，稳定性达 92% 后可保存。
        </text>
        <view class="row btn-row">
          <button class="btn" :class="sampling ? 'btn-ghost' : 'btn-primary'" @click="toggleSensor">
            {{ sampling ? '停止采样' : '开始采样' }}
          </button>
          <button class="btn btn-ghost" @click="applyManual">采信手动度数</button>
        </view>
        <text v-if="sensorError" class="hint warn">{{ sensorError }}</text>
      </view>

      <!-- ═══ 手动输入 ═══ -->
      <view class="card">
        <view class="card-title"><text>手动输入</text></view>
        <view class="field">
          <text class="field-label">朝向度数（正北 0°，顺时针）</text>
          <view class="row">
            <input v-model="manualValue" class="input" type="digit" placeholder="例如 180.0" confirm-type="done" @confirm="applyManual" />
            <button class="btn btn-ghost btn-sm input-apply" @click="applyManual">应用</button>
          </view>
        </view>
        <view class="divider" />
        <view class="field">
          <text class="field-label">按山中线取整</text>
          <picker mode="selector" :range="shanNames" :value="shanIndex" @change="pickMountain">
            <view class="picker-field row-between">
              <text>{{ current.name }}山 · 中线 {{ current.centerDeg.toFixed(1) }}°</text>
              <text class="muted">切换 ›</text>
            </view>
          </picker>
          <text class="hint">选择山中线将读数设为该山正中，适合已知坐向时快速记录。</text>
        </view>
      </view>

      <!-- ═══ 北向与磁偏角 ═══ -->
      <view class="card">
        <view class="card-title"><text>北向与磁偏角</text></view>
        <view class="setting-row">
          <text class="setting-label">读数口径</text>
          <view class="mini-seg">
            <button v-for="item in northOptions" :key="item.key" class="mini-seg-item" :class="{ active: northType === item.key }" @click="setNorth(item.key)">
              {{ item.label }}
            </button>
          </view>
        </view>
        <view class="divider" />
        <view class="setting-row">
          <text class="setting-label">参考城市</text>
          <picker mode="selector" :range="cityNames" :value="cityIndex" @change="pickCity">
            <view class="picker-value">{{ city || '未选择' }}<text class="picker-arrow">›</text></view>
          </picker>
        </view>
        <view class="divider" />
        <view class="setting-row">
          <text class="setting-label">磁偏角</text>
          <input class="mini-input" type="digit" :value="String(declination)" @blur="onDeclinationBlur" />
        </view>
        <text class="hint setting-hint">
          东偏为正、西偏为负。读数只按当前口径记录，不自动换算。
        </text>
      </view>

      <view class="bottom-note">
        <text class="hint">
          手机磁场传感器受金属与电子设备影响较大。涉及立向、施工或纪念地事项时，请用实体罗盘现场复核。
        </text>
      </view>

    </view>

    <view class="action-bar">
      <button class="btn btn-ghost" @click="save(false)">保存读数</button>
      <button class="btn btn-primary" @click="save(true)">去建档</button>
    </view>
  </view>
</template>

<style scoped>
.page {
  padding-bottom: calc(170rpx + env(safe-area-inset-bottom));
}

/* ── 罗盘主体 ── */
.layer-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 14rpx;
}
.layer-chip {
  min-height: 48rpx;
  padding: 0 16rpx;
  border-radius: 999rpx;
  border: 1px solid var(--line);
  background: #fffdf8;
  color: var(--ink-2);
  font-size: 20rpx;
  line-height: 48rpx;
}
.layer-chip::after {
  border: none;
}
.layer-chip.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
}
.dial-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32rpx 24rpx 28rpx;
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, #FDFAF4 0%, #F0EADC 100%);
  border: 1rpx solid var(--line-gold);
  box-shadow: var(--shadow-hero);
}

.readout {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin-top: 28rpx;
  padding-top: 24rpx;
  border-top: 1rpx solid var(--line-gold);
}
.readout-main {
  text-align: left;
}
.readout-shan {
  display: block;
  font-size: 48rpx;
  line-height: 1.2;
  color: var(--accent);
}
.readout-deg {
  display: block;
  margin-top: 4rpx;
  font-size: 30rpx;
  color: var(--ink-2);
  letter-spacing: 0.04em;
}
.readout-pair {
  text-align: right;
}
.readout-pair-text {
  display: block;
  font-size: 28rpx;
  color: var(--ink);
}
.readout-offset {
  display: block;
  margin-top: 4rpx;
  color: var(--muted);
  font-size: 21rpx;
}

.stability {
  width: 100%;
  margin-top: 24rpx;
}
.stability-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8rpx;
}
.stability-label {
  font-size: 22rpx;
  color: var(--muted);
}
.stability-value {
  font-size: 24rpx;
  font-weight: 600;
  color: var(--ink-2);
}
.stability-value.good { color: var(--jade); }
.stability-value.mid { color: var(--gold); }
.stability-track {
  height: 8rpx;
  border-radius: 4rpx;
  background: rgba(28, 26, 23, 0.06);
  overflow: hidden;
}
.stability-fill {
  height: 100%;
  border-radius: 4rpx;
  background: var(--accent);
  transition: width 0.3s ease;
}
.stability-fill.mid { background: var(--gold); }
.stability-fill.good { background: var(--jade); }
.stability-hint {
  display: block;
  margin-top: 12rpx;
}

/* ── 按钮行 ── */
.btn-row {
  margin-top: 20rpx;
}
.btn-row .btn { flex: 1; }
.input-apply {
  flex-shrink: 0;
  min-width: 120rpx;
}

/* ── 设置行 ── */
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  min-height: 80rpx;
}
.setting-label {
  color: var(--ink-2);
  font-size: 25rpx;
}
.setting-hint {
  display: block;
  margin-top: 16rpx;
}
.mini-seg {
  display: flex;
  padding: 4rpx;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}
.mini-seg-item {
  min-height: 52rpx;
  padding: 0 24rpx;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--ink-2);
  font-size: 22rpx;
  line-height: 52rpx;
}
.mini-seg-item::after { border: none; }
.mini-seg-item.active {
  background: var(--surface);
  color: var(--ink);
  box-shadow: 0 2rpx 8rpx rgba(28, 26, 23, 0.06);
}
.picker-value {
  display: flex;
  align-items: center;
  gap: 8rpx;
  color: var(--accent);
  font-size: 25rpx;
}
.picker-arrow {
  color: var(--gold);
  font-size: 32rpx;
}
.mini-input {
  width: 160rpx;
  height: 68rpx;
  padding: 0 16rpx;
  border: 1rpx solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--surface-warm);
  text-align: right;
  font-size: 25rpx;
}
.bottom-note {
  margin: 28rpx 8rpx 0;
}

/* ── 底部操作栏 ── */
.action-bar {
  position: fixed;
  left: 0; right: 0; bottom: 0;
  display: flex;
  gap: 20rpx;
  padding: 20rpx var(--page-padding) calc(20rpx + env(safe-area-inset-bottom));
  background: rgba(247, 243, 236, 0.96);
  border-top: 1rpx solid var(--line);
  backdrop-filter: blur(16px);
  z-index: 20;
}
.action-bar .btn { flex: 1; }
</style>
