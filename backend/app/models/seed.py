"""Seed data loader — populates 48 unique teams + 12 groups on first run."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.event import Event

TEAMS_SEED = [
    # ── Group A ──
    {"name": "United States", "name_cn": "美国", "fifa_code": "USA", "confederation": "CONCACAF",
     "fifa_ranking": 11, "elo_rating": 1870, "group_name": "A", "pot": 1,
     "stats": {"world_cup_titles": 0, "best_result": "Semi-finals (1930)", "appearances": 12}},
    {"name": "Netherlands", "name_cn": "荷兰", "fifa_code": "NED", "confederation": "UEFA",
     "fifa_ranking": 6, "elo_rating": 2020, "group_name": "A", "pot": 2,
     "stats": {"world_cup_titles": 0, "best_result": "Runners-up (1974, 1978, 2010)", "appearances": 12}},
    {"name": "Senegal", "name_cn": "塞内加尔", "fifa_code": "SEN", "confederation": "CAF",
     "fifa_ranking": 18, "elo_rating": 1710, "group_name": "A", "pot": 3,
     "stats": {"world_cup_titles": 0, "best_result": "Quarter-finals (2002)", "appearances": 4}},
    {"name": "Qatar", "name_cn": "卡塔尔", "fifa_code": "QAT", "confederation": "AFC",
     "fifa_ranking": 37, "elo_rating": 1480, "group_name": "A", "pot": 4,
     "stats": {"world_cup_titles": 0, "best_result": "Group Stage (2022)", "appearances": 2}},

    # ── Group B ──
    {"name": "France", "name_cn": "法国", "fifa_code": "FRA", "confederation": "UEFA",
     "fifa_ranking": 2, "elo_rating": 2080, "group_name": "B", "pot": 1,
     "stats": {"world_cup_titles": 2, "best_result": "Champion (1998, 2018)", "appearances": 16}},
    {"name": "Uruguay", "name_cn": "乌拉圭", "fifa_code": "URU", "confederation": "CONMEBOL",
     "fifa_ranking": 14, "elo_rating": 1870, "group_name": "B", "pot": 2,
     "stats": {"world_cup_titles": 2, "best_result": "Champion (1930, 1950)", "appearances": 14}},
    {"name": "South Korea", "name_cn": "韩国", "fifa_code": "KOR", "confederation": "AFC",
     "fifa_ranking": 23, "elo_rating": 1650, "group_name": "B", "pot": 3,
     "stats": {"world_cup_titles": 0, "best_result": "Semi-finals (2002)", "appearances": 12}},
    {"name": "Ghana", "name_cn": "加纳", "fifa_code": "GHA", "confederation": "CAF",
     "fifa_ranking": 60, "elo_rating": 1510, "group_name": "B", "pot": 4,
     "stats": {"world_cup_titles": 0, "best_result": "Quarter-finals (2010)", "appearances": 5}},

    # ── Group C ──
    {"name": "Argentina", "name_cn": "阿根廷", "fifa_code": "ARG", "confederation": "CONMEBOL",
     "fifa_ranking": 1, "elo_rating": 2120, "group_name": "C", "pot": 1,
     "stats": {"world_cup_titles": 3, "best_result": "Champion (1978, 1986, 2022)", "appearances": 18}},
    {"name": "Portugal", "name_cn": "葡萄牙", "fifa_code": "POR", "confederation": "UEFA",
     "fifa_ranking": 8, "elo_rating": 1990, "group_name": "C", "pot": 2,
     "stats": {"world_cup_titles": 0, "best_result": "Semi-finals (1966, 2006)", "appearances": 9}},
    {"name": "Egypt", "name_cn": "埃及", "fifa_code": "EGY", "confederation": "CAF",
     "fifa_ranking": 33, "elo_rating": 1570, "group_name": "C", "pot": 3,
     "stats": {"world_cup_titles": 0, "best_result": "Round of 16 (1934)", "appearances": 4}},
    {"name": "Canada", "name_cn": "加拿大", "fifa_code": "CAN", "confederation": "CONCACAF",
     "fifa_ranking": 42, "elo_rating": 1500, "group_name": "C", "pot": 4,
     "stats": {"world_cup_titles": 0, "best_result": "Group Stage (1986, 2022)", "appearances": 3}},

    # ── Group D ──
    {"name": "Brazil", "name_cn": "巴西", "fifa_code": "BRA", "confederation": "CONMEBOL",
     "fifa_ranking": 3, "elo_rating": 2100, "group_name": "D", "pot": 1,
     "stats": {"world_cup_titles": 5, "best_result": "Champion (1958-2002)", "appearances": 22}},
    {"name": "Germany", "name_cn": "德国", "fifa_code": "GER", "confederation": "UEFA",
     "fifa_ranking": 15, "elo_rating": 1970, "group_name": "D", "pot": 2,
     "stats": {"world_cup_titles": 4, "best_result": "Champion (1954-2014)", "appearances": 20}},
    {"name": "Morocco", "name_cn": "摩洛哥", "fifa_code": "MAR", "confederation": "CAF",
     "fifa_ranking": 13, "elo_rating": 1680, "group_name": "D", "pot": 3,
     "stats": {"world_cup_titles": 0, "best_result": "Semi-finals (2022)", "appearances": 7}},
    {"name": "New Zealand", "name_cn": "新西兰", "fifa_code": "NZL", "confederation": "OFC",
     "fifa_ranking": 103, "elo_rating": 1330, "group_name": "D", "pot": 4,
     "stats": {"world_cup_titles": 0, "best_result": "Group Stage (1982, 2010)", "appearances": 3}},

    # ── Group E ──
    {"name": "England", "name_cn": "英格兰", "fifa_code": "ENG", "confederation": "UEFA",
     "fifa_ranking": 4, "elo_rating": 2040, "group_name": "E", "pot": 1,
     "stats": {"world_cup_titles": 1, "best_result": "Champion (1966)", "appearances": 16}},
    {"name": "Croatia", "name_cn": "克罗地亚", "fifa_code": "CRO", "confederation": "UEFA",
     "fifa_ranking": 10, "elo_rating": 1900, "group_name": "E", "pot": 2,
     "stats": {"world_cup_titles": 0, "best_result": "Runners-up (2018)", "appearances": 7}},
    {"name": "Japan", "name_cn": "日本", "fifa_code": "JPN", "confederation": "AFC",
     "fifa_ranking": 17, "elo_rating": 1700, "group_name": "E", "pot": 3,
     "stats": {"world_cup_titles": 0, "best_result": "Round of 16 (2002-2022)", "appearances": 8}},
    {"name": "Paraguay", "name_cn": "巴拉圭", "fifa_code": "PAR", "confederation": "CONMEBOL",
     "fifa_ranking": 50, "elo_rating": 1530, "group_name": "E", "pot": 4,
     "stats": {"world_cup_titles": 0, "best_result": "Quarter-finals (2010)", "appearances": 8}},

    # ── Group F ──
    {"name": "Spain", "name_cn": "西班牙", "fifa_code": "ESP", "confederation": "UEFA",
     "fifa_ranking": 5, "elo_rating": 2030, "group_name": "F", "pot": 1,
     "stats": {"world_cup_titles": 1, "best_result": "Champion (2010)", "appearances": 16}},
    {"name": "Mexico", "name_cn": "墨西哥", "fifa_code": "MEX", "confederation": "CONCACAF",
     "fifa_ranking": 12, "elo_rating": 1830, "group_name": "F", "pot": 2,
     "stats": {"world_cup_titles": 0, "best_result": "Quarter-finals (1970, 1986)", "appearances": 18}},
    {"name": "Switzerland", "name_cn": "瑞士", "fifa_code": "SUI", "confederation": "UEFA",
     "fifa_ranking": 16, "elo_rating": 1780, "group_name": "F", "pot": 3,
     "stats": {"world_cup_titles": 0, "best_result": "Quarter-finals (1934-1954)", "appearances": 13}},
    {"name": "Cameroon", "name_cn": "喀麦隆", "fifa_code": "CMR", "confederation": "CAF",
     "fifa_ranking": 45, "elo_rating": 1490, "group_name": "F", "pot": 4,
     "stats": {"world_cup_titles": 0, "best_result": "Quarter-finals (1990)", "appearances": 9}},

    # ── Group G ──
    {"name": "Italy", "name_cn": "意大利", "fifa_code": "ITA", "confederation": "UEFA",
     "fifa_ranking": 9, "elo_rating": 1980, "group_name": "G", "pot": 1,
     "stats": {"world_cup_titles": 4, "best_result": "Champion (1934-2006)", "appearances": 18}},
    {"name": "Colombia", "name_cn": "哥伦比亚", "fifa_code": "COL", "confederation": "CONMEBOL",
     "fifa_ranking": 19, "elo_rating": 1810, "group_name": "G", "pot": 2,
     "stats": {"world_cup_titles": 0, "best_result": "Quarter-finals (2014)", "appearances": 7}},
    {"name": "Serbia", "name_cn": "塞尔维亚", "fifa_code": "SRB", "confederation": "UEFA",
     "fifa_ranking": 25, "elo_rating": 1690, "group_name": "G", "pot": 3,
     "stats": {"world_cup_titles": 0, "best_result": "Semi-finals (1930 as Yugoslavia)", "appearances": 13}},
    {"name": "Saudi Arabia", "name_cn": "沙特", "fifa_code": "KSA", "confederation": "AFC",
     "fifa_ranking": 53, "elo_rating": 1400, "group_name": "G", "pot": 4,
     "stats": {"world_cup_titles": 0, "best_result": "Round of 16 (1994)", "appearances": 7}},

    # ── Group H ──
    {"name": "Belgium", "name_cn": "比利时", "fifa_code": "BEL", "confederation": "UEFA",
     "fifa_ranking": 7, "elo_rating": 1950, "group_name": "H", "pot": 1,
     "stats": {"world_cup_titles": 0, "best_result": "Third place (2018)", "appearances": 15}},
    {"name": "Denmark", "name_cn": "丹麦", "fifa_code": "DEN", "confederation": "UEFA",
     "fifa_ranking": 20, "elo_rating": 1820, "group_name": "H", "pot": 2,
     "stats": {"world_cup_titles": 0, "best_result": "Quarter-finals (1998)", "appearances": 7}},
    {"name": "Algeria", "name_cn": "阿尔及利亚", "fifa_code": "ALG", "confederation": "CAF",
     "fifa_ranking": 30, "elo_rating": 1600, "group_name": "H", "pot": 3,
     "stats": {"world_cup_titles": 0, "best_result": "Round of 16 (2014)", "appearances": 5}},
    {"name": "Australia", "name_cn": "澳大利亚", "fifa_code": "AUS", "confederation": "AFC",
     "fifa_ranking": 27, "elo_rating": 1550, "group_name": "H", "pot": 4,
     "stats": {"world_cup_titles": 0, "best_result": "Round of 16 (2006, 2022)", "appearances": 7}},

    # ── Group I ──
    {"name": "Sweden", "name_cn": "瑞典", "fifa_code": "SWE", "confederation": "UEFA",
     "fifa_ranking": 24, "elo_rating": 1760, "group_name": "I", "pot": 1,
     "stats": {"world_cup_titles": 0, "best_result": "Runners-up (1958)", "appearances": 12}},
    {"name": "Nigeria", "name_cn": "尼日利亚", "fifa_code": "NGA", "confederation": "CAF",
     "fifa_ranking": 31, "elo_rating": 1590, "group_name": "I", "pot": 2,
     "stats": {"world_cup_titles": 0, "best_result": "Round of 16 (1994-2014)", "appearances": 7}},
    {"name": "Chile", "name_cn": "智利", "fifa_code": "CHI", "confederation": "CONMEBOL",
     "fifa_ranking": 44, "elo_rating": 1560, "group_name": "I", "pot": 3,
     "stats": {"world_cup_titles": 0, "best_result": "Third place (1962)", "appearances": 9}},
    {"name": "Iran", "name_cn": "伊朗", "fifa_code": "IRN", "confederation": "AFC",
     "fifa_ranking": 22, "elo_rating": 1580, "group_name": "I", "pot": 4,
     "stats": {"world_cup_titles": 0, "best_result": "Group Stage", "appearances": 7}},

    # ── Group J ──
    {"name": "Poland", "name_cn": "波兰", "fifa_code": "POL", "confederation": "UEFA",
     "fifa_ranking": 28, "elo_rating": 1640, "group_name": "J", "pot": 1,
     "stats": {"world_cup_titles": 0, "best_result": "Third place (1974, 1982)", "appearances": 10}},
    {"name": "Tunisia", "name_cn": "突尼斯", "fifa_code": "TUN", "confederation": "CAF",
     "fifa_ranking": 35, "elo_rating": 1520, "group_name": "J", "pot": 2,
     "stats": {"world_cup_titles": 0, "best_result": "Group Stage", "appearances": 7}},
    {"name": "Austria", "name_cn": "奥地利", "fifa_code": "AUT", "confederation": "UEFA",
     "fifa_ranking": 26, "elo_rating": 1720, "group_name": "J", "pot": 3,
     "stats": {"world_cup_titles": 0, "best_result": "Third place (1954)", "appearances": 8}},
    {"name": "Ukraine", "name_cn": "乌克兰", "fifa_code": "UKR", "confederation": "UEFA",
     "fifa_ranking": 29, "elo_rating": 1630, "group_name": "J", "pot": 4,
     "stats": {"world_cup_titles": 0, "best_result": "Quarter-finals (2006)", "appearances": 2}},

    # ── Group K ──
    {"name": "Mali", "name_cn": "马里", "fifa_code": "MLI", "confederation": "CAF",
     "fifa_ranking": 47, "elo_rating": 1450, "group_name": "K", "pot": 1,
     "stats": {"world_cup_titles": 0, "best_result": "Debut", "appearances": 1}},
    {"name": "Costa Rica", "name_cn": "哥斯达黎加", "fifa_code": "CRC", "confederation": "CONCACAF",
     "fifa_ranking": 49, "elo_rating": 1470, "group_name": "K", "pot": 2,
     "stats": {"world_cup_titles": 0, "best_result": "Quarter-finals (2014)", "appearances": 6}},
    {"name": "China PR", "name_cn": "中国", "fifa_code": "CHN", "confederation": "AFC",
     "fifa_ranking": 80, "elo_rating": 1350, "group_name": "K", "pot": 3,
     "stats": {"world_cup_titles": 0, "best_result": "Group Stage (2002)", "appearances": 2}},
    {"name": "Norway", "name_cn": "挪威", "fifa_code": "NOR", "confederation": "UEFA",
     "fifa_ranking": 43, "elo_rating": 1620, "group_name": "K", "pot": 4,
     "stats": {"world_cup_titles": 0, "best_result": "Round of 16 (1998)", "appearances": 4}},

    # ── Group L ──
    {"name": "Ecuador", "name_cn": "厄瓜多尔", "fifa_code": "ECU", "confederation": "CONMEBOL",
     "fifa_ranking": 32, "elo_rating": 1610, "group_name": "L", "pot": 1,
     "stats": {"world_cup_titles": 0, "best_result": "Round of 16 (2006)", "appearances": 5}},
    {"name": "Peru", "name_cn": "秘鲁", "fifa_code": "PER", "confederation": "CONMEBOL",
     "fifa_ranking": 34, "elo_rating": 1580, "group_name": "L", "pot": 2,
     "stats": {"world_cup_titles": 0, "best_result": "Quarter-finals (1970)", "appearances": 6}},
    {"name": "Hungary", "name_cn": "匈牙利", "fifa_code": "HUN", "confederation": "UEFA",
     "fifa_ranking": 36, "elo_rating": 1650, "group_name": "L", "pot": 3,
     "stats": {"world_cup_titles": 0, "best_result": "Runners-up (1938, 1954)", "appearances": 10}},
    {"name": "South Africa", "name_cn": "南非", "fifa_code": "RSA", "confederation": "CAF",
     "fifa_ranking": 62, "elo_rating": 1430, "group_name": "L", "pot": 4,
     "stats": {"world_cup_titles": 0, "best_result": "Group Stage", "appearances": 4}},
]

EVENTS_SEED = [
    {
        "fifa_code": "FRA",
        "type": "INJURY",
        "title": "姆巴佩肌肉拉伤恢复中",
        "description": "赛前训练中左腿肌肉不适，队医评估完全康复概率约 85%，但存在复发风险",
        "severity": "MAJOR",
        "impact": {"attack": -0.10, "team_morale": -0.03},
        "source": "法国队赛前新闻发布会 (2026-07-05)",
    },
    {
        "fifa_code": "BRA",
        "type": "TACTICAL",
        "title": "新主帅战术体系调整",
        "description": "新任主帅上任后改为 4-3-3 阵型，强调边路突破和中场控制",
        "severity": "MINOR",
        "impact": {"tactical_cohesion": -0.05, "attack_variation": 0.05},
        "source": "FIFA 官方公告",
    },
    {
        "fifa_code": "ARG",
        "type": "MORALE",
        "title": "梅西最后一届世界杯",
        "description": "梅西宣布本届为其最后一届世界杯，全队士气高涨，誓为队长再夺一冠",
        "severity": "MAJOR",
        "impact": {"team_morale": 0.12, "big_match_experience": 0.10},
        "source": "梅西个人社交媒体 (2026-06-15)",
    },
    {
        "fifa_code": "ENG",
        "type": "INJURY",
        "title": "贝林厄姆轻伤但可出战",
        "description": "中场核心贝林厄姆脚踝轻微扭伤，队医确认不影响出场但可能影响状态",
        "severity": "MINOR",
        "impact": {"midfield_control": -0.05},
        "source": "英格兰队训练报告 (2026-07-04)",
    },
    {
        "fifa_code": "GER",
        "type": "COACHING",
        "title": "新教练团队首秀大赛",
        "description": "德国队更换主教练后首次参加大赛，球队战术体系仍在磨合期",
        "severity": "MAJOR",
        "impact": {"tactical_cohesion": -0.10, "set_piece_defense": -0.05},
        "source": "德国足协公告",
    },
    {
        "fifa_code": "ESP",
        "type": "MORALE",
        "title": "年轻阵容大赛经验不足",
        "description": "西班牙本届以年轻阵容为主，平均年龄仅 24.5 岁，活力充沛但经验欠缺",
        "severity": "MINOR",
        "impact": {"big_match_experience": -0.08, "stamina": 0.05},
        "source": "西班牙队阵容分析",
    },
]


async def seed_all(session: AsyncSession):
    """Load seed data if database is empty (idempotent)."""
    result = await session.execute(select(Team).limit(1))
    if result.scalars().first():
        return  # already seeded

    team_map: dict[str, Team] = {}
    for data in TEAMS_SEED:
        team = Team(**data)
        session.add(team)
        team_map[data["fifa_code"]] = team

    await session.flush()

    for data in EVENTS_SEED:
        code = data["fifa_code"]
        team = team_map.get(code)
        if team:
            event_data = {k: v for k, v in data.items() if k != "fifa_code"}
            event = Event(team_id=team.id, **event_data)
            session.add(event)

    await session.commit()
    print(f"✅ Seeded {len(TEAMS_SEED)} teams and {len(EVENTS_SEED)} events")
