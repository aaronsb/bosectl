//! Conformance adapter: drives the bmap library for conformance/run.py.
//!
//! Reads requests on stdin and answers on stdout, one line each, as
//! conformance/INTERFACE.md describes. The library talks to a stdio transport
//! instead of Bluetooth, so the runner plays the headphones' side.
//!
//! The adapter holds no device knowledge: it maps call names to library
//! methods and formats what they return.

use std::io::{self, Write};

use bmap::device::Addr;
use bmap::{devices, BmapConnection, BmapError, BmapResult, DeviceConfig, Transport};

/// A transport whose far end is the conformance runner.
struct StdioTransport;

impl StdioTransport {
    fn exchange(&self, word: &str, packet: &[u8]) -> BmapResult<Vec<u8>> {
        write_line(&format!("{} {}", word, hex(packet)));
        let line = read_line().ok_or_else(|| BmapError::Connection("stdin closed".into()))?;
        if line == "timeout" {
            return Err(BmapError::Timeout("timeout from the conformance runner".into()));
        }
        match line.split_once(' ') {
            Some(("recv", h)) => unhex(h),
            None if line == "recv" => Ok(Vec::new()),
            _ => Err(BmapError::Connection(format!("expected recv or timeout, got {:?}", line))),
        }
    }
}

impl Transport for StdioTransport {
    fn send_recv(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
        self.exchange("send", packet)
    }

    fn send_recv_drain(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
        self.exchange("send-drain", packet)
    }
}

fn write_line(line: &str) {
    let mut out = io::stdout().lock();
    let _ = writeln!(out, "{}", line);
    let _ = out.flush();
}

fn read_line() -> Option<String> {
    let mut line = String::new();
    match io::stdin().read_line(&mut line) {
        Ok(0) | Err(_) => None,
        Ok(_) => Some(line.trim_end_matches('\n').to_string()),
    }
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}

fn unhex(text: &str) -> BmapResult<Vec<u8>> {
    let bad = || BmapError::Connection(format!("not hex bytes: {:?}", text));
    if text.len() % 2 != 0 {
        return Err(bad());
    }
    (0..text.len())
        .step_by(2)
        .map(|i| text.get(i..i + 2).and_then(|b| u8::from_str_radix(b, 16).ok()).ok_or_else(bad))
        .collect()
}

fn on_off(value: bool) -> String {
    (if value { "on" } else { "off" }).to_string()
}

/// The number of arguments each call takes, as INTERFACE.md lists them.
/// set_name is left out: its one argument is the rest of the line.
fn arity(method: &str) -> Option<usize> {
    match method {
        "battery" | "firmware" | "name" | "cnc" | "eq" | "multipoint" | "sidetone"
        | "auto_pause" | "auto_answer" => Some(0),
        "set_cnc" | "set_multipoint" | "set_sidetone" | "set_auto_pause"
        | "set_auto_answer" | "set_anc" => Some(1),
        "set_eq" => Some(3),
        _ => None,
    }
}

fn arg<'a>(args: &[&'a str], i: usize) -> BmapResult<&'a str> {
    args.get(i).copied().ok_or_else(|| BmapError::InvalidArg("missing argument".into()))
}

fn num<N: std::str::FromStr>(args: &[&str], i: usize) -> BmapResult<N> {
    let a = arg(args, i)?;
    a.parse().map_err(|_| BmapError::InvalidArg(format!("not a number: {:?}", a)))
}

fn flag(args: &[&str], i: usize) -> BmapResult<bool> {
    match arg(args, i)? {
        "on" => Ok(true),
        "off" => Ok(false),
        a => Err(BmapError::InvalidArg(format!("expected on or off, got {:?}", a))),
    }
}

fn error_line(error: &BmapError) -> String {
    match error {
        BmapError::Unsupported(_) => "err unsupported".into(),
        BmapError::InvalidArg(_) => "err invalid-arg".into(),
        BmapError::Device { code, .. } => format!("err device-error {}", code),
        BmapError::Auth(_) => "err device-error 5".into(),
        BmapError::Timeout(_) => "err timeout".into(),
        BmapError::Desync(_) => "err desync".into(),
        other => format!("err other {}", other),
    }
}

