import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from log_helper import log_action
from drive_builder import build_drive_tree
from datetime import datetime, timedelta
from html import escape

with open('telegram_settings.json', encoding='utf-8') as f:
    settings = json.load(f)
with open('config.json', encoding='utf-8') as f:
    config = json.load(f)
with open('texts.json', encoding='utf-8') as f:
    texts = json.load(f)

bot = Bot(token=settings['API_TOKEN'])
dp = Dispatcher(bot)

# Load tree at startup
drive_tree = build_drive_tree()


async def on_startup(dp):
    await bot.set_my_commands([
        types.BotCommand("start", "Начать"),
        types.BotCommand("help", "Помощь"),
        types.BotCommand("recent", "Последние изменения на диске"),
        types.BotCommand("reload", "Обновить данные (только владелец)")
    ])


@dp.message_handler(commands=['start'], chat_type=['private'])
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup()
    for instr in drive_tree.instruments:
        kb.add(InlineKeyboardButton(instr.name, callback_data=f"instrument:{instr.name}"))
    await message.answer(texts['welcome'], reply_markup=kb)


@dp.message_handler(commands=['reload'], chat_type=['private'])
async def cmd_reload(message: types.Message):
    if message.from_user.id != int(settings["OWNER_ID"]):
        await message.answer(texts['not_allowed'])
        return
    global drive_tree
    drive_tree = build_drive_tree()
    await message.answer(texts['reload_done'])


@dp.message_handler(commands=['help'], chat_type=['private', 'group', 'supergroup'])
async def cmd_help(message: types.Message):
    if message.chat.type in ['group', 'supergroup']:
        await message.answer(texts["help_group"])
    else:
        await message.answer(texts["help"])


# Raw text in handler!!
@dp.message_handler(commands=['recent'], chat_type=['private', 'group', 'supergroup'])
async def cmd_recent(message: types.Message):
    recent_days = config["lookup_interval"]  # how many days back to look
    now = datetime.now()

    recent_files = []
    changed_programs = set()
    last_change_time = None

    for instr in drive_tree.instruments:
        for prog in instr.programs:
            for file in prog.files:
                try:
                    file_dt = datetime.strptime(file.modified_time, "%d.%m.%Y %H:%M")
                    if now - file_dt <= timedelta(days=recent_days):
                        recent_files.append(file)
                        changed_programs.add(prog.name)  # just program name
                        # remember latest modification time
                        if last_change_time is None or file_dt > last_change_time:
                            last_change_time = file_dt
                except Exception as e:
                    print(f"Failed to parse date for file {file.name}: {e}")

    if recent_files:
        last_change_str = last_change_time.strftime("%d.%m.%Y %H:%M") if last_change_time else "?"
        text = (
            f"🆕 Изменения за последние дни({recent_days}):\n\n"
            f"📅 Последнее изменение: <b>{last_change_str}</b>\n"
            f"📦 Количество изменённых файлов: <b>{len(recent_files)}</b>\n\n"
            f"📁 Программы с изменениями:\n"
        )
        text += "\n".join(f"- {prog}" for prog in sorted(changed_programs))
    else:
        text = "Нет изменений за последние дни."

    try:
        await message.reply(text, parse_mode='HTML')
    except:
        await message.answer(text, parse_mode='HTML')


@dp.callback_query_handler(lambda c: c.data.startswith('find_file:'))
async def find_file_in_instrument(callback: types.CallbackQuery):
    instr_name = callback.data.split(':', 1)[1]
    dp.current_search_instr = instr_name
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(texts["btn_cancel"], callback_data=f"instrument:{instr_name}"))
    try:
        await callback.message.edit_text(texts['enter_search_query'], reply_markup=kb)
    except:
        await callback.message.answer(texts['enter_search_query'], reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith('recent_files:'))
async def show_recent_files(callback: types.CallbackQuery):
    instr_name = callback.data.split(':', 1)[1]
    instrument = next((i for i in drive_tree.instruments if i.name == instr_name), None)
    if not instrument:
        try:
            await callback.message.edit_text(texts['no_programs'])
        except:
            await callback.message.answer(texts['no_programs'])
        return

    recent_days = config["lookup_interval"]
    now = datetime.now()
    recent_files = []

    for prog in instrument.programs:
        for file in prog.files:
            try:
                file_dt = datetime.strptime(file.modified_time, "%d.%m.%Y %H:%M")
                if now - file_dt <= timedelta(days=recent_days):
                    recent_files.append((prog.name, file))
            except Exception as e:
                print(f"Failed to parse date for file {file.name}: {e}")

    kb = InlineKeyboardMarkup()
    for prog in instrument.programs:
        kb.add(InlineKeyboardButton(prog.name, callback_data=f"program:{instr_name}:{prog.name}"))
    kb.add(
        InlineKeyboardButton(texts["btn_find"], callback_data=f"find_file:{instr_name}"),
        InlineKeyboardButton(texts["btn_recent"], callback_data=f"recent_files:{instr_name}")
    )
    kb.add(InlineKeyboardButton(texts["btn_home"], callback_data="home"))

    if recent_files:
        header = f"🆕 Недавно изменённые файлы (Дней: {recent_days}):\n\n"
        blocks = [
            f"📄 <a href=\"{escape(file.link)}\">{escape(file.name)}</a>\n"
            f"Программа: {escape(prog_name)}\n"
            f"Изм.: {escape(file.modified_time)}\n\n"
            for prog_name, file in recent_files
        ]

        parts = split_long_message(header, blocks)

        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                try:
                    await callback.message.edit_text(part, reply_markup=kb, parse_mode='HTML')
                except:
                    await callback.message.answer(part, reply_markup=kb, parse_mode='HTML')
            else:
                await callback.message.answer(part, parse_mode='HTML')
    else:
        text = "Нет недавно изменённых файлов."
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except:
            await callback.message.answer(text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith('instrument:'))
