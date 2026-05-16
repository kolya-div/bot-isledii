from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from database.db import async_session
from database.models import Concert, Row
from config import ADMIN_PHONE, ADMIN_USERNAME

router = Router()

# =====================================================================
# ASOSIY FOYDALANUVCHI MENYUSI
# =====================================================================
def get_user_main_kb():
    """Foydalanuvchilar uchun asosiy inline menyu (Chiroyli grid dizayn)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        # 1-qator: Ikkita tugma yonma-yon
        [
            InlineKeyboardButton(text="🎫 Bilet sotib olish", callback_data="buy_ticket"),
            InlineKeyboardButton(text="ℹ️ Konsert haqida", callback_data="concert_info")
        ],
        # 2-qator: Bog'lanish tugmasi to'liq eniga joylashadi
        [
            InlineKeyboardButton(text="📞 Admin bilan bog'lanish", callback_data="contact_admin_user")
        ]
    ])

@router.callback_query(F.data == "user_main_menu")
async def back_to_user_main(call: CallbackQuery):
    """Foydalanuvchi orqaga qaytganda yana asosiy menyu chiqishi [cite: 25, 41]"""
    await call.message.delete()
    await call.message.answer(
        f"Salom {call.from_user.first_name}! 👋\n\n"
        f"Konsert biletlari botiga xush kelibsiz. Kerakli bo'limni tanlang:",
        reply_markup=get_user_main_kb()
    )

# =====================================================================
# 1. KONSERT HAQIDA
# =====================================================================
@router.callback_query(F.data == "concert_info")
async def show_concert_info(call: CallbackQuery):
    """Konsert haqida ma'lumot va reklama rasmini chiqarish """
    async with async_session() as session:
        # Oxirgi faol konsertni topamiz
        res = await session.execute(select(Concert).order_by(Concert.id.desc()).limit(1))
        concert = res.scalar_one_or_none()
        
        if not concert:
            return await call.answer("Tez orada yangi konsert e'lon qilinadi!", show_alert=True)
            
        caption = (
            f"🎸 **{concert.name}**\n\n"
            f"📅 **Vaqti:** {concert.date}\n\n"
            f"🎉 Sizni ajoyib konsert dasturi kutmoqda! Biletlarni hoziroq band qiling."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="user_main_menu")]
        ])
        
        # Eski xabarni o'chirib, rasmli xabar yuboramiz
        await call.message.delete()
        await call.message.answer_photo(
            photo=concert.photo_reklama, 
            caption=caption, 
            parse_mode="Markdown", 
            reply_markup=kb
        )

# =====================================================================
# 2. BILET SOTIB OLISH (QATORLARNI TANLASH)
# =====================================================================
@router.callback_query(F.data == "buy_ticket")
async def show_buy_ticket(call: CallbackQuery):
    """Zal rasmi va admin kiritgan qatorlarni inline menyuda chiqarish """
    async with async_session() as session:
        res = await session.execute(select(Concert).order_by(Concert.id.desc()).limit(1))
        concert = res.scalar_one_or_none()
        
        if not concert:
            return await call.answer("Hozircha sotuvda biletlar yo'q!", show_alert=True)
            
        # Shu konsertga tegishli hamma qatorlarni tortib olamiz
        rows_res = await session.execute(select(Row).where(Row.concert_id == concert.id).order_by(Row.row_number))
        rows = rows_res.scalars().all()
        
        if not rows:
            return await call.answer("Qatorlar hali kiritilmagan!", show_alert=True)
        
        # Qatorlarni yonma-yon chiroyli qilib teramiz (masalan, 3 tadan bir qatorda) [cite: 30]
        kb_list = []
        row_btns = []
        for r in rows:
            row_btns.append(InlineKeyboardButton(text=f"{r.row_number}-qator", callback_data=f"usr_row_{r.id}"))
            if len(row_btns) == 3: # 3 tadan terish dizayni
                kb_list.append(row_btns)
                row_btns = []
        if row_btns:
            kb_list.append(row_btns)
            
        # Orqaga tugmasi [cite: 41]
        kb_list.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="user_main_menu")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
        
        await call.message.delete()
        await call.message.answer_photo(
            photo=concert.photo_zal, 
            caption="🏟 **Zal ko'rinishi**\n\nIltimos, o'zingizga qulay qatorlardan birini tanlang:", 
            parse_mode="Markdown", 
            reply_markup=kb
        )

# =====================================================================
# 3. QATOR BOSILGANDA (NARX VA ADMIN LICHKASI)
# =====================================================================
@router.callback_query(F.data.startswith("usr_row_"))
async def user_row_selected(call: CallbackQuery):
    """Qator tanlanganda narxi va bog'lanish tugmalari chiqishi """
    row_id = int(call.data.split("_")[2])
    
    async with async_session() as session:
        row_res = await session.execute(select(Row).where(Row.id == row_id))
        row = row_res.scalar_one()
        
        # URL (Link) ga aylantirish uchun @ belgisini olib tashlaymiz
        admin_url = f"https://t.me/{ADMIN_USERNAME.replace('@', '')}"
        
        # 3 ta tugma: Admin lichkasi, Tel raqami, Orqaga [cite: 36, 37, 39, 40, 41]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Admin lichkasi", url=admin_url)],
            [InlineKeyboardButton(text="📞 Tel raqami", callback_data="usr_show_phone")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="buy_ticket")]
        ])
        
        # Xuddi zal rasmi o'zgarmasdan, tagidagi matni o'zgaradi [cite: 34, 35]
        await call.message.edit_caption(
            caption=f"🎫 **{row.row_number}-qator** narxi: `{row.price}` so'm\n\n"
                    f"Biletni bron qilish va sotib olish uchun quyidagi tugmalar orqali admin bilan bog'laning 👇",
            parse_mode="Markdown",
            reply_markup=kb
        )

# =====================================================================
# 4. TELEFON RAQAMIDAN NUSXA OLISH
# =====================================================================
@router.callback_query(F.data == "usr_show_phone")
async def usr_show_phone(call: CallbackQuery):
    """Admin tel raqamini osongina nusxa (copy) olish uchun chiqarish """
    # Raqamni markdown dagi ` ` ichiga olsak, telegramda ustiga bossa o'zi copy qilib oladi
    await call.message.answer(
        f"📞 **Admin telefon raqami**\n\n"
        f"Nusxa (copy) olish uchun raqam ustiga bosing:\n"
        f"`{ADMIN_PHONE}`",
        parse_mode="Markdown"
    )
    await call.answer()

# =====================================================================
# 5. ADMIN BILAN BOG'LANISH (ASOSIY MENYUDAN)
# =====================================================================
@router.callback_query(F.data == "contact_admin_user")
async def contact_admin_user_handler(call: CallbackQuery):
    """Foydalanuvchi menyusidagi bog'lanish tugmasi [cite: 42]"""
    await call.message.answer(
        f"👨‍💻 **Admin bilan bog'lanish:**\n\n"
        f"📞 Tel: `{ADMIN_PHONE}`\n"
        f"💬 Telegram: {ADMIN_USERNAME}",
        parse_mode="Markdown"
    )
    await call.answer()