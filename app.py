import streamlit as st
import anthropic
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import re

# ── Configuração da página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Monitor de Ativos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS customizado ─────────────────────────────────────────────────────────
st.markdown("""
<style>
  .metric-card {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 16px;
    border: 1px solid #e9ecef;
    margin-bottom: 8px;
  }
  .positive { color: #1D9E75; font-weight: 600; }
  .negative { color: #D85A30; font-weight: 600; }
  .ai-box {
    background: #f0f4ff;
    border-left: 3px solid #534AB7;
    border-radius: 6px;
    padding: 12px 16px;
    margin-top: 8px;
    font-size: 14px;
    color: #333;
  }
  .stTabs [data-baseweb="tab-list"] { gap: 8px; }
  .stTabs [data-baseweb="tab"] { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Monitor de Ativos")
    st.caption("Powered by Claude AI")
    st.divider()

    api_key = st.text_input(
        "🔑 Chave da API Anthropic",
        type="password",
        placeholder="sk-ant-...",
        help="Obtenha em console.anthropic.com"
    )

    st.divider()
    st.subheader("Minha Watchlist")

    # Watchlist padrão
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = {
            "Ações BR":  ["PETR4.SA", "VALE3.SA", "ITUB4.SA"],
            "FIIs":      ["MXRF11.SA", "HGLG11.SA"],
            "Ações EUA": ["AAPL", "MSFT", "NVDA"],
            "ETFs/BDRs": ["BOVA11.SA", "IVVB11.SA"],
            "Cripto":    ["BTC-USD", "ETH-USD"],
        }

    for categoria, tickers in st.session_state.watchlist.items():
        with st.expander(categoria, expanded=False):
            for t in tickers:
                c1, c2 = st.columns([4, 1])
                c1.write(t)
                if c2.button("✕", key=f"rm_{t}", help="Remover"):
                    st.session_state.watchlist[categoria].remove(t)
                    st.rerun()

    st.divider()
    st.subheader("Adicionar ativo")
    cat_options = list(st.session_state.watchlist.keys())
    new_ticker = st.text_input("Ticker", placeholder="Ex: MGLU3.SA").upper().strip()
    new_cat = st.selectbox("Categoria", cat_options)
    if st.button("➕ Adicionar", use_container_width=True):
        if new_ticker and new_ticker not in st.session_state.watchlist[new_cat]:
            st.session_state.watchlist[new_cat].append(new_ticker)
            st.success(f"{new_ticker} adicionado!")
            st.rerun()

# ── Funções auxiliares ───────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_quote(ticker: str):
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        hist = t.history(period="1d", interval="5m")
        price = info.last_price or 0
        prev  = info.previous_close or price
        chg   = ((price - prev) / prev * 100) if prev else 0
        return {
            "ticker":  ticker,
            "price":   price,
            "change":  chg,
            "high":    info.day_high or 0,
            "low":     info.day_low or 0,
            "volume":  info.three_month_average_volume or 0,
            "hist":    hist,
        }
    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_history(ticker: str, period: str):
    try:
        return yf.Ticker(ticker).history(period=period)
    except Exception:
        return pd.DataFrame()


def get_ai_analysis(ticker: str, price: float, change: float, api_key: str) -> str:
    if not api_key:
        return "⚠️ Insira a chave da API Anthropic na barra lateral para receber análises com IA."
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    f"Analise o ativo {ticker} em 2-3 frases curtas e objetivas. "
                    f"Preço atual: {price:.2f}, variação hoje: {change:+.2f}%. "
                    "Comente sobre desempenho recente, contexto macro relevante e perspectiva de curto prazo. "
                    "Responda em português, sem markdown."
                )
            }]
        )
        return resp.content[0].text
    except Exception as e:
        return f"Erro na análise: {e}"


def price_color(chg: float):
    return "positive" if chg >= 0 else "negative"


def fmt_price(ticker: str, price: float) -> str:
    prefix = "R$" if ticker.endswith(".SA") else ("$" if not ticker.endswith("-USD") else "$")
    return f"{prefix} {price:,.2f}"


# ── Layout principal ─────────────────────────────────────────────────────────
all_tickers = [t for tickers in st.session_state.watchlist.values() for t in tickers]
tab_names   = ["Visão Geral"] + list(st.session_state.watchlist.keys())
tabs        = st.tabs(tab_names)

# ── Tab: Visão Geral ─────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("Resumo do portfólio")

    if not all_tickers:
        st.info("Adicione ativos na barra lateral para começar.")
    else:
        cols = st.columns(min(len(all_tickers), 4))
        quotes = {}
        for i, ticker in enumerate(all_tickers):
            q = get_quote(ticker)
            quotes[ticker] = q
            col = cols[i % 4]
            if q:
                color = price_color(q["change"])
                col.metric(
                    label=ticker,
                    value=fmt_price(ticker, q["price"]),
                    delta=f"{q['change']:+.2f}%",
                )
            else:
                col.metric(label=ticker, value="—", delta="Erro")

        st.divider()

        # Mini-gráfico de variação do dia
        st.subheader("Variação no dia (%)")
        valid = [(t, q["change"]) for t, q in quotes.items() if q]
        if valid:
            df_chg = pd.DataFrame(valid, columns=["Ticker", "Variação (%)"])
            df_chg = df_chg.sort_values("Variação (%)", ascending=True)
            colors = ["#D85A30" if v < 0 else "#1D9E75" for v in df_chg["Variação (%)"]]
            fig = go.Figure(go.Bar(
                x=df_chg["Variação (%)"],
                y=df_chg["Ticker"],
                orientation="h",
                marker_color=colors,
                text=[f"{v:+.2f}%" for v in df_chg["Variação (%)"]],
                textposition="outside",
            ))
            fig.update_layout(
                height=max(250, len(valid) * 40),
                margin=dict(l=10, r=60, t=10, b=10),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, zeroline=True, zerolinecolor="#ccc"),
                yaxis=dict(showgrid=False),
            )
            st.plotly_chart(fig, use_container_width=True)

# ── Tabs por categoria ───────────────────────────────────────────────────────
for idx, (categoria, tickers) in enumerate(st.session_state.watchlist.items()):
    with tabs[idx + 1]:
        st.subheader(categoria)

        if not tickers:
            st.info("Nenhum ativo nesta categoria.")
            continue

        periodo = st.selectbox(
            "Período do gráfico",
            ["5d", "1mo", "3mo", "6mo", "1y", "2y"],
            index=2,
            key=f"period_{categoria}",
            format_func=lambda x: {
                "5d": "5 dias", "1mo": "1 mês", "3mo": "3 meses",
                "6mo": "6 meses", "1y": "1 ano", "2y": "2 anos"
            }[x]
        )

        selected_ticker = st.selectbox(
            "Selecionar ativo para análise detalhada",
            tickers,
            key=f"sel_{categoria}"
        )

        q = get_quote(selected_ticker)

        if q:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço atual",  fmt_price(selected_ticker, q["price"]))
            c2.metric("Variação hoje", f"{q['change']:+.2f}%")
            c3.metric("Máxima do dia", fmt_price(selected_ticker, q["high"]))
            c4.metric("Mínima do dia", fmt_price(selected_ticker, q["low"]))

            # Gráfico histórico
            hist = get_history(selected_ticker, periodo)
            if not hist.empty:
                fig2 = go.Figure()
                fig2.add_trace(go.Candlestick(
                    x=hist.index,
                    open=hist["Open"], high=hist["High"],
                    low=hist["Low"],   close=hist["Close"],
                    increasing_line_color="#1D9E75",
                    decreasing_line_color="#D85A30",
                    name=selected_ticker,
                ))
                fig2.add_trace(go.Bar(
                    x=hist.index, y=hist["Volume"],
                    name="Volume",
                    yaxis="y2",
                    marker_color="rgba(83,74,183,0.25)",
                    showlegend=False,
                ))
                fig2.update_layout(
                    height=420,
                    margin=dict(l=10, r=10, t=10, b=10),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    xaxis_rangeslider_visible=False,
                    yaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
                    yaxis2=dict(overlaying="y", side="right", showgrid=False, showticklabels=False),
                    legend=dict(orientation="h", y=1.02),
                )
                st.plotly_chart(fig2, use_container_width=True)

            # Análise de IA
            st.markdown("**Análise com IA**")
            with st.spinner("Analisando com Claude..."):
                analysis = get_ai_analysis(selected_ticker, q["price"], q["change"], api_key)
            st.markdown(f'<div class="ai-box">{analysis}</div>', unsafe_allow_html=True)

            # Linha do tempo intraday
            if not q["hist"].empty:
                st.markdown("**Intraday (hoje)**")
                fig3 = px.area(
                    q["hist"], y="Close",
                    color_discrete_sequence=["#534AB7"],
                )
                fig3.update_layout(
                    height=180,
                    margin=dict(l=10, r=10, t=10, b=10),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
                )
                st.plotly_chart(fig3, use_container_width=True)

        else:
            st.warning(f"Não foi possível obter dados para {selected_ticker}. Verifique o ticker.")

        # Tabela resumo da categoria
        st.divider()
        st.markdown("**Resumo da categoria**")
        rows = []
        for t in tickers:
            qq = get_quote(t)
            if qq:
                rows.append({
                    "Ticker":    t,
                    "Preço":     f"{qq['price']:,.2f}",
                    "Var. (%)":  f"{qq['change']:+.2f}%",
                    "Máx.":      f"{qq['high']:,.2f}",
                    "Mín.":      f"{qq['low']:,.2f}",
                })
        if rows:
            df_cat = pd.DataFrame(rows)
            st.dataframe(df_cat, use_container_width=True, hide_index=True)
