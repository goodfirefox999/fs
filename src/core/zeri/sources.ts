import type { SourceRef } from './types'
import { createRegistry } from '../utils/registry'

/**
 * 出处登记表。规则里出现的所有 source 都必须来自这里，便于人工逐条核对。
 * verification 一律留在 unverified：只有人工核对后才能改成 verified_by_human，
 * machineCheck 字段记录的是「与哪个开源实现比对过、比对了多少天」，不等同于人工确认。
 */
const REGISTRY: Record<string, SourceRef> = {
  XIEJI_BASE: {
    id: 'XIEJI_BASE',
    title: '《钦定协纪辨方书》',
    locus: '清乾隆四年敕撰，通行四库全书本',
    modern: '起例数据移植自 cnlunar 6.x（MIT，OPN48），本项目按 2020–2035 年逐日比对',
    url: 'https://zh.wikisource.org/wiki/協紀辨方書',
    lineageNote: '原书同时收录「辨正」条款，部分民间神煞被官方否定；本产品只按原文起例列示，不作吉凶担保。',
  },
  LUNAR_ALMANAC: {
    id: 'LUNAR_ALMANAC',
    title: '通书宜忌与神煞（建除十二值、二十八宿、彭祖百忌、吉神宜趋、凶煞宜忌）',
    modern: '6tail/lunar-javascript（MIT）',
    url: 'https://github.com/6tail/lunar-javascript',
  },
  DONG_GONG: {
    id: 'DONG_GONG',
    title: '《董公选择要义》（董公择日）',
    locus: '坊刻本，卷次与作者流传版本复杂',
    modern: '本产品所用条目以《钦定协纪辨方书》卷三引《堪舆经》（金神）与《九天上圣秘传金符经》（九星）为核校依据',
    lineageNote: '《协纪辨方书》对金神按语本身存疑（「未必若是之甚」），且卷六明文删驳受死、龙虎、罪至三煞；本产品按民间通书口径列示并标注待人工复核。',
  },
  JIN_FU_JING: {
    id: 'JIN_FU_JING',
    title: '《九天上圣秘传金符经》九星轮值',
    locus: '妖星·惑星·禾刀·煞贡·直星·卜木·角己·人专·立早 九星顺行',
    modern: '四孟月甲子起妖星、四仲月起惑星、四季月起禾刀；故三星值日随月组而变，不存在脱离月份的固定六十甲子表',
    lineageNote: '官修《协纪辨方书》义例未收此九星，属道教/民间择日系统；「三吉星能解诸凶，唯不能解金神七煞」为其自我限定。',
  },
  ZONG_JING_SAN_HE: {
    id: 'ZONG_JING_SAN_HE',
    title: '三合禄马贵人起例（《选择宗镜》《协纪辨方书》三合类）',
    modern: '地支三合/六合/禄神/天乙贵人/驿马为通行口诀，另见规格附录「二十四山贵人到方速查表」',
    lineageNote: '二十四山贵人到方表存在纳甲派与正五行派两种写法，本产品采用规格提供的纳甲口径并要求人工复核。',
  },
  ZHENG_WU_XING: {
    id: 'ZHENG_WU_XING',
    title: '二十四山正五行与洪范（斗首）五行',
    modern: '正五行见《地理五诀》通行表；洪范五行另见斗首一派',
    lineageNote: '洪范（斗首）五行与正五行对同一山的归属不同，两派不可混用，本产品分开输出。',
  },
  DOU_SHOU: {
    id: 'DOU_SHOU',
    title: '斗首五行（二十四山斗首五行、十干化气、五星、番化）',
    locus: '旧题杨筠松一系，三僚传本；通行口诀「壬子巽巳辛戌土，艮寅丁未木，癸丑丙午乾亥火，坤申甲卯水，乙庚辰酉金」',
    modern: '化气取五运（甲己土、乙庚金、丙辛水、丁壬木、戊癸火）；五星按生克定位；番化诀见包内常量表',
    lineageNote:
      '斗首五行与正五行对同一山的归属不同（甲山斗首属水、正五行属木），两表不可混用。' +
      '三处待人工核对：①土行长生位（土寄坤在申／土寄艮在寅）两说，本包取申；' +
      '②贪狼（贪官）与廉贞（廉子）的吉凶各本不一，本包只给星名不给吉凶；' +
      '③三元/三武格的计数是否计月干，两说并存，本包按四柱全计。' +
      '因吉凶强度未考证，本包定位参考层，不参与五派仲裁。',
  },
  TIAO_HOU: {
    id: 'TIAO_HOU',
    title: '调候用神（《穷通宝鉴》体系）',
    modern: '本产品仅按「月令寒暖燥湿 ↔ 巳午未/亥子丑时辰」的通行法则判定，未收录 120 格全表',
    lineageNote: '调候用神与扶抑用神冲突时以扶抑为主，属流派取舍，需人工复核。',
  },
  XUAN_KONG_DA_GUA: {
    id: 'XUAN_KONG_DA_GUA',
    title: '玄空大卦（先天六十四卦圆图、卦运、抽爻换象）',
    locus: '旧题蒋大鸿《天元五歌》《地理辨证》一系；圆图排列据朱熹《原本周易本义·伏羲六十四卦方位图》「乾尽午中，坤尽子中，离尽卯中，坎尽酉中」',
    modern: '卦数口诀「乾九兑四皆是金，离三震八木成林，巽二坎七先天火，坤一艮六水是真」；爻位 0.9375° 由 360°/384 爻导出',
    url: 'https://m.dushu.com/guoxue/105156/1141561.html',
    lineageNote: '六十四卦配罗盘度数存在「64 卦等分圆周」与「分金/六十龙配卦」两套体系（步长差 0.375°/卦）；爻位顺排与逆排另有按运单双与按上下卦阴阳两说。本产品选用等分圆周 + 显式 yaoOrder 开关，两者都需人工复核。',
  },
  DAGUA_YUN_TABLE: {
    id: 'DAGUA_YUN_TABLE',
    title: '玄空大卦元运年表（阳爻 9 年、阴爻 6 年；一运 1864–1881 … 九运 2017–2043）',
    locus: '未核实到原典刊本卷次；仅核到现代整理文本三处互核（360doc《抽爻换象秘解》《八运风水》年表、罗盘综盘 18-19 层说明）',
    modern: '元运长度由父母卦三爻阴阳相加得出：坤 18、巽离兑各 24、艮坎震各 21、乾 27，合计 180 年',
    url: 'https://www.360doc.cn/article/81818338_1086115693.html',
    lineageNote: '「无五运」的依据是洛书配卦数的 5 居中宫无卦，不是伏羲先天卦序缺位（该序巽为 5）。另有流派把五运单列或寄于四运，元运起止年与本产品不同；两套年表不可互换，本产品表值标 unverified，须人工比对原典后才能确认。',
  },
  TIAN_XING: {
    id: 'TIAN_XING',
    title: '天星择日（七政四余、二十八宿宿度）',
    modern: '宿度取开禧宿度并按用事年岁差校正；星历以 Meeus 算法计算并与 Swiss Ephemeris 逐日比对',
    lineageNote: '开禧宿度与现行度不同，且各派对「宿—山」对应存在差异，必须人工复核。',
  },
  SI_LI_SI_JUE: {
    id: 'SI_LI_SI_JUE',
    title: '四离四绝日',
    modern: '《协纪辨方书》四时否定日条目，节气交接前一日',
  },
  SHOU_SI: {
    id: 'SHOU_SI',
    title: '受死日（官书从删）',
    locus: '《钦定协纪辨方书》四库全书本卷六「要安以下九神」按语',
    modern: '农历月序配日支的固定忌日；通书仍列，官书删驳',
    url: 'https://zh.wikisource.org/zh-hans/%E6%AC%BD%E5%AE%9A%E5%8D%94%E7%B4%80%E8%BE%A8%E6%96%B9%E6%9B%B8_(%E5%9B%9B%E5%BA%AB%E5%85%A8%E6%9B%B8%E6%9C%AC)/%E5%8D%B706',
    lineageNote:
      '卷六按语原文：「若夫龙虎罪至受死三辰并仍旧历从删，夫既以九神为吉则余三不用可知，不必重立名目也。」即官书明言此三辰已从此删；本包因此只作提示，不作硬排除。待核：按语所在的卷六「要安以下九神」一段已逐字核对，受死的月支排布表本身仍待复核（目前仅确认卷六含此按语，其余收录丛辰起例的卷次需逐卷核对）。',
  },
  YANG_GONG_JI: {
    id: 'YANG_GONG_JI',
    title: '杨公十三忌日',
    modern: '相传出自杨筠松，农历固定十三日；通书普遍沿用',
    lineageNote:
      '本包判为「官书未列明文」：在《协纪辨方书》通行本中未检索到「杨公忌日」条目，但该检索未逐卷人工核对，此判断本身待复核（verification_status 仍为 unverified）。因依据只到通书一层，默认硬排除属显式声明的偏离，可由「民俗神煞」开关降为提示。待核：请逐卷核对四库全书本全书（已确认卷六含九神按语，其余收录神煞起例与辨讹的卷次尚待逐卷翻检），确认是否存在「杨公」或「十三忌」的异名条目。',
  },
  CHONG_SANG: {
    id: 'CHONG_SANG',
    title: '重丧日与三丧日',
    modern: '通行通书按农历月序配日干；各地通书口诀略有差异',
    lineageNote:
      '重丧口诀有「正七庚起」与「正月起甲」两系，两系均未核到《协纪》明文卷次，采用哪一系需人工核对所据通书；本包按其中一系起例并标待复核。待核：逐卷核对收录神煞起例与辨讹的卷次（卷次位置尚未确认），并核对本包移植 cnlunar 时所据的丛辰表与现代影印本是否同系。',
  },
  SHI_E_DA_BAI: {
    id: 'SHI_E_DA_BAI',
    title: '十恶大败日（《协纪辨方书》称「无禄」）',
    modern: '日柱十干支表（甲辰、乙巳、丙申、丁亥、戊戌、己丑、庚辰、辛巳、壬申、癸亥）',
    lineageNote: '另有岁煞「大败」（正月起卯逆行四仲，与大时、咸池同组），与十恶大败是两条不同神煞，本产品分别输出、不合并。',
  },
  KAI_XI_DU: {
    id: 'KAI_XI_DU',
    title: '开禧宿度（二十八宿不等宽距度）',
    modern: '宋代《统天历》沿用的二十八宿距度表',
    lineageNote: '宿度随岁差每年西移约 50–52 角秒，本产品按用事年份校正后再判「到山到向」。',
  },
}

