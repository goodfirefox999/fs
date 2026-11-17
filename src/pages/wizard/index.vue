<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import type { Gender, SceneMode } from '@/core/types'
import { periodFromYear } from '@/core/engines/xuankong'
import { resolveFenJin } from '@/core/constants/fenjin120'
import { normalizeDeg, SHAN_NAMES } from '@/core/constants/shan24'
import { useArchiveStore } from '@/stores/archive'
import { useDraftStore } from '@/stores/draft'
import { trackEvent } from '@/services/cloud'
import { degreeText, modeFullLabel, sittingFacingText } from '@/utils/display'

type Step = 1 | 2 | 3

interface MemberForm {
  relation: string
  gender: Gender
  date: string
  unknown: boolean
}

interface PersonForm {
  label: string
  date: string
  unknown: boolean
}

const archiveStore = useArchiveStore()
const draft = useDraftStore()

const step = ref<Step>(1)
const mode = ref<SceneMode>('YANG')
const title = ref('')
const eventYear = ref(new Date().getFullYear())
const propertyType = ref<'RESIDENTIAL' | 'OFFICE' | 'SHOP'>('RESIDENTIAL')
const monumentType = ref<'SINGLE' | 'COUPLE' | 'ANCESTRAL'>('SINGLE')
const members = ref<MemberForm[]>([
  { relation: '本人', gender: 'M', date: '', unknown: false },
])
const deceased = ref<PersonForm[]>([
  { label: '先人', date: '', unknown: false },
])
const descendants = ref<PersonForm[]>([
  { label: '家属', date: '', unknown: false },
])
const dragonOptions = [{ value: '', label: '未确认' }].concat(
  SHAN_NAMES.map((name) => ({ value: name, label: `${name}山` }))
)
const terrain = reactive({
  backSupport: 'STRONG' as 'STRONG' | 'FLAT' | 'HOLLOW',
  frontView: 'OPEN' as 'OPEN' | 'BLOCKED' | 'TILTED',
  leftRight: 'BALANCED' as 'BALANCED' | 'LEFT_MISS' | 'RIGHT_MISS',
  waterFlow: '',
  notes: '',
  incomingDragon: '',
})
const submitting = ref(false)
const manualFacing = ref(draft.compass.facingDeg.toFixed(1))

const relationOptions = ['本人', '配偶', '父母', '子女', '其他']
const propertyOptions = [
  { value: 'RESIDENTIAL', label: '住宅' },
  { value: 'OFFICE', label: '办公' },
  { value: 'SHOP', label: '商铺' },
] as const
const monumentOptions = [
  { value: 'SINGLE', label: '单人纪念位' },
  { value: 'COUPLE', label: '双人合葬位' },
  { value: 'ANCESTRAL', label: '家族纪念地' },
] as const
const backOptions = [
  { value: 'STRONG', label: '后有依托' },
  { value: 'FLAT', label: '后方平坦' },
  { value: 'HOLLOW', label: '后方低洼空缺' },
] as const
const frontOptions = [
  { value: 'OPEN', label: '前方开阔' },
  { value: 'BLOCKED', label: '前方遮挡' },
  { value: 'TILTED', label: '前方倾斜' },
] as const
const sideOptions = [
  { value: 'BALANCED', label: '左右均衡' },
  { value: 'LEFT_MISS', label: '左侧低矮' },
  { value: 'RIGHT_MISS', label: '右侧低矮' },
] as const

const pair = computed(() => sittingFacingText(draft.compass.facingDeg))
const period = computed(() => periodFromYear(eventYear.value))
const fenJin = computed(() =>
  mode.value === 'YIN'
    ? resolveFenJin(normalizeDeg(draft.compass.facingDeg + 180))
    : null
)
const stepTitle = computed(() => {
  if (step.value === 1) return '基本信息'
  if (step.value === 2) return '坐向确认'
  return mode.value === 'YANG' ? '居住者与空间' : '纪念地信息'
})
const yearValue = computed(() => `${eventYear.value}-01-01`)
const readingConfirmed = computed(() => draft.compass.confirmed)

onLoad((query) => {
  if (query?.mode === 'YIN') {
    mode.value = 'YIN'
    draft.setSceneMode('YIN')
  } else {
    draft.setSceneMode('YANG')
  }
})

onShow(() => {
  manualFacing.value = draft.compass.facingDeg.toFixed(1)
  draft.setSceneMode(mode.value)
})

function setMode(value: SceneMode) {
  mode.value = value
  draft.setSceneMode(value)
}

function onYearChange(event: { detail: { value: string } }) {
  const year = Number(String(event.detail.value).slice(0, 4))
  if (Number.isFinite(year)) eventYear.value = year
}

function relationIndex(relation: string) {
  const index = relationOptions.indexOf(relation)
  return index < 0 ? relationOptions.length - 1 : index
}

