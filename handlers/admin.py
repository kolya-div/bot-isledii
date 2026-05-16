import logging
import uuid  # Biletlar uchun yagona kod yaratish uchun kerak
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, WebAppInfo, BufferedInputFile # BufferedInputFile qo'shildi
)
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

# Generatorni import qilish (utils papkangizdagi funksiya)
from utils.ticket_gen import generate_ticket 

# Konfiguratsiya va bazani import qilish
from config import SUPER_ADMIN_ID, ADMINS, WEB_APP_URL, ADMIN_PHONE, ADMIN_USERNAME
from database.db import async_session
from database.models import AdminUser, Concert, Ticket, Row, Seat
from sqlalchemy import select, func, delete

router = Router()

# =====================================================================
# HOLATLAR (FSM) - ALGORITM ASOSIDA
# =====================================================================

class AdminStates(StatesGroup):
    """Konsert yaratish bosqichlari uchun holatlar"""
    waiting_for_admin_id = State()
    
    # Konsert yaratish bosqichlari (Word fayl 6-7 band)
    waiting_for_reklama_photo = State()
    waiting_for_concert_name = State()
    waiting_for_concert_year = State()
    waiting_for_concert_month = State()
    waiting_for_concert_day = State()
    waiting_for_concert_time = State()
    waiting_for_zal_photo = State()
    
    # Qatorlar va joylar sozlamalari (Word fayl 7-band)
    waiting_for_rows_count = State()
    waiting_for_row_price = State()
    waiting_for_seats_per_row = State()

class SellTicketStates(StatesGroup):
    """Admin tomonidan bilet sotish jarayoni uchun holatlar"""
    waiting_for_row_selection = State()
    waiting_for_seat_selection = State()
    waiting_for_customer_name = State() # Ism familiya so'rash bosqichi

# =====================================================================
# YORDAMCHI FUNKSIYALAR (TEZKORLASHTIRILGAN)
# =====================================================================

async def check_is_admin(user_id: int) -> bool:
    """Adminlik huquqini tekshirish (.env dan to'g'ridan-to'g'ri - QOTMASDAN ISHLAYDI)"""
    return (user_id == SUPER_ADMIN_ID) or (user_id in ADMINS)

# =====================================================================
# ASOSIY ADMIN MENYUSI VA TUGMALAR (PREMIUM DIZAYN)
# =====================================================================

def get_admin_main_kb(is_super: bool) -> InlineKeyboardMarkup:
    """Super Admin va Oddiy Admin menyularini chiroyli va qulay joylashtirish"""
    buttons = []
    
    if is_super:
        buttons.append([InlineKeyboardButton(text="🎸 Jańa koncert qosıw", callback_data="add_concert_start")])
        buttons.append([
            InlineKeyboardButton(text="💰 Bilet satiw", callback_data="sell_ticket"),
            InlineKeyboardButton(text="📊 Statistika", callback_data="show_stats")
        ])
        # MANA SHU YER O'ZGARDI:
        buttons.append([InlineKeyboardButton(text="🔗 QR kod link", callback_data="send_scanner_link")])
        
    else:
        buttons.append([
            InlineKeyboardButton(text="💰 Bilet satiw", callback_data="sell_ticket"),
            InlineKeyboardButton(text="📊 Statistika", callback_data="show_stats")
        ])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)
def get_cancel_kb():

    """Jarayonni bekor qilish tugmasi (Qizil e'tibor tortuvchi)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Ámeldi biykarlaw", callback_data="back_to_main")]
    ])

def get_back_keyboard():
    """Umumiy orqaga qaytish tugmasi"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Artqa qaytıw", callback_data="back_to_main")]
    ])

