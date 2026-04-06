//! bmapctl — Minimal CLI for controlling BMAP devices.
//!
//! Single-binary alternative to bosectl, built on the bmap Rust library.

use std::env;
use std::process;

use bmap::{connect, BmapError};

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        usage();
        process::exit(1);
    }

    let cmd = args[1].to_lowercase();
    if cmd == "help" || cmd == "-h" || cmd == "--help" {
        usage();
        process::exit(0);
    }

    let mac = env::var("BMAP_MAC").ok();
    let device_type = env::var("BMAP_DEVICE").ok();

    let dev = match connect(mac.as_deref(), device_type.as_deref()) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("Connection failed: {}", e);
            eprintln!("Is Bluetooth on? Are the headphones paired and connected?");
            process::exit(1);
        }
    };

    let result = match cmd.as_str() {
        "status" => cmd_status(&dev),
        "battery" => dev.battery().map(|b| println!("{}", b)),
        "current" => dev.mode().map(|m| println!("{}", m)),
        "quiet" | "aware" | "immersion" | "cinema" => {
            dev.set_mode(&cmd, false).map(|_| println!("OK: {}", cmd))
        }
        "cnc" => {
            if args.len() < 3 {
                dev.cnc().map(|(cur, max)| println!("{}/{}", cur, max))
            } else {
                let level: u8 = args[2].parse().unwrap_or_else(|_| {
                    eprintln!("CNC level must be 0-10");
                    process::exit(1);
                });
                dev.set_cnc(level).map(|_| println!("CNC: {}/10", level))
            }
        }
        "spatial" => {
            if args.len() < 3 {
                eprintln!("Usage: bmapctl spatial <off|room|head>");
                process::exit(1);
            }
            dev.set_spatial(&args[2]).map(|_| println!("Spatial: {}", args[2]))
        }
        "autoanswer" => {
            if args.len() > 2 {
                let on = matches!(args[2].as_str(), "on" | "1" | "true" | "yes");
                if let Err(e) = dev.set_auto_answer(on) {
                    return err_exit(&e);
                }
            }
            dev.auto_answer().map(|a| println!("{}", if a { "on" } else { "off" }))
        }
        "switch" => {
            if args.len() < 3 {
                eprintln!("Usage: bmapctl switch <name>");
                process::exit(1);
            }
            dev.set_mode(&args[2], false).map(|_| println!("OK: {}", args[2]))
        }
        "eq" => {
            if args.len() < 5 {
                dev.eq().map(|bands| {
                    for b in &bands {
                        println!("{:6}: {:+}", b.name, b.current);
                    }
                })
            } else {
                let bass: i8 = args[2].parse().unwrap_or(0);
                let mid: i8 = args[3].parse().unwrap_or(0);
                let treble: i8 = args[4].parse().unwrap_or(0);
                dev.set_eq(bass, mid, treble).map(|_| println!("EQ: {}/{}/{}", bass, mid, treble))
            }
        }
        "name" => {
            if args.len() > 2 {
                let new_name = args[2..].join(" ");
                if let Err(e) = dev.set_name(&new_name) {
                    return err_exit(&e);
                }
            }
            dev.name().map(|n| println!("{}", n))
        }
        "sidetone" => {
            if args.len() > 2 {
                if let Err(e) = dev.set_sidetone(&args[2]) {
                    return err_exit(&e);
                }
            }
            dev.sidetone().map(|s| println!("{}", s))
        }
        "multipoint" => {
            if args.len() > 2 {
                let on = matches!(args[2].as_str(), "on" | "1" | "true" | "yes");
                if let Err(e) = dev.set_multipoint(on) {
                    return err_exit(&e);
                }
            }
            dev.multipoint().map(|m| println!("{}", if m { "on" } else { "off" }))
        }
        "autopause" => {
            if args.len() > 2 {
                let on = matches!(args[2].as_str(), "on" | "1" | "true" | "yes");
                if let Err(e) = dev.set_auto_pause(on) {
                    return err_exit(&e);
                }
            }
            dev.auto_pause().map(|a| println!("{}", if a { "on" } else { "off" }))
        }
        "anr" => {
            if args.len() > 2 {
                if let Err(e) = dev.set_anr(&args[2]) {
                    return err_exit(&e);
                }
            }
            dev.anr().map(|a| println!("{}", a))
        }
        "prompts" => {
            if args.len() > 2 {
                let on = matches!(args[2].as_str(), "on" | "1" | "true" | "yes");
                if let Err(e) = dev.set_prompts(on) {
                    return err_exit(&e);
                }
            }
            dev.prompts().map(|(on, lang)| {
                println!("{} ({})", if on { "on" } else { "off" }, lang);
            })
        }
        "buttons" => {
            if args.len() >= 4 && args[2] == "set" {
                let btn = match dev.buttons() {
                    Ok(b) => b,
                    Err(e) => return err_exit(&e),
                };
                let action = bmap::device::action_id_from_name(&args[3])
                    .unwrap_or_else(|| {
                        eprintln!("Unknown action: {}", args[3]);
                        process::exit(1);
                    });
                dev.set_buttons(btn.button_id, btn.event, action)
                    .map(|result| {
                        println!("Remapped: {} {} -> {}", result.button_name, result.event_name, result.action_name);
                    })
            } else {
                dev.buttons().map(|btn| {
                    println!("Button:  {} (0x{:02x})", btn.button_name, btn.button_id);
                    println!("Event:   {}", btn.event_name);
                    println!("Action:  {}", btn.action_name);
                })
            }
        }
        "profiles" => dev.modes().map(|modes| {
            for m in &modes {
                print!("  {:2}  {}", m.mode_idx, m.name);
                if !m.editable { print!(" [preset]"); }
                else if !m.configured { print!(" [empty]"); }
                println!();
            }
        }),
        "dump" => {
            let pkt = bmap::protocol::bmap_packet(31, 1, bmap::Operator::Start, &[]);
            dev.send_raw(&pkt).map(|responses| {
                for r in &responses {
                    println!("{}", r.fmt());
                }
            })
        }
        "pair" => dev.pair().map(|_| println!("Pairing mode enabled")),
        "off" => dev.power_off().map(|_| println!("Powering off")),
        "raw" => {
            if args.len() < 3 {
                eprintln!("Usage: bmapctl raw <hex>");
                process::exit(1);
            }
            let hex_str: String = args[2..].join("").replace(' ', "");
            let data = hex_to_bytes(&hex_str);
            println!("TX: {}", hex_str);
            dev.send_raw(&data).map(|responses| {
                for r in &responses {
                    println!("RX: {}", r.fmt());
                }
            })
        }
        _ => {
            // Try as custom profile name
            match dev.set_mode(&cmd, false) {
                Ok(_) => Ok(println!("OK: {}", cmd)),
                Err(_) => {
                    eprintln!("Unknown command: {}", cmd);
                    process::exit(1);
                }
            }
        }
    };

    if let Err(e) = result {
        eprintln!("Error: {}", e);
        process::exit(1);
    }
}

