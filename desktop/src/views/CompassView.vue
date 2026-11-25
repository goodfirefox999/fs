<script setup lang="ts">
/**
 * 罗盘：现场读数 → 真北校正 → 采用为工作台坐向。
 *
 * 磁偏角只在本页参与换算，**不写进工作台状态**：
 * `state.sittingDeg` 永远存真北度数，这样择日/排盘/档案都只有一个口径，
 * 不需要为「磁北还是真北」再加一个会影响 inputHash 的字段。
 */
import { computed, ref } from 'vue'
import { SHAN_NAMES, getMountain, resolveMountain } from '@core/constants/shan24'
import { resolveFenJin } from '@core/constants/fenjin120'
import type { WorkbenchState } from '../workbench'
import CompassSvg from '../components/CompassSvg.vue'

const props = defineProps<{ state: WorkbenchState }>()
const emit = defineEmits<{ scan: [] }>()

type Mode = 'true' | 'magnetic'

const mode = ref<Mode>('true')
/** 真北直读时是线度；磁北模式下是磁北读数 */
const inputDeg = ref(Number(props.state.sittingDeg) || 0)
/** 磁偏角：东偏为正（我国大部分地区为西偏，取负值） */
const declination = ref(0)

function normalize(deg: number): number {
  const value = deg % 360
  return value < 0 ? value + 360 : value
}

const trueDeg = computed(() =>
  normalize(mode.value === 'true' ? inputDeg.value : inputDeg.value + declination.value),
)

const mountain = computed(() => resolveMountain(trueDeg.value))
const offset = computed(() => {
  const raw = ((trueDeg.value - mountain.value.centerDeg + 540) % 360) - 180
  return Math.round(raw * 10) / 10
})
const facing = computed(() => SHAN_NAMES[(mountain.value.index + 12) % 24])
const isJian = computed(() => Math.abs(offset.value) > 4.5)
const neighbor = computed(() => {
  const step = offset.value > 0 ? 1 : -1
  return SHAN_NAMES[(mountain.value.index + step + 24) % 24]
})
const fenJin = computed(() => resolveFenJin(trueDeg.value))

const YUAN_LABEL: Record<string, string> = { TIAN: '天元龙', DI: '地元龙', REN: '人元龙' }

const adopted = computed(
  () =>
    Math.abs(normalize(props.state.sittingDeg) - trueDeg.value) < 0.05 &&
    props.state.mountShan === mountain.value.name,
)

function adopt() {
  props.state.sittingDeg = Number(trueDeg.value.toFixed(1))
  props.state.mountShan = mountain.value.name
  emit('scan')
}

function useCurrent() {
  inputDeg.value = Number(props.state.sittingDeg) || 0
  mode.value = 'true'
}

function step(delta: number) {
  inputDeg.value = Math.round((normalize(inputDeg.value + delta) + Number.EPSILON) * 10) / 10
}
</script>

