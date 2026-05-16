import qrcode
from PIL import Image, ImageDraw, ImageFont
import io

try:
    FONT_PATH = "C:\\Windows\\Fonts\\arial.ttf"
    font_bold = ImageFont.truetype(FONT_PATH, 30)
    font_regular = ImageFont.truetype(FONT_PATH, 20)
    font_small = ImageFont.truetype(FONT_PATH, 16)
except:
    font_bold = ImageFont.load_default()
    font_regular = ImageFont.load_default()
    font_small = ImageFont.load_default()

def generate_ticket(concert_name, row, seat, user_name, concert_time, qr_data):
    width, height = 800, 300
    white = (255, 255, 255)
    black = (0, 0, 0)
    accent = (40, 40, 40)

    img = Image.new('RGB', (width, height), color=white)
    draw = ImageDraw.Draw(img)

    draw.rectangle([10, 10, width-10, height-10], outline=black, width=3)
    draw.line([(250, 20), (250, 280)], fill=black, width=2)

    qr = qrcode.QRCode(version=1, box_size=7, border=1)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    img.paste(qr_img, (30, 40))
    draw.text((60, 240), "SCAN ME", font=font_small, fill=black)

    info_x = 280
    draw.text((info_x, 30), "KONCЕRT CHIPTESI", font=font_small, fill=accent)
    draw.text((info_x, 60), concert_name.upper(), font=font_bold, fill=black)

    draw.text((info_x, 120), f"QATAR: {row}", font=font_regular, fill=black)
    draw.text((info_x + 200, 120), f"JOY: {seat}", font=font_regular, fill=black)

    draw.text((info_x, 170), f"FOYDALANUVCHI: {user_name}", font=font_regular, fill=black)
    draw.text((info_x, 210), f"Waqt: {concert_time}", font=font_regular, fill=accent)

    draw.text((info_x, 250), "Bileti kiriste korseting.", font=font_small, fill=accent)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf