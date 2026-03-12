from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random
import string
import os

def generate_captcha_image() -> tuple:
    """Генерирует сильно искаженное изображение капчи с буквами/цифрами"""
    
    # Генерируем случайный код (5-6 символов)
    length = random.randint(5, 6)
    chars = string.ascii_uppercase + string.digits
    # Исключаем совсем похожие символы
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    chars = chars.replace('S', '').replace('5', '').replace('Z', '').replace('2', '')
    code = ''.join(random.choices(chars, k=length))
    
    print(f"Сгенерирован код: {code}")
    
    # БОЛЬШОЙ РАЗМЕР ИЗОБРАЖЕНИЯ
    width, height = 900, 300
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # 1. СЛОЖНЫЙ ГРАДИЕНТНЫЙ ФОН
    for y in range(height):
        r = int(150 + 105 * (y / height) + random.randint(-20, 20))
        g = int(100 + 155 * (y / height) + random.randint(-20, 20))
        b = int(200 + 55 * (y / height) + random.randint(-20, 20))
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # 2. МНОЖЕСТВО ШУМОВЫХ ЛИНИЙ
    for _ in range(random.randint(20, 30)):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        line_color = (
            random.randint(0, 80),
            random.randint(0, 80),
            random.randint(0, 80)
        )
        line_width = random.randint(1, 3)
        draw.line([(x1, y1), (x2, y2)], fill=line_color, width=line_width)
    
    # 3. МНОЖЕСТВО ШУМОВЫХ ТОЧЕК
    for _ in range(random.randint(2500, 3500)):
        x = random.randint(0, width)
        y = random.randint(0, height)
        point_color = (
            random.randint(0, 120),
            random.randint(0, 120),
            random.randint(0, 120)
        )
        draw.point((x, y), fill=point_color)
    
    # 4. СЛУЧАЙНЫЕ ГЕОМЕТРИЧЕСКИЕ ФИГУРЫ
    for _ in range(random.randint(5, 8)):
        shape_type = random.choice(['rectangle', 'ellipse'])
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(x1, min(x1 + 150, width))
        y2 = random.randint(y1, min(y1 + 80, height))
        shape_color = (
            random.randint(100, 180),
            random.randint(100, 180),
            random.randint(100, 180)
        )
        if shape_type == 'rectangle':
            draw.rectangle([(x1, y1), (x2, y2)], fill=shape_color, outline=None)
        else:
            draw.ellipse([(x1, y1), (x2, y2)], fill=shape_color, outline=None)
    
    # 5. ЗАГРУЗКА ШРИФТА
    try:
        font_paths = [
            "arial.ttf",
            "C:\\Windows\\Fonts\\Arial.ttf",
            "C:\\Windows\\Fonts\\Impact.ttf",
            "C:\\Windows\\Fonts\\Comic.ttf",
            "C:\\Windows\\Fonts\\Verdana.ttf"
        ]
        font = None
        for path in font_paths:
            try:
                font = ImageFont.truetype(path, 70)
                print(f"Шрифт загружен: {path}")
                break
            except:
                continue
        if not font:
            font = ImageFont.load_default()
            print("Используется шрифт по умолчанию")
    except:
        font = ImageFont.load_default()
        print("Используется шрифт по умолчанию")
    
    # 6. РИСУЕМ КАЖДУЮ БУКВУ С ИСКАЖЕНИЯМИ
    x_offset = 50
    positions = []
    
    for char in code:
        # Создаем отдельное изображение для буквы
        char_img = Image.new('RGBA', (120, 150), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        
        # Разные цвета для каждой буквы
        color = (
            random.randint(20, 80),
            random.randint(20, 80),
            random.randint(20, 80)
        )
        
        # Рисуем букву
        char_draw.text((20, 30), char, fill=color, font=font)
        
        # Применяем искажения
        angle = random.randint(-30, 30)
        char_img = char_img.rotate(angle, expand=1, fillcolor=(0, 0, 0, 0))
        
        if random.choice([True, False]):
            new_width = int(char_img.width * random.uniform(0.8, 1.2))
            new_height = int(char_img.height * random.uniform(0.8, 1.2))
            char_img = char_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        char_img = char_img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.3, 0.7)))
        
        positions.append((x_offset, char_img))
        x_offset += char_img.width + random.randint(20, 30)
    
    # Центрируем все буквы
    total_width = positions[-1][0] + positions[-1][1].width - positions[0][0]
    start_x = (width - total_width) // 2
    y_pos = (height - 150) // 2 + random.randint(-20, 20)
    
    for x, char_img in positions:
        new_x = start_x + (x - positions[0][0])
        image.paste(char_img, (new_x, y_pos), char_img)
    
    # 7. ДОПОЛНИТЕЛЬНЫЙ ШУМ ПОВЕРХ БУКВ
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    for _ in range(random.randint(5, 10)):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        overlay_draw.line([(x1, y1), (x2, y2)], 
                         fill=(random.randint(100, 150), 
                               random.randint(100, 150), 
                               random.randint(100, 150), 100),
                         width=1)
    
    image = Image.alpha_composite(image.convert('RGBA'), overlay)
    image = image.convert('RGB')
    
    # 8. ФИНАЛЬНОЕ РАЗМЫТИЕ
    blur_radius = random.uniform(0.5, 1.2)
    image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    
    return image, code

def save_captcha_samples(count=5):
    """Сохраняет несколько примеров капчи для тестирования"""
    
    if not os.path.exists("captcha_samples"):
        os.makedirs("captcha_samples")
    
    print(f"\nГенерация {count} примеров капчи...")
    print("-" * 50)
    
    for i in range(1, count + 1):
        image, code = generate_captcha_image()
        filename = f"captcha_samples/captcha_{i}_{code}.png"
        image.save(filename, 'PNG', quality=95)
        print(f"Пример {i}: код = {code} -> сохранен как {filename}")
    
    print("-" * 50)
    print(f"Все примеры сохранены в папку 'captcha_samples'")

def test_single_captcha():
    """Генерирует и показывает одну капчу"""
    
    print("\nГенерация одной капчи для теста...")
    print("-" * 50)
    
    image, code = generate_captcha_image()
    
    filename = "test_captcha.png"
    image.save(filename, 'PNG', quality=95)
    
    print(f"✅ Код капчи: {code}")
    print(f"✅ Изображение сохранено как: {filename}")
    print(f"✅ Размер изображения: {image.size}")
    print("-" * 50)
    print("👉 Откройте файл test_captcha.png чтобы увидеть результат")

if __name__ == "__main__":
    print("=" * 60)
    print("🍬 ТЕСТ ГЕНЕРАЦИИ КАПЧИ 🍬")
    print("=" * 60)
    
    while True:
        print("\n📋 Выберите действие:")
        print("1 - Сгенерировать одну капчу (test_captcha.png)")
        print("2 - Сгенерировать 5 примеров")
        print("3 - Сгенерировать 10 примеров")
        print("0 - Выход")
        
        choice = input("\n👉 Ваш выбор: ").strip()
        
        if choice == "1":
            test_single_captcha()
        elif choice == "2":
            save_captcha_samples(5)
        elif choice == "3":
            save_captcha_samples(10)
        elif choice == "0":
            print("\n👋 Выход...")
            break
        else:
            print("\n❌ Неверный выбор, попробуйте снова")