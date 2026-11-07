# 港股切換區塊邏輯（只讀取 100% 官方真實 JSON，無則如實回報）
if market == "🇭🇰 港股官方大戶攻防 (HKEX)":
    import json
    import os
    
    if os.path.exists("hsi_latest.json"):
        with open("hsi_latest.json", "r", encoding="utf-8") as f:
            hkex_payload = json.load(f)
            
        report_date = hkex_payload.get("report_date")
        expiry = hkex_payload.get("expiry")
        df_hk = pd.DataFrame(hkex_payload.get("data", []))
        
        st.success(f"✅ 已載入港交所官方結算報表 ({expiry}) | 結算日期: {report_date}")
        
        # 找出全場合約 Call Wall 與 Put Wall
        max_call = df_hk.loc[df_hk['call_oi'].idxmax()]
        max_put = df_hk.loc[df_hk['put_oi'].idxmax()]
        
        c1, c2 = st.columns(2)
        c1.metric("🟢 港交所官方 Call 天花板", f"{int(max_call['strike']):,} 點", f"{int(max_call['call_oi']):,} 張")
        c2.metric("🔴 港交所官方 Put 鋼底", f"{int(max_put['strike']):,} 點", f"{int(max_put['put_oi']):,} 張")
        
        # 繪製真實圖表
        fig_hk = go.Figure()
        fig_hk.add_trace(go.Bar(
            y=df_hk['strike'], x=df_hk['call_oi'],
            name='Call OI (大戶阻力)', orientation='h', marker=dict(color='#00E676'),
            text=[f"{int(x)}張" if x > 500 else "" for x in df_hk['call_oi']],
            textposition='outside'
        ))
        fig_hk.add_trace(go.Bar(
            y=df_hk['strike'], x=-df_hk['put_oi'],
            name='Put OI (大戶支撐)', orientation='h', marker=dict(color='#FF5252'),
            text=[f"{int(x)}張" if x > 500 else "" for x in df_hk['put_oi']],
            textposition='outside'
        ))
        fig_hk.update_layout(
            title=f"<b>恒指即月期權港交所官方大戶攻防圖 ({expiry})</b>",
            barmode='relative', template='plotly_dark',
            xaxis=dict(title='Put 倉 (左) ⟵ ｜ ⟶ Call 倉 (右)', fixedrange=True),
            yaxis=dict(title='恒指行使價 (點位)', fixedrange=True), height=750
        )
        st.plotly_chart(fig_hk, use_container_width=True, config={'displayModeBar': False})
    else:
        st.warning("⚠️ 港交所當日結算文字報表尚未出台或未同步，無官方數據。")
