Import os
import random
import re
import string
import time
import threading
import json
import requests
from urllib.parse import quote
from telebot import types
import telebot
from supabase import create_client, Client

# ==========================================
# 1. إعدادات البوت والـ API والمسؤولين
# ==========================================
TOKEN = '8886482040:AAEzImc8dOE0ZBbsBD7mxpr5mcWaYDItyNc'
bot = telebot.TeleBot(TOKEN)

ADMIN_ID = 8758665082
SUPPORT_LINK = 'https://t.me/ppppp5e'
SUPPORT_USER = '@ppppp5e'
PROOFS_CHANNEL = "@almohlgm"
RECEIVER_PHONE = "07716465605"

CHANNELS = ["@almohlgm"]
CHANNEL_LINKS = ["https://t.me/almohlgm"]

API_URL = "https://darkfollow.shop/api/v2"
API_KEY = "Ig1FjwBweH3inDwnjLvv7Dt1ZzVRoKKNMF7QysS9UT0sSINTUKmWYdohsm3U"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://iwkszjsggdddiaotlzrk.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6lml3a3N6anNnZ2RkZGlhb3RsenJrIxlsa2UiOiJzZXJ2aWNlX3JvbGUiLCJpYXQiOjE3ODQ3MjIxMjQsImV4cCI6MjEwMDI5ODEyNH0.AbTTagJYFUbntAsUSTZtmdfcUUVFOC24ynWDXdo-ExM")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

user_click_tracker = {}
pending_orders_cache = {}  
transfer_cache = {}        
user_carts = {}            
maintenance_items = set()  
temp_add_service = {}      
admin_states = {}          
user_recharge_states = {} 
temp_recharge_phone_states = {} 

PROFIT_MARGIN_USD = 0.5    
try:
    supabase.table("users").update({"is_banned": 0}).eq("user_id", 8758665082).execute()
except Exception:
    pass

def check_spam(user_id):
    if user_id == ADMIN_ID: return False
    now = time.time()
    user_click_tracker.setdefault(user_id, [])
    user_click_tracker[user_id] = [t for t in user_click_tracker[user_id] if now - t < 3]
    user_click_tracker[user_id].append(now)
    if len(user_click_tracker[user_id]) > 5:
        try:
            supabase.table("users").update({"is_banned": 1}).eq("user_id", user_id).execute()
            bot.send_message(user_id, "❌ **تم حظرك تلقائياً بسبب السبام!**", parse_mode="Markdown")
        except Exception: pass
        return True
    return False

def get_http_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'https://darkfollow.shop',
        'Referer': 'https://darkfollow.shop/'
    })
    return session

def send_to_api(service_id, link, quantity):
    try:
        payload = {
            'key': API_KEY,
            'action': 'add',
            'service': str(service_id),
            'link': str(link),
            'quantity': str(quantity)
        }
        session = get_http_session()
        response = session.post(API_URL, data=payload, timeout=20)
        res_json = response.json()
        if "error" in res_json:
            return {"error": res_json["error"]}
        if "order" in res_json:
            return res_json
        return {"error": f"رد غير متوقع من السيرفر ({response.status_code}): {response.text[:100]}"}
    except Exception as e:
        return {"error": f"فشل الاتصال: {str(e)}"}

def get_status(order_id):
    try:
        session = get_http_session()
        payload = {'key': API_KEY, 'action': 'status', 'order': str(order_id)}
        response = session.post(API_URL, data=payload, timeout=15)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def get_api_balance():
    try:
        session = get_http_session()
        payload = {'key': API_KEY, 'action': 'balance'}
        response = session.post(API_URL, data=payload, timeout=15)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def sync_prices_from_api_logic():
    try:
        session = get_http_session()
        payload = {'key': API_KEY, 'action': 'services'}
        response = session.post(API_URL, data=payload, timeout=20)
        api_services = response.json()
        
        if isinstance(api_services, list):
            updated_count = 0
            for srv in api_services:
                s_id = srv.get('service')
                base_rate = float(srv.get('rate', 0))
                new_calculated_price = round(base_rate + PROFIT_MARGIN_USD, 2)
                
                for k, v in SERVICES.items():
                    if str(v.get('service_id')) == str(s_id):
                        v['price'] = new_calculated_price
                        updated_count += 1
            return True, updated_count
        return False, 0
    except Exception as e:
        return False, str(e)

def validate_service_link(service_category, link):
    link_lower = link.lower()
    if not link.startswith('http') and service_category != 'cat_games':
        return False, "⚠️ الرابط المدخل غير صحيح! يجب أن يبدأ الرابط بـ https://"
    if service_category == 'cat_insta':
        if 'instagram.com' not in link_lower:
            return False, "❌ عذراً، هذا القسم خاص بالانستغرام فقط! يرجى إرسال رابط صحيح."
    elif service_category == 'cat_telegram':
        if 't.me/' not in link_lower and not link_lower.startswith('@'):
            return False, "❌ عذراً، هذا القسم خاص بالتليجرام فقط! يرجى إرسال رابط قناة أو مجموعة صحيح."
    elif service_category == 'cat_games':
        if len(link.strip()) < 3:
            return False, "❌ الآيدي المدخل قصير جداً أو غير صالح!"
    return True, "صالح"

def check_order_live_status(order_id, api_order_id):
    if str(api_order_id) == "0" or not str(api_order_id).isdigit():
        return "📦 الطلب يدوي / قيد المعالجة من قبل الدعم."
    res_status = get_status(api_order_id)
    if res_status and 'status' in res_status:
        st = res_status['status']
        rem = res_status.get('remains', 'غير محدد')
        start_cnt = res_status.get('start_count', 'غير محدد')
        return f"📌 الحالة بالمزود: <b>{st}</b>\n📉 العدد المتبقي: `{rem}`\n📊 العدد الابتدائي: `{start_cnt}`"
    return "⚠️ متعذر جلب الحالة من المزود حالياً."

def get_user(user_id):
    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as e:
        print(f"Error fetching user: {e}")
        return None

def find_user_by_id_or_username(query_str):
    clean_query = str(query_str).strip().replace('@', '').lower()
    try:
        res = supabase.table("users").select("*").or_(f"user_id.eq.{clean_query},username.ilike.%{clean_query}%").execute()
        if res.data:
            return res.data[0]
        res_like = supabase.table("users").select("*").ilike("username", f"%{clean_query}%").execute()
        if res_like.data:
            return res_like.data[0]
    except Exception as e:
        print(f"Search user error: {e}")
    return None

def get_points(user_id):
    u = get_user(user_id)
    return round(float(u['points']), 2) if u and 'points' in u and u['points'] is not None else 0.0

def update_points(user_id, amount, is_recharge=False):
    u = get_user(user_id)
    if u:
        current = float(u['points']) if 'points' in u and u['points'] is not None else 0.0
        new_points = round(current + float(amount), 2)
        update_data = {"points": new_points}
        if is_recharge and amount > 0:
            old_recharged = float(u.get('total_recharged', 0.0) or 0.0)
            update_data["total_recharged"] = round(old_recharged + float(amount), 2)
        supabase.table("users").update(update_data).eq("user_id", user_id).execute()
    else:
        new_points = max(0.0, float(amount))
        data = {"user_id": user_id, "points": new_points}
        if is_recharge and amount > 0:
            data["total_recharged"] = float(amount)
        supabase.table("users").insert(data).execute()

def is_banned(user_id):
    u = get_user(user_id)
    return bool(u.get('is_banned', 0)) if u else False

def is_maintenance():
    try:
        res = supabase.table("settings").select("val").eq("key", "maintenance").execute()
        if res.data:
            return bool(res.data[0]['val'])
        return False
    except Exception:
        return False

def toggle_maintenance():
    curr = is_maintenance()
    new_val = 0 if curr else 1
    try:
        supabase.table("settings").upsert({"key": "maintenance", "val": new_val}).execute()
    except Exception as e:
        print(f"Error toggling maintenance: {e}")
    return new_val

def is_item_in_maintenance(item_key):
    return item_key in maintenance_items

def toggle_item_maintenance(item_key):
    if item_key in maintenance_items:
        maintenance_items.remove(item_key)
        return False
    else:
        maintenance_items.add(item_key)
        return True

def get_menu_description(menu_key, default_text=""):
    try:
        res = supabase.table("settings").select("val_text").eq("key", f"desc_{menu_key}").execute()
        if res.data and res.data[0].get('val_text'):
            txt = str(res.data[0]['val_text']).strip()
            if txt:
                return txt
    except Exception as e:
        print(f"Get description error: {e}")
    return default_text

def set_menu_description(menu_key, text):
    try:
        supabase.table("settings").upsert({"key": f"desc_{menu_key}", "val_text": str(text).strip()}).execute()
    except Exception as e:
        print(f"Error setting description: {e}")

def get_user_level(user_id):
    u = get_user(user_id)
    if u and u.get('is_reseller') == 1:
        return {"title": "🕶️ وكيل معتمد", "discount": 0.08}
    spent = float(u['total_spent']) if u and 'total_spent' in u and u['total_spent'] else 0.0
    if spent >= 300: return {"title": "🏆 VIP", "discount": 0.05}
    elif spent >= 200: return {"title": "💎 تاجر محترف", "discount": 0.04}
    elif spent >= 150: return {"title": "🥇 تاجر جيد", "discount": 0.03}
    elif spent >= 100: return {"title": "🥈 تاجر", "discount": 0.02}
    elif spent >= 50: return {"title": "🥉 تاجر مبتدئ", "discount": 0.01}
    else: return {"title": "👤 مستخدم عادي", "discount": 0.0}

def get_service_price(user_id, base_price):
    level_info = get_user_level(user_id)
    discount = level_info['discount']
    return round(base_price * (1 - discount), 2)

def promote_user_to_reseller(admin_id, target_uid):
    if admin_id != ADMIN_ID:
        return
    try:
        supabase.table("users").update({"is_reseller": 1}).eq("user_id", target_uid).execute()
        bot.send_message(admin_id, f"✅ تم ترقية المستخدم (`{target_uid}`) إلى رتبة وكيل معتمد بنجاح!")
        bot.send_message(target_uid, "🏆 **مبروك! تم ترقية حسابك إلى رتبة (وكيل معتمد) في البوت وتحصل الآن على تخفيضات إضافية ضخمة على جميع الخدمات!**", parse_mode="Markdown")
    except Exception as e:
        print(f"Error promoting reseller: {e}")

def get_next_order_id():
    try:
        res = supabase.table("orders").select("last_id").eq("id", 1).execute()
        if res.data:
            next_id = res.data[0]['last_id'] + 1
            supabase.table("orders").update({"last_id": next_id}).eq("id", 1).execute()
            return next_id
        else:
            supabase.table("orders").insert({"id": 1, "last_id": 100}).execute()
            return 100
    except Exception:
        return int(time.time())

def save_order(order_id, user_id, username, service, price, api_order_id="0", link="خدمة مباشرة", service_id=0, qty=1):
    try:
        supabase.table("user_orders").insert({
            "order_id": order_id,
            "api_order_id": str(api_order_id),
            "user_id": user_id,
            "username": username,
            "service": service,
            "price": price,
            "link": link,
            "service_id": service_id,
            "quantity": qty,
            "status": "قيد التنفيذ",
            "created_at_ts": int(time.time())
        }).execute()
        
        u = get_user(user_id)
        if u:
            old_spent = float(u.get('total_spent', 0)) if u.get('total_spent') is not None else 0.0
            new_spent = old_spent + float(price)
            supabase.table("users").update({"total_spent": new_spent, "last_order_ts": int(time.time())}).eq("user_id", user_id).execute()
    except Exception as e:
        print(f"Error saving order: {e}")

