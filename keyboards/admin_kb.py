from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Bilet haqida", callback_data="admin_concert_info")],
        [InlineKeyboardButton(text="➕ Bilet kiritish", callback_data="admin_add_tickets")],
        [InlineKeyboardButton(text="💰 Bilet sotish", callback_data="admin_sell_ticket")],
        [InlineKeyboardButton(text="🔍 QR Scanner", callback_data="admin_qr_scanner")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")]
    ])

def get_back_kb(callback_data):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=callback_data)]
    ])

def get_cancel_back_kb(back_callback):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back_callback)],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_main")]
    ])
