"""伤害计算 & 可视化核心。

从 notebook 搬过来放这里，方便 %autoreload 2 热重载。
Notebook 只需三行：
    import damage_calc as dc
    loadouts = dc.enumerate_loadouts(backpack, EQUIPMENT)
    dc.make_damage_ui(hero_base, loadouts, atk_delta_range, def_delta_range,
                      MONSTERS, monster_name)
"""

from collections import Counter
from itertools import combinations_with_replacement

import numpy as np
from matplotlib.figure import Figure
from IPython.display import display


# ---------------------- 基础公式 ----------------------

def atk_speed_coef(atk_speed):
    """攻速系数 = √max(0, 攻速) / 10。攻速 100 → 1.0；负值视为 0。"""
    return np.sqrt(np.maximum(0, atk_speed)) / 10.0


def armor_passthrough(armor):
    """护甲对应的伤害通过率(1 = 原伤害)。"""
    a = float(armor)
    if a >= 0:
        return 1.0 / (1.0 + 0.06 * a)
    return 1.0 - 0.06 * a


def apply_equipment(base, equipment):
    """累加装备中所有数值字段到基础属性;非数值字段跳过。"""
    eff = dict(base)
    for item in equipment:
        for k, v in item.items():
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            eff[k] = eff.get(k, 0) + v
    return eff


def apply_trait_effects(monster, equipment):
    """按怪物 traits 触发装备 trait_effects,返回调整后的怪物副本。"""
    m = dict(monster)
    traits = set(monster.get('traits', []))
    for item in equipment:
        for trait, effects in item.get('trait_effects', {}).items():
            if trait in traits:
                for k, dv in effects.items():
                    m[k] = m.get(k, 0) + dv
    return m


def crit_multipliers(mon_crit):
    """返回 (首击期望倍率, 后续期望倍率)。"""
    if not mon_crit:
        return 1.0, 1.0
    p = mon_crit['chance']
    mult = mon_crit['multiplier']
    rest = p * mult + (1 - p)
    first = mult if mon_crit.get('first_guaranteed', False) else rest
    return first, rest


def apply_phys_dr(raw_dmg, phys_dr):
    """怪物侧物理减伤。raw_dmg 是每挥 (atk-def),不是每回合伤害。"""
    if not phys_dr:
        return raw_dmg
    return np.maximum(0.0, raw_dmg * phys_dr.get('mult', 1.0) - phys_dr.get('flat', 0))


def apply_map_synergy(mon, undead_cnt):
    """地图亡灵协同:生命 ×(1 + frac·N)。"""
    if '亡灵协同' in mon.get('traits', []) and undead_cnt > 0:
        frac = mon.get('undead_synergy_hp_frac', 1.0)
        mon = dict(mon)
        mon['hp'] = mon['hp'] * (1 + frac * undead_cnt)
    return mon


# ---------------------- 装备组合枚举 ----------------------

def enumerate_loadouts(inv, EQUIPMENT, slots=2):
    """从背包枚举所有可行装备组合(同类可重复,受数量限制)。"""
    names = list(inv.keys())
    out = []
    for combo in combinations_with_replacement(names, slots):
        cnt = Counter(combo)
        if all(cnt[n] <= inv[n] for n in cnt):
            items = [{'name': n, **EQUIPMENT[n]} for n in combo]
            label = '+'.join(combo)
            out.append({'label': label, 'items': items})
    return out


# ---------------------- 主伤害网格 ----------------------

