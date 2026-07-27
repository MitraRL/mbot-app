import telebot
import threading
import time
import uuid
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp, BotCommand
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from supabase import create_client, Client

# --- ТВОИ КЛЮЧИ И ТОКЕН ---
TOKEN = '8864393991:AAExQCkXmUMBDAnMrs2rhJBE-9G1po0Xypw' 
SUPABASE_URL = "https://kvsrxuibrovumaikqptk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt2c3J4dWlicm92dW1haWtxcHRrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NDg3NzQ1NiwiZXhwIjoyMTAwNDUzNDU2fQ.zfFCppQZ35HzZigz3xIDrph4jUY_2M67-gnnC9y6AYg"

ADMIN_ID = 438290253 

bot = telebot.TeleBot(TOKEN)
bot_info = bot.get_me() # Получаем инфу о самом боте (нужно для ссылок)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

user_platform_state = {}
tournament_creation_state = {} # Словарь для хранения состояний при создании турнира

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_stats = KeyboardButton(text="📊 Моя статистика")
    btn_rules = KeyboardButton(text="📜 Правила")
    btn_create = KeyboardButton(text="➕ Создать турнир")
    markup.add(btn_stats, btn_rules)
    markup.add(btn_create)
    return markup

def get_app_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text="🏆 ОТКРЫТЬ ХАБ ТУРНИРОВ", web_app=WebAppInfo(url='https://mitrarl.github.io/mbot-app/')))
    return keyboard

def setup_bot_commands():
    commands = [
        BotCommand("start", "🚀 Главное меню"),
        BotCommand("squad", "📸 Обновить скриншот состава"),
        BotCommand("help", "ℹ️ Справка по боту")
    ]
    try:
        bot.set_my_commands(commands)
    except Exception as e:
        print(f"Ошибка установки списка команд: {e}")

def check_notifications():
    while True:
        try:
            response = supabase.table('notifications').select('*').eq('is_sent', False).execute()
            for notif in response.data:
                try:
                    bot.send_message(notif['telegram_id'], notif['message'])
                except Exception as e:
                    pass
                finally:
                    supabase.table('notifications').update({'is_sent': True}).eq('id', notif['id']).execute()
        except Exception as e:
            pass
        time.sleep(3) 

thread = threading.Thread(target=check_notifications)
thread.daemon = True
thread.start()

# --- ОБРАБОТКА СТАРТА И ИНВАЙТ-ССЫЛОК ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"
    
    # 1. Проверяем, перешел ли игрок по инвайт-ссылке
    args = message.text.split()
    invite_code = None
    if len(args) > 1 and args[1].startswith('invite_'):
        invite_code = args[1].replace('invite_', '')

    # 2. Обработка Инвайт-ссылки
    if invite_code:
        try:
            t_res = supabase.table('tournaments').select('*').eq('invite_code', invite_code).execute()
            if t_res.data:
                tour = t_res.data[0]
                if tour['status'] == 'active':
                    # Проверяем, не состоит ли он уже в нем
                    tp_check = supabase.table('tournament_players').select('*').eq('tournament_id', tour['id']).eq('user_id', user_id).execute()
                    if not tp_check.data:
                        supabase.table('tournament_players').insert({'tournament_id': tour['id'], 'user_id': user_id}).execute()
                        bot.send_message(message.chat.id, f"🎉 Ты успешно присоединился к турниру **{tour['name']}**!", parse_mode="Markdown")
                    else:
                        bot.send_message(message.chat.id, f"⚠️ Ты уже участвуешь в турнире **{tour['name']}**.", parse_mode="Markdown")
                else:
                    bot.send_message(message.chat.id, "❌ Этот турнир еще на модерации или уже завершен.")
            else:
                bot.send_message(message.chat.id, "❌ Неверный или устаревший код приглашения.")
        except Exception as e:
            print(f"Ошибка при присоединении по инвайту: {e}")
    
    try:
        res = supabase.table('users').select('*').eq('id', user_id).execute()
        if res.data:
            user_data = res.data[0]
            if user_data.get('is_banned'):
                bot.send_message(message.chat.id, "🚫 **Организатор ограничил вам доступ.**", parse_mode="Markdown")
                return

            if user_data.get('platform') and user_data.get('platform') != 'Неизвестно':
                bot.send_message(
                    message.chat.id, 
                    f"С возвращением, @{username}! ⚽\nВоспользуйся меню ниже:", 
                    reply_markup=get_main_menu()
                )
                bot.send_message(message.chat.id, "Войти в Турнирный Хаб:", reply_markup=get_app_keyboard())
                return 
    except Exception as e:
        print(f"Ошибка проверки пользователя: {e}")

    try:
        res = supabase.table('users').select('*').eq('id', user_id).execute()
        if not res.data:
            supabase.table('users').insert({
                'id': user_id, 
                'username': username, 
                'group_name': 'Без группы',
                'wins': 0, 'losses': 0, 'goals_for': 0, 'goals_against': 0,
                'can_update_squad': True
            }).execute()
    except:
        pass

    keyboard = InlineKeyboardMarkup(row_width=3)
    keyboard.add(
        InlineKeyboardButton("🎮 PlayStation", callback_data="plat_PlayStation"),
        InlineKeyboardButton("❎ Xbox", callback_data="plat_Xbox"),
        InlineKeyboardButton("💻 PC", callback_data="plat_PC")
    )
    bot.send_message(message.chat.id, f"Привет, @{username}! ⚽\n\nДобро пожаловать в Хаб. Шаг 1 из 2:\n**Выбери платформу:**", reply_markup=keyboard, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith('plat_'))
