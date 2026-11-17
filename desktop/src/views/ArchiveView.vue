<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import type { EvaluationSnapshot } from '@core/archive'
import { useArchiveStore } from '../archive/store'
import type { WorkbenchState } from '../workbench'

const props = defineProps<{ state: WorkbenchState; snapshot?: EvaluationSnapshot | null }>()
const emit = defineEmits<{ open: [state: WorkbenchState]; scan: [] }>()

// reactive 包一层：模板里自动解包 ref，不必到处写 .value
const store = reactive(useArchiveStore())
const titleDraft = ref('')
const editingId = ref('')
const editTitle = ref('')
const message = ref('')

const current = computed(() => store.current())
const dirty = computed(() => store.isDirty(props.state))
const suggestedTitle = computed(() => store.defaultTitle(props.state))

const CATEGORY_LABELS: Record<string, string> = {
  YANG_RUZHAI: '入宅安床',
  YANG_DONGTU: '动土修造',
  YANG_JIAQU: '嫁娶订盟',
  YANG_KAISHI: '开市交易',
  YIN_ANZANG: '安葬破土',
  YIN_XIUFEN: '修坟立碑',
}

function timeText(ts: number): string {
  const d = new Date(ts)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function saveCurrent() {
  // 保存时把当前扫描结论一并写进档案，作为下次 diff 的基准。
  // 没有扫描结果（snapshot 为空）时只存输入，不编造结论。
  const saved = await store.save(
    props.state,
    titleDraft.value || undefined,
    props.snapshot ?? undefined,
  )
  if (saved) {
    titleDraft.value = ''
    message.value = `已保存「${saved.title}」`
  }
}

function openArchive(id: string) {
  const next = store.open(id)
  if (!next) return
  emit('open', next)
  message.value = '已载入档案，请重新扫描'
}

function newArchive() {
  store.startNew()
  message.value = '已新建工作台（尚未保存）'
}

async function removeArchive(id: string, title: string) {
  const ok = window.confirm(`删除档案「${title}」？删除后无法在应用内恢复。`)
  if (!ok) return
  await store.remove(id)
  message.value = '已删除'
}

async function exportArchive(id: string) {
  const file = await store.exportOne(id)
  if (file) {
    message.value = `已导出到 ${file}`
  } else if (store.errorMessage) {
    message.value = ''
  } else {
    message.value = '已取消导出'
  }
}

async function importArchive() {
  const imported = await store.importOne()
  if (!imported) return
  emit('open', imported.state)
  message.value = `已导入「${imported.title}」`
}

function beginRename(id: string, title: string) {
  if (store.readOnly) return
  editingId.value = id
  editTitle.value = title
}

async function commitRename() {
  if (!editingId.value) return
  await store.rename(editingId.value, editTitle.value)
  editingId.value = ''
  editTitle.value = ''
}
</script>

<template>
  <section class="archive">
    <header class="bar">
      <div class="left">
        <span class="serif title">档案</span>
        <span class="muted">
          {{ store.archives.length }} 份 · 存在本机
          <template v-if="current"> · 当前「{{ current.title }}」</template>
          <template v-else> · 未关联档案</template>
        </span>
        <span v-if="current && dirty" class="chip warn">有未保存改动</span>
        <span v-else-if="current" class="chip ok">已保存</span>
      </div>
      <div class="right">
        <input
          v-model="titleDraft"
          class="input title-input"
          :placeholder="current ? '标题（留空沿用原名）' : suggestedTitle"
        />
        <button class="btn" @click="newArchive">新建</button>
        <button class="btn" :disabled="store.readOnly" @click="importArchive">导入…</button>
        <button
          class="btn primary"
          :disabled="store.saving || store.readOnly"
          @click="saveCurrent"
        >
          {{ store.saving ? '保存中…' : current ? '保存当前' : '保存为档案' }}
        </button>
      </div>
    </header>

    <p v-if="store.errorMessage" class="alert bad">{{ store.errorMessage }}</p>
    <p v-if="store.failures.length" class="alert warn">
      有 {{ store.failures.length }} 份档案无法读取（未覆盖原文件）：
      <span v-for="item in store.failures" :key="item.index">
        第 {{ item.index + 1 }} 份 —— {{ item.error }}；
      </span>
    </p>
    <p v-if="message" class="alert ok">{{ message }}</p>

    <div v-if="!store.ready" class="empty muted">正在读取档案…</div>

    <div v-else-if="!store.archives.length" class="empty">
      <p class="serif">还没有档案</p>
      <p class="muted">
        在「择日」里设好用事与坐向，回到这里点「保存为档案」。
        档案会记录完整输入、规则包版本与输入哈希，规则升级后可对比结论变化。
      </p>
    </div>

    <ul v-else class="list">
      <li
        v-for="item in store.archives"
        :key="item.id"
        class="row"
        :class="{ on: item.id === store.currentId }"
      >
        <div class="meta">
          <div class="line">
            <input
              v-if="editingId === item.id"
              v-model="editTitle"
              class="input inline"
              autofocus
              @keyup.enter="commitRename"
              @blur="commitRename"
            />
            <b v-else class="serif name" @dblclick="beginRename(item.id, item.title)">
              {{ item.title }}
            </b>
            <span v-if="item.id === store.currentId" class="chip ok">当前</span>
          </div>
          <div class="sub muted">
            {{ CATEGORY_LABELS[item.state.category] ?? item.state.category }} ·
            {{ item.state.mountShan }}山 {{ item.state.sittingDeg }}° ·
            {{ item.state.startDate }} 起 {{ item.state.daysCount }} 天
          </div>
          <div class="sub muted">
            更新 {{ timeText(item.updatedAt) }} · 规则包 {{ item.rulePackVersion }} ·
            哈希 {{ item.inputHash.slice(0, 8) }}
          </div>
          <div v-if="item.lastEvaluation" class="sub">
            <span class="chip mini">{{ item.lastEvaluation.verdict }}</span>
            上次结论 · 排除 {{ item.lastEvaluation.excludedDays ?? 0 }}/{{
              item.lastEvaluation.totalDays ?? 0
            }}
            天 · {{ timeText(item.lastEvaluation.evaluatedAt) }}
          </div>
        </div>
        <div class="ops">
          <button class="btn" @click="openArchive(item.id)">载入</button>
          <button class="btn" @click="exportArchive(item.id)">导出</button>
          <button
            class="btn danger"
            :disabled="store.readOnly"
            @click="removeArchive(item.id, item.title)"
          >
            删除
          </button>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.archive {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  overflow: auto;
}

.bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
}

