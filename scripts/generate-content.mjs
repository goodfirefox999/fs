import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const outDir = path.join(root, 'cloudfunctions/getReportContent/content')

const STARS = {
  1: {
    name: '一白', element: '水', theme: '流动、沟通与思路',
    inner: '作息、思路与信息流动', outer: '沟通、人际与资源流动',
    action: '保持该区通风与光线柔和，可放置常用书籍或通讯设备。',
    yinAction: '保持纪念地前方视野通透、排水顺畅，通道不积水。',
  },
  2: {
    name: '二黑', element: '土', theme: '承载、积累与迟缓',
    inner: '休息、恢复与承载力', outer: '积累、库存与回款节奏',
    action: '减少长期堆物，保持地面干燥，适合储物或短时休整。',
    yinAction: '检查墓区周边排水与土壤湿度，避免长期积水与塌陷。',
  },
  3: {
    name: '三碧', element: '木', theme: '生发、行动与摩擦',
    inner: '行动力、成长与情绪张力', outer: '推进、竞争与沟通摩擦',
    action: '避免频繁搬动与尖锐摆设，可用绿植或木质收纳柔化空间。',
    yinAction: '控制植被过度生长与根系侵入，保持通道与界址清晰。',
  },
  4: {
    name: '四绿', element: '木', theme: '秩序、学习与细节',
    inner: '学习、专注与细节处理', outer: '文书、协作与流程秩序',
    action: '适合学习、阅读或需要专注的工作位，保持桌面整洁。',
    yinAction: '保持标识、界址与档案信息清晰，便于后续维护。',
  },
  5: {
    name: '五黄', element: '土', theme: '集中、厚重与静止',
    inner: '压力集中与节奏停滞', outer: '资源集中与变动阻力',
    action: '不宜作为长期停留的主位，保持通畅、整洁与适度照明。',
    yinAction: '避免大范围硬化与开挖，保持原有地形与排水路径稳定。',
  },
  6: {
    name: '六白', element: '金', theme: '结构、规则与执行',
    inner: '结构感、规则与执行力', outer: '管理、制度与外部协作',
    action: '适合规则明确的工作区，金属物件收纳归位，避免尖锐外露。',
    yinAction: '检查挡土、护坡与界桩结构，优先处理结构性风险。',
  },
  7: {
    name: '七赤', element: '金', theme: '表达、更新与取舍',
    inner: '表达、取舍与情绪起伏', outer: '谈判、更新与外部变化',
    action: '适合需要表达与沟通的区域，注意控制音量与光线刺激。',
    yinAction: '减少不必要的金属装饰与尖锐构件，保持环境简洁。',
  },
  8: {
    name: '八白', element: '土', theme: '稳固、积累与结果',
    inner: '稳定、积累与身体感受', outer: '成果、资产与长期回报',
    action: '适合稳定收纳与长期使用的家具，保持承重与动线安全。',
    yinAction: '保持地形稳定与排水顺畅，避免在松软土体上增加重载。',
  },
  9: {
    name: '九紫', element: '火', theme: '显现、关系与热度',
    inner: '关系、情绪与可见度', outer: '展示、社交与热度',
    action: '适合社交与展示，注意用电安全与光线过热。',
    yinAction: '注意明火与用电安全，避免在干燥季节堆积易燃物。',
  },
}

const ELEMENT_SHENG = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' }
const ELEMENT_KE = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' }

function relationOf(a, b) {
  if (a === b) return 'BI_HE'
  if (ELEMENT_SHENG[a] === b) return 'SHENG'
  if (ELEMENT_KE[a] === b) return 'KE'
  if (ELEMENT_SHENG[b] === a) return 'BEI_SHENG'
  return 'BEI_KE'
}

const RELATION_TEXT = {
  SHENG: '两星相生，多理解为内外节奏可以相互承接，宜把休息区与活动区分开，避免互相打扰。',
  KE: '两星相克，多理解为内外节奏存在拉扯，宜先稳定作息，再安排外部事务。',
  BI_HE: '两星同气，多理解为节奏一致，容易形成惯性，宜设定清晰的边界与使用时段。',
  BEI_SHENG: '向星生山星，多理解为外部资源回流到内部，适合沉淀、整理与修整。',
  BEI_KE: '向星克山星，多理解为外部事务牵动内部节奏，需预留休息与缓冲。',
}

