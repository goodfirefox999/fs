import type { FiveElement, PalaceId } from '../types'

export const LUOSHU_ORDER: PalaceId[] = [5, 6, 7, 8, 9, 1, 2, 3, 4]

export const GRID_ORDER: PalaceId[] = [4, 9, 2, 3, 5, 7, 8, 1, 6]

export interface PalaceMeta {
  id: PalaceId
  trigram: string
  direction: string
  element: FiveElement
  bits: number | null
}

export const PALACES: Record<PalaceId, PalaceMeta> = {
  1: { id: 1, trigram: '坎', direction: '正北', element: '水', bits: 0b010 },
  2: { id: 2, trigram: '坤', direction: '西南', element: '土', bits: 0b000 },
  3: { id: 3, trigram: '震', direction: '正东', element: '木', bits: 0b001 },
  4: { id: 4, trigram: '巽', direction: '东南', element: '木', bits: 0b110 },
  5: { id: 5, trigram: '中', direction: '中宫', element: '土', bits: null },
  6: { id: 6, trigram: '乾', direction: '西北', element: '金', bits: 0b111 },
  7: { id: 7, trigram: '兑', direction: '正西', element: '金', bits: 0b011 },
  8: { id: 8, trigram: '艮', direction: '东北', element: '土', bits: 0b100 },
  9: { id: 9, trigram: '离', direction: '正南', element: '火', bits: 0b101 },
}

export const PALACE_IDS: PalaceId[] = [1, 2, 3, 4, 5, 6, 7, 8, 9]

export interface StarMeta {
  number: number
  name: string
  alias: string
  element: FiveElement
  theme: string
}

export const STARS: Record<number, StarMeta> = {
  1: { number: 1, name: '一白', alias: '贪狼', element: '水', theme: '流动、沟通与思路' },
  2: { number: 2, name: '二黑', alias: '巨门', element: '土', theme: '承载、积累与迟缓' },
  3: { number: 3, name: '三碧', alias: '禄存', element: '木', theme: '生发、行动与摩擦' },
  4: { number: 4, name: '四绿', alias: '文曲', element: '木', theme: '秩序、学习与细节' },
  5: { number: 5, name: '五黄', alias: '廉贞', element: '土', theme: '集中、厚重与静止' },
  6: { number: 6, name: '六白', alias: '武曲', element: '金', theme: '结构、规则与执行' },
  7: { number: 7, name: '七赤', alias: '破军', element: '金', theme: '表达、更新与取舍' },
  8: { number: 8, name: '八白', alias: '左辅', element: '土', theme: '稳固、积累与结果' },
  9: { number: 9, name: '九紫', alias: '右弼', element: '火', theme: '显现、关系与热度' },
}

export interface BaZhaiStarMeta {
  code: string
  name: string
  xor: number
  element: FiveElement
  level: 'GOOD' | 'CAUTION'
  modernLabel: string
  suggestion: string
}

export const BAZHAI_STARS: Record<number, BaZhaiStarMeta> = {
  0b000: {
    code: 'FU_WEI', name: '伏位', xor: 0b000, element: '木', level: 'GOOD',
    modernLabel: '安定位', suggestion: '适合书房、静思角或稳定收纳，布局以少变动为宜。',
  },
  0b001: {
    code: 'HUO_HAI', name: '祸害', xor: 0b001, element: '土', level: 'CAUTION',
    modernLabel: '易扰位', suggestion: '适合储物间、家政柜或次要通道，减少长时间停留。',
  },
  0b010: {
    code: 'JUE_MING', name: '绝命', xor: 0b010, element: '金', level: 'CAUTION',
    modernLabel: '低效位', suggestion: '适合储藏、设备或过渡空间，保持整洁、减少堆物。',
  },
  0b011: {
    code: 'TIAN_YI', name: '天医', xor: 0b011, element: '土', level: 'GOOD',
    modernLabel: '休养位', suggestion: '适合卧室、餐厅或休息区，宜柔和照明与安静布置。',
  },
  0b100: {
    code: 'SHENG_QI', name: '生气', xor: 0b100, element: '木', level: 'GOOD',
    modernLabel: '活力位', suggestion: '适合客厅、书房或主要活动区，宜明亮、通风与绿植。',
  },
  0b101: {
    code: 'LIU_SHA', name: '六煞', xor: 0b101, element: '水', level: 'CAUTION',
    modernLabel: '湿滞位', suggestion: '适合卫生间、洗衣区或水路设备，重点做好防潮与排水。',
  },
  0b110: {
    code: 'WU_GUI', name: '五鬼', xor: 0b110, element: '火', level: 'CAUTION',
    modernLabel: '燥热位', suggestion: '适合厨房、设备间或通风口，注意散热、防火与避免红色堆叠。',
  },
  0b111: {
    code: 'YAN_NIAN', name: '延年', xor: 0b111, element: '金', level: 'GOOD',
    modernLabel: '和睦位', suggestion: '适合客厅、老人房或家庭共用区，宜成对布置与圆角家具。',
  },
}

export const MING_GUA_BITS: Record<number, number> = {
  1: 0b010, 2: 0b000, 3: 0b001, 4: 0b110,
  6: 0b111, 7: 0b011, 8: 0b100, 9: 0b101,
}

export const MING_GUA_INFO: Record<number, { name: string; element: FiveElement; group: 'EAST' | 'WEST' }> = {
  1: { name: '坎', element: '水', group: 'EAST' },
  2: { name: '坤', element: '土', group: 'WEST' },
  3: { name: '震', element: '木', group: 'EAST' },
  4: { name: '巽', element: '木', group: 'EAST' },
  6: { name: '乾', element: '金', group: 'WEST' },
  7: { name: '兑', element: '金', group: 'WEST' },
  8: { name: '艮', element: '土', group: 'WEST' },
  9: { name: '离', element: '火', group: 'EAST' },
}

export const ELEMENT_MATERIAL_ADVICE: Record<FiveElement, string> = {
  木: '可增加木质家具、棉麻织物或绿植，保持通风与适度日照。',
  火: '可增加主照明或暖色局部光源，注意散热与用电安全。',
  土: '可使用陶器、石材或稳定厚重的收纳，保持地面干燥整洁。',
  金: '可增加金属框灯具、钟表或简洁的金属收纳，避免尖锐外露。',
  水: '可设置水景、加湿设备或蓝色软装，重点检查防潮与排水。',
}
