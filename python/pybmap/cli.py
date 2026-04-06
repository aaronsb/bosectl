"""bosectl CLI — thin wrapper around the pybmap library."""

import os
import sys

import pybmap
from pybmap.constants import SPATIAL_NAMES, SIDETONE_NAMES, VOICE_LANGUAGES
from pybmap.errors import BmapError, BmapConnectionError
from pybmap.protocol import fmt_response

# ── ANSI Colors ──────────────────────────────────────────────────────────────

if sys.stdout.isatty():
    C_RESET = "\033[0m"
    C_BOLD  = "\033[1m"
    C_DIM   = "\033[2m"
    C_CYAN  = "\033[36m"
    C_GREEN = "\033[32m"
    C_YELLOW = "\033[33m"
    C_RED   = "\033[31m"
    C_MAGENTA = "\033[35m"
    C_WHITE = "\033[97m"
else:
    C_RESET = C_BOLD = C_DIM = C_CYAN = C_GREEN = ""
    C_YELLOW = C_RED = C_MAGENTA = C_WHITE = ""

_GRAD = ["\033[96m", "\033[36m", "\033[34m", "\033[35m", "\033[95m"]
_BANNER_LINES = [
    r"    __                         __  __",
    r"   / /_  ____  ________  _____/ /_/ /",
    r"  / __ \/ __ \/ ___/ _ \/ ___/ __/ / ",
    r" / /_/ / /_/ (__  )  __/ /__/ /_/ /  ",
    r"/_.___/\____/____/\___/\___/\__/_/   ",
]
BANNER = "\n".join(
    "%s%s%s%s" % (C_BOLD, _GRAD[i], line, C_RESET) for i, line in enumerate(_BANNER_LINES)
) + "\n%s  Bose QC Ultra 2 — no app, no cloud, no account%s\n" % (C_DIM, C_RESET)


def row(label, value, color=None):
    if color is None:
        color = C_WHITE
    print("  %s%-12s%s %s%s%s" % (C_DIM, label, C_RESET, color, value, C_RESET))


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_status(dev):
    s = dev.status()
    batt_color = C_GREEN if s.battery > 30 else C_YELLOW if s.battery > 10 else C_RED
    row("Battery", "%d%%" % s.battery, batt_color)
    row("Mode", s.mode, C_CYAN)

    cnc_bar = "\u2588" * s.cnc_level + "\u2591" * (s.cnc_max - s.cnc_level)
    row("CNC", "%s %d/%d" % (cnc_bar, s.cnc_level, s.cnc_max))

    if s.eq:
        eq_str = "/".join("%+d" % b.current for b in s.eq)
        row("EQ", "%s (bass/mid/treble)" % eq_str)

    row("Name", s.name, C_BOLD)
    row("FW", s.firmware, C_DIM)
    row("Sidetone", s.sidetone)
    row("Multipoint", "on" if s.multipoint else "off",
        C_GREEN if s.multipoint else C_DIM)
    row("AutoPause", "on" if s.auto_pause else "off",
        C_GREEN if s.auto_pause else C_DIM)
    row("Prompts", "%s (%s)" % ("on" if s.prompts_enabled else "off", s.prompts_language))


def cmd_profiles(dev):
    modes = dev.modes()
    current_idx = dev.mode_idx()
    for idx in sorted(modes):
        config = modes[idx]
        if not config.editable and not config.configured and idx > 4:
            continue
        is_current = idx == current_idx
        marker = " %s*%s" % (C_CYAN, C_RESET) if is_current else ""
        tag = ""
        if not config.editable:
            tag = " %s[preset]%s" % (C_DIM, C_RESET)
        elif not config.configured:
            tag = " %s[empty]%s" % (C_DIM, C_RESET)

        name_color = C_BOLD + C_WHITE if is_current else C_WHITE if (config.editable and config.configured) else C_DIM
        line = "  %s%2d%s  %s%-16s%s" % (C_DIM, idx, C_RESET, name_color, config.name, C_RESET)

        if config.configured or not config.editable:
            parts = []
            if config.cnc_level is not None:
                parts.append("cnc=%d" % config.cnc_level)
            if config.spatial and config.spatial > 0:
                parts.append("spatial=%s" % SPATIAL_NAMES.get(config.spatial, config.spatial))
            if config.wind_block:
                parts.append("wind=on")
            if parts:
                line += "  %s%s%s" % (C_DIM, " ".join(parts), C_RESET)

        line += tag + marker
        print(line)


