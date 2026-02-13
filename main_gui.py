#!/usr/bin/env python
"""
main_gui.py - Запуск HTTP сервера для Godot клиента
Godot сам выбирает игру через /new
"""

from gui.godot_bridge import start_server

if __name__ == "__main__":
    start_server(host='localhost', port=8080)