/// Run one call. `Ok(None)` means the method is not one INTERFACE.md lists.
fn call(dev: &BmapConnection<StdioTransport>, method: &str, args: &[&str]) -> BmapResult<Option<String>> {
    let result = match method {
        "battery" => Some(dev.battery()?.to_string()),
        "firmware" => Some(dev.firmware()?),
        "name" => Some(dev.name()?),
        "cnc" => {
            let (current, max) = dev.cnc()?;
            Some(format!("{}/{}", current, max))
        }
        "eq" => {
            let mut bands = dev.eq()?;
            bands.sort_by_key(|b| b.band_id);
            Some(bands.iter().map(|b| b.current.to_string()).collect::<Vec<_>>().join(" "))
        }
        "multipoint" => Some(on_off(dev.multipoint()?)),
        "sidetone" => Some(dev.sidetone()?.to_string()),
        "auto_pause" => Some(on_off(dev.auto_pause()?)),
        "auto_answer" => Some(on_off(dev.auto_answer()?)),
        "set_cnc" => { dev.set_cnc(num(args, 0)?)?; None }
        "set_eq" => { dev.set_eq(num(args, 0)?, num(args, 1)?, num(args, 2)?)?; None }
        "set_name" => { dev.set_name(arg(args, 0)?)?; None }
        "set_multipoint" => { dev.set_multipoint(flag(args, 0)?)?; None }
        "set_sidetone" => { dev.set_sidetone(arg(args, 0)?)?; None }
        "set_auto_pause" => { dev.set_auto_pause(flag(args, 0)?)?; None }
        "set_auto_answer" => { dev.set_auto_answer(flag(args, 0)?)?; None }
        "set_anc" => { dev.set_anc(flag(args, 0)?)?; None }
        _ => return Ok(None),
    };
    Ok(Some(match result {
        Some(text) => format!("ok {}", text),
        None => "ok".into(),
    }))
}

fn addr(a: Addr) -> String {
    format!("{}.{}", a.0, a.1)
}

fn describe(c: &DeviceConfig) -> Vec<String> {
    let mut lines = vec![
        format!("channel {}", c.rfcomm_channel),
        format!("init {}", c.init_packet.map_or("-".into(), addr)),
        format!("notifications {}", c.notifications.map_or("-".into(), hex)),
    ];
    let features = [
        ("battery", c.battery),
        ("firmware", c.firmware),
        ("product_name", c.product_name),
        ("voice_prompts", c.voice_prompts),
        ("cnc", c.cnc),
        ("eq", c.eq),
        ("buttons", c.buttons),
        ("multipoint", c.multipoint),
        ("sidetone", c.sidetone),
        ("auto_pause", c.auto_pause),
        ("auto_answer", c.auto_answer),
        ("anr", c.anr),
        ("pairing", c.pairing),
        ("routing", c.routing),
        ("source", c.source),
        ("power", c.power),
        ("get_all_modes", c.get_all_modes),
        ("current_mode", c.current_mode),
        ("mode_config", c.mode_config),
        ("favorites", c.favorites),
        ("audio_settings", c.audio_settings),
    ];
    for (name, a) in features {
        if let Some(a) = a {
            lines.push(format!("feature {} {}", name, addr(a)));
        }
    }
    for &a in c.read_only {
        lines.push(format!("read-only {}", addr(a)));
    }
    lines.push(format!("status-supported-only {}", c.status_supported_only as u8));
    lines.push(format!("bose-music-names {}", c.bose_music_names as u8));
    lines.push(format!("anc-toggle {}", c.supports_anc_toggle as u8));
    let slots = c.editable_slots.to_vec();
    lines.push(format!(
        "editable-slots {}",
        if slots.is_empty() { "-".into() } else { slots.iter().map(u8::to_string).collect::<Vec<_>>().join(" ") }
    ));
    for (name, preset) in c.preset_modes {
        lines.push(format!("preset {} {}", name, preset.idx));
    }
    lines
}

fn main() {
    let mut dev: Option<BmapConnection<StdioTransport>> = None;
    while let Some(line) = read_line() {
        let words: Vec<&str> = line.split(' ').collect();
        match (words[0], dev.as_ref()) {
            ("device", _) if words.len() == 2 => match devices::get_device(words[1]) {
                Some(config) => {
                    dev = Some(BmapConnection::new(StdioTransport, config));
                    write_line("ready");
                }
                None => write_line("err unknown-device"),
            },
            ("call", Some(d)) if words.len() > 1 => {
                let method = words[1];
                // set_name takes the rest of the line as its one argument.
                let rest: Vec<&str> = match line.splitn(3, ' ').nth(2) {
                    Some(text) if method == "set_name" => vec![text],
                    _ => words[2..].to_vec(),
                };
                let answer = match arity(method) {
                    Some(n) if n != rest.len() => "err invalid-arg".into(),
                    _ => match call(d, method, &rest) {
                        Ok(Some(answer)) => answer,
                        Ok(None) => "err unknown-request".into(),
                        Err(e) => error_line(&e),
                    },
                };
                write_line(&answer);
            }
            ("describe", Some(d)) if words.len() == 1 => {
                for out in describe(d.config()) {
                    write_line(&out);
                }
                write_line("end");
            }
            _ => write_line("err unknown-request"),
        }
    }
}