def handle_platform_choice(call):
    user_id = call.from_user.id
    platform = call.data.split('_')[1]
    user_platform_state[user_id] = platform
    
    try:
        bot.answer_callback_query(call.id, f"Выбрано: {platform}")
        bot.send_message(
            call.message.chat.id,
            f"✅ Платформа сохранена: **{platform}**.\n\nШаг 2 из 2:\n📸 **Отправь скриншот своего состава** прямо сюда в чат!",
            reply_markup=get_main_menu(), parse_mode="Markdown"
        )
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

@bot.message_handler(commands=['squad'])
def cmd_squad(message):
    bot.reply_to(message, "📸 **Обновление состава**\n\nОтправь новый скриншот состава прямо сюда в чат!", parse_mode="Markdown")

@bot.message_handler(commands=['send'])
def admin_broadcast(message):
    if message.from_user.id != ADMIN_ID: return
    text = message.text.replace('/send', '').strip()
    if not text:
        bot.reply_to(message, "⚠️ Использование: `/send Текст сообщения`", parse_mode="Markdown")
        return
    try:
        res = supabase.table('users').select('id').execute()
        count = 0
        for u in res.data:
            supabase.table('notifications').insert({'telegram_id': u['id'], 'message': f"📢 **Объявление от Организатора:**\n\n{text}"}).execute()
            count += 1
        bot.reply_to(message, f"✅ Рассылка поставлена в очередь для {count} игроков!")
    except Exception as e:
        bot.reply_to(message, f"Ошибка рассылки: {e}")