def damage_grid(hero_atk_arr, hero_def_arr,
                hero_as, hero_armor, hero_regen,
                m_atk, m_def, m_hp, m_as, m_armor,
                hero_first=True, first_strike=False,
                hero_dmg_mult=1.0,
                first_hit_hero_deltas=None,
                magic_salvo=None,
                hero_magic_def_flat=0,
                mon_crit=None,
                m_phys_dr=None,
                beast_counter=False,
                poison_flat=0,
                stun_rounds=0):
    """
    返回单次战斗勇士净损血二维矩阵 (len(def_arr), len(atk_arr))。

    字段语义见 notebook 的 intro 单元;主要特性:
      first_hit_hero_deltas  首击后勇士属性修正(寒霜)
      hero_dmg_mult          勇士伤害倍率(闪避)
      magic_salvo            前 N 次"自然攻击槽"为 D 点魔伤,吃 magic_def_flat
      hero_magic_def_flat    魔法 flat 减免(凝魂之泪累加)
      mon_crit               期望展开;与 magic_salvo 叠加时仅作用于 salvo 之后的物理段
      m_phys_dr              怪物物理减伤:per_swing = max(0, (atk-def)·M - F)
      beast_counter          野兽直觉:勇士每回合攻击触发 1 次必中反击(raw, 不吃攻速/暴击)
      poison_flat            腐蚀毒素:每次常规攻击 +N 物伤,无视防御但吃 armor
      stun_rounds            眩晕:多挨 N 次自然攻击,战斗时长 +N(regen 相应累积)

    打不过格子填 np.inf。
    """
    A, D = np.meshgrid(hero_atk_arr, hero_def_arr)

    def hero_hit_at(atk_val, as_val):
        per_swing = apply_phys_dr(np.maximum(0, atk_val - m_def), m_phys_dr)
        return (per_swing
                * atk_speed_coef(as_val)
                * armor_passthrough(m_armor)
                * hero_dmg_mult)

    d1 = hero_hit_at(A, hero_as)
    deltas = first_hit_hero_deltas or {}
    if deltas:
        d_rest = hero_hit_at(A + deltas.get('atk', 0), hero_as + deltas.get('as', 0))
    else:
        d_rest = d1

    mon_hit = np.maximum(0, m_atk - D) * atk_speed_coef(m_as) * armor_passthrough(hero_armor)

    kill_in_1 = d1 >= m_hp
    remaining = np.maximum(0, m_hp - d1)
    safe_rest = np.where(d_rest > 0, d_rest, 1.0)
    turns_cont = 1 + np.ceil(remaining / safe_rest)
    turns = np.where(kill_in_1, 1.0, turns_cont)

    impossible = (~kill_in_1) & (d_rest <= 0)

    natural_n = turns - (1 if hero_first else 0) + (1 if first_strike else 0)
    natural_n_eff = np.maximum(0, natural_n + stun_rounds)
    elapsed_turns = turns + stun_rounds

    crit_first, crit_rest = crit_multipliers(mon_crit)
    poison_eff = poison_flat * armor_passthrough(hero_armor)

    if magic_salvo:
        mag_rounds  = magic_salvo['rounds']
        mag_per_hit = max(0.0, magic_salvo['dmg'] - hero_magic_def_flat)
        mag_hits  = np.minimum(natural_n_eff, mag_rounds)
        phys_hits = np.maximum(0, natural_n_eff - mag_rounds)
        phys_total = phys_hits * (mon_hit * crit_rest + poison_eff)
        natural_total = mag_hits * mag_per_hit + phys_total
    else:
        first_dmg = mon_hit * crit_first + poison_eff
        rest_dmg  = mon_hit * crit_rest  + poison_eff
        natural_total = np.where(natural_n_eff > 0,
                                 first_dmg + np.maximum(0, natural_n_eff - 1) * rest_dmg,
                                 0.0)

    if beast_counter:
        counter_per = np.maximum(0, m_atk - D) * armor_passthrough(hero_armor)
        counter_total = turns * counter_per
    else:
        counter_total = 0.0

    mon_total = natural_total + counter_total
    net = np.floor(mon_total - elapsed_turns * hero_regen)
    return np.where(impossible, np.inf, net)


# ---------------------- 标量版 (文字汇总用) ----------------------

def hit_scalar(hero_atk, hero_as, m_def, m_armor, dmg_mult, phys_dr=None):
    """damage_grid 的标量对应版本,用于文字汇总。"""
    per_swing = float(apply_phys_dr(max(0, hero_atk - m_def), phys_dr))
    return per_swing * atk_speed_coef(hero_as) * armor_passthrough(m_armor) * dmg_mult


# ---------------------- 文本输出 ----------------------

