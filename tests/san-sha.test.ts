import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  DASHA_FAMILY,
  DASHA_GUIDANCE,
  DASHA_RULE_IDS,
  DASHA_STANCE,
  FOLK_DASHA_RULE_IDS,
  NON_NEGOTIABLE_DASHA,
  SAN_SHA_COURSE_RULES,
  SAN_SHA_MOUNTAIN_RULES,
  checkDasha,
  defaultSanShaLax,
  familyOf,
  guidanceFor,
  isNegotiable,
  stanceOf,
  type DashaInput,
} from '@/core/zeri/dasha'
import { evaluateDay } from '@/core/zeri/evaluate'
import type { ZeRiCategory } from '@/core/types'

const CATEGORIES: ZeRiCategory[] = [
  'YANG_RUZHAI',
  'YANG_DONGTU',
  'YIN_ANZANG',
  'YIN_XIUFEN',
]

/**
 * 戌年午月亥日卯时、坐子山：年家与月家三合局煞同在北（亥子丑）故占山，
 * 日家（亥卯未煞西）与时家（卯 → 煞西）不占山，日支亥落年煞方属「日课犯年煞」。
 * 已避开岁破（冲戌为辰）、月破（冲午为子）、日破/时破、冲山、十恶大败与金神七煞，
 * 让这条数据只覆盖三煞分层。
 */
function input(patch: Partial<DashaInput> = {}): DashaInput {
  return {
    date: '2026-12-08',
    yearGanZhi: '甲戌',
    yearStem: '甲',
    yearBranch: '戌',
    monthBranch: '午',
    dayBranch: '亥',
    dayGanZhi: '乙亥',
    hourBranch: '卯',
    mountShan: '子',
    mountDeg: 0,
    subjectBranches: [],
    badGods: [],
    behavior: 'YI_AND_JI',
    category: 'YIN_ANZANG',
    includesConstruction: false,
    xiu: '翼',
    lunarMonth: 10,
    lunarDay: 30,
    warnOnly: defaultSanShaLax('YIN_ANZANG'),
    ...patch,
  }
}

const ids = (list: { ruleId: string }[]) => list.map((item) => item.ruleId)

