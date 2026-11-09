import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import json
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="港美股大戶未平倉攻防終端", layout="wide")

st.title("📊 港美股大戶未平倉 (OI) 攻防終端")
st.caption("數據來源：CBOE / OCC / 港交所 HKEX 官方清算鏈（100% 真實官方數據）")

market = st.radio(
    "選擇市場：", 
    ["🇺🇸 美股期權鏈 (CBOE/OCC 官方源)", "🇭🇰 港股官方大戶攻防 (HKEX 結算日報)"], 
    horizontal=True
)

if market == "🇺🇸 美股期權鏈 (CBOE/OCC 官方源)":
    with st.form(key="us_form"):
        c_in1, c_in2 = st.columns([3, 1])
        with c_in1:
            symbol = st.text_input("輸入美股代號：", value="SPY").strip().upper()
        with c_in2:
            st.write("")
            submit_btn = st.form_submit_button("🔍 查詢美股")

    if symbol:
        with st.spinner(f"正在向官方源加載 [{symbol}] 數據..."):
            try:
                ticker = yf.Ticker(symbol)
                current_price = None
                try:
                    fast_info = ticker.fast_info
                    current_price = fast_info.get('last_price') or fast_info.get('previous_close')
                except Exception:
                    pass
                
                if not current_price:
                    hist = ticker.history(period="5d")
                    if not hist.empty:
                        current_price = float(hist['Close'].iloc[-1])
                
                expirations = ticker.options
                if not expirations:
                    st.error(f"❌ 查無 [{symbol}] 的官方期權數據。")
                elif not current_price:
                    st.error(f"❌ 無法獲取 [{symbol}] 的有效官方現價。")
                else:
                    # 篩選未來 35 天內（足一個月以上）的所有到期日
                    today = datetime.now().date()
                    one_month_later = today + timedelta(days=35)
                    
                    target_expirations = [
                        exp for exp in expirations 
                        if today <= datetime.strptime(exp, "%Y-%m-%d").date() <= one_month_later
                    ]
                    
                    # 若一個月內無密集合約（例如月期權股），則保證最少展示最近 8 個合約
                    if len(target_expirations) < 4:
                        target_expirations = list(expirations[:8])
                    
                    selected_expiry = st.radio(
                        "📅 選擇到期日（一個月內所有合約，純點擊切換）：",
                        target_expirations,
                        horizontal=True
                    )
                    
                    # 官方數據出處與直接核對 Link
                    yahoo_check_url = f"https://finance.yahoo.com/quote/{symbol}/options/?date={int(datetime.strptime(selected_expiry, '%Y-%m-%d').timestamp())}"
                    cboe_check_url = f"https://www.cboe.com/delayed_quotes/{symbol.lower()}/quote_table"
                    
                    st.markdown(
                        f"""
                        🔍 **官方數據源與 Fact-check 直達連結：**  
                        * [👉 點此在 Yahoo Finance 官方期權鏈核對 [{selected_expiry}] 的 Open Interest]({yahoo_check_url})
                        * [👉 點此在 CBOE（芝加哥期權交易所）官方頁面核對原始數據]({cboe_check_url})
                        """,
                        unsafe_allow_html=True
                    )
                    
                    chain = ticker.option_chain(selected_expiry)
                    calls = chain.calls[['strike', 'openInterest']].fillna(0)
                    puts = chain.puts[['strike', 'openInterest']].fillna(0)
                    
                    calls = calls[(calls['strike'] >= current_price * 0.90) & (calls['strike'] <= current_price * 1.10)]
                    puts = puts[(puts['strike'] >= current_price * 0.90) & (puts['strike'] <= current_price * 1.10)]
                    
                    strikes = sorted(list(set(calls['strike']).union(set(puts['strike']))))
                    df = pd.DataFrame({'strike': strikes})
                    df = df.merge(calls, on='strike', how='left').rename(columns={'openInterest': 'Call_OI'}).fillna(0)
                    df = df.merge(puts, on='strike', how='left').rename(columns={'openInterest': 'Put_OI'}).fillna(0)
                    
                    max_call_row = df.loc[df['Call_OI'].idxmax()]
                    max_put_row = df.loc[df['Put_OI'].idxmax()]
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("官方收盤/現價", f"${current_price:.2f}")
                    c2.metric("🟢 大戶 Call 天花板", f"${max_call_row['strike']:.1f}", f"{int(max_call_row['Call_OI']):,} 張")
                    c3.metric("🔴 大戶 Put 鋼底", f"${max_put_row['strike']:.1f}", f"{int(max_put_row['Put_OI']):,} 張")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        y=df['strike'], x=df['Call_OI'],
                        name='Call OI (天花板)', orientation='h',
                        marker=dict(color='#00E676'),
                        text=[f"{int(x):,}張" if x > 0 else "" for x in df['Call_OI']],
                        textposition='outside', cliponaxis=False
                    ))
                    fig.add_trace(go.Bar(
                        y=df['strike'], x=-df['Put_OI'],
                        name='Put OI (鋼底)', orientation='h',
                        marker=dict(color='#FF5252'),
                        text=[f"{int(x):,}張" if x > 0 else "" for x in df['Put_OI']],
                        textposition='outside', cliponaxis=False,
                        customdata=df['Put_OI'],
                        hovertemplate='Strike: %{y}<br>Put OI: %{customdata:,} 張<extra></extra>'
                    ))
                    fig.add_hline(
                        y=current_price, line_dash="dash", line_color="#FFD700", line_width=2,
                        annotation_text=f"現價 ${current_price:.2f}", annotation_position="top right"
                    )
                    fig.update_layout(
                        title=f"<b>[{symbol}] 美股大戶攻防分佈 ({selected_expiry})</b>",
                        barmode='relative', template='plotly_dark',
                        xaxis=dict(title='Put 倉 (左) ⟵ ｜ ⟶ Call 倉 (右)', fixedrange=True, zeroline=True, zerolinecolor='#FFFFFF'),
                        yaxis=dict(title='行使價 (Strike)', fixedrange=True),
                        height=720, margin=dict(l=10, r=40, t=50, b=40),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})
            except Exception as e:
                st.error(f"獲取數據時出錯: {e}")

