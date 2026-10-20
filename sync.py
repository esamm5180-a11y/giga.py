import os
import time
import requests

WE_USER = os.environ.get("WE_USER")
WE_PASS = os.environ.get("WE_PASS")
FIREBASE_URL = "https://my-net-tracker-default-rtdb.firebaseio.com/net_tracker_data.json"

def fetch_we_data():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json"
    }
    
    # تسجيل الدخول
    login_url = "https://api-my.te.eg/api/user/login"
    login_body = {
        "header": {"customerId": ""},
        "body": {"password": WE_PASS, "userName": WE_USER}
    }
    
    try:
        r = session.post(login_url, json=login_body, headers=headers)
        res = r.json()
        token = res.get("body", {}).get("jwtToken")
        if not token:
            print("خطأ في بيانات تسجيل دخول WE! تأكد من صحة WE_USER و WE_PASS في Secrets.")
            return None
        
        headers["Jwt"] = token
        
        # جلب قائمة الخطوط
        acc_url = "https://api-my.te.eg/api/user/accounts"
        acc_res = session.get(acc_url, headers=headers).json()
        accounts = acc_res.get("body", {}).get("detailedAccounts", [])
        
        lines_balance = {}
        for acc in accounts:
            srv = acc.get("serviceNumber")
            u_url = f"https://api-my.te.eg/api/line/usage?serviceNumber={srv}"
            u_data = session.get(u_url, headers=headers).json()
            rem = u_data.get("body", {}).get("remainingBalance", 0)
            lines_balance[str(srv)] = float(rem)
            
        return lines_balance
    except Exception as e:
        print("خطأ أثناء الاتصال بـ WE:", e)
        return None

def update_firebase(balances):
    if not balances:
        return
    try:
        r = requests.get(FIREBASE_URL)
        lines = r.json()
        if not lines or not isinstance(lines, list):
            print("قاعدة البيانات فارغة أو غير مرتبة كمصفوفة.")
            return
            
        now_ts = int(time.time() * 1000)
        updated = 0
        
        for item in lines:
            target_num = str(item.get("weServiceNumber") or item.get("name") or "").strip()
            for we_num, gb in balances.items():
                if we_num.endswith(target_num[-6:]) or target_num.endswith(we_num[-6:]):
                    item["baseBalance"] = gb
                    item["lastSyncTime"] = now_ts
                    updated += 1
                    print(f"تم تحديث {item.get('name')} إلى: {gb} GB")
                    break
                    
        requests.put(FIREBASE_URL, json=lines)
        print(f"تم بنجاح تحديث {updated} خط في Firebase!")
    except Exception as e:
        print("خطأ في Firebase:", e)

if __name__ == "__main__":
    bals = fetch_we_data()
    if bals:
        update_firebase(bals)
