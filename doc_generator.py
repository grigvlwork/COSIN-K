import os
import re
from pathlib import Path

# Сохраняем директорию запуска и её имя
BASE_DIR = Path.cwd()
BASE_FOLDER_NAME = BASE_DIR.name


def get_relative_path(file_path):
    """Возвращает путь относительно родителя директории запуска (сохраняя имя папки запуска)."""
    try:
        # Получаем путь относительно родителя BASE_DIR
        rel_path = Path(file_path).relative_to(BASE_DIR.parent)
        return f"./{rel_path}"
    except ValueError:
        # Если файл вне родителя BASE_DIR, возвращаем относительно BASE_DIR с именем папки
        try:
            rel_path = Path(file_path).relative_to(BASE_DIR)
            return f"./{BASE_FOLDER_NAME}/{rel_path}"
        except ValueError:
            return str(file_path)


def extract_python_info(file_path):
    """Извлекает функции и классы с методами из Python файла."""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    functions = []
    classes = []

    func_pattern = re.compile(r'^def\s+(\w+)\s*\(', re.MULTILINE)

    class_pattern = re.compile(
        r'^class\s+(\w+)(?:\([^)]*\))?\s*:\s*(.*?)(?=^class\s|\Z)',
        re.MULTILINE | re.DOTALL
    )
    method_pattern = re.compile(r'^\s{4}def\s+(\w+)\s*\(', re.MULTILINE)

    for match in func_pattern.finditer(content):
        line_start = content.rfind('\n', 0, match.start()) + 1
        if content[line_start:match.start()].strip() == '':
            functions.append(match.group(1))

    for match in class_pattern.finditer(content):
        class_name = match.group(1)
        class_body = match.group(2)

        methods = []
        for method_match in method_pattern.finditer(class_body):
            methods.append(method_match.group(1))

        classes.append({
            'name': class_name,
            'methods': methods
        })

    return {'functions': functions, 'classes': classes}


def extract_gdscript_info(file_path):
    """Извлекает функции из GDScript файла."""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    functions = []
    func_pattern = re.compile(r'^func\s+(\w+)\s*\(', re.MULTILINE)

    for match in func_pattern.finditer(content):
        functions.append(match.group(1))

    return functions


def create_python_doc(file_path, info):
    """Создает .docp файл для Python."""
    doc_path = file_path.with_suffix('.docp')
    display_path = get_relative_path(file_path)

    lines = []
    lines.append(f"# Документация для: {file_path.name}\n")
    lines.append(f"Путь: {display_path}\n")
    lines.append("=" * 50 + "\n")

    if info['functions']:
        lines.append("\n## Функции:\n")
        for func in info['functions']:
            lines.append(f"  - {func}()\n")
    else:
        lines.append("\n## Функции: (нет)\n")

    if info['classes']:
        lines.append("\n## Классы:\n")
        for cls in info['classes']:
            lines.append(f"\n### Класс: {cls['name']}\n")
            if cls['methods']:
                lines.append("  Методы:\n")
                for method in cls['methods']:
                    lines.append(f"    - {method}()\n")
            else:
                lines.append("  Методы: (нет)\n")
    else:
        lines.append("\n## Классы: (нет)\n")

    with open(doc_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"  Создан: {get_relative_path(doc_path)}")


def create_gdscript_doc(file_path, functions):
    """Создает .docg файл для GDScript."""
    doc_path = file_path.with_suffix('.docg')
    display_path = get_relative_path(file_path)

    lines = []
    lines.append(f"# Документация для: {file_path.name}\n")
    lines.append(f"Путь: {display_path}\n")
    lines.append("=" * 50 + "\n")

    if functions:
        lines.append("\n## Функции:\n")
        for func in functions:
            lines.append(f"  - {func}()\n")
    else:
        lines.append("\n## Функции: (нет)\n")

    with open(doc_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"  Создан: {get_relative_path(doc_path)}")


def process_directory(start_path='.'):
    """Рекурсивно обрабатывает директорию."""
    start_path = Path(start_path).resolve()

    display_start = get_relative_path(start_path)
    print(f"Начинаю обработку с: {display_start}\n")
    print(f"Базовая директория: {BASE_DIR}\n")

    for root, dirs, files in os.walk(start_path):
        root_path = Path(root)

        for file in files:
            file_path = root_path / file

            if file.endswith('.py'):
                print(f"Обработка Python: {get_relative_path(file_path)}")
                try:
                    info = extract_python_info(file_path)
                    create_python_doc(file_path, info)
                except Exception as e:
                    print(f"  Ошибка: {e}")

            elif file.endswith('.gd'):
                print(f"Обработка GDScript: {get_relative_path(file_path)}")
                try:
                    functions = extract_gdscript_info(file_path)
                    create_gdscript_doc(file_path, functions)
                except Exception as e:
                    print(f"  Ошибка: {e}")


if __name__ == '__main__':
    process_directory('.')
    print("\nГотово!")