describe('三煞按年、月、日、时分层', () => {
  it('占山四条与日课相犯两条分列，不把「日支犯年三煞」叫作日三煞', () => {
    expect(SAN_SHA_MOUNTAIN_RULES).toEqual([
      'D3_YEAR_SAN_SHA_ON_MOUNTAIN',
      'D3_MONTH_SAN_SHA_ON_MOUNTAIN',
      'D3_DAY_SAN_SHA_ON_MOUNTAIN',
      'D3_HOUR_SAN_SHA_ON_MOUNTAIN',
    ])
    expect(SAN_SHA_COURSE_RULES).toEqual(['D3_DAY_ON_YEAR_SAN_SHA', 'D3_HOUR_ON_DAY_SAN_SHA'])
    for (const id of [...SAN_SHA_MOUNTAIN_RULES, ...SAN_SHA_COURSE_RULES]) {
      expect(DASHA_RULE_IDS).toContain(id)
    }
  })

  it('戌年午月坐子山（葬事）：年家与月家占山默认硬排除，日时家三煞在西不占山', () => {
    const result = checkDasha(input())
    expect(ids(result.hits)).toContain('D3_YEAR_SAN_SHA_ON_MOUNTAIN')
    expect(ids(result.hits)).toContain('D3_MONTH_SAN_SHA_ON_MOUNTAIN')
    expect(ids(result.warned)).toContain('D3_DAY_ON_YEAR_SAN_SHA')
    const all = ids(result.hits).concat(ids(result.warned))
    expect(all).not.toContain('D3_DAY_SAN_SHA_ON_MOUNTAIN')
    expect(all).not.toContain('D3_HOUR_SAN_SHA_ON_MOUNTAIN')
  })

  it('葬事默认月家硬排除、入宅默认整层提示；显式白名单可把月家降为提示', () => {
    const funeral = defaultSanShaLax('YIN_ANZANG')
    expect(funeral).not.toContain('D3_YEAR_SAN_SHA_ON_MOUNTAIN')
    expect(funeral).not.toContain('D3_MONTH_SAN_SHA_ON_MOUNTAIN')
    expect(funeral).toEqual(
      expect.arrayContaining([
        'D3_DAY_SAN_SHA_ON_MOUNTAIN',
        'D3_HOUR_SAN_SHA_ON_MOUNTAIN',
        ...SAN_SHA_COURSE_RULES,
      ]),
    )
    expect(defaultSanShaLax('YANG_RUZHAI')).toEqual(SAN_SHA_COURSE_RULES)
    expect(defaultSanShaLax('YANG_RUZHAI', true)).toContain('D3_DAY_SAN_SHA_ON_MOUNTAIN')
    // 嫁娶、开市不是兴工类：不得因「非入宅」就套用年家三煞占山硬排除。
    expect(defaultSanShaLax('YANG_JIAQU')).toEqual(SAN_SHA_COURSE_RULES)
    expect(defaultSanShaLax('YANG_KAISHI')).toEqual(SAN_SHA_COURSE_RULES)
    expect(
      isNegotiable('D3_YEAR_SAN_SHA_ON_MOUNTAIN', {
        category: 'YANG_JIAQU',
        includesConstruction: false,
      }),
    ).toBe(true)

    const monthWarned = checkDasha(input({ warnOnly: ['D3_MONTH_SAN_SHA_ON_MOUNTAIN'] }))
    expect(ids(monthWarned.warned)).toContain('D3_MONTH_SAN_SHA_ON_MOUNTAIN')
    expect(ids(monthWarned.hits)).toContain('D3_YEAR_SAN_SHA_ON_MOUNTAIN')
    expect(monthWarned.rejected).toBe(true)

    const strict = checkDasha(input({ warnOnly: [] }))
    expect(ids(strict.hits)).toEqual(
      expect.arrayContaining(['D3_YEAR_SAN_SHA_ON_MOUNTAIN', 'D3_MONTH_SAN_SHA_ON_MOUNTAIN']),
    )
  })

  it('纯入宅四条占山三煞全部不适用；其余用事年家仍硬排除', () => {
    for (const category of CATEGORIES) {
      const result = checkDasha(input({ category, warnOnly: defaultSanShaLax(category) }))
      const present = ids(result.hits)
        .concat(ids(result.warned))
        .filter((id) => SAN_SHA_MOUNTAIN_RULES.includes(id))
      if (category === 'YANG_RUZHAI') {
        expect(present, '纯入宅不应出现任何占山三煞').toEqual([])
      } else {
        expect(present).toContain('D3_YEAR_SAN_SHA_ON_MOUNTAIN')
      }
    }
  })

  it('入宅勾选伴随动土后按兴工类恢复占山判定', () => {
    const withWork = checkDasha(
      input({
        category: 'YANG_RUZHAI',
        includesConstruction: true,
        warnOnly: defaultSanShaLax('YANG_RUZHAI', true),
      }),
    )
    expect(ids(withWork.hits)).toContain('D3_YEAR_SAN_SHA_ON_MOUNTAIN')
  })

  it('时家三煞两条都要先指定日课时支才可能参与', () => {
    // 申子辰三煞在南（巳午未），午时既犯日家三煞、又占子山之煞方。
    const noHour = checkDasha(
      input({ hourBranch: null, dayBranch: '申', dayGanZhi: '壬申' }),
    )
    const present = ids(noHour.hits).concat(ids(noHour.warned))
    expect(present).not.toContain('D3_HOUR_SAN_SHA_ON_MOUNTAIN')
    expect(present).not.toContain('D3_HOUR_ON_DAY_SAN_SHA')

    const withHour = checkDasha(input({ dayBranch: '申', dayGanZhi: '壬申', hourBranch: '午' }))
    expect(ids(withHour.warned)).toContain('D3_HOUR_ON_DAY_SAN_SHA')
    expect(ids(withHour.warned)).toContain('D3_HOUR_SAN_SHA_ON_MOUNTAIN')
  })
})

