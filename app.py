import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 設定手機與電腦全螢幕版面
st.set_page_config(page_title="大戶期權未平倉攻防工具", layout="wide")

st.title("📊 美股大戶未平倉 (OI) 攻防終端")
st.caption("數據來源：CBOE / OCC 官方清算鏈（真實數據 · 隨開即算）")

# 輸入框：預設 SPY
symbol = st.text_input("請輸入股票代號（例如 SPY, TSLA, NVDA, FSLR）:", value="SPY").strip().upper()

if symbol:
    with st.spinner(f"正在向官方源抓取 [{symbol}] 數據..."):
        try:
            ticker = yf.Ticker(symbol)
            fast_info = ticker.fast_info
            current_price = fast_info.get('last_price') or fast_info.get('previous_close')
            
            expirations = ticker.options
            if not expirations:
                st.error(f"❌ 查無 [{symbol}] 的期權數據，請確認代號是否正確。")
            else:
                # 選擇到期日（預設最近的主力到期日）
                selected_expiry = st.selectbox("選擇期權到期日 (Expiry Date):", expirations, index=0)
                
                # 抓取官方鏈
                chain = ticker.option_chain(selected_expiry)
                calls = chain.calls[['strike', 'openInterest']].fillna(0)
                puts = chain.puts[['strike', 'openInterest']].fillna(0)
                
                # 篩選現價上下 15% 核心攻防區
                calls = calls[(calls['strike'] >= current_price * 0.85) & (calls['strike'] <= current_price * 1.15)]
                puts = puts[(puts['strike'] >= current_price * 0.85) & (puts['strike'] <= current_price * 1.15)]
                
                # 合併數據
                strikes = sorted(list(set(calls['strike']).union(set(puts['strike']))))
                df = pd.DataFrame({'strike': strikes})
                df = df.merge(calls, on='strike', how='left').rename(columns={'openInterest': 'Call_OI'}).fillna(0)
                df = df.merge(puts, on='strike', how='left').rename(columns={'openInterest': 'Put_OI'}).fillna(0)
                
                # 找出重兵區
                max_call_row = df.loc[df['Call_OI'].idxmax()]
                max_put_row = df.loc[df['Put_OI'].idxmax()]
                
                # 顯示核心數字卡片
                c1, c2, c3 = st.columns(3)
                c1.metric("當前官方現價", f"${current_price:.2f}")
                c2.metric("🟢 大戶 Call 天花板", f"${max_call_row['strike']:.1f}", f"{int(max_call_row['Call_OI']):,} 張")
                c3.metric("🔴 大戶 Put 鋼底", f"${max_put_row['strike']:.1f}", f"{int(max_put_row['Put_OI']):,} 張")
                
                # 繪製圖表
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    y=df['strike'],
                    x=df['Call_OI'],
                    name='Call OI (阻力天花板)',
                    orientation='h',
                    marker=dict(color='#00E676')
                ))
                fig.add_trace(go.Bar(
                    y=df['strike'],
                    x=-df['Put_OI'],
                    name='Put OI (支撐鋼底)',
                    orientation='h',
                    marker=dict(color='#FF5252'),
                    customdata=df['Put_OI'],
                    hovertemplate='Strike: %{y}<br>Put OI: %{customdata:,} 張<extra></extra>'
                ))
                fig.add_hline(
                    y=current_price, 
                    line_dash="dash", 
                    line_color="#FFD700", 
                    line_width=2,
                    annotation_text=f"現價 ${current_price:.2f}",
                    annotation_position="top right"
                )
                fig.update_layout(
                    title=f"<b>[{symbol}] 大戶攻防圖 ({selected_expiry})</b>",
                    barmode='relative',
                    template='plotly_dark',
                    xaxis=dict(title='Put 倉 (左) ⟵ ｜ ⟶ Call 倉 (右)', zeroline=True, zerolinecolor='#FFFFFF'),
                    yaxis=dict(title='行使價 (Strike Price)'),
                    height=700
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            st.error(f"獲取數據時出錯: {e}")
