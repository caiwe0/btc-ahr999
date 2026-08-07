"""
BTC AHR999 配置文件（校准版 2026）
集中管理所有可调参数，避免硬编码
"""

class Config:
    # ── 手续费 ──────────────────────────────────
    FEE_RATE = 0.001           # 币安普通用户 0.1% 双向

    # ── AHR999 区间阈值 ─────────────────────────
    EXTREME_LOW  = 0.45        # < 此值 = 极度低估
    DIP_ZONE     = 1.2         # < 此值 = 定投区
    FAIR_HIGH    = 4.0         # < 此值 = 合理偏高，>= 此值 = 高估

    # ── 幂律拟合参数（2026年校准版）────────────
    # price ≈ A * days^B   （days = 距 2009-01-03 创世区块天数）
    # 用 2013($100)/2017($1000)/2021($29000)/2024($43000)/2026($60000) 拟合
    POWER_LAW_A = 4.201e-13
    POWER_LAW_B = 4.5985

    # ── 单K异常检测阈值 ─────────────────────────
    ATR_MULT_EXTREME = 2.5     # 实体 > 2.5×ATR = 极端
    ATR_MULT_BODY    = 0.3     # 实体 < 0.3×ATR = 十字/纺锤
    VOL_MULT_HIGH    = 2.0     # 量 > 2.0×VMA20 = 放量
    VOL_MULT_LOW     = 0.6     # 量 < 0.6×VMA20 = 缩量

    # ── 调度时间（UTC+8）───────────────────────
    SCHEDULE_HOUR   = 8
    SCHEDULE_MINUTE = 0

    # ── Web 服务 ────────────────────────────────
    HOST = "0.0.0.0"
    PORT = 5000
    DEBUG = False

    # ── 数据缓存 ────────────────────────────────
    CACHE_FILE = "btc_cache.csv"
    EXCEL_FILE = "BTC_AHR999.xlsx"
    JSON_FILE  = "ahr999_data.json"
    MANUAL_CSV = "manual_input.csv"

    # ── 颜色映射 ────────────────────────────────
    COLORS = {
        "extreme_low":      "#90EE90",   # 浅绿
        "dip_zone":         "#FFFFFF",   # 白
        "fair_high":        "#FFCCCC",   # 浅红
        "overvalued":       "#FF0000",   # 红
        "extreme_low_anom": "#228B22",   # 深绿
        "dip_zone_anom":    "#FFFF00",   # 黄
        "fair_high_anom":   "#FF6666",   # 中红
        "overvalued_anom":  "#8B0000",   # 深红
        "manual_col":       "#FFF8DC",   # 玉米丝
        "pnl_up":           "#00FF7F",   # 盈利绿
        "pnl_down":         "#FF6347",   # 亏损橙红
        "amount_gold":      "#FFD700",   # 金额金
    }

# ── 模块级别名（兼容 config.XXX 直接访问）──────────────
cfg = Config()
FEE_RATE = cfg.FEE_RATE
EXTREME_LOW = cfg.EXTREME_LOW
DIP_ZONE = cfg.DIP_ZONE
FAIR_HIGH = cfg.FAIR_HIGH
POWER_LAW_A = cfg.POWER_LAW_A
POWER_LAW_B = cfg.POWER_LAW_B
ATR_MULT_EXTREME = cfg.ATR_MULT_EXTREME
ATR_MULT_BODY = cfg.ATR_MULT_BODY
VOL_MULT_HIGH = cfg.VOL_MULT_HIGH
VOL_MULT_LOW = cfg.VOL_MULT_LOW
SCHEDULE_HOUR = cfg.SCHEDULE_HOUR
SCHEDULE_MINUTE = cfg.SCHEDULE_MINUTE
HOST = cfg.HOST
PORT = cfg.PORT
DEBUG = cfg.DEBUG
CACHE_FILE = cfg.CACHE_FILE
EXCEL_FILE = cfg.EXCEL_FILE
JSON_FILE = cfg.JSON_FILE
MANUAL_CSV = cfg.MANUAL_CSV
COLORS = cfg.COLORS