<template>
  <section class="compass-view">
    <div class="stage">
      <CompassSvg :deg="trueDeg" />
      <p class="hint">
        盘面按真北绘制；{{ mode === 'magnetic' ? '当前为磁北读数加磁偏角换算' : '当前为真北直读' }}。
      </p>
    </div>

    <aside class="panel">
      <section class="card">
        <div class="card-title"><span>读数</span></div>
        <div class="field">
          <label class="field-label">读数方式</label>
          <select v-model="mode" class="select">
            <option value="true">真北直读（罗盘已对真北 / 图纸角度）</option>
            <option value="magnetic">磁北读数 + 磁偏角</option>
          </select>
        </div>

        <div v-if="mode === 'magnetic'" class="field">
          <label class="field-label">磁偏角（东偏为正，西偏填负）</label>
          <input v-model.number="declination" class="input" type="number" step="0.1" min="-30" max="30" />
          <p class="tip">
            我国大部分地区磁偏角为西偏（负值），具体数值随地点与年份变化，请以当地磁偏角资料为准。
          </p>
        </div>

        <div class="field">
          <label class="field-label">
            {{ mode === 'true' ? '真北坐山线度' : '磁北读数' }}
          </label>
          <div class="deg-row">
            <button class="btn step" @click="step(-1)">−1°</button>
            <input
              v-model.number="inputDeg"
              class="input deg"
              type="number"
              step="0.1"
              min="0"
              max="359.9"
            />
            <button class="btn step" @click="step(1)">+1°</button>
          </div>
        </div>

        <button class="btn" @click="useCurrent">取当前工作台坐向</button>
      </section>

      <section class="card">
        <div class="card-title"><span>换算结果</span></div>
        <dl class="readout">
          <div><dt>真北线度</dt><dd class="serif">{{ trueDeg.toFixed(1) }}°</dd></div>
          <div><dt>坐山</dt><dd class="serif">{{ mountain.name }}山</dd></div>
          <div><dt>向首</dt><dd>{{ facing }}山</dd></div>
          <div>
            <dt>山中线偏移</dt>
            <dd :class="{ warn: isJian }">{{ offset > 0 ? '+' : '' }}{{ offset }}°</dd>
          </div>
          <div>
            <dt>兼向</dt>
            <dd :class="{ warn: isJian }">
              {{ isJian ? `兼${neighbor}（超 ±4.5°）` : '正针不兼' }}
            </dd>
          </div>
          <div><dt>三元龙</dt><dd>{{ YUAN_LABEL[mountain.yuan] }}</dd></div>
          <div>
            <dt>分金</dt>
            <dd>
              {{ fenJin.slot.ganZhi }} · {{ fenJin.slot.slotNote }}
            </dd>
          </div>
        </dl>

        <p v-if="fenJin.warning" class="alert warn">{{ fenJin.warning }}</p>

        <button class="btn primary" :disabled="adopted" @click="adopt">
          {{ adopted ? '已是当前坐向' : '采用为工作台坐向' }}
        </button>
        <p class="tip">
          采用后，择日与排盘都会按这个真北线度重算；磁偏角本身不写入档案。
        </p>
      </section>
    </aside>
  </section>
</template>

<style scoped>
.compass-view {
  flex: 1;
  display: flex;
  gap: 16px;
  min-width: 0;
  overflow: auto;
  padding: 4px 2px;
}

.stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  min-width: 0;
  padding-top: 8px;
}

.hint {
  margin: 0;
  color: var(--muted);
  font-size: 11px;
}

.panel {
  width: 340px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card {
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
}

.card-title {
  font-family: var(--serif);
  font-size: 14px;
  margin-bottom: 10px;
}

.field {
  margin-bottom: 10px;
}

.field-label {
  display: block;
  color: var(--muted);
  font-size: 11px;
  margin-bottom: 4px;
}

.input,
.select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: #fff;
}

.deg-row {
  display: flex;
  gap: 6px;
  align-items: center;
}

.input.deg {
  flex: 1;
  text-align: center;
  font-family: var(--serif);
  font-size: 16px;
}

.btn {
  padding: 6px 12px;
  border-radius: 7px;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink-2);
}

.btn:hover {
  border-color: var(--jade);
  color: var(--jade);
}

.btn.step {
  flex-shrink: 0;
  padding: 6px 10px;
}

.btn.primary {
  width: 100%;
  margin-top: 10px;
  border-color: var(--jade);
  background: var(--jade);
  color: #fff;
}

.btn.primary:disabled {
  opacity: 0.55;
  background: var(--surface);
  color: var(--muted);
  border-color: var(--line);
}

.readout {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.readout > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  padding-bottom: 5px;
  border-bottom: 1px dashed var(--line);
}

.readout > div:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.readout dt {
  color: var(--muted);
}

.readout dd {
  margin: 0;
  color: var(--ink);
  text-align: right;
}

.readout dd.warn {
  color: var(--gold);
}

.tip {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.6;
}

.alert {
  margin: 8px 0 0;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 11px;
}

.alert.warn {
  color: var(--gold);
  background: var(--gold-soft);
}
</style>