function onRelation(member: MemberForm, event: { detail: { value: number | string } }) {
  member.relation = relationOptions[Number(event.detail.value)] || '其他'
}

function onDate(target: { date: string }, event: { detail: { value: string } }) {
  target.date = String(event.detail.value)
}

function onUnknown(target: { unknown: boolean }, event: { detail: { value: boolean } }) {
  target.unknown = Boolean(event.detail.value)
}

function setGender(member: MemberForm, gender: Gender) {
  member.gender = gender
}

function addMember() {
  members.value.push({ relation: '家属', gender: 'F', date: '', unknown: false })
}

function removeMember(index: number) {
  if (members.value.length <= 1) return
  members.value.splice(index, 1)
}

function addPerson(list: 'deceased' | 'descendants') {
  const target = list === 'deceased' ? deceased.value : descendants.value
  target.push({ label: list === 'deceased' ? '先人' : '家属', date: '', unknown: false })
}

function removePerson(list: 'deceased' | 'descendants', index: number) {
  const target = list === 'deceased' ? deceased.value : descendants.value
  if (target.length <= 1) return
  target.splice(index, 1)
}

function applyFacing() {
  const value = Number(manualFacing.value)
  if (!Number.isFinite(value)) {
    uni.showToast({ title: '请输入有效度数', icon: 'none' })
    return
  }
  draft.setCompass({
    facingDeg: normalizeDeg(value),
    inputMethod: 'MANUAL_DEG',
    stability: 100,
    uncertainty: 0.5,
    confirmed: true,
  })
  manualFacing.value = normalizeDeg(value).toFixed(1)
  uni.showToast({ title: '坐向已更新', icon: 'none' })
}

function confirmReading() {
  draft.setCompass({ confirmed: true })
  uni.showToast({ title: '已确认当前读数', icon: 'none' })
}

function goCompass() {
  uni.navigateTo({ url: `/pages/compass/index?mode=${mode.value}` })
}

function validateStep(current: Step): string {
  if (current === 1) {
    if (!title.value.trim()) return '请填写档案名称'
    if (eventYear.value < 1900 || eventYear.value > 2100) return '年份需在 1900–2100 之间'
  }
  if (current === 2 && !draft.compass.confirmed) {
    return '请确认当前坐向，或重新进行罗盘定向'
  }
  return ''
}

function next() {
  const error = validateStep(step.value)
  if (error) {
    uni.showToast({ title: error, icon: 'none' })
    return
  }
  step.value = Math.min(3, step.value + 1) as Step
  uni.pageScrollTo({ scrollTop: 0, duration: 200 })
}

function prev() {
  if (step.value === 1) {
    uni.navigateBack()
    return
  }
  step.value = Math.max(1, step.value - 1) as Step
  uni.pageScrollTo({ scrollTop: 0, duration: 200 })
}

function submit() {
  const error = validateStep(1) || validateStep(2)
  if (error) {
    uni.showToast({ title: error, icon: 'none' })
    return
  }
  if (submitting.value) return
  submitting.value = true
  try {
    const archive = archiveStore.create({
      mode: mode.value,
      title: title.value.trim(),
      eventYear: eventYear.value,
      reading: draft.toReading(),
      yang:
        mode.value === 'YANG'
          ? {
              propertyType: propertyType.value,
              members: members.value.map((member) => ({
                relation: member.relation,
                birth: {
                  date: member.unknown ? '' : member.date,
                  precision: 'DAY',
                  gender: member.gender,
                },
              })),
            }
          : undefined,
      yin:
        mode.value === 'YIN'
          ? {
              monumentType: monumentType.value,
              deceased: deceased.value.map((person) => ({
                label: person.label || '先人',
                birth: {
                  date: person.unknown ? '' : person.date,
                  precision: 'DAY',
                },
              })),
              descendants: descendants.value.map((person) => ({
                label: person.label || '家属',
                birth: {
                  date: person.unknown ? '' : person.date,
                  precision: 'DAY',
                },
              })),
              terrain: {
                backSupport: terrain.backSupport,
                frontView: terrain.frontView,
                leftRight: terrain.leftRight,
                waterFlow: terrain.waterFlow.trim() || undefined,
                notes: terrain.notes.trim() || undefined,
                incomingDragon: terrain.incomingDragon || undefined,
              },
            }
          : undefined,
    })
    trackEvent('archive_create', { mode: mode.value, period: archive.period })
    draft.reset()
    uni.redirectTo({ url: `/pages/report/index?id=${archive.id}` })
  } catch (error) {
    submitting.value = false
    uni.showToast({
      title: error instanceof Error ? error.message : '档案保存失败',
      icon: 'none',
    })
  }
}
</script>

