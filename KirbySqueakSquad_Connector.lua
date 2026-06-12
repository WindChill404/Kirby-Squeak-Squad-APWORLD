-- KirbySqueakSquad_Connector.lua  (v7 - deferred granting: full collection, low mask)
--
--   THE RULE THAT AVOIDS MASKING: a chest goes gray only if its collectible bit
--   is set BEFORE you open it. So we set each received collectible's bit only at
--   a moment that can't gray its own chest:
--     * received item whose chest you have ALREADY opened -> set bit now (safe).
--     * received item whose chest you have NOT opened yet -> hold; when you open
--       that chest, we KEEP its bit instead of clearing it (collection fills,
--       chest was never gray because the bit wasn't set when you walked in).
--     * key/seal -> MUST set immediately (the game gates EX / Secret Sea on the
--       collectible bit itself - confirmed by capture), so only those 12 chests
--       can still mask, and only if received before opened.
--   Net: sprays, scrolls, music, everything fills your in-game collection, with
--   masking limited to the 12 key/seal chests.
--
--   DETECTION: collectibles 0x02256020; new bit + gate change = check. If you did
--     NOT receive that collectible, clear it (contents match AP); if you DID, keep.
--   ABILITY LOCK: 0x0226188C, reset to 0 after ABILITY_DELAY if scroll not received.
--   STAGE CLEARS: 0x022560D8 + 2*world.   goal = bit 119.

local POLL = 8
local RAM = 0x02000000
local COLL = 0x02256020
local GATE_LO, GATE_HI = 0x02256031, 0x022560DC
local NUM_BITS, GOAL_BIT = 120, 119
local SC_BASE, SC_WORLDS, SC_VBASE = 0x022560D8, 8, 200
local ABILITY_ADDR, ABILITY_DELAY = 0x0226188C, 60

local TEMP = os.getenv("TEMP") or "C:\\Temp"
local CHECKS_FILE = TEMP .. "\\kss_checks.txt"
local ITEMS_FILE  = TEMP .. "\\kss_items.txt"
local GOAL_FILE   = TEMP .. "\\kss_goal.txt"

local NAME_TO_BIT = {
    ["Star seal 1"] = 0,
    ["Star seal 2"] = 1,
    ["Star seal 3"] = 2,
    ["Star seal 4"] = 3,
    ["Star seal 5"] = 4,
    ["Sound player"] = 5,
    ["Vitality half_1"] = 6,
    ["Vitality half_2"] = 7,
    ["Orange"] = 8,
    ["Vitality half_4"] = 9,
    ["Vitality half_5"] = 10,
    ["Vitality half_6"] = 11,
    ["Vitality half_7"] = 12,
    ["Vitality half_8"] = 13,
    ["Prism Plains key"] = 14,
    ["Nature Notch key"] = 15,
    ["Cushy Cloud key"] = 16,
    ["Jam Jungle key"] = 17,
    ["Vocal Volcano key"] = 18,
    ["Ice Island key"] = 19,
    ["Secret Sea key"] = 20,
    ["Ghost medal_1"] = 21,
    ["Ghost medal_2"] = 22,
    ["Ghost medal_3"] = 23,
    ["Ghost medal_4"] = 24,
    ["Ghost medal_5"] = 25,
    ["Ghost medal_6"] = 26,
    ["Ghost medal_7"] = 27,
    ["Fire scroll"] = 28,
    ["Ice scroll"] = 29,
    ["Spark scroll"] = 30,
    ["Beam scroll"] = 31,
    ["Tornado scroll"] = 32,
    ["Enemy Sounds"] = 33,
    ["Hammer scroll"] = 34,
    ["Cupid scroll"] = 35,
    ["Cutter scroll"] = 36,
    ["Laser scroll"] = 37,
    ["Bomb scroll"] = 38,
    ["Wheel scroll"] = 39,
    ["HiJump scroll"] = 40,
    ["UFO scroll"] = 41,
    ["Copy palette 4"] = 42,
    ["Sword scroll"] = 43,
    ["Ninja scroll"] = 44,
    ["Fighter scroll"] = 45,
    ["Throw scroll"] = 46,
    ["Magic scroll"] = 47,
    ["Animal scroll"] = 48,
    ["Bubble scroll"] = 49,
    ["Metal scroll"] = 50,
    ["Party Notes"] = 51,
    ["Beginning Notes"] = 52,
    ["Happy Notes"] = 53,
    ["Graphic piece_17"] = 54,
    ["Battle Notes"] = 55,
    ["Familiar Notes"] = 56,
    ["Secret Notes"] = 57,
    ["Kirby's Sounds"] = 58,
    ["Parasol scroll"] = 59,
    ["Graphic piece_13"] = 60,
    ["Secret Sounds"] = 61,
    ["King DeDeDe badge"] = 62,
    ["Mrs Moley badge"] = 63,
    ["Mecha-Kracko badge"] = 64,
    ["Yadgaine badge"] = 65,
    ["Bohboh badge"] = 66,
    ["Daroach badge"] = 67,
    ["Meta Knight badge"] = 68,
    ["Dark Nebula badge"] = 69,
    ["Yellow"] = 70,
    ["Red"] = 71,
    ["Green"] = 72,
    ["Snow"] = 73,
    ["Carbon"] = 74,
    ["Ocean"] = 75,
    ["Sapphire"] = 76,
    ["Grape"] = 77,
    ["Emerald"] = 78,
    ["Graphic piece_8"] = 79,
    ["Chocolate"] = 80,
    ["Cherry"] = 81,
    ["Chalk"] = 82,
    ["Shadow"] = 83,
    ["Ivory"] = 84,
    ["Citrus"] = 85,
    ["White"] = 86,
    ["Lavender"] = 87,
    ["Copy palette 1"] = 88,
    ["Sleep scroll"] = 89,
    ["Copy palette 3"] = 90,
    ["Copy palette 5"] = 91,
    ["Copy palette 2"] = 92,
    ["Secret Map_1"] = 93,
    ["Secret Map_2"] = 94,
    ["Secret Map_3"] = 95,
    ["Secret Map_4"] = 96,
    ["Secret Map_5"] = 97,
    ["Secret Map_6"] = 98,
    ["Secret Map_7"] = 99,
    ["Graphic piece_1"] = 100,
    ["Spunky Notes"] = 101,
    ["Graphic piece_15"] = 102,
    ["Graphic piece_9"] = 103,
    ["Graphic piece_18"] = 104,
    ["Graphic piece_12"] = 105,
    ["Graphic piece_7"] = 106,
    ["Graphic piece_4"] = 107,
    ["Graphic piece_16"] = 108,
    ["Graphic piece_5"] = 109,
    ["Graphic piece_14"] = 110,
    ["Graphic piece_3"] = 111,
    ["Graphic piece_19"] = 112,
    ["Graphic piece_2"] = 113,
    ["Graphic piece_6"] = 114,
    ["Graphic piece_11"] = 115,
    ["Sound Effects"] = 116,
    ["Vitality half_3"] = 117,
    ["Graphic piece_10"] = 118
}
local BIT_TO_NAME = {}
local KEY_SEAL = {
    ["Cushy Cloud key"] = true,
    ["Ice Island key"] = true,
    ["Jam Jungle key"] = true,
    ["Nature Notch key"] = true,
    ["Prism Plains key"] = true,
    ["Secret Sea key"] = true,
    ["Star seal 1"] = true,
    ["Star seal 2"] = true,
    ["Star seal 3"] = true,
    ["Star seal 4"] = true,
    ["Star seal 5"] = true,
    ["Vocal Volcano key"] = true
}
local ABILITY_SCROLL = {
    [1] = 'Fire scroll',
    [2] = 'Ice scroll',
    [3] = 'Spark scroll',
    [4] = 'Beam scroll',
    [5] = 'Tornado scroll',
    [6] = 'Parasol scroll',
    [7] = 'Cutter scroll',
    [8] = 'Laser scroll',
    [9] = 'Bomb scroll',
    [10] = 'Wheel scroll',
    [11] = 'UFO scroll',
    [12] = 'Hammer scroll',
    [13] = 'Cupid scroll',
    [15] = 'HiJump scroll',
    [16] = 'Sword scroll',
    [17] = 'Throw scroll',
    [18] = 'Magic scroll',
    [19] = 'Ninja scroll',
    [20] = 'Fighter scroll',
    [21] = 'Animal scroll',
    [22] = 'Bubble scroll',
    [23] = 'Metal scroll'
}

local function rb(abs) local ok,v=pcall(mainmemory.read_u8, abs-RAM); return ok and (v or 0) or 0 end
local function wb(abs,val) mainmemory.write_u8(abs-RAM, val % 256) end
local function read_coll() local f={} for i=0,14 do f[i]=rb(COLL+i) end return f end
local function bit_set(f,idx) local by=math.floor(idx/8); local bi=idx%8; return (math.floor((f[by] or 0)/(2^bi))%2)==1 end
local function byte_bit(v,bi) return (math.floor(v/(2^bi))%2)==1 end
local function gate_sum() local s=0 for a=GATE_LO,GATE_HI do s=(s+rb(a))%1000000007 end return s end
local function set_bit(idx) local by=math.floor(idx/8); local bi=idx%8; local a=COLL+by; local c=rb(a); local m=2^bi
    if (math.floor(c/m)%2)==0 then wb(a,c+m) end end
local function clear_bit(idx) local by=math.floor(idx/8); local bi=idx%8; local a=COLL+by; local c=rb(a); local m=2^bi
    if (math.floor(c/m)%2)==1 then wb(a,c-m) end end
local function append_check(idx) local f=io.open(CHECKS_FILE,"a"); if f then f:write(tostring(idx).."\n"); f:close() end end

local items_read=0
local function poll_items()
    local f=io.open(ITEMS_FILE,"r"); if not f then return {} end
    local r={}; local i=0
    for line in f:lines() do i=i+1; if i>items_read then r[#r+1]=line end end
    f:close(); items_read=items_read+#r; return r
end

do local cf=io.open(CHECKS_FILE,"w"); if cf then cf:close() end
   local gf=io.open(GOAL_FILE,"w");   if gf then gf:close() end end

local prev = read_coll()
local prev_gate = gate_sum()
local prev_sc = {}
for w=0,SC_WORLDS-1 do prev_sc[w]=rb(SC_BASE+2*w) end
local goal_sent = false
local received_scrolls = {}
local received_bits = {}   -- bit -> true : collectible received from AP (should be in collection)
local opened_bits = {}     -- bit -> true : you have physically opened this chest
local illegal_frames = 0

local function prev_set_bit(idx) local by=math.floor(idx/8); local bi=idx%8; local m=2^bi
    if (math.floor((prev[by] or 0)/m)%2)==0 then prev[by]=(prev[by] or 0)+m end end

local function tick()
    -- incoming items
    for _,name in ipairs(poll_items()) do
        name=name:gsub("[\r\n]","")
        local b=NAME_TO_BIT[name]
        if name:sub(-6)=="scroll" then received_scrolls[name]=true end
        if b then
            received_bits[b]=true
            if KEY_SEAL[name] then
                set_bit(b); prev_set_bit(b)           -- gate needs it now (may mask its own chest)
            elseif opened_bits[b] then
                set_bit(b); prev_set_bit(b)           -- chest already opened -> safe to show in collection
            end                                       -- else: held; kept when you open that chest
            gui.addmessage("AP: "..name)
        else
            gui.addmessage("AP: "..name)
        end
    end

    -- ability lock (delayed)
    local av=rb(ABILITY_ADDR); local need=ABILITY_SCROLL[av]
    if need~=nil and not received_scrolls[need] then
        illegal_frames=illegal_frames+POLL
        if illegal_frames>=ABILITY_DELAY then wb(ABILITY_ADDR,0); illegal_frames=0 end
    else illegal_frames=0 end

    -- chest opens
    local cur=read_coll(); local g=gate_sum(); local gate_changed=(g~=prev_gate)
    for i=0,NUM_BITS-1 do
        if bit_set(cur,i) and not bit_set(prev,i) and gate_changed then
            append_check(i); opened_bits[i]=true
            print("Check: location "..i); gui.addmessage("AP check: "..i)
            if i==GOAL_BIT then
                if not goal_sent then goal_sent=true
                    local gf=io.open(GOAL_FILE,"w"); if gf then gf:write("1"); gf:close() end
                    print("GOAL reached (cake)!") end
            elseif received_bits[i] then
                -- you received this collectible: KEEP it in your collection
            else
                clear_bit(i); cur[math.floor(i/8)]=rb(COLL+math.floor(i/8))  -- clear-vanilla
            end
        end
    end
    prev=cur; prev_gate=g

    -- stage clears
    for w=0,SC_WORLDS-1 do
        local v=rb(SC_BASE+2*w)
        if v~=prev_sc[w] then
            for bi=0,6 do
                if byte_bit(v,bi) and not byte_bit(prev_sc[w],bi) then
                    local vidx=SC_VBASE+(10*w+bi); append_check(vidx)
                    print("Stage clear: world "..w.." sub "..bi.." (idx "..vidx..")")
                    gui.addmessage("AP stage clear: W"..w.."S"..bi)
                end
            end
            prev_sc[w]=v
        end
    end
end

local n=0
event.onframestart(function() n=n+1; if n%POLL~=0 then return end; tick() end)

local okc=pcall(rb,COLL)
if okc then
    local f=read_coll(); local c=0
    for i=0,NUM_BITS-1 do if bit_set(f,i) then c=c+1 end end
    print("KSS connector ready (v7 deferred-grant). "..c.." chest locations already collected.")
    gui.addmessage("KSS connector ready")
else print("ERROR reading collectibles field"); gui.addmessage("KSS connector: RAM error") end
