-- GEMINUSOS_ACH_DEFAULT - lector de RAM generico para NNDDSS.
-- Generado por GeminusOS. No envia nada a RetroAchievements.
--
-- NNDDSS carga este script cuando no hay un <rom>.lua propio (o como
-- respaldo). Lee las direcciones firmadas por geminus-achd desde
-- /mnt/data/geminus_ach/<rom>.addrs y escribe el mismo snapshot que usa
-- el script de DraStic: /tmp/geminus_ach_snap.txt.

local DATA_DIR = "/mnt/data/geminus_ach"
local SNAP = "/tmp/geminus_ach_snap.txt"
local EVERY = 6
local frame = 0
local addrs = nil
local tried = false

local function strip_ext(name)
    return (name:gsub("%.[^%.]+$", ""))
end

local function rom_base()
    local rom = os and os.getenv and os.getenv("GEMINUS_NDS_ROM")
    if rom and rom ~= "" then return strip_ext(rom:match("[^/]+$") or rom) end

    local f = io and io.open("/proc/self/cmdline", "rb")
    if not f then return nil end
    local data = f:read("*a") or ""
    f:close()

    local prev = nil
    for part in data:gmatch("[^%c]+") do
        if prev == "--rom" then
            return strip_ext(part:match("[^/]+$") or part)
        end
        prev = part
    end
    return nil
end

local function load_addrs(base)
    local f = io and io.open(DATA_DIR .. "/" .. base .. ".addrs", "r")
    if not f then return nil end
    local list = {}
    for line in f:lines() do
        local ra = line:match("^(%d+)")
        if ra then
            ra = tonumber(ra)
            local real = ra
            if real < 0x02000000 then real = real + 0x02000000 end
            list[#list + 1] = real
        end
    end
    f:close()
    if #list == 0 then return nil end
    return list
end

local function write_snapshot()
    if not io or not drastic or not drastic.get_ds_memory_arm9_32 then return end
    local t = {}
    for i = 1, #addrs do
        t[i] = tostring(drastic.get_ds_memory_arm9_32(addrs[i]))
    end
    local f = io.open(SNAP, "w")
    if not f then return end
    f:write(table.concat(t, "\n"))
    f:write("\n")
    f:close()
end

function on_frame_update()
    frame = frame + 1
    if (frame % EVERY) ~= 0 then return end

    if not tried then
        tried = true
        local base = rom_base()
        if base then addrs = load_addrs(base) end
        if not addrs then
            print("GEMINUS_ACH_DEFAULT|sin datos para " .. tostring(base))
        end
    end
    if addrs then write_snapshot() end
end
