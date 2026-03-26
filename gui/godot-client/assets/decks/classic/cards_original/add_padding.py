from PIL import Image, ImageOps
import os

# --- НАСТРОЙКИ ---
input_folder = "./cards_original"  # Папка с исходными картинками
output_folder = "./cards_padded"  # Куда сохранить результат
padding = 2  # Сколько пикселей добавить по краям
# -----------------

# Создаем выходную папку, если её нет
if not os.path.exists(output_folder):
    os.makedirs(output_folder)


def process_image(filename):
    try:
        # Открываем изображение и гарантируем наличие альфа-канала (прозрачности)
        img = Image.open(os.path.join(input_folder, filename)).convert("RGBA")

        # Добавляем отступы.
        # expand=True увеличивает размер холста, не растягивая картинку
        # fill=0 добавляет прозрачные пиксели (RGBA = 0,0,0,0)
        img_with_padding = ImageOps.expand(img, border=padding, fill=0)

        # Сохраняем
        img_with_padding.save(os.path.join(output_folder, filename))
        print(f"Обработано: {filename}")
    except Exception as e:
        print(f"Ошибка с файлом {filename}: {e}")


# Запуск перебора файлов
print("Начинаем обработку...")
count = 0
for filename in os.listdir(input_folder):
    if filename.lower().endswith((".png", ".jpg", ".jpeg")):  # Можно оставить только .png
        process_image(filename)
        count += 1

print(f"Готово! Обработано файлов: {count}")