def describe_monster(m):
    extra = []
    if 'hero_dmg_mult' in m:
        extra.append(f"hero_dmg_mult={m['hero_dmg_mult']}")
    if m.get('first_hit_hero_deltas'):
        extra.append(f"first_hit_hero_deltas={m['first_hit_hero_deltas']}")
    if m.get('magic_salvo'):
        extra.append(f"magic_salvo={m['magic_salvo']}")
    if m.get('mon_crit'):
        extra.append(f"mon_crit={m['mon_crit']}")
    if m.get('phys_dr'):
        extra.append(f"phys_dr={m['phys_dr']}")
    if m.get('beast_counter'):
        extra.append("beast_counter=True")
    if m.get('poison_flat'):
        extra.append(f"poison_flat={m['poison_flat']}")
    if m.get('stun_rounds'):
        extra.append(f"stun_rounds={m['stun_rounds']}")
    if m.get('traits'):
        extra.append(f"traits={m['traits']}")
    return (' ' + ' '.join(extra)) if extra else ''


def print_summary(mon, hero_base, loadouts):
    """打印每一套装备方案下的详细损血。"""
    print(f"勇士 base: atk={hero_base['atk']} def={hero_base['def']} "
          f"as={hero_base['as']} armor={hero_base['armor']} regen={hero_base['regen']}")
    print(f"怪物 {mon['name']}: atk={mon['atk']} def={mon['def']} "
          f"hp={mon['hp']} as={mon['as']} armor={mon['armor']}"
          + describe_monster(mon))
    print('-' * 86)

    stun = mon.get('stun_rounds', 0)
    rows = []
    for ld in loadouts:
        m = apply_trait_effects(mon, ld['items'])
        h = apply_equipment(hero_base, ld['items'])
        mult = m.get('hero_dmg_mult', 1.0)
        pdr  = m.get('phys_dr')
        poi  = m.get('poison_flat', 0) * armor_passthrough(h.get('armor', 0))

        d1 = hit_scalar(h['atk'], h['as'], m['def'], m['armor'], mult, pdr)
        deltas = m.get('first_hit_hero_deltas') or {}
        d_rest = (hit_scalar(h['atk'] + deltas.get('atk', 0),
                             h['as']  + deltas.get('as',  0),
                             m['def'], m['armor'], mult, pdr)
                  if deltas else d1)
        mh = max(0, m['atk'] - h['def']) * atk_speed_coef(m['as']) * armor_passthrough(h.get('armor', 0))

        if d1 >= m['hp']:
            turns, natural_n = 1, 0
        elif d_rest > 0:
            turns = 1 + int(np.ceil((m['hp'] - d1) / d_rest))
            natural_n = turns - 1 + (1 if m.get('first_strike', False) else 0)
        else:
            turns, natural_n = None, None

        crit_first, crit_rest = crit_multipliers(m.get('mon_crit'))

        if turns is None:
            net = float('inf')
            mag_hits = phys_hits = mag_per = 0
            counter_per = 0.0; n_counters = 0
            natural_n_eff = None
        else:
            natural_n_eff = max(0, natural_n + stun)
            elapsed = turns + stun
            salvo = m.get('magic_salvo')
            if salvo:
                mag_per   = max(0.0, salvo['dmg'] - h.get('magic_def_flat', 0))
                mag_hits  = min(natural_n_eff, salvo['rounds'])
                phys_hits = max(0, natural_n_eff - salvo['rounds'])
                natural_total = mag_hits * mag_per + phys_hits * (mh * crit_rest + poi)
            else:
                mag_hits = phys_hits = mag_per = 0
                natural_total = ((mh * crit_first + poi)
                                 + max(0, natural_n_eff - 1) * (mh * crit_rest + poi)
                                ) if natural_n_eff > 0 else 0

            if m.get('beast_counter'):
                counter_per = max(0, m['atk'] - h['def']) * armor_passthrough(h.get('armor', 0))
                n_counters = turns
                counter_total = n_counters * counter_per
            else:
                counter_per = 0.0; n_counters = 0; counter_total = 0.0

            net = int(np.floor(natural_total + counter_total - elapsed * h.get('regen', 0)))
        rows.append((ld['label'], h, d1, d_rest, mh, turns, natural_n_eff,
                     mag_hits, phys_hits, mag_per, crit_first, crit_rest,
                     n_counters, counter_per, poi, net))

    rows.sort(key=lambda r: r[-1])
    for (label, h, d1, d_rest, mh, turns, natural_n_eff,
         mag_hits, phys_hits, mag_per, crit_first, crit_rest,
         n_counters, counter_per, poi, net) in rows:
        stat = f"atk={h['atk']:>3} def={h['def']:>3} as={h['as']:>3} armor={h.get('armor',0)} regen={h.get('regen',0)}"
        if net == float('inf'):
            print(f"[{label}] {stat}  =>  d1={d1:>6.3f} d_rest={d_rest:>6.3f}  打不过")
            continue
        hit_info = (f"我击/回={d1:>6.3f}" if abs(d1 - d_rest) < 1e-9
                    else f"首回合={d1:>6.3f}  后续={d_rest:>6.3f}")
        has_crit = not (crit_first == 1.0 and crit_rest == 1.0)
        if mag_hits:
            mon_info = f"魔法x{mag_hits}@{mag_per:.0f}+普攻x{phys_hits}@{mh:>5.2f}"
            if has_crit:
                mon_info += f"(E[x{crit_rest:.2f}])"
        elif has_crit:
            mon_info = f"常攻x{natural_n_eff}@{mh:>5.2f}(首x{crit_first:.2f},后x{crit_rest:.2f}E)"
        else:
            mon_info = f"常攻x{natural_n_eff}@{mh:>6.3f}"
        if poi:
            mon_info += f" +毒x{natural_n_eff}@{poi:.2f}"
        if n_counters:
            mon_info += f" +反击x{n_counters}@{counter_per:.0f}"
        stun_tag = f"+{stun}眩晕" if stun else ""
        print(f"[{label}] {stat}  =>  {hit_info}  {mon_info}  回合={turns:>3}{stun_tag}  净损血={net}")


