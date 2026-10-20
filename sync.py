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
    
    # 1. تسجيل الدخول
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
            print("خطأ في تسجيل دخول WE! تأكد من بيانات الحساب.")
            return None
        
        headers["Jwt"] = token
        
        # 2. جلب جميع حسابات الخطوط
        acc_url = "https://api-my.te.eg/api/user/accounts"
        acc_res = session.get(acc_url, headers=headers).json()
        accounts = acc_res.get("body", {}).get("detailedAccounts", [])
        
        lines_balance = {}
        for acc in accounts:
            srv = str(acc.get("serviceNumber", "")).strip()
            if not srv:
                continue
            
            # جلب تفاصيل الاستهلاك الدقيقة للخط
            u_url = f"https://api-my.te.eg/api/line/usage?serviceNumber={srv}"
            u_data = session.get(u_url, headers=headers).json()
            body_data = u_data.get("body", {})
            
            # فحص الباقات (الأساسية والإضافية) وجمع المتبقي بدقة
            total_remaining_gb = 0.0
            found_summary = False
            
            # فحص إذا كان هناك ملخص مباشر
            if "detailedLineUsageSummary" in body_data:
                summary = body_data.get("detailedLineUsageSummary", {})
                rem_mb = summary.get("freeAmount") or summary.get("remainingAmount")
                if rem_mb is not None:
                    rem_float = float(rem_mb)
                    if rem_float > 50000:  # إذا كانت القيمة بالميجابايت
                        total_remaining_gb = rem_float / 1024.0
                    else:
                        total_remaining_gb = rem_float
                    found_summary = True

            # إذا لم نجد ملخصاً مباشراً، نقرأ من مصفوفة مجموعات الباقات
            if not found_summary and "usageDetailsUnits" in body_data:
                units = body_data.get("usageDetailsUnits", [])
                for u in units:
                    rem = float(u.get("remaining", 0) or u.get("freeAmount", 0) or 0)
                    if rem > 0:
                        if rem > 50000:
                            total_remaining_gb += (rem / 1024.0)
                        else:
                            total_remaining_gb += rem
                found_summary = True

            # في حال وجود رقم عام direct balance
            if not found_summary:
                direct_rem = float(body_data.get("remainingBalance", 0) or 0)
                if direct_rem > 50000:
                    total_remaining_gb = direct_rem / 1024.0
                else:
                    total_remaining_gb = direct_rem

            lines_balance[srv] = round(total_remaining_gb, 2)
            print(f"الخط {srv} القراءة المسحوبة من WE: {lines_balance[srv]} GB")
            
        return lines_balance
    except Exception as e:
        print("خطأ أثناء الاتصال بـ WE:", e)
        return None

def update_firebase(balances):
    if not balances:
        print("لا توجد أرصدة صالحة تم جلبها من WE.")
        return
        
    try:
        r = requests.get(FIREBASE_URL)
        lines = r.json()
        if not lines or not isinstance(lines, list):
            print("قاعدة البيانات فارغة أو غير مرتبة.")
            return
            
        now_ts = int(time.time() * 1000)
        updated = 0
        
        for item in lines:
            target_num = str(item.get("weServiceNumber") or item.get("name") or "").strip()
            target_clean = "".join(filter(str.isdigit, target_num))
            
            for we_num, gb in balances.items():
                we_clean = "".join(filter(str.isdigit, we_num))
                # مطابقة الأرقام (سواء كاملة أو آخر 6 أرقام)
                if we_clean == target_clean or (len(target_clean) >= 6 and we_clean.endswith(target_clean[-6:])):
                    item["baseBalance"] = gb
                    item["lastSyncTime"] = now_ts
                    updated += 1
                    print(f"✅ تم تحديث الخط [{item.get('name')}] في السيرفر إلى: {gb} GB")
                    break
                    
        requests.put(FIREBASE_URL, json=lines)
        print(f"اكتملت المزامنة بنجاح: تم تحديث {updated} خط في Firebase.")
    except Exception as e:
        print("خطأ في تحديث Firebase:", e)

if __name__ == "__main__":
    bals = fetch_we_data()
    if bals:
        update_firebase(bals)