# =====================================================================
# ASOSIY START VA ADMIN PANEL
# =====================================================================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Botga start bosilganda rolni aniqlash"""
    await state.clear()
    user_id = message.from_user.id
    
    if await check_is_admin(user_id):
        is_super = (user_id == SUPER_ADMIN_ID)
        await message.answer(
            f"🛠 **Admin paneliga xush kelibsiz!**\n\n"
            f"Sizning ID: `{user_id}`\n"
            f"Dareje: {'Super Admin' if is_super else 'Admin'}",
            reply_markup=get_admin_main_kb(is_super),
            parse_mode="Markdown"
        )
    else:
        # Foydalanuvchi menyusi (Algoritm 24-band)
        user_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎫 Bilet satıp alıw", callback_data="buy_ticket")],
            [InlineKeyboardButton(text="ℹ️ Konsert haqqında ", callback_data="concert_info")],
            [InlineKeyboardButton(text="📞 Admin menen baylanısıw", callback_data="contact_admin")]
        ])
        await message.answer(
            f"Salem {message.from_user.first_name}! 👋\n\n"
            f"Koncert biletleri botına xosh keldińiz.",
            reply_markup=user_kb
        )

@router.callback_query(F.data == "back_to_main")
async def back_to_main_handler(call: CallbackQuery, state: FSMContext):
    """Tiykarǵı admin menyusine qaytıw"""
    await state.clear()
    is_super = (call.from_user.id == SUPER_ADMIN_ID)
    await call.message.edit_text(
        "🛠 Admin paneliga qaytdingiz. Kerakli bo'limni tanlang:", 
        reply_markup=get_admin_main_kb(is_super)
    )

# =====================================================================
# TASDIQLASH VA KONSERT QO'SHISH BOSQICHLARI
# =====================================================================

