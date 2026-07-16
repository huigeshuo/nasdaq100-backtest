"""
纳斯达克 100 ETF 定投回测 — Streamlit 界面
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data import load_data
from backtest import run_backtest

# ---- 页面配置 ----
st.set_page_config(
    page_title="纳斯达克 100 定投回测",
    page_icon="📈",
    layout="wide",
)

st.title("📈 纳斯达克 100 ETF 定投回测")
st.caption("策略：底仓 + 每月固定金额定投 · 整数股交易 · 2001–2026 QQQ 历史数据（东方财富）")

# ---- 加载数据 ----
with st.spinner("正在加载价格数据..."):
    try:
        price_df = load_data()
        data_min_year = price_df.index.min().year
        data_max_year = price_df.index.max().year
        data_max_month = price_df.index.max().month
    except Exception as e:
        st.error(f"数据加载失败：{e}")
        st.info("请先运行 `python data.py` 拉取数据（需要网络连接）。")
        st.stop()

# ---- 侧边栏：参数输入 ----
st.sidebar.header("📋 回测参数")

base_amount = st.sidebar.number_input(
    "底仓金额（元）",
    min_value=0,
    value=100_000,
    step=10_000,
    format="%d",
    help="一次性投入的初始资金",
)

monthly_amount = st.sidebar.number_input(
    "每月定投金额（元）",
    min_value=0,
    value=1_000,
    step=500,
    format="%d",
    help="每月固定投入的金额",
)

col1, col2 = st.sidebar.columns(2)
with col1:
    start_year = st.selectbox(
        "起始年份",
        options=list(range(data_min_year, data_max_year + 1)),
        index=0,
    )
with col2:
    end_year = st.selectbox(
        "结束年份",
        options=list(range(data_min_year, data_max_year + 1)),
        index=len(range(data_min_year, data_max_year + 1)) - 1,
    )

st.sidebar.divider()
st.sidebar.caption(
    f"数据范围：{data_min_year}年 至 {data_max_year}年{data_max_month}月\n\n"
    "数据来源：东方财富（QQQ 前复权日线）"
)

if st.sidebar.button("🚀 开始回测", type="primary", use_container_width=True):
    # 筛选数据
    start_period = f"{start_year}-01"
    end_period = f"{end_year}-12"
    df_subset = price_df.loc[start_period:end_period].copy()

    if len(df_subset) == 0:
        st.error("所选时间范围内无可用数据。")
        st.stop()

    # 执行回测
    with st.spinner("回测计算中..."):
        result = run_backtest(
            base_amount=base_amount,
            monthly_amount=monthly_amount,
            price_df=df_subset,
        )

    summary = result["summary"]
    annual = result["annual"]
    transactions = result["transactions"]
    monthly = result["monthly"]

    # ---- 指标卡片 ----
    st.subheader("📊 回测概览")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("总投入", f"¥{summary['total_invested']:,.0f}")
    with col2:
        st.metric("期末总市值", f"¥{summary['final_value']:,.0f}")
    with col3:
        delta_color = "normal" if summary["total_profit"] >= 0 else "inverse"
        st.metric(
            "总收益",
            f"¥{summary['total_profit']:,.0f}",
            delta=f"{summary['total_return_pct']:+.2f}%",
            delta_color=delta_color,
        )
    with col4:
        st.metric("年化收益率 (CAGR)", f"{summary['cagr_pct']:.2f}%")
    with col5:
        st.metric("最大回撤", f"{summary['max_drawdown_pct']:.2f}%")

    st.divider()

    # ---- 收益曲线图 ----
    st.subheader("📈 收益曲线")

    fig = make_subplots(specs=[[{"secondary_y": False}]])
    fig.add_trace(
        go.Scatter(
            x=monthly.index.astype(str),
            y=monthly["portfolio_value"],
            mode="lines",
            name="持仓市值",
            line=dict(color="#2962FF", width=2),
            hovertemplate="%{x}<br>市值：¥%{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=monthly.index.astype(str),
            y=monthly["total_invested"],
            mode="lines",
            name="累计投入",
            line=dict(color="#999999", width=1.5, dash="dash"),
            hovertemplate="%{x}<br>投入：¥%{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=450,
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        xaxis_title=None,
        yaxis_title="金额（元）",
        yaxis_tickprefix="¥",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ---- 年度汇总表 ----
    st.subheader("📅 年度汇总")

    # 格式化显示
    annual_display = annual.copy()
    for col in ["当年投入", "累计投入", "年末市值", "当年市值变化"]:
        annual_display[col] = annual_display[col].apply(lambda x: f"¥{x:,.2f}")

    st.dataframe(
        annual_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "年份": st.column_config.NumberColumn(format="%d"),
        },
    )

    st.divider()

    # ---- 交易记录 ----
    st.subheader("📝 交易明细")

    if transactions.empty:
        st.info("无交易记录（定投金额不足以购买 1 股）。")
    else:
        tx_count = len(transactions)
        years_with_tx = sorted(set(t.split("-")[0] for t in transactions["月份"]))

        st.caption(f"共 {tx_count} 笔买入，覆盖 {len(years_with_tx)} 年")

        with st.expander("查看全部交易记录", expanded=False):
            st.dataframe(
                transactions,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "序号": st.column_config.NumberColumn(format="%d"),
                    "买入价": st.column_config.NumberColumn(format="%.4f"),
                    "买入股数": st.column_config.NumberColumn(format="%d"),
                    "买入金额": st.column_config.NumberColumn(format="¥%.2f"),
                },
            )
else:
    # 初始状态：展示说明
    st.info("👈 在左侧设置参数后，点击「开始回测」按钮查看结果。")
    st.markdown(
        """
        ### 策略说明
        - **底仓 + 月定投**：先一次性投入底仓资金，之后每月固定金额买入
        - **整数股交易**：当月资金不足 1 股时，现金累积到下月
        - **数据来源**：东方财富 API（QQQ 前复权日线数据，2001–2026）
        """
    )
