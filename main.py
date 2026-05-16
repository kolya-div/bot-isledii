import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Konfiguratsiya faylidan kerakli o'zgaruvchilarni chaqirib olamiz
from config import BOT_TOKEN
from database.db import init_db, async_session
from database.models import Ticket, Seat, Row, Concert

# Routerlarni import qilamiz (admin va foydalanuvchi qismlari uchun)
from handlers import admin, user

# =====================================================================
# NGROK VA NETLIFY UCHUN CORS (RUXSATNOMA) MIDDLEWARE 
# =====================================================================
@web.middleware
async def cors_middleware(request, handler):
    """Skaner (Netlify) dan kelayotgan so'rovlarni bloklamaslik uchun ruxsatnoma"""
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
            
    # Hamma saytlarga va brauzerlarga ulanish uchun yashil chiroq
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = '*'
    return response
# =====================================================================

# ==============================================================================
# XAVFSIZLIK VA CORS SOZLAMALARI
# ==============================================================================
# CORS (Cross-Origin Resource Sharing) - bu brauzer xavfsizlik siyosati.
# Web ilova Telegram ichida yoki Ngrok orqali ochilganda muammo chiqmasligi uchun
# barcha ruxsatlarni (Headers) oldindan belgilab qo'yamiz.
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, ngrok-skip-browser-warning, Accept",
}

# ==============================================================================
# WEB SERVER HANDLERLARI (API YO'NALISHLARI)
# ==============================================================================

async def handle_index(request):
    """
    Asosiy sahifa (Root /).
    Ngrok ulanishini tekshirish uchun ishlatiladi.
    Agar 403 Forbidden xatosi chiqsa, shu funksiya uni oldini oladi.
    """
    return web.Response(
        text="Server muvaffaqiyatli ishlayapti! Ngrok ulanishi faol.", 
        status=200
    )

async def handle_options(request):
    """
    CORS OPTIONS so'rovlarini qayta ishlash.
    Brauzer "bu manzilga so'rov yuborish xavfsizmi?" deb so'raganda,
    shu funksiya "ha, xavfsiz" deb CORS_HEADERS ni qaytaradi.
    """
    return web.Response(headers=CORS_HEADERS)

async def handle_verify(request):
    """
    QR kodni tekshirish uchun GET so'rovi.
    Web-skaner QR kodni o'qiganda ushbu API ga murojaat qiladi.
    """
    qr = request.query.get('qr')
    
    if not qr:
        return web.json_response(
            {'success': False, 'message': 'QR kod yuborilmadi!'}, 
            headers=CORS_HEADERS
        )
        
    async with async_session() as session:
        # Chiptani bazadan qidiramiz, Seat va Row jadvallarini ham qo'shib yuklaymiz
        res = await session.execute(
            select(Ticket)
            .options(selectinload(Ticket.seat).selectinload(Seat.row))
            .where(Ticket.qr_code == qr)
        )
        ticket = res.scalar_one_or_none()
        
        # 1-Holat: Baza bo'yicha bunday QR kod umuman yo'q
        if not ticket:
            return web.json_response(
                {'success': False, 'message': 'Soxta QR code! Bunday chipta yo`q.'}, 
                headers=CORS_HEADERS
            )
            
        # 2-Holat: Chipta bor, lekin avval ishlatib bo'lingan (skaner qilingan)
        if ticket.is_used:
            return web.json_response(
                {'success': False, 'message': 'DIQQAT! Bu chipta avval ishlatilgan!'}, 
                headers=CORS_HEADERS
            )
            
        # 3-Holat: Chipta toza, haqiqiy va ishlatishga tayyor
        return web.json_response({
            'success': True,
            'name': ticket.seat.booked_by_name,
            'row': ticket.seat.row.row_number,
            'seat': ticket.seat.seat_number,
            'time': ticket.created_at.strftime("%Y-%m-%d %H:%M")
        }, headers=CORS_HEADERS)

async def handle_confirm(request):
    """
    Chiptani ishlatilgan deb belgilash uchun POST so'rovi.
    Admin chiptani o'tkazib yuborgach, shu funksiya chiptani "kuygan" qilib belgilaydi.
    """
    qr = request.query.get('qr')
    
    async with async_session() as session:
        # Chiptani bazada qulflash (with_for_update)
        # Bu bir vaqtning o'zida ikkita telefon bitta QR kodni skaner qilganda 
        # ikkalasiga ham ruxsat berib yuborishning oldini oladi (Race condition himoyasi)
        res = await session.execute(
            select(Ticket)
            .where(Ticket.qr_code == qr)
            .with_for_update() 
        )
        ticket = res.scalar_one_or_none()
        
        if ticket:
            if not ticket.is_used:
                # Chiptani ishlatilgan qilib saqlaymiz
                ticket.is_used = True
                await session.commit()
                return web.json_response(
                    {'success': True}, 
                    headers=CORS_HEADERS
                )
            else:
                return web.json_response(
                    {'success': False, 'message': 'Bu chipta allaqachon ishlatib bo`lingan!'}, 
                    headers=CORS_HEADERS
                )
                
        return web.json_response(
            {'success': False, 'message': 'Chipta topilmadi!'}, 
            headers=CORS_HEADERS
        )

# ==============================================================================
# ASOSIY ISHGA TUSHIRISH FUNKSIYASI (MAIN ROUTINE)
# ==============================================================================

async def main():
    """
    Barcha jarayonlarni o'z ichiga olgan asosiy funksiya.
    Botni, ma'lumotlar bazasini va Web serverni bir vaqtda ishga tushiradi.
    """
    # 1. Loglarni sozlash
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout
    )
    logger = logging.getLogger(__name__)
    logger.info("Dastur ishga tushmoqda...")
    
    # 2. Ma'lumotlar bazasini tayyorlash
    logger.info("Ma'lumotlar bazasi tekshirilmoqda...")
    await init_db()
    logger.info("Ma'lumotlar bazasi tayyor!")
    
    # 3. Bot va Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # 4. Routerlarni ulash
    dp.include_router(admin.router)
    dp.include_router(user.router)
    logger.info("Routerlar muvaffaqiyatli ulandi.")
    
    # 5. Web ilovani sozlash
    app = web.Application(middlewares=[cors_middleware])
    
    # ESHIKLAR OCHIQ HOLATDA:
    app.router.add_get('/', handle_index)
    app.router.add_get('/api/verify', handle_verify)  
    app.router.add_post('/api/confirm', handle_confirm)
    app.router.add_options('/api/confirm', handle_options)
    
    # 6. Web serverni ishga tushirish
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    
    print("\n" + "="*50)
    print("🚀 --- SERVER VA BOT ISHGA TUSHDI --- 🚀")
    print("🌐 API Manzili: http://localhost:8080")
    print("="*50 + "\n")
    
    # 7. Botni ishga tushirish
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

# DASTURNI ISHGA TUSHIRUVCHI KALIT (FAYLNING ENG OXIRI)
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Dastur to'xtatildi.")