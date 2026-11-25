<script setup lang="ts">
/**
 * 桌面罗盘（SVG）。
 *
 * 为什么不用 `src/components/CompassDial.vue`：那个组件依赖 `uni.createCanvasContext`，
 * 只在 uni-app 运行时可用；且 canvas 需要等 80ms 才能绘制，尺寸变化要重绘。
 * SVG 在 Electron 里直接可渲染，矢量、可缩放、能原样嵌进导出的报告。
 */
import { computed } from 'vue'
import { SHAN_NAMES } from '@core/constants/shan24'
import { resolveFenJin } from '@core/constants/fenjin120'

const props = withDefaults(
  defineProps<{
    /** 真北坐山线度（0–360） */
    deg: number
    /** 是否显示分金文字 */
    showFenJin?: boolean
  }>(),
  { showFenJin: true },
)

const C = 200
const R_OUT = 190
const R_SHAN_IN = 150
const R_GUA_IN = 110

const TRIGRAMS = ['坎', '艮', '震', '巽', '离', '坤', '兑', '乾']

function polar(deg: number, r: number) {
  const rad = ((deg - 90) * Math.PI) / 180
  return { x: C + Math.cos(rad) * r, y: C + Math.sin(rad) * r }
}

function sectorPath(startDeg: number, endDeg: number, r: number): string {
  const a = polar(startDeg, r)
  const b = polar(endDeg, r)
  const large = endDeg - startDeg > 180 ? 1 : 0
  return `M ${C} ${C} L ${a.x.toFixed(2)} ${a.y.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${b.x.toFixed(2)} ${b.y.toFixed(2)} Z`
}

const normalized = computed(() => ((props.deg % 360) + 360) % 360)
const current = computed(() => getMountainByDeg(normalized.value))
const fenJin = computed(() => resolveFenJin(normalized.value))

function getMountainByDeg(deg: number) {
  const index = Math.floor(((deg + 7.5) % 360) / 15) % 24
  return { index, name: SHAN_NAMES[index] }
}

const highlight = computed(() => {
  const center = current.value.index * 15
  return sectorPath(center - 7.5, center + 7.5, R_OUT)
})

/** 指针：从中心指向当前线度方向（罗盘 0° 在上，故直接用 deg）。 */
const needle = computed(() => {
  const tip = polar(normalized.value, R_GUA_IN - 12)
  const tail = polar(normalized.value + 180, R_GUA_IN * 0.45)
  return { tip, tail }
})

const shanLabel = computed(() => SHAN_NAMES.map((name, index) => ({
  name,
  angle: index * 15,
  cardinal: ['子', '卯', '午', '酉'].includes(name),
  branch: index % 2 === 0,
})))

const guaLabel = computed(() => TRIGRAMS.map((name, index) => ({
  name,
  angle: index * 45,
  cardinal: [0, 2, 4, 6].includes(index),
})))
</script>

<template>
  <svg class="compass" viewBox="0 0 400 400" role="img" aria-label="二十四山罗盘">
    <defs>
      <radialGradient id="paper" cx="50%" cy="45%" r="70%">
        <stop offset="0%" stop-color="#FFFDF8" />
        <stop offset="100%" stop-color="#F1E8D8" />
      </radialGradient>
    </defs>

    <circle :cx="C" :cy="C" :r="R_OUT" fill="#2C2420" />
    <circle :cx="C" :cy="C" :r="R_OUT - 3" fill="url(#paper)" />

    <!-- 当前山高亮 -->
    <path :d="highlight" fill="rgba(63,107,90,0.18)" stroke="rgba(63,107,90,0.55)" stroke-width="1" />

    <!-- 二十四山分隔线 -->
    <line
      v-for="i in 24"
      :key="`sep-${i}`"
      :x1="polar((i - 1) * 15 - 7.5, R_SHAN_IN).x"
      :y1="polar((i - 1) * 15 - 7.5, R_SHAN_IN).y"
      :x2="polar((i - 1) * 15 - 7.5, R_OUT - 3).x"
      :y2="polar((i - 1) * 15 - 7.5, R_OUT - 3).y"
      stroke="rgba(43,38,32,0.12)"
      stroke-width="0.7"
    />

    <!-- 二十四山文字 -->
    <text
      v-for="item in shanLabel"
      :key="item.name"
      x="200"
      :y="C - R_OUT + 22"
      text-anchor="middle"
      dominant-baseline="middle"
      :transform="`rotate(${item.angle} 200 200)`"
      :fill="item.cardinal ? '#A8442A' : item.branch ? '#3D3630' : '#6B5E52'"
      font-size="13"
      font-family="Songti SC, Source Han Serif SC, serif"
    >
      {{ item.name }}
    </text>

    <!-- 八卦内环 -->
    <circle :cx="C" :cy="C" :r="R_SHAN_IN" fill="none" stroke="rgba(176,138,79,0.35)" stroke-width="0.8" />
    <text
      v-for="item in guaLabel"
      :key="`gua-${item.name}`"
      x="200"
      :y="C - R_SHAN_IN + 20"
      text-anchor="middle"
      dominant-baseline="middle"
      :transform="`rotate(${item.angle} 200 200)`"
      :fill="item.cardinal ? '#A8442A' : '#8C8074'"
      font-size="12"
      font-family="Songti SC, Source Han Serif SC, serif"
    >
      {{ item.name }}
    </text>

    <circle :cx="C" :cy="C" :r="R_GUA_IN" fill="none" stroke="rgba(176,138,79,0.22)" stroke-width="0.8" />

    <!-- 指针 -->
    <line
      :x1="needle.tail.x"
      :y1="needle.tail.y"
      :x2="needle.tip.x"
      :y2="needle.tip.y"
      stroke="#A8442A"
      stroke-width="2.5"
      stroke-linecap="round"
    />
    <circle :cx="needle.tip.x" :cy="needle.tip.y" r="4" fill="#A8442A" />
    <circle :cx="C" :cy="C" r="4" fill="#2B2620" />

    <!-- 中心读数 -->
    <text x="200" y="196" text-anchor="middle" fill="#2B2620" font-size="15" font-family="Songti SC, serif">
      {{ current.name }}山
    </text>
    <text x="200" y="214" text-anchor="middle" fill="#8A7F70" font-size="10">
      {{ normalized.toFixed(1) }}°
    </text>

    <!-- 分金文字 -->
    <text
      v-if="showFenJin"
      x="200"
      y="232"
      text-anchor="middle"
      fill="#6B5E52"
      font-size="10"
    >
      {{ fenJin.slot.ganZhi }} · {{ fenJin.slot.slotNote }}
    </text>
  </svg>
</template>

<style scoped>
.compass {
  display: block;
  width: 100%;
  height: auto;
  max-width: 420px;
  filter: drop-shadow(0 10px 24px rgba(28, 26, 23, 0.16));
}
</style>