<template>
  <view class="page wizard">
    <view class="shell">
      <view class="wizard-head">
        <text class="eyebrow">NEW ARCHIVE</text>
        <text class="wizard-title serif">新建{{ modeFullLabel(mode) }}档案</text>
        <view class="steps">
          <view
            v-for="index in 3"
            :key="index"
            class="step"
            :class="{ active: step === index, done: step > index }"
          >
            <text class="step-num">{{ step > index ? '✓' : index }}</text>
            <text class="step-name">
              {{ index === 1 ? '基本信息' : index === 2 ? '坐向' : mode === 'YANG' ? '居住者' : '纪念地' }}
            </text>
          </view>
        </view>
      </view>

      <view v-if="step === 1" class="card">
        <view class="card-title"><text>档案类型</text></view>
        <view class="mode-switch">
          <button
            class="mode-option"
            :class="{ active: mode === 'YANG' }"
            @click="setMode('YANG')"
          >
            <text class="mode-option-title serif">阳宅</text>
            <text class="mode-option-desc">居住 / 办公 / 商铺</text>
          </button>
          <button
            class="mode-option"
            :class="{ active: mode === 'YIN' }"
            @click="setMode('YIN')"
          >
            <text class="mode-option-title serif">纪念地</text>
            <text class="mode-option-desc">先人纪念地环境记录</text>
          </button>
        </view>

        <view class="field top-gap">
          <text class="field-label">档案名称</text>
          <input
            v-model="title"
            class="input"
            maxlength="30"
            :placeholder="mode === 'YANG' ? '例如：城南新居' : '例如：祖居后山纪念地'"
          />
        </view>

        <view class="field">
          <text class="field-label">{{ mode === 'YANG' ? '入宅或建档年份' : '建档参考年份' }}</text>
          <picker mode="date" fields="year" :value="yearValue" start="1900-01-01" end="2100-12-31" @change="onYearChange">
            <view class="picker-field row-between">
              <text>{{ eventYear }} 年 · {{ period }}运</text>
              <text class="muted">切换 ›</text>
            </view>
          </picker>
          <text class="hint">九宫运盘按此年份推算；同一房屋在不同年份会有不同的运星组合。</text>
        </view>

        <view v-if="mode === 'YANG'" class="field">
          <text class="field-label">空间类型</text>
          <view class="option-row">
            <button
              v-for="item in propertyOptions"
              :key="item.value"
              class="option-chip"
              :class="{ active: propertyType === item.value }"
              @click="propertyType = item.value"
            >
              {{ item.label }}
            </button>
          </view>
        </view>

        <view v-else class="field">
          <text class="field-label">纪念位类型</text>
          <view class="option-row wrap">
            <button
              v-for="item in monumentOptions"
              :key="item.value"
              class="option-chip"
              :class="{ active: monumentType === item.value }"
              @click="monumentType = item.value"
            >
              {{ item.label }}
            </button>
          </view>
        </view>
      </view>

      <view v-if="step === 2" class="card">
        <view class="card-title">
          <text>当前坐向</text>
          <text class="badge" :class="readingConfirmed ? 'info' : 'caution'">
            {{ readingConfirmed ? '已确认' : '待确认' }}
          </text>
        </view>

        <view class="reading-box">
          <view class="reading-main">
            <text class="reading-name serif">{{ pair.text }}</text>
            <text class="reading-deg">{{ pair.deg }}</text>
          </view>
          <view class="reading-side">
            <text class="badge" :class="pair.isJianXiang ? 'caution' : 'info'">
              {{ pair.isJianXiang ? '兼向' : '正向' }}
            </text>
            <text class="tiny muted">稳定性 {{ Math.round(draft.compass.stability) }}%</text>
          </view>
        </view>

        <view v-if="fenJin" class="fenjin-box">
          <view class="row-between">
            <text class="tiny muted">当前分金</text>
            <text class="badge" :class="fenJin.slot.quality === 'WANG_XIANG' ? 'info' : 'caution'">
              {{ fenJin.slot.qualityDetail }}
            </text>
          </view>
          <text class="fenjin-name serif">
            {{ fenJin.slot.mount }}山 {{ fenJin.slot.ganZhi }} · {{ fenJin.slot.nayin }}
          </text>
          <text class="tiny muted">
            线度 {{ fenJin.slot.startDeg.toFixed(1) }}° – {{ fenJin.slot.endDeg.toFixed(1) }}°，
            偏移 {{ fenJin.offset.toFixed(1) }}°
          </text>
          <text v-if="fenJin.warning" class="hint warn">{{ fenJin.warning }}</text>
        </view>

        <view class="divider" />

        <view class="field">
          <text class="field-label">手动校准朝向（0–360°）</text>
          <view class="row">
            <input v-model="manualFacing" class="input" type="digit" @confirm="applyFacing" />
            <button class="btn btn-ghost btn-sm apply" @click="applyFacing">应用</button>
          </view>
          <text class="hint">
            房屋正面朝向为向，背面为坐。若已在现场用实体罗盘读数，可在此直接输入。
          </text>
        </view>

        <view class="row actions">
          <button class="btn btn-ghost" @click="goCompass">打开罗盘精测</button>
          <button class="btn btn-primary" :disabled="readingConfirmed" @click="confirmReading">
            {{ readingConfirmed ? '已确认' : '确认此读数' }}
          </button>
        </view>

        <view class="hint-box">
          <text class="hint">
            罗盘读数会决定九宫排盘、分金与兼向判断。读数未确认时不会进入下一步。
          </text>
        </view>
      </view>

      <view v-if="step === 3" class="card">
        <template v-if="mode === 'YANG'">
          <view class="card-title">
            <text>居住者信息</text>
            <button class="plain-button link tiny" @click="addMember">＋ 添加</button>
          </view>
          <text class="hint section-hint">
            用于生成命卦与八宅分区参考。出生日期会按立春划分年柱；不方便填写时可标记为不详。
          </text>

          <view v-for="(member, index) in members" :key="index" class="person-card">
            <view class="person-head">
              <text class="person-index">成员 {{ index + 1 }}</text>
              <button
                v-if="members.length > 1"
                class="plain-button tiny danger-text"
                @click="removeMember(index)"
              >
                移除
              </button>
            </view>

            <view class="person-row">
              <text class="person-label">关系</text>
              <picker
                mode="selector"
                :range="relationOptions"
                :value="relationIndex(member.relation)"
                @change="onRelation(member, $event)"
              >
                <view class="picker-value">{{ member.relation }} ›</view>
              </picker>
            </view>

            <view class="person-row">
              <text class="person-label">性别</text>
              <view class="mini-seg">
                <button
                  class="mini-seg-item"
                  :class="{ active: member.gender === 'M' }"
                  @click="setGender(member, 'M')"
                >
                  男
                </button>
                <button
                  class="mini-seg-item"
                  :class="{ active: member.gender === 'F' }"
                  @click="setGender(member, 'F')"
                >
                  女
                </button>
              </view>
            </view>

            <view class="person-row">
              <text class="person-label">出生日期</text>
              <picker
                mode="date"
                :value="member.date || '1990-01-01'"
                start="1920-01-01"
                end="2026-12-31"
                :disabled="member.unknown"
                @change="onDate(member, $event)"
              >
                <view class="picker-value" :class="{ muted: member.unknown }">
                  {{ member.unknown ? '不详' : member.date || '请选择' }} ›
                </view>
              </picker>
            </view>

            <view class="person-row">
              <text class="person-label">日期不详</text>
              <switch
                :checked="member.unknown"
                color="#A8442A"
                style="transform: scale(0.8)"
                @change="onUnknown(member, $event)"
              />
            </view>
          </view>
        </template>

        <template v-else>
          <view class="card-title">
            <text>仙命信息</text>
            <button class="plain-button link tiny" @click="addPerson('deceased')">＋ 添加</button>
          </view>
          <text class="hint section-hint">
            仙命按年干支纳音参与坐山、分金与三煞比对。出生日期不详时可留空，分析会标注待补充。
          </text>

          <view v-for="(person, index) in deceased" :key="`d-${index}`" class="person-card">
            <view class="person-head">
              <text class="person-index">仙命 {{ index + 1 }}</text>
              <button
                v-if="deceased.length > 1"
                class="plain-button tiny danger-text"
                @click="removePerson('deceased', index)"
              >
                移除
              </button>
            </view>
            <view class="person-row">
              <text class="person-label">称谓</text>
              <input v-model="person.label" class="mini-text" maxlength="12" placeholder="先人" />
            </view>
            <view class="person-row">
              <text class="person-label">出生日期</text>
              <picker
                mode="date"
                :value="person.date || '1950-01-01'"
                start="1900-01-01"
                end="2026-12-31"
                :disabled="person.unknown"
                @change="onDate(person, $event)"
              >
                <view class="picker-value" :class="{ muted: person.unknown }">
                  {{ person.unknown ? '不详' : person.date || '请选择' }} ›
                </view>
              </picker>
            </view>
            <view class="person-row">
              <text class="person-label">日期不详</text>
              <switch
                :checked="person.unknown"
                color="#A8442A"
                style="transform: scale(0.8)"
                @change="onUnknown(person, $event)"
              />
            </view>
          </view>

          <view class="card-title top-gap">
            <text>家属信息（择日参考）</text>
            <button class="plain-button link tiny" @click="addPerson('descendants')">＋ 添加</button>
          </view>
          <view v-for="(person, index) in descendants" :key="`f-${index}`" class="person-card">
            <view class="person-head">
              <text class="person-index">家属 {{ index + 1 }}</text>
              <button
                v-if="descendants.length > 1"
                class="plain-button tiny danger-text"
                @click="removePerson('descendants', index)"
              >
                移除
              </button>
            </view>
            <view class="person-row">
              <text class="person-label">称谓</text>
              <input v-model="person.label" class="mini-text" maxlength="12" placeholder="家属" />
            </view>
            <view class="person-row">
              <text class="person-label">出生日期</text>
              <picker
                mode="date"
                :value="person.date || '1990-01-01'"
                start="1920-01-01"
                end="2026-12-31"
                :disabled="person.unknown"
                @change="onDate(person, $event)"
              >
                <view class="picker-value" :class="{ muted: person.unknown }">
                  {{ person.unknown ? '不详' : person.date || '请选择' }} ›
                </view>
              </picker>
            </view>
            <view class="person-row">
              <text class="person-label">日期不详</text>
              <switch
                :checked="person.unknown"
                color="#A8442A"
                style="transform: scale(0.8)"
                @change="onUnknown(person, $event)"
              />
            </view>
          </view>

          <view class="card-title top-gap"><text>周边环境</text></view>
          <view class="terrain-row">
            <text class="person-label">后方</text>
            <picker mode="selector" :range="backOptions" range-key="label" @change="terrain.backSupport = backOptions[Number($event.detail.value)].value">
              <view class="picker-value">{{ backOptions.find((item) => item.value === terrain.backSupport)?.label }} ›</view>
            </picker>
          </view>
          <view class="terrain-row">
            <text class="person-label">前方</text>
            <picker mode="selector" :range="frontOptions" range-key="label" @change="terrain.frontView = frontOptions[Number($event.detail.value)].value">
              <view class="picker-value">{{ frontOptions.find((item) => item.value === terrain.frontView)?.label }} ›</view>
            </picker>
          </view>
          <view class="terrain-row">
            <text class="person-label">左右</text>
            <picker mode="selector" :range="sideOptions" range-key="label" @change="terrain.leftRight = sideOptions[Number($event.detail.value)].value">
              <view class="picker-value">{{ sideOptions.find((item) => item.value === terrain.leftRight)?.label }} ›</view>
            </picker>
          </view>
          <view class="terrain-row">
            <text class="person-label">入首龙</text>
            <picker mode="selector" :range="dragonOptions" range-key="label" @change="terrain.incomingDragon = dragonOptions[Number($event.detail.value)].value">
              <view class="picker-value">{{ dragonOptions.find((item) => item.value === terrain.incomingDragon)?.label }} ›</view>
            </picker>
          </view>
          <text class="tiny muted">入首龙用于正五行「补龙」判定；不确定时留空，择日结果会显式标注该项数据缺口。</text>
          <view class="field top-gap">
            <text class="field-label">水路或排水情况（选填）</text>
            <input v-model="terrain.waterFlow" class="input" maxlength="40" placeholder="例如：左前方有排水沟" />
          </view>
          <view class="field">
            <text class="field-label">现场备注（选填）</text>
            <textarea v-model="terrain.notes" class="textarea" maxlength="200" placeholder="记录道路、台阶、植被、界址等现场信息" />
          </view>
        </template>
      </view>

      <view v-if="step === 3" class="card summary">
        <view class="card-title"><text>提交前核对</text></view>
        <view class="summary-row"><text>档案</text><text>{{ title }}</text></view>
        <view class="summary-row"><text>类型</text><text>{{ modeFullLabel(mode) }}</text></view>
        <view class="summary-row"><text>年份 / 运</text><text>{{ eventYear }} 年 · {{ period }}运</text></view>
        <view class="summary-row"><text>坐向</text><text>{{ pair.text }} · {{ degreeText(draft.compass.facingDeg) }}</text></view>
        <view v-if="mode === 'YANG'" class="summary-row">
          <text>居住者</text><text>{{ members.length }} 人</text>
        </view>
        <template v-else>
          <view class="summary-row"><text>仙命</text><text>{{ deceased.length }} 位</text></view>
          <view class="summary-row">
            <text>分金</text><text>{{ fenJin?.slot.ganZhi }} · {{ fenJin?.slot.qualityDetail }}</text>
          </view>
        </template>
        <text class="hint summary-hint">
          提交后档案保存在本机，可随时回到档案页修改信息或重新定向。完整分析需按份解锁。
        </text>
      </view>

      <view class="action-spacer" />
    </view>

    <view class="action-bar">
      <button class="btn btn-ghost" @click="prev">{{ step === 1 ? '取消' : '上一步' }}</button>
      <button v-if="step < 3" class="btn btn-primary" @click="next">下一步</button>
      <button v-else class="btn btn-primary" :disabled="submitting" @click="submit">
        {{ submitting ? '正在建立…' : '建立档案' }}
      </button>
    </view>
  </view>