# ==========================================
# 4. قاموس الخدمات الشامل
# ==========================================
SERVICES = {
    'flash_fol_1k': {'name': 'فلاش متابعين 1k', 'btn_label': '1k', 'price': 2.0, 'cost': 1.0, 'service_id': 2051, 'qty': 1000, 'category': 'cat_insta', 'msg': 'أرسل رابط حسابك:'},
    'flash_fol_2k': {'name': 'فلاش متابعين 2k', 'btn_label': '2k', 'price': 4.0, 'cost': 2.0, 'service_id': 2051, 'qty': 2000, 'category': 'cat_insta', 'msg': 'أرسل رابط حسابك:'},
    'flash_fol_5k': {'name': 'فلاش متابعين 5k', 'btn_label': '5k', 'price': 12.0, 'cost': 6.0, 'service_id': 2051, 'qty': 5000, 'category': 'cat_insta', 'msg': 'أرسل رابط حسابك:'},

    'buy_fol_1k': {'name': 'متابعين 1k', 'btn_label': '1k', 'price': 1.5, 'cost': 0.8, 'service_id': 1961, 'qty': 1100, 'category': 'cat_insta', 'msg': 'أرسل رابط حسابك:'},
    'buy_fol_2k': {'name': 'متابعين 2k', 'btn_label': '2k', 'price': 3.0, 'cost': 1.6, 'service_id': 1961, 'qty': 2200, 'category': 'cat_insta', 'msg': 'أرسل رابط حسابك:'},
    'buy_fol_3k': {'name': 'متابعين 3k', 'btn_label': '3k', 'price': 4.5, 'cost': 2.4, 'service_id': 1961, 'qty': 3300, 'category': 'cat_insta', 'msg': 'أرسل رابط حسابك:'},
    'buy_fol_4k': {'name': 'متابعين 4k', 'btn_label': '4k', 'price': 6.0, 'cost': 3.2, 'service_id': 1961, 'qty': 4400, 'category': 'cat_insta', 'msg': 'أرسل رابط حسابك:'},
    'buy_fol_5k': {'name': 'متابعين 5k', 'btn_label': '5k', 'price': 7.5, 'cost': 4.0, 'service_id': 1961, 'qty': 5500, 'category': 'cat_insta', 'msg': 'أرسل رابط حسابك:'},
    'buy_fol_10k': {'name': 'متابعين 10k', 'btn_label': '10k', 'price': 15.0, 'cost': 8.0, 'service_id': 1961, 'qty': 11000, 'category': 'cat_insta', 'msg': 'أرسل رابط حسابك:'},

    'dragon_fol_1k': {'name': 'دراجون متابعين 1k', 'btn_label': '1k', 'price': 1.5, 'cost': 0.7, 'service_id': 1548, 'qty': 1000, 'category': 'cat_insta', 'msg': 'أرسل رابط حسابك:'},
    'dragon_fol_2k': {'name': 'دراجون متابعين 2k', 'btn_label': '2k', 'price': 3.0, 'cost': 1.4, 'service_id': 1548, 'qty': 2000, 'category': 'cat_insta', 'msg': 'أرسل رابط حسابك:'},
    'dragon_fol_5k': {'name': 'دراجون متابعين 5k', 'btn_label': '5k', 'price': 7.0, 'cost': 3.5, 'service_id': 1548, 'qty': 5000, 'category': 'cat_insta', 'msg': 'أرسل رابط حسابك:'},

    'tg_sub_20d_1k': {'name': 'أعضاء تليجرام (ضمان 20 يوم) 1k', 'btn_label': '1k', 'price': 5.9, 'cost': 5.4, 'service_id': 2035, 'qty': 1000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة/المجموعة:'},
    'tg_sub_20d_2k': {'name': 'أعضاء تليجرام (ضمان 20 يوم) 2k', 'btn_label': '2k', 'price': 11.8, 'cost': 10.8, 'service_id': 2035, 'qty': 2000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة/المجموعة:'},
    'tg_sub_20d_5k': {'name': 'أعضاء تليجرام (ضمان 20 يوم) 5k', 'btn_label': '5k', 'price': 29.5, 'cost': 27.0, 'service_id': 2035, 'qty': 5000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة/المجموعة:'},

    'tg_sub_fixed_1k': {'name': 'أعضاء تليجرام ثابت بدون نزول (ضمان دائم) 1k', 'btn_label': '1k', 'price': 12.0, 'cost': 8.0, 'service_id': 2033, 'qty': 1000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة/المجموعة:'},
    'tg_sub_fixed_2k': {'name': 'أعضاء تليجرام ثابت بدون نزول (ضمان دائم) 2k', 'btn_label': '2k', 'price': 24.0, 'cost': 16.0, 'service_id': 2033, 'qty': 2000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة/المجموعة:'},
    'tg_sub_fixed_5k': {'name': 'أعضاء تليجرام ثابت بدون نزول (ضمان دائم) 5k', 'btn_label': '5k', 'price': 60.0, 'cost': 40.0, 'service_id': 2033, 'qty': 5000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة/المجموعة:'},

    'tg_vip_30d_1k': {'name': 'أعضاء مميزون (قاعدة كبيرة) 1k', 'btn_label': '1k', 'price': 7.6, 'cost': 7.1, 'service_id': 2000, 'qty': 1000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة/المجموعة:'},
    'tg_vip_30d_2k': {'name': 'أعضاء مميزون (قاعدة كبيرة) 2k', 'btn_label': '2k', 'price': 15.2, 'cost': 14.2, 'service_id': 2000, 'qty': 2000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة/المجموعة:'},
    'tg_vip_30d_5k': {'name': 'أعضاء مميزون (قاعدة كبيرة) 5k', 'btn_label': '5k', 'price': 38.0, 'cost': 35.5, 'service_id': 2000, 'qty': 5000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة/المجموعة:'},

    'tg_bot_start_1k': {'name': 'ستارت بوت مميز 1k', 'btn_label': '1k', 'price': 6.1, 'cost': 5.6, 'service_id': 1821, 'qty': 1000, 'category': 'cat_telegram', 'msg': 'أرسل رابط البوت:'},
    'tg_bot_start_2k': {'name': 'ستارت بوت مميز 2k', 'btn_label': '2k', 'price': 12.2, 'cost': 11.2, 'service_id': 1821, 'qty': 2000, 'category': 'cat_telegram', 'msg': 'أرسل رابط البوت:'},
    'tg_bot_start_5k': {'name': 'ستارت بوت مميز 5k', 'btn_label': '5k', 'price': 30.5, 'cost': 28.0, 'service_id': 1821, 'qty': 5000, 'category': 'cat_telegram', 'msg': 'أرسل رابط البوت:'},

    'tg_vip_no_drop_1k': {'name': 'أعضاء مميزون (بدون نزول) 1k', 'btn_label': '1k', 'price': 13.3, 'cost': 12.8, 'service_id': 1991, 'qty': 1000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة/المجموعة:'},
    'tg_vip_no_drop_2k': {'name': 'أعضاء مميزون (بدون نزول) 2k', 'btn_label': '2k', 'price': 26.6, 'cost': 25.6, 'service_id': 1991, 'qty': 2000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة/المجموعة:'},
    'tg_vip_no_drop_5k': {'name': 'أعضاء مميزون (بدون نزول) 5k', 'btn_label': '5k', 'price': 66.5, 'cost': 64.0, 'service_id': 1991, 'qty': 5000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة/المجموعة:'},

    'tg_boost_1d_1k': {'name': 'تعزيز قنوات Boost 1k', 'btn_label': '1k', 'price': 39.5, 'cost': 39.0, 'service_id': 1757, 'qty': 1000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة للتعزيز:'},
    'tg_boost_1d_2k': {'name': 'تعزيز قنوات Boost 2k', 'btn_label': '2k', 'price': 79.0, 'cost': 78.0, 'service_id': 1757, 'qty': 2000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة للتعزيز:'},
    'tg_boost_1d_5k': {'name': 'تعزيز قنوات Boost 5k', 'btn_label': '5k', 'price': 197.5, 'cost': 195.0, 'service_id': 1757, 'qty': 5000, 'category': 'cat_telegram', 'msg': 'أرسل رابط القناة للتعزيز:'},

    'buy_like_1k': {'name': 'لايكات 1k', 'btn_label': '1k', 'price': 1.0, 'cost': 0.4, 'service_id': 2010, 'qty': 1000, 'category': 'cat_insta', 'msg': 'أرسل رابط البوست:'},
    'buy_like_2k': {'name': 'لايكات 2k', 'btn_label': '2k', 'price': 2.0, 'cost': 0.8, 'service_id': 2010, 'qty': 2000, 'category': 'cat_insta', 'msg': 'أرسل رابط البوست:'},
    'buy_like_5k': {'name': 'لايكات 5k', 'btn_label': '5k', 'price': 5.0, 'cost': 2.0, 'service_id': 2010, 'qty': 5000, 'category': 'cat_insta', 'msg': 'أرسل رابط البوست:'},
    'buy_like_10k': {'name': 'لايكات 10k', 'btn_label': '10k', 'price': 10.0, 'cost': 4.0, 'service_id': 2010, 'qty': 10000, 'category': 'cat_insta', 'msg': 'أرسل رابط البوست:'},

    'buy_view_1k': {'name': 'مشاهدات 1k', 'btn_label': '1k', 'price': 0.2, 'cost': 0.05, 'service_id': 1840, 'qty': 1000, 'category': 'cat_insta', 'msg': 'أرسل رابط الفيديو:'},
    'buy_view_2k': {'name': 'مشاهدات 2k', 'btn_label': '2k', 'price': 0.4, 'cost': 0.10, 'service_id': 1840, 'qty': 2000, 'category': 'cat_insta', 'msg': 'أرسل رابط الفيديو:'},
    'buy_view_3k': {'name': 'مشاهدات 3k', 'btn_label': '3k', 'price': 0.6, 'cost': 0.15, 'service_id': 1840, 'qty': 3000, 'category': 'cat_insta', 'msg': 'أرسل رابط الفيديو:'},
    'buy_view_4k': {'name': 'مشاهدات 4k', 'btn_label': '4k', 'price': 0.8, 'cost': 0.20, 'service_id': 1840, 'qty': 4000, 'category': 'cat_insta', 'msg': 'أرسل رابط الفيديو:'},
    'buy_view_5k': {'name': 'مشاهدات 5k', 'btn_label': '5k', 'price': 1.0, 'cost': 0.25, 'service_id': 1840, 'qty': 5000, 'category': 'cat_insta', 'msg': 'أرسل رابط الفيديو:'},

    'buy_share_1k': {'name': 'مشاركات 1k', 'btn_label': '1k', 'price': 1.2, 'cost': 0.5, 'service_id': 1842, 'qty': 1000, 'category': 'cat_insta', 'msg': 'أرسل رابط المنشور:'},
    'buy_share_2k': {'name': 'مشاركات 2k', 'btn_label': '2k', 'price': 2.4, 'cost': 1.0, 'service_id': 1842, 'qty': 2000, 'category': 'cat_insta', 'msg': 'أرسل رابط المنشور:'},
    'buy_share_3k': {'name': 'مشاركات 3k', 'btn_label': '3k', 'price': 3.6, 'cost': 1.5, 'service_id': 1842, 'qty': 3000, 'category': 'cat_insta', 'msg': 'أرسل رابط المنشور:'},
    'buy_share_4k': {'name': 'مشاركات 4k', 'btn_label': '4k', 'price': 4.8, 'cost': 2.0, 'service_id': 1842, 'qty': 4000, 'category': 'cat_insta', 'msg': 'أرسل رابط المنشور:'},
    'buy_share_5k': {'name': 'مشاركات 5k', 'btn_label': '5k', 'price': 6.0, 'cost': 2.5, 'service_id': 1842, 'qty': 5500, 'category': 'cat_insta', 'msg': 'أرسل رابط المنشور:'},
    'buy_share_10k': {'name': 'مشاركات 10k', 'btn_label': '10k', 'price': 11.0, 'cost': 5.0, 'service_id': 1842, 'qty': 10000, 'category': 'cat_insta', 'msg': 'أرسل رابط المنشور:'},

    'buy_esim_month': {'name': 'شريحة eSIM شهر', 'btn_label': 'شهر', 'price': 15.0, 'cost': 10.0, 'service_id': 0, 'qty': 1, 'category': 'cat_esim'},
    'buy_esim_week': {'name': 'شريحة eSIM أسبوع', 'btn_label': 'أسبوع', 'price': 5.0, 'cost': 3.0, 'service_id': 0, 'qty': 1, 'category': 'cat_esim'},

    'buy_itunes_2': {'name': 'بطاقة آيتونز 2$', 'btn_label': '2$', 'price': 3.5, 'cost': 2.2, 'service_id': 0, 'qty': 1, 'category': 'cat_itunes'},
    'buy_itunes_3': {'name': 'بطاقة آيتونز 3$', 'btn_label': '3$', 'price': 5.0, 'cost': 3.2, 'service_id': 0, 'qty': 1, 'category': 'cat_itunes'},
    'buy_itunes_4': {'name': 'بطاقة آيتونز 4$', 'btn_label': '4$', 'price': 6.5, 'cost': 4.2, 'service_id': 0, 'qty': 1, 'category': 'cat_itunes'},
    'buy_itunes_5': {'name': 'بطاقة آيتونز 5$', 'btn_label': '5$', 'price': 7.5, 'cost': 5.2, 'service_id': 0, 'qty': 1, 'category': 'cat_itunes'},
    'buy_itunes_15': {'name': 'بطاقة آيتونز 15$', 'btn_label': '15$', 'price': 22.0, 'cost': 15.5, 'service_id': 0, 'qty': 1, 'category': 'cat_itunes'},

    'pubg_60': {'name': '🟡 60 شدة ببجي', 'btn_label': '60 UC', 'price': 1.5, 'cost': 1.0, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '🎮 **أرسل آيدي حسابك في ببجي (Player ID) واسمك داخل اللعبة:**'},
    'pubg_120': {'name': '🟡 120 شدة ببجي', 'btn_label': '120 UC', 'price': 2.9, 'cost': 2.0, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '🎮 **أرسل آيدي حسابك في ببجي (Player ID) واسمك داخل اللعبة:**'},
    'pubg_180': {'name': '🟡 180 شدة ببجي', 'btn_label': '180 UC', 'price': 4.0, 'cost': 3.0, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '🎮 **أرسل آيدي حسابك في ببجي (Player ID) واسمك داخل اللعبة:**'},
    'pubg_336': {'name': '👑 336 شدة ببجي', 'btn_label': '336 UC', 'price': 7.0, 'cost': 5.0, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '🎮 **أرسل آيدي حسابك في ببجي (Player ID) واسمك داخل اللعبة:**'},
    'pubg_688': {'name': '🔥 688 شدة ببجي', 'btn_label': '688 UC', 'price': 13.0, 'cost': 10.0, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '🎮 **أرسل آيدي حسابك في ببجي (Player ID) واسمك داخل اللعبة:**'},
    'pubg_1170': {'name': '💎 1170 شدة ببجي', 'btn_label': '1170 UC', 'price': 22.0, 'cost': 17.0, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '🎮 **أرسل آيدي حسابك في ببجي (Player ID) واسمك داخل اللعبة:**'},

    'ff_100': {'name': '🔴 100 جوهرة فري فاير', 'btn_label': '100 💎', 'price': 2.3, 'cost': 1.2, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '🔥 **أرسل آيدي حسابك في فري فاير (Player ID) واسمك باللعبة:**'},
    'ff_210': {'name': '🔴 210 جوهرة فري فاير', 'btn_label': '210 💎', 'price': 4.0, 'cost': 2.5, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '🔥 **أرسل آيدي حسابك في فري فاير (Player ID) واسمك باللعبة:**'},
    'ff_530': {'name': '🔴 530 جوهرة فري فاير', 'btn_label': '530 💎', 'price': 8.5, 'cost': 6.0, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '🔥 **أرسل آيدي حسابك في فري فاير (Player ID) واسمك باللعبة:**'},
    'ff_1080': {'name': '💎 1080 جوهرة فري فاير', 'btn_label': '1080 💎', 'price': 16.5, 'cost': 12.0, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '🔥 **أرسل آيدي حسابك في فري فاير (Player ID) واسمك باللعبة:**'},

    'ludo_100': {'name': '🎲 100 مجوهرة لودو', 'btn_label': '100 🎲', 'price': 2.5, 'cost': 1.5, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '🎲 **أرسل آيدي حسابك في لودو (Player ID):**'},
    'ludo_500': {'name': '🎲 500 مجوهرة لودو', 'btn_label': '500 🎲', 'price': 9.0, 'cost': 6.5, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '🎲 **أرسل آيدي حسابك في لودو (Player ID):**'},

    'coc_500': {'name': '⚔️ 500 مجوهرة كلاش', 'btn_label': '500 ⚔️', 'price': 8.0, 'cost': 5.5, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '⚔️ **أرسل آيدي تاغ حسابك بـ كلاش (#Tag) واسمك:**'},
    'coc_1200': {'name': '⚔️ 1200 مجوهرة كلاش', 'btn_label': '1200 ⚔️', 'price': 17.0, 'cost': 13.0, 'service_id': 0, 'qty': 1, 'category': 'cat_games', 'msg': '⚔️ **أرسل آيدي تاغ حسابك بـ كلاش (#Tag) واسمك:**'}
}

def load_custom_services_from_db():
    try:
        res_del_srvs = supabase.table("deleted_services").select("srv_key").execute()
        deleted_keys = {row['srv_key'] for row in res_del_srvs.data} if res_del_srvs.data else set()

        res = supabase.table("settings").select("val_text").eq("key", "custom_services_list").execute()
        if res.data and res.data[0].get('val_text'):
            txt = res.data[0]['val_text']
            if txt:
                saved_services = json.loads(txt)
                updated_saved_dict = {}
                
                for k, v in saved_services.items():
                    if k in deleted_keys:
                        continue
                    if 'is_custom_tiers' not in v and 'tiers' in v:
                        v['is_custom_tiers'] = True
                    SERVICES[k] = v
                    updated_saved_dict[k] = v

                if len(saved_services) != len(updated_saved_dict):
                    supabase.table("settings").upsert({
                        "key": "custom_services_list",
                        "val_text": json.dumps(updated_saved_dict, ensure_ascii=False) if updated_saved_dict else ""
                    }, on_conflict="key").execute()

                print(f"✅ Loaded {len(updated_saved_dict)} custom services from database (Filtered).")
    except Exception as e:
        print(f"Error loading custom services: {e}")

load_custom_services_from_db()

CATEGORIES = {
    'cat_games': 'قسم الشحن والألعاب 🎮',
    'cat_insta': 'قسم الانستغرام 📸',
    'cat_telegram': 'قسم التليجرام ✈️',
    'cat_itunes': 'قسم آيتونز 🍎',
    'cat_esim': 'قسم شرائح eSIM 📱'
}

try:
    res_del_cats = supabase.table("deleted_categories").select("cat_key").execute()
    if res_del_cats.data:
        for row in res_del_cats.data:
            bc = row.get('cat_key')
            if bc in CATEGORIES:
                del CATEGORIES[bc]
except Exception as e:
    print(f"Error loading deleted categories from table: {e}")

try:
    res_del_srvs = supabase.table("deleted_services").select("srv_key").execute()
    if res_del_srvs.data:
        for row in res_del_srvs.data:
            b_srv = row.get('srv_key')
            if b_srv in SERVICES:
                del SERVICES[b_srv]
        print(f"✅ تم فلترة {len(res_del_srvs.data)} خدمة محذوفة مسبقاً من الذاكرة.")
except Exception as e:
    print(f"Error loading deleted services from table: {e}")

def admin_panel_shortcut(chat_id, message_id=None):
    m_status = "مفعل 🛠️" if is_maintenance() else "معطل 🟢"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕/❌ إدارة الأقسام والخدمات", callback_data='adm_manage_services'),
        types.InlineKeyboardButton("🏷️ الأسعار والمالية", callback_data='adm_menu_finance'),
        types.InlineKeyboardButton("👥 إدارة المستخدمين والوكلاء", callback_data='adm_menu_users'),
        types.InlineKeyboardButton("🎟️ الكروت والمسابقات", callback_data='adm_menu_promos'),
        types.InlineKeyboardButton("⚙️ النظام والإذاعة", callback_data='adm_menu_system'),
        types.InlineKeyboardButton("🛠️ صيانة الأزرار والأقسام الشاملة", callback_data='adm_maint_control_menu'),
        types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='start')
    )
    text = (
        f"🛠️ **لوحة تحكم الإدارة الشاملة (الرئيسية):**\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📌 **وضع صيانة البوت الكلي:** {m_status}\n"
        f"اختر القسم المطلوب للتعديل عليه:"
    )
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def notify_admin_new_user(user_id, first_name, username):
    try:
        safe_username = f"@{username}" if username and username != "لا يوجد" else "لا يوجد يوزر"
        safe_name = str(first_name).replace('[', '').replace(']', '').replace('*', '').replace('_', '')
        
        text = (
            f"👤 عضو جديد دخل البوت لأول مرة!\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔹 الاسم: {safe_name}\n"
            f"🔹 اليوزر: {safe_username}\n"
            f"🔹 الآيدي (ID): {user_id}"
        )
        bot.send_message(ADMIN_ID, text)
    except Exception as e:
        print(f"❌ Failed to send admin notification: {e}")

def prepare_order_summary_direct(message, base_price, data_name):
    chat_id = message.chat.id
    raw_text = message.text or ""
    
    pending_orders_cache[chat_id] = {
        'service_id': 0,
        'qty': 1,
        'name': data_name,
        'price': base_price,
        'link': raw_text.strip()
    }
    send_order_confirmation_screen(chat_id)

def prepare_order_summary(message, base_price, service_id, quantity, data_name):
    chat_id = message.chat.id
    raw_text = message.text or ""
    
    service_cat = 'cat_insta'
    for k, v in SERVICES.items():
        if v.get('service_id') == service_id:
            service_cat = v.get('category', 'cat_insta')
            break
            
    is_valid, err_msg = validate_service_link(service_cat, raw_text)
    if not is_valid:
        bot.send_message(chat_id, err_msg)
        return

    urls = re.findall(r'https?://[^\s\)\],]+', raw_text)
    clean_link = urls[0].split('?')[0] if urls else raw_text.strip()

    pending_orders_cache[chat_id] = {
        'service_id': service_id,
        'qty': quantity,
        'name': data_name,
        'price': base_price,
        'link': clean_link
    }
    send_order_confirmation_screen(chat_id)

def register_user_if_new(user_id, first_name, username, referrer_id=None):
    try:
        u = get_user(user_id)
        safe_username = username if username else "لا يوجد"
        safe_name = str(first_name) if first_name else "بدون اسم"

        if not u:
            notify_admin_new_user(user_id, safe_name, safe_username)

            initial_points = 0.0
            clean_referrer = None
            if referrer_id and str(referrer_id).isdigit():
                clean_referrer = int(referrer_id)
                if clean_referrer != user_id:
                    initial_points = 0.1

            user_data = {
                "user_id": user_id,
                "first_name": safe_name,
                "username": safe_username,
                "points": initial_points,
                "total_recharged": 0.0,
                "total_spent": 0.0,
                "is_banned": 0,
                "is_reseller": 0,
                "last_order_ts": int(time.time())
            }

            if clean_referrer:
                user_data["referrer"] = str(clean_referrer)

            supabase.table("users").insert(user_data).execute()

            if initial_points > 0:
                try:
                    bot.send_message(user_id, "🎉 **أهلاً بك! حصلت على (0.1 نقطة) هدية ترحيبية لدخولك عبر رابط دعوة!**", parse_mode="Markdown")
                except Exception:
                    pass

            if clean_referrer:
                ref_user = get_user(clean_referrer)
                if ref_user:
                    reward = 0.2
                    update_points(clean_referrer, reward)
                    try:
                        bot.send_message(
                            clean_referrer, 
                            f"🎉 **مبروك! انضم شخص جديد عبر رابط الدعوة الخاص بك.**\n💰 تم إضافة `{reward}` نقطة إلى حسابك بنجاح!", 
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        print(f"Failed to notify referrer: {e}")
            return True
        else:
            try:
                supabase.table("users").update({
                    "first_name": safe_name,
                    "username": safe_username
                }).eq("user_id", user_id).execute()
            except Exception:
                pass
    except Exception as e:
        print(f"Register user exception: {e}")
    return False

def check_sub(user_id):
    for ch in CHANNELS:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            print(f"[Warning] Check sub exception for {user_id} in {ch}: {e}")
            continue
    return True

def send_proof_to_channel(user_id, order_id, service_name, quantity=1, api_id="خدمة مباشرة"):
    try:
        uid_str = str(user_id)
        hidden_id = uid_str[:3] + "***" + uid_str[-3:] if len(uid_str) > 6 else uid_str
        
        api_info = ""
        if str(api_id) != "خدمة مباشرة" and not str(api_id).startswith("بيانات") and not str(api_id).startswith("Player ID"):
            api_info = f"🔖 **رقم الـ API:** `{api_id}`\n"
            
        qty_info = f"🔢 **الكمية:** {quantity}\n" if quantity > 1 else ""

        proof_text = (
            f"👑 **عملية شراء جديدة بنجاح!**\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 **رقم الطلب:** `{order_id}`\n"
            f"{api_info}"
            f"👤 **الزبون:** `{hidden_id}`\n"
            f"📦 **الخدمة / المنتج:** {service_name}\n"
            f"{qty_info}"
            f"⚡ **الحالة:** تم الاستلام والتنفيذ بنجاح ✅\n\n"
            f"📢 **قناة التعاملات والإثباتات:** {PROOFS_CHANNEL}"
        )
        
        bot_username = bot.get_me().username
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🤖 تجربة البوت وطلب خدماتك", url=f"https://t.me/{bot_username}"))

        bot.send_message(PROOFS_CHANNEL, proof_text, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Error sending proof: {e}")

def notify_admin_new_order(user_id, username, order_id, service_name, price, link="خدمة مباشرة"):
    try:
        link_str = f"\n🔗 **الرابط / التفاصيل:** `{link}`" if link != "خدمة مباشرة" else ""
        text = (
            f"🚨 **طلب جديد عبر البوت!**\n\n"
            f"🆔 **رقم الطلب:** `{order_id}`\n"
            f"👤 **الزبون:** {user_id} (@{username})\n"
            f"📦 **الخدمة:** {service_name}\n"
            f"💰 **المبلغ المقتطع:** {price} نقطة"
            f"{link_str}"
        )
        bot.send_message(ADMIN_ID, text, parse_mode="Markdown")
    except Exception as e:
        print(f"Admin notify error: {e}")

def referral_menu(chat_id, message_id):
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start={chat_id}"
    points = get_points(chat_id)
    
    try:
        res = supabase.table("users").select("user_id", count="exact", head=True).eq("referrer", str(chat_id)).execute()
        invites = res.count if res.count is not None else 0
    except Exception:
        invites = 0

    promo_text = (
        "ماركت المهاجم للخدمات الاكترونية، 🔥\n"
        "عالم اخر من مختلف الخدمات: \n\n"
        "1-رشق انستغرام جميع الفئات( متابعين، لايكات...)\n"
        "2-رشىق تلجرام جميع الفئات(اعضاء، ستارت بوتات، اعضاء مميزون للبحث)\n"
        "3-شحن جميع الالعاب (كلاش، ببجي، لودو، فري فاير)\n"
        "4-بطاقات ايتونز\n"
        "5-شرائح eslm انترنت بلا حدود\n\n"
        "*كل هاذه الخدمات وبأسعار تنافسية\n"
        "شتنتضر جرب خدماتنة وشكرنا لاحقا 😉🔥\n\n"
        f"🔗 رابط الدخول واستلام جائتك الهداية:\n{referral_link}"
    )

    share_url = f"https://t.me/share/url?url={referral_link}&text={quote(promo_text)}"

    text = (
        f"👥 **نظام دعوة الأصدقاء المزدوج**\n\n"
        f"📊 **إحصائياتك:**\n"
        f"• عدد الأشخاص الذين دعوتهم: `{invites}` شخص\n"
        f"• رصيدك الحالي: `{points}` نقطة\n\n"
        f"🎁 **المكافأة المزدوجة:**\n"
        f"• تحصل أنت على **(0.2 نقطة)** عن كل شخص يدخل برابطك.\n"
        f"• يحصل صديقك الجديد على **(0.1 نقطة)** هدية ترحيبية فورية!\n\n"
        f"🔗 رابط الدعوة الخاص بك:\n"
        f"`{referral_link}`"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📲 مشاركة الرابط فورياً", url=share_url),
        types.InlineKeyboardButton("🔙 العودة للقائمة", callback_data='start')
    )
    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

def auto_check_orders_and_notifications():
    while True:
        try:
            time.sleep(300)
            res = supabase.table("user_orders").select("*").eq("status", "قيد التنفيذ").neq("api_order_id", "0").execute()
            pending_orders = res.data if res.data else []

            for order in pending_orders:
                try:
                    res_status = get_status(order['api_order_id'])
                    if res_status and 'status' in res_status:
                        new_status = res_status['status']
                        status_ar = "قيد التنفيذ"
                        
                        if new_status in ['Completed', 'المكتملة']:
                            status_ar = "مكتمل ✅"
                        elif new_status in ['Canceled', 'المبلغ المسترد', 'Cancelled']:
                            status_ar = "ملغي وتم التعويض ❌"
                            refund_amt = float(order.get('price', 0.0))
                            update_points(order['user_id'], refund_amt)
                            bot.send_message(
                                order['user_id'],
                                f"⚠️ **إشعار تعويض:**\nتم إلغاء طلبك رقم <code>{order['order_id']}</code> للخدمة ({order['service']}) من قبل المصدر.\n✅ **تم إعادة مبلغ ({refund_amt}) نقطة لرصيدك تلقائياً!**",
                                parse_mode="HTML"
                            )

                        if status_ar != "قيد التنفيذ":
                            supabase.table("user_orders").update({"status": status_ar}).eq("order_id", order['order_id']).execute()
                except Exception as e:
                    print(f"Error checking order {order['order_id']}: {e}")
        except Exception as e:
            print(f"Auto thread error: {e}")

threading.Thread(target=auto_check_orders_and_notifications, daemon=True).start()

def main_menu(chat_id, message_id=None):
    if is_banned(chat_id):
        bot.send_message(chat_id, "❌ أنت محظور من استخدام البوت.")
        return

    if is_maintenance() and chat_id != ADMIN_ID:
        bot.send_message(chat_id, "🛠️ **البوت قيد الصيانة والتحديثات حالياً.**\nسنكون معكم قريباً بحلّة جديدة! 🌟", parse_mode="Markdown")
        return

    points = get_points(chat_id)
    level_info = get_user_level(chat_id)
    user_title = level_info['title']
    discount_pct = int(level_info['discount'] * 100)
    
    status_text = f"{user_title} (خصم {discount_pct}%)" if discount_pct > 0 else user_title

    cart_count = len(user_carts.get(chat_id, []))
    cart_btn_text = f"🛒 سلة الشراء ({cart_count})" if cart_count > 0 else "🛒 سلة الشراء"

    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for cat_k, cat_v in CATEGORIES.items():
        if not is_item_in_maintenance(cat_k) or chat_id == ADMIN_ID:
            markup.add(types.InlineKeyboardButton(cat_v, callback_data=cat_k))

    markup.add(
        types.InlineKeyboardButton("🔥 الأكثر طلباً", callback_data="top_services"),
        types.InlineKeyboardButton(cart_btn_text, callback_data="view_my_cart")
    )
    markup.add(
        types.InlineKeyboardButton("🎯 المسابقات والسحوبات", callback_data="active_giveaways"),
        types.InlineKeyboardButton("🔄 تحويل نقاط", callback_data="transfer_points")
    )
    markup.add(
        types.InlineKeyboardButton("🎖️ نظام الرتب والوكلاء", callback_data="ranks_info"),
        types.InlineKeyboardButton("👥 دعوة الأصدقاء", callback_data="referral_menu")
    )
    markup.add(
        types.InlineKeyboardButton("🎁 مكافأة يومية", callback_data="daily_reward"),
        types.InlineKeyboardButton("📦 طلباتي والتتبع الذكي", callback_data="my_orders")
    )
    markup.add(
        types.InlineKeyboardButton("💰 شحن رصيد آسياسيل (تلقائي)", callback_data="asiacell_recharge_menu"),
        types.InlineKeyboardButton("👨‍💻 الدعم الفني", url=SUPPORT_LINK)
    )
    
    if chat_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="admin_panel"))

    text = (
        f"نورت بوت المهاجم اولوياتنا رضا زبون 🌟\n\n"
        f"💰 رصيدك: <b>{points}</b> نقطة\n"
        f"🎖️ رتبتك الخدمات: <b>{status_text}</b>\n\n"
        f"اختر القسم أو الخدمة المطلوبة:"
    )
    
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="HTML")
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")

def update_menu_safely(bot_inst, chat_id, message_id, menu_key, markup_kb):
    text_to_show = get_menu_description(menu_key, "")
    if not text_to_show:
        text_to_show = "📌 **اختر الخدمة أو الفئة المطلوبة:**"
    try:
        bot_inst.edit_message_text(text_to_show, chat_id, message_id, reply_markup=markup_kb, parse_mode="Markdown")
    except Exception:
        try:
            bot_inst.edit_message_text(text_to_show, chat_id, message_id, reply_markup=markup_kb)
        except Exception as e:
            print(f"Safe update menu error: {e}")

@bot.callback_query_handler(func=lambda call: True)
def query(call):
    try:
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        data = call.data

        # 🚨 إيقاف دائرة التحميل فوراً لأي زر في البوت لكي لا يعلق الزر أبدًا
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        # 👑 معالجة فورية ومضمونة لجميع أزرار الأدمن لمنع التعليق نهائياً
        if chat_id == ADMIN_ID:
            if data in ['start', 'back_start', 'admin_panel']:
                admin_panel_shortcut(chat_id, message_id)
                return
            elif data == 'adm_manage_services':
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("📁 إضافة قسم رئيسي جديد", callback_data='adm_add_new_category'),
                    types.InlineKeyboardButton("➕ إضافة خدمة جديدة", callback_data='adm_add_new_srv_cat'),
                    types.InlineKeyboardButton("❌ حذف خدمة أو قسم", callback_data='adm_delete_srv_list'),
                    types.InlineKeyboardButton("📝 تعديل نصوص ووصف الأقسام", callback_data='adm_edit_descriptions'),
                    types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data='admin_panel')
                )
                bot.edit_message_text("📦 **قسم إدارة الأقسام والخدمات بالبوت:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
                return
            elif data == 'adm_menu_finance':
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("💵 رصيد DarkFollow المالي", callback_data='adm_check_df_balance'),
                    types.InlineKeyboardButton("🔄 مزامنة الأسعار فورياً (+0.5$ ربح)", callback_data='adm_force_sync_prices'),
                    types.InlineKeyboardButton("✏️ تعديل سعر خدمة محددة", callback_data='adm_edit_single_price'),
                    types.InlineKeyboardButton("📈 رفع/خفض الأسعار بنسبة (%)", callback_data='adm_bulk_price_pct_menu'),
                    types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data='admin_panel')
                )
                bot.edit_message_text("🏷️ **قسم التحكم بالأسعار والمالية:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
                return
            elif data == 'adm_menu_users':
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("🔍 البحث عن مستخدم وتعديل رصيده", callback_data='adm_search'),
                    types.InlineKeyboardButton("🕶️ ترقية مستخدم إلى (وكيل معتمد)", callback_data='adm_promote_reseller_prompt'),
                    types.InlineKeyboardButton("🚫 إدارة المحظورين (Unban)", callback_data='adm_list_banned'),
                    types.InlineKeyboardButton("👥 إحصائية المشتركين الكلية", callback_data='adm_count'),
                    types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data='admin_panel')
                )
                bot.edit_message_text("👥 **قسم إدارة وتتبع المستخدمين والوكلاء:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
                return
            elif data == 'adm_menu_promos':
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("🎁 إنشاء كود شحن فردي", callback_data='adm_gen_card'),
                    types.InlineKeyboardButton("🎟️ إنشاء كود هدية عامة بالقناة", callback_data='adm_gen_gift'),
                    types.InlineKeyboardButton("🎯 إنشاء مسابقة جديدة مع النشر", callback_data='adm_create_gw'),
                    types.InlineKeyboardButton("🎲 سحب الفائزين بالمسابقة", callback_data='adm_draw_gw'),
                    types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data='admin_panel')
                )
                bot.edit_message_text("🎟️ **قسم الهدايا، المسابقات والكروت الشحن:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
                return
            elif data == 'adm_menu_system':
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("📢 إذاعة مع التثبيت والخيارات", callback_data='adm_targeted_broadcast'),
                    types.InlineKeyboardButton("📊 تحليل سلوك وأوقات الزبائن", callback_data='adm_behavior_analytics'),
                    types.InlineKeyboardButton("📈 تقرير الأرباح المتقدم والتوب", callback_data='adm_stats'),
                    types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data='admin_panel')
                )
                bot.edit_message_text("⚙️ **قسم إعدادات النظام والإذاعات:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
                return
            elif data == 'adm_maint_control_menu':
                m_status = "مفعل 🛠️" if is_maintenance() else "معطل 🟢"
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton(f"🛠️ تغيير صيانة البوت الكلي ({m_status})", callback_data='adm_toggle_maint'),
                    types.InlineKeyboardButton("🔘 صيانة أزرار وقوائم البوت العامة", callback_data='adm_maint_buttons_menu'),
                    types.InlineKeyboardButton("📂 صيانة الأقسام والخدمات", callback_data='adm_maint_services_by_cat'),
                    types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data='admin_panel')
                )
                bot.edit_message_text("🛠️ **إدارة صيانة الأزرار والأقسام الشاملة:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
                return

        # معالجة حذف الخدمات المفردة للأدمن مباشرة وبكل أمان
        if data.startswith('delsrv_') and chat_id == ADMIN_ID:
            srv_key = data.replace('delsrv_', '', 1).strip()

            if not srv_key or srv_key not in SERVICES:
                try:
                    bot.send_message(chat_id, f"❌ خطأ: الخدمة غير موجودة أو تم حذفها مسبقاً!")
                except Exception:
                    pass
                return

            try:
                del_name = SERVICES[srv_key].get('name', 'الخدمة')
                cat_key = SERVICES[srv_key].get('category', 'cat_insta')

                # 1. حذف الخدمة من الذاكرة الحية
                if srv_key in SERVICES:
                    del SERVICES[srv_key]

                # 2. حفظ الحذف في جدول deleted_services بقاعدة البيانات
                try:
                    check = supabase.table("deleted_services").select("srv_key").eq("srv_key", srv_key).execute()
                    if not check.data:
                        supabase.table("deleted_services").insert({"srv_key": srv_key}).execute()
                except Exception as db_err:
                    print(f"DB Error: {db_err}")

                # 3. تحديث الإعدادات
                try:
                    custom_only = {k: v for k, v in SERVICES.items() if k.startswith('custom_srv_')}
                    supabase.table("settings").upsert({
                        "key": "custom_services_list",
                        "val_text": json.dumps(custom_only, ensure_ascii=False) if custom_only else ""
                    }, on_conflict="key").execute()
                except Exception as set_err:
                    print(f"Settings Error: {set_err}")

                # 4. إعادة بناء الأزرار وتحديث القائمة
                markup = types.InlineKeyboardMarkup(row_width=1)
                cat_services = {k: v for k, v in SERVICES.items() if v.get('category') == cat_key}
                cat_name = CATEGORIES.get(cat_key, "القسم")

                for s_key, s_data in cat_services.items():
                    s_name = s_data.get('name', '').strip()
                    if s_name:
                        markup.add(types.InlineKeyboardButton(f"🗑️ {s_name}", callback_data=f"delsrv_{s_key}"))

                markup.add(types.InlineKeyboardButton(f"❌ حذف القسم بالكامل ({cat_name})", callback_data=f"delcat_{cat_key}"))
                markup.add(types.InlineKeyboardButton("🔙 رجوع للأقسام", callback_data='adm_delete_srv_list'))

                try:
                    bot.edit_message_text(
                        f"📁 **{cat_name}**\n✅ تم حذف ({del_name}) بنجاح!\n\nاختر خدمة أخرى للحذف:",
                        chat_id,
                        message_id,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                except Exception:
                    bot.send_message(chat_id, f"✅ تم حذف ({del_name}) بنجاح!", reply_markup=markup, parse_mode="Markdown")

            except Exception as e:
                print(f"Delete Error: {e}")
                try:
                    bot.send_message(chat_id, f"❌ حدث خطأ أثناء الحذف:\n`{str(e)}`", parse_mode="Markdown")
                except Exception:
                    pass
            return

        # بقية معالجات البيانات والأزرار الأخرى...
        if data in CATEGORIES or data in ['cat_insta', 'cat_telegram', 'cat_games', 'cat_itunes', 'cat_esim', 'insta_menu', 'telegram_menu', 'games_menu', 'itunes_menu', 'esim_menu']:
            if data in ['cat_insta', 'insta_menu']: call.data = 'cat_insta'
            elif data in ['cat_telegram', 'telegram_menu']: call.data = 'cat_telegram'
            elif data in ['cat_games', 'games_menu']: call.data = 'cat_games'
            elif data in ['cat_itunes', 'itunes_menu']: call.data = 'cat_itunes'
            elif data in ['cat_esim', 'esim_menu']: call.data = 'cat_esim'

        if check_spam(chat_id) or is_banned(chat_id):
            return

        if is_maintenance() and chat_id != ADMIN_ID:
            bot.send_message(chat_id, "🛠️ البوت قيد الصيانة حالياً.")
            return

        if data in ['start', 'back_start']:
            if not check_sub(chat_id) and chat_id != ADMIN_ID:
                bot.send_message(chat_id, "❌ لم تشترك في القناة المطلوب الاشتراك فيها!")
                return
            main_menu(chat_id, message_id)
            return

    except Exception as e:
        print(f"Callback Error: {e}")





        

        elif call.data == 'cat_insta' or call.data == 'insta_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            back_target = 'adm_maint_buttons_menu' if is_adm_maint else 'back_start'
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for k, v in SERVICES.items():
                if v.get('category') == 'cat_insta' and k.startswith('custom_srv_'):
                    s_name = v.get('name', 'خدمة غير مسماة')
                    s_price = v.get('price', 0)
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_name} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            markup.add(types.InlineKeyboardButton(f"{v.get('btn_label', s_name)} ({s_price} ن)", callback_data=k))

            markup.add(
                types.InlineKeyboardButton("👤 قسم المتابعين", callback_data='insta_fol_sub_menu'),
                types.InlineKeyboardButton("❤️ قسم اللايكات", callback_data='open_like_menu'),
                types.InlineKeyboardButton("👁️ قسم المشاهدات", callback_data='open_view_menu'),
                types.InlineKeyboardButton("✈️ قسم المشاركات", callback_data='open_share_menu'),
                types.InlineKeyboardButton("🔙 رجوع", callback_data=back_target)
            )
            update_menu_safely(bot, chat_id, message_id, 'cat_insta', markup)

        elif call.data == 'cat_telegram' or call.data == 'telegram_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            back_target = 'adm_maint_buttons_menu' if is_adm_maint else 'back_start'
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for k, v in SERVICES.items():
                if v.get('category') == 'cat_telegram' and k.startswith('custom_srv_'):
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{v['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            markup.add(types.InlineKeyboardButton(f"{v.get('btn_label', v['name'])} ({v.get('price', 0)} ن)", callback_data=k))

            markup.add(
                types.InlineKeyboardButton("🛡️ أعضاء تليجرام ثابت (بدون نزول)", callback_data='tg_opt_fixed'),
                types.InlineKeyboardButton("👤 أعضاء تليجرام (ضمان 20 يوم)", callback_data='tg_opt_20d'),
                types.InlineKeyboardButton("💎 أعضاء مميزون قاعدة كبيرة (ضمان 30 يوم)", callback_data='tg_opt_vip_30d'),
                types.InlineKeyboardButton("🤖 ستارت بوت مميز (حسابات متصلة)", callback_data='tg_opt_bot_start'),
                types.InlineKeyboardButton("🔥 أعضاء مميزون بدون نزول سريع", callback_data='tg_opt_no_drop'),
                types.InlineKeyboardButton("🚀 تعزيز قنوات Boost (ضمان يوم)", callback_data='tg_opt_boost'),
                types.InlineKeyboardButton("🔙 رجوع", callback_data=back_target)
            )
            update_menu_safely(bot, chat_id, message_id, 'cat_telegram', markup)

        elif call.data == 'cat_games' or call.data == 'games_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            back_target = 'adm_maint_buttons_menu' if is_adm_maint else 'back_start'
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            for k, v in SERVICES.items():
                if v.get('category') == 'cat_games' and k.startswith('custom_srv_'):
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{v['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            markup.add(types.InlineKeyboardButton(f"{v.get('btn_label', v['name'])} ({v.get('price', 0)} ن)", callback_data=k))

            markup.add(
                types.InlineKeyboardButton("🟡 ببجي موبايل", callback_data='pubg_menu'),
                types.InlineKeyboardButton("🔴 فري فاير", callback_data='ff_menu'),
                types.InlineKeyboardButton("🎲 لودو كلوب", callback_data='ludo_menu'),
                types.InlineKeyboardButton("⚔️ كلاش أوف كلانس", callback_data='coc_menu'),
                types.InlineKeyboardButton("🔙 رجوع للقائمة", callback_data=back_target)
            )
            update_menu_safely(bot, chat_id, message_id, 'cat_games', markup)

        elif call.data == 'cat_itunes' or call.data == 'itunes_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            back_target = 'adm_maint_buttons_menu' if is_adm_maint else 'back_start'
            markup = types.InlineKeyboardMarkup(row_width=1)
            for k in ['buy_itunes_2', 'buy_itunes_3', 'buy_itunes_4', 'buy_itunes_5', 'buy_itunes_15']:
                if k in SERVICES:
                    s_data = SERVICES[k]
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            markup.add(types.InlineKeyboardButton(f"🍎 {s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)", callback_data=k))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=back_target))
            update_menu_safely(bot, chat_id, message_id, 'cat_itunes', markup)

        elif call.data == 'cat_esim' or call.data == 'esim_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            back_target = 'adm_maint_buttons_menu' if is_adm_maint else 'back_start'
            markup = types.InlineKeyboardMarkup(row_width=1)
            for k in ['buy_esim_month', 'buy_esim_week']:
                if k in SERVICES:
                    s_data = SERVICES[k]
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            markup.add(types.InlineKeyboardButton(f"📱 {s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)", callback_data=k))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=back_target))
            update_menu_safely(bot, chat_id, message_id, 'cat_esim', markup)

        elif call.data == 'asiacell_recharge_menu':
            if is_item_in_maintenance('asiacell_recharge_menu') and chat_id != ADMIN_ID:
                bot.send_message(chat_id, "🛠️ خدمة شحن الرصيد قيد الصيانة حالياً.")
                return
            markup = types.InlineKeyboardMarkup(row_width=2)
            for i in range(1, 11):
                pts = round(float(i) * 0.92, 2)
                markup.add(types.InlineKeyboardButton(f"{i} ألف آسياسيل ⬅️ ({pts} نقطة)", callback_data=f"asiapack_{i}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data='start'))
            
            bot.edit_message_text(
                f"💳 **شحن رصيد آسياسيل الفوري (تلقائي ومؤمن):**\n\n"
                f"اختر المبلغ الذي تريد تحويله من القائمة أدناه\n"
                f"(كل 1 ألف آسيا = 0.92 نقطة):",
                chat_id, message_id, reply_markup=markup, parse_mode="Markdown"
            )

        elif call.data.startswith('asiapack_'):
            amount_k = int(call.data.replace('asiapack_', ''))
            temp_recharge_phone_states[chat_id] = {'amount_k': amount_k}
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='asiacell_recharge_menu'))
            
            msg = bot.send_message(
                chat_id,
                f"📱 **أدخل رقم الهاتف الذي ستُحول منه الرصيد (مثال: `077xxxxxxxx`):**",
                parse_mode="Markdown",
                reply_markup=markup
            )
            bot.register_next_step_handler(msg, process_asiacell_phone_input)

        elif call.data == 'view_my_cart':
            if is_item_in_maintenance('view_my_cart') and chat_id != ADMIN_ID:
                bot.send_message(chat_id, "🛠️ قسم السلة قيد الصيانة حالياً.")
                return
            cart = user_carts.get(chat_id, [])
            if not cart:
                bot.send_message(chat_id, "🛒 **سلة المشتريات فارغة حالياً.**", parse_mode="Markdown")
                return

            total_cost = sum(item['price'] for item in cart)
            text = f"🛒 **سلة مشترياتك الحالية ({len(cart)} منتجات):**\n━━━━━━━━━━━━━━━━━━━\n\n"
            for idx, item in enumerate(cart, 1):
                text += f"{idx}. **{item['name']}** - {item['price']} نقطة\n🔗 `{item['link']}`\n\n"
            text += f"💰 **إجمالي التكلفة الكلية:** `{round(total_cost, 2)}` نقطة"

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("✅ تأكيد ودفع كل المنتجات بالسلة", callback_data='checkout_entire_cart'),
                types.InlineKeyboardButton("🗑️ تفريغ السلة", callback_data='clear_my_cart'),
                types.InlineKeyboardButton("🔙 العودة للقائمة", callback_data='start')
            )
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data == 'clear_my_cart':
            user_carts[chat_id] = []
            bot.send_message(chat_id, "🗑️ **تم تفريغ سلة المشتريات بنجاح.**", parse_mode="Markdown")
            main_menu(chat_id, message_id)

        elif call.data == 'add_to_cart_now':
            order = pending_orders_cache.get(chat_id)
            if not order:
                bot.send_message(chat_id, "⚠️ انتهت الجلسة.")
                return

            if chat_id not in user_carts:
                user_carts[chat_id] = []
            user_carts[chat_id].append(order)
            del pending_orders_cache[chat_id]

            bot.send_message(chat_id, f"🛒 **تمت إضافة ({order['name']}) إلى سلة المشتريات بنجاح!**", parse_mode="Markdown")
            main_menu(chat_id)

        elif call.data == 'checkout_entire_cart':
            cart = user_carts.get(chat_id, [])
            if not cart:
                bot.send_message(chat_id, "❌ السلة فارغة.")
                return

            total_cost = round(sum(item['price'] for item in cart), 2)
            user_points = get_points(chat_id)

            if user_points < total_cost:
                bot.send_message(chat_id, f"⚠️ رصيدك غير كافٍ لدفع السلة!\nرصيدك: `{user_points}` نقطة\nالمطلوب: `{total_cost}` نقطة", parse_mode="Markdown")
                return

            update_points(chat_id, -total_cost)
            username = call.from_user.username or "لا يوجد"
            bot.send_message(chat_id, "⏳ **جاري تنفيذ جميع طلبيات السلة...**", parse_mode="Markdown")
            
            success_count = 0
            for item in cart:
                order_id = get_next_order_id()
                s_id = item.get('service_id', 0)
                qty = item.get('qty', 1)
                
                if s_id > 0:
                    res = send_to_api(s_id, item['link'], qty)
                    api_id = res.get('order', '0') if isinstance(res, dict) else '0'
                    save_order(order_id, chat_id, username, item['name'], item['price'], api_id, item['link'], s_id, qty)
                    send_proof_to_channel(chat_id, order_id, item['name'], qty, api_id)
                else:
                    save_order(order_id, chat_id, username, item['name'], item['price'], "0", item['link'], 0, 1)
                    send_proof_to_channel(chat_id, order_id, item['name'], 1, item['link'])
                success_count += 1

            user_carts[chat_id] = []
            bot.send_message(chat_id, f"🎉 **تم تنفيذ جميع طلبات السلة بنجاح! ({success_count} طلبات)**", parse_mode="Markdown")

        elif call.data == 'top_services':
            if is_item_in_maintenance('top_services') and chat_id != ADMIN_ID:
                bot.send_message(chat_id, "🛠️ هذا القسم قيد الصيانة حالياً.")
                return
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🔥 1000 متابع فلاش (2 ن)", callback_data='flash_fol_1k'),
                types.InlineKeyboardButton("🛡️ أعضاء تليجرام ثابت 1k (12 ن)", callback_data='tg_sub_fixed_1k'),
                types.InlineKeyboardButton("🟡 60 شدة ببجي (1.5 ن)", callback_data='pubg_60'),
                types.InlineKeyboardButton("🔙 رجوع", callback_data='start')
            )
            update_menu_safely(bot, chat_id, message_id, 'top_services', markup)

        elif call.data == 'active_giveaways':
            if is_item_in_maintenance('active_giveaways') and chat_id != ADMIN_ID:
                bot.send_message(chat_id, "🛠️ قسم المسابقات قيد الصيانة حالياً.")
                return
            res = supabase.table("giveaways").select("*").eq("is_active", 1).execute()
            giveaways = res.data if res.data else []

            if not giveaways:
                bot.send_message(chat_id, "🎯 **لا توجد مسابقات سارية حالياً.**", parse_mode="Markdown")
                return

            markup = types.InlineKeyboardMarkup(row_width=1)
            for g in giveaways:
                markup.add(types.InlineKeyboardButton(f"🎁 {g['title']} ({g['prize_points']} نقطة)", callback_data=f"enter_gw_{g['id']}"))
            markup.add(types.InlineKeyboardButton("🔙 العودة للقائمة", callback_data='start'))
            bot.edit_message_text("🏆 **اختر المسابقة للدخول والسحب العشوائي:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data.startswith('enter_gw_'):
            gw_id = int(call.data.replace('enter_gw_', ''))
            res = supabase.table("giveaway_participants").select("*").eq("giveaway_id", gw_id).eq("user_id", chat_id).execute()
            
            if res.data:
                bot.send_message(chat_id, "⚠️ **أنت مشترك بالفعل بهذه المسابقة!**", parse_mode="Markdown")
            else:
                supabase.table("giveaway_participants").insert({"giveaway_id": gw_id, "user_id": chat_id}).execute()
                bot.send_message(chat_id, "✅ **تم دخولك للمسابقة بنجاح!**", parse_mode="Markdown")

        elif call.data == 'transfer_points':
            if is_item_in_maintenance('transfer_points') and chat_id != ADMIN_ID:
                bot.send_message(chat_id, "🛠️ خدمة تحويل النقاط قيد الصيانة حالياً.")
                return
            msg = bot.send_message(chat_id, "🔄 **أرسل الآيدي (ID) الخاص بالشخص المراد التحويل له:**", parse_mode="Markdown")
            bot.register_next_step_handler(msg, process_transfer_target_id)

        elif call.data.startswith('tg_opt_'):
            opt_type = call.data
            markup = types.InlineKeyboardMarkup(row_width=1)
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            back_target = 'adm_maint_buttons_menu' if is_adm_maint else 'cat_telegram'

            matched_services = {}
            for k, v in SERVICES.items():
                if v.get('category') == 'cat_telegram':
                    if k.startswith('custom_srv_'):
                        continue
                    s_name = v.get('name', '')
                    if opt_type == 'tg_opt_20d' and ('20' in s_name or '٢٠' in s_name):
                        matched_services[k] = v
                    elif opt_type == 'tg_opt_fixed' and ('ثابت' in s_name or 'دائم' in s_name):
                        matched_services[k] = v
                    elif opt_type == 'tg_opt_vip_30d' and ('مميزون' in s_name or 'قاعدة' in s_name) and '30' in s_name:
                        matched_services[k] = v
                    elif opt_type == 'tg_opt_bot_start' and 'ستارت' in s_name:
                        matched_services[k] = v
                    elif opt_type == 'tg_opt_no_drop' and 'بدون نزول' in s_name and 'مميزون' in s_name:
                        matched_services[k] = v
                    elif opt_type == 'tg_opt_boost' and ('boost' in s_name.lower() or 'تعزيز' in s_name):
                        matched_services[k] = v

            if matched_services:
                first_srv_key = None
                for k, s_data in matched_services.items():
                    if not first_srv_key:
                        first_srv_key = k
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            btn_text = f"{s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)"
                            markup.add(types.InlineKeyboardButton(btn_text, callback_data=k))
                
                if not is_adm_maint and first_srv_key:
                    markup.add(types.InlineKeyboardButton("✍️ اختيار العدد بنفسك", callback_data=f"custom_{first_srv_key}"))

            if is_adm_maint:
                markup.add(types.InlineKeyboardButton("✍️ تفعيل/إيقاف الكل بهذه الفئة", callback_data=f"maint_group_opt_{opt_type}"))

            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=back_target))
            update_menu_safely(bot, chat_id, message_id, opt_type, markup)

        elif call.data == 'insta_fol_sub_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            back_target = 'adm_maint_buttons_menu' if is_adm_maint else 'cat_insta'
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("⚡ فلاش متابعين انستغرام الأسرع في العالم", callback_data='open_flash_fol'),
                types.InlineKeyboardButton("💎 لاو متابعين انستغرام ضمان 90 يوم", callback_data='insta_fol_menu'),
                types.InlineKeyboardButton("🐉 دراجون متابعين انستا تحديث جديد", callback_data='open_dragon_fol'),
                types.InlineKeyboardButton("🔙 رجوع", callback_data=back_target)
            )
            update_menu_safely(bot, chat_id, message_id, 'insta_fol_sub_menu', markup)

        elif call.data == 'open_flash_fol':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            markup = types.InlineKeyboardMarkup(row_width=1)
            for k in ['flash_fol_1k', 'flash_fol_2k', 'flash_fol_5k']:
                if k in SERVICES:
                    s_data = SERVICES[k]
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            btn_text = f"{s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)"
                            markup.add(types.InlineKeyboardButton(btn_text, callback_data=k))
            if not is_adm_maint:
                markup.add(types.InlineKeyboardButton("✍️ اختيار العدد بنفسك", callback_data="custom_flash_fol_1k"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='insta_fol_sub_menu'))
            update_menu_safely(bot, chat_id, message_id, 'open_flash_fol', markup)

        elif call.data == 'insta_fol_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            markup = types.InlineKeyboardMarkup(row_width=1)
            for k in ['buy_fol_1k', 'buy_fol_2k', 'buy_fol_3k', 'buy_fol_4k', 'buy_fol_5k', 'buy_fol_10k']:
                if k in SERVICES:
                    s_data = SERVICES[k]
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            btn_text = f"{s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)"
                            markup.add(types.InlineKeyboardButton(btn_text, callback_data=k))
            if not is_adm_maint:
                markup.add(types.InlineKeyboardButton("✍️ اختيار العدد بنفسك", callback_data="custom_buy_fol_1k"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='insta_fol_sub_menu'))
            update_menu_safely(bot, chat_id, message_id, 'insta_fol_menu', markup)

        elif call.data == 'open_dragon_fol':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            markup = types.InlineKeyboardMarkup(row_width=1)
            for k in ['dragon_fol_1k', 'dragon_fol_2k', 'dragon_fol_5k']:
                if k in SERVICES:
                    s_data = SERVICES[k]
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            btn_text = f"{s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)"
                            markup.add(types.InlineKeyboardButton(btn_text, callback_data=k))
            if not is_adm_maint:
                markup.add(types.InlineKeyboardButton("✍️ اختيار العدد بنفسك", callback_data="custom_dragon_fol_1k"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='insta_fol_sub_menu'))
            update_menu_safely(bot, chat_id, message_id, 'open_dragon_fol', markup)

        elif call.data == 'open_like_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            markup = types.InlineKeyboardMarkup(row_width=1)
            for k in ['buy_like_1k', 'buy_like_2k', 'buy_like_5k', 'buy_like_10k']:
                if k in SERVICES:
                    s_data = SERVICES[k]
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            btn_text = f"{s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)"
                            markup.add(types.InlineKeyboardButton(btn_text, callback_data=k))
            if not is_adm_maint:
                markup.add(types.InlineKeyboardButton("✍️ اختيار العدد بنفسك", callback_data="custom_buy_like_1k"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='cat_insta'))
            update_menu_safely(bot, chat_id, message_id, 'open_like_menu', markup)

        elif call.data == 'open_view_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            markup = types.InlineKeyboardMarkup(row_width=1)
            for k in ['buy_view_1k', 'buy_view_2k', 'buy_view_3k', 'buy_view_4k', 'buy_view_5k']:
                if k in SERVICES:
                    s_data = SERVICES[k]
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            btn_text = f"{s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)"
                            markup.add(types.InlineKeyboardButton(btn_text, callback_data=k))
            if not is_adm_maint:
                markup.add(types.InlineKeyboardButton("✍️ اختيار العدد بنفسك", callback_data="custom_buy_view_1k"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='cat_insta'))
            update_menu_safely(bot, chat_id, message_id, 'open_view_menu', markup)

        elif call.data == 'open_share_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            markup = types.InlineKeyboardMarkup(row_width=1)
            for k in ['buy_share_1k', 'buy_share_2k', 'buy_share_3k', 'buy_share_4k', 'buy_share_5k', 'buy_share_10k']:
                if k in SERVICES:
                    s_data = SERVICES[k]
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            btn_text = f"{s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)"
                            markup.add(types.InlineKeyboardButton(btn_text, callback_data=k))
            if not is_adm_maint:
                markup.add(types.InlineKeyboardButton("✍️ اختيار العدد بنفسك", callback_data="custom_buy_share_1k"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='cat_insta'))
            update_menu_safely(bot, chat_id, message_id, 'open_share_menu', markup)

        elif call.data == 'pubg_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            markup = types.InlineKeyboardMarkup(row_width=1)
            for k in ['pubg_60', 'pubg_120', 'pubg_180', 'pubg_336', 'pubg_688', 'pubg_1170']:
                if k in SERVICES:
                    s_data = SERVICES[k]
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            btn_text = f"{s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)"
                            markup.add(types.InlineKeyboardButton(btn_text, callback_data=k))
            markup.add(types.InlineKeyboardButton("🔙 رجوع للألعاب", callback_data='cat_games'))
            update_menu_safely(bot, chat_id, message_id, 'pubg_menu', markup)

        elif call.data == 'ff_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            markup = types.InlineKeyboardMarkup(row_width=1)
            for k in ['ff_100', 'ff_210', 'ff_530', 'ff_1080']:
                if k in SERVICES:
                    s_data = SERVICES[k]
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            btn_text = f"{s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)"
                            markup.add(types.InlineKeyboardButton(btn_text, callback_data=k))
            markup.add(types.InlineKeyboardButton("🔙 رجوع للألعاب", callback_data='cat_games'))
            update_menu_safely(bot, chat_id, message_id, 'ff_menu', markup)

        elif call.data == 'ludo_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            markup = types.InlineKeyboardMarkup(row_width=1)
            for k in ['ludo_100', 'ludo_500']:
                if k in SERVICES:
                    s_data = SERVICES[k]
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            btn_text = f"{s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)"
                            markup.add(types.InlineKeyboardButton(btn_text, callback_data=k))
            markup.add(types.InlineKeyboardButton("🔙 رجوع للألعاب", callback_data='cat_games'))
            update_menu_safely(bot, chat_id, message_id, 'ludo_menu', markup)

        elif call.data == 'coc_menu':
            is_adm_maint = (chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''))
            markup = types.InlineKeyboardMarkup(row_width=1)
            for k in ['coc_500', 'coc_1200']:
                if k in SERVICES:
                    s_data = SERVICES[k]
                    if is_adm_maint:
                        st = "🛠️ (صيانة)" if is_item_in_maintenance(k) else "🟢 (شغالة)"
                        markup.add(types.InlineKeyboardButton(f"{s_data['name']} - {st}", callback_data=f"toggle_maint_{k}"))
                    else:
                        if not is_item_in_maintenance(k) or chat_id == ADMIN_ID:
                            btn_text = f"{s_data.get('btn_label', s_data['name'])} ({s_data.get('price', 0)} ن)"
                            markup.add(types.InlineKeyboardButton(btn_text, callback_data=k))
            markup.add(types.InlineKeyboardButton("🔙 رجوع للألعاب", callback_data='cat_games'))
            update_menu_safely(bot, chat_id, message_id, 'coc_menu', markup)

        elif call.data.startswith('custom_'):
            base_service_key = call.data.replace('custom_', '')
            s_info = SERVICES.get(base_service_key)
            if not s_info:
                for k, v in SERVICES.items():
                    if k in base_service_key or base_service_key in k:
                        s_info = v
                        base_service_key = k
                        break

            if s_info:
                text_req = f"✍️ **أدخل الكمية المطلوبة لـ ({s_info['name']}):**\n*(الحد الأدنى: 100 - الحد الأقصى: 100,000)*"
                markup_back = types.InlineKeyboardMarkup()
                markup_back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='start'))
                
                bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
                bot.register_next_step_handler(call.message, process_generic_custom_qty, base_service_key)
            else:
                bot.send_message(chat_id, "⚠️ هذه الخدمة لا تدعم الكميات المخصصة حالياً.")

        elif call.data == 'ranks_info':
            if is_item_in_maintenance('ranks_info') and chat_id != ADMIN_ID:
                bot.send_message(chat_id, "🛠️ هذا القسم قيد الصيانة حالياً.")
                return
            lvl = get_user_level(chat_id)
            text = (
                f"🎖️ **نظام الرتب والتخفيضات والوكلاء:**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"مستواك الحالي: **{lvl['title']}**\n\n"
                f"📌 **تفاصيل الرتب والخصومات:**\n"
                f"• 👤 **مستخدم عادي:** خصم 0%\n"
                f"• 🥉 **تاجر مبتدئ:** إنفاق 50+ نقطة (خصم 1%)\n"
                f"• 🥈 **تاجر:** إنفاق 100+ نقطة (خصم 2%)\n"
                f"• 🥇 **تاجر جيد:** إنفاق 150+ نقطة (خصم 3%)\n"
                f"• 💎 **تاجر محترف:** إنفاق 200+ نقطة (خصم 4%)\n"
                f"• 🏆 **VIP:** إنفاق 300+ نقطة (خصم 5%)\n"
                f"• 🕶️ **وكيل معتمد:** صلاحية خاصة (خصم 8% على كل الخدمات!)\n\n"
                f"💡 يتم تطبيق الخصم تلقائياً عند طلب أي خدمة!"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 العودة للقائمة", callback_data='start'))
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data == 'referral_menu':
            if is_item_in_maintenance('referral_menu') and chat_id != ADMIN_ID:
                bot.send_message(chat_id, "🛠️ هذا القسم قيد الصيانة حالياً.")
                return
            referral_menu(chat_id, message_id)

        elif call.data == 'daily_reward':
            if is_item_in_maintenance('daily_reward') and chat_id != ADMIN_ID:
                bot.send_message(chat_id, "🛠️ مكافأة اليوم قيد الصيانة حالياً.")
                return
            now = int(time.time())
            res = supabase.table("daily_reward").select("last_claim").eq("user_id", chat_id).execute()
            row = res.data[0] if res.data else None
            if row and (now - row['last_claim'] < 86400):
                remain = 86400 - (now - row['last_claim'])
                hours, minutes = remain // 3600, (remain % 3600) // 60
                bot.send_message(chat_id, f"⏳ لا يمكنك استلام المكافأة الآن.\nيرجى الانتظار: {hours} ساعة و {minutes} دقيقة.")
            else:
                update_points(chat_id, 0.1)
                supabase.table("daily_reward").upsert({"user_id": chat_id, "last_claim": now}).execute()
                bot.send_message(chat_id, f"🎉 تم استلام مكافأتك اليومية (0.1 نقطة) بنجاح!")

        elif call.data == 'my_orders':
            if is_item_in_maintenance('my_orders') and chat_id != ADMIN_ID:
                bot.send_message(chat_id, "🛠️ قسم طلباتي قيد الصيانة حالياً.")
                return
            res = supabase.table("user_orders").select("*").eq("user_id", chat_id).order("order_id", desc=True).limit(5).execute()
            orders = res.data if res.data else []
            if not orders:
                bot.send_message(chat_id, "📦 لا توجد لديك طلبات قائمة حالياً.")
            else:
                bot.send_message(chat_id, "📦 <b>سجل طلباتك الأخيرة (مع التتبع المباشر للـ API):</b>\n━━━━━━━━━━━━━━━━━━━", parse_mode="HTML")
                for o in orders:
                    s_name = str(o['service']).replace('<', '&lt;').replace('>', '&gt;')
                    icon = "⏳" if "قيد" in str(o['status']) else ("❌" if "ملغي" in str(o['status']) else "✅")
                    markup_ord = types.InlineKeyboardMarkup()
                    if str(o.get('api_order_id')) != "0":
                        markup_ord.add(types.InlineKeyboardButton("🔄 تحديث حالة الطلب لحظياً", callback_data=f"track_order_{o['order_id']}"))
                    
                    text = (
                        f"🆔 <b>رقم الطلب:</b> <code>{o['order_id']}</code>\n"
                        f"🛍️ <b>الخدمة:</b> {s_name}\n"
                        f"💰 <b>السعر:</b> {o['price']} نقطة\n"
                        f"{icon} <b>الحالة:</b> {o['status']}"
                    )
                    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup_ord if markup_ord.keyboard else None)

        elif call.data.startswith('track_order_'):
            o_id = int(call.data.replace('track_order_', ''))
            res = supabase.table("user_orders").select("*").eq("order_id", o_id).eq("user_id", chat_id).execute()
            if res.data:
                ord_info = res.data[0]
                live_info = check_order_live_status(o_id, ord_info.get('api_order_id'))
                bot.answer_callback_query(call.id, "✅ تم جلب أحدث حالة للطلب بنجاح!", show_alert=False)
                bot.send_message(chat_id, f"🔍 **نتيجة التتبع المباشر للطلب (`{o_id}`):**\n\n{live_info}", parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "❌ الطلب غير موجود.", show_alert=True)

        elif call.data == 'enter_voucher_code':
            text_req = "🔑 **أرسل كود الشحن أو الهدية:**"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='start'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_user_redeem_input)

        elif call.data == 'admin_panel' and chat_id == ADMIN_ID:
            admin_panel_shortcut(chat_id, message_id)

        elif call.data == 'adm_manage_services' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("📁 إضافة قسم رئيسي جديد", callback_data='adm_add_new_category'),
                types.InlineKeyboardButton("➕ إضافة خدمة جديدة", callback_data='adm_add_new_srv_cat'),
                types.InlineKeyboardButton("❌ حذف خدمة أو قسم", callback_data='adm_delete_srv_list'),
                types.InlineKeyboardButton("📝 تعديل نصوص ووصف الأقسام", callback_data='adm_edit_descriptions'),
                types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data='admin_panel')
            )
            bot.edit_message_text("📦 **قسم إدارة الأقسام والخدمات بالبوت:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data == 'adm_edit_descriptions' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=1)
            desc_options = [
                ('tg_opt_fixed', 'تليجرام ثابت'),
                ('tg_opt_20d', 'تليجرام 20 يوم'),
                ('tg_opt_vip_30d', 'تليجرام VIP 30 يوم'),
                ('tg_opt_bot_start', 'ستارت بوت'),
                ('tg_opt_no_drop', 'تليجرام بدون نزول'),
                ('tg_opt_boost', 'تعزيز قنوات Boost'),
                ('open_flash_fol', 'انستا فلاش'),
                ('insta_fol_menu', 'انستا 90 يوم'),
                ('open_dragon_fol', 'انستا دراجون'),
                ('open_like_menu', 'انستا لايكات'),
                ('open_view_menu', 'انستا مشاهدات'),
                ('pubg_menu', 'شدات ببجي'),
                ('ff_menu', 'جواهر فري فاير')
            ]
            for key, name in desc_options:
                markup.add(types.InlineKeyboardButton(name, callback_data=f"editdesc_{key}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='adm_manage_services'))
            bot.edit_message_text("📝 **اختر القسم الذي تريد تعديل وصفه:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data.startswith('editdesc_') and chat_id == ADMIN_ID:
            menu_key = call.data.replace('editdesc_', '')
            admin_states[chat_id] = {'action': 'edit_desc', 'menu_key': menu_key}
            
            text_req = "📝 **أرسل الآن الوصف الجديد الذي تريده أن يظهر للمستخدم في هذا القسم:**"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_edit_descriptions'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_admin_edit_desc)

        elif call.data == 'adm_add_new_category' and chat_id == ADMIN_ID:
            text_req = "📁 **أدخل مفتاح القسم باللغة الإنجليزية (مثال: `cat_tiktok`):**"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_manage_services'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, step_add_category_key)

        elif call.data == 'adm_add_new_srv_cat' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for cat_k, cat_v in CATEGORIES.items():
                markup.add(types.InlineKeyboardButton(cat_v, callback_data=f"addsrv_cat_{cat_k}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='adm_manage_services'))
            bot.edit_message_text("📂 **اختر القسم الرئيسي الذي تريد إضافة الخدمة فيه:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data.startswith('addsrv_cat_') and chat_id == ADMIN_ID:
            cat_key = call.data.replace('addsrv_cat_', '')
            temp_add_service[chat_id] = {'category': cat_key}
            
            text_req = "📝 **أدخل اسم الخدمة الجديدة التي ستظهر للمستخدمين:**"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_manage_services'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, step_srv_name)

        elif call.data == 'adm_delete_srv_list' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for cat_k, cat_v in CATEGORIES.items():
                markup.add(types.InlineKeyboardButton(cat_v, callback_data=f"adm_del_cat_srvs_{cat_k}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='adm_manage_services'))
            bot.edit_message_text("📌 **اختر القسم لعرض خدماته وحذفها فوراً، أو لحذف القسم كله:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data.startswith('adm_del_cat_srvs_') and chat_id == ADMIN_ID:
            cat_key = call.data.replace('adm_del_cat_srvs_', '')
            cat_name = CATEGORIES.get(cat_key, "القسم")
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            cat_services = {k: v for k, v in SERVICES.items() if v.get('category') == cat_key}
            
            seen_names = set()
            service_keys_map = {}
            for s_key, s_data in cat_services.items():
                name = s_data['name']
                base_name = name
                for suffix in [' 1k', ' 2k', ' 3k', ' 4k', ' 5k', ' 10k', ' (ضمان 20 يوم)', ' ثابت', ' فلاش', ' دراجون']:
                    if suffix in base_name:
                        base_name = base_name.replace(suffix, '')
                
                base_name = base_name.strip()
                if base_name not in seen_names:
                    seen_names.add(base_name)
                    service_keys_map[base_name] = s_key
                    markup.add(types.InlineKeyboardButton(f"🗑️ {base_name}", callback_data=f"delgroup_{cat_key}_{s_key}"))
            
            markup.add(types.InlineKeyboardButton(f"❌ حذف القسم بالكامل ({cat_name})", callback_data=f"delcat_{cat_key}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع للأقسام", callback_data='adm_delete_srv_list'))
            
            bot.edit_message_text(f"📁 **{cat_name}**\nاختر الخدمة الرئيسية لحذفها كـ مجموعة نهائياً:", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data.startswith('delgroup_') and chat_id == ADMIN_ID:
            parts = call.data.split('_', 2)
            if len(parts) >= 3:
                cat_key = parts[1]
                target_srv_key = parts[2]

                suffixes = [
                    ' 1k', ' 2k', ' 3k', ' 4k', ' 5k', ' 10k',
                    ' (ضمان 20 يوم)', ' ثابت', ' فلاش', ' دراجون'
                ]

                target_base_name = ""
                if target_srv_key in SERVICES:
                    target_base_name = SERVICES[target_srv_key].get('name', '')
                    for suffix in suffixes:
                        target_base_name = target_base_name.replace(suffix, '')
                    target_base_name = target_base_name.strip()

                if not target_base_name:
                    bot.answer_callback_query(
                        call.id,
                        "❌ الخدمة غير موجودة أو تم حذفها مسبقاً!",
                        show_alert=True
                    )
                else:
                    keys_to_delete = []

                    for srv_key, srv_data in list(SERVICES.items()):
                        if srv_data.get('category') != cat_key:
                            continue

                        srv_base_name = srv_data.get('name', '')

                        for suffix in suffixes:
                            srv_base_name = srv_base_name.replace(suffix, '')

                        if srv_base_name.strip() == target_base_name:
                            keys_to_delete.append(srv_key)

                    for srv_key in keys_to_delete:
                        if srv_key in SERVICES:
                            del SERVICES[srv_key]

                        try:
                            check = (
                                supabase.table("deleted_services")
                                .select("srv_key")
                                .eq("srv_key", srv_key)
                                .execute()
                            )

                            if not check.data:
                                supabase.table("deleted_services").insert({
                                    "srv_key": srv_key
                                }).execute()

                        except Exception as e:
                            print(f"Error saving deleted service {srv_key}: {e}")

                    try:
                        custom_only = {
                            key: value
                            for key, value in SERVICES.items()
                            if key.startswith('custom_srv_')
                        }

                        payload = {
                            "key": "custom_services_list",
                            "val_text": json.dumps(
                                custom_only,
                                ensure_ascii=False
                            ) if custom_only else ""
                        }

                        supabase.table("settings").upsert(
                            payload,
                            on_conflict="key"
                        ).execute()

                    except Exception as e:
                        print(f"Error updating custom services after group delete: {e}")

                    bot.answer_callback_query(
                        call.id,
                        f"✅ تم حذف مجموعة ({target_base_name}) نهائياً!",
                        show_alert=True
                    )

                    markup = types.InlineKeyboardMarkup(row_width=1)

                    cat_services = {
                        key: value
                        for key, value in SERVICES.items()
                        if value.get('category') == cat_key
                    }

                    seen_names = set()

                    for srv_key, srv_data in cat_services.items():
                        base_name = srv_data.get('name', '')

                        for suffix in suffixes:
                            base_name = base_name.replace(suffix, '')

                        base_name = base_name.strip()

                        if base_name not in seen_names:
                            seen_names.add(base_name)

                            markup.add(
                                types.InlineKeyboardButton(
                                    f"🗑️ {base_name}",
                                    callback_data=f"delgroup_{cat_key}_{srv_key}"
                                )
                            )

                    cat_name = CATEGORIES.get(cat_key, "القسم")

                    markup.add(
                        types.InlineKeyboardButton(
                            f"❌ حذف القسم بالكامل ({cat_name})",
                            callback_data=f"delcat_{cat_key}"
                        )
                    )

                    markup.add(
                        types.InlineKeyboardButton(
                            "🔙 رجوع للأقسام",
                            callback_data="adm_delete_srv_list"
                        )
                    )

                    try:
                        bot.edit_message_text(
                            f"📁 **{cat_name}**\n"
                            f"✅ تم حذف الخدمة بنجاح ولن تظهر بعد الآن.\n"
                            f"اختر خدمة أخرى للحذف:",
                            chat_id,
                            message_id,
                            reply_markup=markup,
                            parse_mode="Markdown"
                        )

                    except Exception as e:
                        print(f"Error updating delete menu: {e}")
                        
        elif call.data.startswith('delsrv_') and chat_id == ADMIN_ID:
            # 1. إيقاف دائرة التحميل من تيليجرام فوراً لمنع تعليق الزر
            try:
                bot.answer_callback_query(call.id)
            except Exception:
                pass

            srv_key = call.data.replace('delsrv_', '', 1).strip()

            if not srv_key or srv_key not in SERVICES:
                try:
                    bot.answer_callback_query(call.id, "❌ هذه الخدمة غير موجودة أو تم حذفها مسبقاً!", show_alert=True)
                except Exception:
                    pass
                return

            try:
                del_name = SERVICES[srv_key].get('name', 'الخدمة')
                cat_key = SERVICES[srv_key].get('category', 'cat_insta')

                # 2. الحذف الفعلي من الذاكرة الحية للبوت
                if srv_key in SERVICES:
                    del SERVICES[srv_key]

                # 3. حفظ الحذف في جدول deleted_services بقاعدة البيانات لمنع عودتها عند الـ Restart
                try:
                    check = supabase.table("deleted_services").select("srv_key").eq("srv_key", srv_key).execute()
                    if not check.data:
                        supabase.table("deleted_services").insert({"srv_key": srv_key}).execute()
                except Exception as e:
                    print(f"DB Error (deleted_services): {e}")

                # 4. تحديث قائمة الخدمات المخصصة في جدول الإعدادات
                try:
                    custom_only = {k: v for k, v in SERVICES.items() if k.startswith('custom_srv_')}
                    supabase.table("settings").upsert({
                        "key": "custom_services_list",
                        "val_text": json.dumps(custom_only, ensure_ascii=False) if custom_only else ""
                    }, on_conflict="key").execute()
                except Exception as e:
                    print(f"DB Error (settings): {e}")

                # 5. إعادة بناء القائمة المحدثة للأزرار
                markup = types.InlineKeyboardMarkup(row_width=1)
                cat_services = {k: v for k, v in SERVICES.items() if v.get('category') == cat_key}
                cat_name = CATEGORIES.get(cat_key, "القسم")

                for s_key, s_data in cat_services.items():
                    s_name = s_data.get('name', '').strip()
                    if s_name:
                        markup.add(
                            types.InlineKeyboardButton(
                                f"🗑️ {s_name}",
                                callback_data=f"delsrv_{s_key}"
                            )
                        )

                markup.add(types.InlineKeyboardButton(f"❌ حذف القسم بالكامل ({cat_name})", callback_data=f"delcat_{cat_key}"))
                markup.add(types.InlineKeyboardButton("🔙 رجوع للأقسام", callback_data='adm_delete_srv_list'))

                # 6. محاولة تحديث الرسالة بأمان تام مع منع خطأ تعليق الرسائل المتطابقة
                try:
                    bot.edit_message_text(
                        f"📁 **{cat_name}**\n"
                        f"✅ تم حذف ({del_name}) بنجاح ولن تظهر بعد الآن.\n\n"
                        f"اختر خدمة أخرى للحذف:",
                        chat_id,
                        message_id,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                except Exception as edit_err:
                    print(f"Edit message warning: {edit_err}")
                    # في حال لم تتغير الرسالة، نرسل رسالة جديدة لتأكيد الحذف وتحديث القائمة
                    bot.send_message(
                        chat_id,
                        f"✅ تم حذف ({del_name}) بنجاح!",
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )

            except Exception as e:
                print(f"Critical error in delsrv: {e}")
                try:
                    bot.send_message(chat_id, f"❌ حدث خطأ أثناء تنفيذ الحذف: `{str(e)}`", parse_mode="Markdown")
                except Exception:
                    pass

            
        elif call.data.startswith('delcat_') and chat_id == ADMIN_ID:
            cat_to_del = call.data.replace('delcat_', '', 1)

            if cat_to_del in CATEGORIES:
                cat_name = CATEGORIES[cat_to_del]

                keys_to_del = [
                    k for k, v in SERVICES.items()
                    if v.get('category') == cat_to_del
                ]

                for k in keys_to_del:
                    if k in SERVICES:
                        del SERVICES[k]

                    try:
                        supabase.table("deleted_services").insert(
                            {"srv_key": k}
                        ).execute()
                    except Exception:
                        pass

                del CATEGORIES[cat_to_del]

                try:
                    check_category = (
                        supabase.table("deleted_categories")
                        .select("cat_key")
                        .eq("cat_key", cat_to_del)
                        .execute()
                    )

                    if not check_category.data:
                        supabase.table("deleted_categories").insert({
                            "cat_key": cat_to_del
                        }).execute()

                except Exception as e:
                    print(f"Error saving deleted category: {e}")

                try:
                    custom_only = {
                        key: value
                        for key, value in SERVICES.items()
                        if key.startswith("custom_srv_")
                    }

                    supabase.table("settings").upsert(
                        {
                            "key": "custom_services_list",
                            "val_text": json.dumps(
                                custom_only,
                                ensure_ascii=False
                            ) if custom_only else ""
                        },
                        on_conflict="key"
                    ).execute()

                except Exception as e:
                    print(f"Error updating custom services after category delete: {e}")

                bot.answer_callback_query(
                    call.id,
                    f"✅ تم حذف قسم ({cat_name}) نهائياً!",
                    show_alert=True
                )

                admin_panel_shortcut(chat_id, message_id)

        elif call.data == 'adm_menu_finance' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("💵 رصيد DarkFollow المالي", callback_data='adm_check_df_balance'),
                types.InlineKeyboardButton("🔄 مزامنة الأسعار فورياً (+0.5$ ربح)", callback_data='adm_force_sync_prices'),
                types.InlineKeyboardButton("✏️ تعديل سعر خدمة محددة", callback_data='adm_edit_single_price'),
                types.InlineKeyboardButton("📈 رفع/خفض الأسعار بنسبة (%)", callback_data='adm_bulk_price_pct_menu'),
                types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data='admin_panel')
            )
            bot.edit_message_text("🏷️ **قسم التحكم بالأسعار والمالية:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data == 'adm_check_df_balance' and chat_id == ADMIN_ID:
            res_bal = get_api_balance()
            if isinstance(res_bal, dict) and 'balance' in res_bal:
                bal_val = res_bal['balance']
                curr = res_bal.get('currency', 'USD')
                bot.answer_callback_query(call.id, f"رصيدك الحالي: {bal_val} {curr}", show_alert=True)
                bot.send_message(chat_id, f"💵 **رصيدك الحالي في موقع DarkFollow:**\n`{bal_val} {curr}`", parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "تعذر جلب الرصيد من المزود حالياً.", show_alert=True)

        elif call.data == 'adm_force_sync_prices' and chat_id == ADMIN_ID:
            success, result = sync_prices_from_api_logic()
            if success:
                bot.answer_callback_query(call.id, f"✅ تمت مزامنة وتحديث ({result}) خدمة بنجاح!", show_alert=True)
                bot.send_message(chat_id, f"🔄 **تمت مزامنة الأسعار من موقع DarkFollow وتحديثها بنجاح!**\n📊 عدد الخدمات المحدثة: `{result}` خدمة.", parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "❌ فشلت عملية المزامنة مع المزود.", show_alert=True)
                bot.send_message(chat_id, f"❌ **تعذر إتمام المزامنة:**\n`{result}`", parse_mode="Markdown")

        elif call.data == 'adm_edit_single_price' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=2)
            for key, val in SERVICES.items():
                markup.add(types.InlineKeyboardButton(f"{val['name']} ({val.get('price', 0)} ن)", callback_data=f"setprc_{key}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='adm_menu_finance'))
            bot.edit_message_text("✏️ **اختر الخدمة المراد تعديل سعرها:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data.startswith('setprc_') and chat_id == ADMIN_ID:
            service_key = call.data.replace('setprc_', '')
            service_info = SERVICES.get(service_key)
            if service_info:
                text_req = f"✏️ **الخدمة:** {service_info['name']}\n💰 السعر الحالي: `{service_info.get('price', 0)}` نقطة\n\nأرسل **السعر الجديد** بالنقاط الآن:"
                markup_back = types.InlineKeyboardMarkup()
                markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_edit_single_price'))
                bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
                bot.register_next_step_handler(call.message, process_update_single_price, service_key)

        elif call.data == 'adm_bulk_price_pct_menu' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("📉 خفض السعر بنسبة (%)", callback_data='adm_bulk_decrease_pct'),
                types.InlineKeyboardButton("📈 زيادة السعر بنسبة (%)", callback_data='adm_bulk_increase_pct'),
                types.InlineKeyboardButton("🔙 رجوع", callback_data='adm_menu_finance')
            )
            bot.edit_message_text("📈 **اختر نوع تعديل الأسعار الكلي:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data == 'adm_bulk_decrease_pct' and chat_id == ADMIN_ID:
            text_req = "📉 **خفض أسعار الخدمات:**\n\nأدخل نسبة الخفض (مثال: `10` لخفض الأسعار 10%):"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_bulk_price_pct_menu'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_update_bulk_price_decrease)

        elif call.data == 'adm_bulk_increase_pct' and chat_id == ADMIN_ID:
            text_req = "📈 **زيادة أسعار الخدمات:**\n\nأدخل نسبة الزيادة (مثال: `15` لزيادة الأسعار 15%):"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_bulk_price_pct_menu'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_update_bulk_price_increase)

        elif call.data == 'adm_menu_users' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🔍 البحث عن مستخدم وتعديل رصيده", callback_data='adm_search'),
                types.InlineKeyboardButton("🕶️ ترقية مستخدم إلى (وكيل معتمد)", callback_data='adm_promote_reseller_prompt'),
                types.InlineKeyboardButton("🚫 إدارة المحظورين (Unban)", callback_data='adm_list_banned'),
                types.InlineKeyboardButton("👥 إحصائية المشتركين الكلية", callback_data='adm_count'),
                types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data='admin_panel')
            )
            bot.edit_message_text("👥 **قسم إدارة وتتبع المستخدمين والوكلاء:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data == 'adm_search' and chat_id == ADMIN_ID:
            text_req = "🔍 **أرسل ID المستخدم أو اسم المستخدم (@username) للبحث عنه:**"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_menu_users'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_admin_user_search)

        elif call.data == 'adm_promote_reseller_prompt' and chat_id == ADMIN_ID:
            text_req = "🕶️ **أرسل ID المستخدم لترقيته إلى رتبة (وكيل معتمد):**"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_menu_users'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_admin_promote_reseller)

        elif call.data == 'adm_count' and chat_id == ADMIN_ID:
            try:
                res_u = supabase.table("users").select("user_id", count="exact", head=True).execute()
                total_u = res_u.count if res_u.count is not None else 0
                res_ord = supabase.table("user_orders").select("order_id", count="exact", head=True).execute()
                total_o = res_ord.count if res_ord.count is not None else 0
                
                text = (
                    f"👥 **إحصائيات البوت الكلية:**\n"
                    f"━━━━━━━━━━━━━━━━━━━\n\n"
                    f"• 👤 إجمالي المشتركين بالبوت: `{total_u}` عضو\n"
                    f"• 📦 إجمالي الطلبات الكلية: `{total_o}` طلب"
                )
                bot.send_message(chat_id, text, parse_mode="Markdown")
            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ أثناء جلب الإحصائيات: {e}")

        elif call.data == 'adm_list_banned' and chat_id == ADMIN_ID:
            res = supabase.table("users").select("user_id, username").eq("is_banned", 1).execute()
            banned_users = res.data if res.data else []
            if not banned_users:
                bot.send_message(chat_id, "🟢 لا يوجد مستخدمين محظورين حالياً.")
                return
            markup = types.InlineKeyboardMarkup(row_width=1)
            for bu in banned_users:
                markup.add(types.InlineKeyboardButton(f"🔓 فك الحظر عن: {bu['user_id']} (@{bu.get('username','لا يوجد')})", callback_data=f"unban_{bu['user_id']}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='adm_menu_users'))
            bot.edit_message_text("🚫 **قائمة المحظورين:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data.startswith('unban_') and chat_id == ADMIN_ID:
            b_id = int(call.data.replace('unban_', ''))
            supabase.table("users").update({"is_banned": 0}).eq("user_id", b_id).execute()
            bot.send_message(chat_id, f"✅ **تم فك الحظر عن المستخدم (`{b_id}`) بنجاح!**", parse_mode="Markdown")

        elif call.data.startswith('admin_add_pts_') and chat_id == ADMIN_ID:
            target_uid = int(call.data.replace('admin_add_pts_', ''))
            admin_states[chat_id] = {'action': 'add_pts', 'target': target_uid}
            
            text_req = f"💰 **أدخل عدد النقاط المراد إضافتها للمستخدم (`{target_uid}`):**"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_menu_users'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_admin_modify_points)

        elif call.data.startswith('admin_msg_') and chat_id == ADMIN_ID:
            target_uid = int(call.data.replace('admin_msg_', ''))
            admin_states[chat_id] = {'action': 'send_msg', 'target': target_uid}
            
            text_req = f"💬 **أرسل الرسالة للمستخدم (`{target_uid}`):**"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_menu_users'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_admin_send_direct_msg)

        elif call.data == 'adm_menu_promos' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🎁 إنشاء كود شحن فردي", callback_data='adm_gen_card'),
                types.InlineKeyboardButton("🎟️ إنشاء كود هدية عامة بالقناة", callback_data='adm_gen_gift'),
                types.InlineKeyboardButton("🎯 إنشاء مسابقة جديدة مع النشر", callback_data='adm_create_gw'),
                types.InlineKeyboardButton("🎲 سحب الفائزين بالمسابقة", callback_data='adm_draw_gw'),
                types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data='admin_panel')
            )
            bot.edit_message_text("🎟️ **قسم الهدايا، المسابقات والكروت الشحن:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data == 'adm_gen_card' and chat_id == ADMIN_ID:
            text_req = "أرسل قيمة النقاط لكود الشحن المراد إنشاؤه:"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_menu_promos'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_gen_card)

        elif call.data == 'adm_gen_gift' and chat_id == ADMIN_ID:
            text_req = "🎟️ **أدخل الكود وقيمة النقاط وعدد الأشخاص يفصل بينها مسافة:**"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_menu_promos'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_gen_gift_code)

        elif call.data == 'adm_create_gw' and chat_id == ADMIN_ID:
            text_req = "🏆 **أدخل عنوان المسابقة - نقاط الجائزة - عدد الفائزين:**"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_menu_promos'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_create_giveaway)

        elif call.data == 'adm_draw_gw' and chat_id == ADMIN_ID:
            res = supabase.table("giveaways").select("*").eq("is_active", 1).execute()
            gws = res.data if res.data else []
            if not gws:
                bot.send_message(chat_id, "❌ لا توجد مسابقات سارية حالياً لتنفيذ السحب عليها.")
                return

            markup = types.InlineKeyboardMarkup(row_width=1)
            for g in gws:
                markup.add(types.InlineKeyboardButton(f"🎲 سحب فائزين: {g['title']}", callback_data=f"draw_winners_{g['id']}"))
            bot.edit_message_text("🎲 **اختر المسابقة المراد إجراء السحب العشوائي لها:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data.startswith('draw_winners_') and chat_id == ADMIN_ID:
            gw_id = int(call.data.replace('draw_winners_', ''))
            gw_res = supabase.table("giveaways").select("*").eq("id", gw_id).execute()
            if not gw_res.data:
                return

            gw = gw_res.data[0]
            parts_res = supabase.table("giveaway_participants").select("user_id").eq("giveaway_id", gw_id).execute()
            participants = [p['user_id'] for p in parts_res.data] if parts_res.data else []

            if not participants:
                bot.send_message(chat_id, "❌ لا يوجد مشاركين بهذه المسابقة لإجراء السحب!")
                return

            winner_count = min(len(participants), int(gw['winners_count']))
            winners = random.sample(participants, winner_count)

            supabase.table("giveaways").update({"is_active": 0}).eq("id", gw_id).execute()

            winners_text = ""
            for w_id in winners:
                update_points(w_id, float(gw['prize_points']))
                winners_text += f"• `{w_id}` (تم إضافة {gw['prize_points']} نقطة)\n"
                try:
                    bot.send_message(w_id, f"🎉 **مبروك! لقد فزت بالمسابقة: {gw['title']}**", parse_mode="Markdown")
                except Exception:
                    pass

            bot.send_message(ADMIN_ID, f"🎉 **تم إجراء السحب العشوائي للمسابقة ({gw['title']}) بنجاح!**\n\n🏆 **الفائزون:**\n{winners_text}", parse_mode="Markdown")

        elif call.data == 'adm_menu_system' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("📢 إذاعة مع التثبيت والخيارات", callback_data='adm_targeted_broadcast'),
                types.InlineKeyboardButton("📊 تحليل سلوك وأوقات الزبائن", callback_data='adm_behavior_analytics'),
                types.InlineKeyboardButton("📈 تقرير الأرباح المتقدم والتوب", callback_data='adm_stats'),
                types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data='admin_panel')
            )
            bot.edit_message_text("⚙️ **قسم إعدادات النظام والإذاعات:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data == 'adm_targeted_broadcast' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("📢 إذاعة لجميع الأعضاء (عادية)", callback_data='bc_type_all'),
                types.InlineKeyboardButton("📌 إذاعة لجميع الأعضاء + تثبيت", callback_data='bc_type_pin'),
                types.InlineKeyboardButton("🌙 إذاعة للمستخدمين الخاملين فقط", callback_data='bc_type_inactive'),
                types.InlineKeyboardButton("🔙 رجوع", callback_data='adm_menu_system')
            )
            bot.edit_message_text("📢 **اختر نوع الإذاعة المطلوبة:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data.startswith('bc_type_') and chat_id == ADMIN_ID:
            b_type = call.data.replace('bc_type_', '')
            admin_states[chat_id] = {'action': 'broadcast', 'type': b_type}
            
            text_req = "📢 **أرسل الآن الرسالة لإذاعتها:**"
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data='adm_targeted_broadcast'))
            bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_admin_broadcast_execution)

        elif call.data == 'adm_behavior_analytics' and chat_id == ADMIN_ID:
            res_orders = supabase.table("user_orders").select("*").execute()
            orders = res_orders.data if res_orders.data else []
            total_orders = len(orders)
            if total_orders == 0:
                bot.send_message(chat_id, "📊 **لا توجد بيانات كافية لتحليل سلوك الزبائن حالياً.**", parse_mode="Markdown")
                return

            morning_cnt = sum(1 for o in orders if 6 <= time.localtime(o.get('created_at_ts', time.time())).tm_hour < 12)
            evening_cnt = sum(1 for o in orders if 12 <= time.localtime(o.get('created_at_ts', time.time())).tm_hour < 18)
            night_cnt = total_orders - (morning_cnt + evening_cnt)

            text = (
                f"📊 **تقرير تحليل سلوك ودراسة الزبائن:**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"🛍️ **إجمالي الطلبات الكلي:** `{total_orders}` طلب\n\n"
                f"• 🌅 الفترة الصباحية: `{morning_cnt}` طلب\n"
                f"• ☀️ الفترة المسائية: `{evening_cnt}` طلب\n"
                f"• 🌙 الفترة الليلية: `{night_cnt}` طلب"
            )
            bot.send_message(chat_id, text, parse_mode="Markdown")

        elif call.data == 'adm_stats' and chat_id == ADMIN_ID:
            res_users = supabase.table("users").select("user_id, first_name, total_spent").order("total_spent", desc=True).limit(5).execute()
            top_users = res_users.data if res_users.data else []
            
            res_orders = supabase.table("user_orders").select("*").execute()
            orders_list = res_orders.data if res_orders.data else []
            orders_c = len(orders_list)
            
            total_revenue = sum(float(o.get('price', 0)) for o in orders_list)
            total_cost = 0.0
            for o in orders_list:
                s_name = o.get('service')
                for k, v in SERVICES.items():
                    if v['name'] == s_name:
                        total_cost += v.get('cost', float(o.get('price', 0)) * 0.5)
                        break

            net_profit_points = round(total_revenue - total_cost, 2)
            top_str = ""
            for idx, tu in enumerate(top_users, 1):
                top_str += f"{idx}. {tu.get('first_name', 'مستخدم')} (أنفق: {tu.get('total_spent', 0)} ن)\n"

            text = (
                f"📊 **تقرير الأرباح الإحصائي المتقدم:**\n\n"
                f"📦 **إجمالي الطلبات المنفذة:** {orders_c}\n"
                f"💰 **إجمالي المبيعات:** {round(total_revenue, 2)} نقطة\n"
                f"📈 **صافي الربح التقديري:** {net_profit_points} نقطة\n\n"
                f"🏆 **أعلى 5 مستخدمين إنفاقاً:**\n{top_str}"
            )
            bot.send_message(chat_id, text, parse_mode="Markdown")

        elif call.data == 'adm_maint_control_menu' and chat_id == ADMIN_ID:
            m_status = "مفعل 🛠️" if is_maintenance() else "معطل 🟢"
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton(f"🛠️ تغيير صيانة البوت الكلي ({m_status})", callback_data='adm_toggle_maint'),
                types.InlineKeyboardButton("🔘 صيانة أزرار وقوائم البوت العامة", callback_data='adm_maint_buttons_menu'),
                types.InlineKeyboardButton("📂 صيانة الأقسام والخدمات", callback_data='adm_maint_services_by_cat'),
                types.InlineKeyboardButton("🔙 رجوع للوحة الإدارة", callback_data='admin_panel')
            )
            bot.edit_message_text("🛠️ **إدارة صيانة الأزرار والأقسام الشاملة:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data == 'adm_toggle_maint' and chat_id == ADMIN_ID:
            toggle_maintenance()
            bot.send_message(chat_id, f"✅ تم تبديل حالة صيانة البوت الكلي بنجاح.")

        elif call.data == 'adm_maint_buttons_menu' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=2)
            buttons_list = [
                ('top_services', '🔥 الأكثر طلباً'),
                ('view_my_cart', '🛒 سلة الشراء'),
                ('active_giveaways', '🎯 المسابقات'),
                ('transfer_points', '🔄 تحويل نقاط'),
                ('ranks_info', '🎖️ نظام الرتب'),
                ('referral_menu', '👥 دعوة الأصدقاء'),
                ('daily_reward', '🎁 مكافأة يومية'),
                ('my_orders', '📦 طلباتي والتتبع'),
                ('asiacell_recharge_menu', '💰 شحن آسياسيل'),
                ('support_btn', '👨‍💻 الدعم الفني')
            ]
            for btn_key, btn_name in buttons_list:
                st = "🛠️ (صيانة)" if is_item_in_maintenance(btn_key) else "🟢 (شغال)"
                markup.add(types.InlineKeyboardButton(f"{btn_name} - {st}", callback_data=f"toggle_maint_{btn_key}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='adm_maint_control_menu'))
            bot.edit_message_text("🔘 **صيانة أزرار البوت الرئيسية:**\nاضغط على الزر لتفعيل أو إلغاء الصيانة عنه:", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data == 'adm_maint_categories' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for cat_key, cat_name in CATEGORIES.items():
                st = "🛠️ (صيانة)" if is_item_in_maintenance(cat_key) else "🟢 (شغال)"
                markup.add(types.InlineKeyboardButton(f"{cat_name} - {st}", callback_data=f"toggle_maint_{cat_key}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='adm_maint_control_menu'))
            bot.edit_message_text("📂 **صيانة الأقسام الرئيسية:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data == 'adm_maint_services_by_cat' and chat_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("📸 صيانة خدمات الانستغرام", callback_data='insta_menu'),
                types.InlineKeyboardButton("✈️ صيانة خدمات التليجرام", callback_data='telegram_menu'),
                types.InlineKeyboardButton("🎮 صيانة خدمات الألعاب", callback_data='games_menu'),
                types.InlineKeyboardButton("🍎 صيانة بطاقات آيتونز", callback_data='cat_itunes'),
                types.InlineKeyboardButton("📱 صيانة شرائح eSIM", callback_data='cat_esim'),
                types.InlineKeyboardButton("🔙 رجوع", callback_data='adm_maint_control_menu')
            )
            bot.edit_message_text("🛠️ **اختر القسم الرئيسي:**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data.startswith('maint_group_opt_') and chat_id == ADMIN_ID:
            opt_type = call.data.replace('maint_group_opt_', '')
            keys_map = {
                'tg_opt_fixed': ['tg_sub_fixed_1k', 'tg_sub_fixed_2k', 'tg_sub_fixed_5k'],
                'tg_opt_20d': ['tg_sub_20d_1k', 'tg_sub_20d_2k', 'tg_sub_20d_5k'],
                'tg_opt_vip_30d': ['tg_vip_30d_1k', 'tg_vip_30d_2k', 'tg_vip_30d_5k'],
                'tg_opt_bot_start': ['tg_bot_start_1k', 'tg_bot_start_2k', 'tg_bot_start_5k'],
                'tg_opt_no_drop': ['tg_vip_no_drop_1k', 'tg_vip_no_drop_2k', 'tg_vip_no_drop_5k'],
                'tg_opt_boost': ['tg_boost_1d_1k', 'tg_boost_1d_2k', 'tg_boost_1d_5k']
            }
            if opt_type in keys_map:
                group_keys = keys_map[opt_type]
                all_maint = all(is_item_in_maintenance(k) for k in group_keys)
                target_state = not all_maint
                for r_key in group_keys:
                    if target_state:
                        maintenance_items.add(r_key)
                    else:
                        if r_key in maintenance_items:
                            maintenance_items.remove(r_key)
                bot.send_message(chat_id, f"✅ **تم تغيير حالة صيانة الفئة بنجاح!**")

        elif call.data.startswith('toggle_maint_') and chat_id == ADMIN_ID:
            item_key = call.data.replace('toggle_maint_', '')
            is_now_maint = toggle_item_maintenance(item_key)
            status_txt = "🛠️ (صيانة)" if is_now_maint else "🟢 (شغالة)"
            bot.send_message(chat_id, f"✅ تم تحديث حالة العنصر إلى: {status_txt}")

        elif call.data in SERVICES:
            data = SERVICES[call.data]
            if chat_id == ADMIN_ID and 'صيانة' in (call.message.text or ''):
                return

            if is_item_in_maintenance(call.data) and chat_id != ADMIN_ID:
                bot.send_message(chat_id, "🛠️ هذه الخدمة قيد الصيانة حالياً.")
                return

            srv_key = call.data

            if data.get('is_custom_tiers') and 'tiers' in data:
                markup = types.InlineKeyboardMarkup(row_width=2)
                for t in data['tiers']:
                    t_qty = t['qty']
                    t_price = get_service_price(chat_id, t['price'])
                    btn_label = f"{t_qty} ({t_price} نقطة)"
                    markup.add(types.InlineKeyboardButton(btn_label, callback_data=f"buytier_{srv_key}_{t_qty}"))
                
                markup.add(types.InlineKeyboardButton("✍️ اختيار العدد بنفسك (يدوي)", callback_data=f"custom_{srv_key}"))
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=data.get('category', 'back_start')))
                
                text_menu = f"📦 **{data['name']}**\n━━━━━━━━━━━━━━━━━━━\n\nاختر الكمية المطلوبة من الأزرار أدناه أو أدخلها يدوياً:"
                try:
                    bot.edit_message_text(text_menu, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
                except Exception:
                    bot.send_message(chat_id, text_menu, reply_markup=markup, parse_mode="Markdown")
                return

            if data.get('category') in ['cat_itunes', 'cat_esim'] or data.get('service_id') == 0:
                final_price = get_service_price(chat_id, data.get('price', 1.0))
                
                pending_orders_cache[chat_id] = {
                    'service_id': 0,
                    'qty': 1,
                    'name': data['name'],
                    'price': final_price,
                    'link': 'بطاقة رقمية / خدمة مباشرة'
                }
                
                markup_confirm = types.InlineKeyboardMarkup(row_width=1)
                markup_confirm.add(
                    types.InlineKeyboardButton("🛒 إضافة لسلة المشتريات", callback_data='add_to_cart_now'),
                    types.InlineKeyboardButton("✅ تأكيد الشراء الآن", callback_data='confirm_order_now'),
                    types.InlineKeyboardButton("❌ إلغاء الطلب", callback_data='cancel_order_now'),
                    types.InlineKeyboardButton("🔙 رجوع", callback_data=data.get('category', 'back_start'))
                )
                
                text_confirm = (
                    f"🧾 **تأكيد ملخص الطلب:**\n"
                    f"━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📦 المنتج: {data['name']}\n"
                    f"💰 السعر النهائي: `{final_price}` نقطة"
                )
                
                try:
                    bot.edit_message_text(text_confirm, chat_id, message_id, reply_markup=markup_confirm, parse_mode="Markdown")
                except Exception:
                    bot.send_message(chat_id, text_confirm, reply_markup=markup_confirm, parse_mode="Markdown")
                return

            base_price = float(data.get('price', 1.0))
            final_price = get_service_price(chat_id, base_price)
            api_qty = data.get('qty', 1000)

            text_req = (
                f"📦 **{data['name']}**\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔗 {data.get('msg', 'أرسل الرابط المطلوب:')}\n"
                f"*(السعر: {final_price} نقطة)*"
            )
            
            markup_back = types.InlineKeyboardMarkup()
            markup_back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=data.get('category', 'back_start')))
            
            try:
                bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
            except Exception:
                bot.send_message(chat_id, text_req, reply_markup=markup_back, parse_mode="Markdown")

            if data['service_id'] == 0:
                bot.register_next_step_handler(call.message, prepare_order_summary_direct, final_price, data['name'])
            else:
                bot.register_next_step_handler(call.message, prepare_order_summary, final_price, data['service_id'], api_qty, data['name'])

        elif call.data.startswith('buytier_'):
            try:
                _, srv_key, qty_str = call.data.split('_', 2)
                target_qty = int(qty_str)
                if srv_key in SERVICES:
                    s_data = SERVICES[srv_key]
                    selected_tier = next((t for t in s_data.get('tiers', []) if t['qty'] == target_qty), None)
                    if selected_tier:
                        final_price = get_service_price(chat_id, selected_tier['price'])
                        api_qty_to_send = selected_tier['api_qty']
                        
                        text_req = f"🔗 {s_data.get('msg', 'أرسل الرابط المطلوب:')}\n*(الكمية المختارة: {target_qty} - السعر: {final_price} نقطة)*"
                        markup_back = types.InlineKeyboardMarkup()
                        markup_back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=srv_key))
                        
                        bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
                        bot.register_next_step_handler(call.message, prepare_order_summary_with_api_qty, final_price, s_data['service_id'], api_qty_to_send, f"{s_data['name']} ({target_qty})")
            except Exception as e:
                print(f"Error in buytier handler: {e}")

        elif call.data.startswith('buyqty_'):
            parts = call.data.split('_')
            if len(parts) >= 3:
                srv_key = parts[1]
                qty = int(parts[2])
                
                if srv_key in SERVICES:
                    s_data = SERVICES[srv_key]
                    price_per_1k = s_data.get('price', 1.0)
                    total_price = round((price_per_1k / 1000.0) * qty, 2)
                    final_price = get_service_price(chat_id, total_price)
                    
                    text_req = f"🔗 {s_data.get('msg', 'أرسل الرابط المطلوب:')}\n*(الكمية: {qty} - السعر: {final_price} نقطة)*"
                    markup_back = types.InlineKeyboardMarkup()
                    markup_back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=srv_key))
                    
                    bot.edit_message_text(text_req, chat_id, message_id, reply_markup=markup_back, parse_mode="Markdown")
                    
                    if s_data['service_id'] == 0:
                        bot.register_next_step_handler(call.message, prepare_order_summary_direct, final_price, f"{s_data['name']} ({qty})")
                    else:
                        bot.register_next_step_handler(call.message, prepare_order_summary, final_price, s_data['service_id'], qty, f"{s_data['name']} ({qty})")

        elif call.data == 'confirm_order_now':
            order_data = pending_orders_cache.get(chat_id)
            if not order_data:
                bot.send_message(chat_id, "⚠️ انتهت جلسة الطلب، يرجى إعادة المحاولة.")
                return

            final_price = order_data['price']
            user_points = get_points(chat_id)

            if user_points < final_price:
                bot.send_message(chat_id, f"⚠️ رصيدك غير كافٍ!\nرصيدك: {user_points} نقطة\nالمطلوب: {final_price} نقطة")
                return

            update_points(chat_id, -final_price)
            del pending_orders_cache[chat_id]

            if order_data['service_id'] > 0:
                bot.send_message(chat_id, "⏳ **جاري إرسال طلبك عبر الـ API...**", parse_mode="Markdown")
                res = send_to_api(order_data['service_id'], order_data['link'], order_data['qty'])
                if res and isinstance(res, dict) and 'order' in res:
                    username = call.from_user.username or "غير معروف"
                    order_id = get_next_order_id()
                    api_id = res['order']
                    save_order(order_id, chat_id, username, order_data['name'], final_price, api_id, order_data['link'], order_data['service_id'], order_data['qty'])
                    bot.send_message(chat_id, f"✅ **تم إرسال طلبك بنجاح!**\n🆔 رقم الطلب: `{order_id}`\n🔖 رقم الـ API: `{api_id}`", parse_mode="Markdown")
                    send_proof_to_channel(chat_id, order_id, order_data['name'], order_data['qty'], api_id)
                    notify_admin_new_order(chat_id, username, order_id, order_data['name'], final_price, order_data['link'])
                else:
                    update_points(chat_id, final_price)
                    bot.send_message(chat_id, f"❌ **فشل إرسال الطلب، تم إعادة النقاط لرصيدك تلقائياً.**", parse_mode="Markdown")
            else:
                order_id = get_next_order_id()
                username = call.from_user.username or "لا يوجد"
                link_info = order_data.get('link', 'خدمة مباشرة')
                save_order(order_id, chat_id, username, order_data['name'], final_price, "0", link_info, 0, 1)
                bot.send_message(ADMIN_ID, f"📦 **طلب جديد (يدوي/لعبة):**\n🆔 رقم الطلب: `{order_id}`\n👤 المستخدم: `{chat_id}` (@{username})\n📦 الخدمة: {order_data['name']}\n🎮 التفاصيل: `{link_info}`", parse_mode="Markdown")
                bot.send_message(chat_id, f"✅ **تم استلام طلبك بنجاح!**\n🆔 رقم الطلب: `{order_id}`\n📩 تواصل مع الدعم لاستلام الطلب: {SUPPORT_USER}", parse_mode="Markdown")
                send_proof_to_channel(chat_id, order_id, order_data['name'], 1, link_info)

        elif call.data == 'cancel_order_now':
            if chat_id in pending_orders_cache:
                del pending_orders_cache[chat_id]
            bot.send_message(chat_id, "❌ **تم إلغاء الطلب.**", parse_mode="Markdown")

    except Exception as e:
        print(f"Callback Error: {e}")

def process_admin_user_search(message):
    chat_id = message.chat.id
    if chat_id != ADMIN_ID: return
    query_str = message.text.strip()
    u = find_user_by_id_or_username(query_str)
    
    if not u:
        bot.send_message(chat_id, "❌ **لم يتم العثور على هذا المستخدم في قاعدة البيانات!**", parse_mode="Markdown")
        return
        
    uid = u['user_id']
    uname = u.get('username', 'لا يوجد')
    fname = u.get('first_name', 'بدون اسم')
    pts = u.get('points', 0.0)
    recharged = u.get('total_recharged', 0.0)
    spent = u.get('total_spent', 0.0)
    is_res = "نعم 🕶️" if u.get('is_reseller') == 0 else "وكيل معتمد 🏆"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 تعديل الرصيد (إضافة/خصم)", callback_data=f"admin_add_pts_{uid}"),
        types.InlineKeyboardButton("💬 إرسال رسالة مباشرة", callback_data=f"admin_msg_{uid}"),
        types.InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")
    )
    
    text = (
        f"👤 **معلومات المستخدم:**\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 الآيدي: `{uid}`\n"
        f"🔹 الاسم: {fname}\n"
        f"🔹 اليوزر: @{uname}\n"
        f"💰 الرصيد الحالي: `{pts}` نقطة\n"
        f"💳 إجمالي الشحن: `{recharged}` نقطة\n"
        f"🛍️ إجمالي الإنفاق: `{spent}` نقطة\n"
        f"🎖️ رتبة الوكيل: {is_res}"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

def process_admin_promote_reseller(message):
    chat_id = message.chat.id
    if chat_id != ADMIN_ID: return
    try:
        target_uid = int(message.text.strip())
        promote_user_to_reseller(ADMIN_ID, target_uid)
    except ValueError:
        bot.send_message(chat_id, "⚠️ يرجى إدخال ID صحيح بالأرقام فقط.")

def process_admin_modify_points(message):
    chat_id = message.chat.id
    if chat_id != ADMIN_ID: return
    st = admin_states.get(chat_id)
    if not st or st.get('action') != 'add_pts':
        return
    target_uid = st.get('target')
    try:
        val = float(message.text.strip())
        update_points(target_uid, val)
        bot.send_message(chat_id, f"✅ **تم تعديل رصيد المستخدم (`{target_uid}`) بمقدار ({val}) نقطة بنجاح!**", parse_mode="Markdown")
        try:
            bot.send_message(target_uid, f"🎁 **تم تحديث رصيدك من قبل الإدارة بمقدار ({val}) نقطة!**", parse_mode="Markdown")
        except Exception:
            pass
        del admin_states[chat_id]
    except ValueError:
        bot.send_message(chat_id, "⚠️ يرجى إدخال رقم صحيح بالنقاط.")

def process_admin_send_direct_msg(message):
    chat_id = message.chat.id
    if chat_id != ADMIN_ID: return
    st = admin_states.get(chat_id)
    if not st or st.get('action') != 'send_msg':
        return
    target_uid = st.get('target')
    msg_text = message.text.strip()
    try:
        bot.send_message(target_uid, f"📬 **رسالة إدارية خاصة:**\n\n{msg_text}", parse_mode="Markdown")
        bot.send_message(chat_id, f"✅ **تم إرسال الرسالة للمستخدم (`{target_uid}`) بنجاح!**", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(chat_id, f"❌ فشل إرسال الرسالة: {e}")
    del admin_states[chat_id]

def process_admin_broadcast_execution(message):
    chat_id = message.chat.id
    if chat_id != ADMIN_ID: return
    st = admin_states.get(chat_id)
    if not st or st.get('action') != 'broadcast':
        return
    b_type = st.get('type')
    del admin_states[chat_id]
    
    try:
        res = supabase.table("users").select("user_id, last_order_ts").execute()
        users = res.data if res.data else []
    except Exception:
        users = []

    if not users:
        bot.send_message(chat_id, "❌ لا يوجد مستخدمين لإذاعة الرسالة لهم.")
        return

    success = 0
    now = time.time()
    for u in users:
        uid = u['user_id']
        if b_type == 'inactive':
            last_o = u.get('last_order_ts', 0)
            if now - last_o < 604800:
                continue
                
        try:
            sent_msg = bot.copy_message(chat_id=uid, from_chat_id=chat_id, message_id=message.message_id)
            if b_type == 'pin':
                try:
                    bot.pin_chat_message(chat_id=uid, message_id=sent_msg.message_id)
                except Exception:
                    pass
            success += 1
            time.sleep(0.05)
        except Exception:
            pass
            
    bot.send_message(chat_id, f"✅ **تمت الإذاعة بنجاح!**\nوصلت إلى: `{success}` مستخدم.", parse_mode="Markdown")

def process_asiacell_phone_input(message):
    chat_id = message.chat.id
    raw_text = message.text.strip()
    
    if chat_id not in temp_recharge_phone_states:
        return
        
    amount_k = temp_recharge_phone_states[chat_id]['amount_k']
    del temp_recharge_phone_states[chat_id]
    
    phone_match = re.search(r'(07\d{9})', raw_text)
    if not phone_match:
        bot.send_message(chat_id, "❌ **رقم الهاتف غير صحيح!** يرجى التأكد وإعادة المحاولة من القائمة الرئيسية.")
        return
        
    user_phone = phone_match.group(1)
    points_to_get = round(float(amount_k) * 0.92, 2)
    
    user_recharge_states[chat_id] = {
        'amount_k': amount_k,
        'points': points_to_get,
        'phone': user_phone
    }
    
    transfer_code = f"*123*{amount_k * 1000}*{RECEIVER_PHONE}*1#"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 اختيار مبلغ آخر", callback_data='asiacell_recharge_menu'))
    
    bot.send_message(
        chat_id,
        f"✅ **تم تسجيل رقمك بنجاح:** `{user_phone}`\n\n"
        f"📲 **خطوات التحويل لـ {amount_k} ألف آسياسيل:**\n"
        f"1️⃣ قم بتحويل رصيد بقيمة **{amount_k},000 دينار** من رقمك المسجل إلى رقمنا:\n"
        f"`{RECEIVER_PHONE}`\n\n"
        f"💡 (أو انسخ كود التحويل السريع التالي واتصل به):\n"
        f"`{transfer_code}`\n\n"
        f"⏳ **بانتظار إتمام التحويل من خطك ومطابقة الرقم أوتوماتيكياً...**",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.chat.id == ADMIN_ID and message.text and not message.text.startswith('/'))
def handle_incoming_sms_forward(message):
    text = message.text.strip()
    
    all_numbers = re.findall(r'\d+', text.replace(',', ''))
    if not all_numbers:
        return
    
    sender_phone_in_sms = None
    for num in all_numbers:
        if (num.startswith('07') and len(num) == 11) or (num.startswith('7') and len(num) == 10):
            if len(num) == 10:
                sender_phone_in_sms = "0" + num
            else:
                sender_phone_in_sms = num
            break

    transfer_amount_k = None
    for num_str in all_numbers:
        val = int(num_str)
        if val in range(1, 11) or val in [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000]:
            if val >= 1000:
                transfer_amount_k = val // 1000
            else:
                transfer_amount_k = val
            break

    if not transfer_amount_k or not sender_phone_in_sms:
        bot.send_message(
            ADMIN_ID, 
            f"⚠️ **[تنبيه تحليل] لم يتم التعرف على الرقم أو المبلغ بدقة:**\n\n📄 **النص الوارد:**\n`{text}`", 
            parse_mode="Markdown"
        )
        return

    matched_user_id = None
    points_to_add = 0.0
    clean_sms_phone = sender_phone_in_sms[-10:]

    for uid, state in list(user_recharge_states.items()):
        if state['amount_k'] == transfer_amount_k:
            state_phone = state.get('phone', '')
            clean_state_phone = state_phone[-10:]
            if not clean_state_phone or clean_sms_phone == clean_state_phone:
                matched_user_id = uid
                points_to_add = state['points']
                del user_recharge_states[uid]
                break

    if matched_user_id:
        update_points(matched_user_id, points_to_add, is_recharge=True)
        bot.send_message(
            matched_user_id, 
            f"🎉 **تم التحقق من تحويلك بقيمة ({transfer_amount_k} ألف دينار) بنجاح!**\n⭐ تم إضافة `{points_to_add}` نقطة إلى رصيدك تلقائياً ⚡", 
            parse_mode="Markdown"
        )
        bot.send_message(
            ADMIN_ID, 
            f"✅ **تمت المطابقة وإضافة النقاط بنجاح للزبون:** `{matched_user_id}`\n💰 المبلغ: `{transfer_amount_k} ألف`", 
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            ADMIN_ID, 
            f"⚠️ **[كشف خطأ] رقم الهاتف أو المبلغ غير مطابق لجلسة مفتوحة**\n\n"
            f"📱 **الرقم المستخرج:** `{sender_phone_in_sms}`\n"
            f"💰 **المبلغ المستخرج:** `{transfer_amount_k} ألف`\n"
            f"📄 **النص الوارد:**\n`{text}`", 
            parse_mode="Markdown"
        )

def process_admin_edit_desc(message):
    chat_id = message.chat.id
    st = admin_states.get(chat_id)
    if not st or st.get('action') != 'edit_desc':
        return
    menu_key = st.get('menu_key')
    new_desc = message.text.strip()
    set_menu_description(menu_key, new_desc)
    bot.send_message(chat_id, f"✅ **تم حفظ وتحديث وصف القسم بنجاح!**\n\nالنص الجديد:\n{new_desc}")
    del admin_states[chat_id]

def step_add_category_key(message):
    chat_id = message.chat.id
    cat_key = message.text.strip().lower()
    if not cat_key.startswith('cat_'): 
        cat_key = f"cat_{cat_key}"
    temp_add_service[chat_id] = {'new_cat_key': cat_key}
    msg = bot.send_message(chat_id, "📁 **أدخل اسم القسم الذي سيظهر للمستخدمين:**", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_add_category_name)

def step_add_category_name(message):
    chat_id = message.chat.id
    cat_name = message.text.strip()
    data = temp_add_service.get(chat_id)
    if not data: 
        return
    cat_key = data['new_cat_key']
    CATEGORIES[cat_key] = cat_name
    bot.send_message(chat_id, f"✅ **تم إضافة القسم الجديد ({cat_name}) بنجاح!**", parse_mode="Markdown")
    del temp_add_service[chat_id]

def step_srv_name(message):
    chat_id = message.chat.id
    if chat_id not in temp_add_service:
        temp_add_service[chat_id] = {'category': 'cat_insta'}
    temp_add_service[chat_id]['name'] = message.text.strip()
    msg = bot.send_message(chat_id, "🆔 أرسل Service ID (أو 0 لليدوي):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_srv_id)

def step_srv_id(message):
    chat_id = message.chat.id
    try:
        temp_add_service[chat_id]['service_id'] = int(message.text.strip())
        msg = bot.send_message(
            chat_id, 
            "⚙️ أرسل التيرات بالصيغة:\n`الكمية:السعر:كمية_API`\n\n*مثال:* `1000:1.5:1100 2000:3.0:2200`", 
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, step_srv_save_final)
    except ValueError:
        bot.send_message(chat_id, "⚠️ أدخل رقماً صحيحاً للـ ID.")

def step_srv_save_final(message):
    chat_id = message.chat.id
    srv = temp_add_service.get(chat_id)
    if not srv: 
        return
    try:
        tiers = []
        for p in message.text.strip().split():
            sub = p.split(':')
            if len(sub) == 3:
                tiers.append({
                    'qty': int(sub[0]), 
                    'price': float(sub[1]), 
                    'api_qty': int(sub[2])
                })
        
        if not tiers:
            bot.send_message(chat_id, "⚠️ الصيغة غير صحيحة! يرجى إعادة إرسال التيرات بالشكل المطلوب.")
            return
            
        key = f"custom_srv_{int(time.time())}"
        SERVICES[key] = {
            'name': srv['name'], 
            'btn_label': srv['name'][:30],
            'service_id': srv['service_id'], 
            'category': srv['category'],
            'is_custom_tiers': True, 
            'tiers': tiers
        }
        
        custom_only = {k: v for k, v in SERVICES.items() if k.startswith('custom_srv_')}
        supabase.table("settings").upsert({
            "key": "custom_services_list", 
            "val_text": json.dumps(custom_only, ensure_ascii=False)
        }, on_conflict="key").execute()
        
        bot.send_message(chat_id, "✅ **تمت إضافة وحفظ الخدمة بالتيرات بنجاح!**", parse_mode="Markdown")
        del temp_add_service[chat_id]
    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء الحفظ: {e}")

def process_generic_custom_qty(message, base_service_key):
    chat_id = message.chat.id
    
    if message.text and message.text.startswith('/'):
        return

    try:
        qty = int(message.text.strip())
        service_data = SERVICES.get(base_service_key)
        
        markup_back = types.InlineKeyboardMarkup()
        markup_back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='start'))

        if qty < 100 or qty > 100000:
            bot.send_message(chat_id, "⚠️ يرجى إدخال كمية صحيحة بين 100 و 100,000:", reply_markup=markup_back)
            return

        if not service_data:
            bot.send_message(chat_id, "❌ تعذر العثور على بيانات الخدمة.", reply_markup=markup_back)
            return

        price_per_1000 = service_data.get('price', 1.0)
        cost_for_qty = (qty / 1000.0) * price_per_1000
        final_price = get_service_price(chat_id, cost_for_qty)

        msg_prompt = service_data.get('msg', 'أرسل الرابط المطلوب:')

        msg = bot.send_message(chat_id, f"{msg_prompt}\n(السعر النهائي لـ {qty} وحدة: {final_price} نقطة)", reply_markup=markup_back)
        bot.register_next_step_handler(msg, prepare_order_summary, final_price, service_data['service_id'], qty, f"{service_data['name']} ({qty})")

    except ValueError:
        markup_back = types.InlineKeyboardMarkup()
        markup_back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='start'))
        bot.send_message(chat_id, "⚠️ يرجى إدخال أرقام صحيحة فقط:", reply_markup=markup_back)

def process_update_single_price(message, service_key):
    try:
        new_price = float(message.text.strip())
        if new_price <= 0:
            bot.send_message(message.chat.id, "❌ السعر يجب أن يكون أكبر من 0.")
            return

        old_price = SERVICES[service_key].get('price', 0)
        SERVICES[service_key]['price'] = new_price

        bot.send_message(
            message.chat.id,
            f"✅ **تم تحديث سعر الخدمة بنجاح!**\n\n📌 الخدمة: {SERVICES[service_key]['name']}\n💰 السعر القديم: `{old_price}`\n🏷️ السعر الجديد: `{new_price}`",
            parse_mode="Markdown"
        )
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ يرجى إدخال رقم صحيح.")

def process_update_bulk_price_decrease(message):
    try:
        pct = float(message.text.strip())
        if pct <= 0:
            bot.send_message(message.chat.id, "⚠️ النسبة يجب أن تكون أكبر من 0.")
            return
        multiplier = 1 - (pct / 100)
        for k in SERVICES:
            old_p = SERVICES[k].get('price', 1.0)
            SERVICES[k]['price'] = max(0.1, round(old_p * multiplier, 2))
        bot.send_message(message.chat.id, f"✅ **تم خفض جميع أسعار البوت بنسبة ({pct}%) بنجاح!**", parse_mode="Markdown")
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ يرجى إدخال نسبة مئوية صحيحة.")

def process_update_bulk_price_increase(message):
    try:
        pct = float(message.text.strip())
        if pct <= 0:
            bot.send_message(message.chat.id, "⚠️ النسبة يجب أن تكون أكبر من 0.")
            return
        multiplier = 1 + (pct / 100)
        for k in SERVICES:
            old_p = SERVICES[k].get('price', 1.0)
            SERVICES[k]['price'] = round(old_p * multiplier, 2)
        bot.send_message(message.chat.id, f"✅ **تم زيادة جميع أسعار البوت بنسبة ({pct}%) بنجاح!**", parse_mode="Markdown")
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ يرجى إدخال نسبة مئوية صحيحة.")

def process_gen_card(message):
    try:
        amount = float(message.text.strip())
        if amount <= 0: return
        code_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        card_code = f"CARD-{code_suffix}"
        supabase.table("vouchers").insert({"code": card_code, "amount": amount}).execute()
        bot_username = bot.get_me().username
        direct_link = f"https://t.me/{bot_username}?start={card_code}"
        bot.send_message(message.chat.id, f"✅ **تم إنشاء كود الشحن الفردي:**\n💰 القيمة: {amount}\n🔑 الكود: `{card_code}`\n🔗 الرابط المباشر:\n`{direct_link}`", parse_mode="Markdown")
    except Exception:
        bot.send_message(message.chat.id, "⚠️ خطأ في إدخال القيمة.")

def process_gen_gift_code(message):
    try:
        parts = message.text.strip().split()
        code = parts[0].upper()
        pts = float(parts[1])
        uses = int(parts[2])

        supabase.table("gift_codes").insert({"code": code, "points": pts, "max_uses": uses, "used_count": 0}).execute()
        bot.send_message(message.chat.id, f"✅ **تم إنشاء كود الهدية العامة:**\n🔑 الكود: `{code}`\n💰 النقاط: {pts}\n👥 السعة: لـ {uses} شخص", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ خطأ في الإدخال: {e}")

def process_create_giveaway(message):
    try:
        parts = [p.strip() for p in message.text.split('-')]
        title = parts[0]
        pts = float(parts[1])
        winners = int(parts[2])

        supabase.table("giveaways").insert({"title": title, "prize_points": pts, "winners_count": winners, "is_active": 1}).execute()
        bot.send_message(message.chat.id, f"🎉 **تم نشر المسابقة بنجاح!**\n🏆 العنوان: {title}\n💰 الجائزة: {pts} نقطة\n👥 عدد الفائزين: {winners}", parse_mode="Markdown")
        
        try:
            bot_username = bot.get_me().username
            gw_text = f"🎯 **مسابقة جديدة في البوت!**\n\n🏆 العنوان: {title}\n💰 جائزة الفائز: {pts} نقطة\n👥 عدد الفائزين: {winners}\n\n👉 شارك الآن عبر الرابط:\nhttps://t.me/{bot_username}"
            bot.send_message(PROOFS_CHANNEL, gw_text, parse_mode="Markdown")
        except Exception:
            pass
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ خطأ بالإدخال: {e}")

def process_transfer_target_id(message):
    chat_id = message.chat.id
    try:
        target_id = int(message.text.strip())
        if target_id == chat_id:
            bot.send_message(chat_id, "❌ لا يمكنك تحويل النقاط لنفسك!")
            return
        if not get_user(target_id):
            bot.send_message(chat_id, "❌ المستلم غير موجود بالبوت!")
            return
        transfer_cache[chat_id] = {'target_id': target_id}
        msg = bot.send_message(chat_id, "💰 **أدخل عدد النقاط المراد تحويلها (عمولة 5%):**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_transfer_amount)
    except ValueError:
        bot.send_message(chat_id, "⚠️ أدخل ID صحيح بالأرقام فقط.")

def process_transfer_amount(message):
    chat_id = message.chat.id
    try:
        amount = float(message.text.strip())
        if get_points(chat_id) < amount or amount <= 0:
            bot.send_message(chat_id, "⚠️ رصيدك غير كافٍ أو المبلغ غير صحيح.")
            return
        target_id = transfer_cache.get(chat_id, {}).get('target_id')
        update_points(chat_id, -amount)
        update_points(target_id, amount * 0.95)
        bot.send_message(chat_id, f"✅ **تم تحويل {amount} نقطة بنجاح.**", parse_mode="Markdown")
        try:
            bot.send_message(target_id, f"🎉 **وصلك تحويل نقاط بقيمة {amount * 0.95} نقطة من `{chat_id}`!**", parse_mode="Markdown")
        except Exception:
            pass
    except ValueError:
        bot.send_message(chat_id, "⚠️ أدخل أرقاماً صحيحة فقط.")

def process_user_redeem_input(message):
    chat_id = message.chat.id
    raw_code = message.text.strip().upper()
    
    res = supabase.table("vouchers").select("amount").eq("code", raw_code).execute()
    if res.data:
        amt = res.data[0]['amount']
        update_points(chat_id, amt, is_recharge=True)
        supabase.table("vouchers").delete().eq("code", raw_code).execute()
        bot.send_message(chat_id, f"🎉 **تم شحن {amt} نقطة برصيدك بنجاح!**", parse_mode="Markdown")
        return

    res_gift = supabase.table("gift_codes").select("*").eq("code", raw_code).execute()
    if res_gift.data:
        g = res_gift.data[0]
        used_cnt = g.get('used_count', 0)
        max_u = g.get('max_uses', 1)
        
        if used_cnt >= max_u:
            bot.send_message(chat_id, "❌ **انتهت كمية استخدام هذا الكود!**", parse_mode="Markdown")
            return
            
        res_used = supabase.table("gift_claims").select("*").eq("code", raw_code).eq("user_id", chat_id).execute()
        if res_used.data:
            bot.send_message(chat_id, "⚠️ **لقد قمت باستخدام هذا الكود مسبقاً!**", parse_mode="Markdown")
            return

        amt = float(g['points'])
        update_points(chat_id, amt, is_recharge=True)
        supabase.table("gift_codes").update({"used_count": used_cnt + 1}).eq("code", raw_code).execute()
        supabase.table("gift_claims").insert({"code": raw_code, "user_id": chat_id}).execute()
        
        bot.send_message(chat_id, f"🎉 **مبروك! تم استبدال الكود وحصلت على ({amt}) نقطة بنجاح!**", parse_mode="Markdown")
        return

    bot.send_message(chat_id, "❌ الكود غير صحيح أو انتهت صلاحيته.")

@bot.message_handler(commands=['start', 'redeem', 'admin'])
def handle_commands(message):
    chat_id = message.chat.id
    text = message.text

    if is_banned(chat_id):
        return

    if text.startswith('/start'):
        args = text.split()
        param = args[1] if len(args) > 1 else None
        
        if param and param.startswith('CARD-'):
            message.text = param
            process_user_redeem_input(message)
            return

        referrer_id = param if param and param != str(chat_id) and param.isdigit() else None
        register_user_if_new(chat_id, message.from_user.first_name, message.from_user.username, referrer_id)
        
        if chat_id != ADMIN_ID:
            try:
                if not check_sub(chat_id):
                    markup = types.InlineKeyboardMarkup()
                    for i in range(len(CHANNELS)):
                        markup.add(types.InlineKeyboardButton("اشترك في القناة 📢", url=CHANNEL_LINKS[i]))
                    markup.add(types.InlineKeyboardButton("تحققت من الاشتراك ✅", callback_data='start'))
                    bot.send_message(chat_id, "عذراً، يجب عليك الاشتراك في القناة أولاً:", reply_markup=markup)
                    return
            except Exception:
                pass

        main_menu(chat_id)

    elif text.startswith('/redeem'):
        args = text.split(maxsplit=1)
        if len(args) > 1:
            message.text = args[1]
            process_user_redeem_input(message)

    elif text.startswith('/admin') and chat_id == ADMIN_ID:
        admin_panel_shortcut(chat_id)

if __name__ == "__main__":
    print("🚀 Bot running successfully!")
    bot.infinity_polling(timeout=10, long_polling_timeout=5, skip_pending=True)
