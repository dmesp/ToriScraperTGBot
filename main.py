#!/usr/bin/python
import re
import sys
import asyncio
import logging
import requests
import contextvars
from bs4 import BeautifulSoup
from config import TOKEN, URL    #type: ignore

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.handlers import CallbackQueryHandler
from aiogram.types import Message, FSInputFile, ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.utils.markdown import hbold

phone_link_var = contextvars.ContextVar('phone_link')
phone_link_var.set("1")

bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


async def send_error(error):
    await bot.send_message(chat_id="5239151807", text=f"""{hbold("An error has occured:")}\n{error}""")

async def make_request(url):
    try:
        page = BeautifulSoup(requests.get(url).content, 'html.parser')     
        return page
    except Exception as e:
        await send_error(e)
    
async def phone_suitability_check():
    page = await make_request(URL)
    page_main_div = page.find("div", class_="list_mode_thumb")
    phone_divs = page_main_div.find_all("a")
    number = 0
    while True:
        paid_first_place = phone_divs[number].find("div", class_="polepos_marker")
        if paid_first_place == None:
            phone_div = phone_divs[number]
            phone_other_data = phone_div.find("div", class_="cat_geo")
            replaced = phone_other_data.get_text().replace("\t", "").strip()
            phone_other_array = replaced.split("\n")
            phone_other_array.append("")
            phone_company = phone_other_array[1]
            phone_deal_type = phone_other_array[0]

            #checking that this is not a commercial 
            if phone_company == "" and phone_deal_type != "Ostetaan" and phone_other_data .find("span", class_="list_store_logo") == None:
                return phone_div
            else:
                number += 1
        else:
            number += 1 

                
async def get_phone_basic_data(): 
    phone_div = await phone_suitability_check()

    class Phone:
        def __init__(self, phone_name, phone_price, phone_link):
            self.name = phone_name or "not aviable"
            self.price = phone_price or "not aviable"
            self.link = phone_link or "not aviable"

        def __str__(self):
            return f"{self.name}, {self.price}, {self.link}"
        
    return Phone(phone_div.find("div", class_="li-title").get_text(), phone_div.find("p", class_="list_price").get_text(), phone_div.get('href'))
        
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    if message.from_user.id != 5239151807:
        await message.answer("Not available") 
    else:
        while True:
            try:
                phone = await get_phone_basic_data()
                if phone_link_var.get() == phone.link:
                    print(phone.name)
                else:
                    phone_link_var.set(phone.link)        
                    additional_data_page  = await make_request(phone.link) 
                    battery = await get_phone_battery(additional_data_page)
                    msg = f"""{hbold(phone.name)}\n{hbold(phone.price)}\n{hbold(f"{battery}")}"""

                    number_of_photos = await get_phone_photos(additional_data_page)  

                    show_description = InlineKeyboardButton(text="📜 Description 📜", callback_data="show_description")           
                    link_button = InlineKeyboardButton(text="📎 Link 📎", url=phone.link)
                    search_first_step = InlineKeyboardMarkup(inline_keyboard = [[show_description], [link_button]])
         

                    array = []
                    for i in range(number_of_photos):
                        phone_photo = FSInputFile(f"images/preview{i}.jpg") 
                        array.append(InputMediaPhoto(media=phone_photo))
                    await message.answer_media_group(media=array)
                    await message.answer(text=msg, reply_markup=search_first_step)

            except Exception as e:
                print(e)

            await asyncio.sleep(10)

@dp.callback_query(lambda c: c.data == "show_description")
async def show_handle(callback_query: types.CallbackQuery):
    cq = callback_query
    phone_url = cq.message.reply_markup.inline_keyboard[1][0].url
    description = await get_phone_desc(phone_url)
    list = cq.message.text.splitlines()
    list.append(f"Description:\n{description}")

    if len(list) == 3: #battery info not exists
        msg_text = f"""{hbold(list[0])}\n{hbold(list[1])}\n\n{(list[2])}"""
    elif len(list) == 4: #battery info exists
        msg_text = f"""{hbold(list[0])}\n{hbold(list[1])}\n{hbold(list[2])}\n\n{(list[3])}"""

    show_description = InlineKeyboardButton(text="📜 Hide description 📜", callback_data="hide_description")           
    link_button = InlineKeyboardButton(text="📎 Link 📎", url=phone_url)
    search_first_step = InlineKeyboardMarkup(inline_keyboard = [[show_description], [link_button]])
    await cq.message.edit_text(text=msg_text[:1024], reply_markup=search_first_step)

@dp.callback_query(lambda c: c.data == "hide_description")
async def show_handle(callback_query: types.CallbackQuery):
    cq = callback_query
    phone_url = cq.message.reply_markup.inline_keyboard[1][0].url
    list = cq.message.text.split("Description:")
    msg_text = f"""{hbold(list[0])}"""
    show_description = InlineKeyboardButton(text="📜 Description 📜", callback_data="show_description")            
    link_button = InlineKeyboardButton(text="📎 Link 📎", url=phone_url)
    sec = InlineKeyboardMarkup(inline_keyboard = [[show_description], [link_button]])

    try:
        await cq.message.edit_caption(caption=msg_text, reply_markup=sec)
    except:
        await cq.message.edit_text(text=msg_text, reply_markup=sec)

async def get_phone_desc(url):
    mainPageResponse = requests.get(url) 
    if mainPageResponse.ok == True:
        page = BeautifulSoup(mainPageResponse.content, 'html.parser') 
        try:
            main_div = page.find("div", class_="body")
            main_div.find('div', class_="group-title").decompose()
            desc_text = main_div.get_text()
            stripped = desc_text.strip()
            return stripped
        except AttributeError:
            return "Description is not aviable."
        except Exception as error:
            return str(error)

async def get_phone_photos(page):
    try:
        array = []
        main_div = page.find("div", class_="content_area")
        image_div = main_div.find_all("span", class_="thumb_link")

        if image_div != None:        
            for i in range(len(image_div)):
                pic = image_div[i].get('href')
                array.append(pic) 

            for i in range(len(array)):
                with open(f"images/preview{i}.jpg", "wb") as f:
                    f.write(requests.get(array[i]).content)
            return len(array)
                            
    except Exception as e:
        pass


async def get_phone_battery(page):
        try:
            main_div = page.find("div", class_="body")
            main_div_text =  main_div.get_text()
            battery_percentage = re.search("\d+(?=%)", main_div_text) 

            if battery_percentage:
                return battery_percentage.group() + "%"
            else:
                return ""
            
        except Exception as e:
            print(e)
            return ""
 
async def main() -> None:
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())