def cmd_profile_set(dev, args):
    if not args:
        print("Usage: bosectl profile set <name> [cnc=N] [spatial=off|room|head] "
              "[wind=on|off] [anc=on|off]", file=sys.stderr)
        sys.exit(1)

    lookup_name = args[0]
    opts = {}
    for arg in args[1:]:
        if "=" not in arg:
            print("Invalid option: %s (expected key=value)" % arg, file=sys.stderr)
            sys.exit(1)
        k, v = arg.split("=", 1)
        opts[k.lower()] = v

    spatial_map = {"off": 0, "room": 1, "head": 2}
    bool_map = {"on": 1, "off": 0, "1": 1, "0": 0, "true": 1, "false": 0}

    settings = {}
    if "cnc" in opts:
        settings["cnc_level"] = int(opts["cnc"])
    if "spatial" in opts:
        settings["spatial"] = spatial_map.get(opts["spatial"], 0)
    if "wind" in opts:
        settings["wind_block"] = bool_map.get(opts["wind"].lower(), 0)
    if "anc" in opts:
        settings["anc_toggle"] = bool_map.get(opts["anc"].lower(), 1)
    if "name" in opts:
        settings["name"] = opts["name"]

    try:
        dev.update_profile(lookup_name, **settings)
        print("Updated: %s" % lookup_name)
    except BmapError:
        slot = dev.create_profile(lookup_name, **settings)
        print("Created (slot %d): %s" % (slot, lookup_name))


def cmd_buttons(dev):
    btn = dev.buttons()
    if btn is None:
        print("Could not read button config")
        return
    print("Button:     %s (0x%02x)" % (btn.button_name, btn.button_id))
    print("Event:      %s" % btn.event_name)
    print("Action:     %s" % btn.action_name)
    if btn.supported_actions:
        print("Supported:  %s" % ", ".join(btn.supported_actions))
    print("Raw:        %s" % btn.raw.hex())


def cmd_eq(dev, args):
    if not args or args[0] == "flat":
        dev.set_eq(0, 0, 0)
    elif len(args) == 3:
        dev.set_eq(int(args[0]), int(args[1]), int(args[2]))
    elif args[0] != "get":
        print("Usage: bosectl eq <bass> <mid> <treble>  (each -10 to +10)", file=sys.stderr)
        print("       bosectl eq flat                    (reset to 0/0/0)", file=sys.stderr)
        sys.exit(1)

    bands = dev.eq()
    for b in bands:
        print("%-6s: %+d" % (b.name, b.current))


def cmd_dump(dev):
    print("Triggering AudioModes GetAll (async)...")
    responses = dev.send_raw(
        pybmap.bmap_packet(31, 1, pybmap.constants.OP_START).hex()
    )
    for resp in responses:
        print(fmt_response(resp))
        if resp.fblock == 31 and resp.func == 6 and resp.op == pybmap.constants.OP_STATUS:
            from pybmap.devices.parsers import parse_mode_config_48
            config = parse_mode_config_48(resp.payload)
            if config:
                for field in config._fields:
                    if field != "raw":
                        print("    %s: %s" % (field, getattr(config, field)))


# ── Usage / Main ─────────────────────────────────────────────────────────────

def usage():
    print(BANNER)

    def section(title):
        print("  %s%s%s%s" % (C_BOLD, C_CYAN, title, C_RESET))

    def cmd(name, desc):
        print("    %s%-26s%s %s%s%s" % (C_GREEN, name, C_RESET, C_DIM, desc, C_RESET))

    section("Modes")
    cmd("quiet", "Quiet — full ANC")
    cmd("aware", "Aware — transparency")
    cmd("immersion", "Immersion — spatial audio, head tracking")
    cmd("cinema", "Cinema — spatial audio, fixed stage")
    print()

    section("Profiles")
    cmd("profiles", "List all audio profiles")
    cmd("profile set NAME [opts]", "Create/update a custom profile")
    cmd("profile rm NAME", "Delete a custom profile")
    cmd("switch NAME", "Switch to any profile by name")
    print("    %-26s %sOptions: cnc=N spatial=off|room|head%s" % ("", C_DIM, C_RESET))
    print("    %-26s %s         wind=on|off anc=on|off%s" % ("", C_DIM, C_RESET))
    print()

    section("Settings")
    cmd("cnc <0-10>", "Set noise cancellation level")
    cmd("eq B M T", "Set EQ (-10 to +10), or 'eq flat'")
    cmd("spatial MODE", "Spatial audio: off, room, head")
    cmd("name [TEXT]", "Get/set device name")
    cmd("sidetone MODE", "Sidetone: off, low, medium, high")
    cmd("multipoint on|off", "Toggle multipoint connection")
    cmd("autopause on|off", "Toggle auto play/pause on remove")
    cmd("autoanswer on|off", "Toggle auto-answer calls")
    cmd("prompts on|off", "Toggle voice prompts")
    print()

    section("Control")
    cmd("pair", "Enter Bluetooth pairing mode")
    cmd("off", "Power off headphones")
    print()

    section("Info")
    cmd("status", "Show all settings")
    cmd("battery", "Battery percentage (just the number)")
    cmd("current", "Current mode name (just the word)")
    cmd("buttons", "Show button mapping")
    print()

    section("Debug")
    cmd("dump", "Dump all AudioModes state")
    cmd("raw <hex>", "Send raw BMAP packet (hex bytes)")
    print()
    sys.exit(1)


