Make sure to use the newest release!

Disclaimer: I do not have programming experience and created this Archipelago experience with AI. Please let me know of any issues or suggestions on Discord! Still working to make this sound more human, you'll see some of my annotations as you read.

Disclaimer #2: I am fairly certain this only works on Windows due to the live ram editing.

# Kirby: Squeak Squad — Archipelago

**Release v0.0.8.** The BizHawk connector's Lua console prints its own build number on load (currently `v47`); pair the connector and apworld from this same release.

A multiworld randomizer for Kirby: Squeak Squad (Nintendo DS). Opening chests and
clearing stages send checks; you receive your items from Archipelago. Abilities are
locked behind their Progressive copies, and boss badges gate access to later worlds.

---

## What you need

- **BizHawk** (the emulator), using its **melonDS** core for NDS.
- A **vanilla US** Kirby: Squeak Squad ROM (you supply this). The ROM is **not** patched —
  chests stay vanilla and Archipelago delivers items by name, so a clean ROM is what you want.
- **Archipelago 0.6.7** or newer (the standard installer build).
- The two files from the latest **Release**:
  * `kirby_squeak_squad.apworld`
  * `KirbySqueakSquad_Connector.lua`

Keep the connector and the apworld together as a matched set — use the connector
that ships in the same release as the apworld.

---

## One-time install

1. Drop **`kirby_squeak_squad.apworld`** into Archipelago's `custom_worlds` folder
   (replace any older copy). - You can also just double click it like normal
2. Launch the Archipelago Launcher. You should see a **"Kirby Squeak Squad Client"**
   button with the Squeaker icon. That confirms the apworld is installed.

---

## Generating a game

1. Make a YAML for your slot. The important field is your **slot name** (e.g.
   `name: windstarkirby`) — remember it, you'll type it when connecting.
2. Generate / host the game (locally or on archipelago.gg) like any other AP game.
   Successful generation means the logic held (badge + ability gating included).

> **This release changed the apworld's data** (a corrected treasure map and looser
> chest logic), so **generate a fresh seed** for it — older seeds won't match.

### Optional settings (YAML)

By default the goal is to **beat the game** and no extras are on. To change things,
add any of these to your YAML:

- `goal: chests_and_daroach` — instead of beating the game, your goal becomes
  collecting a number of chests **and** beating Daroach (the Ice Island / stage-6
  boss). Leave it out (or use `goal: beat_game`) for the normal goal.
- `chest_goal_count: 70` — only used by the `chests_and_daroach` goal; how many
  chests are required (1–119, default 70).
- `death_link: true` — **full send and receive.** When on, your deaths are broadcast to
  the multiworld, and an incoming death kills Kirby right where he stands (normal death
  and respawn). A death that arrives while you're on the world map applies the next time
  you enter a stage.
- `ability_checks: true` — adds a check the first time you use each copy ability you
  receive (23 extra locations, balanced with 23 extra filler items).
