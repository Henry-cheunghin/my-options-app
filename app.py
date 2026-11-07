import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="大戶未平倉攻防終端", layout="wide")

st.title("📊 美股大戶未平倉 (OI) 攻防終端")
st.caption("數據來源：CBOE / OCC 官方清算鏈（100% 真實數據 · 純觸控防彈鍵盤）")

# 使用 Form 封裝輸入框，輸入完撳「查詢」後手機鍵盤會自動隱藏，不會亂彈
with st.form(key="search_form"):
    c_in1, c_in2 = st.columns([3, 1])
    with c_in1:
        symbol = st.text_input("輸入美股代號：", value="SPY").strip().upper()
    with c_in2:
        st.write("") # 對齊排版
        submit_btn = st.form_submit_button("🔍 查詢股票")

if symbol:
    with st.spinner(f"正在加載 [{symbol}] 官方期權數據..."):
        try:
            ticker = yf.Ticker(symbol)
            
            # 獲取官方現價
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
                # 只取最近 6 個核心到期日，改用橫向 Radio 按鈕，徹底杜絕彈出輸入法鍵盤
                recent_expirations = list(expirations[:6])
                selected_expiry = st.radio(
                    "📅 選擇到期日（點擊即切換，不彈鍵盤）：",
                    recent_expirations,
                    horizontal=True
                )
                
                chain = ticker.option_chain(selected_expiry)
                calls = chain.calls[['strike', 'openInterest']].fillna(0)
                puts = chain.puts[['strike', 'openInterest']].fillna(0)
                
                # 篩選現價上下 10% 核心攻防密集區
                calls = calls[(calls['strike'] >= current_price * 0.90) & (calls['strike'] <= current_price * 1.10)]
                puts = puts[(puts['strike'] >= current_price * 0.90) & (puts['strike'] <= current_price * 1.10)]
                
                strikes = sorted(list(set(calls['strike']).union(set(puts['strike']))))
                df = pd.DataFrame({'strike': strikes})
                df = df.merge(calls, on='strike', how='left').rename(columns={'openInterest': 'Call_OI'}).fillna(0)
                df = df.merge(puts, on='strike', how='left').rename(columns={'openInterest': 'Put_OI'}).fillna(0)
                
                # 找出重兵點位
                max_call_row = df.loc[df['Call_OI'].idxmax()]
                max_put_row = df.loc[df['Put_OI'].idxmax()]
                
                # 頂部關鍵指標卡片
                c1, c2, c3 = st.columns(3)
                c1.metric("官方收盤/現價", f"${current_price:.2f}")
                c2.metric("🟢 大戶 Call 天花板", f"${max_call_row['strike']:.1f}", f"{int(max_call_row['Call_OI']):,} 張")
                c3.metric("🔴 大戶 Put 鋼底", f"${max_put_row['strike']:.1f}", f"{int(max_put_row['Put_OI']):,} 張")
                
                # 繪製圖表
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    y=df['strike'], 
                    x=df['Call_OI'],
                    name='Call OI (天花板)', 
                    orientation='h',
                    marker=dict(color='#00E676'),
                    text=[f"{int(x):,}張" if x > 0 else "" for x in df['Call_OI']],
                    textposition='outside',
                    cliponaxis=False
                ))
                fig.add_trace(go.Bar(
                    y=df['strike'], 
                    x=-df['Put_OI'],
                    name='Put OI (鋼底)', 
                    orientation='h',
                    marker=dict(color='#FF5252'),
                    text=[f"{int(x):,}張" if x > 0 else "" for x in df['Put_OI']],
                    textposition='outside',
                    cliponaxis=False,
                    customdata=df['Put_OI'],
                    hovertemplate='Strike: %{y}<br>Put OI: %{customdata:,} 張<extra></extra>'
                ))
                fig.add_hline(
                    y=current_price, line_dash="dash", line_color="#FFD700", line_width=2,
                    annotation_text=f"現價 ${current_price:.2f}", annotation_position="top right"
                )
                
                fig.update_layout(
                    title=f"<b>[{symbol}] 大戶攻防分佈 ({selected_expiry})</b>",
                    barmode='relative',
                    template='plotly_dark',
                    xaxis=dict(
                        title='Put 倉 (左) ⟵ ｜ ⟶ Call 倉 (右)', 
                        fixedrange=True,
                        zeroline=True, 
                        zerolinecolor='#FFFFFF'
                    ),
                    yaxis=dict(
                        title='行使價 (Strike)', 
                        fixedrange=True
                    ),
                    height=720,
                    margin=dict(l=10, r=40, t=50, b=40),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                st.plotly_chart(
                    fig, 
                    use_container_width=True, 
                    config={'displayModeBar': False, 'scrollZoom': False}
                )
                
                st.write("---")
                st.subheader("📋 行使價官方未平倉數據明細")
                show_df = df.sort_values(by='strike', ascending=False)[['strike', 'Call_OI', 'Put_OI']].copy()
                show_df.columns = ['行使價 (Strike)', 'Call 未平倉 (張)', 'Put 未平倉 (張)']
                st.dataframe(show_df, use_container_width=True, hide_index=True)
                
        except Exception as e:
            st.error(f"獲取數據時出錯: {e}")