fn err_exit(e: &BmapError) {
    eprintln!("Error: {}", e);
    process::exit(1);
}

fn cmd_status(dev: &bmap::BmapConnection<impl bmap::Transport>) -> Result<(), BmapError> {
    let s = dev.status()?;
    let cnc_bar: String = "█".repeat(s.cnc_level as usize)
        + &"░".repeat((s.cnc_max - s.cnc_level) as usize);

    println!("  Battery      {}%", s.battery);
    if !s.mode.is_empty() {
        println!("  Mode         {}", s.mode);
    }
    if dev.anr().is_ok() {
        if let Ok(anr) = dev.anr() {
            println!("  ANR          {}", anr);
        }
    } else {
        println!("  CNC          {} {}/{}", cnc_bar, s.cnc_level, s.cnc_max);
    }
    if !s.eq.is_empty() {
        let eq_str: Vec<String> = s.eq.iter().map(|b| format!("{:+}", b.current)).collect();
        println!("  EQ           {} (bass/mid/treble)", eq_str.join("/"));
    }
    println!("  Name         {}", s.name);
    println!("  FW           {}", s.firmware);
    println!("  Sidetone     {}", s.sidetone);
    println!("  Multipoint   {}", if s.multipoint { "on" } else { "off" });
    println!("  AutoPause    {}", if s.auto_pause { "on" } else { "off" });
    println!("  Prompts      {} ({})", if s.prompts_enabled { "on" } else { "off" }, s.prompts_language);
    Ok(())
}

fn hex_to_bytes(hex: &str) -> Vec<u8> {
    let hex = if hex.len() % 2 != 0 { &hex[..hex.len() - 1] } else { hex };
    (0..hex.len())
        .step_by(2)
        .filter_map(|i| u8::from_str_radix(&hex[i..i + 2], 16).ok())
        .collect()
}

fn usage() {
    println!("bmapctl — Control BMAP Bluetooth audio devices");
    println!();
    println!("Usage: bmapctl <command> [args...]");
    println!();
    println!("  status              Show all settings");
    println!("  battery             Battery percentage");
    println!("  current             Current mode name");
    println!("  quiet/aware/...     Switch audio mode");
    println!("  cnc                 Show noise cancellation level");
    println!("  eq [B M T]          Show/set EQ (-10 to +10)");
    println!("  name [TEXT]         Show/set device name");
    println!("  sidetone [MODE]     Show/set sidetone (off/low/medium/high)");
    println!("  multipoint [on|off] Toggle multipoint");
    println!("  autopause [on|off]  Toggle auto play/pause");
    println!("  prompts             Show voice prompt status");
    println!("  buttons             Show button mapping");
    println!("  buttons set <action> Remap button (e.g. ANC, VPA, Disabled)");
    println!("  pair                Enter pairing mode");
    println!("  off                 Power off");
    println!("  raw <hex>           Send raw BMAP packet");
    println!();
    println!("Environment:");
    println!("  BMAP_MAC=XX:XX:XX:XX:XX:XX   Device MAC (auto-detected if unset)");
    println!("  BMAP_DEVICE=qc_ultra2         Device type (default: qc_ultra2)");
}
