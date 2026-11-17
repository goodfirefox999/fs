<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { SHAN_24_LIST, branchOfMountain, getMountain, resolveMountain } from '@core/constants/shan24'
import { ZHI } from '@core/constants/nayin60'
import type { ZeRiCategory } from '@core/types'
import type { WorkbenchState } from '../workbench'

const props = defineProps<{ state: WorkbenchState }>()
const emit = defineEmits<{ scan: [] }>()

const CATEGORIES: Array<{ value: ZeRiCategory; label: string; hint: string }> = [
  { value: 'YANG_RUZHAI', label: '入宅安床', hint: '搬移、安床、入宅' },
  { value: 'YANG_DONGTU', label: '动土修造', hint: '动土、修造、起基、拆卸' },
  { value: 'YANG_JIAQU', label: '嫁娶订盟', hint: '嫁娶、纳采、订盟' },
  { value: 'YANG_KAISHI', label: '开市交易', hint: '开市、交易、立券' },
  { value: 'YIN_ANZANG', label: '安葬破土', hint: '安葬、启钻、破土' },
  { value: 'YIN_XIUFEN', label: '修坟立碑', hint: '修坟、立碑、谢土' },
]

const mountains = SHAN_24_LIST.map((item) => item.name)
const hourBranches = ['', ...ZHI]

const sitting = computed(() => getMountain(props.state.mountShan))
const sittingBranch = computed(() => branchOfMountain(props.state.mountShan))
const facing = computed(() => mountains[(sitting.value.index + 12) % 24])

/**
 * 线度实际落在哪一山。模板里无条件展示，必须始终有值：
 * 之前这里漏了定义，`degMountain.name` 一渲染就抛 TypeError，整个左侧面板白屏。
 */
const degMountain = computed(() => resolveMountain(Number(props.state.sittingDeg) || 0))

/**
 * 手输线度导致山名跳变时的短暂提示。
 * 不做自动消失的强提示，只在 1.4s 内说明「为什么我选的山变了」——
 * 否则用户会以为是自己点错了。
 */
const shanFlash = ref(false)
let flashTimer: ReturnType<typeof setTimeout> | undefined
onUnmounted(() => {
  if (flashTimer) clearTimeout(flashTimer)
})

const isYin = computed(
  () => props.state.category === 'YIN_ANZANG' || props.state.category === 'YIN_XIUFEN',
)

function addSubject() {
  props.state.subjects.push({ label: `主命${props.state.subjects.length + 1}`, date: '', gender: 'M' })
}

/**
 * 坐山名与线度必须同源：判定（三煞占山、大卦抽爻）看的是线度，
 * 只改山名不改线度会让界面显示「坐亥山」而实际按子山度数判定。
 * 选山名 → 取该山中线；填线度 → 反推所属山名（兼向就在线度里改）。
 */
function pickShan(name: string) {
  props.state.mountShan = name
  props.state.sittingDeg = getMountain(name).centerDeg
}

function commitDeg() {
  const deg = Number(props.state.sittingDeg)
  if (!Number.isFinite(deg)) return
  const norm = ((deg % 360) + 360) % 360
  props.state.sittingDeg = Number(norm.toFixed(1))
  const next = resolveMountain(norm)
  const jumped = next.name !== props.state.mountShan
  props.state.mountShan = next.name
  if (jumped) {
    shanFlash.value = true
    if (flashTimer) clearTimeout(flashTimer)
    flashTimer = setTimeout(() => {
      shanFlash.value = false
    }, 1400)
  }
}

function addDeceased() {
  props.state.deceased.push({ label: `仙命${props.state.deceased.length + 1}`, date: '', gender: 'M' })
}
</script>