const CLASSIC_TEXT = {
  SHENG: '传统飞星以山星对应内在与居住状态、向星对应外部与资源流动。本组合两星相生，按内外相承理解，供空间安排参考。',
  KE: '传统飞星以山星对应内在与居住状态、向星对应外部与资源流动。本组合两星相克，按内外拉扯理解，供空间安排参考。',
  BI_HE: '传统飞星以山星对应内在与居住状态、向星对应外部与资源流动。本组合两星同气，按节奏一致理解，供空间安排参考。',
  BEI_SHENG: '传统飞星以山星对应内在与居住状态、向星对应外部与资源流动。本组合向星生山星，按外部回流理解，供空间安排参考。',
  BEI_KE: '传统飞星以山星对应内在与居住状态、向星对应外部与资源流动。本组合向星克山星，按外部牵动理解，供空间安排参考。',
}

const RISK_TEXT = {
  balanced: '整体节奏偏平稳，可按实际采光、通风与使用频率安排功能，不必因单一组合做大拆大改。',
  attention: '组合中含有需要留意的星曜，宜减少长期停留与过度装饰，优先保持通风、采光与通道畅通。',
  active: '五黄参与组合，传统上宜静不宜动；保持整洁、通风与适度照明，避免大范围拆改。',
}

const YIN_RISK_TEXT = {
  balanced: '整体宜保持原有地形与排水路径，按现场条件做最小必要维护。',
  attention: '宜重点检查排水、边坡与植被，不做大范围硬化或开挖。',
  active: '五黄参与时更宜保持现状稳定，避免大范围硬化、开挖与重载。',
}

function riskLevelOf(shan, xiang) {
  if (shan === 5 || xiang === 5) return 'active'
  if ([2, 7].includes(shan) || [2, 7].includes(xiang)) return 'attention'
  return 'balanced'
}

function unique(list) {
  return Array.from(new Set(list.filter(Boolean)))
}

const entries = []
for (let shan = 1; shan <= 9; shan++) {
  for (let xiang = 1; xiang <= 9; xiang++) {
    const s = STARS[shan]
    const x = STARS[xiang]
    const relation = relationOf(s.element, x.element)
    const riskLevel = riskLevelOf(shan, xiang)
    const title = `山${s.name} · 向${x.name}`
    const analysis = `山星${s.name}（${s.element}）主${s.theme}，关联${s.inner}；向星${x.name}（${x.element}）主${x.theme}，关联${x.outer}。${RELATION_TEXT[relation]}${RISK_TEXT[riskLevel]}`
    const yinAnalysis = `在纪念地环境建档中，山星对应靠山与地形稳定，向星对应前方视野与排水。山星${s.name}（${s.element}）关联${s.inner}，向星${x.name}（${x.element}）关联${x.outer}。${RELATION_TEXT[relation]}${YIN_RISK_TEXT[riskLevel]}`
    entries.push({
      id: `S${shan}X${xiang}`,
      combo: { shan, xiang },
      title,
      classic: {
        source: '传统飞星组合通义（整理）',
        paraphrase: CLASSIC_TEXT[relation],
      },
      analysis,
      actions: unique([s.action, x.action, RISK_TEXT[riskLevel]]),
      yin: {
        analysis: yinAnalysis,
        actions: unique([
          s.yinAction,
          x.yinAction,
          '以现场排水、边坡稳定、通道安全与植被维护为先，必要时请地质或结构专业人员评估。',
        ]),
      },
      riskLevel,
      reviewStatus: 'editorial-v1',
      version: 1,
    })
  }
}

const banned = [
  '算命', '占卜', '预测', '改运', '转运', '化煞', '破解', '开光', '加持', '消灾',
  '解难', '辟邪', '镇宅', '大师', '祖传', '秘法', '灵验', '最灵', '保证', '必然',
  '凶宅', '血光', '破财', '灾祸', '克夫', '克妻', '绝后', '损丁', '庇佑',
  '升官发财', '鬼怪', '寻龙点穴',
]
const payload = JSON.stringify({ version: '2026.10.1', shuangxing: entries }, null, 2)
for (const word of banned) {
  if (payload.includes(word)) {
    throw new Error(`内容库命中禁词: ${word}`)
  }
}

if (entries.length !== 81) throw new Error(`双星组合数量错误: ${entries.length}`)

fs.mkdirSync(outDir, { recursive: true })
fs.writeFileSync(path.join(outDir, 'shuangxing.json'), payload, 'utf8')
console.log(`generated ${entries.length} combos -> ${path.relative(root, outDir)}/shuangxing.json`)
