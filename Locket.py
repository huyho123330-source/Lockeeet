import sqlite3
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import requests
import re
from datetime import datetime, timezone

# ==================== CẤU HÌNH TOKEN & ADMIN ====================
TOKEN = "8632781019:AAH-qf97a-d4dKec0IOyMpvNXACf_m1kaRk"  

# 📌 Danh sách ID Admin
ADMIN_IDS = [
    1963443961,  # 👈 ID Admin chính của bạn
]

DEV_USERNAME = "@ngocquynh066"        # 👈 Username liên hệ Admin & Nạp tiền
DEFAULT_START_MONEY = 0               
DEFAULT_VICTIM = "heavensbrat"       # 👈 Username nạn nhân mặc định dùng chung

API_KEY = "appl_JngFETzdodyLmCREOlwTUtXdQik"
# ===============================================================

bot = telebot.TeleBot(TOKEN)

# --- QUẢN LÝ DATABASE & CẤU HÌNH (SQLITE) ---
def init_db():
    conn = sqlite3.connect("bot_vip_database.db", check_same_thread=False)
    cursor = conn.cursor()
    # Bảng người dùng
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            locket_status TEXT DEFAULT '🔒 CHƯA KÍCH HOẠT',
            state TEXT DEFAULT NULL,
            locket_username TEXT DEFAULT NULL,
            temp_data TEXT DEFAULT NULL
        )
    """)
    # Bảng mã quà tặng
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            money INTEGER,
            uses_left INTEGER DEFAULT 1
        )
    """)
    # Bảng lưu cài đặt động (Phí chạy, Thưởng giới thiệu, Nạn nhân mặc định...) lưu bền vững không mất khi restart bot
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_setting(key, default_val):
    conn = sqlite3.connect("bot_vip_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row is not None else default_val

def set_setting(key, value):
    conn = sqlite3.connect("bot_vip_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

# --- HÀM XỬ LÝ LOCKET EXPLOIT ---
def resolve_uid(name: str):
    if not name:
        return None
    if name.startswith("user:"):
        name = name[5:]
    name = name.strip().strip('/')
    if not name:
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
            "Accept": "text/html"
        }
        if "locket.cam/" in name:
            name = name.split("locket.cam/")[-1].strip('/')
            
        resp = requests.get(f"https://locket.cam/{name}", headers=headers, timeout=8, allow_redirects=True)
        html = resp.text
        m = re.search(r'invites%2F([A-Za-z0-9]{28,})', html)
        if m:
            uid_raw = m.group(1)
            if len(uid_raw) >= 28:
                return str(uid_raw[:28])
            return str(uid_raw)
        return None
    except Exception:
        return None

def get_gold_expiry(uid: str) -> str:
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "X-Platform": "iOS"
        }
        resp = requests.get(f"https://api.revenuecat.com/v1/subscribers/{uid}", headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        exp = data.get("subscriber", {}).get("entitlements", {}).get("Gold", {}).get("expires_date")
        if not exp:
            return "none"
        return str(exp)
    except Exception:
        return "none"

def test_is_gold_valid(expiry: str) -> bool:
    if not expiry or expiry in ("none", "null"):
        return False
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return expiry > now_utc

def try_alias(my_uid: str, gold_uid: str) -> str:
    body = {"new_app_user_id": gold_uid}
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "X-Platform": "iOS",
            "Content-Type": "application/json"
        }
        resp = requests.post(
            f"https://api.revenuecat.com/v1/subscribers/{my_uid}/alias",
            headers=headers,
            json=body,
            timeout=8
        )
        code = resp.status_code
        content = resp.text
        if code == 200:
            return "ok"
        if "7255" in content:
            return "limit"
        return f"error:{content}"
    except Exception as e:
        err_body = str(e)
        if "7255" in err_body:
            return "limit"
        return f"error:{err_body}"

# --- HÀM KIỂM TRA QUYỀN & DB USER ---
def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_all_admin_ids():
    return ADMIN_IDS

def notify_all_admins(text, parse_mode="HTML"):
    for aid in get_all_admin_ids():
        try:
            bot.send_message(aid, text, parse_mode=parse_mode)
        except Exception:
            pass