describe('可放宽性的事件分级', () => {
  const matrix: Array<
    [string, { category: ZeRiCategory; includesConstruction: boolean }, boolean]
  > = [
    ['D3_YEAR_SAN_SHA_ON_MOUNTAIN', { category: 'YIN_ANZANG', includesConstruction: false }, false],
    ['D3_YEAR_SAN_SHA_ON_MOUNTAIN', { category: 'YANG_DONGTU', includesConstruction: false }, false],
    ['D3_YEAR_SAN_SHA_ON_MOUNTAIN', { category: 'YANG_RUZHAI', includesConstruction: true }, false],
    ['D3_YEAR_SAN_SHA_ON_MOUNTAIN', { category: 'YANG_RUZHAI', includesConstruction: false }, true],
    ['D3_MONTH_SAN_SHA_ON_MOUNTAIN', { category: 'YIN_ANZANG', includesConstruction: false }, true],
    ['D3_MONTH_SAN_SHA_ON_MOUNTAIN', { category: 'YANG_RUZHAI', includesConstruction: false }, true],
    ['D3_DAY_SAN_SHA_ON_MOUNTAIN', { category: 'YANG_RUZHAI', includesConstruction: false }, true],
    ['D3_HOUR_SAN_SHA_ON_MOUNTAIN', { category: 'YIN_ANZANG', includesConstruction: false }, true],
    ['D3_DAY_SAN_SHA_ON_MOUNTAIN', { category: 'YANG_RUZHAI', includesConstruction: true }, true],
    ['D3_DAY_ON_YEAR_SAN_SHA', { category: 'YIN_ANZANG', includesConstruction: false }, true],
    ['D3_HOUR_ON_DAY_SAN_SHA', { category: 'YANG_RUZHAI', includesConstruction: false }, true],
    ['D3_SUI_PO', { category: 'YANG_RUZHAI', includesConstruction: true }, false],
    ['D3_CHONG_SHAN', { category: 'YANG_RUZHAI', includesConstruction: true }, false],
  ]

  it.each(matrix)('%s 在 %j 下 negotiable=%s', (ruleId, ctx, expected) => {
    expect(isNegotiable(ruleId, ctx)).toBe(expected)
  })

  it('纯入宅下日课相犯与日时占山均可放宽；兴工口径的年家占山不可放宽', () => {
    const pure = { category: 'YANG_RUZHAI' as const, includesConstruction: false }
    for (const ruleId of ['D3_MONTH_SAN_SHA_ON_MOUNTAIN', 'D3_DAY_SAN_SHA_ON_MOUNTAIN', 'D3_HOUR_SAN_SHA_ON_MOUNTAIN']) {
      expect(isNegotiable(ruleId, pure), ruleId).toBe(true)
    }
    expect(isNegotiable('D3_YEAR_SAN_SHA_ON_MOUNTAIN', pure)).toBe(true)
    const work = { category: 'YANG_RUZHAI' as const, includesConstruction: true }
    expect(isNegotiable('D3_YEAR_SAN_SHA_ON_MOUNTAIN', work)).toBe(false)

    // 不可放宽项由规则层拦住：写进白名单也不会真的降为提示
    const result = checkDasha(input({ warnOnly: ['D3_YEAR_SAN_SHA_ON_MOUNTAIN', 'D3_SUI_PO'] }))
    expect(ids(result.warned)).not.toContain('D3_YEAR_SAN_SHA_ON_MOUNTAIN')
    expect(ids(result.warned)).not.toContain('D3_SUI_PO')
    expect(ids(result.hits)).toContain('D3_YEAR_SAN_SHA_ON_MOUNTAIN')
  })
})

describe('三煞硬排除层级', () => {
  it('仅年家：月家降为提示；整层：六条全部升级且不留下任何降级项', () => {
    const onlyYear = checkDasha(
      input({ warnOnly: defaultSanShaLax('YIN_ANZANG', false, 'year') }),
    )
    expect(ids(onlyYear.warned)).toContain('D3_MONTH_SAN_SHA_ON_MOUNTAIN')
    expect(ids(onlyYear.hits)).toContain('D3_YEAR_SAN_SHA_ON_MOUNTAIN')

    const whole = checkDasha(input({ warnOnly: defaultSanShaLax('YIN_ANZANG', false, 'all') }))
    expect(whole.warned).toHaveLength(0)
    expect(ids(whole.hits)).toEqual(
      expect.arrayContaining([
        'D3_YEAR_SAN_SHA_ON_MOUNTAIN',
        'D3_MONTH_SAN_SHA_ON_MOUNTAIN',
        'D3_DAY_ON_YEAR_SAN_SHA',
      ]),
    )
    // 日家、时家三煞在西，本就不占子山；时支卯也不犯日家三煞
    expect(ids(whole.hits)).not.toContain('D3_DAY_SAN_SHA_ON_MOUNTAIN')
    expect(ids(whole.hits)).not.toContain('D3_HOUR_ON_DAY_SAN_SHA')

    expect(defaultSanShaLax('YIN_ANZANG', false, 'all')).toEqual([])
  })

  it('层级经 evaluateDay 生效：2026-11-02 午年戌月坐子山，年家与月家同落煞方', () => {
    const base = {
      date: '2026-11-02',
      category: 'YIN_ANZANG' as const,
      mountShan: '子',
      sittingDeg: 0,
      eventYear: 2026,
    }
    const byLevel = (level: 'year' | 'year_month' | 'all') =>
      evaluateDay({ ...base, sanShaPolicy: level })

    const relaxed = byLevel('year').dasha
    expect(ids(relaxed.hits)).toContain('D3_YEAR_SAN_SHA_ON_MOUNTAIN')
    expect(ids(relaxed.hits)).not.toContain('D3_MONTH_SAN_SHA_ON_MOUNTAIN')
    expect(ids(relaxed.warned)).toContain('D3_MONTH_SAN_SHA_ON_MOUNTAIN')

    const standard = byLevel('year_month').dasha
    expect(ids(standard.hits)).toContain('D3_MONTH_SAN_SHA_ON_MOUNTAIN')

    const strict = byLevel('all').dasha
    const shaRules = [...SAN_SHA_MOUNTAIN_RULES, ...SAN_SHA_COURSE_RULES]
    expect(ids(strict.warned).filter((id) => shaRules.includes(id))).toEqual([])
    expect(ids(strict.hits)).toContain('D3_MONTH_SAN_SHA_ON_MOUNTAIN')
  })
})

