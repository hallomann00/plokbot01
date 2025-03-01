from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, CallbackContext
import json
import schedule
import time
import os
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import requests
from datetime import datetime, timedelta

# Настройки Telegram
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
bot = Bot(token=TELEGRAM_TOKEN)

# Создание Flask-приложения
app = Flask(__name__)

# Загрузка данных из файла
def load_data():
    try:
        with open("ads.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return []

# Сохранение данных в файл
def save_data(data):
    with open("ads.json", "w") as file:
        json.dump(data, file, indent=4)

# Получение цены игры из Steam
def get_steam_price(app_id):
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=RU"
    try:
        response = requests.get(url)
        data = response.json()
        if data[str(app_id)].get("success"):
            price_overview = data[str(app_id)]["data"].get("price_overview")
            if price_overview:
                return price_overview["final"] / 100  # Преобразуем из копеек в рубли
    except Exception as e:
        print(f"Ошибка при получении цены: {e}")
    return None

# Создание объявления на Playerok через Selenium
def post_ad(game_name, category, title, price, description, item_data):
    options = Options()
    options.headless = True  # Безголовый режим Firefox
    driver = webdriver.Firefox(options=options)
    driver.get("https://playerok.com")

    # Логин на сайте
    login_field = driver.find_element(By.ID, "login")
    login_field.send_keys("your_email")  # Замените на ваш email
    password_field = driver.find_element(By.ID, "password")
    password_field.send_keys("your_password")  # Замените на ваш пароль
    password_field.send_keys(Keys.RETURN)
    time.sleep(5)

    # Создание объявления
    create_ad_button = driver.find_element(By.LINK_TEXT, "Добавить объявление")
    create_ad_button.click()
    time.sleep(2)

    game_input = driver.find_element(By.ID, "game_name")
    game_input.send_keys(game_name)
    category_select = driver.find_element(By.ID, "category")
    category_select.send_keys(category)
    title_input = driver.find_element(By.ID, "title")
    title_input.send_keys(title)
    price_input = driver.find_element(By.ID, "price")
    price_input.send_keys(str(price))
    description_input = driver.find_element(By.ID, "description")
    description_input.send_keys(description)
    item_data_input = driver.find_element(By.ID, "item_data")
    item_data_input.send_keys(item_data)

    submit_button = driver.find_element(By.ID, "submit")
    submit_button.click()
    time.sleep(5)

    driver.quit()

# Проверка и публикация объявлений
def check_and_post_ads():
    ads = load_data()
    current_date = datetime.now().date()
    for ad in ads:
        last_posted = ad["last_posted"]
        interval = ad["post_interval"]
        if not last_posted or (current_date - datetime.strptime(last_posted, "%Y-%m-%d").date()).days >= interval:
            # Обновление цены на основе Steam
            app_id = "APP_ID_FOR_GAME"  # Замените на актуальный app_id
            steam_price = get_steam_price(app_id)
            if steam_price:
                ad["price"] = int(steam_price * 1.2)  # Наценка 20%
            post_ad(
                ad["game_name"],
                ad["category"],
                ad["title"],
                ad["price"],
                ad["description"],
                ad["item_data"]
            )
            ad["last_posted"] = current_date.strftime("%Y-%m-%d")
            save_data(ads)

# Команда для добавления нового объявления
def add_ad(update: Update, context: CallbackContext):
    ads = load_data()
    new_ad = {
        "id": len(ads) + 1,
        "game_name": update.message.text.split()[1],
        "category": "Steam ключи",
        "title": "Новое объявление",
        "price": 1000,
        "description": "Описание по умолчанию",
        "item_data": "KEY1234",
        "discount": 0,
        "last_posted": "",
        "post_interval": 5
    }
    ads.append(new_ad)
    save_data(ads)
    update.message.reply_text("Объявление успешно добавлено!")

# Команда для просмотра всех объявлений
def list_ads(update: Update, context: CallbackContext):
    ads = load_data()
    if not ads:
        update.message.reply_text("Список объявлений пуст.")
        return
    message = "\n".join([f"{ad['id']}. {ad['title']} - {ad['price']} руб." for ad in ads])
    update.message.reply_text(message)

# Команда для удаления объявления
def delete_ad(update: Update, context: CallbackContext):
    ads = load_data()
    ad_id = int(update.message.text.split()[1])
    ads = [ad for ad in ads if ad["id"] != ad_id]
    save_data(ads)
    update.message.reply_text(f"Объявление с ID {ad_id} удалено.")

# Команда для обновления цены
def update_price(update: Update, context: CallbackContext):
    ads = load_data()
    ad_id = int(update.message.text.split()[1])
    new_price = int(update.message.text.split()[2])
    for ad in ads:
        if ad["id"] == ad_id:
            ad["price"] = new_price
            break
    save_data(ads)
    update.message.reply_text(f"Цена обновлена для объявления с ID {ad_id}.")

# Настройка вебхуков
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK"

# Запуск планировщика
def start_scheduler():
    schedule.every().day.at("10:00").do(check_and_post_ads)
    while True:
        schedule.run_pending()
        time.sleep(1)

# Главная функция
if __name__ == "__main__":
    dispatcher = Dispatcher(bot, None, workers=0)
    dispatcher.add_handler(CommandHandler("add", add_ad))
    dispatcher.add_handler(CommandHandler("list", list_ads))
    dispatcher.add_handler(CommandHandler("delete", delete_ad))
    dispatcher.add_handler(CommandHandler("update_price", update_price))

    # Запуск планировщика в фоновом режиме
    import threading
    scheduler_thread = threading.Thread(target=start_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()

    # Установка вебхука
    WEBHOOK_URL = "https://your-username.pythonanywhere.com/webhook"  # Замените на ваш URL
    bot.set_webhook(url=WEBHOOK_URL)

    # Запуск Flask-приложения
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))