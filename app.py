else:
    st.subheader("🇭🇰 恒生指數 (HSI 即月合約) 港交所官方結算盤面")
    
    if os.path.exists("hsi_latest.json"):
        try:
            with open("hsi_latest.json", "r", encoding="utf-8") as f:
                hkex_payload = json.load(f)
                
            report_date = hkex_payload.get("report_date", "未記錄")
            expiry = hkex_payload.get("expiry", "即月")
            raw_data = hkex_payload.get("data", [])
            
            if raw_data:
                df_hk = pd.DataFrame(raw_data)
                
                # --- 大戶 P&L / 最大痛點演算法 ---
                strikes = df_hk['strike'].tolist()
                pnl_records = []
                for s in strikes:
                    # 計算買方獲利 (即大戶虧損)
                    call_payout = sum([max(0, s - r['strike']) * r['call_oi'] for _, r in df_hk.iterrows()])
                    put_payout = sum([max(0, r['strike'] - s) * r['put_oi'] for _, r in df_hk.iterrows()])
                    total_loss = call_payout + put_payout
                    pnl_records.append({"strike": s, "loss": total_loss})
                
                pnl_df = pd.DataFrame(pnl_records).sort_values(by="loss", ascending=True).reset_index(drop=True)
                top1_settle = pnl_df.iloc[0]['strike']
                top2_settle = pnl_df.iloc[1]['strike']
                
                # 解決頂底同一點的問題：Call 天花板向現價上方尋找最大值
                put_max = df_hk.loc[df_hk['put_oi'].idxmax()]
                # 若 24,000 點是雙向最大，天花板取 24,400 以上的最大 Call (例如 24,800 點)
                high_calls = df_hk[df_hk['strike'] > put_max['strike']]
                call_max = high_calls.loc[high_calls['call_oi'].idxmax()] if not high_calls.empty else df_hk.loc[df_hk['call_oi'].idxmax()]
                
                st.success(f"✅ 港交所官方結算數據 ({expiry}) ｜ 結算日期: {report_date}")
                
                # 4 格直觀大戶攻防與結算推算卡片
                c1, c2 = st.columns(2)
                c1.metric("🥇 第一大機會結算位 (Max Pain)", f"{int(top1_settle):,} 點", "大戶 P&L 最大化")
                c2.metric("🥈 第二大機會結算位 (次級痛點)", f"{int(top2_settle):,} 點", "次級防守點")
                
                c3, c4 = st.columns(2)
                c3.metric("🟢 大戶實質 Call 天花板", f"{int(call_max['strike']):,} 點", f"{int(call_max['call_oi']):,} 張")
                c4.metric("🔴 大戶實質 Put 鋼底", f"{int(put_max['strike']):,} 點", f"{int(put_max['put_oi']):,} 張")
                
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
                # 畫出第一大機會結算位參考線
                fig_hk.add_hline(
                    y=top1_settle, line_dash="dot", line_color="#00FFFF", line_width=2,
                    annotation_text=f"第一推算結算點: {int(top1_settle):,}", annotation_position="bottom right"
                )
                fig_hk.update_layout(
                    title=f"<b>恒指即月期權大戶攻防與結算預測圖 ({expiry})</b>",
                    barmode='relative', template='plotly_dark',
                    xaxis=dict(title='Put 倉 (左) ⟵ ｜ ⟶ Call 倉 (右)', fixedrange=True),
                    yaxis=dict(title='恒指行使價 (點位)', fixedrange=True),
                    height=750
                )
                st.plotly_chart(fig_hk, use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("⚠️ 檔案中暫無有效行使價數據。")
        except Exception as e:
            st.error(f"解析官方數據時出錯: {e}")
    else:
        st.warning("⚠️ 港交所當日結算檔案尚未生成。")
