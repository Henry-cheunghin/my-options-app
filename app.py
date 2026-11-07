import os
import re
import json
import requests
from datetime import datetime
import pytz

def fetch_and_parse_hkex_hsio():
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    now = datetime.now(hk_tz)
    
    # 港交所官方衍生產品結算日報 URL 規則 (hsioYYMMDD.htm)
    # 例如 2026年11月06日: hsio261106.htm
    date_str = now.strftime('%y%m%d')
    url = f"https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/hsio{date_str}.htm"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"正在連線港交所官方源: {url}")
    res = requests.get(url, headers=headers, timeout=20)
    
    if res.status_code != 200:
        print(f"港交所當日結算報表尚未出台或未發布 (HTTP {res.status_code})")
        return None
    
    text = res.text
    
    # 即月合約標籤防呆 (例如 NOV-26)
    curr_month_str = now.strftime('%b-%y').upper()
    print(f"鎖定即月合約月份: {curr_month_str}")
    
    # 解析各 Strike 的 Call OI 與 Put OI
    # 官方格式一般包含: STRIKE, CALL VOL, CALL OI, PUT VOL, PUT OI
    strikes_data = []
    
    # 正則提取標準格式行：行使價 (4-5位數字) 以及後續成交量與未平倉
    lines = text.split('\n')
    in_contract_section = False
    
    for line in lines:
        if curr_month_str in line:
            in_contract_section = True
        if in_contract_section and ("TOTAL" in line or "MONTHLY TOTAL" in line):
            in_contract_section = False
            
        if in_contract_section:
            # 尋找匹配數字行
            # 範例匹配: 24000   12   1,107   51   782
            match = re.search(r'(\d{5})\s+(\d+|-)\s+([\d,]+|-)\s+(\d+|-)\s+([\d,]+|-)', line)
            if match:
                strike = int(match.group(1))
                call_oi = match.group(3).replace(',', '')
                put_oi = match.group(5).replace(',', '')
                
                call_oi = int(call_oi) if call_oi != '-' else 0
                put_oi = int(put_oi) if put_oi != '-' else 0
                
                strikes_data.append({
                    "strike": strike,
                    "call_oi": call_oi,
                    "put_oi": put_oi
                })
                
    if not strikes_data:
        print("未能在官方頁面解析到即月行使價數據")
        return None
        
    output = {
        "report_date": now.strftime('%Y-%m-%d'),
        "source": "HKEX Official Daily Market Report (hsio)",
        "expiry": curr_month_str,
        "data": strikes_data
    }
    
    # 寫入 json 文件保存
    with open("hsi_latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 成功抓取並生成 100% 官方真實恒指未平倉數據，共 {len(strikes_data)} 檔行使價。")
    return True

if __name__ == "__main__":
    fetch_and_parse_hkex_hsio()
