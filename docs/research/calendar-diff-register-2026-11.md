# C20 历算差异登记表（首版，2026-11-01）

> 定位：分歧登记，非门禁。规范依据：GB/T 33661-2017《农历的编算和颁行》（2017-05-12 发布，紫金山天文台起草）+ 紫金山天文台《中国天文年历》。
> oracle：lunar_python 1.4.8 / sxtwl 2.0.7（dev-only，tools/requirements-dev-oracle.txt）。

## 一、节气时刻（2026–2027 × 24 节气，zeri vs lunar_python）

- 样本 48 条，>60s 分歧 0 条，最大秒差 9s
- 2026 冬至: lunar_python 无此条（键名映射待核）
- 2027 冬至: lunar_python 无此条（键名映射待核）

## 二、干支纪日（2024–2027 × 每月 1/11/21 日 = 144 样本，zeri vs lunar_python vs sxtwl）

- 样本 144 条，分歧 0 条

## 三、闰月（2017–2027，zeri vs lunar_python；0=无闰）

- 样本 11 年，分歧 0 条（2020 闰四月、2023 闰二月为已知锚点）

## 四、sxtwl 节气接入状态

- sxtwl 2.0.7 节气接口为逐日扫描 + 儒略日（UT），与本登记表的北京时间口径需换算；
- 首版登记表未纳入其节气列（换算实现见 tools/calendar_diff_register.py 的 sxtwl_terms，
  精度口径待与 GB/T 33661 对齐后升级）——如实登记为「接入中」。
