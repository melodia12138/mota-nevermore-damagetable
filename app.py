"""Streamlit 演示:魔塔《永不复还 500F》怪物伤害表。

部署:推到 GitHub → streamlit.io/cloud 选仓库和入口 app.py。
本地预览:streamlit run app.py
"""

import contextlib
import io

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

import damage_calc as dc
from equipment import EQUIPMENT
from monsters import MONSTERS

# 中文字体:Streamlit Cloud 会通过 packages.txt 装 fonts-noto-cjk
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'Microsoft YaHei',
                                   'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

st.set_page_config(page_title='永不复还 500F · 怪物伤害表', layout='wide')
st.title('魔塔《永不复还 500F》怪物伤害表')

# ---------------- 侧栏:勇士属性 / 背包 / 怪物 ----------------
with st.sidebar:
    st.header('勇士基础属性')
    c1, c2 = st.columns(2)
    hero_atk    = c1.number_input('atk',   value=28, step=1)
    hero_def    = c2.number_input('def',   value=27, step=1)
    hero_as     = c1.number_input('as',    value=100, step=5)
    hero_armor  = c2.number_input('armor', value=0,  step=1)
    hero_regen  = c1.number_input('regen', value=0,  step=1)
    hero_base = {'atk': hero_atk, 'def': hero_def, 'as': hero_as,
                 'armor': hero_armor, 'regen': hero_regen}

    st.header('背包')
    BACKPACK_DEFAULTS = {
        '劣质皮甲': 1,
        '佣兵短剑': 2,
        '骷髅盾':   2,
        '轻骑护手': 1,
        '加速手套': 2,
        '凝魂之泪': 2,
    }
    backpack = {}
    for name in EQUIPMENT:
        default = BACKPACK_DEFAULTS.get(name, 0)
        n = st.number_input(name, min_value=0, max_value=4, value=default, step=1, key=f'bp_{name}')
        if n:
            backpack[name] = n
    SLOTS = st.number_input('装备槽数', min_value=1, max_value=4, value=2, step=1)

    st.header('扫描范围')
    atk_max = st.number_input('Δatk 最大', min_value=1, max_value=15, value=5)
    def_max = st.number_input('Δdef 最大', min_value=1, max_value=15, value=5)
    atk_delta_range = np.arange(0, atk_max + 1)
    def_delta_range = np.arange(0, def_max + 1)

# ---------------- 主栏:怪物选择 + 输出 ----------------
mon_name = st.selectbox('怪物', list(MONSTERS.keys()))
mon_template = MONSTERS[mon_name]

cols = st.columns([1, 1, 2])
show_detail = cols[0].checkbox('打印各装备详情', value=False)
undead_cnt = (cols[1].number_input('其他亡灵协同怪数', 0, 9, 0)
              if '亡灵协同' in mon_template.get('traits', [])
              else 0)

if not backpack:
    st.warning('背包为空,请在侧栏添加至少一件装备。')
    st.stop()

loadouts = dc.enumerate_loadouts(backpack, EQUIPMENT, slots=int(SLOTS))
st.caption(f"共 {len(loadouts)} 套装备方案: " + '、'.join(l['label'] for l in loadouts))

mon = dc.apply_map_synergy({'name': mon_name, **mon_template}, undead_cnt)

# 文字汇总(可选)
if show_detail:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        dc.print_summary(mon, hero_base, loadouts)
    st.code(buf.getvalue(), language='text')

# 热图
fig = dc.build_heatmap(mon, hero_base, loadouts, atk_delta_range, def_delta_range)
st.pyplot(fig)