describe('占山与日课相犯的结构分开', () => {
  it('时家三煞的煞方由时支起，不是由日支起（否则与日家占山同解）', () => {
    // 亥日申时坐午山：亥卯未煞西不占午；申子辰煞南，正是午山 → 只有时家条命中。
    const result = checkDasha(
      input({
        dayBranch: '亥',
        dayGanZhi: '乙亥',
        hourBranch: '申',
        mountShan: '午',
        mountDeg: 180,
        warnOnly: defaultSanShaLax('YIN_ANZANG'),
      }),
    )
    expect(ids(result.warned)).toContain('D3_HOUR_SAN_SHA_ON_MOUNTAIN')
    expect(ids(result.warned)).toContain('D3_HOUR_ON_DAY_SAN_SHA')
    const all = ids(result.hits).concat(ids(result.warned))
    expect(all).not.toContain('D3_DAY_SAN_SHA_ON_MOUNTAIN')
    // 同一天里两条的煞方来源不同：日支定的是「相犯」，时支定的是「占山」
    expect(familyOf('D3_HOUR_SAN_SHA_ON_MOUNTAIN')).toBe('SAN_SHA_MOUNTAIN')
    expect(familyOf('D3_HOUR_ON_DAY_SAN_SHA')).toBe('SAN_SHA_COURSE')
  })

  it('命中项带上 family，且每条三煞都有归属（防漏标）', () => {
    const result = checkDasha(input())
    for (const hit of [...result.hits, ...result.warned]) {
      expect(hit.family, hit.ruleId).toBeTruthy()
    }
    for (const id of [...SAN_SHA_MOUNTAIN_RULES, ...SAN_SHA_COURSE_RULES]) {
      expect(DASHA_FAMILY[id], id).toBeDefined()
    }
    const unknown = Object.keys(DASHA_FAMILY).filter((id) => !DASHA_RULE_IDS.includes(id))
    expect(unknown, `DASHA_FAMILY 里有多余 id：${unknown.join(', ')}`).toEqual([])
    expect(familyOf('D3_SUI_PO')).toBe('GENERAL')
  })

  it('民俗口径条目自成一区，与三煞层级分歧分列', () => {
    // 受死与杨公忌都属民俗；三煞层级降级项属流派口径分歧。
    expect(FOLK_DASHA_RULE_IDS).toEqual(
      expect.arrayContaining(['D3_SHOU_SI', 'D3_YANG_GONG_JI', 'D3_SI_FEI', 'D3_CHONG_SANG']),
    )
    const folk = new Set(FOLK_DASHA_RULE_IDS)
    for (const id of [...SAN_SHA_MOUNTAIN_RULES, ...SAN_SHA_COURSE_RULES]) {
      expect(folk.has(id), id).toBe(false)
    }
  })

  it('杨公忌按通书口径默认为硬排除，但可随民俗开关降级（不再是不可放宽项）', () => {
    const ctx = { category: 'YIN_ANZANG' as const, includesConstruction: false }
    expect(isNegotiable('D3_YANG_GONG_JI', ctx)).toBe(true)
    expect(NON_NEGOTIABLE_DASHA).not.toContain('D3_YANG_GONG_JI')

    const kept = checkDasha(input({ badGods: [], warnOnly: [] }))
    expect(ids(kept.hits)).not.toContain('D3_YANG_GONG_JI')

    const hard = checkDasha(input({ lunarMonth: 5, lunarDay: 5, warnOnly: [] }))
    expect(ids(hard.hits)).toContain('D3_YANG_GONG_JI')
    const relaxed = checkDasha(
      input({ lunarMonth: 5, lunarDay: 5, warnOnly: ['D3_YANG_GONG_JI'] }),
    )
    expect(ids(relaxed.warned)).toContain('D3_YANG_GONG_JI')
    expect(relaxed.rejected).toBe(true) // 该场景年家三煞占山仍在排除
    expect(guidanceFor('D3_YANG_GONG_JI')).toContain('官书未列明文')
  })
})