export type SourceKey = keyof typeof REGISTRY

/** 运行时可枚举的登记表键，供「规则必须引用已登记出处」的守卫测试使用。 */
export const SOURCE_KEYS: string[] = Object.keys(REGISTRY)

const SOURCE_REGISTRY = createRegistry('规则出处', REGISTRY, '禁止回退到空出处或猜测书名')

export function sourceOf(key: string): SourceRef {
  return SOURCE_REGISTRY.require(key)
}

/** 规则元数据：出处 + 校验状态；verification 只能由人工改。 */
export interface RuleMeta {
  ruleId: string
  name: string
  sourceKey: string
  /** 已完成的可复现机器校验说明（不等同于人工确认） */
  machineCheck?: string
  needsHumanReview?: boolean
}

export function ruleMeta(meta: RuleMeta): {
  ruleId: string
  name: string
  source: SourceRef
  verification: 'unverified'
  needsHumanReview: boolean
} {
  const base = sourceOf(meta.sourceKey)
  return {
    ruleId: meta.ruleId,
    name: meta.name,
    source: {
      ...base,
      modern: meta.machineCheck
        ? `${base.modern ? `${base.modern}；` : ''}${meta.machineCheck}`
        : base.modern,
    },
    verification: 'unverified',
    needsHumanReview: meta.needsHumanReview ?? true,
  }
}