def get_user(user_id):
    conn = sqlite3.connect("bot_vip_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, locket_status, state, locket_username, temp_data FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_user_state(user_id, state):
    conn = sqlite3.connect("bot_vip_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET state = ? WHERE user_id = ?", (state, user_id))
    conn.commit()
    conn.close()

def update_user_temp(user_id, temp_data):
    conn = sqlite3.connect("bot_vip_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET temp_data = ? WHERE user_id = ?", (temp_data, user_id))
    conn.commit()
    conn.close()

def update_user_balance(user_id, balance):
    conn = sqlite3.connect("bot_vip_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance, user_id))
    conn.commit()
    conn.close()

def update_user_status(user_id, status):
    conn = sqlite3.connect("bot_vip_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET locket_status = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

def register_user(user_id, username, first_name):
    conn = sqlite3.connect("bot_vip_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        default_v = get_setting("global_victim", DEFAULT_VICTIM)
        cursor.execute("INSERT INTO users (user_id, username, first_name, balance, locket_username) VALUES (?, ?, ?, ?, ?)", 
                       (user_id, username, first_name, DEFAULT_START_MONEY, default_v))
    else:
        cursor.execute("UPDATE users SET locket_username = ? WHERE user_id = ? AND (locket_username IS NULL OR locket_username = '')", 
                       (get_setting("global_victim", DEFAULT_VICTIM), user_id))
    conn.commit()
    conn.close()

def get_all_user_ids():
    conn = sqlite3.connect("bot_vip_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

# --- GIAO DIỆN BÀN PHÍM CHÍNH ---
def get_main_keyboard(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🚀 NÂNG CẤP LOCKET GOLD"),
        KeyboardButton("💳 NẠP TIỀN (IB ADMIN)")
    )
    markup.add(
        KeyboardButton("💎 HỒ SƠ CÁ NHÂN"),
        KeyboardButton("🎁 GIỚI THIỆU BẠN BÈ")
    )
    markup.add(
        KeyboardButton("🎟️ NHẬP MÃ QUÀ TẶNG"),
        KeyboardButton("🛠️ HỖ TRỢ & LIÊN HỆ")
    )
    if is_admin(user_id):
        markup.add(KeyboardButton("👑 HỆ THỐNG ADMIN"))
    return markup

# --- LỆNH /START ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    args = message.text.split()
    
    register_user(user.id, user.username, user.first_name)
    update_user_state(user.id, None)
    
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].replace("ref_", ""))
            if referrer_id != user.id:
                ref_user = get_user(referrer_id)
                if ref_user:
                    current_ref_reward = int(get_setting("ref_reward", 5000))
                    new_balance = ref_user[0] + current_ref_reward
                    update_user_balance(referrer_id, new_balance)
                    bot.send_message(referrer_id, f"🎉 <b>CHÚC MỪNG!</b> Bạn nhận được <code>+{current_ref_reward:,.0f} VNĐ</code> từ liên kết giới thiệu bạn bè!", parse_mode="HTML")
        except Exception as e:
            print(f"Lỗi xử lý ref: {e}")

    user_data = get_user(user.id)
    balance = user_data[0]
    
    welcome_text = (
        f"🌟 <b>HỆ THỐNG LOCKET GOLD VIP PRO</b> 🌟\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Xin chào, <b>{user.first_name}</b>!\n"
        f"🆔 ID Tài khoản: <code>{user.id}</code>\n"
        f"💰 Số dư hiện tại: <code>{balance:,.0f} VNĐ</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <i>Hệ thống tự động kích hoạt Gold nhanh chóng, an toàn và ổn định 24/7. Vui lòng chọn chức năng bên dưới:</i>"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML", reply_markup=get_main_keyboard(user.id))

# --- CÁC LỆNH QUẢN TRỊ ADMIN ---
@bot.message_handler(commands=['setref'])
def admin_set_ref(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            current_val = int(get_setting("ref_reward", 5000))
            bot.reply_to(message, f"⚠️ Cú pháp: /setref [số_tiền]\n💰 Mức thưởng giới thiệu hiện tại: <code>{current_val:,.0f} VNĐ</code>", parse_mode="HTML")
            return
            
        new_reward = int(parts[1])
        set_setting("ref_reward", new_reward)
        bot.reply_to(message, f"✅ <b>ĐÃ CẬP NHẬT TIỀN THƯỞNG GIỚI THIỆU!</b>\n🎁 Mức thưởng mới: <code>{new_reward:,.0f} VNĐ / lượt</code>", parse_mode="HTML")
        notify_all_admins(f"🔄 Admin vừa thay đổi tiền thưởng giới thiệu thành: <code>{new_reward:,.0f} VNĐ</code>")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Lỗi cú pháp: {e}")

@bot.message_handler(commands=['setfee'])
def admin_set_fee(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            current_val = int(get_setting("admin_cost", 20000))
            bot.reply_to(message, f"⚠️ Cú pháp: /setfee [số_tiền]\n💳 Phí chế độ Admin Setup hiện tại: <code>{current_val:,.0f} VNĐ</code>", parse_mode="HTML")
            return
            
        new_fee = int(parts[1])
        set_setting("admin_cost", new_fee)
        bot.reply_to(message, f"✅ <b>ĐÃ CẬP NHẬT PHÍ CHẾ ĐỘ ADMIN SETUP!</b>\n💳 Phí mới: <code>{new_fee:,.0f} VNĐ</code>", parse_mode="HTML")
        notify_all_admins(f"🔄 Admin vừa thay đổi phí chế độ Admin Setup thành: <code>{new_fee:,.0f} VNĐ</code>")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Lỗi cú pháp: {e}")

@bot.message_handler(commands=['setall_victim'])
def admin_set_all_victim(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            current_v = get_setting("global_victim", DEFAULT_VICTIM)
            bot.reply_to(message, f"⚠️ Cú pháp: /setall_victim [username_nạn_nhân]\n🎯 Nguồn nạn nhân ẩn hiện tại: <code>{current_v}</code>", parse_mode="HTML")
            return
        
        new_victim = parts[1].strip().replace("@", "")
        set_setting("global_victim", new_victim)
        
        conn = sqlite3.connect("bot_vip_database.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET locket_username = ?", (new_victim,))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ <b>ĐÃ CẬP NHẬT NẠN NHÂN (NGUỒN ẨN) TOÀN BOT!</b>\n🎯 Username mới: <code>{new_victim}</code>", parse_mode="HTML")
        notify_all_admins(f"🔄 Admin vừa đổi nguồn ẩn toàn bot thành: <code>{new_victim}</code>")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Lỗi xử lý: {e}")

@bot.message_handler(commands=['userinfo'])
def admin_user_info(message):
    if not is_admin(message.from_user.id):
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Cú pháp: /userinfo [user_id]", parse_mode="HTML")
            return
            
        target_id = int(parts[1])
        user_data = get_user(target_id)
        
        if not user_data:
            bot.reply_to(message, f"❌ Không tìm thấy thông tin của User ID <code>{target_id}</code> trong Database.", parse_mode="HTML")
            return
            
        balance = user_data[0]
        info_text = (
            f"👤 <b>THÔNG TIN TÀI KHOẢN USER</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: <code>{target_id}</code>\n"
            f"💰 Số dư: <code>{balance:,.0f} VNĐ</code>\n"
            f"🎯 Nguồn ẩn hiện tại (Admin): <code>{user_data[3]}</code>"
        )
        bot.reply_to(message, info_text, parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Lỗi: {e}")

@bot.message_handler(commands=['sendall'])
def admin_send_all(message):
    if not is_admin(message.from_user.id):
        return
    try:
        content = message.text.split(maxsplit=1)
        if len(content) < 2:
            bot.reply_to(message, "⚠️ Cú pháp: /sendall [nội dung thông báo]", parse_mode="HTML")
            return
        
        announcement = content[1]
        user_ids = get_all_user_ids()
        
        msg_wait = bot.reply_to(message, f"⏳ Đang gửi thông báo đến <code>{len(user_ids)}</code> người dùng...", parse_mode="HTML")
        
        success_count = 0
        for uid in user_ids:
            try:
                bot.send_message(uid, f"📢 <b>THÔNG BÁO TỪ HỆ THỐNG</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{announcement}", parse_mode="HTML")
                success_count += 1
            except Exception:
                pass
                
        bot.edit_message_text(f"✅ Đã gửi thông báo thành công cho <code>{success_count}/{len(user_ids)}</code> người dùng!", message.chat.id, msg_wait.message_id, parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Lỗi gửi thông báo: {e}")

@bot.message_handler(commands=['addmoney'])
def admin_add_money(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Cú pháp: /addmoney [user_id] [số_tiền]", parse_mode="HTML")
            return
            
        target_id = int(parts[1])
        amount = int(parts[2])
        
        user_data = get_user(target_id)
        if not user_data:
            bot.reply_to(message, f"❌ Không tìm thấy User ID <code>{target_id}</code> trong Database.", parse_mode="HTML")
            return
            
        current_balance = user_data[0]
        new_balance = current_balance + amount
        update_user_balance(target_id, new_balance)
        
        bot.reply_to(message, f"✅ <b>CỘNG TIỀN THÀNH CÔNG!</b>\n👤 User ID: <code>{target_id}</code>\n➕ Đã cộng: <code>{amount:,.0f} VNĐ</code>\n💰 Số dư mới: <code>{new_balance:,.0f} VNĐ</code>", parse_mode="HTML")
        
        try:
            bot.send_message(target_id, f"🎉 <b>TÀI KHOẢN ĐƯỢC CỘNG TIỀN!</b>\nAdmin đã cộng vào tài khoản của bạn: <code>+{amount:,.0f} VNĐ</code>\n💰 Số dư mới: <code>{new_balance:,.0f} VNĐ</code>", parse_mode="HTML")
        except Exception:
            pass
    except Exception as e:
        bot.reply_to(message, f"⚠️ Lỗi cú pháp hoặc dữ liệu: {e}")

@bot.message_handler(commands=['submoney'])
def admin_sub_money(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Cú pháp: /submoney [user_id] [số_tiền]", parse_mode="HTML")
            return
            
        target_id = int(parts[1])
        amount = int(parts[2])
        
        user_data = get_user(target_id)
        if not user_data:
            bot.reply_to(message, f"❌ Không tìm thấy User ID <code>{target_id}</code> trong Database.", parse_mode="HTML")
            return
            
        current_balance = user_data[0]
        new_balance = max(0, current_balance - amount)
        update_user_balance(target_id, new_balance)
        
        bot.reply_to(message, f"✅ <b>TRỪ TIỀN THÀNH CÔNG!</b>\n👤 User ID: <code>{target_id}</code>\n➖ Đã trừ: <code>{amount:,.0f} VNĐ</code>\n💰 Số dư mới: <code>{new_balance:,.0f} VNĐ</code>", parse_mode="HTML")
        
        try:
            bot.send_message(target_id, f"⚠️ <b>TÀI KHOẢN BỊ TRỪ TIỀN!</b>\nAdmin đã trừ bớt số dư của bạn: <code>-{amount:,.0f} VNĐ</code>\n💰 Số dư mới: <code>{new_balance:,.0f} VNĐ</code>", parse_mode="HTML")
        except Exception:
            pass
    except Exception as e:
        bot.reply_to(message, f"⚠️ Lỗi cú pháp hoặc dữ liệu: {e}")

@bot.message_handler(commands=['createcode'])
def admin_create_code(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 4:
            bot.reply_to(message, "⚠️ Cú pháp: /createcode [mã_code] [số_tiền] [số_lượng]\nVí dụ: /createcode TET2026 50000 10", parse_mode="HTML")
            return
            
        code = parts[1].strip().upper()
        money = int(parts[2])
        quantity = int(parts[3])
        
        conn = sqlite3.connect("bot_vip_database.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO promo_codes (code, money, uses_left) VALUES (?, ?, ?)", (code, money, quantity))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"🎁 <b>TẠO MÃ QUÀ TẶNG THÀNH CÔNG!</b>\n🎟️ Mã: <code>{code}</code>\n💰 Giá trị: <code>{money:,.0f} VNĐ</code>\n📦 Số lượng: <code>{quantity}</code> lượt dùng", parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Lỗi tạo mã: {e}")

# --- XỬ LÝ TOÀN BỘ TIN NHẮN & NÚT BẤM ---
@bot.message_handler(func=lambda message: True)
def handle_all_text_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    user_data = get_user(user_id)
    if not user_data:
        register_user(user_id, message.from_user.username, message.from_user.first_name)
        user_data = get_user(user_id)
        
    state = user_data[2]
    
    # 🔙 Xử lý nút QUAY LẠI toàn cục
    if text in ["🔙 Quay lại", "QUAY LẠI"]:
        update_user_state(user_id, None)
        update_user_temp(user_id, None)
        bot.send_message(message.chat.id, "🏠 Đã quay lại menu chính.", reply_markup=get_main_keyboard(user_id)
        return

    # 2. Xử lý chọn Chế độ Nâng cấp Locket Gold
    if state == "SELECT_UPGRADE_MODE":
        if text.startswith("👑 Chế độ Admin Setup"):
            update_user_state(user_id, "WAITING_FOR_MY_UID_ADMIN")
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(KeyboardButton("🔙 Quay lại"))
            current_cost_admin = int(get_setting("admin_cost", 20000))
            bot.send_message(message.chat.id, f"👑 <b>CHẾ ĐỘ ADMIN SETUP</b>\n💰 Phí: <code>{current_cost_admin:,.0f} VNĐ</code>\n🔗 Vui lòng gửi <b>Link trang cá nhân Locket</b> hoặc <b>Username Locket</b> của bạn:", parse_mode="HTML", reply_markup=markup)
        elif text == "💎 Chế độ Free (Dùng chung nguồn xin)":
            update_user_state(user_id, "WAITING_FOR_CUSTOM_TARGET")
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(KeyboardButton("🔙 Quay lại"))
            bot.send_message(
                message.chat.id, 
                f"💎 <b>CHẾ ĐỘ FREE (XIN USER NGUỒN)</b>\n"
                f"💰 Phí: <code>0 VNĐ</code>\n\n"
                f"🤫 <b>HƯỚNG DẪN THỰC HIỆN:</b>\n"
                f"1️⃣ Đi xin <b>Username Locket</b> của một người quen đang có sẵn Gold (có huy hiệu).\n"
                f"2️⃣ Gửi Username đó vào đây <i>(Cam kết: Quá trình diễn ra trong im lặng, tuyệt đối <b>không làm mất Gold</b> của người cho nguồn)</i>.\n\n"
                f"👉 Vui lòng gửi Username Locket của người chứa Gold vào đây trước:", 
                parse_mode="HTML", 
                reply_markup=markup
            )
        else:
            bot.send_message(message.chat.id, "⚠️ Vui lòng chọn một trong hai chế độ bên dưới bằng cách bấm nút.", reply_markup=message.reply_markup)
        return

    # 3. Chế độ 1: Nhập UID của user sau khi chọn Admin Setup
    if state == "WAITING_FOR_MY_UID_ADMIN":
        update_user_state(user_id, None)
        balance = user_data[0]
        current_cost_admin = int(get_setting("admin_cost", 20000))
        
        if balance < current_cost_admin:
            bot.reply_to(message, f"❌ Số dư không đủ <code>{current_cost_admin:,.0f} VNĐ</code> để thực hiện! Vui lòng liên hệ Admin nạp thêm tiền.", reply_markup=get_main_keyboard(user_id))
            return

        msg_wait = bot.reply_to(message, "⏳ Đang kết nối RevenueCat và kích hoạt gói...", parse_mode="HTML")
        
        my_uid = resolve_uid(text)
        if not my_uid:
            bot.edit_message_text("❌ Không tìm thấy Locket UID của bạn. Vui lòng kiểm tra lại!", message.chat.id, msg_wait.message_id)
            return

        victim_username = user_data[3] or get_setting("global_victim", DEFAULT_VICTIM)
        gold_uid = resolve_uid(victim_username)
        if not gold_uid:
            bot.edit_message_text("❌ Lỗi hệ thống: Không thể lấy dữ liệu nguồn Gold nội bộ.", message.chat.id, msg_wait.message_id)
            return

        gold_expiry = get_gold_expiry(gold_uid)
        if not test_is_gold_valid(gold_expiry):
            bot.edit_message_text("⚠️ Nguồn Gold của hệ thống đang hết hạn. Vui lòng báo Admin!", message.chat.id, msg_wait.message_id)
            return

        res = try_alias(my_uid, gold_uid)
        if res == "ok":
            new_balance = balance - current_cost_admin
            update_user_balance(user_id, new_balance)
            update_user_status(user_id, "✅ GOLX VİP (Đã kích hoạt)")
            
            success_msg = (
                f"✅ <b>KÍCH HOẠT LOCKET GOLD THÀNH CÔNG!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 <b>Thông tin gói dịch vụ:</b>\n"
                f"👤 Tài khoản nhận: <code>{text}</code>\n"
                f"📱 User Telegram: @{message.from_user.username or 'Không có'} (ID: <code>{user_id}</code>)\n"
                f"💰 Số dư còn lại: <code>{new_balance:,.0f} VNĐ</code>\n"
                f"👑 Chế độ: Admin Setup (-{current_cost_admin:,.0f}đ)\n"
                f"⏳ Hạn sử dụng Gold: <code>{gold_expiry}</code>\n"
                f"⏱️ Thời gian: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 Bot: @{bot.get_me().username}"
            )
            # 🛠️ ĐÃ SỬA: Xóa bỏ reply_markup ở edit_message_text vì dùng bàn phím thường (ReplyKeyboardMarkup)
            bot.edit_message_text(success_msg, message.chat.id, msg_wait.message_id, parse_mode="HTML")
            bot.send_message(message.chat.id, "🏠 Trở về menu chính:", reply_markup=get_main_keyboard(user_id))
            
            notify_all_admins(
                f"📢 <b>USER KÍCH HOẠT GÓI (ADMIN SETUP)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 User Telegram: @{message.from_user.username or 'Không có'} (ID: <code>{user_id}</code>)\n"
                f"🎯 Tài khoản nhận Gold: <code>{text}</code>\n"
                f"🔍 <b>Nguồn kích hoạt (Admin ẩn):</b> <code>{victim_username}</code>\n"
                f"💰 Doanh thu: <code>{current_cost_admin:,.0f} VNĐ</code>",
                parse_mode="HTML"
            )

        elif res == "limit":
            bot.edit_message_text("⚠️ Đã đạt giới hạn liên kết (Lỗi 7255). Vui lòng thử lại sau!", message.chat.id, msg_wait.message_id)
            bot.send_message(message.chat.id, "🏠 Trở về menu chính:", reply_markup=get_main_keyboard(user_id))
        else:
            bot.edit_message_text(f"❌ Kích hoạt thất bại: {res}", message.chat.id, msg_wait.message_id)
            bot.send_message(message.chat.id, "🏠 Trở về menu chính:", reply_markup=get_main_keyboard(user_id))
        return

    # 4. Chế độ 2 (Bước 1): User nhập Username nguồn Gold xin được
    if state == "WAITING_FOR_CUSTOM_TARGET":
        gold_uid = resolve_uid(text)
        if not gold_uid:
            bot.reply_to(message, "❌ Không tìm thấy thông tin nguồn Gold từ username bạn nhập. Vui lòng kiểm tra lại:")
            return
            
        gold_expiry = get_gold_expiry(gold_uid)
        if not test_is_gold_valid(gold_expiry):
            bot.reply_to(message, "⚠️ Nguồn Gold bạn nhập hiện đang hết hạn hoặc không có huy hiệu Gold hợp lệ! Vui lòng xin username khác:")
            return
            
        update_user_temp(user_id, gold_uid)
        update_user_state(user_id, "WAITING_FOR_MY_UID_CUSTOM")
        
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("🔙 Quay lại"))
        bot.send_message(message.chat.id, f"✅ Nguồn Gold hợp lệ và hoạt động trong im lặng!\n⏳ Hạn nguồn: <code>{gold_expiry}</code>\n\n🔗 Bây giờ, hãy gửi <b>Link trang cá nhân Locket hoặc Username Locket của bạn</b> để nhận:", parse_mode="HTML", reply_markup=markup)
        return

    # 4. Chế độ 2 (Bước 2): User nhập UID của chính mình để nhận Gold từ nguồn tự thêm
    if state == "WAITING_FOR_MY_UID_CUSTOM":
        gold_uid = user_data[4]
        update_user_state(user_id, None)
        update_user_temp(user_id, None)
        
        balance = user_data[0]
        current_cost_free = 0
        if balance < current_cost_free:
            bot.reply_to(message, "❌ Số dư không đủ!", reply_markup=get_main_keyboard(user_id))
            return

        msg_wait = bot.reply_to(message, "⏳ Đang thực hiện liên kết gói Free...", parse_mode="HTML")
        
        my_uid = resolve_uid(text)
        if not my_uid:
            bot.edit_message_text("❌ Không tìm thấy Locket UID của bạn!", message.chat.id, msg_wait.message_id)
            bot.send_message(message.chat.id, "🏠 Trở về menu chính:", reply_markup=get_main_keyboard(user_id))
            return

        gold_expiry = get_gold_expiry(gold_uid)

        res = try_alias(my_uid, gold_uid)
        if res == "ok":
            new_balance = balance - current_cost_free
            update_user_balance(user_id, new_balance)
            update_user_status(user_id, "✅ GOLX VİP (Free Mode)")
            
            success_msg = (
                f"✅ <b>KÍCH HOẠT LOCKET GOLD (FREE MODE) THÀNH CÔNG!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 <b>Thông tin chi tiết gói:</b>\n"
                f"👤 Tài khoản nhận: <code>{text}</code>\n"
                f"📱 User Telegram: @{message.from_user.username or 'Không có'} (ID: <code>{user_id}</code>)\n"
                f"💰 Số dư còn lại: <code>{new_balance:,.0f} VNĐ</code>\n"
                f"💎 Chế độ: Xin user nguồn (Free)\n"
                f"⏳ Hạn sử dụng Gold: <code>{gold_expiry}</code>\n"
                f"⏱️ Thời gian: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 Bot: @{bot.get_me().username}"
            )
            # 🛠️ ĐÃ SỬA: Xóa bỏ reply_markup ở edit_message_text
            bot.edit_message_text(success_msg, message.chat.id, msg_wait.message_id, parse_mode="HTML")
            bot.send_message(message.chat.id, "🏠 Trở về menu chính:", reply_markup=get_main_keyboard(user_id))
        elif res == "limit":
            bot.edit_message_text("⚠️ Đã đạt giới hạn liên kết (Lỗi 7255).", message.chat.id, msg_wait.message_id)
            bot.send_message(message.chat.id, "🏠 Trở về menu chính:", reply_markup=get_main_keyboard(user_id))
        else:
            bot.edit_message_text(f"❌ Kích hoạt thất bại: {res}", message.chat.id, msg_wait.message_id)
            bot.send_message(message.chat.id, "🏠 Trở về menu chính:", reply_markup=get_main_keyboard(user_id))
        return

    # 5. Xử lý các nút bấm Menu chính
    if text == "🚀 NÂNG CẤP LOCKET GOLD":
        update_user_state(user_id, "SELECT_UPGRADE_MODE")
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        current_cost_admin = int(get_setting("admin_cost", 20000))
        markup.add(
            KeyboardButton(f"👑 Chế độ Admin Setup (-{current_cost_admin:,.0f}đ)"),
            KeyboardButton("💎 Chế độ Free (Dùng chung nguồn xin)"),
            KeyboardButton("🔙 Quay lại")
        )
        bot.send_message(
            message.chat.id, 
            "🚀 <b>LỰA CHỌN CHẾ ĐỘ NÂNG CẤP LOCKET GOLD</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Vui lòng chọn chế độ bạn muốn sử dụng bên dưới:",
            parse_mode="HTML",
            reply_markup=markup
        )
        
    elif text == "🎟️ NHẬP MÃ QUÀ TẶNG":
        update_user_state(user_id, "WAITING_FOR_PROMO_CODE")
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("🔙 Quay lại"))
        bot.send_message(message.chat.id, "🎟️ Vui lòng gửi mã quà tặng (Promo Code) của bạn vào khung chat:", reply_markup=markup)
        
    elif text == "💳 NẠP TIỀN (IB ADMIN)":
        pay_text = (
            f"💳 <b>HƯỚNG DẪN NẠP TIỀN</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Liên hệ trực tiếp Admin để nạp tiền vào tài khoản:\n"
            f"👉 Người quản lý: <code>{DEV_USERNAME}</code>\n"
            f"🆔 ID của bạn để chuyển khoản/xác thực: <code>{user_id}</code>\n"
            f"💡 <i>Sau khi chuyển khoản, vui lòng gửi bill qua cho Admin để được cộng tiền tự động/thủ công nhanh nhất!</i>"
        )
        bot.send_message(message.chat.id, pay_text, parse_mode="HTML")

    elif text == "💎 HỒ SƠ CÁ NHÂN":
        profile_text = (
            f"💎 <b>HỒ SƠ TÀI KHOẢN CÁ NHÂN</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Họ tên: <b>{message.from_user.first_name}</b>\n"
            f"🔗 Username: @{message.from_user.username or 'Không có'}\n"
            f"🆔 ID tài khoản: <code>{user_id}</code>\n"
            f"💰 Số dư: <code>{user_data[0]:,.0f} VNĐ</code>\n"
            f"📊 Trạng thái Locket: <code>{user_data[1]}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        bot.send_message(message.chat.id, profile_text, parse_mode="HTML")

    elif text == "🎁 GIỚI THIỆU BẠN BÈ":
        bot_info = bot.get_me()
        current_ref_reward = int(get_setting("ref_reward", 5000))
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        ref_text = (
            f"🎁 <b>CHƯƠNG TRÌNH GIỚI THIỆU BẠN BÈ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Giới thiệu bạn bè tham gia bot để nhận ngay <code>+{current_ref_reward:,.0f} VNĐ</code> vào tài khoản khi họ bấm vào link!\n\n"
            f"🔗 <b>Link giới thiệu của bạn:</b>\n<code>{ref_link}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 Hãy chia sẻ link này cho bạn bè ngay nhé!"
        )
        bot.send_message(message.chat.id, ref_text, parse_mode="HTML")

    elif text == "🛠️ HỖ TRỢ & LIÊN HỆ":
        support_text = (
            f"🛠️ <b>HỖ TRỢ & CSKH 24/7</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💬 Mọi thắc mắc, khiếu nại hoặc cần hỗ trợ nạp rút, vui lòng liên hệ Admin:\n"
            f"👉 Support: <code>{DEV_USERNAME}</code>"
        )
        bot.send_message(message.chat.id, support_text, parse_mode="HTML")

    elif text == "👑 HỆ THỐNG ADMIN" and is_admin(user_id):
        current_cost_admin = int(get_setting("admin_cost", 20000))
        current_ref_reward = int(get_setting("ref_reward", 5000))
        current_victim = get_setting("global_victim", DEFAULT_VICTIM)
        admin_menu_text = (
            f"👑 <b>BẢNG ĐIỀU KHIỂN HỆ THỐNG ADMIN</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ <b>Cấu hình hiện tại:</b>\n"
            f"• Phí Admin Setup: <code>{current_cost_admin:,.0f} VNĐ</code> (Đổi bằng /setfee [số])\n"
            f"• Thưởng giới thiệu: <code>{current_ref_reward:,.0f} VNĐ</code> (Đổi bằng /setref [số])\n"
            f"• Nguồn nạn nhân ẩn: <code>{current_victim}</code> (Đổi bằng /setall_victim [user])\n\n"
            f"📋 <b>Các lệnh quản trị hỗ trợ:</b>\n"
            f"• /userinfo [user_id] - Xem thông tin user\n"
            f"• /addmoney [id] [tiền] - Cộng tiền user\n"
            f"• /submoney [id] [tiền] - Trừ tiền user\n"
            f"• /createcode [mã] [tiền] [SL] - Tạo mã quà tặng\n"
            f"• /setall_victim [user] - Đổi nguồn ẩn toàn bot\n"
            f"• /setfee [tiền] - Đổi phí Admin Setup\n"
            f"• /setref [tiền] - Đổi thưởng giới thiệu\n"
            f"• /sendall [nội dung] - Gửi thông báo toàn bộ user"
        )
        bot.send_message(message.chat.id, admin_menu_text, parse_mode="HTML")

# --- CHẠY BOT ---
if __name__ == "__main__":
    print("🤖 Bot Locket VIP đang chạy...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Lỗi kết nối Bot: {e}")