describe('官书从删的煞不静默硬排除', () => {
  it('受死即使只把其余条目列为提示也不导致排除', () => {
    // 纯入宅 + 未定时支：受死成为场景里唯一可能升级为排除的大煞，降级只能来自规则层本身。
    const result = checkDasha(
      input({
        category: 'YANG_RUZHAI',
        hourBranch: null,
        badGods: ['受死'],
        warnOnly: SAN_SHA_COURSE_RULES,
      }),
    )
    expect(ids(result.hits)).not.toContain('D3_SHOU_SI')
    expect(ids(result.warned)).toContain('D3_SHOU_SI')
    expect(result.rejected).toBe(false)
    expect(guidanceFor('D3_SHOU_SI')).toContain('从删')
  })

  it('四废仍受民俗开关控制，与受死区别对待', () => {
    const strict = checkDasha(input({ badGods: ['四废'], warnOnly: [] }))
    expect(ids(strict.hits)).toContain('D3_SI_FEI')
  })
})

describe('排除说明的完整性', () => {
  it('每条大煞都有非空说明（防止键写错导致界面静默变空）', () => {
    expect(DASHA_RULE_IDS.length).toBeGreaterThanOrEqual(22)
    const missing = DASHA_RULE_IDS.filter((id) => !DASHA_GUIDANCE[id]?.trim())
    expect(missing, `缺说明的大煞规则：${missing.join(', ')}`).toEqual([])
    for (const id of DASHA_RULE_IDS) {
      expect(guidanceFor(id, { category: 'YIN_ANZANG', includesConstruction: false })).toBe(
        DASHA_GUIDANCE[id],
      )
    }
  })

  it('入宅含动土时三煞占山说明切换为兴工口径', () => {
    const text = guidanceFor('D3_YEAR_SAN_SHA_ON_MOUNTAIN', {
      category: 'YANG_RUZHAI',
      includesConstruction: true,
    })
    expect(text).toContain('已勾选')
    expect(text).not.toBe(DASHA_GUIDANCE.D3_YEAR_SAN_SHA_ON_MOUNTAIN)
  })
})

describe('正煞与傍煞的严重度标注', () => {
  it('煞区五山中，中间一支的三山为正煞，两端一支为傍煞', () => {
    // 午年三煞在北：亥(330) 壬(345) 子(0) 癸(15) 丑(30)
    const gradeOf = (deg: number, shan: string) =>
      checkDasha(input({ mountShan: shan, mountDeg: deg, warnOnly: [] })).hits.find(
        (hit) => hit.ruleId === 'D3_YEAR_SAN_SHA_ON_MOUNTAIN',
      )?.shaGrade

    expect(gradeOf(0, '子')).toBe('正煞')
    expect(gradeOf(345, '壬')).toBe('正煞')
    expect(gradeOf(15, '癸')).toBe('正煞')
    expect(gradeOf(330, '亥')).toBe('傍煞')
    expect(gradeOf(30, '丑')).toBe('傍煞')
    expect(gradeOf(337, '亥')).toBe('傍煞')
    expect(gradeOf(25, '丑')).toBe('傍煞')
  })

  it('线度落山与所选山名不符时，说明里按线度说', () => {
    const result = checkDasha(input({ mountShan: '亥', mountDeg: 345, warnOnly: [] }))
    const hit = result.hits.find((item) => item.ruleId === 'D3_YEAR_SAN_SHA_ON_MOUNTAIN')
    // 345° 落在壬山（正煞区），而所选山名写成亥（傍煞），必须暴露这个不一致
    expect(hit?.shaGrade).toBe('正煞')
    expect(hit?.reason).toContain('线度345°实落壬山')
  })

  it('分级只加标注，不改变 reject 与 negotiable', () => {
    const pang = checkDasha(input({ mountShan: '亥', mountDeg: 330, warnOnly: [] }))
    const zheng = checkDasha(input({ mountShan: '子', mountDeg: 0, warnOnly: [] }))
    const hit = (r: typeof pang) =>
      r.hits.find((item) => item.ruleId === 'D3_YEAR_SAN_SHA_ON_MOUNTAIN')
    expect(hit(pang)?.negotiable).toBe(false)
    expect(hit(zheng)?.negotiable).toBe(false)
    expect(pang.rejected).toBe(true)
    expect(hit(pang)?.shaGrade).toBe('傍煞')
    expect(hit(pang)?.reason).toContain('傍煞')
  })
})