<template>
  <aside class="panel">
    <section class="card">
      <div class="card-title"><span>用事</span></div>
      <div class="cat-grid">
        <button
          v-for="item in CATEGORIES"
          :key="item.value"
          class="cat"
          :class="{ on: state.category === item.value }"
          @click="state.category = item.value; emit('scan')"
        >
          <b>{{ item.label }}</b>
          <em>{{ item.hint }}</em>
        </button>
      </div>
    </section>

    <section class="card">
      <div class="card-title"><span>坐向</span></div>
      <div class="field">
        <label class="field-label" for="shan">坐山（向首自动取对宫）</label>
        <select
          id="shan"
          :value="state.mountShan"
          class="select"
          @change="pickShan(($event.target as HTMLSelectElement).value); emit('scan')"
        >
          <option v-for="name in mountains" :key="name" :value="name">{{ name }}山 · {{ name === state.mountShan ? `向${facing}` : '' }}</option>
        </select>
      </div>
      <div class="field">
        <label class="field-label" for="deg">坐山线度（用于玄空大卦抽爻、三煞占山）</label>
        <input
          id="deg"
          v-model.number="state.sittingDeg"
          class="input"
          type="number"
          step="0.1"
          min="0"
          max="359.9"
          @change="commitDeg(); emit('scan')"
        />
        <p v-if="shanFlash" class="tip">
          线度落到{{ degMountain.name }}山，坐山已按线度更正（判定看线度，不看旧选择）。
        </p>
      </div>
      <div class="row-2">
        <span class="chip" :class="{ warn: degMountain.name !== state.mountShan }">度落 {{ degMountain.name }}山</span>
        <span class="chip">{{ sitting.centerDeg }}° 山中线</span>
        <span class="chip">坐山支 {{ sittingBranch || '无（取卦宫）' }}</span>
        <span class="chip">向首 {{ facing }}山</span>
        <span class="chip">三元龙 {{ { TIAN: '天元', DI: '地元', REN: '人元' }[sitting.yuan] }}</span>
      </div>
      <label v-if="state.category === 'YANG_RUZHAI'" class="switch" style="margin-bottom: 10px">
        <input v-model="state.includesConstruction" type="checkbox" @change="emit('scan')" />
        <span>本次入宅伴随动土、修造或安门</span>
      </label>
      <p v-if="state.category === 'YANG_RUZHAI'" class="tip">
        {{ state.includesConstruction
          ? '已按兴工类处理：年家与月家三煞占山恢复硬排除。'
          : '纯入宅不兴工，三煞占山不适用；若实际要动工，请勾选此项或改用「动土修造」。' }}
      </p>
      <div class="field">
        <label class="field-label" for="dragon">入首龙（{{ isYin ? '阴宅补龙用' : '未采集时补龙规则标记数据缺口' }}）</label>
        <select id="dragon" v-model="state.incomingDragon" class="select">
          <option value="">未确认</option>
          <option v-for="name in mountains" :key="name" :value="name">{{ name }}山</option>
        </select>
      </div>
    </section>

    <section class="card">
      <div class="card-title"><span>扫描范围</span></div>
      <div class="row-2">
        <div class="field" style="flex: 1; margin: 0">
          <label class="field-label" for="start">起始日期</label>
          <input id="start" v-model="state.startDate" class="input" type="date" />
        </div>
        <div class="field" style="width: 96px; margin: 0">
          <label class="field-label" for="days">天数</label>
          <select id="days" v-model.number="state.daysCount" class="select">
            <option :value="30">30</option>
            <option :value="60">60</option>
            <option :value="90">90</option>
            <option :value="180">180</option>
          </select>
        </div>
      </div>
      <div class="field" style="margin-top: 10px">
        <label class="field-label" for="hour">日课时支（定出后才判调候、日破、时破）</label>
        <select id="hour" v-model="state.hourBranch" class="select">
          <option v-for="item in hourBranches" :key="item" :value="item">{{ item ? `${item}时` : '不指定' }}</option>
        </select>
      </div>
    </section>

    <section class="card">
      <div class="card-title">
        <span>人员</span>
        <span class="mini">
          <button class="linkbtn" @click="addSubject">+主命</button>
          <button class="linkbtn" @click="addDeceased">+仙命</button>
        </span>
      </div>
      <div v-for="(person, key) in state.subjects" :key="`s${key}`" class="person">
        <input v-model="person.label" class="input name" />
        <input v-model="person.date" class="input" type="date" />
        <select v-model="person.gender" class="select sex">
          <option value="M">男</option>
          <option value="F">女</option>
        </select>
        <button class="linkbtn del" @click="state.subjects.splice(key, 1)">删</button>
      </div>
      <div v-for="(person, key) in state.deceased" :key="`d${key}`" class="person">
        <input v-model="person.label" class="input name" />
        <input v-model="person.date" class="input" type="date" />
        <select v-model="person.gender" class="select sex">
          <option value="M">男</option>
          <option value="F">女</option>
        </select>
        <button class="linkbtn del" @click="state.deceased.splice(key, 1)">删</button>
      </div>
      <p class="tip">主命与仙命都参与「冲命」硬排除；相主评分只看第一位主命。</p>
    </section>

    <section class="card">
      <div class="card-title"><span>严格度与筛选</span></div>
      <div class="field">
        <label class="field-label" for="sansha">三煞硬排除层级（默认随用事类型）</label>
        <select id="sansha" v-model="state.sanShaMode" class="select" @change="emit('scan')">
          <option value="year">仅年家占山硬排（月/日/时与日课相犯作提示）</option>
          <option value="year_month">年家＋月家占山硬排（默认）</option>
          <option value="all">四家占山＋日课相犯全部硬排</option>
        </select>
        <p class="tip">
          三档口径：「仅年家」= 只忌本年煞方兴工，月/日/时与日课相犯都降为提示，适合你确认只按年家论煞的流派；
          「年家＋月家」= 兴工与葬事的通书常规口径，也是本工作台默认；
          「整层」= 连日家、时家占山与时支犯日煞一并硬排，适合阴宅大事或你要求最严的场景。
          年家三煞占山在兴工口径下始终不可放宽；纯入宅（不勾伴随动工）时四条占山规则都不参与判定。
        </p>
      </div>
      <div class="switch-list">
        <label class="switch">
          <input v-model="state.jinShenMode" type="checkbox" true-value="reject" false-value="warn" @change="emit('scan')" />
          <span>金神七煞硬排除</span>
        </label>
        <label class="switch">
          <input v-model="state.folkMode" type="checkbox" true-value="reject" false-value="warn" @change="emit('scan')" />
          <span>民俗神煞硬排除（四废、往亡、十恶大败、大败、杨公忌；受死除外）</span>
        </label>
        <label class="switch">
          <input v-model="state.chongSangMode" type="checkbox" true-value="reject" false-value="warn" @change="emit('scan')" />
          <span>重丧日硬排除（口诀两系并存，默认按提示）</span>
        </label>
        <label class="switch">
          <input v-model="state.onlyHuangDao" type="checkbox" @change="emit('scan')" />
          <span>只看黄道日</span>
        </label>
        <label class="switch">
          <input v-model="state.avoidXiuXiong" type="checkbox" @change="emit('scan')" />
          <span>避开二十八宿判凶之日</span>
        </label>
        <label class="switch">
          <input v-model="state.yaoOrder" type="checkbox" true-value="DESC" false-value="ASC" @change="emit('scan')" />
          <span>大卦爻位逆排</span>
        </label>
      </div>
      <p class="tip">
        不可放宽项只有历法事实与官书明文两类：岁破、月破、日破、时破、冲坐山、冲主命与仙命、四离四绝、
        协纪等第「诸事皆忌」，以及兴工口径下的年家三煞占山。
        杨公忌、四废、往亡、十恶大败、大败属通书沿用的民俗口径，默认硬排但可关；
        受死按《协纪辨方书》卷六「并仍旧历从删」恒作提示，任何开关都不会把它升级为排除，重丧同理另有独立开关。
        其余开关只改变显示口径，原始判定一律保留在排除统计中。
      </p>
      <button class="btn primary scan" @click="emit('scan')">立即重扫</button>
    </section>
  </aside>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 336px;
  flex-shrink: 0;
}

.cat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.cat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink-2);
}

.cat b {
  font-family: var(--serif);
  font-size: 14px;
  color: var(--ink);
}

.cat em {
  font-style: normal;
  font-size: 11px;
  color: var(--muted);
}

.cat.on {
  border-color: var(--jade);
  background: var(--jade-soft);
}

.row-2 {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  flex-wrap: wrap;
}

.person {
  display: grid;
  grid-template-columns: 62px 1fr 52px 26px;
  gap: 6px;
  margin-bottom: 6px;
  align-items: center;
}

.person .sex,
.person .del {
  padding: 6px 4px;
  text-align: center;
}

.linkbtn {
  border: none;
  background: none;
  color: var(--jade);
  padding: 2px 4px;
  font-size: 12px;
}

.linkbtn.del {
  color: var(--clay);
}

.tip {
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.6;
}

.switch-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.switch {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-2);
  font-size: 12px;
}

.switch input {
  accent-color: var(--jade);
}

.scan {
  width: 100%;
  margin-top: 10px;
}

.mini {
  display: flex;
  gap: 4px;
}
</style>
