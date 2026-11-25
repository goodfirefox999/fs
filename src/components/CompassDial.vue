<script setup lang="ts">
import { getCurrentInstance, onMounted, watch } from 'vue'
import { SHAN_NAMES } from '@/core/constants/shan24'
import { FENJIN_SLOTS } from '@/core/constants/fenjin120'

/** 后天八卦方位（自北顺时针） */
const BAGUA_RING = ['坎', '艮', '震', '巽', '离', '坤', '兑', '乾']

const props = withDefaults(
  defineProps<{
    size: number
    heading: number
    lockedDeg?: number | null
    showBagua?: boolean
    showFenJin?: boolean
  }>(),
  { lockedDeg: null, showBagua: false, showFenJin: false }
)

const instance = getCurrentInstance()

// 八卦方位（对应二十四山中的卦位山）
const TRIGRAMS = ['坎', '艮', '震', '巽', '离', '坤', '兑', '乾']
// 八卦对应的山索引
const TRIGRAM_SHAN_IDX = [0, 3, 6, 9, 12, 15, 18, 21]

function draw() {
  const size = props.size
  if (!size) return
  const ctx = uni.createCanvasContext('dial', instance?.proxy)
  const cx = size / 2
  const cy = size / 2
  const R = size / 2 - 4
  const toRad = (deg: number) => (deg * Math.PI) / 180

  ctx.clearRect(0, 0, size, size)

  // ── 最外圈：深色底盘 ──
  ctx.setFillStyle('#2C2420')
  ctx.beginPath()
  ctx.arc(cx, cy, R, 0, Math.PI * 2)
  ctx.fill()

  // ── 外圈装饰：铜色细环 ──
  ctx.setStrokeStyle('rgba(160, 128, 72, 0.4)')
  ctx.setLineWidth(1.5)
  ctx.beginPath()
  ctx.arc(cx, cy, R - 2, 0, Math.PI * 2)
  ctx.stroke()

  // ── 第一层：宣纸白底盘 ──
  const r1 = R - 8
  ctx.setFillStyle('#F5EFE3')
  ctx.beginPath()
  ctx.arc(cx, cy, r1, 0, Math.PI * 2)
  ctx.fill()

  // ── 24山分区交替底色 ──
  for (let i = 0; i < 24; i++) {
    const startAngle = toRad(i * 15 - 7.5 - 90)
    const endAngle = toRad(i * 15 + 7.5 - 90)
    if (i % 2 === 0) {
      ctx.setFillStyle('rgba(240, 234, 220, 0.5)')
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.arc(cx, cy, r1 - 2, startAngle, endAngle)
      ctx.closePath()
      ctx.fill()
    }
  }

  // ── 24山分隔线 ──
  ctx.setStrokeStyle('rgba(28, 26, 23, 0.12)')
  ctx.setLineWidth(0.6)
  for (let i = 0; i < 24; i++) {
    const angle = toRad(i * 15 - 7.5 - 90)
    ctx.beginPath()
    ctx.moveTo(cx + Math.cos(angle) * (r1 * 0.35), cy + Math.sin(angle) * (r1 * 0.35))
    ctx.lineTo(cx + Math.cos(angle) * (r1 - 2), cy + Math.sin(angle) * (r1 - 2))
    ctx.stroke()
  }

  // ── 八卦区域底色 ──
  for (let t = 0; t < 8; t++) {
    const startAngle = toRad(t * 45 - 22.5 - 90)
    const endAngle = toRad(t * 45 + 22.5 - 90)
    const trigramShanIdx = TRIGRAM_SHAN_IDX[t]
    // 四正卦方位用淡金色底
    if ([0, 2, 4, 6].includes(t)) {
      ctx.setFillStyle('rgba(176, 58, 46, 0.03)')
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.arc(cx, cy, r1 - 4, startAngle, endAngle)
      ctx.closePath()
      ctx.fill()
    }
    void trigramShanIdx
  }

  // ── 中圈装饰线 ──
  ctx.setStrokeStyle('rgba(160, 128, 72, 0.2)')
  ctx.setLineWidth(0.8)
  ctx.beginPath()
  ctx.arc(cx, cy, r1 * 0.65, 0, Math.PI * 2)
  ctx.stroke()

  ctx.setStrokeStyle('rgba(160, 128, 72, 0.12)')
  ctx.beginPath()
  ctx.arc(cx, cy, r1 * 0.4, 0, Math.PI * 2)
  ctx.stroke()

  // ── 八卦文字（内侧大圈） ──
  ctx.setFontSize(Math.max(10, size * 0.038))
  ctx.setTextAlign('center')
  ctx.setTextBaseline('middle')
  TRIGRAMS.forEach((name, index) => {
    const angle = toRad(index * 45 - 90)
    const x = cx + Math.cos(angle) * (r1 * 0.52)
    const y = cy + Math.sin(angle) * (r1 * 0.52)
    const isCardinal = [0, 2, 4, 6].includes(index)
    ctx.setFillStyle(isCardinal ? '#B03A2E' : '#8C8074')
    ctx.fillText(name, x, y)
  })

  // ── 二十四山文字（外圈） ──
  ctx.setFontSize(Math.max(9, size * 0.032))
  SHAN_NAMES.forEach((name, index) => {
    const angle = toRad(index * 15 - 90)
    const x = cx + Math.cos(angle) * (r1 * 0.85)
    const y = cy + Math.sin(angle) * (r1 * 0.85)
    const cardinal = ['子', '卯', '午', '酉'].includes(name)
    const diZhi = index % 2 === 0 // 地支山
    ctx.setFillStyle(cardinal ? '#B03A2E' : diZhi ? '#3D3630' : '#6B5E52')
    ctx.fillText(name, x, y)
  })

  // ── 天池中心 ──
  const centerR = r1 * 0.18
  // 中心底
  ctx.setFillStyle('#FDFAF4')
  ctx.beginPath()
  ctx.arc(cx, cy, centerR + 6, 0, Math.PI * 2)
  ctx.fill()
  ctx.setStrokeStyle('rgba(160, 128, 72, 0.3)')
  ctx.setLineWidth(1)
  ctx.beginPath()
  ctx.arc(cx, cy, centerR + 6, 0, Math.PI * 2)
  ctx.stroke()

  // 天池十字线（南北向）
  ctx.setStrokeStyle('rgba(176, 58, 46, 0.25)')
  ctx.setLineWidth(0.8)
  ctx.beginPath()
  ctx.moveTo(cx, cy - centerR - 4)
  ctx.lineTo(cx, cy + centerR + 4)
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(cx - centerR - 4, cy)
  ctx.lineTo(cx + centerR + 4, cy)
  ctx.stroke()

  // ── 锁定线 ──
  if (props.lockedDeg !== null && props.lockedDeg !== undefined) {
    const lockRad = toRad(props.lockedDeg - 90)
    ctx.setStrokeStyle('rgba(160, 128, 72, 0.5)')
    ctx.setLineWidth(2)
    ctx.setLineDash([4, 4])
    ctx.beginPath()
    ctx.moveTo(
      cx - Math.cos(lockRad) * (r1 - 12),
      cy - Math.sin(lockRad) * (r1 - 12)
    )
    ctx.lineTo(
      cx + Math.cos(lockRad) * (r1 - 12),
      cy + Math.sin(lockRad) * (r1 - 12)
    )
    ctx.stroke()
    ctx.setLineDash([])
  }

  // ── 指南针（天池针） ──
  ctx.save()
  ctx.translate(cx, cy)
  ctx.rotate(toRad(props.heading))

  // 针身（南半 · 松绿色）
  ctx.setFillStyle('#2D5A4A')
  ctx.beginPath()
  ctx.moveTo(0, r1 * 0.12)
  ctx.lineTo(-3, 0)
  ctx.lineTo(3, 0)
  ctx.closePath()
  ctx.fill()

  // 针身（北半 · 朱砂红 + 三角箭头）
  ctx.setFillStyle('#B03A2E')
  ctx.beginPath()
  ctx.moveTo(0, -r1 * 0.55)
  ctx.lineTo(-4, -r1 * 0.35)
  ctx.lineTo(4, -r1 * 0.35)
  ctx.closePath()
  ctx.fill()

  // 针杆
  ctx.setStrokeStyle('#B03A2E')
  ctx.setLineWidth(1.5)
  ctx.beginPath()
  ctx.moveTo(0, 0)
  ctx.lineTo(0, -r1 * 0.4)
  ctx.stroke()

  ctx.restore()

  // ── 中心圆点 ──
  ctx.setFillStyle('#1C1A17')
  ctx.beginPath()
  ctx.arc(cx, cy, 3.5, 0, Math.PI * 2)
  ctx.fill()

  ctx.setFillStyle('#F5EFE3')
  ctx.beginPath()
  ctx.arc(cx, cy, 1.5, 0, Math.PI * 2)
  ctx.fill()

  ctx.draw()
}

onMounted(() => {
  setTimeout(draw, 80)
})

watch(
  () => [props.heading, props.lockedDeg, props.size, props.showBagua, props.showFenJin],
  () => {
    draw()
  }
)
</script>

<template>
  <canvas
    id="dial"
    canvas-id="dial"
    class="dial"
    :style="{ width: size + 'px', height: size + 'px' }"
  />
</template>

<style scoped>
.dial {
  display: block;
  border-radius: 50%;
  box-shadow:
    0 20rpx 60rpx rgba(28, 26, 23, 0.18),
    0 4rpx 12rpx rgba(28, 26, 23, 0.1),
    inset 0 0 0 1rpx rgba(160, 128, 72, 0.15);
}
</style>