# ---------------------- 热图 ----------------------

def compute_best_grid(mon, hero_base, loadouts, atk_delta_range, def_delta_range):
    """遍历所有装备方案,对每格取最低净损血。"""
    all_dmg = []
    for ld in loadouts:
        m_adj = apply_trait_effects(mon, ld['items'])
        eq_atk       = sum(it.get('atk',            0) for it in ld['items'])
        eq_def       = sum(it.get('def',            0) for it in ld['items'])
        eq_as        = sum(it.get('as',             0) for it in ld['items'])
        eq_armor     = sum(it.get('armor',          0) for it in ld['items'])
        eq_regen     = sum(it.get('regen',          0) for it in ld['items'])
        eq_magic_def = sum(it.get('magic_def_flat', 0) for it in ld['items'])
        dmg = damage_grid(hero_base['atk'] + atk_delta_range + eq_atk,
                          hero_base['def'] + def_delta_range + eq_def,
                          hero_base['as']    + eq_as,
                          hero_base['armor'] + eq_armor,
                          hero_base['regen'] + eq_regen,
                          m_adj['atk'], m_adj['def'], m_adj['hp'],
                          m_adj['as'], m_adj['armor'],
                          hero_first=True,
                          first_strike=m_adj.get('first_strike', False),
                          hero_dmg_mult=m_adj.get('hero_dmg_mult', 1.0),
                          first_hit_hero_deltas=m_adj.get('first_hit_hero_deltas'),
                          magic_salvo=m_adj.get('magic_salvo'),
                          hero_magic_def_flat=hero_base.get('magic_def_flat', 0) + eq_magic_def,
                          mon_crit=m_adj.get('mon_crit'),
                          m_phys_dr=m_adj.get('phys_dr'),
                          beast_counter=m_adj.get('beast_counter', False),
                          poison_flat=m_adj.get('poison_flat', 0),
                          stun_rounds=m_adj.get('stun_rounds', 0))
        all_dmg.append(dmg)
    return np.min(np.stack(all_dmg, axis=0), axis=0)


