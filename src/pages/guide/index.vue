<script setup lang="ts">
import { useAppStore } from '@/stores/app'
import { useArchiveStore } from '@/stores/archive'

const appStore = useAppStore()
const archiveStore = useArchiveStore()

const sections = [
  {
    title: '这是什么工具',
    body: [
      '居境罗盘是一份传统人居环境与方位信息的记录工具。它把罗盘读数、年份、空间类型与人员信息整理成结构化档案，并按三元九宫、八宅、分金与择日等传统规则给出可回看的整理结果。',
      '它不提供结果承诺，也不替代医疗、投资、法律、结构、地质、消防或施工安全评估。所有内容仅作文化与环境安排参考。',
    ],
  },
  {
    title: '档案里记录什么',
    body: [
      '阳宅档案：房屋坐向、入宅或建档年份、空间类型、居住者出生信息，以及由此生成的九宫、八宅分区与择日候选。',
      '纪念地档案：坐向、分金线度、纪念位类型、仙命出生信息、家属信息与周边地形记录，以及由此生成的仙命比对与择日候选。',
      '所有档案默认保存在本机。删除小程序或清理缓存前，请自行留存重要信息。',
    ],
  },
  {
    title: '罗盘读数如何工作',
    body: [
      '小程序优先使用手机方向传感器采样，取最近 20 个读数的圆均值，并以集中度衡量稳定性。稳定性达到 92% 后可保存。',
      '传感器受金属门窗、磁铁、电子设备与握持姿势影响。任何涉及立向、施工或纪念地的事项，都应到现场用实体罗盘复核。',
      '也可以直接输入度数或选择山中线。磁北与真北是两种读数口径，本工具只记录所选口径与参考磁偏角，不自动换算。',
    ],
  },
  {
    title: '纪念地档案的口径',
    body: [
      '纪念地部分按“先人纪念地环境建档”处理，使用中性的地理与环境记录语言。它只覆盖可以自动核验的传统规则：年干支纳音、坐山正五行、分金纳音、三煞、冲山与冲兼等。分金的吉凶分类口径尚未完成三源核验，本工具不输出此类结论。',
      '丧坑、丧窟、刺穴、地虎食骨等分金细则流派差异较大，本工具不自动下结论，需要专业罗盘师结合现场判断。',
      '纪念地的用地性质、审批、产权、界址、排水与边坡安全，不属于本工具的判断范围，请咨询相应主管部门与专业人士。',
    ],
  },
  {
    title: '排盘与兼向的口径',
    body: [
      '九宫排盘沿用三元九宫挨星法：运星入中顺飞，山星与向星取坐山、向首所临运星，按元旦盘同元龙之阴阳定顺逆。',
      '每山 15° 中，正中 9° 为正向，两侧各 3° 为兼向。兼向时按传统起例区分：同卦宫且阴阳相同不作替（如子兼癸），阴阳互兼与跨卦宫（出卦）用替卦起星。',
      '五黄入中按本山元龙定顺逆；若您的流派采用寄坤寄艮，可在设置中切换。出卦线度会单独提示，建议重新立极定向。',
    ],
  },
  {
    title: '择日参考的口径',
    body: [
      '择日按用途匹配宜项，并排除宜忌冲突、日支冲家属与仙命、冲坐山、岁破、月破、四离四绝；杨公忌按通书口径默认排除、可切为提示。三煞按年／月／日／时占山与日课相犯分层，默认在兴工与阴宅用事中硬排年家、月家占山，其余按提示处理；重丧日按提示或排除设置处理。',
      '另按《钦定协纪辨方书》起例补充神煞与宜忌等第：先判每日吉神凶煞并见情况，得出「从宜不从忌／从宜亦从忌／从忌不从宜／诸事皆忌」四档，判为诸事皆忌的日子不再列为候选。',
      '月支与太岁按交节当日、立春当日切换，与通书一致；当日细则中还列出吉神宜趋、凶煞宜忌、二十八宿、值神、吉时与吉神方位，均按同一口径计算。',
      '结果只列出条件更匹配的候选日，「条件分」统计的是规则命中数量，不代表优劣结论，也不承诺结果。施工、安葬、迁居等事项仍需结合气象、安全、审批与家庭协商自行决定。',
      '十二地支山可直接套用日支冲山规则；四维山（乾、坤、艮、巽）与八天干山不做直接冲山判断，建议用实体罗盘复核兼向。',
    ],
  },
  {
    title: '五派并列与规则出处',
    body: [
      '择日先经一层“大煞”前置排除。不可放宽项只收历法事实与官书明文两类：岁破、月破、日破、时破、冲坐山、冲主命与仙命、四离四绝，以及《协纪辨方书》等第判为“诸事皆忌”的日子；兴工与阴宅用事下的年家三煞占山同属不可放宽。三煞拆成“占山四条”（看坐山是否落煞方）与“日课相犯两条”（日支犯年煞、时支犯日煞，看四柱自身），后者不构成对坐山的排除；四家占山各自的煞方都由该柱自身地支的三合局起。金神七煞（限修造与入宅）与四废、往亡、十恶大败、大败、杨公忌、重丧按所选口径排除或提示——杨公忌属通书沿用、官书未列明文，默认排除是显式声明的偏离；受死因《协纪辨方书》卷六明文“并仍旧历从删”，恒列为提示，任何设置都不会把它升成排除。命中不可放宽项即不进入流派评分，任何流派的吉星都不改写这一层结果。',
      '通过前置层后，正五行、三合、董公、玄空大卦、天星五套规则各自独立判定并并列展示：正五行讲补龙扶山相主与调候通关，三合讲三合六合与禄马贵人到山到向，董公讲十二建星与九星值日，玄空大卦按阳爻九年、阴爻六年的卦运与抽爻换象，天星按太阳视黄经入宿度。不同流派的结论不合并为单一吉凶；出现相反判定时，界面同时列出双方依据与出处。',
      '传统出处：《钦定协纪辨方书》（清乾隆敕撰）为神煞起例与宜忌等第主源，《董公选择要义》《九天上圣秘传金符经》为董公九星与金神七煞主源，《天元五歌》《地理辨证》一系为玄空大卦主源，开禧宿度与《星学大成》一系为天星主源；干支、节气、二十八宿值日等历法事实由开源库 lunar-javascript（MIT）计算。',
      '需要如实说明的边界：官修《协纪辨方书》卷六明文删驳“受死、龙虎、罪至”三煞，对金神亦按语存疑，本产品仍按民间通书口径列出并标注待人工复核；正五行与洪范（斗首）五行对同一山的归属不同，两派不混用；六十四卦配罗盘有“等分圆周”与“分金配卦”两套体系；董公九星值日随月组轮转，不存在脱离月份的固定六十甲子表。',
      '天星部分仅计算太阳，算法与 Swiss Ephemeris 逐日比对的实测误差为 0.014°，未达本项目自设的 0.01° 精度门槛，因此天星流派固定标注为“部分计算”，太阴、五星与四余不给出结论；度数落在宿界 0.03° 以内时会提示复核。',
      '所有规则的核对状态初始均为“未人工确认”，需要人工逐条比对古籍原文后才能改为已确认；开源组件许可与校验方式见项目内 THIRD_PARTY_NOTICES.md。',
    ],
  },
  {
    title: '数据与隐私',
    body: [
      '档案、设置与权益缓存保存在本机存储中。内容包与已购权益通过微信小程序云端读取；支付由微信支付完成。',
      '本工具不会主动上传通讯录、照片或精确位置。只有在您主动点击“按当前位置推荐城市”时，才会请求一次定位权限，用于匹配参考磁偏角。',
      '您可以在“我的”页面清空本机档案或全部本地数据。清空后，云端购买记录仍会保留，但本机档案删除后无法在应用内自动恢复，请谨慎操作。',
    ],
  },
  {
    title: '付费说明',
    body: [
      '基础建档、罗盘定向、九宫预览与择日筛选可免费使用。每份档案的完整九宫分析按份解锁，一次购买对应一份档案，不自动续费。',
      '虚拟内容一经解锁即完成交付。若遇到支付成功但未解锁、重复扣款或内容加载异常，请通过小程序客服反馈，并附上档案名称与支付时间。',
    ],
  },
]