def _parse_bool_arg(args, cmd_name):
    if not args:
        return None  # just read
    val = args[0].lower()
    if val in ("on", "1", "true", "yes"):
        return True
    elif val in ("off", "0", "false", "no"):
        return False
    else:
        print("Usage: bosectl %s [on|off]" % cmd_name, file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        usage()

    cmd = sys.argv[1].lower()
    if cmd in ("help", "-h", "--help"):
        usage()

    # Determine MAC and device type from env vars
    mac = os.environ.get("BOSE_MAC") or os.environ.get("BMAP_MAC")
    device_type = os.environ.get("BMAP_DEVICE", "qc_ultra2")

    try:
        dev = pybmap.connect(mac=mac, device_type=device_type)
    except BmapError as e:
        print("%sConnection failed:%s %s" % (C_RED, C_RESET, e), file=sys.stderr)
        print("%sIs Bluetooth on? Are the headphones paired and connected?%s" % (C_DIM, C_RESET), file=sys.stderr)
        sys.exit(1)

    preset_names = set(dev.preset_modes.keys())

    try:
        if cmd in preset_names:
            dev.set_mode(cmd)
            desc = dev.preset_modes[cmd].get("description", cmd)
            print("OK: %s" % desc)
        elif cmd == "status":
            cmd_status(dev)
        elif cmd == "battery":
            print(dev.battery())
        elif cmd == "current":
            print(dev.mode())
        elif cmd == "profiles":
            cmd_profiles(dev)
        elif cmd == "profile":
            if len(sys.argv) < 3:
                cmd_profiles(dev)
            elif sys.argv[2].lower() in ("set", "create", "add"):
                cmd_profile_set(dev, sys.argv[3:])
            elif sys.argv[2].lower() in ("rm", "delete", "del"):
                if len(sys.argv) < 4:
                    print("Usage: bosectl profile rm <name>", file=sys.stderr)
                    sys.exit(1)
                dev.delete_profile(sys.argv[3])
                print("Deleted: %s" % sys.argv[3])
            else:
                cmd_profile_set(dev, sys.argv[2:])
        elif cmd == "switch":
            if len(sys.argv) < 3:
                print("Usage: bosectl switch <name>", file=sys.stderr)
                sys.exit(1)
            dev.set_mode(sys.argv[2])
            print("OK: %s" % sys.argv[2])
        elif cmd == "dump":
            cmd_dump(dev)
        elif cmd == "cnc":
            if len(sys.argv) < 3:
                cur, mx = dev.cnc()
                print("%d/%d" % (cur, mx))
            else:
                dev.set_cnc(int(sys.argv[2]))
                print("CNC: %s/10" % sys.argv[2])
        elif cmd == "eq":
            cmd_eq(dev, sys.argv[2:])
        elif cmd == "name":
            if len(sys.argv) > 2:
                dev.set_name(" ".join(sys.argv[2:]))
            print(dev.name())
        elif cmd == "sidetone":
            if len(sys.argv) > 2:
                dev.set_sidetone(sys.argv[2])
            print(dev.sidetone())
        elif cmd == "multipoint":
            val = _parse_bool_arg(sys.argv[2:], "multipoint")
            if val is not None:
                dev.set_multipoint(val)
            print("on" if dev.multipoint() else "off")
        elif cmd == "autopause":
            val = _parse_bool_arg(sys.argv[2:], "autopause")
            if val is not None:
                dev.set_auto_pause(val)
            print("on" if dev.auto_pause() else "off")
        elif cmd == "autoanswer":
            val = _parse_bool_arg(sys.argv[2:], "autoanswer")
            if val is not None:
                dev.set_auto_answer(val)
            print("on" if dev.auto_answer() else "off")
        elif cmd == "prompts":
            val = _parse_bool_arg(sys.argv[2:], "prompts")
            if val is not None:
                dev.set_prompts(val)
            enabled, lang = dev.prompts()
            print("%s (%s)" % ("on" if enabled else "off", lang))
        elif cmd == "spatial":
            if len(sys.argv) < 3:
                print("Usage: bosectl spatial <off|room|head>", file=sys.stderr)
                sys.exit(1)
            dev.set_spatial(sys.argv[2].lower())
            print("Spatial: %s" % sys.argv[2].lower())
        elif cmd == "buttons":
            cmd_buttons(dev)
        elif cmd == "pair":
            dev.pair()
            print("Pairing mode enabled")
        elif cmd == "off":
            dev.power_off()
            print("Powering off")
        elif cmd == "raw":
            if len(sys.argv) < 3:
                print("Usage: bosectl raw <hex>", file=sys.stderr)
                sys.exit(1)
            hex_str = " ".join(sys.argv[2:])
            print("TX: %s" % hex_str.replace(" ", ""))
            responses = dev.send_raw(hex_str)
            for resp in responses:
                print("RX: %s" % fmt_response(resp))
        else:
            # Try as a custom profile name
            try:
                dev.set_mode(sys.argv[1])
                print("OK: %s" % sys.argv[1])
            except BmapError:
                print("Unknown command: %s" % cmd, file=sys.stderr)
                sys.exit(1)
    except BmapError as e:
        print("%sError:%s %s" % (C_RED, C_RESET, e), file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print("%sError:%s %s" % (C_RED, C_RESET, e), file=sys.stderr)
        sys.exit(1)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
