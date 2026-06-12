-- KirbySqueakSquad_Connector.lua  (v8.5 - fractional heals; fix Cherry name clash)
--
--   Adds to v7:
--   * FILLER now has an effect when received: Maxim Tomato / Energy Drink /
--     food (Maxim Tomato full, Meat 1/2, Energy Drink 1/3, Cherries 1/6) restores a
--     fraction of max health; 1-Up adds a life. Effects are queued and
--     applied the next time you're in a level (Kirby info pointer valid).
--   * ABILITY_DELAY trimmed to 40 frames (still long enough to dodge the
--     mid-transition freeze; shorter window before an un-scrolled ability drops).
--
--   (v7 behavior kept: deferred collectible granting for full collection with
--    masking limited to the 12 keys/seals; clear-vanilla; stage clears; goal 119.)

local POLL = 8
local RAM = 0x02000000
local COLL = 0x02256020
local GATE_LO, GATE_HI = 0x02256031, 0x022560DC
local NUM_BITS, GOAL_BIT = 120, 119
local SC_BASE, SC_WORLDS, SC_VBASE = 0x022560D8, 8, 200
local WORLD_NAMES = {"Prism Plains","Nature Notch","Cushy Cloud","Jam Jungle","Vocal Volcano","Ice Island","Secret Sea","Gamble Galaxy"}
local ABILITY_ADDR, ABILITY_DELAY = 0x0226188C, 40
local KINFO_PTR = 0x022618C0     -- pointer to Kirby info; 0 = not in level
local HP_OFF, MAXHP_OFF = 0x68, 0x6C
local LIFE_ADDR = 0x02261898     -- 32-bit life count

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
-- heal = fraction of MAX health restored; life = extra lives
local FILLER = {
    ["Maxim Tomato"] = {heal = 1.0},     -- full
    ["Meat"]         = {heal = 1/2},     -- half
    ["Energy Drink"] = {heal = 1/3},     -- third
    ["Cherries"]     = {heal = 1/6},     -- sixth
    ["1-Up"]         = {life = 1},
}

-- Kirby-flavored pop-ups -----------------------------------------------------
local function msg(text) gui.addmessage(text) end

-- pick flavor by what kind of thing arrived
local function item_flavor(name)
    if name:sub(-6)=="scroll" then
        return "(*v*) Scroll get!  "..name.." -- ability unlocked!"
    elseif KEY_SEAL[name] then
        return "(>'-')> Key get!  "..name
    elseif FILLER[name] and FILLER[name].life then
        return "p(^_^)q 1-UP!  one more try in your pocket!"
    elseif FILLER[name] and FILLER[name].heal then
        return "<(^o^)> Yum!  "..name.." restored some health!"
    elseif name:find("badge") then
        return "(^o^)b Badge get!  "..name
    elseif name:find("seal") then
        return "(*^-^) Star Seal!  "..name
    else
        return "(>^-^)>  Treasure get!  "..name
    end
end

local CHEST_FLAVOR = {
    "* poyo! chest opened -- check sent! *",
    "<(o.o<)  inhaled a check!",
    "(^o^)  treasure tracked!",
    "*(^_^)* another one for the squad!",
}
local function chest_msg()
    return CHEST_FLAVOR[(math.random(#CHEST_FLAVOR))]
end

local function rb(abs) local ok,v=pcall(mainmemory.read_u8, abs-RAM); return ok and (v or 0) or 0 end
local function wb(abs,val) mainmemory.write_u8(abs-RAM, val % 256) end
local function ru32(abs) local ok,v=pcall(mainmemory.read_u32_le, abs-RAM); return ok and (v or 0) or 0 end
local function wu32(abs,val) pcall(mainmemory.write_u32_le, abs-RAM, val) end
local function read_coll() local f={} for i=0,14 do f[i]=rb(COLL+i) end return f end
local function bit_set(f,idx) local by=math.floor(idx/8); local bi=idx%8; return (math.floor((f[by] or 0)/(2^bi))%2)==1 end
local function byte_bit(v,bi) return (math.floor(v/(2^bi))%2)==1 end
local function gate_sum() local s=0 for a=GATE_LO,GATE_HI do s=(s+rb(a))%1000000007 end return s end
local function set_bit(idx) local by=math.floor(idx/8); local bi=idx%8; local a=COLL+by; local c=rb(a); local m=2^bi
    if (math.floor(c/m)%2)==0 then wb(a,c+m) end end
local function clear_bit(idx) local by=math.floor(idx/8); local bi=idx%8; local a=COLL+by; local c=rb(a); local m=2^bi
    if (math.floor(c/m)%2)==1 then wb(a,c-m) end end
local function append_check(idx) local f=io.open(CHECKS_FILE,"a"); if f then f:write(tostring(idx).."\n"); f:close() end end

local function kirby_base()
    local p=ru32(KINFO_PTR)
    if p>=0x02000000 and p<0x03000000 then return p end
    return nil
end

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
local received_bits = {}
local opened_bits = {}
local illegal_frames = 0
local pending_heal = 0.0   -- accumulated fraction of max HP to restore
local pending_lives = 0

local function prev_set_bit(idx) local by=math.floor(idx/8); local bi=idx%8; local m=2^bi
    if (math.floor((prev[by] or 0)/m)%2)==0 then prev[by]=(prev[by] or 0)+m end end

local function apply_filler()
    local base=kirby_base()
    if pending_heal > 0 and base then
        local mx=ru32(base+MAXHP_OFF)
        if mx>0 and mx<1000 then
            local cur=ru32(base+HP_OFF)
            local add=math.floor(mx*pending_heal + 0.5)
            local newhp=cur+add; if newhp>mx then newhp=mx end
            wu32(base+HP_OFF, newhp)
            pending_heal=0.0
        end
    end
    if pending_lives>0 then
        local cur=ru32(LIFE_ADDR)
        if cur<999 then wu32(LIFE_ADDR, cur+pending_lives); pending_lives=0 end
    end
end

local function tick()
    -- incoming items
    for _,name in ipairs(poll_items()) do
        name=name:gsub("[\r\n]","")
        local b=NAME_TO_BIT[name]
        if name:sub(-6)=="scroll" then received_scrolls[name]=true end
        if b then
            received_bits[b]=true
            if KEY_SEAL[name] then set_bit(b); prev_set_bit(b)
            elseif opened_bits[b] then set_bit(b); prev_set_bit(b) end
            msg(item_flavor(name))
        else
            local fx=FILLER[name]
            if fx then
                if fx.life then pending_lives=pending_lives+fx.life end
                if fx.heal then pending_heal=pending_heal+fx.heal end
            end
            msg(item_flavor(name))
        end
    end

    apply_filler()

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
            print("Check: location "..i); msg(chest_msg())
            if i==GOAL_BIT then
                if not goal_sent then goal_sent=true
                    local gf=io.open(GOAL_FILE,"w"); if gf then gf:write("1"); gf:close() end
                    print("GOAL reached (cake)!") end
            elseif received_bits[i] then
                -- received: keep it in the collection
            else
                clear_bit(i); cur[math.floor(i/8)]=rb(COLL+math.floor(i/8))
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
                    msg("(>^o^)>  Stage clear!  "..(WORLD_NAMES[w+1] or ("W"..w)).." "..(bi+1))
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
    print("KSS connector ready (v8.5). "..c.." chest locations already collected.")
    msg("<(^-^<) Kirby connector ready! let's find some treasure!")
else print("ERROR reading collectibles field"); msg("x_x  connector: RAM error") end