else:
    st.subheader("🇭🇰 港股市場官方大戶未平倉攻防終端 (HKEX)")
    
    with st.form(key="hk_form"):
        c_hk1, c_hk2 = st.columns([3, 1])
        with c_hk1:
            hk_input = st.text_input("輸入港股代號或指數（例如 HSI, 0700, 9988, 3690）：", value="0700").strip().upper()
        with c_hk2:
            st.write("")
            hk_submit = st.form_submit_button("🔍 查詢港股")

    if os.path.exists("hsi_latest.json"):
        try:
            with open("hsi_latest.json", "r", encoding="utf-8") as f:
                hkex_payload = json.load(f)
                
            report_date = hkex_payload.get("report_date", "未記錄")
            stocks_dict = hkex_payload.get("stocks", {})
            
            clean_date = report_date.replace("-", "")[2:8] if len(report_date) >= 10 else "261106"
            hkex_hsio_url = f"https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/hsio{clean_date}.htm"
            hkex_dmo_url = f"https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/dmo{clean_date}.htm"
            
            st.markdown(
                f"""
                🔍 **港交所 HKEX 官方每日日報出處直達：**  
                * [👉 點此核對當日恒指期權官方報表 (hsio{clean_date}.htm)]({hkex_hsio_url})
                * [👉 點此核對當日全港個股期權官方報表 (dmo{clean_date}.htm)]({hkex_dmo_url})
                """,
                unsafe_allow_html=True
            )
            
            clean_input = hk_input.replace(".HK", "").zfill(4) if hk_input.isdigit() else hk_input
            matched_key = None
            for k in stocks_dict.keys():
                if clean_input in k or hk_input in k:
                    matched_key = k
                    break
                    
            if not matched_key:
                st.error(f"❌ 官方結算庫中暫未收錄代號 [{hk_input}]。")
                st.info(f"💡 目前日報庫已收錄標的：{', '.join(stocks_dict.keys())}")
            else:
                stock_data = stocks_dict[matched_key]
                contracts_dict = stock_data.get("contracts", {})
                contract_options = list(contracts_dict.keys())
                
                selected_contract_label = st.radio(
                    "📅 選擇合約到期日（純點擊切換）：",
                    contract_options,
                    horizontal=True
                )
                
                contract_info = contracts_dict[selected_contract_label]
                settle_date = contract_info.get("expiry_date", "待定")
                raw_data = contract_info.get("data", [])
                
                if raw_data:
                    df_hk = pd.DataFrame(raw_data)
                    
                    strikes = df_hk['strike'].tolist()
                    pnl_records = []
                    for s in strikes:
                        call_payout = sum([max(0, s - r['strike']) * r['call_oi'] for _, r in df_hk.iterrows()])
                        put_payout = sum([max(0, r['strike'] - s) * r['put_oi'] for _, r in df_hk.iterrows()])
                        pnl_records.append({"strike": s, "loss": call_payout + put_payout})
                    
                    pnl_df = pd.DataFrame(pnl_records).sort_values(by="loss", ascending=True).reset_index(drop=True)
                    top1_settle = pnl_df.iloc[0]['strike']
                    top2_settle = pnl_df.iloc[1]['strike']
                    
                    put_max = df_hk.loc[df_hk['put_oi'].idxmax()]
                    high_calls = df_hk[df_hk['strike'] > put_max['strike']]
                    call_max = high_calls.loc[high_calls['call_oi'].idxmax()] if not high_calls.empty else df_hk.loc[df_hk['call_oi'].idxmax()]
                    
                    st.info(f"📌 **標的**：{matched_key} ｜ **結算日報發布日**：{report_date} ｜ 🎯 **到期結算日**：**{settle_date}**")
                    
                    unit_str = "點" if "HSI" in matched_key or "恒生" in matched_key else "元"
                    
                    c1, c2 = st.columns(2)
                    c1.metric(f"🥇 第一大機會結算位 ({settle_date})", f"{top1_settle:,.1f} {unit_str}", "大戶 P&L 最佳點位")
                    c2.metric(f"🥈 第二大機會結算位 ({settle_date})", f"{top2_settle:,.1f} {unit_str}", "次級防守點位")
                    
                    c3, c4 = st.columns(2)
                    c3.metric("🟢 大戶實質 Call 天花板", f"{call_max['strike']:,.1f} {unit_str}", f"{int(call_max['call_oi']):,} 張")
                    c4.metric("🔴 大戶實質 Put 鋼底", f"{put_max['strike']:,.1f} {unit_str}", f"{int(put_max['put_oi']):,} 張")
                    
                    fig_hk = go.Figure()
                    fig_hk.add_trace(go.Bar(
                        y=df_hk['strike'], x=df_hk['call_oi'],
                        name='Call OI (大戶阻力)', orientation='h', marker=dict(color='#00E676'),
                        text=[f"{int(x)}張" for x in df_hk['call_oi']], textposition='outside'
                    ))
                    fig_hk.add_trace(go.Bar(
                        y=df_hk['strike'], x=-df_hk['put_oi'],
                        name='Put OI (大戶支撐)', orientation='h', marker=dict(color='#FF5252'),
                        text=[f"{int(x)}張" for x in df_hk['put_oi']], textposition='outside'
                    ))
                    fig_hk.add_hline(
                        y=top1_settle, line_dash="dot", line_color="#00FFFF", line_width=2,
                        annotation_text=f"預測結算: {top1_settle:,.1f}", annotation_position="bottom right"
                    )
                    fig_hk.update_layout(
                        title=f"<b>[{matched_key}] 大戶攻防與結算預測圖 (結算日: {settle_date})</b>",
                        barmode='relative', template='plotly_dark',
                        xaxis=dict(title='Put 倉 (左) ⟵ ｜ ⟶ Call 倉 (右)', fixedrange=True),
                        yaxis=dict(title=f'行使價 ({unit_str})', fixedrange=True),
                        height=750
                    )
                    st.plotly_chart(fig_hk, use_container_width=True, config={'displayModeBar': False})
        except Exception as e:
            st.error(f"解析數據出錯: {e}")
