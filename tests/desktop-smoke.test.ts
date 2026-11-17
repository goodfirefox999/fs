// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

/**
 * 桌面工作台挂载冒烟测试。
 *
 * 存在的理由：`vite build` 不执行组件，模板里引用未定义变量（如曾经漏掉的
 * `degMountain`）能一路通过构建，直到用户打开应用才白屏。
 * 这条测试把「挂载 → 切模块 → 保存档案」整条链路跑一遍。
 */
describe('桌面工作台', () => {
  it('渲染择日工作台、切到档案、保存一份档案', async () => {
    const saved: unknown[][] = []
    window.desktop = {
      platform: 'darwin',
      loadArchives: vi.fn(async () => ({ archives: [] })),
      saveArchives: vi.fn(async (list: unknown[]) => {
        saved.push(list)
        return { ok: true, file: '/tmp/archives.json' }
      }),
      exportArchives: vi.fn(async () => ({ ok: true, file: '/tmp/out.json' })),
      importArchives: vi.fn(async () => ({ ok: false })),
    }

    const App = (await import('@desktop/App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('居境罗盘')
    expect(wrapper.text()).toContain('用事')
    // 左侧面板的「度落某山」依赖 degMountain，漏定义时这里会抛错
    expect(wrapper.text()).toContain('度落')

    const navs = wrapper.findAll('.mod')
    expect(navs.length).toBeGreaterThanOrEqual(4)

    // 排盘：四派必须并列出现，缺数据也要出卡片（标 PARTIAL）
    await navs[1].trigger('click')
    await flushPromises()
    for (const label of ['八宅', '玄空飞星', '流年紫白', '仙命']) {
      expect(wrapper.text(), `排盘页缺少「${label}」卡片`).toContain(label)
    }

    // 罗盘：读数面板与采用按钮
    await navs[2].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('换算结果')
    expect(wrapper.text()).toContain('坐山')

    // 档案
    await navs[3].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('还没有档案')

    const saveBtn = wrapper.findAll('button').find((btn) => btn.text().includes('保存为档案'))
    expect(saveBtn, '档案页应有「保存为档案」按钮').toBeTruthy()
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(saved).toHaveLength(1)
    expect(saved[0]).toHaveLength(1)
    expect(wrapper.text()).toContain('已保存')
    // 保存时一并写入评估快照，列表应展示「上次结论」
    expect(wrapper.text()).toContain('上次结论')
  })
})