@router.callback_query(F.data == "add_concert_start")
async def add_concert_confirm_handler(call: CallbackQuery):
    """Jańa koncert qosıwdan aldın eskertiw hám tastıyıqlaw"""
    # Tasdiqlash tugmalari
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Awa, óshirip jańadan baslaw", callback_data="confirm_new_concert")],
        [InlineKeyboardButton(text="❌ Joq, biykarlaw", callback_data="back_to_main")]
    ])
    
    await call.message.edit_text(
        "⚠️ **DÍQQAT! awır ámeliyat**\n\n"
        "Siz jańa koncert jaratpaqshısız. Eger bunı tastıyıqlasańız, **aldınǵı barlıq koncert maǵlıwmatları, "
        "Kirgizilgen qatarlar hám satılǵan biletler bazadan pútkilley joǵaladı!**\n\n"
        "Haqıyqatında da barlıq eski maǵlıwmattı óshirip, jańa koncert qosıwdı qáleysiz be?",
        reply_markup=confirm_kb,
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "confirm_new_concert")
async def add_concert_step_1(call: CallbackQuery, state: FSMContext):
    """Tastıyıqlanǵannan soń bazanı tazalap, 1-qádemdi baslaw"""
    
    # 1. Eski ma'lumotlarni bazadan tozalash
    async with async_session() as session:
        try:
            # Ketma-ketlik muhim (avval bilet, keyin joy, keyin qator, oxirida konsert)
            await session.execute(delete(Ticket))
            await session.execute(delete(Seat))
            await session.execute(delete(Row))
            await session.execute(delete(Concert))
            await session.commit()
        except Exception as e:
            logging.error(f"Bazanı tazalawda qáte: {e}")
            return await call.message.edit_text(
                "❌ Eski maǵlıwmatlardı óshiriwde qátelik júz berdi. Programmist penen baylanısıń.",
                reply_markup=get_back_keyboard()
            )

    # 2. Tozalab bo'lgach, rasmni so'rash
    await call.message.edit_text(
        "✅ **Baza tazalandi!**\n\n"
        "🖼 **1-Qadem:** Jana koncert ushın reklama fotosın jiberiń::", 
        reply_markup=get_cancel_kb(), 
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_reklama_photo)
# =====================================================================
# KONSERT QO'SHISH BOSQICHLARI (ALGORITM 6-7 BAND)
# =====================================================================
@router.callback_query(F.data == "add_concert_start")
async def add_concert_step_1(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("🖼 **1-Qadem:** Koncert reklama fotosini jbering:", reply_markup=get_cancel_kb(), parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_reklama_photo)

@router.message(AdminStates.waiting_for_reklama_photo, F.photo)
async def add_concert_step_2(message: Message, state: FSMContext):
    await state.update_data(reklama_photo=message.photo[-1].file_id)
    await message.answer("📝 **2-Qadem:** Koncert atamasın kirgiziń:", reply_markup=get_cancel_kb(), parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_concert_name)

@router.message(AdminStates.waiting_for_concert_name)
async def add_concert_step_3(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📅 **3-Qadem:** Koncert jılın kirgiziń (máselen: 2026):", reply_markup=get_cancel_kb(), parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_concert_year)

@router.message(AdminStates.waiting_for_concert_year)
async def add_concert_step_4(message: Message, state: FSMContext):
    await state.update_data(year=message.text)
    await message.answer("🗓 **4-Qadem:** Koncert ayın kirgiziń (máselen: Avgust):", reply_markup=get_cancel_kb(), parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_concert_month)

@router.message(AdminStates.waiting_for_concert_month)
async def add_concert_step_5(message: Message, state: FSMContext):
    await state.update_data(month=message.text)
    await message.answer("📆 **5-Qadem:** kúnin kirgiziń (máselen: 25):", reply_markup=get_cancel_kb(), parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_concert_day)

@router.message(AdminStates.waiting_for_concert_day)
async def add_concert_step_6(message: Message, state: FSMContext):
    await state.update_data(day=message.text)
    await message.answer("⏰ **6-Qadem:** Koncert baslanıw waqtın kirgiziń (máselen: 19:30):", reply_markup=get_cancel_kb(), parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_concert_time)

@router.message(AdminStates.waiting_for_concert_time)
async def add_concert_step_7(message: Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("🏟 **7-Qadem:** Koncert imaratı/zalınıń súwretin jiberiń:", reply_markup=get_cancel_kb(), parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_zal_photo)

@router.message(AdminStates.waiting_for_zal_photo, F.photo)
async def add_concert_step_8(message: Message, state: FSMContext):
    await state.update_data(zal_photo=message.photo[-1].file_id)
    await message.answer("🔢 **8-Qadem:** Zalda neshe qatar bar? (Tek nomer):", reply_markup=get_cancel_kb(), parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_rows_count)

# =====================================================================
# QATORLAR VA JOYNI SOZLASH (ALGORITM 7-BAND)
# =====================================================================
@router.message(AdminStates.waiting_for_rows_count)
async def add_concert_step_9(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Iltimas, tek nomer kirgiziń!!")
    
    rows_count = int(message.text)
    await state.update_data(rows_count=rows_count, current_processing_row=1, row_data={})
    
    await message.answer(f"💰 **1-qatar** bilet bahasın kirgiziń (máselen: 150000):", reply_markup=get_cancel_kb(), parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_row_price)

@router.message(AdminStates.waiting_for_row_price)
async def add_concert_step_10(message: Message, state: FSMContext):
    data = await state.get_data()
    row_num = data['current_processing_row']
    
    # Narxni vaqtinchalik saqlaymiz
    row_data = data.get('row_data', {})
    row_data[row_num] = {'price': message.text}
    await state.update_data(row_data=row_data)
    
    await message.answer(f"💺 **{row_num}-qatarda** neshe orin bar?", reply_markup=get_cancel_kb(), parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_seats_per_row)

@router.message(AdminStates.waiting_for_seats_per_row)
async def add_concert_step_11(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Orinlar sanin sanada kiriting!")
        
    data = await state.get_data()
    row_num = data['current_processing_row']
    total_rows = data['rows_count']
    
    row_data = data['row_data']
    row_data[row_num]['seats'] = int(message.text)
    await state.update_data(row_data=row_data)
    
    if row_num < total_rows:
        next_row = row_num + 1
        await state.update_data(current_processing_row=next_row)
        await message.answer(f"💰 **{next_row}-qatar** bilet bahasın kirgiziń:", reply_markup=get_cancel_kb(), parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_row_price)
    else:
        # HAMMA MA'LUMOTLAR OLINDI - BAZAGA SAQLASH
        await message.answer("⌛️ Maǵlıwmatlar bazaǵa saqlanbaqta, kútiń...")
        
        async with async_session() as session:
            try:
                # 1. Konsertni yaratish
                new_concert = Concert(
                    name=data['name'],
                    date=f"{data['day']}-{data['month']} {data['year']}, {data['time']}",
                    photo_reklama=data['reklama_photo'],
                    photo_zal=data['zal_photo']
                )
                session.add(new_concert)
                await session.flush() # ID olish uchun
                
                # 2. Qatorlar va Joylarni yaratish
                for r_idx, r_info in data['row_data'].items():
                    db_row = Row(
                        concert_id=new_concert.id, 
                        row_number=r_idx, 
                        price=r_info['price']
                    )
                    session.add(db_row)
                    await session.flush()
                    
                    for s_idx in range(1, r_info['seats'] + 1):
                        db_seat = Seat(
                            row_id=db_row.id, 
                            seat_number=s_idx, 
                            is_booked=False
                        )
                        session.add(db_seat)
                
                await session.commit()
                
                # Yakuniy xabar
                await message.answer_photo(
                    photo=data['reklama_photo'],
                    caption=f"✅ ****KONCERT TABÍSLÍ DÚZILDI!**\n\n"
                            f"🎸 Ati: {data['name']}\n"
                            f"📅 Waqti : {data['day']}-{data['month']} {data['year']} soat {data['time']}\n"
                            f"🔢 Qatarlar: {total_rows} ta",
                    parse_mode="Markdown"
                )
                await message.answer("🛠 Admin paneliga qaytdingiz:", reply_markup=get_admin_main_kb(message.from_user.id == SUPER_ADMIN_ID))
                await state.clear()
                
            except Exception as e:
                logging.error(f"Koncert saqlawda qáte: {e}")
                await message.answer("❌ Bazaǵa saqlawda qáte júz berdi. Qayta urınıń.")

# =====================================================================
# STATISTIKA VA ADMIN QO'SHISH
# =====================================================================
@router.callback_query(F.data == "show_stats")
async def admin_stats_handler(call: CallbackQuery):
    async with async_session() as session:
        # Algoritm 23-band: Nechta sotildi, nechta bo'sh
        total_s = await session.execute(select(func.count(Seat.id)))
        booked_s = await session.execute(select(func.count(Seat.id)).where(Seat.is_booked == True))
        
        t = total_s.scalar() or 0
        b = booked_s.scalar() or 0
        
        await call.message.edit_text(
            f"📊 **Bot Statistikasi:**\n\n"
            f"🎫 Ulıwma orinlar: {t}\n"
            f"✅ Satilgan/Bron: {b}\n"
            f"⏳ Bo's orinlar: {t - b}",
            reply_markup=get_cancel_kb(),
            parse_mode="Markdown"
        )

@router.callback_query(F.data == "add_admin")
async def add_admin_call(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("👤 Taza adminning Telegram ID sini yuboring:", reply_markup=get_cancel_kb())
    await state.set_state(AdminStates.waiting_for_admin_id)

@router.message(AdminStates.waiting_for_admin_id)
async def add_admin_db(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("ID raqam bo'lishi kerak!")
    
    async with async_session() as session:
        new_a = AdminUser(tg_id=int(message.text), name=f"Admin_{message.text}")
        session.add(new_a)
        await session.commit()
        await message.answer(f"✅ ID: {message.text} Tabisli bazaga Admin qilib qo'sildi!")
        await state.clear()
        await message.answer("🛠 Admin panel:", reply_markup=get_admin_main_kb(message.from_user.id == SUPER_ADMIN_ID))

# =====================================================================
# FOIDALANUVCHI BILAN BOG'LANISH
# =====================================================================
@router.callback_query(F.data == "contact_admin")
async def contact_admin_handler(call: CallbackQuery):
    # Algoritm 42-band
    await call.message.answer(
        f"👨‍💻 **Admin menen baylanısıw:**\n\n"
        f"📞 Tel: `{ADMIN_PHONE}`\n"
        f"💬 Telegram: {ADMIN_USERNAME}",
        parse_mode="Markdown"
    )
    await call.answer()

# =====================================================================
# BILET SOTISH LOGIKASI (ALGORITM 8, 9, 10-BANDLAR)
# =====================================================================

@router.callback_query(F.data == "sell_ticket")
async def sell_ticket_start(call: CallbackQuery):
    """Admin bilet sotish tugmasini bossa kiritilgan hamma qatorlar chiqadi """
    if not await check_is_admin(call.from_user.id):
        return await call.answer("Bungan ruxsatingiz joq!", show_alert=True)

    async with async_session() as session:
        # Oxirgi faol konsertni aniqlash
        concert_res = await session.execute(select(Concert).order_by(Concert.id.desc()).limit(1))
        concert = concert_res.scalar_one_or_none()
        
        if not concert:
            return await call.message.edit_text("❌ Ele biranta da koncert jaratilmagan!", reply_markup=get_cancel_kb())

        # Qatorlarni olish
        rows_res = await session.execute(select(Row).where(Row.concert_id == concert.id).order_by(Row.row_number))
        rows = rows_res.scalars().all()
        
        if not rows:
            return await call.message.edit_text("❌ Bul koncert ushın qatarlar kirgizilmegen!", reply_markup=get_cancel_kb())

        keyboard = []
        # Har bir qator uchun inline tugma 
        for r in rows:
            keyboard.append([InlineKeyboardButton(
                text=f"Qatar: {r.row_number} | Bahasi: {r.price} so'm", 
                callback_data=f"sel_row_{r.id}"
            )])
        
        keyboard.append([InlineKeyboardButton(text="🔙 Artaqa", callback_data="back_to_main")])
        
        await call.message.edit_text(
            f"🏟 **{concert.name}**\n\nIltimas, satiw ushun qatardi tanlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode="Markdown"
        )

@router.callback_query(F.data.startswith("sel_row_"))
async def sell_ticket_select_seat(call: CallbackQuery):
    """Qatar tanlanganda sol qatardaǵı barlıq orınlar shiģip ketedi. """
    row_id = int(call.data.split("_")[2])
    
    async with async_session() as session:
        # Qator ma'lumotlarini olish
        row_res = await session.execute(select(Row).where(Row.id == row_id))
        row = row_res.scalar_one()
        
        # Joylarni olish
        seats_res = await session.execute(select(Seat).where(Seat.row_id == row_id).order_by(Seat.seat_number))
        seats = seats_res.scalars().all()
        
        keyboard = [[]]
        row_idx = 0
        
        for s in seats:
            # Band bo'lgan joylarni qizil, bo'sh joylarni yashil belgimiz
            status_emoji = "🔴" if s.is_booked else "🟢"
            btn_text = f"{status_emoji} {s.seat_number}"
            
            # Agar joy band bo'lsa, bosish imkonini bermaymiz yoki ogohlantiramiz
            cb_data = f"sel_seat_{s.id}" if not s.is_booked else "seat_taken"
            
            if len(keyboard[row_idx]) >= 5: # Bir qatorda 5 ta tugma
                keyboard.append([])
                row_idx += 1
            
            keyboard[row_idx].append(InlineKeyboardButton(text=btn_text, callback_data=cb_data))
        
        keyboard.append([InlineKeyboardButton(text="🔙 Qatarlarga qaytiw", callback_data="sell_ticket")])
        
        await call.message.edit_text(
            f"💺 **{row.row_number}-qatar** tanlandi.\nBahasi: `{row.price}` so'm.\n\nSatiw ushun orindi tanlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode="Markdown"
        )

@router.callback_query(F.data == "seat_taken")
async def seat_taken_handler(call: CallbackQuery):
    await call.answer("❌ Bul jer álleqashan satılǵan!", show_alert=True)

@router.callback_query(F.data.startswith("sel_seat_"))
async def sell_ticket_get_name(call: CallbackQuery, state: FSMContext):
    seat_id = int(call.data.split("_")[2])
    
    async with async_session() as session:
        seat_res = await session.execute(select(Seat).where(Seat.id == seat_id))
        seat = seat_res.scalar_one()
        
        await state.update_data(target_seat_id=seat_id)
        
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Artaqa", callback_data=f"sel_row_{seat.row_id}")]
        ])
        
        try:
            # Xabarni o'zgartirishga urinamiz
            await call.message.edit_text(
                f"👤 **Orin {seat.seat_number} tańlandı.**\n\nBilet iyesiniń atı hám familiyasın kirgiziń:",
                reply_markup=back_kb,
                parse_mode="Markdown"
            )
        except TelegramBadRequest:
            # Agar foydalanuvchi tugmani 2 marta bossa va xabar o'zgarmasa, xatoni jimgina o'tkazib yuboramiz
            pass
            
        await state.set_state(SellTicketStates.waiting_for_customer_name)
        
        # Tugma bosilganda soat kabi aylanib qolmasligi uchun
        await call.answer()

@router.message(SellTicketStates.waiting_for_customer_name)
async def sell_ticket_finalize(message: Message, state: FSMContext):
    """Atı kirgizilgennen keyin ózine tán QR kodlı bilet jaratadı"""
    user_data = await state.get_data()
    seat_id = user_data.get('target_seat_id') 
    full_name = message.text #
    
    async with async_session() as session:
        try:
            # 1. Ma'lumotlarni bazadan olish
            res = await session.execute(
                select(Seat, Row, Concert)
                .join(Row, Seat.row_id == Row.id)
                .join(Concert, Row.concert_id == Concert.id)
                .where(Seat.id == seat_id)
            )
            data = res.fetchone()
            
            if not data:
                return await message.answer("❌ Xatelik: orin tapilmadi.")
                
            seat, row, concert = data
            
            # 2. HAR SAFAR YANGI VA UNIKAL KOD YARATISH
            # uuid4() har bir bilet uchun takrorlanmas kod beradi
            unique_code = f"TICK-{uuid.uuid4().hex[:8].upper()}"
            
            # 3. Bazani yangilash
            seat.is_booked = True
            seat.booked_by_name = full_name
            
            # 4. Biletni saqlash
            new_ticket = Ticket(seat_id=seat.id, qr_code=unique_code, is_used=False)
            session.add(new_ticket)
            await session.commit() 
            
            # 5. BILETNI GENERATSIYA QILISH
            # Bu yerda sizning utils dagi funksiyangiz chaqiriladi
            ticket_buf = generate_ticket(
                concert_name=concert.name,
                row=row.row_number,
                seat=seat.seat_number,
                user_name=full_name,
                concert_time=concert.date,
                qr_data=unique_code # QR kod aynan shu kodni o'z ichiga oladi
            )
            
            # 6. Rasmni yuborish
            photo = BufferedInputFile(ticket_buf.read(), filename=f"ticket_{unique_code}.png")
            
            await message.answer_photo(
                photo=photo,
                caption=(
                    f"✅ **Bilet tabisli satildi!**\n\n"
                    f"👤 Mijaz: {full_name}\n"
                    f"🎫 Bilet kodi: `{unique_code}`\n\n"
                    f"Skaner ushun tayyar!"
                ),
                parse_mode="Markdown"
            )
            
            await state.clear()
            await message.answer("🛠 Admin panel:", reply_markup=get_admin_main_kb(message.from_user.id == SUPER_ADMIN_ID))

        except Exception as e:
            logging.error(f"QR kod jaratıwda qáte: {e}")
            await message.answer("❌ QR kodlı biletti tayarlawda qátelik júz berdi.")
@router.callback_query(F.data == "send_scanner_link")
async def send_scanner_link_handler(call: CallbackQuery):
    """Super admin QR kod silteme túymesin basqanda isleydi"""
    await call.message.answer(
        f"🌐 **QR Skaner veb-saytı mánzili:**\n\n"
        f"🔗 {WEB_APP_URL}\n\n"
        f"👆 Bul siltemeni nusqalap alıń yamasa ústine basıp brauzerde (Chrome, Safari) ashıń. "
        f"Bul mánzildi tek isenimli adminlerge beriń!",
        parse_mode="Markdown"
    )
    await call.answer()