.bar .left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.bar .right {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.title {
  font-size: 15px;
}

.chip {
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  border: 1px solid var(--line);
}

.chip.ok {
  color: var(--jade);
  border-color: var(--jade);
  background: var(--jade-soft);
}

.chip.warn {
  color: var(--gold);
  border-color: var(--gold);
  background: var(--gold-soft);
}

.chip.mini {
  padding: 0 6px;
  font-size: 10px;
  margin-right: 4px;
}

.alert {
  margin: 0;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
}

.alert.bad {
  color: var(--clay);
  background: var(--clay-soft);
}

.alert.warn {
  color: var(--gold);
  background: var(--gold-soft);
}

.alert.ok {
  color: var(--jade);
  background: var(--jade-soft);
}

.empty {
  padding: 40px 16px;
  text-align: center;
  border: 1px dashed var(--line);
  border-radius: 10px;
}

.empty p {
  margin: 4px 0;
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
}

.row.on {
  border-color: var(--jade);
  background: linear-gradient(0deg, var(--jade-soft), var(--surface));
}

.meta {
  min-width: 0;
  flex: 1;
}

.line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.name {
  font-size: 14px;
  cursor: text;
}

.sub {
  font-size: 11px;
  margin-top: 2px;
}

.ops {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.btn {
  padding: 5px 12px;
  border-radius: 7px;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink-2);
}

.btn:hover {
  border-color: var(--jade);
  color: var(--jade);
}

.btn.primary {
  border-color: var(--jade);
  background: var(--jade);
  color: #fff;
}

.btn.primary:disabled {
  opacity: 0.6;
}

.btn.danger {
  color: var(--clay);
}

.btn:disabled,
.btn:disabled:hover {
  opacity: 0.45;
  border-color: var(--line);
  color: var(--ink-2);
  cursor: not-allowed;
}

.btn.danger:disabled,
.btn.danger:disabled:hover {
  color: var(--clay);
}

/* 全局 .input 是 width:100%，放进 flex 工具栏会把按钮挤出去 */
.title-input {
  width: 210px;
  flex: 0 1 210px;
  min-width: 120px;
}

.input.inline {
  padding: 3px 6px;
  border: 1px solid var(--jade);
  border-radius: 6px;
  background: #fff;
}
</style>
