"""怪物属性表。

字段：
    atk / def / hp / as / armor       基本属性
    first_strike                       先攻（默认 False）
    hero_dmg_mult                      勇士对怪造成伤害的倍率（默认 1.0；闪避等）
    traits                             字符串列表，装备 trait_effects 依此触发

后续如有连击 / 吸血 / 魔攻 / 坚固，按需追加字段与 damage_grid 逻辑。
"""

MONSTERS = {
    # '荷依米':     {'atk':  3, 'def':  0, 'hp':  32, 'as':  80, 'armor': 0},
    # '倍荷玛战士': {'atk': 11, 'def':  3, 'hp':  80, 'as':  90, 'armor': 0},
    '倍荷玛拉战士': {'atk': 28, 'def':  15, 'hp':  288, 'as':  90, 'armor': 0},
    '大哥布林':    {'atk': 26, 'def':  12, 'hp':  245, 'as':  110, 'armor': 0},
    '恶魔种子':    {'atk':  29, 'def':  17, 'hp':  275, 'as':  60, 'armor': 0},
    '青蓝幼蝠':     {'atk': 35, 'def': 8, 'hp': 138, 'as': 140, 'armor': 0,
                   'hero_dmg_mult': 0.65},   # 闪避 35%
    '青蓝蝠':     {'atk': 40, 'def': 23, 'hp': 232, 'as': 160, 'armor': 0,
                   'hero_dmg_mult': 0.7},   # 闪避 30%
    '灵魂之火':   {'atk': 45, 'def': 15, 'hp': 107, 'as':  82, 'armor': 0,
                   'first_hit_hero_deltas': {'as': -160}},   # 寒霜攻击
    '爆炎流浪法师': {'atk': 33, 'def': 14, 'hp': 310, 'as': 100, 'armor': 0,
                   'magic_salvo': {'rounds': 7, 'dmg': 60}},
    '废弃夜魇法兵': {'atk': 42, 'def': 24, 'hp': 373, 'as': 100, 'armor': 0,
                   'magic_salvo': {'rounds': 3, 'dmg': 120}},   # 奥术飞弹：前 3 回合不普攻，改为 120 魔法伤害
    '守墓者':     {'atk': 40, 'def': 20, 'hp': 187, 'as': 110, 'armor': 0,
                   'traits': ['亡灵协同'],
                   'undead_synergy_hp_frac': 0.1},   # 亡灵协同 +10%/只
    '守墓将军':    {'atk': 50, 'def': 25, 'hp': 270, 'as': 135, 'armor': 0,
                   'traits': ['亡灵协同']},   # 亡灵协同：地图上每多一只其它亡灵协同怪 → 生命 +100%（默认系数）
    '隐墓剑':     {'atk': 52, 'def': 16, 'hp': 210, 'as': 240, 'armor': 0,
                   'traits': ['亡灵协同'],
                   'undead_synergy_hp_frac': 0.1,   # 亡灵协同 +10%/只
                   'mon_crit': {'chance': 0.2, 'multiplier': 2.5, 'first_guaranteed': True}},
                   # 致命一击：20% 概率 ×2.5，首击必暴。按期望计算：E[后续]=1.3
    '废弃夜魇战兵': {'atk': 45, 'def':  27, 'hp':  268, 'as':  150, 'armor': 0},
    '废弃夜魇甲兵': {'atk': 40, 'def':  28, 'hp':  550, 'as':   90, 'armor': 0,
                   'phys_dr': {'mult': 0.75, 'flat': 3}},   # 皮肤硬化：物伤先 ×0.75，再 -3
    # '墓穴亡影':     {'atk': 63, 'def': 24, 'hp': 375, 'as': 150, 'armor': 0,
    #                'traits': ['亡灵协同'], 'undead_synergy_hp_frac': 0.18,
    #                 'hero_dmg_mult': 0.5},
    # '嗜血守墓者':   {'atk': 68, 'def': 38, 'hp': 296, 'as': 150, 'armor': 0,
    #                'traits': ['亡灵协同'],
    #                'undead_synergy_hp_frac': 0.24},
    # '狂怒野兽':     {'atk': 51, 'def': 36, 'hp': 538, 'as':  95, 'armor': 0,
    #                'beast_counter': True,   # 野兽直觉：勇士每次攻击触发 1 次反击，必中
    #                'mon_crit': {'chance': 0.15, 'multiplier': 2.0, 'first_guaranteed': True}},
    #                # 致命一击：15% ×2，首击必暴。E[后续]=1.15
    # '封尘古蝠':     {'atk': 90, 'def': 10, 'hp': 520, 'as': 150, 'armor': 0,
    #                'hero_dmg_mult': 0.7,   # 闪避 30%
    #                'poison_flat': 5},        # 腐蚀毒素：每次攻击额外 +5 无视防御物伤
    # '恶魔之芽':    {'atk':  77, 'def':  43, 'hp':  299, 'as':  60, 'armor': 0},
    # '封尘法师':    {'atk': 69, 'def': 29, 'hp': 452, 'as': 100, 'armor': 0,
    #                'magic_salvo': {'rounds': 1, 'dmg': 275},   # 次级沟壑:1 次 275 魔伤
    #                'stun_rounds': 2},                            # 眩晕 2 回合(勇士多挨 2 次攻击)
    # '狂怒兽战士':     {'atk': 70, 'def': 55, 'hp': 768, 'as':  115, 'armor': 0,
    #                'beast_counter': True,   # 野兽直觉：勇士每次攻击触发 1 次反击，必中
    #                'mon_crit': {'chance': 0.15, 'multiplier': 3.0, 'first_guaranteed': True}},
}