</template>

<style scoped>
.wizard {
  --bg: #F7F3EC;
  --surface: #FDFAF4;
  --surface-2: #F0EADC;
  --surface-warm: #FAF5EB;
  --ink: #1C1A17;
  --ink-2: #3D3630;
  --ink-3: #6B5E52;
  --muted: #8C8074;
  --accent: #B03A2E;
  --accent-soft: rgba(176, 58, 46, 0.08);
  --accent-faint: rgba(176, 58, 46, 0.04);
  --jade: #2D5A4A;
  --jade-soft: rgba(45, 90, 74, 0.08);
  --gold: #A08048;
  --gold-soft: rgba(160, 128, 72, 0.12);
  --line-gold: rgba(160, 128, 72, 0.25);
  --danger: #8E3B2F;
  --line: rgba(28, 26, 23, 0.08);
  --radius: 16rpx;
  --radius-lg: 24rpx;
  --radius-sm: 8rpx;
  --shadow-card: 0 2rpx 16rpx rgba(28, 26, 23, 0.04);
  --page-padding: 36rpx;

  min-height: 100vh;
  padding-bottom: calc(176rpx + env(safe-area-inset-bottom));
  background:
    radial-gradient(circle at 100% 0, var(--gold-soft), transparent 34%),
    var(--bg);
  color: var(--ink);
  font-size: 26rpx;
  line-height: 1.6;
  box-sizing: border-box;
}

