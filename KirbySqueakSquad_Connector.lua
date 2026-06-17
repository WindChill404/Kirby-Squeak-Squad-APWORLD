-- KirbySqueakSquad_Connector.lua  (v29 - adds the in-game opened-chest overlay; v28 overflow fix kept)
--
--   New in v29:
--   * IN-GAME OPENED-CHEST OVERLAY. For the stage you're on, draws a checklist of its chests
--     marking which you've already opened (sent as AP checks), since the game's own level-map
--     icons can't show this (they ride the per-stage counter v28 decrements). "Opened" is the
--     union of this session's sent checks plus the server's authoritative list, which the client
--     now writes to kss_checked.txt -- so it survives reloads and includes chests opened earlier.
--     Toggle it on/off live with the OVERLAY_TOGGLE_KEY (default "T"); default-on is configurable.
--     Pure display: it only reads RAM + that file and calls gui.text, never writes game memory.
--
--   New in v28:
--   * SURGICAL re-collect overflow fix (see below).
--
-- KirbySqueakSquad_Connector.lua  (v28 - SURGICAL re-collect overflow fix; masking + watchdog gating)
--
--   New in v28:
--   * RE-COLLECT OVERFLOW FIX, done right. Each stage has a one-byte "chests found" counter at
--     0x02256030 + world*10 + substage (mapped via COUNTERMAP, confirmed across worlds 0/1/2). The
--     game bumps it on every collection, even re-collecting the same masked chest on a replay, and
--     once it passes the stage max (3/3) the results screen overflows -> white screen. Now, when the
--     connector masks a chest, it decrements ONLY that one fenced byte by 1, undoing the bump, so a
--     masked chest counts 0 and the total can't climb on replays. The write is hard-fenced to
--     0x02256030..0x0225607F, so unlike v26's broad reset it can never reach the per-world clear
--     masks (0x0225609A+) or stage-clear bytes (0x022560D8+) -- progression is untouched.
--
--   v27 (REVERTED v26): pulled v26's broad counter reset, which stomped progression data.
--
--   New in v26 (REVERTED in v27):
--   * WHITE-SCREEN-ON-REPLAY FIX (the real one): every stage keeps a "chests found" counter
--     (the 3/3 on the level-select), and the game increments it each time you collect a chest --
--     even the SAME chest re-collected on a later run. Because masking clears the collectible bit,
--     the game lets you re-collect a masked chest, so that counter climbed every replay and, once
--     it passed the stage's max (e.g. a 4th collect in a 3-chest stage), the results screen
--     overflowed and white-screened. Now, whenever the connector masks a chest, it also UNDOES the
--     counter bump (restores that stage's count byte to its pre-collection value), so a masked
--     chest contributes 0 and the count can never exceed the max no matter how many replays. Only
--     the opened-counter sub-range is touched; stage-clear bytes are never altered. This is why the
--     bug only ever hit on RE-ENTERING a stage, never on a first clear (you start at 0).
--
--   New in v25:
--   * TRANSITION-HANG FIX (white screen stuck between chest-open and stage-select on a progression
--     item): the ability watchdog is now gated to only drop an un-received ability while Kirby is
--     IN a stage. Before, it ran during the out-of-stage chest-open transition too -- opening a
--     scroll hands Kirby that ability mid get-sequence, and the watchdog zeroing the ability byte
--     right then desynced the sequence and hung the white screen (the progression-item get-sequence
--     outlasts the 40-frame drop delay, so it fired mid-sequence). Now matched to how vitality and
--     color writes are already gated: connector touches the ability only during active gameplay.
--     The lock is still fully enforced -- it drops the ability the instant Kirby is back in a stage.
--     MASKTEST proved the masking itself is safe (save AND transition), so masking is unchanged.
--
--   New in v24:
--   * Masking RESTORED for keys, star seals, and ability scrolls. Testing (a standalone MASKTEST
--     plus the OPENDIFF save-footprint capture) proved that clearing a chest's collectible bit is
--     save-safe even across the stage-exit save -- a masked chest just reads as an opened gray
--     chest, which reloads fine. Keys/seals/scrolls have the identical footprint to a regular
--     collectible, so they're masked normally again: AP keeps full control of those items, no
--     vanilla leak, and Progressive Ability is fully intact. (The v23 "leave them vanilla" fix was
--     a wrong turn -- the corruption a tester hit was NOT the masking.)
--   * BOSS BADGES still left un-cleared (NO_CLEAR): a badge chest also writes a large world-
--     progression block, so it needs the in-progress world-gating handling, not a plain bit-clear.
--
--   (v23 was: left keys/seals/scrolls/badges vanilla to dodge a suspected save-corruption that
--    turned out not to be the masking. Superseded.)
--
--   New in v22:
--   * DeathLink RECEIVE works: an incoming death applies the captured in-place death-commit
--     cluster (HP=0 + DEATH_FLAGS) so Kirby dies normally where he stands. Full send+receive.
--   * Vitality halves: max HP is now driven by halves received (36 + 4 per completed heart);
--     the bits are never kept in-level, which fixes the heart-complete animation CRASH.
--   * Weak foods heal 1/9 (was 1/12).
--
--   From v21:
--   * Color: reverted to the LIVE render byte (0x0226189C). Safe, cosmetic, and only
--     reverts on screens the game repaints (e.g. the collection screen), reapplying on
--     the next gameplay frame. The save-byte / spray approaches are gone.
--     (DeathLink became full send+receive in v22, above.)
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
--   * Weak foods (Hamburger/Nikuman/Omelet/Rice Ball/Pudding) heal 1/9 each.
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
local DEATH_OUT   = TEMP .. "\\kss_death_out.txt"  -- connector -> client: Kirby died (send)
local DEATH_IN    = TEMP .. "\\kss_death_in.txt"   -- client -> connector: remote death (receive)
local COLOR_FILE  = TEMP .. "\\kss_color.txt"      -- client -> connector: starting color index
local CHECKED_FILE = TEMP .. "\\kss_checked.txt"   -- client -> connector: authoritative checked-chest list (for the overlay)
-- ---- in-game opened-chest overlay (Option B) ----
local OVERLAY_DEFAULT_ON = true    -- is the overlay showing when you launch?
local OVERLAY_TOGGLE_KEY = "T"     -- press this key to show/hide the overlay live.
                                   -- If it clashes with an EmuHawk hotkey, change it (any key
                                   -- name works, e.g. "Y", "Tab", "F8") or unbind it in EmuHawk.
local STATE_ADDR  = 0x02255740                     -- gamestate; 0x2e = Kirby Dead
local COLOR_ADDR  = 0x0226189C                     -- LIVE Kirby color (render byte; safe to write)
local NUM_COLORS  = 19

-- DeathLink RECEIVE: the exact in-place death-commit cluster the game sets when it kills
-- Kirby (verified by capture). Writing HP=0 plus these (relative to the Kirby struct base)
-- makes the game run its normal death where Kirby stands. Held for a few frames so it takes.
local DEATH_FLAGS = {
    {0x018,4}, {0x070,0}, {0x08C,0}, {0x094,0}, {0x09C,0},
    {0x0A0,-697}, {0x0B4,11}, {0x0E4,3}, {0x100,21}, {0x128,0}, {0x164,0},
}

-- Vitality halves: collectible bits whose HEALTH upgrade the game does NOT derive from the
-- bitfield. We drive max HP ourselves from how many halves were received, and we never let
-- these bits persist in-level (so the game's heart-complete animation can't crash on a
-- mismatched count). maxHP = BASE_MAXHP + HEART_HP * floor(halves / 2).
local VITALITY = {[6]=true,[7]=true,[9]=true,[10]=true,[11]=true,[12]=true,[13]=true,[117]=true}
local BASE_MAXHP, HEART_HP = 36, 4

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

-- SAVE-SAFETY (v24): testing (MASKTEST + the OPENDIFF capture) showed that clearing a chest's
-- collectible bit to mask it is SAVE-SAFE even across the stage-exit save -- a masked chest just
-- looks like an opened gray chest, which the game reloads fine. Keys, seals, and ability scrolls
-- have the exact same save footprint as a regular collectible (just their bit + an opened byte),
-- so they are masked normally again -- this keeps AP in full control of those items with NO leak
-- and Progressive Ability fully intact. (v23 had wrongly left them vanilla; the corruption a tester
-- hit was NOT the masking.)
--
-- The ONE exception is BOSS BADGES: opening a badge chest also writes a large world-progression
-- block (the next-world unlock), so clearing just the badge bit would orphan that. Badge handling
-- is part of the in-progress in-game world-gating work, so badges stay un-cleared for now.
local NO_CLEAR = {}
for b=62,69 do NO_CLEAR[b]=true end                                                         -- boss badges only

-- heal = fraction of MAX health restored; life = extra lives
local FILLER = {
    ["Maxim Tomato"] = {heal = 1.0},     -- full
    ["Meat"]         = {heal = 1/2},     -- half
    ["Energy Drink"] = {heal = 1/3},     -- third
    ["Cherries"]     = {heal = 1/6},     -- sixth
    ["1-Up"]         = {life = 1},
    -- weak foods: bottom of the mixing tree, 1/9 each
    ["Hamburger"]    = {heal = 1/9},
    ["Nikuman"]      = {heal = 1/9},
    ["Omelet"]       = {heal = 1/9},
    ["Rice Ball"]    = {heal = 1/9},
    ["Pudding"]      = {heal = 1/9},
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
local function wu32(abs,val) pcall(mainmemory.write_u32_le, abs-RAM, val % 0x100000000) end
local function read_coll() local f={} for i=0,14 do f[i]=rb(COLL+i) end return f end
local function bit_set(f,idx) local by=math.floor(idx/8); local bi=idx%8; return (math.floor((f[by] or 0)/(2^bi))%2)==1 end
local function byte_bit(v,bi) return (math.floor(v/(2^bi))%2)==1 end
local function gate_sum() local s=0 for a=GATE_LO,GATE_HI do s=(s+rb(a))%1000000007 end return s end

-- Per-stage "chests found" counter (the 3/3 on level-select). One byte per stage, laid out as
--   byte = 0x02256030 + world*10 + substage     (world/substage are the raw 0-indexed RAM values).
-- Confirmed across worlds 0/1/2 via the COUNTERMAP capture. Every counter sits in
-- 0x02256030..0x0225607F, safely below the per-world clear masks (0x0225609A+) and stage-clear
-- bytes (0x022560D8+). When we MASK a chest the game bumps this counter; we undo exactly that one
-- byte so a masked chest counts 0 and re-collecting it on replays can't climb to the stage max
-- (which overflows -> white screen). Targeting one fenced byte means we never touch progression.
local COUNTER_BASE = 0x02256030
local WORLD_ADDR, SUBSTAGE_ADDR = 0x02260BF4, 0x02260BF8
local COUNTER_MIN, COUNTER_MAX  = 0x02256030, 0x0225607F   -- hard fence: never write outside this
local function dec_stage_counter()
    local w, s = ru32(WORLD_ADDR), ru32(SUBSTAGE_ADDR)
    if w > 7 or s > 9 then return end                       -- not a real stage index -> do nothing
    local a = COUNTER_BASE + w*10 + s
    if a < COUNTER_MIN or a > COUNTER_MAX then return end    -- fence: stay clear of progression data
    local c = rb(a)
    if c > 0 then wb(a, c-1) end                             -- undo this masked chest's +1 bump
end
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
local last_death_in = ""
do local df=io.open(DEATH_IN,"r"); if df then last_death_in=(df:read("*l") or ""); df:close() end end
local kill_frames = 0       -- per-frame death-commit application remaining (dense, short)
local suppress_frames = 0   -- ticks to not echo our own forced death
local color_target = nil
-- Vitality health: how many halves received -> drives max HP
local vit_received = 0
local vit_heal = false
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
    -- DeathLink SEND: when Kirby dies, gamestate flips to 0x2e -> tell the client.
    -- DeathLink RECEIVE: an incoming death writes kss_death_in.txt; we apply the in-place
    -- death-commit cluster (HP=0 + DEATH_FLAGS), held briefly, so the game runs its normal
    -- death where Kirby stands. suppress_frames stops us echoing our own forced death.
    local st = rb(STATE_ADDR)
    if st == 0x2e and prev_state ~= 0x2e and suppress_frames == 0 then
        death_out_n = death_out_n + 1
        local f=io.open(DEATH_OUT,"w"); if f then f:write(tostring(death_out_n)); f:close() end
        print("DeathLink: Kirby died -> notified client")
    end
    prev_state = st
    if suppress_frames > 0 then suppress_frames = suppress_frames - 1 end

    do
        local f=io.open(DEATH_IN,"r")
        if f then
            local v=(f:read("*l") or ""); f:close()
            if v~="" and v~=last_death_in then
                last_death_in=v
                kill_frames = 80             -- ~20 frames of cluster, then hold HP=0 briefly
                suppress_frames = 35
                msg("(x_x)  DeathLink received!")
                print("DeathLink: received -> applying death-commit cluster")
            end
        end
    end
    -- (death-commit cluster is applied per-frame in the frame handler so it's dense and
    -- brief: a long sparse re-apply re-triggers the hit sound and freezes the squish.)

    -- Vitality health: keep max HP in sync with halves received. Skip transient states
    -- (e.g. invincibility / ability grab read maxHP ~100) so we don't fight them.
    do
        local base=kirby_base()
        if base then
            local target = BASE_MAXHP + HEART_HP * math.floor(vit_received / 2)
            local mx = ru32(base + MAXHP_OFF)
            if mx >= 30 and mx <= 60 and mx ~= target then
                wu32(base + MAXHP_OFF, target)
                if vit_heal then
                    wu32(base + HP_OFF, target); vit_heal = false   -- top up on a fresh grant
                end
            end
        end
    end

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
                if VITALITY[b] then
                    vit_received = vit_received + 1   -- grows max HP; bit NOT set (crash-safe)
                    vit_heal = true
                elseif KEY_SEAL[name] then grant_and_claim(b)
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
        if kirby_base() then
            illegal_frames=illegal_frames+POLL
            -- Only drop while IN a stage. NEVER during the out-of-stage chest-open transition:
            -- opening a scroll hands Kirby that ability mid get-sequence, and zeroing the ability
            -- byte there desyncs the sequence and HANGS the white transition screen (the bug two
            -- testers hit on progression items). The lock is still enforced the instant Kirby is
            -- back in a stage.
            if illegal_frames>=ABILITY_DELAY then wb(ABILITY_ADDR,0); illegal_frames=0 end
        else
            illegal_frames=0   -- out of stage: pause the watchdog, leave the ability untouched
        end
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
            elseif VITALITY[i] then
                -- never let a vitality bit persist in-level: keeping it would let the game's
                -- heart-complete animation read an inflated count and crash. Check already
                -- sent above; health is driven by vit_received instead.
                clear_bit(i); cur[math.floor(i/8)]=rb(COLL+math.floor(i/8)); dec_stage_counter()
            elseif received_bits[i] then
                -- received: keep it in the collection
            elseif NO_CLEAR[i] then
                -- boss badge: opening one also writes a large world-progression block, so a plain
                -- bit-clear would orphan that. Left intact pending the in-game world-gating work.
                -- Check already fired above.
            else
                clear_bit(i); cur[math.floor(i/8)]=rb(COLL+math.floor(i/8)); dec_stage_counter()
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

-- ===================== IN-GAME OPENED-CHEST OVERLAY (Option B) =====================
-- For the stage you're currently on, lists which of its chests you've already opened
-- (sent as AP checks). The game's own level-map icons can't show this -- they're driven
-- by the per-stage counter we decrement to stop the re-collect overflow -- so this draws
-- an independent checklist instead. "Opened" is the union of: chests THIS session has
-- sent, plus the authoritative list the client writes to kss_checked.txt from the server
-- (so it survives reloads and shows chests opened before the overlay existed). The stage
-- key is world*10+substage -- the same layout as the counter -- and substage = in-game
-- stage-1 (so 1-5 -> 0-4, EX -> 5, Boss -> 6). Press OVERLAY_TOGGLE_KEY to show/hide.

local CHEST_BY_STAGE = {
  [1] = { {52,"Beginning Notes"} },
  [2] = { {5,"Sound player"}, {28,"Fire scroll"} },
  [3] = { {14,"Prism Plains key"}, {72,"Green"}, {100,"Graphic piece_1"} },
  [4] = { {88,"Copy palette 1"} },
  [5] = { {6,"Vitality half_1"}, {113,"Graphic piece_2"} },
  [6] = { {62,"King DeDeDe badge"} },
  [10] = { {0,"Star seal 1"}, {48,"Animal scroll"}, {58,"Kirby's Sounds"} },
  [11] = { {21,"Ghost medal_1"}, {85,"Citrus"} },
  [12] = { {39,"Wheel scroll"}, {92,"Copy palette 2"}, {111,"Graphic piece_3"} },
  [13] = { {36,"Cutter scroll"} },
  [14] = { {15,"Nature Notch key"}, {31,"Beam scroll"}, {107,"Graphic piece_4"} },
  [15] = { {7,"Vitality half_2"}, {93,"Secret Map_1"}, {109,"Graphic piece_5"} },
  [16] = { {63,"Mrs Moley badge"} },
  [20] = { {30,"Spark scroll"}, {77,"Grape"}, {114,"Graphic piece_6"} },
  [21] = { {1,"Star seal 2"}, {56,"Familiar Notes"} },
  [22] = { {22,"Ghost medal_2"}, {94,"Secret Map_2"}, {106,"Graphic piece_7"} },
  [23] = { {16,"Cushy Cloud key"}, {40,"HiJump scroll"}, {87,"Lavender"} },
  [24] = { {32,"Tornado scroll"} },
  [25] = { {8,"Orange"}, {79,"Graphic piece_8"}, {117,"Vitality half_3"} },
  [26] = { {64,"Mecha-Kracko badge"} },
  [30] = { {49,"Bubble scroll"}, {83,"Shadow"}, {103,"Graphic piece_9"} },
  [31] = { {2,"Star seal 3"}, {70,"Yellow"} },
  [32] = { {9,"Vitality half_4"}, {50,"Metal scroll"}, {90,"Copy palette 3"} },
  [33] = { {17,"Jam Jungle key"}, {95,"Secret Map_3"}, {118,"Graphic piece_10"} },
  [34] = { {37,"Laser scroll"} },
  [35] = { {23,"Ghost medal_3"}, {29,"Ice scroll"}, {51,"Party Notes"} },
  [36] = { {65,"Yadgaine badge"} },
  [40] = { {3,"Star seal 4"}, {33,"Enemy Sounds"}, {59,"Parasol scroll"} },
  [41] = { {34,"Hammer scroll"}, {84,"Ivory"}, {115,"Graphic piece_11"} },
  [42] = { {10,"Vitality half_5"}, {44,"Ninja scroll"}, {105,"Graphic piece_12"} },
  [43] = { {18,"Vocal Volcano key"}, {71,"Red"}, {96,"Secret Map_4"} },
  [45] = { {24,"Ghost medal_4"}, {42,"Copy palette 4"}, {89,"Sleep scroll"} },
  [46] = { {66,"Bohboh badge"} },
  [50] = { {43,"Sword scroll"}, {60,"Graphic piece_13"}, {116,"Sound Effects"} },
  [51] = { {4,"Star seal 5"}, {73,"Snow"} },
  [52] = { {11,"Vitality half_6"}, {45,"Fighter scroll"}, {110,"Graphic piece_14"} },
  [53] = { {19,"Ice Island key"}, {53,"Happy Notes"}, {82,"Chalk"} },
  [54] = { {35,"Cupid scroll"}, {91,"Copy palette 5"}, {102,"Graphic piece_15"} },
  [55] = { {25,"Ghost medal_5"}, {81,"Cherry"}, {97,"Secret Map_5"} },
  [56] = { {67,"Daroach badge"} },
  [60] = { {46,"Throw scroll"}, {61,"Secret Sounds"}, {86,"White"} },
  [61] = { {26,"Ghost medal_6"}, {76,"Sapphire"}, {108,"Graphic piece_16"} },
  [62] = { {38,"Bomb scroll"}, {54,"Graphic piece_17"}, {101,"Spunky Notes"} },
  [63] = { {20,"Secret Sea key"}, {47,"Magic scroll"}, {75,"Ocean"} },
  [64] = { {80,"Chocolate"} },
  [65] = { {12,"Vitality half_7"}, {98,"Secret Map_6"}, {104,"Graphic piece_18"} },
  [66] = { {68,"Meta Knight badge"} },
  [70] = { {41,"UFO scroll"}, {55,"Battle Notes"}, {112,"Graphic piece_19"} },
  [71] = { {27,"Ghost medal_7"}, {78,"Emerald"}, {99,"Secret Map_7"} },
  [72] = { {13,"Vitality half_8"}, {57,"Secret Notes"}, {74,"Carbon"} },
  [76] = { {69,"Dark Nebula badge"} },
}

local overlay_on = OVERLAY_DEFAULT_ON
local toggle_prev = false
local function update_overlay_toggle()
    local ok, keys = pcall(input.get)
    if not ok or not keys then return end
    local down = keys[OVERLAY_TOGGLE_KEY] and true or false
    if down and not toggle_prev then
        overlay_on = not overlay_on
        msg(overlay_on and "Chest overlay: ON" or "Chest overlay: OFF")
    end
    toggle_prev = down
end

local checked_file = {}            -- bit -> true, from kss_checked.txt (server-authoritative)
local function reload_checked()
    local t = {}
    local f = io.open(CHECKED_FILE, "r")
    if f then
        for line in f:lines() do
            local b = tonumber(line)
            if b then t[b] = true end
        end
        f:close()
    end
    checked_file = t
end

local function is_opened(bit)
    return (opened_bits[bit] or checked_file[bit]) and true or false
end

local function stage_label(w, s)
    local wn = WORLD_NAMES[w+1] or ("World "..(w+1))
    local sn
    if s <= 4 then sn = tostring(s+1)
    elseif s == 5 then sn = "EX"
    elseif s == 6 then sn = "Boss"
    else sn = "?" end
    return string.format("%d-%s %s", w+1, sn, wn)
end

local function draw_overlay()
    if not overlay_on then return end
    local w, s = ru32(WORLD_ADDR), ru32(SUBSTAGE_ADDR)
    if w > 7 or s > 9 then return end
    local list = CHEST_BY_STAGE[w*10 + s]
    if not list then return end
    local nopen = 0
    for _,c in ipairs(list) do if is_opened(c[1]) then nopen = nopen + 1 end end
    local x, y = 4, 4
    pcall(gui.text, x, y, string.format("[KSS] %s  (%d/%d opened)", stage_label(w,s), nopen, #list), 0xFFFFFFFF)
    y = y + 16
    for _,c in ipairs(list) do
        local op = is_opened(c[1])
        pcall(gui.text, x, y, (op and "[x] " or "[ ] ")..c[2], op and 0xFF66FF66 or 0xFFD8D8D8)
        y = y + 14
    end
end
-- ================================================================================

local n=0
event.onframestart(function()
    n=n+1
    update_overlay_toggle()
    if n % 30 == 0 then reload_checked() end   -- refresh server-authoritative opened list ~2x/sec
    draw_overlay()                             -- redraw every frame (gui layer clears each frame)
    -- DeathLink RECEIVE applied here (per-frame) so it's dense and brief. First ~20 frames
    -- write the full commit cluster to start the death; the rest just hold HP=0 silently so
    -- the game's death animation can play out WITHOUT being reset (which caused the repeated
    -- hit sound and the frozen squish). When not in a level, it waits for the next stage.
    if kill_frames > 0 then
        local base=kirby_base()
        if base then
            wu32(base+HP_OFF, 0)
            if kill_frames > 60 then
                for _,p in ipairs(DEATH_FLAGS) do wu32(base+p[1], p[2]) end
            end
            kill_frames = kill_frames - 1
        end
    end
    if n%POLL~=0 then return end
    tick()
end, "kss_connector")

local okc=pcall(rb,COLL)
if okc then
    local f=read_coll(); local c=0
    for i=0,NUM_BITS-1 do if bit_set(f,i) then c=c+1 end end
    print("KSS connector ready (v29). "..c.." chest locations already collected.")
    msg("<(^-^<) Kirby connector ready! let's find some treasure!")
else print("ERROR reading collectibles field"); msg("x_x  connector: RAM error") end
