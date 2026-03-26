import os


def generate_tree(directory, prefix="", output_lines=None):
    if output_lines is None:
        output_lines = []

    # Получаем список всего в папке
    try:
        entries = sorted(os.listdir(directory))
    except PermissionError:
        return output_lines

    # --- НАСТРОЙКИ ФИЛЬТРАЦИИ ---

    # 1. Игнорировать по точному имени (папки или файлы)
    ignore_names = ['.git', '.godot', '__pycache__', 'venv']

    # 2. Игнорировать файлы по расширению (с точкой в начале)
    # Добавь сюда расширения, которые не должны попадать в дерево
    ignore_extensions = ['.import', '.tmp', '.log', '.bak', '.docp', '.docg',
                         '.uid']

    # 3. Папки, где нужно скрыть содержимое (показать только имя папки)
    skip_content_dirs = ['assets', 'images', 'doc']

    # --- ЛОГИКА ОБРАБОТКИ ---

    # Формируем отфильтрованный список
    filtered_entries = []
    for entry in entries:
        # Пропускаем скрытые файлы (начинаются с точки)
        if entry.startswith('.'):
            continue

        # Пропускаем по имени
        if entry in ignore_names:
            continue

        # Получаем расширение файла
        _, ext = os.path.splitext(entry)

        # Пропускаем по расширению
        if ext in ignore_extensions:
            continue

        filtered_entries.append(entry)

    # Сортируем список перед выводом
    entries = sorted(filtered_entries)

    for index, entry in enumerate(entries):
        path = os.path.join(directory, entry)
        connector = "└── " if index == len(entries) - 1 else "├── "

        output_lines.append(f"{prefix}{connector}{entry}")

        if os.path.isdir(path):
            # Если папка в списке "показать пустой", то внутрь не заходим
            if entry in skip_content_dirs:
                continue

            extension = "    " if index == len(entries) - 1 else "│   "
            generate_tree(path, prefix + extension, output_lines)

    return output_lines


# --- ЗАПУСК ---

project_dir = "."

# Создаем папку для документации, если её нет
os.makedirs('./doc', exist_ok=True)

# Формируем дерево
tree_lines = [os.path.basename(os.path.abspath(project_dir)) + "/"]
generate_tree(project_dir, "", tree_lines)

# Сохраняем результат
with open('./doc/tree.txt', mode='w', encoding='UTF8') as file:
    print("\n".join(tree_lines), file=file)

print("Готово! Структура сохранена в ./doc/tree.txt")