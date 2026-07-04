-- KirbySqueakSquad_Connector.lua  (v44 - Meta Knight badge item-locked; Gamble Galaxy no longer free)
--
--   New in v44:
--   * GAMBLE GALAXY ITEM-LOCK. The Meta Knight badge (bit 68) was in NO_CLEAR, so beating Meta Knight
--     left the vanilla badge set and the game opened Gamble Galaxy from it + your star seals -- WITHOUT
--     ever receiving the Meta Knight Badge from AP (out of logic; regions.py gates Gamble Galaxy behind
--     the received badge). Bit 68 now masks like any other badge: beating Meta Knight sends the check
--     then clears the bit, and Gamble Galaxy is wired into WORLD_GATE ([7]=68) so its unlock is held off
--     until you RECEIVE the Meta Knight Badge (which sets bit 68 on the map via collection_bits, like
--     the seals). Only Dark Nebula (69, the final boss, gates nothing) stays in NO_CLEAR.
--
-- KirbySqueakSquad_Connector.lua  (v43 - Vocal Volcano EX/boss substage off-by-one fixed)
--
--   New in v43:
--   * VOCAL VOLCANO EX/BOSS KEYING. Vocal Volcano (world 5) has only 4 normal stages, so the game
--     reports its EX at substage 4 and its boss at substage 5 -- one lower than every other world.
--     CHEST_BY_STAGE keyed them at 45/46 (the uniform EX=5/boss=6 assumption), so entering the EX
--     stage looked up empty key 44 and never active-cleared the Animal Copy Palette (bit 89): a
--     received copy masked its own chest and the check never fired. Moved EX -> key 44 and boss -> 45,
--     and taught stage_label (via EX_SUBSTAGE) that VV's EX is substage 4, so the boss no longer shows
--     as "5-EX" in the overlay.
--
-- KirbySqueakSquad_Connector.lua  (v42 - Nature Notch world-gate lock-out fixed; release v0.0.8)
--
--   New in v42:
--   * NATURE NOTCH LOCK-OUT FIX. enforce_world_gates no longer clears Nature Notch's world-unlock bit.
--     Beating Dedede force-opens that world and scripts you into 2-1, so the connector was in a tug-of-
--     war with the game over that bit -- which went unstable across a client disconnect and repeated
--     world-select round-trips, flickering 2-2 open and eventually locking you out of 2-1 (which is
--     in-logic). Nature Notch is the one world with a scripted entry, so its real gate is 2-2+, handled
--     by NN_STAGE_GATE holding 2-1's cleared flag off until the King DeDeDe badge arrives. Worlds 3+ are
--     still gated normally at the world-unlock bit.
--
-- KirbySqueakSquad_Connector.lua  (v41 - collection masking fixed at the source; scroll upgrades granted)
--
--   New in v41:
--   * MASKING FIX (checks now fire for items you've already been sent). A received item's collectible
--     bit is no longer left set when its chest loads. maintain_collection ACTIVELY CLEARS the current
--     stage's still-unopened chest bits (WORLD/SUBSTAGE update to the target stage ~73 frames before it
--     loads), so the chest loads openable -- not grayed -- and its open fires the check on the spot.
--     Already-opened chests stay shown, so a received item doesn't vanish from the collection when you
--     open it on its own stage.
--   * SCROLL UPGRADES actually apply in-level now. enforce_upgrade_store() GRANTS the session upgrade
--     bit for any ability whose 2nd Progressive copy you've received (it previously only stripped
--     unearned upgrades), so an AP-sent scroll upgrades the ability and survives level changes/reloads.
--   * TREASURE-BYTE REMAP: 10 mislabeled treasures corrected against the collection-room category order
--     (Orange->79, Parasol Scroll->33, Sleep Scroll->42, Spunky Notes->54, ...). Requires a fresh
--     generation with the matching apworld.
--   * Tracker/overlay caches (kss_opened_cache.txt, kss_checked.txt) are cleared on load, so a previous
--     seed's opened chests don't linger.
--
-- KirbySqueakSquad_Connector.lua  (v37 - Nature Notch 2-2 gate via the 2-1 cleared flag)
--
--   New in v37:
--   * Nature Notch 2-2+ now stay LOCKED until the King DeDeDe badge is received. The post-Dedede
--     push forces you through 2-1, and clearing 2-1 normally unlocks 2-2 -- so, after the 2-1 clear
--     CHECK has been sent (AP still registers it), the connector holds 2-1's *cleared* flag off
--     (bit0 of 0x022560DA) while the badge isn't owned, which keeps 2-2 from unlocking. When the
--     badge arrives it restores the flag (only if you actually cleared 2-1) so progression resumes.
--     This closes the world-1 hole that the v34 boss-beaten mask left open (that mask is scoped to
--     worlds >= 2 to avoid disturbing the scripted 2-1 push). Toggle: NN_STAGE_GATE.
--     NOTE: this is the first time we write a stage-clear byte -- worth a save+reload check that the
--     2-1/2-2 state and overall save stay clean.
--
-- KirbySqueakSquad_Connector.lua  (v36 - title-cased item names, named copy palettes, starting spray)
--
--   New in v36:
--   * Item names are Title Cased everywhere (NAME_TO_BIT + the overlay labels), matching the apworld
--     rename (e.g. "Fire scroll" -> "Fire Scroll", "Vitality half_1" -> "Vitality Half 1"). The five
--     generic "Copy palette N" items are now named: Check / Pastel / Industrial / Animal / Machine
--     Copy Palette. (NAME_TO_BIT, items.py, kss_chest_data.py and the overlay all stay in lockstep.)
--   * Random Starting Color (the live cosmetic tint) is GONE. The apworld's new Starting Spray option
--     grants a real spray as starting inventory, so the connector just receives it like any other
--     collectible and sets its bit -- no live render-byte write, no kss_color.txt. The player owns the
--     spray (shows in collection, applies from the spray menu) and no location check is consumed.
--
-- KirbySqueakSquad_Connector.lua  (v35 - persistent overlay cache; AP link moves to the Lua console)
--
--   New in v35:
--   * The always-on in-game "AP client: LINKED..." indicator is GONE. Instead the connector prints
--     ">>> KSS: Archipelago client connected (bridge live)." to the Lua console once, the first time
--     it sees the client's bridge file. Keeps the game screen clean.
--   * The opened-chest overlay now PERSISTS across sessions on its own. The connector keeps its own
--     kss_opened_cache.txt (union of chests it detected + the client's authoritative list) and
--     reloads it on launch, so the overlay is correct after a Lua reload / BizHawk restart and even
--     before the AP client reconnects (or with no client running). It only ever gains bits.
--
-- KirbySqueakSquad_Connector.lua  (v34 - world gating: post-boss leak closed via boss-beaten mask)
--
--   New in v34:
--   * POST-BOSS LEAK CLOSED. v33's gate cleared 0x02256094 (stages-playable), which controls the
--     world-map nodes a NORMAL map re-init builds -- but right after a boss the game opens the next
--     world straight from the boss-beaten flag 0x022560D6 instead, so the new world stayed walkable/
--     enterable until a "round trip" (enter another world and come back) forced a rebuild. Confirmed
--     by capture: 0x94 bit2 was already clear yet Cushy Cloud was fully playable post-boss.
--     enforce_world_gates() now also CLEARS 0x022560D6 bit (W-1) for any gated world W>=2 (the bit of
--     the boss that opens W), so the post-boss map-init locks the world immediately -- no round trip.
--     Verified in-game: masking the Mrs Moley bit locked Cushy the instant she fell.
--     World 1's boss bit (bit0) is deliberately left alone so the scripted post-Dedede 2-1 push still
--     works; Nature Notch 2-1 stays in-logic in regions.py. Cosmetic only: a gated world's prior boss
--     node may show un-beaten while you lack the badge.
--
--   New in v33:
--   * IN-GAME WORLD GATING. Each world's stages stay locked until you've RECEIVED the boss badge
--     from the previous world (the linear chain in regions.py): Nature Notch <- King DeDeDe badge,
--     Cushy Cloud <- Mrs Moley, Jam Jungle <- Mecha-Kracko, and so on (worlds 1-6 via badges 62-67).
--     Lever is bit W of 0x02256094 (the "stages playable" bitfield; bit2 = Cushy Cloud confirmed by
--     capture). The game writes that bit only once (when you beat the prior boss) and never re-asserts
--     it, so enforce_world_gates() drives it both ways: it SETS the bit while you hold the gating
--     badge and CLEARS it while you don't. You can still slide the world-map cursor onto a locked
--     world, but entering bounces you back at its stage-select. Set WORLD_GATING=false to disable.
--     NOTE: beating King DeDeDe scripts you straight into 2-1, bypassing this bit, so Nature Notch's
--     FIRST stage must be modeled as in-logic in regions.py; the gate then catches everything from
--     2-2 on. World 0 (Prism Plains) is never gated; Secret Sea stays on the seal system.
--     TEST: with a badge un-received, confirm that world's stages bounce you; once the badge is
--     received, confirm the world opens normally. Capture one more boss->unlock (e.g. world 2->3) to
--     confirm bit3 follows the bit=world pattern before trusting the upper worlds.
--
--   New in v32:
--   * SCROLL-UPGRADE LEAK FIXED. The game keeps a session-only "this ability is upgraded" bitfield
--     in working RAM at 0x022618AC (bit = scroll collectible bit - 28). Grabbing a scroll set that
--     bit and granted you the EX upgrade for the whole session -- even with the chest bit masked
--     and no 2nd Progressive copy received. It's not in the save (gone on reload), but a single
--     long session kept the unearned upgrade the entire time. enforce_upgrade_store() now keeps the
--     bit cleared for any ability you haven't received the 2nd copy of, in safe states only (in a
--     stage / on the world map, never during the 0x1B/0x1C chest-get transition). Authorized
--     upgrades (2nd copy received -> chest bit derived into the store at load) are left untouched.
--     RAM map credit: bitfield base + per-ability bits pinned via the focused upgrade-watch capture.
--
--   New in v31:
--   * KEYS / STAR SEALS no longer AUTO-CLAIM. When COLLECTION_ON_RECEIVE is on they ride the same
--     collection-timing as cosmetics: held SET out of a stage (so the game still sees them on the
--     world map to open EX gates / Secret Sea) and CLEARED in a stage (so their chest stays
--     openable). That means YOU open the key/seal chest to send its check, instead of it being
--     auto-sent on receive -- so the location tracker can be marked off normally. Set
--     COLLECTION_ON_RECEIVE=false to restore the v30 auto-claim behavior.
--     TEST after updating: confirm EX stages and Secret Sea still unlock from RECEIVING the
--     key/seal (the gate is read on the map, where the bit is held set) -- if one doesn't open,
--     tell me and we'll capture exactly when the game reads it.
--   * Boss badges stay as they were (collection-managed for now); proper badge gating + display is
--     part of the world-gating work.
--
--   New in v30:
--   * Collection-on-receive (no patch) -- see below.
--
-- KirbySqueakSquad_Connector.lua  (v30 - collection-on-receive [no patch]; overlay + overflow fix kept)
--
--   New in v30:
--   * COLLECTION ON RECEIVE (no ROM patch). A received collectible now appears in the in-game
--     collection as soon as you receive it, not only after you open its chest. The collectible bit
--     doubles as the chest's opened/gray flag, so we decouple them by timing (proven crash-safe by
--     the KSS_COLLECTION_TEST harness): out of a stage the connector SETS your received collectible
--     bits so the collection screen shows them; in a stage it CLEARS them so the matching chests
--     stay un-gray and openable; on the treasure (chest-open) screen it leaves them alone so masking
--     runs untouched. Vitality (HP-driven), keys/seals (permanently set for EX gates), and badges
--     (NO_CLEAR) keep their existing handling. Toggle with COLLECTION_ON_RECEIVE (set false for the
--     v29 fill-as-you-open behavior).
--
--   New in v29:
--   * In-game opened-chest overlay + client kss_checked.txt feed (see below).
--
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
local CHECKED_FILE = TEMP .. "\\kss_checked.txt"   -- client -> connector: authoritative checked-chest list (for the overlay)
local CACHE_FILE   = TEMP .. "\\kss_opened_cache.txt" -- connector-owned persistent opened-bit cache (survives reloads / no client)
local CONNECTED_FILE = TEMP .. "\\kss_connected.txt"  -- client -> connector: present only while actually connected to the AP server
-- ---- in-game opened-chest overlay (Option B) ----
local OVERLAY_DEFAULT_ON = true    -- is the overlay showing when you launch?
local OVERLAY_TOGGLE_KEY = "T"     -- press this key to show/hide the overlay live.
                                   -- If it clashes with an EmuHawk hotkey, change it (any key
                                   -- name works, e.g. "Y", "Tab", "F8") or unbind it in EmuHawk.
