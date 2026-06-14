-- KirbySqueakSquad_Connector.lua  (v21 - stable: live-color revert; death link send-only)
--
--   New in v21 (stable build):
--   * Color: reverted to the LIVE render byte (0x0226189C). Safe, cosmetic, and only
--     reverts on screens the game repaints (e.g. the collection screen), reapplying on
--     the next gameplay frame. The save-byte / spray approaches are gone.
--   * DeathLink is SEND-ONLY: zeroing HP does not kill Kirby (leaves a crash-prone 0-HP
--     state) and forcing the death state blocks the real sequence, so incoming deaths
--     are not applied. Outgoing deaths still broadcast normally.
--
--   From v19:
--   * Random starting spray: grants the spray collectible bit directly from slot_data
--     (the apworld removes that chest as a check). Fixes "spray never actually owned".
--   * Frame handler is now named so reloading the script REPLACES the old handler
--     instead of stacking it (fixes every message appearing twice after a reload).
--
--   From v18:
--   * Random starting color REMOVED entirely (was too fragile).
--   * DeathLink receive now forces the death STATE (0x2e) in a short burst so Kirby
--     actually dies; zeroing HP alone did not trigger it.
--
--   From v17:
--   * REMOVED the persistent saved-color/background writes (they could corrupt the
--     save). Color is LIVE-only again (0x0226189C); belly-background feature removed.
--     Use KirbySqueakSquad_RECOVER.lua if a v16 save was bricked.
--
--   From v16:
--   * Random color now writes the PERSISTENT saved index (0x0225601D) once per seed,
--     so it sticks across levels/menus/restarts AND the player can re-spray freely.
--   * Random belly/Copy-Palette background (0x0225601F) added the same way.
--
--   From v15:
--   * Random color now re-asserts continuously in-level (survives re-entry/menus).
--   * Ability watchdog delay back to 40 frames.
--   * Ability-acquired checks sent again (only register if the apworld option is on).
--
--   From v14:
--   * Death Link: when the option is on, Kirby dying (gamestate 0x2e) sends a
--     death to the multiworld, and an incoming death zeroes Kirby's health.
--
--   From v13:
--   * Stage clears are re-sent on connector load (previously a stage cleared in
--     an earlier session -- like the Daroach boss -- never registered until
--     re-cleared). Fixes the chests_and_daroach goal not completing.
--
--   From v12:
--   * Random starting color: if the apworld option is on, the client passes a
--     per-seed color and the connector writes it to 0x0226189C once you are in a
--     level. You can still change color later with spray paints.
--
--   From v11:
--   * Removed the ability-acquired (first-use) checks.
--
--   From v10:
--   * Zero masking: whenever a bit must be set on RECEIVE (keys/star seals for EX
--     gates; a 2nd ability copy for the scroll upgrade), the connector AUTO-CLAIMS
--     that chest's check so no location is ever lost. (Side effect: that chest's
--     item releases when you receive the key/upgrade rather than when you open it.)
--
--   From v9:
--   * Progressive Ability: each copy ability is received as "Progressive <X>".
--     1st copy lets you USE the base ability; 2nd copy gives the UPGRADED version.
--   * Ability-acquired checks: first time you legitimately hold a received
--     ability, an acquired-ability check (idx 400+) is sent.
--   * Weak foods (Hamburger/Nikuman/Omelet/Rice Ball/Pudding) heal 1/12 each.
--
--   Kept from v8.5: fractional heals; deferred collectible granting for full
--   collection; clear-vanilla; stage clears; goal 119.

local POLL = 8
local RAM = 0x02000000
local COLL = 0x02256020
local GATE_LO, GATE_HI = 0x02256031, 0x022560DC
local NUM_BITS, GOAL_BIT = 120, 119
local SC_BASE, SC_WORLDS, SC_VBASE = 0x022560D8, 8, 200
local ACQUIRED_VBASE = 400       -- ability-acquired check idx = 400 + ability acq index
local WORLD_NAMES = {"Prism Plains","Nature Notch","Cushy Cloud","Jam Jungle","Vocal Volcano","Ice Island","Secret Sea","Gamble Galaxy"}
local ABILITY_ADDR, ABILITY_DELAY = 0x0226188C, 40
local KINFO_PTR = 0x022618C0     -- pointer to Kirby info; 0 = not in level
local HP_OFF, MAXHP_OFF = 0x68, 0x6C
local LIFE_ADDR = 0x02261898     -- 32-bit life count

