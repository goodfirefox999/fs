<script setup lang="ts">
import { computed, getCurrentInstance, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import type { Archive, Report } from '@/core/types'
import { GRID_ORDER, PALACES } from '@/core/constants/luoshu'
import { buildReport, reportModeLabel } from '@/core/engines/report'
import { useArchiveStore } from '@/stores/archive'
import { formatTimestamp, modeLabel, sittingFacingText } from '@/utils/display'

const instance = getCurrentInstance()
const archiveStore = useArchiveStore()

const archiveId = ref('')
const archive = ref<Archive | null>(null)
const report = ref<Report | null>(null)
const imagePath = ref('')
const generating = ref(false)

const canvasSize = computed(() => {
  let width = 327
  try {
    width = Math.min((uni.getSystemInfoSync().windowWidth || 375) - 48, 360)
  } catch {
    width = 327
  }
  return { width, height: Math.round(width * 1.62) }
})

const pair = computed(() =>
  archive.value ? sittingFacingText(archive.value.reading.facingDeg) : null
)

onLoad((query) => {
  archiveId.value = String(query?.id ?? '') || archiveStore.currentId
  const found = archiveStore.getById(archiveId.value)
  if (!found) return
  archive.value = found
  report.value = buildReport(found, { contents: null, unlocked: false, zeri: [] })
  setTimeout(() => drawPoster(), 120)
})

function roundRect(
  ctx: UniApp.CanvasContext,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
) {
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.lineTo(x + width - radius, y)
  ctx.arc(x + width - radius, y + radius, radius, -Math.PI / 2, 0)
  ctx.lineTo(x + width, y + height - radius)
  ctx.arc(x + width - radius, y + height - radius, radius, 0, Math.PI / 2)
  ctx.lineTo(x + radius, y + height)
  ctx.arc(x + radius, y + height - radius, radius, Math.PI / 2, Math.PI)
  ctx.lineTo(x, y + radius)
  ctx.arc(x + radius, y + radius, radius, Math.PI, (Math.PI * 3) / 2)
  ctx.closePath()
}

function drawPoster() {
  const currentArchive = archive.value
  const currentReport = report.value
  if (!currentArchive || !currentReport) return
  const ctx = uni.createCanvasContext('poster', instance?.proxy)
  const { width, height } = canvasSize.value
  const scale = width / 360
  const padding = 24 * scale
  const contentWidth = width - padding * 2

  ctx.setFillStyle('#F6F1E7')
  ctx.fillRect(0, 0, width, height)

  ctx.setStrokeStyle('rgba(176,138,79,0.35)')
  ctx.setLineWidth(1)
  ctx.strokeRect(padding * 0.55, padding * 0.55, width - padding * 1.1, height - padding * 1.1)

  ctx.setFillStyle('#A8442A')
  ctx.setFontSize(10 * scale)
  ctx.setTextAlign('left')
  ctx.fillText('TRADITIONAL SITE RECORD', padding, padding + 10 * scale)

  ctx.setFillStyle('#2B2620')
  ctx.setFontSize(20 * scale)
  const titleLines = wrapText(ctx, currentArchive.title, contentWidth, 20 * scale, 2)
  let cursorY = padding + 32 * scale
  titleLines.forEach((line) => {
    ctx.fillText(line, padding, cursorY)
    cursorY += 26 * scale
  })

  ctx.setFillStyle('#8C8175')
  ctx.setFontSize(10 * scale)
  ctx.fillText(
    `${reportModeLabel(currentArchive.mode)} · ${currentArchive.eventYear} 年 · 运${currentArchive.period}`,
    padding,
    cursorY + 2
  )

  const pairTop = cursorY + 22 * scale
  ctx.setFillStyle('#A8442A')
  ctx.setFontSize(26 * scale)
  ctx.fillText(pair.value?.text ?? '', padding, pairTop + 20 * scale)
  ctx.setFillStyle('#5E5548')
  ctx.setFontSize(11 * scale)
  ctx.fillText(pair.value?.deg ?? '', padding, pairTop + 38 * scale)

  ctx.setFillStyle('#3F6B5A')
  ctx.setFontSize(13 * scale)
  ctx.fillText(currentReport.chart.patternLabel, padding, pairTop + 60 * scale)

  const gridTop = pairTop + 78 * scale
  const gap = 4 * scale
  const cell = (contentWidth - gap * 2) / 3
  GRID_ORDER.forEach((palaceId, index) => {
    const col = index % 3
    const row = Math.floor(index / 3)
    const x = padding + col * (cell + gap)
    const y = gridTop + row * (cell + gap)
    const meta = PALACES[palaceId]
    const palace = currentReport.chart.palaces.find((item) => item.palace === palaceId)
    if (!palace) return
    ctx.setFillStyle(palaceId === 5 ? '#F1E8D8' : '#FBF7EF')
    roundRect(ctx, x, y, cell, cell, 6 * scale)
    ctx.fill()
    ctx.setStrokeStyle('rgba(43,38,32,0.12)')
    ctx.setLineWidth(0.8)
    ctx.stroke()

    ctx.setFillStyle('#8C8175')
    ctx.setFontSize(7 * scale)
    ctx.fillText(meta.direction, x + 6 * scale, y + 12 * scale)

    ctx.setFillStyle('#2B2620')
    ctx.setFontSize(14 * scale)
    ctx.fillText(`${palace.shan} · ${palace.xiang}`, x + 6 * scale, y + cell * 0.55)
    ctx.setFillStyle('#8C8175')
    ctx.setFontSize(7 * scale)
    ctx.fillText(
      `运${palace.yun} 年${palace.annual ?? '—'}`,
      x + 6 * scale,
      y + cell - 8 * scale
    )
  })

  const footerTop = gridTop + cell * 3 + gap * 2 + 22 * scale
  ctx.setFillStyle('#5E5548')
  ctx.setFontSize(9 * scale)
  ctx.fillText(
    `${modeLabel(currentArchive.mode)} · ${formatTimestamp(currentArchive.updatedAt)} 更新`,
    padding,
    footerTop
  )
  ctx.setFillStyle('#8C8175')
  ctx.setFontSize(8 * scale)
  ctx.fillText('居境罗盘 · 传统人居环境方位参考', padding, footerTop + 16 * scale)
  ctx.fillText('本图仅作环境记录参考，不替代现场复核。', padding, footerTop + 29 * scale)

  ctx.draw(false, () => {
    setTimeout(() => {
      uni.canvasToTempFilePath(
        {
          canvasId: 'poster',
          destWidth: width * 2,
          destHeight: height * 2,
          success: (result) => {
            imagePath.value = result.tempFilePath
            generating.value = false
          },
          fail: () => {
            generating.value = false
            uni.showToast({ title: '图片导出失败，可截图保存', icon: 'none' })
          },
        },
        instance?.proxy
      )
    }, 120)
  })
}

function wrapText(
  ctx: UniApp.CanvasContext,
  text: string,
  maxWidth: number,
  fontSize: number,
  maxLines: number
): string[] {
  const perLine = Math.max(1, Math.floor(maxWidth / fontSize))
  const lines: string[] = []
  let rest = text
  while (rest && lines.length < maxLines) {
    lines.push(rest.slice(0, perLine))
    rest = rest.slice(perLine)
  }
  if (rest && lines.length) {
    lines[lines.length - 1] = `${lines[lines.length - 1].slice(0, perLine - 1)}…`
  }
  void ctx
  return lines
}

function generate() {
  if (generating.value) return
  generating.value = true
  imagePath.value = ''
  drawPoster()
}

function saveImage() {
  if (!imagePath.value) {
    uni.showToast({ title: '请先生成分享图', icon: 'none' })
    return
  }
  // #ifdef MP-WEIXIN
  uni.saveImageToPhotosAlbum({
    filePath: imagePath.value,
    success: () => uni.showToast({ title: '已保存到相册', icon: 'none' }),
    fail: () => uni.showToast({ title: '保存失败，请检查相册权限', icon: 'none' }),
  })
  // #endif
  // #ifdef H5
  uni.previewImage({
    urls: [imagePath.value],
    fail: () => uni.showToast({ title: '可长按图片或截图保存', icon: 'none' }),
  })
  // #endif
}

function openReport() {
  if (!archive.value) return
  uni.navigateTo({ url: `/pages/report/index?id=${archive.value.id}` })
}
</script>

<template>
  <view class="page">
    <view class="shell">
      <view class="page-head">
        <text class="eyebrow">SHARE CARD</text>
        <text class="head-title serif">生成分享图</text>
        <text class="head-sub">导出一张仅含坐向与九宫摘要的图片，不包含出生日期等个人信息。</text>
      </view>

      <view v-if="!archive || !report" class="card empty-card">
        <text class="empty-title serif">未找到档案</text>
        <text class="hint">请从档案页进入分享图。</text>
      </view>

      <template v-else>
        <view class="card canvas-card">
          <canvas
            id="poster"
            canvas-id="poster"
            class="poster-canvas"
            :style="{ width: canvasSize.width + 'px', height: canvasSize.height + 'px' }"
          />
        </view>

        <view class="hint privacy-hint">
          分享图只包含档案名称、坐向、年份与九宫数字，不包含居住者、仙命或家属出生信息。
        </view>

        <view class="actions">
          <button class="btn btn-ghost" :disabled="generating" @click="generate">
            {{ generating ? '正在生成…' : '重新生成' }}
          </button>
          <button class="btn btn-primary" @click="saveImage">
            {{ imagePath ? '保存 / 预览' : '先生成图片' }}
          </button>
        </view>

        <button class="btn btn-ghost back-report" @click="openReport">返回档案分析</button>

        <view class="hint footer-hint">
          分享图仅用于记录与交流。涉及纪念地、施工或家庭信息时，请自行确认分享范围。
        </view>
      </template>
    </view>
  </view>
</template>

<style scoped>
.page-head {
  padding: 24rpx 0 22rpx;
}
.head-title {
  display: block;
  margin-top: 4rpx;
  font-size: 42rpx;
}
.head-sub {
  display: block;
  margin-top: 6rpx;
  color: var(--muted);
  font-size: 22rpx;
  line-height: 1.7;
}
.canvas-card {
  display: flex;
  justify-content: center;
  padding: 20rpx;
  background: #e9dfcd;
}
.poster-canvas {
  display: block;
  border-radius: 4rpx;
  box-shadow: 0 16rpx 40rpx rgba(43, 38, 32, 0.16);
  background: #f6f1e7;
}
.privacy-hint {
  display: block;
  margin: 18rpx 6rpx 0;
}
.actions {
  display: flex;
  gap: 16rpx;
  margin-top: 24rpx;
}
.actions .btn {
  flex: 1;
}
.back-report {
  margin-top: 16rpx;
  width: 100%;
}
.footer-hint {
  display: block;
  margin-top: 24rpx;
  text-align: center;
}
.empty-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14rpx;
  text-align: center;
  padding: 64rpx 36rpx;
}
.empty-title {
  font-size: 32rpx;
}
</style>
