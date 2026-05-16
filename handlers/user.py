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
    """Paydalanıwshılar ushın tiykarģı inline menyu (Súwretli setka dizayn)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        # 1-qator: Ikkita tugma yonma-yon
        [
            InlineKeyboardButton(text="🎫 Bilet satıp alıw", callback_data="buy_ticket"),
            InlineKeyboardButton(text="ℹ️ Koncert haqqında", callback_data="concert_info")
        ],
        # 2-qator: Bog'lanish tugmasi to'liq eniga joylashadi
        [
            InlineKeyboardButton(text="📞 Admin bilan bog'lanish", callback_data="contact_admin_user")
        ]
    ])

@router.callback_query(F.data == "user_main_menu")
async def back_to_user_main(call: CallbackQuery):
    """Paydalanıwshı artqa qaytqanda jáne tiykarǵı menyu shıǵıwı [cite: 25, 41]"""
    await call.message.delete()
    await call.message.answer(
        f"Salem {call.from_user.first_name}! 👋\n\n"
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
            f"📅 **Waqiti:** {concert.date}\n\n"
            f"🎉 Sizdi ájayıp koncert baǵdarlaması kútpekte! Biletlerdi házir-aq bánt etiń."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Artqa", callback_data="user_main_menu")]
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
    """Zal súwreti hám admin kirgizgen qatarlardı inline menyude kórsetiw """
    async with async_session() as session:
        res = await session.execute(select(Concert).order_by(Concert.id.desc()).limit(1))
        concert = res.scalar_one_or_none()
        
        if not concert:
            return await call.answer("Házirshe satıwda biletler joq!", show_alert=True)
            
        # Shu konsertga tegishli hamma qatorlarni tortib olamiz
        rows_res = await session.execute(select(Row).where(Row.concert_id == concert.id).order_by(Row.row_number))
        rows = rows_res.scalars().all()
        
        if not rows:
            return await call.answer("Qatarlar ele kiritilmagen!", show_alert=True)
        
        # Qatorlarni yonma-yon chiroyli qilib teramiz (masalan, 3 tadan bir qatorda) [cite: 30]
        kb_list = []
        row_btns = []
        for r in rows:
            row_btns.append(InlineKeyboardButton(text=f"{r.row_number}-qatar", callback_data=f"usr_row_{r.id}"))
            if len(row_btns) == 3: # 3 tadan terish dizayni
                kb_list.append(row_btns)
                row_btns = []
        if row_btns:
            kb_list.append(row_btns)
            
        # Orqaga tugmasi [cite: 41]
        kb_list.append([InlineKeyboardButton(text="🔙 Artqa", callback_data="user_main_menu")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
        
        await call.message.delete()
        await call.message.answer_photo(
            photo=concert.photo_zal, 
            caption="🏟 **Zal ko'rinisi**\n\nIltimas, ózińizge qolaylı qatarlardan birin tańlań:", 
            parse_mode="Markdown", 
            reply_markup=kb
        )

# =====================================================================
# 3. QATOR BOSILGANDA (NARX VA ADMIN LICHKASI)
# =====================================================================
@router.callback_query(F.data.startswith("usr_row_"))
async def user_row_selected(call: CallbackQuery):
    """Qatar tanlanganda bahası hám baylanıs túymeleri shıģarıwı. """
    row_id = int(call.data.split("_")[2])
    
    async with async_session() as session:
        row_res = await session.execute(select(Row).where(Row.id == row_id))
        row = row_res.scalar_one()
        
        # URL (Link) ga aylantirish uchun @ belgisini olib tashlaymiz
        admin_url = f"https://t.me/{ADMIN_USERNAME.replace('@', '')}"
        
        # 3 ta tugma: Admin lichkasi, Tel raqami, Orqaga [cite: 36, 37, 39, 40, 41]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Admin lichkasi", url=admin_url)],
            [InlineKeyboardButton(text="📞 Tel nomeri", callback_data="usr_show_phone")],
            [InlineKeyboardButton(text="🔙 Arqaga", callback_data="buy_ticket")]
        ])
        
        # Xuddi zal rasmi o'zgarmasdan, tagidagi matni o'zgaradi [cite: 34, 35]
        await call.message.edit_caption(
            caption=f"🎫 **{row.row_number}-qatar** bahasi: `{row.price}` so'm\n\n"
                    f"Biletti bronlaw hám satıp alıw ushın tómendegi túymeler arqalı admin menen baylanısıń. 👇",
            parse_mode="Markdown",
            reply_markup=kb
        )

# =====================================================================
# 4. TELEFON RAQAMIDAN NUSXA OLISH
# =====================================================================
@router.callback_query(F.data == "usr_show_phone")
async def usr_show_phone(call: CallbackQuery):
    """Admin telefon nomerin ańsat ǵana nusqalaw ushın kórsetiw """
    # Raqamni markdown dagi ` ` ichiga olsak, telegramda ustiga bossa o'zi copy qilib oladi
    await call.message.answer(
        f"📞 **Admin telefon nomeri**\n\n"
        f"Nusqa (copy) alıw ushın san ústine basıń:\n"
        f"`{ADMIN_PHONE}`",
        parse_mode="Markdown"
    )
    await call.answer()

# =====================================================================
# 5. ADMIN BILAN BOG'LANISH (ASOSIY MENYUDAN)
# =====================================================================
@router.callback_query(F.data == "contact_admin_user")
async def contact_admin_user_handler(call: CallbackQuery):
    """Paydalanıwshı menyusindegi baylanıs túymesi [cite: 42]"""
    await call.message.answer(
        f"👨‍💻 **Admin menen baylanısıw:**\n\n"
        f"📞 Tel: `{ADMIN_PHONE}`\n"
        f"💬 Telegram: {ADMIN_USERNAME}",
        parse_mode="Markdown"
    )
    await call.answer()