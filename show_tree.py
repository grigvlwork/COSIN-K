import os


def generate_tree(directory, prefix="", output_lines=None):
    if output_lines is None:
        output_lines = []

    # Получаем список всего в папке
    try:
        entries = sorted(os.listdir(directory))
    except PermissionError:
        return output_lines

    # Фильтруем мусор (скрытые файлы, git, godot импорты)
    ignore_list = ['.git', '.godot', '.import', '__pycache__']
    entries = [e for e in entries if not e.startswith('.') and e not in ignore_list]

    for index, entry in enumerate(entries):
        path = os.path.join(directory, entry)
        connector = "└── " if index == len(entries) - 1 else "├── "

        output_lines.append(f"{prefix}{connector}{entry}")

        if os.path.isdir(path):
            extension = "    " if index == len(entries) - 1 else "│   "
            generate_tree(path, prefix + extension, output_lines)

    return output_lines


# Укажи здесь имя папки своего проекта, если скрипт лежит не в корне
project_dir = "."
tree_lines = [os.path.basename(os.path.abspath(project_dir)) + "/"]
generate_tree(project_dir, "", tree_lines)

print("\n".join(tree_lines))