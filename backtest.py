"""
纳斯达克 100 ETF 定投回测引擎。

策略：底仓 + 每月固定金额定投，整数股交易。

输入：
  - base_amount:   底仓一次性投入（元）
  - monthly_amount: 每月定投金额（元）
  - price_df:       月度价格 DataFrame（来自 data.py），含 Open / Close / Return

输出：
  - summary:      总投入、总收益、总收益率、年化收益率(CAGR)、最大回撤
  - annual:       每年投入、年末市值、当年市值变化
  - transactions: 每笔买入记录
  - monthly:      每月持仓明细（用于绘图）
"""

import pandas as pd
import numpy as np


def run_backtest(
    base_amount: float,
    monthly_amount: float,
    price_df: pd.DataFrame,
) -> dict:
    """
    执行回测。

    参数
    ----------
    base_amount : float
        底仓一次性投入金额。
    monthly_amount : float
        每月定投金额。
    price_df : pd.DataFrame
        月度价格数据，索引为 Period[M]，含列 Open、Close。

    返回
    ----------
    dict，包含：
      - summary:       dict 格式的汇总指标
      - annual:        pd.DataFrame 年度汇总
      - transactions:  pd.DataFrame 交易记录
      - monthly:       pd.DataFrame 每月明细
    """
    df = price_df.sort_index().copy()

    if len(df) == 0:
        raise ValueError("价格数据为空")

    cash = base_amount
    shares = 0
    total_invested = base_amount

    monthly_records = []
    transactions = []

    for month, row in df.iterrows():
        open_price = row["Open"]
        close_price = row["Close"]

        # 月初：加入本月定投资金
        cash += monthly_amount
        total_invested += monthly_amount

        # 买入整数股
        if open_price > 0 and cash >= open_price:
            buyable = int(cash / open_price)
            if buyable > 0:
                cost = buyable * open_price
                shares += buyable
                cash -= cost
                transactions.append({
                    "month": str(month),
                    "price": round(open_price, 4),
                    "shares": buyable,
                    "amount": round(cost, 2),
                })

        # 月末市值
        portfolio_value = shares * close_price + cash

        monthly_records.append({
            "month": month,
            "open": open_price,
            "close": close_price,
            "shares": shares,
            "cash": round(cash, 2),
            "portfolio_value": round(portfolio_value, 2),
            "total_invested": round(total_invested, 2),
        })

    monthly_df = pd.DataFrame(monthly_records)
    monthly_df = monthly_df.set_index("month")

    # ---- 汇总指标 ----
    final_value = monthly_df["portfolio_value"].iloc[-1]
    total_profit = final_value - total_invested
    total_return_pct = (total_profit / total_invested) * 100 if total_invested > 0 else 0

    # 年化收益率 (CAGR)
    years = len(df) / 12.0
    cagr = (final_value / total_invested) ** (1 / years) - 1 if total_invested > 0 and years > 0 else 0

    # 最大回撤
    peak = monthly_df["portfolio_value"].expanding().max()
    drawdown = (monthly_df["portfolio_value"] - peak) / peak
    max_drawdown = drawdown.min()

    summary = {
        "total_invested": round(total_invested, 2),
        "final_value": round(final_value, 2),
        "total_profit": round(total_profit, 2),
        "total_return_pct": round(total_return_pct, 2),
        "cagr_pct": round(cagr * 100, 2),
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "years": round(years, 2),
        "final_shares": shares,
        "final_cash": round(cash, 2),
    }

    # ---- 年度汇总 ----
    annual_data = []
    years_in_data = sorted(set(m.year for m in monthly_df.index))

    prev_year_end_value = 0
    is_first_year = True

    for year in years_in_data:
        year_mask = monthly_df.index.year == year
        year_months = monthly_df[year_mask]

        year_invested = monthly_amount * len(year_months)
        if is_first_year:
            year_invested += base_amount
            is_first_year = False

        year_end_value = year_months["portfolio_value"].iloc[-1]

        if prev_year_end_value == 0 and year == years_in_data[0]:
            year_change = year_end_value - total_invested  # 第一年：市值 - 累计投入
        else:
            year_change = year_end_value - prev_year_end_value

        annual_data.append({
            "年份": year,
            "当年投入": round(year_invested, 2),
            "累计投入": round(year_months["total_invested"].iloc[-1], 2),
            "年末市值": round(year_end_value, 2),
            "当年市值变化": round(year_change, 2),
        })

        prev_year_end_value = year_end_value

    annual_df = pd.DataFrame(annual_data)

    # ---- 交易记录 ----
    tx_df = pd.DataFrame(transactions)
    if not tx_df.empty:
        tx_df.insert(0, "序号", range(1, len(tx_df) + 1))
        tx_df.columns = ["序号", "月份", "买入价", "买入股数", "买入金额"]

    return {
        "summary": summary,
        "annual": annual_df,
        "transactions": tx_df,
        "monthly": monthly_df,
    }