function goCompass() {
  uni.navigateTo({ url: '/pages/compass/index?mode=YANG' })
}

function goArchive() {
  uni.switchTab({ url: '/pages/archive/index' })
}
</script>

<template>
  <view class="page">
    <view class="shell">
      <view class="page-head">
        <text class="eyebrow">GUIDE & BOUNDARIES</text>
        <text class="head-title serif">使用说明与边界</text>
        <text class="head-sub">先读口径，再开始记录。</text>
      </view>

      <view class="card intro">
        <text class="intro-title serif">记录优先，判断其次。</text>
        <text class="intro-text">
          这份工具把“看到了什么、量到了什么、录入了什么”保存下来，再按明确的传统规则整理。它不替您做决定，也不承诺任何结果。
        </text>
        <view class="row intro-actions">
          <button class="btn btn-primary btn-sm" @click="goCompass">去罗盘定向</button>
          <button class="btn btn-ghost btn-sm" @click="goArchive">查看档案</button>
        </view>
      </view>

      <view v-for="(section, index) in sections" :key="section.title" class="card section">
        <view class="section-head">
          <text class="section-index serif">{{ String(index + 1).padStart(2, '0') }}</text>
          <text class="section-title serif">{{ section.title }}</text>
        </view>
        <text v-for="(paragraph, pIndex) in section.body" :key="pIndex" class="section-text">
          {{ paragraph }}
        </text>
      </view>

      <view class="card boundary">
        <text class="boundary-title serif">明确不做什么</text>
        <text class="boundary-text">· 不提供医疗、心理、投资、法律或婚姻决策建议。</text>
        <text class="boundary-text">· 不判断房屋结构安全、地质灾害、消防隐患或工程质量。</text>
        <text class="boundary-text">· 不替代纪念地用地的审批、产权、界址与施工许可。</text>
        <text class="boundary-text">· 不对任何日期、坐向或空间安排作出结果承诺。</text>
      </view>

      <view class="version">
        <text>居境罗盘 · 传统人居环境方位参考工具</text>
        <text>本机档案 {{ archiveStore.archives.length }} 份 · 内容包 {{ appStore.content?.version || '待加载' }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page-head {
  padding: 30rpx 4rpx 26rpx;
  border-bottom: 1rpx solid var(--line-gold);
}
.head-title {
  display: block;
  margin-top: 6rpx;
  color: var(--ink);
  font-size: 42rpx;
  letter-spacing: 0.06em;
}
.head-sub {
  display: block;
  margin-top: 8rpx;
  color: var(--ink-3);
  font-size: 22rpx;
  line-height: 1.7;
  letter-spacing: 0.04em;
}
.intro {
  padding: 34rpx 30rpx 30rpx;
  border: 1rpx solid var(--line-gold);
  border-top: 5rpx solid var(--accent);
  background: linear-gradient(150deg, var(--surface) 0%, var(--surface-warm) 100%);
  box-shadow: var(--shadow-card);
}
.intro-title {
  display: block;
  color: var(--accent-deep);
  font-size: 36rpx;
  line-height: 1.45;
  letter-spacing: 0.06em;
}
.intro-text {
  display: block;
  margin-top: 16rpx;
  color: var(--ink-2);
  font-size: 23rpx;
  line-height: 1.95;
  text-align: justify;
}
.intro-actions {
  margin-top: 24rpx;
  padding-top: 22rpx;
  border-top: 1rpx solid var(--line-gold);
}
.intro-actions .btn {
  flex: 1;
}
.section {
  margin-top: 20rpx;
  padding: 28rpx 28rpx 30rpx;
  border: 1rpx solid var(--line);
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.section-head {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 20rpx;
  padding-bottom: 18rpx;
  border-bottom: 1rpx solid var(--line-gold);
}
.section-index {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 52rpx;
  height: 52rpx;
  border: 1rpx solid var(--accent);
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent-deep);
  font-size: 20rpx;
  line-height: 1;
  letter-spacing: 0.04em;
}
.section-title {
  flex: 1;
  color: var(--ink);
  font-size: 30rpx;
  line-height: 1.5;
  letter-spacing: 0.04em;
}
.section-text {
  display: block;
  margin-top: 14rpx;
  color: var(--ink-2);
  font-size: 23rpx;
  line-height: 1.95;
  text-align: justify;
}
.boundary {
  margin-top: 24rpx;
  padding: 28rpx 28rpx 30rpx;
  border: 1rpx solid var(--line);
  border-left: 6rpx solid var(--accent);
  background: var(--danger-soft);
  box-shadow: var(--shadow-card);
}
.boundary-title {
  display: block;
  margin-bottom: 16rpx;
  padding-bottom: 14rpx;
  border-bottom: 1rpx solid var(--line-gold);
  color: var(--accent-deep);
  font-size: 29rpx;
  letter-spacing: 0.06em;
}
.boundary-text {
  display: block;
  margin-top: 10rpx;
  color: var(--ink-2);
  font-size: 22rpx;
  line-height: 1.85;
}
.version {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  margin-top: 38rpx;
  padding: 24rpx 0;
  border-top: 1rpx solid var(--line);
  color: var(--muted);
  font-size: 20rpx;
  line-height: 1.7;
  text-align: center;
}
</style>