local TEMP = os.getenv("TEMP") or "C:\\Temp"
local CHECKS_FILE = TEMP .. "\\kss_checks.txt"
local ITEMS_FILE  = TEMP .. "\\kss_items.txt"
local GOAL_FILE   = TEMP .. "\\kss_goal.txt"
local DEATH_OUT   = TEMP .. "\\kss_death_out.txt"  -- connector -> client: Kirby died (send-only)
local COLOR_FILE  = TEMP .. "\\kss_color.txt"      -- client -> connector: starting color index
local STATE_ADDR  = 0x02255740                     -- gamestate; 0x2e = Kirby Dead
local COLOR_ADDR  = 0x0226189C                     -- LIVE Kirby color (render byte; safe to write)
local NUM_COLORS  = 19

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
-- Copy abilities for the Progressive system:
--   val    = value at 0x18C when this ability is held
--   scroll = that ability's scroll collectible bit (set on the 2nd copy = upgrade)
--   acq    = ability-acquired location index (check sent on first legit use)
local ABILITY = {
    ["Fire"]    = {val=0x01, scroll=28, acq=0},
    ["Ice"]     = {val=0x02, scroll=29, acq=1},
    ["Spark"]   = {val=0x03, scroll=30, acq=2},
    ["Beam"]    = {val=0x04, scroll=31, acq=3},
    ["Tornado"] = {val=0x05, scroll=32, acq=4},
    ["Hammer"]  = {val=0x0C, scroll=34, acq=5},
    ["Cupid"]   = {val=0x0D, scroll=35, acq=6},
    ["Cutter"]  = {val=0x07, scroll=36, acq=7},
    ["Laser"]   = {val=0x08, scroll=37, acq=8},
    ["Bomb"]    = {val=0x09, scroll=38, acq=9},
    ["Wheel"]   = {val=0x0A, scroll=39, acq=10},
    ["HiJump"]  = {val=0x0F, scroll=40, acq=11},
    ["UFO"]     = {val=0x0B, scroll=41, acq=12},
    ["Sword"]   = {val=0x10, scroll=43, acq=13},
    ["Ninja"]   = {val=0x13, scroll=44, acq=14},
    ["Fighter"] = {val=0x14, scroll=45, acq=15},
    ["Throw"]   = {val=0x11, scroll=46, acq=16},
    ["Magic"]   = {val=0x12, scroll=47, acq=17},
    ["Animal"]  = {val=0x15, scroll=48, acq=18},
    ["Bubble"]  = {val=0x16, scroll=49, acq=19},
    ["Metal"]   = {val=0x17, scroll=50, acq=20},
    ["Parasol"] = {val=0x06, scroll=59, acq=21},
    ["Sleep"]   = {val=0x0E, scroll=89, acq=22},
}
-- reverse lookup: 0x18C value -> ability name (only the 23 gated abilities)
local VAL_TO_ABILITY = {}
for nm,d in pairs(ABILITY) do VAL_TO_ABILITY[d.val]=nm end
-- heal = fraction of MAX health restored; life = extra lives
local FILLER = {
    ["Maxim Tomato"] = {heal = 1.0},     -- full
    ["Meat"]         = {heal = 1/2},     -- half
    ["Energy Drink"] = {heal = 1/3},     -- third
    ["Cherries"]     = {heal = 1/6},     -- sixth
    ["1-Up"]         = {life = 1},
    -- weak foods: bottom of the mixing tree (two of them = one cherry), 1/12 each
    ["Hamburger"]    = {heal = 1/12},
    ["Nikuman"]      = {heal = 1/12},
    ["Omelet"]       = {heal = 1/12},
    ["Rice Ball"]    = {heal = 1/12},
    ["Pudding"]      = {heal = 1/12},
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
   -- NOTE: kss_color.txt is NOT cleared here. The client writes it once per seed; the
   -- connector reads it and applies the color continuously, so it must survive reloads.

local prev = read_coll()
local prev_gate = gate_sum()
local prev_sc = {}
-- Start from 0 so that on the first tick, every CURRENTLY-set stage-clear bit is
-- detected and sent. This makes stages cleared in a previous session (e.g. a boss
-- like Daroach beaten before a connector reload) re-register; checks are deduped
-- by the client/server, so re-sending is harmless.
for w=0,SC_WORLDS-1 do prev_sc[w]=0 end
local goal_sent = false
-- DeathLink state
local death_out_n = 0
local prev_state = rb(STATE_ADDR)
local color_target = nil
os.remove(DEATH_OUT)
local received_prog = {}   -- ability name -> count of Progressive copies received (0/1/2)
local acquired_sent = {}   -- ability name -> first-use check already sent
local received_bits = {}
local opened_bits = {}
local illegal_frames = 0
local pending_heal = 0.0   -- accumulated fraction of max HP to restore
local pending_lives = 0

local function prev_set_bit(idx) local by=math.floor(idx/8); local bi=idx%8; local m=2^bi
    if (math.floor((prev[by] or 0)/m)%2)==0 then prev[by]=(prev[by] or 0)+m end end

-- Some bits must be set the moment the item is RECEIVED (keys/seals unlock EX
-- gates; a 2nd ability copy sets its scroll bit for the upgrade). Setting a bit
-- before its chest is opened would "mask" that chest (an already-set chest writes
-- nothing when opened, so no check fires). To avoid losing the check, we
-- auto-claim it here: send the chest's check now, then set the bit. If the chest
-- was already opened, its check already went out, so we just set the bit.
local autoclaimed = {}
local function grant_and_claim(b)
    if b ~= GOAL_BIT and not opened_bits[b] and not autoclaimed[b] then
        append_check(b); autoclaimed[b]=true
        print("Auto-claimed location "..b.." (bit set on receive)")
    end
    set_bit(b); prev_set_bit(b)
end

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
    -- DeathLink (SEND-ONLY): when Kirby dies, the gamestate flips to 0x2e. We notify the
    -- client, which broadcasts the death. Incoming deaths are NOT applied: zeroing HP does
    -- not trigger KSS's death (it just strands Kirby at 0 HP in a crash-prone state), and
    -- forcing the state blocks the real death sequence. So this is send-only by design.
    local st = rb(STATE_ADDR)
    if st == 0x2e and prev_state ~= 0x2e then
        death_out_n = death_out_n + 1
        local f=io.open(DEATH_OUT,"w"); if f then f:write(tostring(death_out_n)); f:close() end
        print("DeathLink: Kirby died -> notified client")
    end
    prev_state = st

    -- Starting color: client drops kss_color.txt with an index once per seed. We hold the
    -- LIVE render byte to that color while Kirby is in a level. This is cosmetic and safe.
    -- QUIRK: the game repaints Kirby from its SAVED color on some screens (notably opening
    -- the collection screen), so the color reverts there and we re-apply it on the next
    -- gameplay frame. Spray paints can't override it while this is enforced.
    if color_target == nil then
        local cf=io.open(COLOR_FILE,"r")
        if cf then
            local v=tonumber((cf:read("*l") or "")); cf:close()
            if v then color_target = v % NUM_COLORS; print("Starting color = "..color_target) end
        end
    end
    if color_target ~= nil and kirby_base() then wb(COLOR_ADDR, color_target) end

    -- incoming items
    for _,name in ipairs(poll_items()) do
        name=name:gsub("[\r\n]","")
        local prog = name:match("^Progressive (.+)$")
        if prog and ABILITY[prog] then
            received_prog[prog]=(received_prog[prog] or 0)+1
            if received_prog[prog]>=2 then
                -- 2nd copy: set the scroll bit -> game gives the upgraded ability.
                -- grant_and_claim auto-sends that scroll chest's check if needed.
                grant_and_claim(ABILITY[prog].scroll)
                msg("(*v*) "..prog.." UPGRADED!  scroll power unlocked!")
            else
                msg("(*^-^) "..prog.." get!  you can use "..prog.." now!")
            end
        else
            local b=NAME_TO_BIT[name]
            if b then
                received_bits[b]=true
                if KEY_SEAL[name] then grant_and_claim(b)
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
    end

    apply_filler()

    -- ability lock (delayed): drop a gated ability the player hasn't received yet
    local av=rb(ABILITY_ADDR)
    local abname=VAL_TO_ABILITY[av]
    if abname and (received_prog[abname] or 0) < 1 then
        illegal_frames=illegal_frames+POLL
        if illegal_frames>=ABILITY_DELAY then wb(ABILITY_ADDR,0); illegal_frames=0 end
    else
        illegal_frames=0
        -- ability-acquired check: only meaningful if the apworld option added these
        -- locations; if not, the server simply ignores the unknown id (harmless).
        if abname and (received_prog[abname] or 0) >= 1 and not acquired_sent[abname] then
            acquired_sent[abname]=true
            append_check(ACQUIRED_VBASE + ABILITY[abname].acq)
            print("Ability acquired: "..abname)
        end
    end

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
event.onframestart(function() n=n+1; if n%POLL~=0 then return end; tick() end, "kss_connector")

local okc=pcall(rb,COLL)
if okc then
    local f=read_coll(); local c=0
    for i=0,NUM_BITS-1 do if bit_set(f,i) then c=c+1 end end
    print("KSS connector ready (v21). "..c.." chest locations already collected.")
    msg("<(^-^<) Kirby connector ready! let's find some treasure!")
else print("ERROR reading collectibles field"); msg("x_x  connector: RAM error") end
