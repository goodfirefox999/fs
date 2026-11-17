/**
 * 排盘：八宅 / 玄空飞星 / 流年紫白 / 仙命，四派并列。
 *
 * 与择日侧 `core/zeri/` 对称：各自出事实与倾向，不合并成单一结论。
 */

export {
  PAIPAN_SCHOOL_IDS,
  PAIPAN_SCHOOL_LABELS,
  type PaipanPersonInput,
  type PaipanReport,
  type PaipanSchoolId,
  type PaipanSchoolResult,
  type PaipanStatus,
  type PaipanSubRule,
} from './types'
export { paipanSourceOf } from './sources'
export { adaptBaZhai, adaptFeiXing, adaptXianMing, adaptXuanKong, starName } from './adapters'
export { buildPaipanReport, type PaipanInput } from './report'