def build_heatmap(mon, hero_base, loadouts, atk_delta_range, def_delta_range):
    """构造热图 figure 并返回(不 display)。Streamlit 直接 st.pyplot(fig) 用。"""
    best = compute_best_grid(mon, hero_base, loadouts, atk_delta_range, def_delta_range)
    show = np.where(np.isinf(best), np.nan, best)

    atk_axis = hero_base['atk'] + atk_delta_range
    def_axis = hero_base['def'] + def_delta_range
    base_atk, base_def = hero_base['atk'], hero_base['def']

    fig = Figure(figsize=(18, 5))
    ax0 = fig.add_subplot(1, 3, 1)
    ax1 = fig.add_subplot(1, 3, 2)
    ax2 = fig.add_subplot(1, 3, 3)

    pcm = ax0.pcolormesh(atk_axis, def_axis, show,
                         shading='auto', cmap='RdYlGn_r')
    fig.colorbar(pcm, ax=ax0, label='最低净损血')
    for i, da in enumerate(atk_axis):
        for j, dd in enumerate(def_axis):
            v = show[j, i]
            if np.isfinite(v):
                ax0.text(da, dd, f'{int(v)}', ha='center', va='center', fontsize=9, color='black')
            else:
                ax0.text(da, dd, '×', ha='center', va='center', fontsize=11, color='dimgray')
    ax0.set_xlabel(f"勇士攻击 (base = {base_atk})")
    ax0.set_ylabel(f"勇士防御 (base = {base_def})")
    ax0.set_xticks(atk_axis); ax0.set_yticks(def_axis)
    ax0.set_title(f"{mon['name']}  [atk={mon['atk']} def={mon['def']} hp={mon['hp']} as={mon['as']}]")

    ax1.plot(atk_axis, show[0, :], marker='o', lw=2, color='C0')
    ax1.axvline(base_atk, color='red', ls='--', alpha=0.6, label=f'base={base_atk}')
    ax1.set_xlabel(f"勇士攻击 (base = {base_atk})"); ax1.set_ylabel('最低净损血')
    ax1.set_title(f'固定 def = {base_def}'); ax1.grid(alpha=0.3); ax1.legend()

    ax2.plot(def_axis, show[:, 0], marker='o', lw=2, color='C1')
    ax2.axvline(base_def, color='red', ls='--', alpha=0.6, label=f'base={base_def}')
    ax2.set_xlabel(f"勇士防御 (base = {base_def})"); ax2.set_ylabel('最低净损血')
    ax2.set_title(f'固定 atk = {base_atk}'); ax2.grid(alpha=0.3); ax2.legend()

    fig.tight_layout()
    return fig


def draw_heatmap(mon, hero_base, loadouts, atk_delta_range, def_delta_range):
    """notebook 用:构造 figure 并 display。"""
    fig = build_heatmap(mon, hero_base, loadouts, atk_delta_range, def_delta_range)
    display(fig)


# ---------------------- 交互 UI ----------------------

def make_damage_ui(hero_base, loadouts, atk_delta_range, def_delta_range,
                   MONSTERS, default_monster_name, print_loadouts=False):
    """构造并显示交互 UI,返回 VBox(方便外面 close 掉旧实例)。

    - 怪物下拉
    - 其他亡灵数(仅当怪有亡灵协同 trait 时显示)
    - 打印各装备详情 checkbox(默认取 print_loadouts)
    """
    import ipywidgets as widgets

    dd = widgets.Dropdown(options=list(MONSTERS.keys()),
                          value=default_monster_name, description='怪物')
    undead_dd = widgets.Dropdown(options=list(range(10)), value=0,
                                 description='其他亡灵',
                                 layout=widgets.Layout(display='none'))
    print_cb = widgets.Checkbox(value=bool(print_loadouts),
                                description='打印各装备详情',
                                indent=False)

    def sync_undead(mon_name):
        traits = MONSTERS.get(mon_name, {}).get('traits', [])
        undead_dd.layout.display = '' if '亡灵协同' in traits else 'none'

    dd.observe(lambda change: sync_undead(change['new']), names='value')
    sync_undead(dd.value)

    def render(mon_name, undead_cnt, do_print):
        mon = {'name': mon_name, **MONSTERS[mon_name]}
        mon = apply_map_synergy(mon, undead_cnt)
        if do_print:
            print_summary(mon, hero_base, loadouts)
        draw_heatmap(mon, hero_base, loadouts, atk_delta_range, def_delta_range)

    out = widgets.interactive_output(render, {
        'mon_name':   dd,
        'undead_cnt': undead_dd,
        'do_print':   print_cb,
    })
    ui = widgets.VBox([widgets.HBox([dd, undead_dd, print_cb]), out])
    display(ui)
    return ui
