-- GeminusOS local achievements runtime (DraStic Lua)
-- Generado por ra_local_export.py. No envia nada a RetroAchievements.

local ACH = {
--__ACH__
}

local CHECK_EVERY = 6          -- ~10 Hz a 60 fps
local EVENT_FILE  = "/tmp/geminus_ach_events"
local STATE_FILE  = "/mnt/data/geminus_local_ach.tsv"

local frame = 0
local unlocked = {}
local warned_io = false

local function get_mem(size, addr)
    if size == 8  then return drastic.get_ds_memory_arm9_8(addr) end
    if size == 16 then return drastic.get_ds_memory_arm9_16(addr) end
    return drastic.get_ds_memory_arm9_32(addr)
end

local function bswap16(v)
    return ((v % 256) * 256) + math.floor(v / 256) % 256
end
local function bswap32(v)
    local b1 = v % 256; v = math.floor(v / 256)
    local b2 = v % 256; v = math.floor(v / 256)
    local b3 = v % 256; v = math.floor(v / 256)
    local b4 = v % 256
    return b1 * 16777216 + b2 * 65536 + b3 * 256 + b4
end
local function bswap24(v)
    local b1 = v % 256; v = math.floor(v / 256)
    local b2 = v % 256; v = math.floor(v / 256)
    local b3 = v % 256
    return b1 * 65536 + b2 * 256 + b3
end
local function popcount(v)
    local n = 0
    while v > 0 do n = n + (v % 2); v = math.floor(v / 2) end
    return n
end

local BIT = { M=0, N=1, O=2, P=3, Q=4, R=5, S=6, T=7 }

local function read_operand(txt)
    -- 16 bits: "0x 1234"; resto: "0xH1234"
    local sp_addr = txt:match("^0x (%x+)")
    if sp_addr then
        return get_mem(16, tonumber(sp_addr, 16))
    end
    local code, hex = txt:match("^0x([hHxXwWgGiIjJlLuUkKmMnNoOpPqQrRsStT])(%x+)")
    if code then
        local addr = tonumber(hex, 16)
        local v
        local c = code:upper()
        if c == "H" then v = get_mem(8, addr)
        elseif c == "X" or c == "G" then v = get_mem(32, addr); if c == "G" then v = bswap32(v) end
        elseif c == "W" or c == "J" then v = get_mem(24, addr) or get_mem(32, addr); if c == "J" then v = bswap24(v) end
        elseif c == "I" then v = bswap16(get_mem(16, addr))
        elseif c == "L" then v = get_mem(8, addr) % 16
        elseif c == "U" then v = math.floor(get_mem(8, addr) / 16) % 16
        elseif c == "K" then v = popcount(get_mem(8, addr))
        elseif BIT[c] ~= nil then v = math.floor(get_mem(8, addr) / (2 ^ BIT[c])) % 2
        else v = get_mem(8, addr) end
        return v
    end
    -- numero
    local neg = false
    if txt:sub(1,1) == "-" then neg = true; txt = txt:sub(2) end
    local v
    if txt:match("^0x") then v = tonumber(txt:sub(3), 16)
    elseif txt:match("^[hH]") then v = tonumber(txt:sub(2), 16)
    else v = tonumber(txt) end
    if v == nil then return nil end
    if neg then v = -v end
    return v
end

local function parse_condition(raw)
    local s = raw
    local reset = false
    -- flags al principio (R:, P:, A:, ...). Se pueden encadenar.
    while true do
        local flag, rest = s:match("^([A-Z]):(.*)$")
        if not flag then break end
        if flag == "R" then reset = true end
        if flag == "P" then return { pause = true } end
        s = rest
    end
    if s:match("^AddAddress") or s:match("^Remember") or
       s:match("^ResetIf") or s:match("^PauseIf") or
       s:match("^AndNext") or s:match("^OrNext") then
        return nil
    end

    local need = 1
    local hit = s:match("%((%d+)%)%s*$")
    if hit then need = tonumber(hit); s = s:gsub("%(%d+%)%s*$", "") end

    local lhs, op, rhs = s:match("^(.-)([<>=!]+)(.+)$")
    if not lhs then
        -- condicion "memoria != 0"
        lhs, op, rhs = s, "!=", "0"
    end
    local a = read_operand(lhs)
    local b = read_operand(rhs)
    if a == nil or b == nil then return nil end

    local kind = "eq"
    if op == "=" then kind = "eq"
    elseif op == "!=" then kind = "ne"
    elseif op == ">" then kind = "gt"
    elseif op == ">=" then kind = "ge"
    elseif op == "<" then kind = "lt"
    elseif op == "<=" then kind = "le"
    else return nil end

    -- Guardamos los textos para releer en cada frame (la RAM cambia).
    return { lhs = lhs, rhs = rhs, op = kind, need = need, hits = 0, reset = reset }
end

local function eval_condition(c)
    local a = read_operand(c.lhs)
    local b = read_operand(c.rhs)
    if a == nil or b == nil then return false end
    if c.op == "eq" then return a == b end
    if c.op == "ne" then return a ~= b end
    if c.op == "gt" then return a > b end
    if c.op == "ge" then return a >= b end
    if c.op == "lt" then return a < b end
    if c.op == "le" then return a <= b end
    return false
end

-- Parsear los grupos: $ = OR, _ = AND.
for _, a in ipairs(ACH) do
    a.groups = {}
    a.ok = false
    local ok = true
    for group in (a.mem .. "$"):gmatch("(.-)%$") do
        local g = { conds = {} }
        for cond in (group .. "_"):gmatch("(.-)_") do
            if cond ~= "" then
                local pc = parse_condition(cond)
                if pc == nil or pc.pause then ok = false; break end
                table.insert(g.conds, pc)
            end
        end
        if not ok then break end
        if #g.conds > 0 then table.insert(a.groups, g) end
    end
    a.supported = ok and #a.groups > 0
end

local nsup, ntotal = 0, #ACH
for _, a in ipairs(ACH) do
    if a.supported then nsup = nsup + 1
    else print(string.format("GEMINUS_ACH_SKIP|%s|%s", tostring(a.id), tostring(a.title))) end
end
print(string.format("GEMINUS_ACH_LOAD|%d|%d", nsup, ntotal))

local function write_event(a)
    local line = string.format("GEMINUS_ACH|%s|%s", tostring(a.id), tostring(a.title))
    print(line)
    if io then
        local ok, f = pcall(io.open, EVENT_FILE, "a")
        if ok and f then f:write(line .. "\n"); f:close() end
        local ok2, st = pcall(io.open, STATE_FILE, "a")
        if ok2 and st then
            local when = (os and os.date) and os.date("%Y-%m-%d %H:%M:%S") or ""
            st:write(string.format("%s\t%s\t%s\t%s\n", tostring(a.id), tostring(a.game), tostring(a.title), when))
            st:close()
        end
    elseif not warned_io then
        warned_io = true
        print("GEMINUS_ACH_WARN|sin io")
    end
end

function on_frame_update()
    frame = frame + 1
    if (frame % CHECK_EVERY) ~= 0 then return end

    for _, a in ipairs(ACH) do
        if a.supported and not unlocked[a.id] then
            local any = false
            for _, g in ipairs(a.groups) do
                local all = true
                for _, c in ipairs(g.conds) do
                    local v = eval_condition(c)
                    if c.reset and v then c.hits = 0 end
                    if v then c.hits = c.hits + 1 else c.hits = 0 end
                    if c.hits < c.need then all = false end
                end
                if all then any = true; break end
            end
            if any then
                unlocked[a.id] = true
                write_event(a)
            end
        end
    end
end