.shell {
  width: 100%;
  max-width: 900rpx;
  margin: 0 auto;
  padding: 0 var(--page-padding);
  box-sizing: border-box;
}

.serif,
.wizard-title,
.card-title,
.reading-name,
.fenjin-name {
  font-family: "Songti SC", "STSong", "Noto Serif CJK SC", serif;
}

.wizard-head {
  padding: 48rpx 0 36rpx;
}

.eyebrow {
  display: block;
  color: var(--gold);
  font-size: 18rpx;
  font-weight: 600;
  letter-spacing: 0.28em;
  line-height: 1.4;
}

.wizard-title {
  display: block;
  margin-top: 10rpx;
  color: var(--ink);
  font-size: 46rpx;
  font-weight: 600;
  letter-spacing: 0.06em;
  line-height: 1.35;
}

.steps {
  display: flex;
  align-items: flex-start;
  margin-top: 38rpx;
}

.step {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  min-width: 0;
  color: var(--muted);
}

.step:not(:last-child)::after {
  content: "";
  position: absolute;
  top: 30rpx;
  left: calc(50% + 40rpx);
  width: calc(100% - 80rpx);
  border-top: 2rpx dashed var(--line-gold);
}

.step-num {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 60rpx;
  height: 60rpx;
  border: 2rpx solid var(--line-gold);
  border-radius: var(--radius-sm);
  background: var(--surface-warm);
  box-shadow: inset 0 0 0 4rpx var(--surface-warm), inset 0 0 0 6rpx var(--line-gold);
  color: var(--gold);
  font-family: "Songti SC", "STSong", serif;
  font-size: 25rpx;
  font-weight: 700;
  line-height: 1;
  box-sizing: border-box;
}