# --- ЛОГИКА СОЗДАНИЯ ТУРНИРА (Многошаговая) ---
@bot.message_handler(content_types=['text'])
def handle_text(message):
    text = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"

    # Шаг ввода названия турнира
    if user_id in tournament_creation_state and tournament_creation_state[user_id]['step'] == 'waiting_name':
        if len(text) < 3 or len(text) > 40:
            bot.send_message(message.chat.id, "⚠️ Название должно быть от 3 до 40 символов. Попробуй еще раз:")
            return
        
        tournament_creation_state[user_id]['name'] = text
        tournament_creation_state[user_id]['step'] = 'waiting_privacy'

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🔓 Открытый (Виден всем в Лобби)", callback_data="privacy_public"),
            InlineKeyboardButton("🔒 Закрытый (Только по ссылке)", callback_data="privacy_private")
        )
        bot.send_message(message.chat.id, f"Название: **{text}**\n\nВыбери тип приватности:", reply_markup=markup, parse_mode="Markdown")
        return

    # Кнопки Главного меню
    if text == "➕ Создать турнир":
        tournament_creation_state[user_id] = {'step': 'waiting_name'}
        bot.send_message(message.chat.id, "🏆 **Создание турнира**\n\nВведи крутое название для твоего турнира (например, 'Кубок Москвы'):", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
        
    elif text == "📊 Моя статистика":
        bot.send_message(message.chat.id, "Статистика переезжает в Web-интерфейс Хаба. Нажми 'Открыть турнир', чтобы посмотреть подробности по каждой лиге!")

    elif text == "📜 Правила":
        rules = "📜 **Правила Платформы:**\n1. Уважай соперников.\n2. Вноси честные результаты.\n3. Спорные моменты решаются Организатором турнира."
        bot.send_message(message.chat.id, rules, parse_mode="Markdown")
        
    elif text not in ['/start', '/help', '/commands'] and not text.startswith('/send'):
        bot.reply_to(message, "Воспользуйся кнопкой ниже для входа в турниры 👇", reply_markup=get_app_keyboard())

# --- ОБРАБОТКА ВЫБОРА ПРИВАТНОСТИ И ОТПРАВКА НА МОДЕРАЦИЮ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('privacy_'))
def handle_privacy(call):
    user_id = call.from_user.id
    if user_id not in tournament_creation_state:
        bot.answer_callback_query(call.id, "Время сессии истекло. Начни заново.", show_alert=True)
        return

    is_private = True if call.data == 'privacy_private' else False
    tour_name = tournament_creation_state[user_id]['name']
    invite_code = str(uuid.uuid4())[:8] # Генерируем короткий уникальный код

    try:
        # Сохраняем турнир как pending
        res = supabase.table('tournaments').insert({
            'name': tour_name,
            'creator_id': user_id,
            'is_private': is_private,
            'status': 'pending',
            'invite_code': invite_code
        }).execute()
        
        tour_id = res.data[0]['id']

        bot.edit_message_text(f"✅ Заявка на турнир **{tour_name}** отправлена на модерацию!\nКак только админ ее проверит, бот пришлет тебе ссылку для инвайтов.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        bot.send_message(call.message.chat.id, "Возвращаю меню:", reply_markup=get_main_menu())

        # Отправляем уведомление Глобальному Админу (Тебе)
        admin_markup = InlineKeyboardMarkup()
        admin_markup.add(
            InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_approve_{tour_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject_{tour_id}")
        )
        privacy_text = "Закрытый 🔒" if is_private else "Открытый 🔓"
        bot.send_message(
            ADMIN_ID,
            f"🚨 **Новая заявка на турнир!**\n\n"
            f"👤 ID Автора: `{user_id}`\n"
            f"🏆 Название: **{tour_name}**\n"
            f"👁 Тип: {privacy_text}",
            reply_markup=admin_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {e}")

    del tournament_creation_state[user_id] # Очищаем состояние


# --- КНОПКИ АДМИНА (ОДОБРИТЬ/ОТКЛОНИТЬ) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('mod_'))
def handle_moderation(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет прав!")
        return

    parts = call.data.split('_')
    action = parts[1]
    tour_id = parts[2]

    try:
        tour_res = supabase.table('tournaments').select('*').eq('id', tour_id).execute()
        if not tour_res.data:
            bot.answer_callback_query(call.id, "Турнир уже не существует.")
            return
        
        tour = tour_res.data[0]

        if action == 'approve':
            # Одобряем турнир
            supabase.table('tournaments').update({'status': 'active'}).eq('id', tour_id).execute()
            
            # Автоматически добавляем создателя в участники турнира
            try:
                supabase.table('tournament_players').insert({'tournament_id': tour_id, 'user_id': tour['creator_id']}).execute()
            except: pass

            bot.edit_message_text(f"{call.message.text}\n\n**[ ✅ ОДОБРЕН ]**", call.message.chat.id, call.message.message_id)
            
            # Отправляем радостную весть создателю
            invite_link = f"https://t.me/{bot_info.username}?start=invite_{tour['invite_code']}"
            bot.send_message(
                tour['creator_id'],
                f"🎉 Твоя заявка одобрена! Турнир **{tour['name']}** создан и активен.\n\n"
                f"🔗 **Твоя личная ссылка для приглашения друзей:**\n`{invite_link}`\n\n"
                f"*(Нажми на ссылку, чтобы скопировать)*\nОни перейдут по ней и автоматически станут участниками!",
                parse_mode="Markdown"
            )

        elif action == 'reject':
            supabase.table('tournaments').update({'status': 'rejected'}).eq('id', tour_id).execute()
            bot.edit_message_text(f"{call.message.text}\n\n**[ ❌ ОТКЛОНЕН ]**", call.message.chat.id, call.message.message_id)
            bot.send_message(tour['creator_id'], f"❌ К сожалению, твоя заявка на создание турнира **{tour['name']}** была отклонена администратором.", parse_mode="Markdown")

    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка базы данных: {e}")

# (Код для сохранения фото остается таким же)
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"
    photo_id = message.photo[-1].file_id 

    # Проверка споров (оставляем старую логику для обратной совместимости пока не обновим фронт)
    try:
        disputes = supabase.table('matches').select('*').eq('is_completed', False).eq('is_disputed', True).execute()
        user_dispute_match = None
        for m in disputes.data:
            if m['player1'] == username or m['player2'] == username:
                user_dispute_match = m
                break
        if user_dispute_match:
            caption = f"🚨 **ПРУФЫ ПО СПОРНОМУ МАТЧУ** 🚨\n\n👤 Игрок: @{username}\n⚔️ Матч: {user_dispute_match['player1']} vs {user_dispute_match['player2']} ({user_dispute_match['round']})"
            bot.send_photo(ADMIN_ID, photo_id, caption=caption, parse_mode='Markdown')
            bot.reply_to(message, "✅ **Доказательства отправлены!**", parse_mode="Markdown")
            return 
    except: pass

    # Сохранение фото состава
    platform = user_platform_state.get(user_id, 'PC') # Fallback
    bot.send_chat_action(message.chat.id, 'upload_photo')
    try:
        file_info = bot.get_file(photo_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_name = f"squad_{user_id}_{int(time.time())}.jpg"
        
        supabase.storage.from_('squads').upload(path=file_name, file=downloaded_file, file_options={"content-type": "image/jpeg"})
        squad_url = supabase.storage.from_('squads').get_public_url(file_name)
        
        # Сохраняем в users (глобальный) - позже будем прикреплять к конкретным турнирам
        supabase.table('users').update({'current_squad_url': squad_url}).eq('id', user_id).execute()
        
        bot.reply_to(message, "✅ Фото состава успешно сохранено в твой профиль!", reply_markup=get_app_keyboard())
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка сохранения фото.")

try:
    bot.set_chat_menu_button(menu_button=MenuButtonWebApp(type='web_app', text='🏆 Турнир', web_app=WebAppInfo(url='https://mitrarl.github.io/mbot-app/')))
except: pass

print("Бот запущен и готов к работе...")
bot.infinity_polling(timeout=10, long_polling_timeout=5)