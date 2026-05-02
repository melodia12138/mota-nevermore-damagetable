"""装备属性表。

数值字段会被 apply_equipment 累加到 hero_base：
    atk / def / armor / regen    直接 +
    as                           攻速（100 = 100%，+15 表示 +15%）
    magic_def_flat               单次魔法伤害减免（普攻不触发，当前未建模）

其他字段：
    short                        heatmap/summary 里用的短标签
    trait_effects                {'怪物 trait': {'怪物字段': delta}}，条件触发
"""

EQUIPMENT = {
    '劣质皮甲': {'def': 1, 'short': '甲'},
    '佣兵短剑': {'atk': 2, 'short': '剑'},
    '骷髅盾':   {'armor': 1, 'short': '盾',
                 'trait_effects': {'亡灵协同': {'atk': -5}}},
    '轻骑护手': {'as': 15, 'regen': 1, 'short': '手'},
    '加速手套': {'as': 50, 'short': '套'},
    '凝魂之泪': {'magic_def_flat': 30, 'short': '泪'},
    '小圆盾': {'armor': 2, 'def': 2, 'short': '圆盾'},
    '回复戒指': {'regen': 4, 'short': '回5'},
}
