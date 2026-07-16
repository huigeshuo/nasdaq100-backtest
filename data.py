"""
纳斯达克 100 ETF 月度价格数据模块。

数据来源：东方财富（East Money）API
  - QQQ（Invesco QQQ ETF）：2001-01 至 2026-06
  - 日线数据重采样为月度 OHLC，前复权价格

由于在中国大陆无法访问 Yahoo Finance，改用东方财富 API。
"""

import os
import time
import pandas as pd
import requests

# 数据文件路径
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CSV_PATH = os.path.join(DATA_DIR, "nasdaq100_monthly.csv")

# 东方财富 API 配置
EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


def _fetch_daily_from_eastmoney(
    secid: str,
    start_date: str,
    end_date: str,
    max_retries: int = 5,
) -> pd.DataFrame:
    """
    从东方财富拉取日线 K 线数据（前复权）。

    参数
    ----------
    secid : str
        东方财富证券代码，如 "105.QQQ"（105 = NASDAQ）。
    start_date : str
        起始日期 YYYYMMDD。
    end_date : str
        结束日期 YYYYMMDD。
    max_retries : int
        最大重试次数。

    返回
    ----------
    pd.DataFrame，列：日期, 开盘, 收盘, 最高, 最低, 成交量
    """
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",          # 日线
        "fqt": "1",            # 前复权
        "beg": start_date,
        "end": end_date,
        "lmt": "10000",        # 最大返回条数
    }

    for attempt in range(max_retries):
        try:
            resp = requests.get(EASTMONEY_KLINE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            klines = data.get("data", {}).get("klines", [])
            if not klines:
                raise ValueError(f"{secid} 返回空数据（{start_date} 至 {end_date}）")

            # 解析 K 线数据
            # 格式：日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
            records = []
            for line in klines:
                parts = line.split(",")
                records.append({
                    "date": parts[0],
                    "open": float(parts[1]),
                    "close": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "volume": int(parts[5]),
                })

            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            return df

        except (requests.ConnectionError, requests.Timeout,
                ConnectionError, TimeoutError) as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 10
                print(f"  {secid} 请求失败（{e}），{wait}秒后重试...")
                time.sleep(wait)
            else:
                raise
        except Exception:
            # 非网络错误直接抛出
            raise

    raise RuntimeError(f"无法获取 {secid} 的数据")


def _daily_to_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    """
    将日线数据重采样为月度 OHLC。

    返回 DataFrame，列为：Open, Close
    索引为 Period[M]（如 '2001-01', '2001-02', ...）
    """
    monthly = daily.resample("MS").agg({
        "open": "first",
        "close": "last",
    })
    monthly = monthly.rename(columns={"open": "Open", "close": "Close"})
    monthly = monthly.dropna()

    monthly.index = monthly.index.to_period("M")
    monthly.index.name = "month"

    return monthly


def load_data(force_refresh: bool = False) -> pd.DataFrame:
    """
    加载纳斯达克 100 月度价格数据。

    首次调用时从东方财富拉取并缓存到 CSV，
    后续调用直接读 CSV。设置 force_refresh=True 可强制重新拉取。

    返回 DataFrame，列为：Open, Close, Return
    索引为 Period[M]（如 '2001-01', '2001-02', ...）
    """
    if not force_refresh and os.path.exists(CSV_PATH):
        print(f"从缓存加载数据：{CSV_PATH}")
        df = pd.read_csv(CSV_PATH, index_col=0)
        df.index = pd.PeriodIndex(df.index, freq="M")
        df.index.name = "month"
        return df

    print("正在从东方财富拉取 QQQ 日线数据（2001-2026）...")
    daily = _fetch_daily_from_eastmoney(
        secid="105.QQQ",
        start_date="20010101",
        end_date="20260630",
    )
    print(f"  获取到 {len(daily)} 条日线数据")

    print("正在重采样为月度数据...")
    monthly = _daily_to_monthly(daily)
    print(f"  共 {len(monthly)} 个月")

    # 添加月度收益率列
    monthly["Return"] = monthly["Close"] / monthly["Open"] - 1

    # 确保 data 目录存在
    os.makedirs(DATA_DIR, exist_ok=True)

    monthly.to_csv(CSV_PATH, index=True)
    print(f"数据已缓存至 {CSV_PATH}")

    return monthly


def get_date_range(df: pd.DataFrame):
    """返回 DataFrame 中可用的最早和最晚月份。"""
    return df.index.min(), df.index.max()


if __name__ == "__main__":
    # 独立运行：拉取并打印数据概览
    df = load_data(force_refresh=True)
    print(f"\n数据范围：{df.index.min()} 至 {df.index.max()}")
    print(f"共 {len(df)} 个月")
    print(f"\n前 5 行：")
    print(df.head())
    print(f"\n后 5 行：")
    print(df.tail())
