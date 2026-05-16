from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, BigInteger
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

# Bazaning asosi
Base = declarative_base()

class AdminUser(Base):
    """
    Admin roli: added_at ustuni xatolik bermasligi uchun butunlay olib tashlandi.
    Telegram ID raqamlari katta bo'lgani uchun Integer o'rniga BigInteger qilingan.
    """
    __tablename__ = 'admin_users'
    
    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String)

class Concert(Base):
    """
    Konsert haqida: reklama fotosi, nomi, vaqti va zal surati saqlanadi.
    """
    __tablename__ = 'concerts'
    __table_args__ = {'extend_existing': True} # Qayta aniqlash xatosini oldini oladi
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    date = Column(String) # To'liq sana (kun, oy, yil, soat) 
    photo_reklama = Column(String) # Reklama rasm ID 
    photo_zal = Column(String)      # Zal rasm ID 
    created_at = Column(DateTime, default=datetime.utcnow)

    # Qatorlar bilan bog'liqlik
    rows = relationship("Row", back_populates="concert", cascade="all, delete-orphan")

class Row(Base):
    """
    Bilet kiritish: qatorlar narxi va undagi joylar soni.
    """
    __tablename__ = 'rows'
    
    id = Column(Integer, primary_key=True)
    concert_id = Column(Integer, ForeignKey('concerts.id'))
    row_number = Column(Integer) # Qator raqami 
    price = Column(String)        # Shu qatorning narxi 
    
    # Bog'liqliklar
    concert = relationship("Concert", back_populates="rows")
    seats = relationship("Seat", back_populates="row", cascade="all, delete-orphan")

class Seat(Base):
    """
    Joylar: har bir qatorda nechta joy borligi va bron holati.
    """
    __tablename__ = 'seats'
    
    id = Column(Integer, primary_key=True)
    row_id = Column(Integer, ForeignKey('rows.id'))
    seat_number = Column(Integer) # Joy raqami 
    is_booked = Column(Boolean, default=False) # Bron qilinganmi? 
    booked_by_name = Column(String, nullable=True) # Ism familiya 
    
    # Bog'liqliklar
    row = relationship("Row", back_populates="seats")
    ticket = relationship("Ticket", back_populates="seat", uselist=False)

class Ticket(Base):
    """
    Bilet: QR kod yagona bo'lishi kerak.
    Faqat bir marta skanerlanadi.
    """
    __tablename__ = 'tickets'
    
    id = Column(Integer, primary_key=True)
    seat_id = Column(Integer, ForeignKey('seats.id'))
    qr_code = Column(String, unique=True, index=True) # Yagona QR kod 
    is_used = Column(Boolean, default=False) # Skanerlanganda True bo'ladi 
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Bog'liqliklar
    seat = relationship("Seat", back_populates="ticket")

# Kelajakda statistika uchun qo'shimcha logs jadvali (ixtiyoriy)
class ActionLog(Base):
    __tablename__ = 'action_logs'
    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger) # Bu yerda ham BigInteger qilindi
    action = Column(String) # Masalan: "Bilet sotildi" 
    timestamp = Column(DateTime, default=datetime.utcnow)