.step-name {
  font-size: 21rpx;
  letter-spacing: 0.08em;
  line-height: 1.4;
}

.step.active {
  color: var(--accent);
}

.step.active .step-num {
  border-color: var(--accent);
  background: var(--accent);
  box-shadow: inset 0 0 0 4rpx var(--accent), inset 0 0 0 6rpx rgba(253, 250, 244, 0.7), 0 4rpx 12rpx var(--accent-soft);
  color: var(--surface);
}

.step.done {
  color: var(--jade);
}

.step.done .step-num {
  border-color: var(--jade);
  background: var(--jade-soft);
  box-shadow: inset 0 0 0 4rpx var(--bg), inset 0 0 0 6rpx var(--jade);
  color: var(--jade);
}

.card {
  position: relative;
  padding: 34rpx 30rpx;
  border: 1rpx solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-card);
  box-sizing: border-box;
}

.card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  margin-bottom: 26rpx;
  color: var(--ink);
  font-size: 30rpx;
  font-weight: 600;
  letter-spacing: 0.06em;
  line-height: 1.45;
}

.card-title > text:first-child {
  position: relative;
  padding-left: 20rpx;
}

.card-title > text:first-child::before {
  content: "";
  position: absolute;
  top: 0.25em;
  bottom: 0.25em;
  left: 0;
  width: 5rpx;
  border-radius: 2rpx;
  background: var(--accent);
}

.mode-switch {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18rpx;
}

