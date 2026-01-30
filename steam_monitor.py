import os
import re
import time
import sys
import winreg
from pathlib import Path

def get_steam_path():
    """Получаем путь к Steam из реестра Windows"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                           r"Software\Valve\Steam")
        steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
        winreg.CloseKey(key)
        return Path(steam_path)
    except Exception:
        # Если нет в реестре, пробуем стандартные пути
        default_paths = [
            Path("C:/Program Files (x86)/Steam"),
            Path(os.path.expanduser("~/.steam/steam")),
            Path(os.path.expanduser("~/.local/share/Steam"))
        ]
        for path in default_paths:
            if path.exists():
                return path
        raise FileNotFoundError("Не удалось найти папку Steam")

def parse_logs(log_file_path):
    """Парсим логи Steam и извлекаем информацию о загрузке"""
    if not log_file_path.exists():
        return None
    
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Читаем последние 100 строк (самые актуальные)
            lines = f.readlines()[-100:]
    except:
        return None
    
    current_game = None
    status = "Не активно"
    speed_mbps = 0.0
    progress = 0
    
    # Регулярные выражения для поиска в логах
    appid_pattern = r'AppID (\d+)'
    download_pattern = r'Downloading (\d+)%.*?(\d+\.\d+) (\w+)/sec'
    pause_pattern = r'paused|pause'
    complete_pattern = r'Downloaded|fully downloaded'
    game_name_pattern = r'\[(\d+)\]\s*(.+)'
    
    # Ищем информацию в обратном порядке (от новых записей к старым)
    for line in reversed(lines):
        # Ищем название игры
        if current_game is None:
            match = re.search(game_name_pattern, line)
            if match:
                appid = match.group(1)
                # Можно расширить через Steam API, но для простоты оставим так
                current_game = f"Игра (AppID: {appid})"
        
        # Ищем статус паузы
        if re.search(pause_pattern, line, re.IGNORECASE):
            status = "На паузе"
            speed_mbps = 0.0
        
        # Ищем завершение загрузки
        if re.search(complete_pattern, line, re.IGNORECASE):
            status = "Завершено"
            speed_mbps = 0.0
        
        # Ищем активную загрузку
        match = re.search(download_pattern, line)
        if match and status != "На паузе":
            progress = int(match.group(1))
            speed = float(match.group(2))
            unit = match.group(3).lower()
            
            # Конвертируем скорость в МБ/с
            if unit == 'kb':
                speed_mbps = speed / 1024
            elif unit == 'mb':
                speed_mbps = speed
            elif unit == 'gb':
                speed_mbps = speed * 1024
            else:
                speed_mbps = 0
            
            status = f"Загружается ({progress}%)"
            break
    
    return {
        'game': current_game or "Неизвестная игра",
        'status': status,
        'speed_mbps': round(speed_mbps, 2),
        'progress': progress
    }

def main():
    """Основная функция мониторинга"""
    print("=== Мониторинг загрузки Steam ===")
    print("Скрипт будет работать 5 минут, обновляя данные каждую минуту...")
    
    try:
        steam_path = get_steam_path()
        log_file = steam_path / "logs" / "content_log.txt"
        
        if not log_file.exists():
            print(f"Лог-файл не найден: {log_file}")
            print("Убедитесь, что Steam запущен и ведёт запись логов.")
            return
        
        print(f"Найден Steam в: {steam_path}")
        print("=" * 50)
        
        # Мониторим 5 минут
        for i in range(5):
            info = parse_logs(log_file)
            
            if info:
                print(f"[{time.strftime('%H:%M:%S')}] Минута {i+1}/5")
                print(f"Игра: {info['game']}")
                print(f"Статус: {info['status']}")
                print(f"Скорость: {info['speed_mbps']} МБ/с")
                
                # Проверяем, если загрузка завершена или не активна
                if "Завершено" in info['status']:
                    print("Загрузка завершена. Мониторинг остановлен.")
                    break
                elif info['game'] == "Неизвестная игра" and info['speed_mbps'] == 0:
                    print("Активных загрузок не обнаружено.")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Не удалось прочитать логи")
            
            print("=" * 50)
            
            # Ждём 1 минуту (60 секунд) перед следующим обновлением
            if i < 4:  # Не ждём после последней итерации
                time.sleep(60)
    
    except Exception as e:
        print(f"Ошибка: {e}")
        print("Убедитесь, что Steam установлен и у вас есть права на чтение файлов.")

def run_in_background():
    """Запуск в фоновом режиме (для Windows)"""
    if os.name == 'nt':  # Windows
        # Создаём батник для запуска в фоне
        script_path = os.path.abspath(__file__)
        bat_content = f'@echo off\npythonw "{script_path}"\n'
        
        bat_path = os.path.join(os.getenv('APPDATA'), 
                              'Microsoft', 'Windows', 
                              'Start Menu', 'Programs', 
                              'Startup', 'steam_monitor.bat')
        
        with open(bat_path, 'w') as f:
            f.write(bat_content)
        
        print(f"Скрипт добавлен в автозагрузку: {bat_path}")
        print("Перезагрузите компьютер для запуска в фоне.")
    else:
        print("Для Linux/Mac используйте nohup или systemd:")
        print("nohup python3 steam_monitor.py &")

if __name__ == "__main__":
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1 and sys.argv[1] == "--background":
        run_in_background()
    else:
        main()