Disclaimer: I do not have programming experience and created this Archipelago experience with AI. Please let me know of any issues or suggestions on Discord!

# Kirby: Squeak Squad — Archipelago — How to Play

A multiworld randomizer for Kirby: Squeak Squad (Nintendo DS). Opening chests and
clearing stages send checks; you receive your items from Archipelago. Abilities are
locked behind their scrolls, and boss badges gate access to later worlds.

---

## What you need

- **BizHawk** (the emulator), using its **melonDS** core for NDS.
- A **vanilla US** Kirby: Squeak Squad ROM (you supply this).
- **Archipelago 0.6.7** or newer (the standard installer build).
- The two files from this folder:
  - `kirby_squeak_squad.apworld`
  - `KirbySqueakSquad_Connector.lua`

---

## One-time install

1. Drop **`kirby_squeak_squad.apworld`** into Archipelago's `custom_worlds` folder
   (replace any older copy).
2. Launch the Archipelago Launcher. You should see a **"Kirby Squeak Squad Client"**
   button with the Kirby icon. That confirms the apworld is installed.

---

## Generating a game

1. Make a YAML for your slot. The important field is your **slot name** (e.g.
   `name: windstarkirby`) — remember it, you'll type it when connecting.
2. Generate / host the game (locally or on archipelago.gg) like any other AP game.
   Successful generation means the logic held (badge + scroll gating included).

### Optional: goal settings (YAML)

By default the goal is to **beat the game**. You don't need to add anything for that.
If you want a different goal, add these to your YAML:

- `goal: chests_and_daroach` — instead of beating the game, your goal becomes
  collecting a number of chests **and** beating Daroach (the Ice Island / stage-6
  boss). Leave it out (or use `goal: beat_game`) for the normal goal.
- `chest_goal_count: 70` — only used by the `chests_and_daroach` goal; how many
  chests are required (1–119, default 70).

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
     collected as "already done," so load it while your count is still 0. (1-1 has no
     chests, so it's the natural spot.)

2. **(Only if needed) delete** `kss_checks.txt`, `kss_items.txt`, `kss_goal.txt` from
   your `%TEMP%` folder. You normally do **not** need to — the connector clears its
   own files on load. Only do this after a crash, a force-quit, or when switching to a
   different room/seed.

3. **Load the connector.** With Kirby standing in that first stage, open BizHawk's
   **Lua Console** (Tools → Lua Console) and load
   **`KirbySqueakSquad_Connector.lua`**. It should print:
   `KSS connector ready (v8.1). 0 chest locations already collected.`
   The `0` is your green light. A different number means you're on an old or polluted
   save — start a fresh file and reload.

4. **Open the Kirby Squeak Squad Client** from the Archipelago Launcher.

5. **Connect.** In the client: `/connect <address:port>`, then enter your **slot
   name** when asked. Wait for **"Connected."** Now play normally.

---

## Useful client commands

- **`/received`** — lists every collectible you've received from Archipelago so far.
  Handy because the in-game collection fills with a delay, so this is the quick way
  to see what's actually arrived.
- **`/kss`** — prints the three bridge file paths, for troubleshooting.

Now play. Keep BizHawk (with the connector running) and the client both open.

---

## What happens as you play

- **Open a chest** → one check is sent for that chest, and you receive the item
  Archipelago placed there. The chest's vanilla item is replaced by the AP item.
- **Clear a stage** → a stage-clear check is sent (every chest-bearing stage counts).
- **Abilities are scroll-locked**: inhaling an enemy for an ability whose scroll you
  haven't received yet will let you hold it for about a second, then Kirby drops back
  to Normal. Once you receive that scroll, the ability works normally.
- **Boss badges gate worlds** (in the logic): you'll receive the previous world's
  boss badge before the next world is expected — Archipelago places items so this
  always works out.
- **Your collection fills** as you open chests and receive collectibles — sprays,
  scrolls, music, and the rest show up on the collection screen.
- **Filler items have an effect**: a received Maxim Tomato, Energy Drink, or
  Invincible Candy refills your health; a 1-Up adds a life. If one arrives while
  you're on the menu or world map, it applies the next time you enter a stage.

---

## Known quirks (not bugs)

- **Key / Star Seal chests can gray out.** The game opens EX stages and Secret Sea by
  reading these 12 collectibles directly, so their bits must be set the instant you
  receive them. If you receive a key or seal **before** opening its own chest, that
  chest comes up gray and won't send its check. This is the only masking left (12
  chests, and only in that ordering) and is unavoidable without ROM patching.
- **Collection fills gradually**, not the instant items arrive — a received
  collectible appears once you've opened its chest. This is deliberate (it's what
  keeps non-key chests from graying out).
- **The very first stage (1-1) prints a "Stage clear" line but sends no check.**
  Chestless stages have no stage-clear location, so the detection is harmlessly
  ignored. Expected.

---

## Troubleshooting

- **A flood of checks the moment you connect** → stale `%TEMP%` files. Disconnect,
  delete the three `kss_*.txt` files, reload the connector, reconnect.
- **Connector shows a non-zero count on a fresh save** → you're on a polluted save
  from an earlier session; start a brand-new file.
- **Ability won't stick even with the scroll** → confirm the scroll actually arrived
  in the client log; the lock uses received scrolls, not in-game pickups.
- **Nothing sends when you open chests** → make sure the Lua console still shows the
  connector running and the client still says Connected.

---

## File pairing

Keep the **connector** and the **apworld** together as a set. They share a fixed
check protocol, so you don't need to regenerate rooms when only the connector
changes. If you update one, use the matching version of the other from the same
release.