async def choose_program(callback: types.CallbackQuery):
    instr_name = callback.data.split(':', 1)[1]
    instrument = next((i for i in drive_tree.instruments if i.name == instr_name), None)
    if not instrument:
        try:
            await callback.message.edit_text(texts['no_programs'])
        except:
            await callback.message.answer(texts['no_programs'])
        return
    kb = InlineKeyboardMarkup()
    for prog in instrument.programs:
        kb.add(InlineKeyboardButton(prog.name, callback_data=f"program:{instr_name}:{prog.name}"))
    kb.add(InlineKeyboardButton(texts["btn_find"], callback_data=f"find_file:{instr_name}"))
    kb.add(InlineKeyboardButton(texts["btn_recent"], callback_data=f"recent_files:{instr_name}"))
    kb.add(InlineKeyboardButton(texts["btn_home"], callback_data="home"))
    try:
        await callback.message.edit_text(texts['choose_program'].format(instrument=instr_name), reply_markup=kb)
    except:
        await callback.message.answer(texts['choose_program'].format(instrument=instr_name), reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith('program:'))
async def choose_file(callback: types.CallbackQuery):
    _, instr_name, prog_name = callback.data.split(':', 2)
    instrument = next((i for i in drive_tree.instruments if i.name == instr_name), None)
    program = next((p for p in instrument.programs if p.name == prog_name), None)

    if not program or not program.files:
        try:
            await callback.message.edit_text(texts['no_files'])
        except:
            await callback.message.answer(texts['no_files'])
        return

    text = texts['files'].format(program=escape(prog_name)) + "\n"
    for file in program.files:
        text += (
            f"📄 <a href=\"{escape(file.link)}\">{escape(file.name)}</a>\n"
            f"(Изм.: {escape(file.modified_time)})\n"
        )

    log_action(callback.from_user.username, f"Viewed program {prog_name} of {instr_name}")

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(texts["btn_check_again"], callback_data=f"program:{instr_name}:{prog_name}"),
        InlineKeyboardButton(texts["btn_other_program"], callback_data=f"instrument:{instr_name}")
    )
    kb.add(InlineKeyboardButton(texts["btn_home"], callback_data="home"))
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except:
        await callback.message.answer(text, reply_markup=kb, parse_mode='HTML')


@dp.message_handler(lambda message: True, chat_type=['private'])
async def handle_search_query(message: types.Message):
    query = message.text.lower()
    results = []

    instr_name = getattr(dp, 'current_search_instr', None)

    if instr_name:
        instrument = next((i for i in drive_tree.instruments if i.name == instr_name), None)
        if instrument:
            for prog in instrument.programs:
                for file in prog.files:
                    if query in file.name.lower():
                        results.append(
                            f"📄 <a href=\"{escape(file.link)}\">{escape(file.name)}</a> "
                            f"(Изм.: {escape(file.modified_time)})\n"
                        )
    else:
        for instr in drive_tree.instruments:
            for prog in instr.programs:
                for file in prog.files:
                    if query in file.name.lower():
                        results.append(
                            f"[{escape(instr.name)}] 📄 <a href=\"{escape(file.link)}\">{escape(file.name)}</a> "
                            f"(Изм.: {escape(file.modified_time)})\n"
                        )

    kb = InlineKeyboardMarkup()
    if instr_name:
        kb.add(
            InlineKeyboardButton(texts["btn_search_again"], callback_data=f"find_file:{instr_name}"),
            InlineKeyboardButton(texts["btn_back_instr"], callback_data=f"instrument:{instr_name}")
        )
    else:
        kb.add(
            InlineKeyboardButton(texts["btn_search_again"], callback_data="find_file:all"),
            InlineKeyboardButton(texts["btn_home"], callback_data="home")
        )

    if results:
        header = texts['search_results'] + "\n\n"
        parts = split_long_message(header, results)
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                try:
                    await message.reply(part, reply_markup=kb, parse_mode='HTML')
                except:
                    await message.answer(part, reply_markup=kb, parse_mode='HTML')
            else:
                await message.answer(part, parse_mode='HTML')
    else:
        await message.answer(texts['no_results'], reply_markup=kb)

    # reset search instrument
    if hasattr(dp, 'current_search_instr'):
        del dp.current_search_instr


@dp.callback_query_handler(lambda c: c.data == 'home')
async def go_home(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    for instr in drive_tree.instruments:
        kb.add(InlineKeyboardButton(instr.name, callback_data=f"instrument:{instr.name}"))
    try:
        await callback.message.edit_text(texts['welcome'], reply_markup=kb)
    except:
        await callback.message.answer(texts['welcome'], reply_markup=kb)


def split_long_message(header, blocks, max_length=4000):
    """
    Split a list of text blocks into message parts under max_length.
    header: text to start first message with
    blocks: list of strings (e.g. file descriptions)
    Returns list of message parts.
    """
    parts = []
    current = header

    for block in blocks:
        if len(current) + len(block) < max_length:
            current += block
        else:
            parts.append(current)
            current = block
    if current:
        parts.append(current)

    return parts


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
