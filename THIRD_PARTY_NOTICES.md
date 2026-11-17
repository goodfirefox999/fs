# 第三方开源组件与许可声明

本文件记录本项目直接依赖或作为校验基准的开源组件。原则：只使用宽松许可（MIT/BSD/CC0）的代码与数据；
AGPL 项目（如 Horosa）与无许可证仓库（如 suangua、YiSphere、compass-web、luopan、殆知阁仓库整体）不复制其代码或文本，
仅参考公开文档中的概念与术语。

## 随客户端打包

| 组件 | 版本 | 许可 | 用途 | 作者/版权 |
| --- | --- | --- | --- | --- |
| lunar-javascript | 1.7.7 | MIT | 干支、节气、农历、建除十二值、二十八宿、彭祖百忌、黄黑道、吉神宜趋/凶煞宜忌、神煞方位 | Copyright (c) 6tail |

MIT 许可证原文见 <https://opensource.org/license/mit>。上述组件的版权声明与许可证副本随发行包保留在本文件中。

## 仅用于开发期校验（不随客户端发布）

| 来源 | 许可 | 校验内容 |
| --- | --- | --- |
| cnlunar（OPN48） | MIT | 《钦定协纪辨方书》起例移植：2020–2035 年共 5844 天逐日比对 42 项神煞与建除值，结果一致；受死、大败两项在随包夹具（2026–2027 年 730 天）中逐日比对，见 `tests/xieji-oracle.test.ts`。差异仅在年界口径（cnlunar 以正月初一换年，本项目以立春换年），故岁德、岁德合在 1–2 月存在预期差异。 |
| Know-your-fate `fengshui-kanyu/scripts/_common.py`（tf1993614） | MIT | 玄空飞星下卦排盘：9 运 × 24 山共 216 局的运盘、山盘、向盘与格局判定，结果与本项目引擎逐宫一致（`tests/xuankong-oracle.test.ts`）。八宅游年八方与 1901–2099 年男女命卦同样逐条一致（`tests/bazhai-oracle.test.ts`）。 |
| Swiss Ephemeris（pyswisseph） | 公开软件，商用需按其条款确认 | 太阳视黄经与均时差的精度校验：2026 年逐日比对，最大黄经误差 0.014°。该结果未达规格要求的 0.01°，因此天星包固定输出 `PARTIAL` 并公布误差界。星历数值不写入客户端。 |

上述三个仓库均为 MIT 许可的独立实现，本项目只在其运行时输出上做对照，不复制其源码；
`tests/fixtures/*.json` 中保存的是事实性数值（排盘结果与神煞命中集合），并在文件头注明来源与许可。

## 概念与术语参考（未复制代码或文本）

传统择日与堪舆术语、典籍名称来自公开领域的古籍（《钦定协纪辨方书》《葬书》《宅经》《青囊奥语》《董公选择要义》《九天上圣秘传金符经》等）
以及公开网络资料。以下仓库因许可原因未使用其代码：

- Horace-Maxwell/Horosa：AGPL-3.0（整体避免引入）。
- Sudo-Biao/suangua、voidforall/fengshui.skill、0xfnzero/YiSphere、freekingg/compass-web、masterflywolf/luopan、
  garychowcmu/daizhigev20、lhw828/GuWen、ShousenZHANG/chinese-fortune：仓库未标注许可证，仅参考公开描述。

## 数据口径备注

- 本项目以立春为年界、以交节当日为月界；与以正月初一换年的通书在 1–2 月的年家神煞上会有差异，界面与文档已注明。
- 所有规则的 `verification_status` 初始为 `unverified`，须由人工逐条核对古籍原文后才能改为 `verified_by_human`。
