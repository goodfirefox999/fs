<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app'
import { callCloudFunction, initCloud } from '@/services/cloud'
import { useArchiveStore } from '@/stores/archive'

onLaunch(() => {
  // 先把旧版本档案迁移并回写，再初始化云能力（纯本地操作，不依赖网络）。
  // 有迁移失败项时 hydrate() 内部会跳过回写，避免用可读子集覆盖用户原始档案。
  useArchiveStore().hydrate()
  initCloud()
  // #ifdef MP-WEIXIN
  void callCloudFunction('login').catch(() => {
    // 登录态失败不阻断本地功能
  })
  // #endif
})
</script>
