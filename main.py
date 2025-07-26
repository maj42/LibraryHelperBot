import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from log_helper import log_action
from drive_builder import build_drive_tree

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
        types.BotCommand("reload", "Обновить данные (только владелец)")
    ])


@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup()
    for instr in drive_tree.instruments:
        kb.add(InlineKeyboardButton(instr.name, callback_data=f"instrument:{instr.name}"))
    await message.answer(texts['welcome'], reply_markup=kb)


@dp.message_handler(commands=['reload'])
async def cmd_reload(message: types.Message):
    if message.from_user.id != int(settings["OWNER_ID"]):
        await message.answer(texts['not_allowed'])
        return
    global drive_tree
    drive_tree = build_drive_tree()
    await message.answer(texts['reload_done'])


@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    await message.answer(texts["help"])


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
    text = texts['files'].format(program=prog_name) + "\n"
    for file in program.files:
        text += f"📄 {file.name}\nВремя изменения: {file.modified_time})\n{file.link}\n\n"
    log_action(callback.from_user.username, f"Viewed program {prog_name} of {instr_name}")

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(texts["btn_check_again"], callback_data=f"program:{instr_name}:{prog_name}"),
        InlineKeyboardButton(texts["btn_other_program"], callback_data=f"instrument:{instr_name}")
    )
    kb.add(InlineKeyboardButton(texts["btn_home"], callback_data="home"))
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except:
        await callback.message.answer(text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == 'home')
async def go_home(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    for instr in drive_tree.instruments:
        kb.add(InlineKeyboardButton(instr.name, callback_data=f"instrument:{instr.name}"))
    try:
        await callback.message.edit_text(texts['welcome'], reply_markup=kb)
    except:
        await callback.message.answer(texts['welcome'], reply_markup=kb)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