describe('分类与立场登记的完整性', () => {
  it('每条大煞都必须登记 family，未登记直接抛错而不是静默归入通用类', () => {
    const missing = DASHA_RULE_IDS.filter((id) => !DASHA_FAMILY[id])
    expect(missing, `未登记 family 的大煞规则：${missing.join(', ')}`).toEqual([])
    const unknown = Object.keys(DASHA_FAMILY).filter((id) => !DASHA_RULE_IDS.includes(id))
    expect(unknown, `DASHA_FAMILY 里有多余 id：${unknown.join(', ')}`).toEqual([])
    // 只锁「抛错 + 指明规则 id + 说明要登记」，不锁具体措辞：
    // 报错文案属于实现细节，改文案不该让守卫失效，但放宽成 toThrow() 就测不到信息量了。
    expect(() => familyOf('D3_NOT_A_RULE')).toThrow(/D3_NOT_A_RULE.*登记/)
  })

  it('民俗区每条都有出处立场分档，非民俗条目不带 stance', () => {
    const missing = FOLK_DASHA_RULE_IDS.filter((id) => !DASHA_STANCE[id])
    expect(missing, `民俗区缺立场分档：${missing.join(', ')}`).toEqual([])
    expect(stanceOf('D3_SUI_PO')).toBeUndefined()

    const result = checkDasha(
      input({
        badGods: ['受死'],
        lunarMonth: 5,
        lunarDay: 5,
        warnOnly: defaultSanShaLax('YIN_ANZANG'),
      }),
    )
    expect(result.warned.find((hit) => hit.ruleId === 'D3_SHOU_SI')?.stance).toBe(
      'OFFICIAL_DELETED',
    )
    // 杨公忌默认仍是硬排除，但带上「原书未载·通书沿用」的分档，不与官书明文同权
    expect(result.hits.find((hit) => hit.ruleId === 'D3_YANG_GONG_JI')?.stance).toBe('FOLK_ONLY')
    expect(result.hits.find((hit) => hit.ruleId === 'D3_SUI_PO')?.stance).toBeUndefined()
  })
})

describe('桌面端复用路径', () => {
  it('src/core 不依赖 uni 运行时或 dcloudio 包', () => {
    const root = path.resolve(process.cwd(), 'src/core')
    const files = (fs.readdirSync(root, { recursive: true }) as string[])
      .map((name) => String(name))
      .filter((name) => name.endsWith('.ts'))
    expect(files.length).toBeGreaterThan(20)
    const offenders = files.filter((name) => {
      const text = fs.readFileSync(path.join(root, name), 'utf8')
      if (name.endsWith('.d.ts')) return false
      return /\buni\.[a-zA-Z]+\(/.test(text) || /from ['"]@dcloudio/.test(text)
    })
    expect(offenders, `core 中存在 uni 调用：${offenders.join(', ')}`).toEqual([])
  })

  it('入宅含动土与纯入宅给出不同的候选结果', () => {
    const base = {
      category: 'YANG_RUZHAI' as const,
      mountShan: '子',
      sittingDeg: 0,
      eventYear: 2026,
    }
    const pure = evaluateDay({ date: '2026-12-08', ...base })
    const work = evaluateDay({ date: '2026-12-08', ...base, includesConstruction: true })
    expect(pure.dasha.hits.some((hit) => hit.ruleId === 'D3_YEAR_SAN_SHA_ON_MOUNTAIN')).toBe(false)
    expect(pure.dasha.warned.some((hit) => SAN_SHA_MOUNTAIN_RULES.includes(hit.ruleId))).toBe(false)
    expect(work.dasha.hits.some((hit) => hit.ruleId === 'D3_YEAR_SAN_SHA_ON_MOUNTAIN')).toBe(true)
    expect(work.schools).toHaveLength(0)
  })
})
