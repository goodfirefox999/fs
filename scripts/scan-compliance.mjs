import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const targets = ['src', 'cloudfunctions', 'README.md']
const ignoreDirs = new Set(['node_modules', 'dist', 'unpackage', '.git'])

const ABSOLUTE = [
  '算命', '占卜', '预测', '改运', '转运', '化煞', '破解', '开光', '加持', '消灾',
  '解难', '辟邪', '镇宅', '大师', '祖传', '秘法', '灵验', '最灵', '保证', '必然',
  '凶宅', '血光', '破财', '灾祸', '克夫', '克妻', '绝后', '损丁', '庇佑',
  '升官发财', '鬼怪', '寻龙点穴',
]

const AD_LAW = ['最佳', '最强', '最好', '第一品牌', '唯一', '顶级', '绝对', '100%']
const CAUTIOUS = ['化解', '煞气', '吉凶', '风水', '阴阳宅', '丁财两旺']
const SWITCHES = ['enable_yinzhai_mode', 'reviewMode', 'auditMode', '隐藏入口', '审核开关']

// 施工依据 v1.0 附录 E 第 6 条：120 分金的旺相/孤虚/空亡吉凶口径未经三源核验，
// 首版不得在用户可见文案里出现。扫描 UI 模板与报告文案，硬阻断。
const FENJIN_VERDICT = ['旺相', '孤虚', '龟甲空亡', '煞曜']
const fenjinClaimFiles = (file) => /\.vue$/.test(file) || /src\/core\/engines\/(xianming|report)\.ts$/.test(file)

function isTextClaim(line) {
  if (/linear-gradient|radial-gradient|Math\.|toFixed|\.style|calc\(/.test(line)) return false
  if (/^\s*[\w-]+\s*:\s*[^;]*100%\s*;?\s*$/.test(line)) return false
  return true
}

function walk(target) {
  const full = path.join(root, target)
  if (!fs.existsSync(full)) return []
  const stat = fs.statSync(full)
  if (stat.isFile()) return [full]
  const files = []
  for (const name of fs.readdirSync(full)) {
    if (ignoreDirs.has(name)) continue
    files.push(...walk(path.join(target, name)))
  }
  return files
}

const files = targets.flatMap(walk).filter((file) => /\.(ts|js|vue|json|md|scss|css)$/.test(file))
const absoluteHits = []
const adHits = []
const cautiousHits = []
const switchHits = []
const fenjinHits = []

for (const file of files) {
  const relative = path.relative(root, file)
  const content = fs.readFileSync(file, 'utf8')
  const lines = content.split(/\r?\n/)
  lines.forEach((line, index) => {
    const at = `${relative}:${index + 1}`
    for (const word of ABSOLUTE) {
      if (line.includes(word)) absoluteHits.push(`${at}  ${word}`)
    }
    for (const word of AD_LAW) {
      if (!line.includes(word)) continue
      // 100% 多出现在 CSS 尺寸与数值计算中，只拦截文案式用法
      if (word === '100%' && !isTextClaim(line)) continue
      adHits.push(`${at}  ${word}`)
    }
    for (const word of CAUTIOUS) {
      if (line.includes(word)) cautiousHits.push(`${at}  ${word}`)
    }
    for (const word of SWITCHES) {
      if (line.includes(word)) switchHits.push(`${at}  ${word}`)
    }
    if (fenjinClaimFiles(relative)) {
      // 豁免说明合规约束的注释/免责声明：它们出现吉凶词是为了解释为何不输出。
      const isComplianceNote = /^\s*(\/\/|\*|\/\*|<!--|['"`])/.test(line)
        && /(未经|不得|未核验|红线|附录\s*E|不输出|禁止|合规)/.test(line)
      if (!isComplianceNote) {
        for (const word of FENJIN_VERDICT) {
          if (line.includes(word)) fenjinHits.push(`${at}  ${word}`)
        }
      }
    }
  })
}

console.log(`scanned ${files.length} files`)
if (absoluteHits.length) {
  console.error(`\n[禁词] ${absoluteHits.length}`)
  absoluteHits.forEach((hit) => console.error(`  ${hit}`))
}
if (adHits.length) {
  console.error(`\n[广告法] ${adHits.length}`)
  adHits.forEach((hit) => console.error(`  ${hit}`))
}
if (switchHits.length) {
  console.error(`\n[审核开关] ${switchHits.length}`)
  switchHits.forEach((hit) => console.error(`  ${hit}`))
}
if (fenjinHits.length) {
  console.error(`\n[分金红线] ${fenjinHits.length}（附录 E：未核验吉凶不得出现在用户可见文案）`)
  fenjinHits.forEach((hit) => console.error(`  ${hit}`))
}
if (cautiousHits.length) {
  console.warn(`\n[谨慎词] ${cautiousHits.length}（需人工确认语境）`)
  cautiousHits.forEach((hit) => console.warn(`  ${hit}`))
}

if (absoluteHits.length || adHits.length || switchHits.length || fenjinHits.length) {
  process.exit(1)
}
console.log('compliance scan passed')