.mode-option {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 8rpx;
  min-height: 148rpx;
  margin: 0;
  padding: 26rpx 24rpx;
  overflow: hidden;
  border: 1rpx solid var(--line-gold);
  border-radius: var(--radius);
  background: var(--surface-warm);
  color: var(--ink-2);
  text-align: left;
  line-height: 1.4;
  box-sizing: border-box;
}

.mode-option::before {
  content: "";
  position: absolute;
  inset: 7rpx;
  border: 1rpx solid var(--line-gold);
  border-radius: 10rpx;
  pointer-events: none;
}

.mode-option::after,
.option-chip::after,
.mini-seg-item::after,
.btn::after,
.plain-button::after {
  border: none;
}

.mode-option.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  box-shadow: 0 5rpx 18rpx var(--accent-faint);
  color: var(--accent);
}

.mode-option.active::before {
  border-color: rgba(176, 58, 46, 0.28);
}

.mode-option-title {
  position: relative;
  color: var(--ink);
  font-size: 33rpx;
  font-weight: 600;
  letter-spacing: 0.12em;
}

.mode-option.active .mode-option-title {
  color: var(--accent);
}

.mode-option-desc {
  position: relative;
  color: var(--muted);
  font-size: 20rpx;
  line-height: 1.5;
}

.top-gap,
.field {
  margin-top: 30rpx;
}

.field-label {
  display: block;
  margin-bottom: 12rpx;
  color: var(--ink-2);
  font-size: 24rpx;
  font-weight: 500;
  letter-spacing: 0.03em;
}

.input,
.picker-field,
.textarea,
.mini-text {
  border: 1rpx solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--surface-warm);
  color: var(--ink);
  box-sizing: border-box;
}

.input,
.picker-field {
  width: 100%;
  min-height: 86rpx;
  padding: 0 24rpx;
  font-size: 26rpx;
  line-height: 86rpx;
}

.textarea {
  width: 100%;
  min-height: 184rpx;
  padding: 20rpx 24rpx;
  font-size: 25rpx;
  line-height: 1.7;
}

.picker-field {
  display: flex;
  align-items: center;
}

.hint {
  color: var(--muted);
  font-size: 21rpx;
  line-height: 1.75;
}

.field > .hint {
  display: block;
  margin-top: 12rpx;
}

.muted {
  color: var(--muted);
}

.tiny {
  font-size: 21rpx;
}

.row,
.row-between {
  display: flex;
  align-items: center;
}

.row {
  gap: 16rpx;
}

.row-between {
  justify-content: space-between;
  gap: 20rpx;
}

.option-row {
  display: flex;
  gap: 14rpx;
}

.option-row.wrap {
  flex-wrap: wrap;
}

.option-chip {
  min-height: 68rpx;
  margin: 0;
  padding: 0 26rpx;
  border: 1rpx solid var(--line);
  border-radius: 999rpx;
  background: var(--surface-warm);
  color: var(--ink-3);
  font-size: 23rpx;
  line-height: 68rpx;
}

.option-chip.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 500;
}

.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 42rpx;
  padding: 0 16rpx;
  border: 1rpx solid transparent;
  border-radius: 999rpx;
  font-size: 19rpx;
  font-weight: 500;
  letter-spacing: 0.04em;
  line-height: 1;
  box-sizing: border-box;
}

.badge.info {
  border-color: rgba(45, 90, 74, 0.16);
  background: var(--jade-soft);
  color: var(--jade);
}

.badge.caution {
  border-color: var(--line-gold);
  background: var(--gold-soft);
  color: var(--gold);
}

.reading-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  padding: 28rpx 26rpx;
  border: 1rpx solid var(--line-gold);
  border-radius: var(--radius);
  background: linear-gradient(135deg, var(--surface-warm), var(--accent-faint));
}

.reading-name {
  display: block;
  color: var(--ink);
  font-size: 38rpx;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.reading-deg {
  display: block;
  margin-top: 6rpx;
  color: var(--ink-3);
  font-size: 23rpx;
  letter-spacing: 0.04em;
}

.reading-side {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  align-items: flex-end;
  gap: 10rpx;
}

.fenjin-box {
  margin-top: 20rpx;
  padding: 24rpx 26rpx;
  border: 1rpx solid rgba(45, 90, 74, 0.16);
  border-radius: var(--radius);
  background: var(--jade-soft);
}

.fenjin-name {
  display: block;
  margin: 12rpx 0 8rpx;
  color: var(--jade);
  font-size: 29rpx;
  font-weight: 600;
}

.warn {
  display: block;
  margin-top: 12rpx;
  color: var(--danger);
}

.divider {
  height: 1rpx;
  margin: 30rpx 0 0;
  background: linear-gradient(90deg, transparent, var(--line-gold), transparent);
}

.actions {
  margin-top: 26rpx;
}

.actions .btn {
  flex: 1;
}

.apply {
  flex-shrink: 0;
  min-width: 126rpx;
}

.hint-box {
  margin-top: 24rpx;
  padding: 20rpx 22rpx;
  border-left: 4rpx solid var(--line-gold);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--surface-warm);
}

