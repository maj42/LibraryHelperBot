from datetime import datetime


def log_action(username, action):
    with open('bot.log', 'a', encoding='utf-8') as f:
        time = datetime.now().strftime("%d.%m.%Y %H:%M")
        f.write(f"[{time}] {username}: {action}\n")
