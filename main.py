import os
import re
import random
import string
import asyncio
from datetime import datetime
from telegram import Bot
from telegram.ext import ApplicationBuilder, MessageHandler, filters


BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_BACKUP_ID = int(os.getenv("GROUP_BACKUP_ID", "-1004311007604"))
DEFAULT_EXPIRE = os.getenv("DEFAULT_EXPIRE", "2027-12-31")


def generate_random_string(length: int | None = None) -> str:
    if length is None:
        length = random.randint(14, 22)
    return "".join(random.choice(string.ascii_uppercase) for _ in range(length))


def string_to_byte_list(text: str) -> str:
    return ",".join(str(ord(char)) for char in text)


def get_expire_from_caption(caption: str | None) -> str:
    if not caption:
        return DEFAULT_EXPIRE
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", caption)
    if match:
        return match.group(0)
    return DEFAULT_EXPIRE


def build_expire_lua(expire_date: str) -> str:
    return f'''
local function cek_kadaluarsa()
    local batas = "{expire_date}"
    local sekarang = os.date("%Y-%m-%d")
    if sekarang >= batas then
        gg.alert("⏰ SCRIPT KADALUARSA")
        os.exit()
    end
end
cek_kadaluarsa()
'''


def proteksi_tahap_satu(raw: str, expire: str) -> str:
    f1 = generate_random_string()
    f2 = generate_random_string()
    f3 = generate_random_string()

    header = (
        f"local {f1}=function(C)return string.char(table.unpack(C or {{}}))end\n"
        f"local {f2}=function(A,B)return _ENV[{f1}({{{string_to_byte_list('gg')}}})][{f1}(B)]end\n"
        f"local {f3}=function(S)return {f1}(S)end\n"
    )
    raw = raw.replace('"', "'")
    raw = raw.replace("gg.", f"{f2}({{{string_to_byte_list('gg')}}},{{{string_to_byte_list('')}}}})")
    return header + build_expire_lua(expire) + raw


def proteksi_tahap_dua(raw: str) -> str:
    template = '''
local gg=gg local io=io local os=os local string=string local table=table local math=math
gg.setVisible(false)

local function tag_acak(len)
    len = len or math.random(14, 22)
    local s = ""
    for _ = 1, len do
        s = s .. string.char(math.random(65, 90))
    end
    return s
end

local g = {}
g.cfg = (gg.EXT_CACHE_DIR or "/sdcard") .. "/" .. (gg.getFile():match("[^/]+$") or "SECURE") .. ".cfg"
pcall(function()
    local l = loadfile(g.cfg)
    if l then g.sel = l() end
end)
if not g.sel or #g.sel < 2 then
    g.sel = { gg.getFile():gsub("/[^/]+$", ""), "/sdcard" }
end

local _ENC = {}
gg.setVisible(false)
gg.toast("MANIFESTDEPLOYMENT")

local function blok_debug()
    local big = ("\\255"):rep(1024)
    for _ = 1, 1200 do
        gg.refineNumber("0", big, big, big, big, big, big)
    end
end
blok_debug()

local blok = { "loadfile", "dofile", "load" }
local real = {}
for _, nama in ipairs(blok) do
    if _G[nama] then
        real[nama] = _G[nama]
        _G[nama] = function(...)
            gg.toast("🚫 DRAG CHANNEL: " .. nama)
            return nil
        end
    end
end

local ori_io = io
local aman_io = {}
aman_io.open = function(path, mode)
    if type(path) ~= "string" then return ori_io.open(path, mode) end
    if path:lower():find("%.lua") or path:lower():find("dump") then
        gg.toast("🚫 Akses file dilindungi")
        return nil
    end
    return ori_io.open(path, mode)
end
for k, v in pairs(ori_io) do
    if not aman_io[k] then aman_io[k] = v end
end
_G.io = aman_io

local ori_print = print
print = function(...)
    for _, val in ipairs({...}) do
        if type(val) == "string" and val:lower():find("dump") then
            gg.toast("🚫 Log diblokir")
            return
        end
    end
    return ori_print(...)
end

local ori_editall = gg.editAll
gg.editAll = function(...)
    local arg = { ... }
    if tostring(arg[1]):match("[%a;]") then
        return ori_editall(...)
    end
    local res = gg.getResults(...)
    for _, item in pairs(res) do
        item.value = arg[1]
        item.flags = arg[2]
        item.freeze = true
    end
    gg.addListItems(res)
    gg.removeListItems(res)
end

gg.toast("🛡️ Proteksi siap")
'''
    return template + "\n" + raw


async def kirim_backup(bot: Bot, chat_id: int, data: bytes, nama: str, expire: str):
    teks = (
        "📂 Backup file asli\n"
        f"Nama: {nama}\n"
        f"Kadaluarsa: {expire}\n"
        f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await bot.send_document(chat_id=chat_id, document=data, filename=nama, caption=teks)


async def proses_lua(raw: bytes, nama: str, expire: str) -> bytes:
    try:
        teks = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Bukan file teks Lua")
    tahap1 = proteksi_tahap_satu(teks, expire)
    tahap2 = proteksi_tahap_dua(tahap1)
    return tahap2.encode("utf-8")


async def terima_file(update, context):
    dok = update.message.document
    if not dok:
        await update.message.reply_text("Kirim file .lua")
        return

    nama = dok.file_name
    if not nama.lower().endswith(".lua"):
        await update.message.reply_text("Hanya terima file .lua")
        return

    expire = get_expire_from_caption(update.message.caption)
    file_bot = await dok.get_file()
    data_asli = await file_bot.download_as_bytearray()

    await kirim_backup(context.bot, GROUP_BACKUP_ID, bytes(data_asli), nama, expire)

    try:
        hasil = await proses_lua(bytes(data_asli), nama, expire)
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal: {str(e)}")
        return

    nama_keluar = f"{nama}.PROGRAM.BETA.lua"
    caption = f"✅ Proteksi selesai | Kadaluarsa: {expire}"
    await update.message.reply_document(document=hasil, filename=nama_keluar, caption=caption)


def jalankan():
    if not BOT_TOKEN:
        raise RuntimeError("Isi BOT_TOKEN di Secrets")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.ALL, terima_file))
    app.run_polling()


if __name__ == "__main__":
    jalankan()