- `starting_spray: <color>` — own a spray paint from the **start**. It's granted as real
  starting inventory: it shows in your collection and you can apply / re-apply it from the
  spray menu, and **no location check is spent** for it. Use `random` to be granted a random
  spray each seed, or leave it out / use `none` for Kirby's default Pink only. Colors:
  `yellow, red, green, snow, carbon, ocean, sapphire, grape, emerald, orange, chocolate,
  cherry, chalk, shadow, ivory, citrus, white, lavender`. (This replaces the old cosmetic
  Random Starting Color — it grants the real spray, so it sticks and doesn't fight the spray menu.)

When you connect, the client logs which goal is active, so you can confirm it took.

---

## Starting a play session — do these in order

The order matters: get **into the game first**, load the **connector second**,
connect the **client third**. The connector clears stale data on load, so it must
load before you connect the client.

1. **Boot the ROM in BizHawk.** From the title screen choose **Story** and start a
   **new file**. Play through the intro until you are **inside the first stage (1-1)
   and actively controlling Kirby**.
   - Why here: the game's memory (your progress, Kirby's state, the ability value)
     is only fully populated once you're in a stage. Loading the connector at the
     title screen or on the menus can read garbage. Being in 1-1 is the safe point.
   - Do this **before opening any chests**. The connector treats whatever is already
     collected as "already done," so load it while your count is still 0. (1-1 has
     no chests, so it's the natural spot.)

2. **(Only if needed) delete** the `kss_*.txt` files from your `%TEMP%` folder. You
   normally do **not** need to — the connector clears its own bridge, cache, and tracker
   files on load. Only do this after a crash, a force-quit, or when switching to a
   different room/seed and something seems stuck.

3. **Load the connector.** With Kirby standing in that first stage, open BizHawk's
   **Lua Console** (Tools → Lua Console) and load **`KirbySqueakSquad_Connector.lua`**.
   It should print: `KSS connector ready (v42). 0 chest locations already collected.`
   The `0` is your green light. A different number means you're on an old or polluted
   save — start a fresh file and reload.

4. **Open the Kirby Squeak Squad Client** from the Archipelago Launcher.

5. **Connect.** In the client: `/connect <address:port>`, then enter your **slot
   name** when asked. Wait for **"Connected."** Now play normally. - When rejoining, I would advise being in a stage or stage select of a world you have unlocked, being on the world map can be weird

---

## Useful client commands

- **`/received`** — lists every collectible you've received from Archipelago so far.
- **`/kss`** — prints the bridge file paths, for troubleshooting.
- **`/chests`** — shows the number of in-game chests you've opened (for the chests/Daroach goal).

Keep BizHawk (with the connector running) and the client both open while you play.

---

## What happens as you play

- **Open a chest** → one check is sent for that chest, and you receive the item
  Archipelago placed there. This is true even for a chest whose treasure you've
  already been sent — the check still fires.
- **Clear a stage** → a stage-clear check is sent (every chest-bearing stage counts).
- **Abilities are locked**: inhaling an enemy for an ability you haven't received yet
  lets you hold it for about a second, then Kirby drops back to Normal. The **first**
  Progressive copy of an ability lets you keep it; the **second** copy is its **scroll
  upgrade** (the enhanced version), which now applies in a stage and sticks across levels.
- **Boss badges gate worlds**: a world stays locked until you've received the previous
  world's boss badge. Archipelago places items so this always works out.
- **Your collection fills** as you receive collectibles and open chests — sprays, scrolls,
  music, and the rest show on the collection screen. Received items appear right away
  (with one exception; see Known quirks).
- **Filler items heal**: a received Maxim Tomato fully heals; Meat heals about half,
  Energy Drink a third, Cherries a sixth, and the small foods (Hamburger, Nikuman,
  Omelet, Rice Ball, Pudding) a ninth each. A 1-Up adds a life. If one arrives while
  you're on the menu or world map, it applies the next time you enter a stage.
- **Vitality halves grow your health bar**: every two you receive adds a heart (+4 max
  HP) and tops you off. They raise your health but don't show on the collection screen and
  skip the upgrade cutscene — intentionally, since that cutscene used to crash the game.

---

## Tracking what you've opened

Because opened chests are recorded by the connector instead of being left in your save,
the level-map chest icons don't fill in. Two ways to see your progress:

- **Built-in overlay.** While you're on a stage, a checklist of that stage's chests appears
  top-left, marking which you've opened (e.g. `[KSS] 2-3 Nature Notch (2/3 opened)`). Press
  **T** to toggle it. Change `OVERLAY_TOGGLE_KEY` in the connector if T conflicts, or set
  `OVERLAY_DEFAULT_ON = false` to start hidden. It reads the server's authoritative list
  (via `kss_checked.txt`), so it's correct across reloads, and it never writes game memory.
- **Universal Tracker** (optional, full route view). It works with this world: put its
  `tracker` apworld in `custom_worlds`, keep your slot YAML in `Players`, and it adds a
  tracker tab to the client. Download:
  <https://github.com/FarisTheAncient/Archipelago/releases>. [Untested]

---

## Known quirks (not bugs)

- **A received collectible briefly disappears from your collection on the stage that holds
  its chest.** To keep that chest openable — so its check still fires — the connector hides
  that one stage's not-yet-opened chests while you're entering / on it. It comes right back
  the moment you open the chest or leave the stage, and it only ever affects the single
  stage you're currently on.
- **Opening a vitality-half chest plays a health-up, then it reverts.** The chest is only a
  *check* — your real max-HP growth comes from *receiving* vitality items (every two = +4
  HP), which persists. The momentary boost from the chest itself is undone on purpose, so
  you don't get health the seed didn't grant.
- **Incoming deaths apply when you're in a stage.** Death Link is full send and receive,
  but if a remote death arrives while you're on the world map, Kirby dies the moment you
  next enter a stage (his health only exists in-stage).
- **Opened chests don't fill the level-map icons.** Every chest you open is recorded by the
  connector rather than left set in your save (this is what keeps AP in control of the item
  and what makes replays safe). The trade-off is that the game's own map icons stay empty —
  use the built-in overlay (press **T**) or the Archipelago tracker to see what you've
  opened. See "Tracking what you've opened" above.
- **Replaying a cleared stage is safe.** Re-entering a stage and re-opening its chests is
  fine. Earlier builds could white-screen on the results screen once a stage's chest count
  was pushed past its max on a replay; the connector now prevents that.
- **The forced drop into Nature Notch 2-1 (right after Dedede) is a special case.** It
  skips normal stage select, so a 2-1 chest for a treasure you'd already been sent could
  load already-opened. Its check isn't lost — please report it if you hit it and it causes
  trouble.
- **The second Progressive Ability checks auto-send the scroll.** When you get a Progressive ability for the second
  time, you get the functions of having that scroll, and to do so the game has to make sure you have the scroll and it
  sets it. If you haven't already found that scroll, it will send the check of where it was, otherwise it would become
  an impossible check. Only scrolls are affected like this because they're the only collectibles that persist in levels.

---

## Troubleshooting

- **A flood of checks the moment you connect** → stale `%TEMP%` files. Disconnect,
  delete the `kss_*.txt` files, reload the connector, reconnect.
- **Connector shows a non-zero count on a fresh save** → you're on a polluted save
  from an earlier session; start a brand-new file.
- **Ability / scroll won't take even after it arrived** → confirm the item actually
  showed in the client log; the lock and the upgrade both use received items, not in-game
  pickups. The upgrade re-applies in-stage, so give it a moment after entering a level.
- **Nothing sends when you open chests** → make sure the Lua console still shows the
  connector running and the client still says Connected.
- **Received an item but nothing happened** → confirm the connector says **v42** and
  the client says Connected.

---

## File pairing

Keep the **connector** and the **apworld** together as a set. They share a fixed
check protocol. If you update one, use the matching version of the other from the
same release. Note that **this** release changed apworld data, so generate a fresh
seed for it (see "Generating a game").

---

## Credits

- **CalDrac** — original Kirby: Squeak Squad randomizer and treasure data.
- **WindChill404** — Archipelago world, BizHawk connector, and integration.
