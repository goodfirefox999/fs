"""二十八宿值日（符号层，纯查表/算术，不含吉凶）。

为什么这一支可以做成「确定」
--------------------------
二十八宿值日是**纯周期算术**：日有 60 干支、宿有 28，二者每 420 日（=60×7）
重合一次，于是旧法分「七元」：一元甲子起虚、二元起奎、三元起毕、四元起鬼、
五元起翼、六元起氐、七元起箕，七元走完复归虚宿。

由此可推出一条**独立的机器自校验**：二十八宿各配七政（日月火水木金土），
而七政与星期的对应是固定的（日=周日、月=周一、火=周二、水=周三、木=周四、
金=周五、土=周六）。任何正确的值宿表都必须满足「宿的七政 == 当日星期」，
且该恒等式在整个 1900-2100 区间成立 —— 表错一位即以天文数量级的违例暴露。
本模块把这条恒等式做成 ``weekday_consistent``，并在测试里逐日验证（见
``tests/unit/test_xiu.py``）。

锚点
----
``1996-01-28``：甲子日、星期日、虚宿值日（一元甲子起虚）。三项同时成立，
故它既是七元的起点，也是可被星期恒等式约束的锚点。锚点选择不影响结论——
任一满足「甲子日 + 虚宿 + 七政相符」的日期都会给出同一张表（差 420 日即重合）。

不职责
------
本模块只回答「某日值何宿、该宿属何七政/五行/禽名」。**不说吉凶**——
「角宿吉、亢宿凶」是《玉匣记》一系的断言，属规则层（见 ``PUB-XIU-*``）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

__all__ = [
    "XIU_ORDER",
    "XIU_TABLE",
    "XIU_ANCHOR",
    "QI_ZHENG",
    "WEEKDAY_QIZHENG",
    "XiuInfo",
    "xiu_index_of_date",
    "xiu_of_date",
    "qizheng_of_date",
    "yuan_of_date",
    "weekday_consistent",
    "xiu_cycle_offset",
]

#: 二十八宿次序（角起，轸终）。次序本身是定义，不含吉凶。
XIU_ORDER: tuple[str, ...] = (
    "角", "亢", "氐", "房", "心", "尾", "箕",
    "斗", "牛", "女", "虚", "危", "室", "壁",
    "奎", "娄", "胃", "昴", "毕", "觜", "参",
    "井", "鬼", "柳", "星", "张", "翼", "轸",
)

#: 七政次序：与 ``宿序 % 7`` 对应（角木、亢金、氐土、房日、心月、尾火、箕水…）
QI_ZHENG: tuple[str, ...] = ("木", "金", "土", "日", "月", "火", "水")

#: 星期（Python ``weekday()``：周一=0 … 周日=6）→ 七政
WEEKDAY_QIZHENG: dict[int, str] = {
    0: "月", 1: "火", 2: "水", 3: "木", 4: "金", 5: "土", 6: "日",
}


@dataclass(frozen=True)
class XiuInfo:
    """一宿的静态属性（名称性信息，不含吉凶）。

    ``qizheng`` 同时充当通行全称里的「行」字（角**木**蛟、房**日**兔、毕**月**乌），
    因此不再单列 ``wuxing`` 字段 —— 两个字段恒等，多一个就多一处漂移面。
    """

    index: int
    name: str
    qizheng: str
    bird: str

    @property
    def full_name(self) -> str:
        """通行全称，如「角木蛟」「昴日鸡」。"""
        return f"{self.name}{self.qizheng}{self.bird}"


#: 二十八宿属性表：(宿名, 禽名)。五行与七政由位置推出，不另立表以免漂移。
#: 禽名为传统命名（角木蛟、亢金龙…），属名称而非吉凶判断。
_XIU_BIRDS: tuple[tuple[str, str], ...] = (
    ("角", "蛟"), ("亢", "龙"), ("氐", "貉"), ("房", "兔"), ("心", "狐"), ("尾", "虎"), ("箕", "豹"),
    ("斗", "獬"), ("牛", "牛"), ("女", "蝠"), ("虚", "鼠"), ("危", "燕"), ("室", "猪"), ("壁", "貐"),
    ("奎", "狼"), ("娄", "狗"), ("胃", "雉"), ("昴", "鸡"), ("毕", "乌"), ("觜", "猴"), ("参", "猿"),
    ("井", "犴"), ("鬼", "羊"), ("柳", "獐"), ("星", "马"), ("张", "鹿"), ("翼", "蛇"), ("轸", "蚓"),
)

XIU_TABLE: tuple[XiuInfo, ...] = tuple(
    XiuInfo(index=i, name=name, qizheng=QI_ZHENG[i % 7], bird=bird)
    for i, (name, bird) in enumerate(_XIU_BIRDS)
)

#: 七元锚点：1996-01-28 甲子日 · 星期日 · 虚宿值日（一元甲子起虚）
XIU_ANCHOR: date = date(1996, 1, 28)
#: 锚点日的宿序（虚 = 10）
_ANCHOR_INDEX: int = XIU_ORDER.index("虚")


def xiu_cycle_offset(d: date) -> int:
    """``d`` 距锚点的天数（可为负）。"""
    return (d - XIU_ANCHOR).days


def xiu_index_of_date(d: date) -> int:
    """``d`` 的值日宿序（0=角 … 27=轸）。"""
    return (_ANCHOR_INDEX + xiu_cycle_offset(d)) % 28


def xiu_of_date(d: date) -> XiuInfo:
    """``d`` 的值日宿。"""
    return XIU_TABLE[xiu_index_of_date(d)]


def qizheng_of_date(d: date) -> str:
    """``d`` 值宿所属七政（应为当日星期对应的七政）。"""
    return QI_ZHENG[xiu_index_of_date(d) % 7]


def yuan_of_date(d: date) -> int:
    """``d`` 所在「元」（1..7）。一元 = 60 日，七元 = 420 日。"""
    return (xiu_cycle_offset(d) // 60) % 7 + 1


def weekday_consistent(d: date) -> bool:
    """星期恒等式：值宿七政 == 当日星期对应七政。

    这是本模块唯一的自校验：表若错位一位，本函数在绝大多数日期返回 False。
    """
    return qizheng_of_date(d) == WEEKDAY_QIZHENG[d.weekday()]
