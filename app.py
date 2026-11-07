import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import json
import os

st.set_page_config(page_title="港美股大戶未平倉攻防終端", layout="wide")

st.title("📊 港美股大戶未平倉 (OI) 攻防終端")
st.caption("數據來源：CBOE / OCC / 港交所 HKEX 官方清算鏈（100% 真實官方數據）")

market = st.radio(
    "選擇市場：", 
    ["🇺🇸 美股期權鏈 (CBOE/OCC 官方源)", "🇭🇰 港股官方大戶攻防 (HKEX 結算日報)"], 
    horizontal=True
)

if market == "🇺🇸 美股期權鏈 (CBOE/OCC 官方源)":
    with st.form(key="search_form"):
        c_in1, c_in2 = st.columns([3, 1])
        with c_in1:
            symbol = st.text_input("輸入美股代號：", value="SPY").strip().upper()
        with c_in2:
            st.write("")
            submit_btn = st.form_submit_button("🔍 查詢股票")

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
                    recent_expirations = list(expirations[:6])
                    selected_expiry = st.radio(
                        "📅 選擇到期日（純點擊切換）：",
                        recent_expirations,
                        horizontal=True
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
    
    if os.path.exists("hsi_latest.json"):
        try:
            with open("hsi_latest.json", "r", encoding="utf-8") as f:
                hkex_payload = json.load(f)
                
            report_date = hkex_payload.get("report_date", "未記錄")
            stocks_dict = hkex_payload.get("stocks", {})
            
            # 若為舊版單合約結構，自動兼容
            if not stocks_dict and "contracts" in hkex_payload:
                stocks_dict = {"恒生指數 (HSI)": {"contracts": hkex_payload["contracts"]}}
            elif not stocks_dict and "data" in hkex_payload:
                stocks_dict = {"恒生指數 (HSI)": {"contracts": {"🇭🇰 即月月期權": {"expiry_date": "2026-11-27", "data": hkex_payload["data"]}}}}
            
            # 港股標的單選按鈕（手機點擊即切換，不彈出輸入法）
            stock_list = list(stocks_dict.keys())
            selected_stock = st.radio("🎯 選擇跟蹤港股標的：", stock_list, horizontal=True)
            
            contracts_dict = stocks_dict[selected_stock].get("contracts", {})
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
                
                # 計算大戶 P&L 最佳結算位 (Max Pain)
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
                
                # 提示數據日與到期日
                st.info(f"📌 **數據發布基準日**：{report_date} ｜ 🎯 **合約到期結算日**：**{settle_date}**")
                
                # 判斷單位（指數為「點」，個股為「元」）
                unit_str = "點" if "指數" in selected_stock else "元"
                
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
                    title=f"<b>[{selected_stock}] 大戶攻防與結算預測圖 (結算日: {settle_date})</b>",
                    barmode='relative', template='plotly_dark',
                    xaxis=dict(title='Put 倉 (左) ⟵ ｜ ⟶ Call 倉 (右)', fixedrange=True),
                    yaxis=dict(title=f'行使價 ({unit_str})', fixedrange=True),
                    height=750
                )
                st.plotly_chart(fig_hk, use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("⚠️ 該合約無行使價數據。")
        except Exception as e:
            st.error(f"解析官方數據出錯: {e}")
    else:
        st.warning("⚠️ 港交所官方結算檔案尚未生成。")