-- ---- collection-on-receive (no-patch) ----
-- When true, a received collectible shows in the in-game COLLECTION as soon as you receive it,
-- instead of only after you open its chest. The collectible bit doubles as the chest's "opened/
-- gray" flag, so we fake the decoupling by timing (validated crash-safe by KSS_COLLECTION_TEST):
--   out of a stage (and not the treasure screen) -> SET received bits  (collection shows them)
--   in a stage                                   -> CLEAR them         (chests stay openable)
-- Set false to fall back to the v29 behavior (collection fills only as you open chests).
local COLLECTION_ON_RECEIVE = true
-- v34 (#4): also show self-sent items on the post-stage CLEAR screen, so you don't have to step out
-- to the map to see them. Normally maintain_collection() skips the 0x1B/0x1C chest-tally states; with
-- this on, it still SETS received-item bits there. Re-enabled: the phantom-check problem is now
-- handled two ways -- prev_set_bit makes display writes invisible to the open-detector, and on the
-- clear screen we skip displaying the CURRENT stage's own chest bits (see maintain_collection), so a
-- chest you're actually opening this clear can't be masked by its display bit. Received items (incl.
-- the one you just earned) show immediately on the clear screen again.
local SHOW_RECEIVED_ON_CLEAR = true
local STATE_ADDR  = 0x02255740                     -- gamestate; 0x2e = Kirby Dead

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
local VITALITY = {[6]=true,[7]=true,[8]=true,[9]=true,[10]=true,[11]=true,[12]=true,[13]=true}
local BASE_MAXHP, HEART_HP = 36, 4

local NAME_TO_BIT = {
    ["Star Seal 1"] = 0,
    ["Star Seal 2"] = 1,
    ["Star Seal 3"] = 2,
    ["Star Seal 4"] = 3,
    ["Star Seal 5"] = 4,
    ["Sound Player"] = 5,
    ["Vitality Half 1"] = 6,
    ["Vitality Half 2"] = 7,
    ["Vitality Half 3"] = 8,
    ["Vitality Half 4"] = 9,
    ["Vitality Half 5"] = 10,
    ["Vitality Half 6"] = 11,
    ["Vitality Half 7"] = 12,
    ["Vitality Half 8"] = 13,
    ["Prism Plains Key"] = 14,
    ["Nature Notch Key"] = 15,
    ["Cushy Cloud Key"] = 16,
    ["Jam Jungle Key"] = 17,
    ["Vocal Volcano Key"] = 18,
    ["Ice Island Key"] = 19,
    ["Secret Sea Key"] = 20,
    ["Ghost Medal 1"] = 21,
    ["Ghost Medal 2"] = 22,
    ["Ghost Medal 3"] = 23,
    ["Ghost Medal 4"] = 24,
    ["Ghost Medal 5"] = 25,
    ["Ghost Medal 6"] = 26,
    ["Ghost Medal 7"] = 27,
    ["Fire Scroll"] = 28,
    ["Ice Scroll"] = 29,
    ["Spark Scroll"] = 30,
    ["Beam Scroll"] = 31,
    ["Tornado Scroll"] = 32,
    ["Enemy Sounds"] = 59,
    ["Hammer Scroll"] = 34,
    ["Cupid Scroll"] = 35,
    ["Cutter Scroll"] = 36,
    ["Laser Scroll"] = 37,
    ["Bomb Scroll"] = 38,
    ["Wheel Scroll"] = 39,
    ["HiJump Scroll"] = 40,
    ["UFO Scroll"] = 41,
    ["Animal Copy Palette"] = 89,
    ["Sword Scroll"] = 43,
    ["Ninja Scroll"] = 44,
    ["Fighter Scroll"] = 45,
    ["Throw Scroll"] = 46,
    ["Magic Scroll"] = 47,
    ["Animal Scroll"] = 48,
    ["Bubble Scroll"] = 49,
    ["Metal Scroll"] = 50,
    ["Party Notes"] = 51,
    ["Beginning Notes"] = 52,
    ["Happy Notes"] = 53,
    ["Graphic Piece 17"] = 117,
    ["Battle Notes"] = 55,
    ["Familiar Notes"] = 56,
    ["Secret Notes"] = 57,
    ["Kirby's Sounds"] = 58,
    ["Parasol Scroll"] = 33,
    ["Graphic Piece 13"] = 116,
    ["Secret Sounds"] = 61,
    ["King DeDeDe Badge"] = 62,
    ["Mrs Moley Badge"] = 63,
    ["Mecha-Kracko Badge"] = 64,
    ["Yadgaine Badge"] = 65,
    ["Bohboh Badge"] = 66,
    ["Daroach Badge"] = 67,
    ["Meta Knight Badge"] = 68,
    ["Dark Nebula Badge"] = 69,
    ["Yellow"] = 70,
    ["Red"] = 71,
    ["Green"] = 72,
    ["Snow"] = 73,
    ["Carbon"] = 74,
    ["Ocean"] = 75,
    ["Sapphire"] = 76,
    ["Grape"] = 77,
    ["Emerald"] = 78,
    ["Graphic Piece 8"] = 101,
    ["Chocolate"] = 80,
    ["Cherry"] = 81,
    ["Chalk"] = 82,
    ["Shadow"] = 83,
    ["Ivory"] = 84,
    ["Citrus"] = 85,
    ["White"] = 86,
    ["Lavender"] = 87,
    ["Check Copy Palette"] = 88,
    ["Sleep Scroll"] = 42,
    ["Industrial Copy Palette"] = 90,
    ["Machine Copy Palette"] = 91,
    ["Pastel Copy Palette"] = 92,
    ["Secret Map 1"] = 93,
    ["Secret Map 2"] = 94,
    ["Secret Map 3"] = 95,
    ["Secret Map 4"] = 96,
    ["Secret Map 5"] = 97,
    ["Secret Map 6"] = 98,
    ["Secret Map 7"] = 99,
    ["Graphic Piece 1"] = 100,
    ["Spunky Notes"] = 54,
    ["Graphic Piece 15"] = 102,
    ["Graphic Piece 9"] = 103,
    ["Graphic Piece 18"] = 104,
    ["Graphic Piece 12"] = 105,
    ["Graphic Piece 7"] = 106,
    ["Graphic Piece 4"] = 107,
    ["Graphic Piece 16"] = 108,
    ["Graphic Piece 5"] = 109,
    ["Graphic Piece 14"] = 110,
    ["Graphic Piece 3"] = 111,
    ["Graphic Piece 19"] = 112,
    ["Graphic Piece 2"] = 113,
    ["Graphic Piece 6"] = 114,
    ["Graphic Piece 11"] = 115,
    ["Sound Effects"] = 60,
    ["Orange"] = 79,
    ["Graphic Piece 10"] = 118
}
local KEY_SEAL = {
    ["Cushy Cloud Key"] = true,
    ["Ice Island Key"] = true,
    ["Jam Jungle Key"] = true,
    ["Nature Notch Key"] = true,
    ["Prism Plains Key"] = true,
    ["Secret Sea Key"] = true,
    ["Star Seal 1"] = true,
    ["Star Seal 2"] = true,
    ["Star Seal 3"] = true,
    ["Star Seal 4"] = true,
    ["Star Seal 5"] = true,
    ["Vocal Volcano Key"] = true
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
    ["Parasol"] = {val=0x06, scroll=33, acq=21},
    ["Sleep"]   = {val=0x0E, scroll=42, acq=22},
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
NO_CLEAR[69]=true   -- only Dark Nebula now (final Gamble Galaxy boss; nothing gates on it). Meta Knight
-- (68) was removed -- leaving it set let beating Meta Knight open Gamble Galaxy WITHOUT receiving the
-- badge; it now masks normally and Gamble Galaxy opens only on receiving it (bit 68 held on the map by
-- collection_bits, exactly like the star seals). The
-- world-1-6 gating badges (62-67) are NO LONGER exempt: leaving them set let an in-game boss kill
-- light the badge bit permanently, which (a) showed the badge in the collection without receiving it
-- and (b) is the bit the game derives the next world's unlock from -- the root cause of the gate
-- leaking. They now mask like any collectible (check fires first, then the bit clears), and a
-- RECEIVED badge re-shows via collection_bits out of a stage.

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
    local lname = name:lower()
    if lname:sub(-6)=="scroll" then
        return "(*v*) Scroll get!  "..name.." -- ability unlocked!"
    elseif KEY_SEAL[name] then
        return "(>'-')> Key get!  "..name
    elseif FILLER[name] and FILLER[name].life then
        return "p(^_^)q 1-UP!  one more try in your pocket!"
    elseif FILLER[name] and FILLER[name].heal then
        return "<(^o^)> Yum!  "..name.." restored some health!"
    elseif lname:find("badge") then
        return "(^o^)b Badge get!  "..name
    elseif lname:find("seal") then
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
-- AP client link indicator: confirms the connector is actually talking to the Archipelago client.
local client_seen = false      -- true once the client's bridge files appear / items start arriving
local n_items_rx, n_checks_tx = 0, 0
local function append_check(idx) n_checks_tx=n_checks_tx+1; local f=io.open(CHECKS_FILE,"a"); if f then f:write(tostring(idx).."\n"); f:close() end end

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
    f:close(); items_read=items_read+#r; n_items_rx=n_items_rx+#r; return r
end

-- Print the "connected" notice only when the client signals a real AP-server connection
-- (it writes kss_connected.txt on the Connected package and clears it at launch). Watching the
-- items file was premature -- that file can linger from a prior session before you've connected.
local function poll_connected()
    if client_seen then return end
    local f=io.open(CONNECTED_FILE,"r"); if not f then return end
    f:close(); client_seen=true
    print(">>> KSS: connected to the Archipelago server.")
end

do local cf=io.open(CHECKS_FILE,"w"); if cf then cf:close() end
   local gf=io.open(GOAL_FILE,"w");   if gf then gf:close() end end
-- Drop any leftover connection flag on load: only a running, AP-connected client rewrites it
-- (every ~1s), so a stale flag from a closed/disconnected client can't falsely report "connected".
os.remove(CONNECTED_FILE)
-- Drop the persistent overlay/tracker files on load too, so a previous seed's opened chests don't
-- linger in the tracker. The connected client rewrites kss_checked.txt from the server (authoritative
-- for THIS seed) within ~1-2s, and opened chests this session repopulate the cache as you go.
os.remove(CACHE_FILE)
os.remove(CHECKED_FILE)

local prev = read_coll()
local prev_gate = gate_sum()
local prev_sc = {}
-- Start from 0 so that on the first tick, every CURRENTLY-set stage-clear bit is
-- detected and sent. This makes stages cleared in a previous session (e.g. a boss
-- like Daroach beaten before a connector reload) re-register; checks are deduped
-- by the client/server, so re-sending is harmless.
for w=0,SC_WORLDS-1 do prev_sc[w]=0 end
local nn1_was_cleared = false   -- has Nature Notch 2-1 been cleared this session (for the stage gate)
local goal_sent = false
-- DeathLink state
local death_out_n = 0
local prev_state = rb(STATE_ADDR)
local last_death_in = ""
do local df=io.open(DEATH_IN,"r"); if df then last_death_in=(df:read("*l") or ""); df:close() end end
local kill_frames = 0       -- per-frame death-commit application remaining (dense, short)
local suppress_frames = 0   -- ticks to not echo our own forced death
-- Vitality health: how many halves received -> drives max HP
local vit_received = 0
local vit_heal = false
os.remove(DEATH_OUT)
local received_prog = {}   -- ability name -> count of Progressive copies received (0/1/2)
local acquired_sent = {}   -- ability name -> first-use check already sent
local received_bits = {}
-- normal collectibles we've received and now manage for the in-game collection display.
-- (Excludes vitality [HP-driven, never set], keys/seals [permanently set via grant_and_claim],
-- and badges [NO_CLEAR].) maintain_collection() sets these out of a stage / clears them in one.
local collection_bits = {}
local TREASURE_STATES = { [0x1B]=true, [0x1C]=true }   -- post-stage chest-open screens: leave bits alone here
local opened_bits = {}
-- Persistent overlay cache (v35): a connector-OWNED record of every chest bit we've ever seen
-- opened -- whether we detected it ourselves (opened_bits) or the client fed it (kss_checked.txt).
-- Written to kss_opened_cache.txt and reloaded on launch, so the in-game overlay survives a Lua
-- reload / BizHawk restart and shows correctly even before the AP client reconnects (or with no
-- client at all). It only ever gains bits, never loses them.
local opened_cache = {}
local function save_cache()
    local f = io.open(CACHE_FILE, "w"); if not f then return end
    local ks = {}; for b,_ in pairs(opened_cache) do ks[#ks+1] = b end
    table.sort(ks)
    for _,b in ipairs(ks) do f:write(tostring(b).."\n") end
    f:close()
end
local function cache_add(bit)
    if not opened_cache[bit] then opened_cache[bit] = true; save_cache() end
end
do  -- load the cache once at launch
    local f = io.open(CACHE_FILE, "r")
    if f then
        for line in f:lines() do local b = tonumber(line); if b then opened_cache[b] = true end end
        f:close()
    end
end
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

-- Forward declaration: returns a set {bit=true} of the chests in the stage currently being cleared.
-- Defined after CHEST_BY_STAGE (below); current stage's chest bits, skipped on the clear screen so
-- this-stage opens stay detectable while other received items display.
local current_stage_chest_bits
local is_opened   -- forward declaration; defined after the opened/checked/cache tables (below)

-- Collection-on-receive timing: hold received collectibles' bits SET while out of a stage so the
-- collection screen shows them, and CLEAR while in a stage so their chests don't gray. Called at the
-- END of tick(), after chest-open detection.
local function maintain_collection()
    if not COLLECTION_ON_RECEIVE then return end
    if kirby_base() then
        for b in pairs(collection_bits) do clear_bit(b) end
    elseif SHOW_RECEIVED_ON_CLEAR or not TREASURE_STATES[rb(STATE_ADDR)] then
        -- Out of a stage: show received items in the in-game collection -- EXCEPT the chests of the stage
        -- WORLD/SUBSTAGE points at, which we actively CLEAR. Picking a stage updates those addresses to the
        -- target ~73 frames before it loads (and the stage renders its chests from these bits during the
        -- same 0x1B select/load state), so merely skipping them isn't enough: a bit set earlier stays set
        -- and the chest loads grayed/masked. Clearing the target stage's bits here guarantees they're clear
        -- when it renders -> the chest for an already-received item loads openable and its open fires a check.
        -- Everything else still displays, and keys/seals stay set on the map to drive the EX/Secret Sea gates.
        -- prev_set_bit keeps the bits we DO set from being misread as opens; the cleared ones re-sync via the
        -- detection loop's prev=cur, so a later real open still reads as a fresh flip.
        local skip = current_stage_chest_bits and current_stage_chest_bits() or nil
        for b in pairs(collection_bits) do
            -- Active-clear only the current stage's STILL-UNOPENED chests -- those are the ones that must
            -- load openable. A chest you've already opened here is checked, so there's no open left to
            -- mask; keep it shown, so a received item doesn't vanish off the collection the moment you
            -- open its chest while you're still standing on that stage.
            if skip and skip[b] and not is_opened(b) then clear_bit(b)
            else set_bit(b); prev_set_bit(b) end
        end
    end
end

-- Scroll-upgrade leak fix: the game keeps a SESSION-ONLY "this ability is upgraded" bitfield in
-- working RAM at UPGRADE_STORE, indexed by (scroll collectible bit - 28): byte = UPGRADE_STORE +
-- idx//8, bit idx%8 (verified on Fire/Beam/Cutter/Wheel/Animal -- all land on a constant offset of
-- 28). Grabbing a scroll sets its bit (during the chest-get white transition) and hands you the EX
-- upgrade for the WHOLE session, even though the chest bit is masked and you were never sent the
-- 2nd Progressive copy. It's working RAM, not in the save, so it vanishes on reload -- but a single
-- long session keeps the unearned upgrade the entire time, which is the common way people play.
-- Authorized upgrades come from the saved chest bit being derived into this store at LOAD, so for
-- any ability whose 2nd copy you HAVE received we leave its bit alone. For every other ability we
-- keep its store bit cleared -- but ONLY in a safe state (in a stage, or on the world map), NEVER
-- during the 0x1B/0x1C chest-get transition, where touching ability state desyncs the get-sequence
-- and hangs the white screen (the same trap the ability watchdog avoids).
local UPGRADE_STORE = 0x022618AC
local function enforce_upgrade_store()
    local st = rb(STATE_ADDR)
    if TREASURE_STATES[st] then return end                 -- never during the chest-get transition
    if not (kirby_base() or st == 0x05) then return end     -- only in a stage or on the world map
    for name, info in pairs(ABILITY) do
        local idx = info.scroll - 28
        local a = UPGRADE_STORE + math.floor(idx/8)
        local m = 2^(idx%8)
        local c = rb(a)
        local set = (math.floor(c/m)%2) == 1
        if (received_prog[name] or 0) >= 2 then
            if not set then wb(a, c+m) end   -- GRANT: 2nd copy received -> keep the upgrade active in-level
        else
            if set then wb(a, c-m) end        -- CLEAR: unearned (native scroll grab) -> strip it
        end
    end
end

-- World gating (v34): physically lock each world's stages until its gating boss badge is RECEIVED,
-- matching the linear badge chain in regions.py. Two levers, because the game decides "world W is
-- enterable" in two different places:
--   * 0x02256094 (WORLD_UNLOCK), bit W = world W playable. A NORMAL world-map (re)init derives the
--     walkable nodes from this. We SET bit W while you hold world W's badge, CLEAR it while you
--     don't. (Confirmed bit2 = Cushy Cloud. The game writes it once on boss-clear and never
--     re-asserts, so we drive it both ways.)
--   * 0x022560D6 (BOSS_BEATEN), bit W = world W's boss beaten. The POST-BOSS map-init opens the
--     NEXT world straight from THIS flag, not from 0x94 -- that's the "world stays enterable until a
--     round trip" leak. So for a gated world W (badge not received) we also CLEAR the bit of the
--     boss that opens it (world W-1's boss = bit W-1), so the post-boss init locks it immediately.
--     (Confirmed in-game: masking bit1 locked Cushy the instant Mrs Moley fell -- no round trip.)
-- World 0 (Prism Plains) is the start, never gated. World 1's boss bit (bit0) is left ALONE: the
-- post-Dedede push into Nature Notch 2-1 is intentional/scripted (2-1 is modeled in-logic in
-- regions.py), so the boss-beaten clear is scoped to worlds >= 2. Secret Sea (world 6) is gated by the
-- Daroach badge; Gamble Galaxy (world 7) is gated by the Meta Knight badge (plus the seals the game
-- reads on the map). Set WORLD_GATING=false to disable the whole feature.
local WORLD_UNLOCK = 0x02256094
local BOSS_BEATEN  = 0x022560D6
local WORLD_GATING = true
-- Nature Notch stage gate: the post-Dedede push forces 2-1 to be played before the King DeDeDe
-- badge is owned, and clearing 2-1 normally unlocks 2-2. While the badge isn't received we hold
-- 2-1's *cleared* flag off (after its AP check has gone out) so 2-2+ stay locked; once the badge
-- arrives we restore it so progression resumes. Set false to disable just this.
local NN_STAGE_GATE = true
local WORLD_GATE = {          -- world bit (0-indexed) -> gating badge collectible bit (prev boss)
    [1] = 62,   -- Nature Notch   <- King DeDeDe badge
    [2] = 63,   -- Cushy Cloud    <- Mrs Moley badge
    [3] = 64,   -- Jam Jungle     <- Mecha-Kracko badge
    [4] = 65,   -- Vocal Volcano  <- Yadgaine badge
    [5] = 66,   -- world 5        <- Bohboh badge
    [6] = 67,   -- world 6        <- Daroach badge
    [7] = 68,   -- Gamble Galaxy  <- Meta Knight badge (Secret Sea boss). Gamble Galaxy also needs the
                -- star seals in-game (held on the map via collection_bits), but its badge gate lives
                -- here so beating Meta Knight can't open it without RECEIVING the Meta Knight Badge.
}
local function enforce_world_gates()
    if not WORLD_GATING then return end
    local c = rb(WORLD_UNLOCK); local nc = c
    local b = rb(BOSS_BEATEN);  local nb = b
    for wbit, badge in pairs(WORLD_GATE) do
        local m = 2^wbit
        if received_bits[badge] then
            if (math.floor(nc/m)%2) == 0 then nc = nc + m end       -- authorized: ensure 0x94 bit SET
        elseif wbit >= 2 then
            -- Gate worlds 2+ at the world-unlock bit. Nature Notch (wbit 1) is deliberately NOT locked
            -- here: beating Dedede scripts you into 2-1 and the game force-opens the world, and 2-1 is
            -- in-logic -- clearing the world bit fights that and can strand you out of 2-1 on the map
            -- (the disconnect / world-select round-trip lock-out). Nature Notch's real gate is 2-2+,
            -- handled by NN_STAGE_GATE holding 2-1's cleared flag off until the King DeDeDe badge arrives.
            if (math.floor(nc/m)%2) == 1 then nc = nc - m end       -- gated: ensure 0x94 bit CLEARED
            local bm = 2^(wbit-1)                                   -- world W opened by world W-1's boss
            if (math.floor(nb/bm)%2) == 1 then nb = nb - bm end     -- also stop the boss-beaten force-open
        end
    end
    if nc ~= c then wb(WORLD_UNLOCK, nc) end
    if nb ~= b then wb(BOSS_BEATEN, nb) end
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

    -- incoming items
    poll_connected()
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
                elseif KEY_SEAL[name] and not COLLECTION_ON_RECEIVE then grant_and_claim(b)
                elseif COLLECTION_ON_RECEIVE then collection_bits[b]=true
                    -- includes keys/seals: held SET out of a stage, so the game still sees them on
                    -- the world map to open EX gates / Secret Sea, but CLEARED in a stage so their
                    -- chest stays openable -> no auto-claim, so the tracker can be marked off normally.
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
        -- A genuine chest open is a fresh bit flip (connector-set bits are all prev_set_bit-synced,
        -- so they never read as flips here). gate_changed alone missed opens that didn't coincide with
        -- a gate-range byte change -- e.g. opening the chest for a treasure you'd already been sent:
        -- the bit was cleared in-stage so the chest wasn't grayed, you opened it, the flip was real, but
        -- no check fired. Now an unchecked location fires on any fresh flip; already-checked ones still
        -- require gate_changed so replays don't spam duplicates.
        if bit_set(cur,i) and not bit_set(prev,i) and (gate_changed or not is_opened(i)) then
            append_check(i); opened_bits[i]=true; cache_add(i)
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
            elseif (not COLLECTION_ON_RECEIVE) and received_bits[i] then
                -- legacy behavior: keep the bit so opening the chest reveals it in the collection.
                -- With COLLECTION_ON_RECEIVE on, received chests instead mask normally (below) and
                -- the collectible is shown by maintain_collection() while you're out of a stage.
            elseif NO_CLEAR[i] then
                -- Dark Nebula badge (69): the final Gamble Galaxy boss, gates nothing after it, so its
                -- vanilla badge is left intact. Meta Knight (68) and the gating badges 62-67 are no
                -- longer here -- they fall through to the normal mask, so an unearned boss kill sends
                -- the check then clears the bit (Gamble Galaxy then opens only on RECEIVING badge 68).
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
                    if w==1 and bi==0 then nn1_was_cleared=true end   -- Nature Notch 2-1
                end
            end
            prev_sc[w]=v
        end
    end

    -- Nature Notch stage gate (runs AFTER the loop above, so 2-1's clear check has already been
    -- sent this tick). While the King DeDeDe badge isn't received, hold 2-1's cleared flag OFF so
    -- 2-2+ stay locked despite the forced 2-1 push; once the badge is received, restore the flag
    -- (only if 2-1 was actually cleared) so the game unlocks 2-2 again. Bit0 of SC_BASE+2 = 2-1.
    if NN_STAGE_GATE then
        local a = SC_BASE + 2
        local v = rb(a)
        local has = byte_bit(v, 0)
        if not received_bits[62] then
            if has then wb(a, v - 1); prev_sc[1] = v - 1 end          -- gate: keep 2-1 un-cleared
        elseif nn1_was_cleared and not has then
            wb(a, v + 1); prev_sc[1] = v + 1                          -- badge in hand: restore 2-1
        end
    end

    enforce_upgrade_store()  -- clear unearned scroll upgrades (session-only working-RAM bitfield)
    maintain_collection()   -- collection-on-receive timing (runs after chest-open detection)
end

-- ===================== IN-GAME OPENED-CHEST OVERLAY (Option B) =====================
-- For the stage you're currently on, lists which of its chests you've already opened
-- (sent as AP checks). The game's own level-map icons can't show this -- they're driven
-- by the per-stage counter we decrement to stop the re-collect overflow -- so this draws
-- an independent checklist instead. "Opened" is the union of: chests THIS session has
-- sent, plus the authoritative list the client writes to kss_checked.txt from the server
-- (so it survives reloads and shows chests opened before the overlay existed). The stage
-- key is world*10+substage -- the same layout as the counter -- and substage = in-game
-- stage-1 (so 1-5 -> 0-4, EX -> 5, Boss -> 6). Exception: Vocal Volcano (world 5) has only 4
-- normal stages, so its EX is substage 4 and its boss substage 5. Press OVERLAY_TOGGLE_KEY to show/hide.

local CHEST_BY_STAGE = {
  [1] = { {52,"Beginning Notes"} },
  [2] = { {5,"Sound Player"}, {28,"Fire Scroll"} },
  [3] = { {14,"Prism Plains Key"}, {72,"Green"}, {100,"Graphic Piece 1"} },
  [4] = { {88,"Check Copy Palette"} },
  [5] = { {6,"Vitality Half 1"}, {113,"Graphic Piece 2"} },
  [6] = { {62,"King DeDeDe Badge"} },
  [10] = { {0,"Star Seal 1"}, {48,"Animal Scroll"}, {58,"Kirby's Sounds"} },
  [11] = { {21,"Ghost Medal 1"}, {85,"Citrus"} },
  [12] = { {39,"Wheel Scroll"}, {92,"Pastel Copy Palette"}, {111,"Graphic Piece 3"} },
  [13] = { {36,"Cutter Scroll"} },
  [14] = { {15,"Nature Notch Key"}, {31,"Beam Scroll"}, {107,"Graphic Piece 4"} },
  [15] = { {7,"Vitality Half 2"}, {93,"Secret Map 1"}, {109,"Graphic Piece 5"} },
  [16] = { {63,"Mrs Moley Badge"} },
  [20] = { {30,"Spark Scroll"}, {77,"Grape"}, {114,"Graphic Piece 6"} },
  [21] = { {1,"Star Seal 2"}, {56,"Familiar Notes"} },
  [22] = { {22,"Ghost Medal 2"}, {94,"Secret Map 2"}, {106,"Graphic Piece 7"} },
  [23] = { {16,"Cushy Cloud Key"}, {40,"HiJump Scroll"}, {87,"Lavender"} },
  [24] = { {32,"Tornado Scroll"} },
  [25] = { {8,"Vitality Half 3"}, {79,"Orange"}, {117,"Graphic Piece 17"} },
  [26] = { {64,"Mecha-Kracko Badge"} },
  [30] = { {49,"Bubble Scroll"}, {83,"Shadow"}, {103,"Graphic Piece 9"} },
  [31] = { {2,"Star Seal 3"}, {70,"Yellow"} },
  [32] = { {9,"Vitality Half 4"}, {50,"Metal Scroll"}, {90,"Industrial Copy Palette"} },
  [33] = { {17,"Jam Jungle Key"}, {95,"Secret Map 3"}, {118,"Graphic Piece 10"} },
  [34] = { {37,"Laser Scroll"} },
  [35] = { {23,"Ghost Medal 3"}, {29,"Ice Scroll"}, {51,"Party Notes"} },
  [36] = { {65,"Yadgaine Badge"} },
  [40] = { {3,"Star Seal 4"}, {33,"Parasol Scroll"}, {59,"Enemy Sounds"} },
  [41] = { {34,"Hammer Scroll"}, {84,"Ivory"}, {115,"Graphic Piece 11"} },
  [42] = { {10,"Vitality Half 5"}, {44,"Ninja Scroll"}, {105,"Graphic Piece 12"} },
  [43] = { {18,"Vocal Volcano Key"}, {71,"Red"}, {96,"Secret Map 4"} },
  -- Vocal Volcano has only 4 normal stages, so its EX/boss sit one substage LOWER than every other
  -- world: the game reports EX at substage 4 (key 44) and the boss at substage 5 (key 45), not 45/46.
  -- Keying them at 45/46 (the uniform assumption) left the EX active-clear looking up empty key 44,
  -- so a received Animal Copy Palette masked its own chest and no check fired.
  [44] = { {24,"Ghost Medal 4"}, {42,"Sleep Scroll"}, {89,"Animal Copy Palette"} },
  [45] = { {66,"Bohboh Badge"} },
  [50] = { {43,"Sword Scroll"}, {60,"Sound Effects"}, {116,"Graphic Piece 13"} },
  [51] = { {4,"Star Seal 5"}, {73,"Snow"} },
  [52] = { {11,"Vitality Half 6"}, {45,"Fighter Scroll"}, {110,"Graphic Piece 14"} },
  [53] = { {19,"Ice Island Key"}, {53,"Happy Notes"}, {82,"Chalk"} },
  [54] = { {35,"Cupid Scroll"}, {91,"Machine Copy Palette"}, {102,"Graphic Piece 15"} },
  [55] = { {25,"Ghost Medal 5"}, {81,"Cherry"}, {97,"Secret Map 5"} },
  [56] = { {67,"Daroach Badge"} },
  [60] = { {46,"Throw Scroll"}, {61,"Secret Sounds"}, {86,"White"} },
  [61] = { {26,"Ghost Medal 6"}, {76,"Sapphire"}, {108,"Graphic Piece 16"} },
  [62] = { {38,"Bomb Scroll"}, {54,"Spunky Notes"}, {101,"Graphic Piece 8"} },
  [63] = { {20,"Secret Sea Key"}, {47,"Magic Scroll"}, {75,"Ocean"} },
  [64] = { {80,"Chocolate"} },
  [65] = { {12,"Vitality Half 7"}, {98,"Secret Map 6"}, {104,"Graphic Piece 18"} },
  [66] = { {68,"Meta Knight Badge"} },
  [70] = { {41,"UFO Scroll"}, {55,"Battle Notes"}, {112,"Graphic Piece 19"} },
  [71] = { {27,"Ghost Medal 7"}, {78,"Emerald"}, {99,"Secret Map 7"} },
  [72] = { {13,"Vitality Half 8"}, {57,"Secret Notes"}, {74,"Carbon"} },
  [76] = { {69,"Dark Nebula Badge"} },
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
    -- fold the server's authoritative opened list into the persistent cache, so those bits stick
    -- even if the client later disconnects or kss_checked.txt is cleared
    local changed = false
    for b,_ in pairs(t) do if not opened_cache[b] then opened_cache[b] = true; changed = true end end
    if changed then save_cache() end
end

function is_opened(bit)
    return (opened_bits[bit] or checked_file[bit] or opened_cache[bit]) and true or false
end

-- Most worlds have 5 normal stages (EX at substage 5, boss at 6). Vocal Volcano (w=4) has only 4,
-- so its EX is at substage 4 and boss at 5. Map any such exceptions here so the overlay labels match.
local EX_SUBSTAGE = { [4] = 4 }   -- world index (0-based) -> substage of that world's EX stage

local function stage_label(w, s)
    local wn = WORLD_NAMES[w+1] or ("World "..(w+1))
    local ex = EX_SUBSTAGE[w] or 5
    local sn
    if s < ex then sn = tostring(s+1)
    elseif s == ex then sn = "EX"
    elseif s == ex + 1 then sn = "Boss"
    else sn = "?" end
    return string.format("%d-%s %s", w+1, sn, wn)
end

-- Assigns the forward-declared local. Set of chest bits in the stage being played/cleared right now,
-- from the same WORLD/SUBSTAGE the overlay uses. Skipped on the clear screen so this-stage opens stay
-- detectable while the clear screen displays the rest.
function current_stage_chest_bits()
    local w, s = ru32(WORLD_ADDR), ru32(SUBSTAGE_ADDR)
    local set = {}
    if w <= 7 and s <= 9 then
        local list = CHEST_BY_STAGE[w*10 + s]
        if list then for _,c in ipairs(list) do set[c[1]] = true end end
    end
    return set
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
            -- Refresh the echo-suppression for as long as we're actually applying the death.
            -- A death received on the map waits here (base invalid) until you enter a stage, by
            -- which point the original 35-tick window has expired -- without this, the applied
            -- death would be re-sent as a fresh DeathLink. Re-arming here keeps it suppressed.
            suppress_frames = 8
            kill_frames = kill_frames - 1
        end
    end
    enforce_world_gates()  -- frame START pass (see the frame-END pass below for why both)
    if n%POLL~=0 then return end
    tick()
end, "kss_connector")

-- World-gate frame-END pass. The game re-derives a world's unlock bit from "prior boss beaten" and
-- re-asserts it MID-frame (confirmed: 0x94 oscillates while 0xD6 says the prior boss is down). A
-- frame-start clear runs before that, so at the frame boundary the bit is sometimes ours, sometimes
-- the game's -- and the world-select latches whatever it sees. Clearing again at frame end, AFTER the
-- game's writes, makes the boundary value reliably ours, so the latch reads a locked world.
event.onframeend(function()
    enforce_world_gates()
end, "kss_worldgate_end")

local okc=pcall(rb,COLL)
if okc then
    local f=read_coll(); local c=0
    for i=0,NUM_BITS-1 do if bit_set(f,i) then c=c+1 end end
    print("KSS connector ready (v44). "..c.." chest locations already collected.")
    msg("<(^-^<) Kirby connector ready! let's find some treasure!")
else print("ERROR reading collectibles field"); msg("x_x  connector: RAM error") end
