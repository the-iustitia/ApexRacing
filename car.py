import os
import json

# Путь к папке с картинками
folder_path = r"/home/mrnothing/Рабочий стол/Workspace/Apex Racing/images"  # ← Заменить на свой путь

# Расширения, которые считаем картинками
image_extensions = ['.jpg', '.jpeg', '.png', '.webp']

# Примерные шансы (можно настроить по вкусу)
default_chance = 0.5

# Получаем список всех файлов в папке
files = os.listdir(folder_path)

# Фильтруем только картинки
images = [f for f in files if os.path.splitext(f)[1].lower() in image_extensions]

# Строим список объектов
cars = []
for filename in sorted(images):
    name_raw = os.path.splitext(filename)[0]  # Без расширения
    image = filename

    # Преобразуем имя файла в отображаемое название
    name = name_raw.replace("_", "/").replace("-", " ").title()

    cars.append({
        "name": name,
        "image": image,
        "chance": default_chance  # Можно тут делать рандом или на основе правил
    })

# Выводим как JSON
json_output = json.dumps(cars, indent=4, ensure_ascii=False)
print(json_output)

# (по желанию) сохранить в файл
with open("cars.json", "w", encoding="utf-8") as f:
    f.write(json_output)
