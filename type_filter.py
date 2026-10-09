# Фильтр по типу одежды. Определяем тип по названию лота (латиница + китайский).
# Если у подписчика типы не выбраны, пропускаем всё.
import re

KW = {'шапка': ['beanie', 'knit hat', 'knit cap', 'balaclava', '毛线帽', '针织帽', '冷帽', '毛帽', '头套', '护耳帽'],
 'кепка': ['cap', 'snapback', 'baseball cap', 'trucker', '棒球帽', '鸭舌帽', '卡车帽', '平沿帽', '老帽'],
 'шляпа': ['hat', 'bucket hat', 'fedora', 'beret', '渔夫帽', '礼帽', '草帽', '盆帽', '牛仔帽', '绅士帽', '贝雷帽'],
 'куртка': ['jacket',
            'bomber',
            'blouson',
            'parka',
            'down jacket',
            '夹克',
            '皮衣',
            '皮夹克',
            '棉服',
            '羽绒服',
            '棉衣',
            '外套',
            '机车服',
            '飞行员'],
 'пальто': ['coat', 'overcoat', 'trench', 'peacoat', 'pea coat', '大衣', '呢大衣', '羊毛大衣', '风衣', '毛呢外套'],
 'ветровка': ['windbreaker',
              'anorak',
              'shell jacket',
              'track jacket',
              'nylon jacket',
              '风衣',
              '冲锋衣',
              '防风衣',
              '防风外套',
              '皮肤衣',
              '山地外套'],
 'жилетка': ['vest', 'gilet', 'waistcoat', '马甲', '羽绒马甲', '工装马甲'],
 'зипка': ['zip hoodie', 'zip up hoodie', 'zip-up', 'zip up', 'full zip', 'zipup', '拉链卫衣', '拉链连帽', '连帽拉链'],
 'худи': ['hoodie', 'hooded', 'pullover hoodie', '连帽卫衣', '帽衫', '连帽衫', '连帽'],
 'свитшот': ['sweatshirt', 'crewneck', 'crew neck', 'sweat', '卫衣', '圆领卫衣', '套头卫衣', '圆领'],
 'лонгслив': ['long sleeve', 'longsleeve', 'long-sleeve', 'l/s', '长袖', '长t', '长袖t恤'],
 'футболка': ['t-shirt', 'tshirt', 't shirt', 'tee', 'tee shirt', 't恤', '短袖', '体恤'],
 'майка': ['tank top', 'tank', 'singlet', 'sleeveless', 'camisole', '背心', '吊带', '无袖'],
 'браслет': ['bracelet', 'bangle', 'cuff', '手链', '手镯', '手环', '手串'],
 'кольцо': ['ring', 'signet', '戒指', '指环', '尾戒', '对戒'],
 'сумка': ['bag',
           'tote',
           'shoulder bag',
           'crossbody',
           'messenger',
           'handbag',
           'pouch',
           'clutch',
           '单肩包',
           '斜挎包',
           '手提包',
           '托特包',
           '腰包',
           '挎包',
           '手拿包',
           '公文包',
           '邮差包',
           '水桶包',
           '包包',
           '女包',
           '男包'],
 'рюкзак': ['backpack', 'rucksack', 'daypack', 'back pack', '背包', '双肩包', '书包', '登山包', '双肩'],
 'штаны': ['pants',
           'trousers',
           'cargo',
           'slacks',
           'sweatpants',
           'joggers',
           'track pants',
           '长裤',
           '休闲裤',
           '工装裤',
           '西裤',
           '运动裤',
           '卫裤',
           '裤子',
           '直筒裤',
           '阔腿裤',
           '束脚裤',
           '灯芯绒裤'],
 'джинсы': ['jeans', 'denim pants', '牛仔裤', '牛仔长裤', '丹宁裤'],
 'шорты': ['shorts', 'short pants', '短裤', '五分裤', '沙滩裤', '中裤', '七分裤'],
 'носки': ['socks', 'sock', '袜'],
 'кроссовки': ['sneakers',
               'sneaker',
               'trainers',
               'runners',
               'running shoes',
               '运动鞋',
               '球鞋',
               '跑鞋',
               '跑步鞋',
               '老爹鞋',
               '篮球鞋'],
 'ботинки': ['boots', 'boot', 'derby', 'oxford', 'loafers', 'leather shoes', '靴', '皮鞋', '马丁'],
 'казаки': ['cowboy boots', 'cowboy boot', 'western boots', 'cossack', '西部靴', '牛仔靴', '哥萨克', '尖头靴'],
 'кеды': ['canvas shoes',
          'canvas sneaker',
          'low top',
          'low-top',
          'chuck 70',
          'all star',
          '帆布鞋',
          '板鞋',
          '低帮',
          '小白鞋'],
 'высокие кеды': ['high top', 'high-top', 'hi top', 'hi-top', 'chuck taylor', '高帮', '高帮帆布', '高帮鞋']}

def _compile(kw_by_type):
    out = {}
    for t, kws in kw_by_type.items():
        parts = []
        for k in kws:
            k = k.lower()
            if re.fullmatch(r"[a-z0-9 \-/.]+", k):
                parts.append(r"(?<![a-z0-9])" + re.escape(k) + r"s?(?![a-z0-9])")
            else:
                parts.append(re.escape(k))
        out[t] = re.compile("|".join(parts))
    return out

_MATCHERS = _compile(KW)


def type_ok(title, wanted):
    wanted = [w for w in (wanted or []) if w in _MATCHERS]
    if not wanted:
        return True
    t = (title or "").lower()
    return any(_MATCHERS[w].search(t) for w in wanted)
