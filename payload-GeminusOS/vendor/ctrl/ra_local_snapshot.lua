-- Snapshot de RAM para el daemon geminus-achd (DraStic).
-- Generado por ra_local_export.py.
local ADDRS = {
--__ADDRS__
}

local SNAP = "/tmp/geminus_ach_snap.txt"
local EVERY = 6
local frame = 0

function on_frame_update()
    frame = frame + 1
    if (frame % EVERY) ~= 0 then return end
    if not io then return end

    local t = {}
    for i = 1, #ADDRS do
        t[i] = tostring(drastic.get_ds_memory_arm9_32(ADDRS[i].r))
    end

    local f = io.open(SNAP, "w")
    if not f then return end
    f:write(table.concat(t, "\n"))
    f:write("\n")
    f:close()
end
