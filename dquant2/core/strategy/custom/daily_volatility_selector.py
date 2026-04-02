"""
日频多因子轮动策略


横截面 Alpha 的标准做法：

市值过滤（核心）：500亿 ≤ 流通市值 ≤ 1500亿
流动性过滤（必须）：近20日平均成交额 ≥ 5亿，公式：avg_turnover = mean(volume * close, 20)
换手率过滤（活跃度）：近5日平均换手率 ≥ 2%
风险排除项（必须）：
- ST / *ST
- 停牌
- 连续跌停 / 涨停
- 财报异常


波动因子
推荐因子：ATR / Close ，VolFactor = ATR(14) / Close，表示相对波动，而不是绝对价格
振幅因子：AmpFactor = mean((High - Low) / Close, 5)，
成交量放大因子（聪明钱）：VolRatio = Volume_today / MA(Volume, 20)
趋势稳定因子（防止乱震）：Trend = Close / MA(Close, 20)， 如0.98 < Trend < 1.05



线性打分模型：
Score =
    0.35 * VolFactor
  + 0.25 * AmpFactor
  + 0.20 * VolRatio
  + 0.20 * TrendScore

每天选 Top 10



每日收盘后选股，次日开盘 / VWAP 买入

单只股票 ≤ 50% ，总股票数 2~3

止损与止盈（规则化）
推荐组合：

固定止损：-6%

移动止盈：回撤 3%

最大持有期：5~10 天

📌 时间止损非常重要

极端风险保护
- 单日组合回撤 > 3% → 全部减仓
- 连续 3 天亏损 → 暂停 1天，并发送lark消息给用户





"""

import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class DailyRotationStrategy:
    def __init__(
        self,
        target_stock_num=5,
        capital=1_000_000,
        max_position_ratio=0.2,
    ):
        """
        :param target_stock_num: 每天持有股票数量
        :param capital: 初始资金
        :param max_position_ratio: 单只股票最大仓位
        """
        self.target_stock_num = target_stock_num
        self.capital = capital
        self.max_position_ratio = max_position_ratio

    # =========================
    # 1. 获取股票基础池 (改为本地数据库)
    # =========================
    def get_stock_universe(self) -> pd.DataFrame:
        """
        从本地 quant.db 获取最新一天的A股横截面行情
        包含市值、换手率等
        """
        # 连接本地数据库
        db_path = 'data/db/quant.db'
        if not os.path.exists(db_path):
            print(f"警告：找不到本地数据库 {db_path}，请先使用 Tushare 下载数据。")
            return pd.DataFrame()
            
        conn = sqlite3.connect(db_path)
        
        try:
            # 获取最新有交易的日期
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(trade_date) FROM daily")
            latest_date = cursor.fetchone()[0]
            
            if not latest_date:
                print("警告：daily 表中没有找到价格数据。")
                return pd.DataFrame()
                
            print(f"✅ 使用本地数据库截面日期: {latest_date}")
            
            # 使用 SQL JOIN 直接提取最新的横截面数据
            sql = f"""
            SELECT 
                d.ts_code as symbol,
                sb.name as name,
                d.close as price,
                d.amount * 1000 as amount,        -- tushare的amount是千元,AKShare通常是元
                db.turnover_rate as turnover,
                db.circ_mv * 10000 as market_cap, -- tushare的circ_mv是万元
                ((d.high - d.low) / d.pre_close) * 100 as amplitude
            FROM daily d
            JOIN stock_basic sb ON d.ts_code = sb.ts_code
            LEFT JOIN daily_basic db ON d.ts_code = db.ts_code AND d.trade_date = db.trade_date
            WHERE d.trade_date = '{latest_date}'
            """
            
            df = pd.read_sql_query(sql, conn)
            
            # 兼容 AKShare 前端代码所预期的格式
            # (不需要再 rename，因为 SQL 已经 as 好了)
            
            # 将 symbol 例如 000001.SZ 格式转换为 纯代码 (如果是前端期待的话)
            # 根据原先 AKShare 返回的逻辑，如果是保留原样则无需处理
            
            return df
            
        except Exception as e:
            print(f"从本地数据库获取数据失败: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

    # =========================
    # 2. 股票筛选
    # =========================
    def filter_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        多条件过滤
        """

        # 剔除 ST
        df = df[~df["name"].str.contains("ST")]

        # 市值过滤（单位：元）
        df = df[
            (df["market_cap"] >= 5e10) &  # 500亿
            (df["market_cap"] <= 1.5e11)  # 1500亿
        ]

        # 换手率 >= 2%
        df = df[df["turnover"] >= 2]

        # 成交额 >= 5亿
        df = df[df["amount"] >= 5e8]

        # 振幅 3% - 8%
        df = df[
            (df["amplitude"] >= 3) &
            (df["amplitude"] <= 8)
        ]

        return df

    # =========================
    # 3. 因子打分
    # =========================
    def score_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        多因子打分（标准化后加权）
        """

        df = df.copy()

        # 因子标准化（Z-score）
        df["turnover_z"] = (df["turnover"] - df["turnover"].mean()) / df["turnover"].std()
        df["amount_z"] = (df["amount"] - df["amount"].mean()) / df["amount"].std()
        df["amplitude_z"] = (df["amplitude"] - df["amplitude"].mean()) / df["amplitude"].std()

        # 综合评分（可自行调权重）
        df["score"] = (
            0.4 * df["turnover_z"] +
            0.4 * df["amount_z"] +
            0.2 * df["amplitude_z"]
        )

        return df.sort_values("score", ascending=False)

    # =========================
    # 4. 选股结果
    # =========================
    def select_stocks(self) -> pd.DataFrame:
        """
        执行完整选股流程
        """
        df = self.get_stock_universe()
        df = self.filter_stocks(df)
        df = self.score_stocks(df)

        return df.head(self.target_stock_num)

    # =========================
    # 5. 仓位分配
    # =========================
    def allocate_positions(self, selected_df: pd.DataFrame) -> pd.DataFrame:
        """
        等权分配资金
        """
        stock_num = len(selected_df)
        if stock_num == 0:
            return pd.DataFrame()

        single_position_cash = min(
            self.capital / stock_num,
            self.capital * self.max_position_ratio
        )

        selected_df = selected_df.copy()
        selected_df["target_cash"] = single_position_cash
        selected_df["shares"] = (single_position_cash / selected_df["price"]).astype(int)

        return selected_df


# =========================
# 主执行
# =========================
if __name__ == "__main__":
    strategy = DailyRotationStrategy(
        target_stock_num=5,
        capital=1_000_000,
        max_position_ratio=0.2,
    )

    selected = strategy.select_stocks()
    positions = strategy.allocate_positions(selected)

    print("📈 今日选股结果：")
    print(positions[[
        "symbol",
        "name",
        "price",
        "market_cap",
        "turnover",
        "amount",
        "amplitude",
        "score",
        "shares",
    ]])
