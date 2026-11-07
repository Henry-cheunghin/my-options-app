import os
import re
import json
from datetime import datetime
import pytz
from playwright.sync_api import sync_playwright

# 30 隻主力活躍港股 + 恒指官方代碼對照表
TARGET_MAPPING = {
    "TCH": {"name": "騰訊控股", "code": "0700"},
    "BAB": {"name": "阿里巴巴", "code": "9988"},
    "MET": {"name": "美團", "code": "3690"},
    "MIU": {"name": "小米集團", "code": "1810"},
    "BID": {"name": "百度集團", "code": "9888"},
    "KST": {"name": "快手", "code": "1024"},
    "JDH": {"name": "京東集團", "code": "9618"},
    "NTD": {"name": "網易", "code": "9999"},
    "BYE": {"name": "比亞迪電子", "code": "0285"},
    "KSO": {"name": "金山軟件", "code": "3888"},
    "SMC": {"name": "中芯國際", "code": "0981"},
    "HUA": {"name": "華虹半導體", "code": "1347"},
    "SUN": {"name": "舜宇光學", "code": "2382"},
    "BYD": {"name": "比亞迪股份", "code": "1211"},
    "LIH": {"name": "理想汽車", "code": "2015"},
    "XPE": {"name": "小鵬汽車", "code": "9868"},
    "NIO": {"name": "蔚來", "code": "9866"},
    "HEX": {"name": "香港交易所", "code": "0388"},
    "HKB": {"name": "滙豐控股", "code": "0005"},
    "PAI": {"name": "中國平安", "code": "2318"},
    "CLI": {"name": "中國人壽", "code": "2628"},
    "AIA": {"name": "友邦保險", "code": "1299"},
    "CCB": {"name": "建設銀行", "code": "0939"},
    "ICB": {"name": "工商銀行", "code": "1398"},
    "BCM": {"name": "中國銀行", "code": "3988"},
    "CTH": {"name": "中國移動", "code": "0941"},
    "CNC": {"name": "中國海洋石油", "code": "0883"},
    "PTR": {"name": "中國石油", "code": "0857"}
}

def get_hk_date_str():
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    now = datetime.now(hk_tz)
    return now.strftime('%y%m%d'), now.strftime('%Y-%m-%d'), now.strftime('%b-%y').upper()

def run_scraper():
    date_code, report_date, curr_month_str = get_hk_date_str()
    url_hsio = f"https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/hsio{date_code}.htm"
    url_dmo = f"https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/dmo{date_code}.htm"
    
    payload = {
        "report_date": report_date,
        "source": "HKEX Official Daily Market Report (hsio & dmo)",
        "stocks": {}
    }
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        
        # 1. 解析恒指期權 (hsio)
        try:
            page.goto(url_hsio, timeout=60000, wait_until="domcontentloaded")
            content_hsio = page.content()
            hsi_strikes = []
            in_section = False
            for line in content_hsio.split("\n"):
                if curr_month_str in line:
                    in_section = True
                if in_section and ("TOTAL" in line or "MONTHLY TOTAL" in line):
                    in_section = False
                if in_section:
                    parts = line.split()
                    # 匹配恒指標準格式行
                    if len(parts) >= 7 and parts[0].isdigit() and len(parts[0]) == 5:
                        strike = int(parts[0])
                        # 正確對位倒數及未平倉欄位
                        c_oi = parts[3].replace(',', '') if parts[3] != '-' else '0'
                        p_oi = parts[5].replace(',', '') if parts[5] != '-' else '0'
                        if c_oi.isdigit() and p_oi.isdigit():
                            c_val, p_val = int(c_oi), int(p_oi)
                            if c_val > 0 or p_val > 0:
                                hsi_strikes.append({"strike": strike, "call_oi": c_val, "put_oi": p_val})
                                
            if hsi_strikes:
                payload["stocks"]["恒生指數 (HSI)"] = {
                    "contracts": {
                        f"🇭🇰 即月月期權 ({curr_month_str})": {
                            "expiry_date": curr_month_str,
                            "data": hsi_strikes
                        }
                    }
                }
        except Exception as e:
            print(f"恒指日報解析失敗: {e}")
            
        # 2. 解析股票期權 (dmo)
        try:
            page.goto(url_dmo, timeout=60000, wait_until="domcontentloaded")
            content_dmo = page.content()
            
            for code_key, info in TARGET_MAPPING.items():
                if f" {code_key} " in content_dmo or f"\n{code_key}" in content_dmo:
                    pos = content_dmo.find(code_key)
                    sub_text = content_dmo[pos:pos + 15000]
                    stock_strikes = []
                    
                    for line in sub_text.split("\n"):
                        parts = line.split()
                        # 個股期權行格式校驗
                        if len(parts) >= 6:
                            try:
                                strike = float(parts[0])
                                # 取真實未平倉列 (避免誤取成交量)
                                c_str = parts[-3].replace(',', '') if parts[-3] != '-' else '0'
                                p_str = parts[-1].replace(',', '') if parts[-1] != '-' else '0'
                                if c_str.isdigit() and p_str.isdigit():
                                    c_val, p_val = int(c_str), int(p_str)
                                    if c_val > 0 or p_val > 0:
                                        stock_strikes.append({"strike": strike, "call_oi": c_val, "put_oi": p_val})
                            except:
                                pass
                                
                    if stock_strikes:
                        full_label = f"{info['name']} ({info['code']}.HK)"
                        payload["stocks"][full_label] = {
                            "contracts": {
                                f"🇭🇰 即月期權 ({curr_month_str})": {
                                    "expiry_date": curr_month_str,
                                    "data": stock_strikes
                                }
                            }
                        }
        except Exception as e:
            print(f"個股日報解析失敗: {e}")
            
        browser.close()
        
    if payload["stocks"]:
        with open("hsi_latest.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("✅ 修正後真實 OI 數據已寫入 hsi_latest.json！")

if __name__ == "__main__":
    run_scraper()