.section-hint {
  display: block;
  margin: -10rpx 0 24rpx;
}

.person-card {
  margin-top: 20rpx;
  padding: 0 24rpx;
  overflow: hidden;
  border: 1rpx solid var(--line);
  border-radius: var(--radius);
  background: var(--surface-warm);
  box-shadow: inset 3rpx 0 0 var(--gold-soft);
}

.person-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 76rpx;
}

.person-index {
  color: var(--accent);
  font-size: 22rpx;
  font-weight: 600;
  letter-spacing: 0.12em;
}

.person-row,
.terrain-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  min-height: 84rpx;
  border-top: 1rpx solid var(--line);
}

.terrain-row {
  padding: 0 4rpx;
}

.person-label {
  flex-shrink: 0;
  color: var(--ink-2);
  font-size: 24rpx;
}

.picker-value {
  color: var(--accent);
  font-size: 24rpx;
  text-align: right;
}

.picker-value.muted {
  color: var(--muted);
}

.mini-text {
  width: 260rpx;
  height: 64rpx;
  padding: 0 18rpx;
  text-align: right;
  font-size: 24rpx;
  line-height: 64rpx;
}

.mini-seg {
  display: flex;
  padding: 5rpx;
  border: 1rpx solid var(--line);
  border-radius: 999rpx;
  background: var(--surface-2);
}

.mini-seg-item {
  min-width: 76rpx;
  min-height: 50rpx;
  margin: 0;
  padding: 0 20rpx;
  border-radius: 999rpx;
  background: transparent;
  color: var(--ink-3);
  font-size: 21rpx;
  line-height: 50rpx;
}

.mini-seg-item.active {
  background: var(--surface);
  box-shadow: 0 2rpx 8rpx var(--line);
  color: var(--accent);
  font-weight: 600;
}

.danger-text {
  color: var(--danger);
}

.summary {
  margin-top: 26rpx;
  border-color: var(--line-gold);
  background: var(--surface-warm);
  box-shadow: inset 0 0 0 7rpx var(--surface-warm), inset 0 0 0 8rpx var(--line-gold), var(--shadow-card);
}

.summary .card-title {
  padding-bottom: 20rpx;
  border-bottom: 1rpx solid var(--line-gold);
}

.summary-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 28rpx;
  padding: 18rpx 2rpx;
  border-bottom: 1rpx dashed var(--line-gold);
  color: var(--ink-2);
  font-size: 24rpx;
  line-height: 1.6;
}

.summary-row text:first-child {
  flex-shrink: 0;
  color: var(--muted);
}

.summary-row text:last-child {
  color: var(--ink);
  text-align: right;
}

.summary-hint {
  display: block;
  margin-top: 22rpx;
  padding-top: 4rpx;
}

.btn {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 88rpx;
  margin: 0;
  padding: 0 28rpx;
  border: 1rpx solid transparent;
  border-radius: var(--radius-sm);
  font-size: 26rpx;
  font-weight: 500;
  letter-spacing: 0.06em;
  line-height: 1.4;
  box-sizing: border-box;
}

.btn-sm {
  min-height: 76rpx;
  padding: 0 24rpx;
  font-size: 24rpx;
}

.btn-primary {
  border-color: var(--accent);
  background: var(--accent);
  box-shadow: 0 5rpx 14rpx var(--accent-soft);
  color: var(--surface);
}

.btn-ghost {
  border-color: var(--line-gold);
  background: var(--surface-warm);
  color: var(--ink-2);
}

.btn[disabled] {
  border-color: var(--line);
  background: var(--surface-2);
  box-shadow: none;
  color: var(--muted);
  opacity: 0.75;
}

.plain-button {
  min-height: auto;
  margin: 0;
  padding: 8rpx 0 8rpx 16rpx;
  background: transparent;
  line-height: 1.4;
}

.plain-button.link {
  color: var(--accent);
}

.action-spacer {
  height: 28rpx;
}

.action-bar {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 20;
  display: flex;
  gap: 20rpx;
  padding: 22rpx var(--page-padding) calc(22rpx + env(safe-area-inset-bottom));
  border-top: 1rpx solid var(--line-gold);
  background: rgba(250, 245, 235, 0.88);
  box-shadow: 0 -8rpx 30rpx rgba(28, 26, 23, 0.05);
  backdrop-filter: blur(20rpx) saturate(1.15);
  -webkit-backdrop-filter: blur(20rpx) saturate(1.15);
  box-sizing: border-box;
}

.action-bar .btn {
  flex: 1;
}
</style>
