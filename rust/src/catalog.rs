//! Bose device catalog — known BMAP-capable devices.
//!
//! Sourced from the decompiled Bose Music APK (`BoseProductId.java`
//! enum). The enum's `value` field is the product ID reported over
//! Bluetooth Modalias; verified against WOLVERINE (0x4082) and EDITH
//! (0x4062).

/// All Bose USB devices share this vendor ID.
pub const BOSE_USB_VID: u16 = 0x05A7;

/// BMAP Bluetooth service UUID (SDP record).
pub const BMAP_UUID: &str = "00000000-deca-fade-deca-deafdecacaff";

/// Device category.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Category {
    Headphones,
    Earbuds,
    Speaker,
}

/// A known Bose BMAP device.
#[derive(Debug, Clone)]
pub struct BoseDevice {
    pub product_id: u16,
    pub codename: &'static str,
    pub name: &'static str,
    pub category: Category,
    /// Library config key, or None if not yet supported.
    pub config: Option<&'static str>,
}

/// All known BMAP-capable Bose devices.
pub const CATALOG: &[BoseDevice] = &[
    // Headphones
    BoseDevice { product_id: 0x400C, codename: "wolfcastle", name: "QuietComfort 35",                        category: Category::Headphones, config: Some("qc35") },
    BoseDevice { product_id: 0x4015, codename: "stetson",    name: "Hearphones",                             category: Category::Headphones, config: None },
    BoseDevice { product_id: 0x4020, codename: "baywolf",    name: "QuietComfort 35 II",                     category: Category::Headphones, config: Some("qc35") },
    BoseDevice { product_id: 0x4021, codename: "atlas",      name: "ProFlight",                              category: Category::Headphones, config: None },
    BoseDevice { product_id: 0x4024, codename: "goodyear",   name: "Noise Cancelling Headphones 700",        category: Category::Headphones, config: None },
    BoseDevice { product_id: 0x402B, codename: "beanie",     name: "Hearphones II",                          category: Category::Headphones, config: None },
    BoseDevice { product_id: 0x4039, codename: "duran",      name: "QuietComfort 45",                        category: Category::Headphones, config: None },
    BoseDevice { product_id: 0x4066, codename: "lonestarr",  name: "QuietComfort Ultra Headphones",          category: Category::Headphones, config: None },
    BoseDevice { product_id: 0x4075, codename: "prince",     name: "QuietComfort Headphones",                category: Category::Headphones, config: None },
    BoseDevice { product_id: 0x4082, codename: "wolverine",  name: "QuietComfort Ultra Headphones (2nd Gen)", category: Category::Headphones, config: Some("qc_ultra2") },
    // Earbuds
    BoseDevice { product_id: 0x4012, codename: "ice",        name: "SoundSport",                             category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x4013, codename: "flurry",     name: "SoundSport Pulse",                       category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x4014, codename: "powder",     name: "QuietControl 30",                        category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x4018, codename: "levi",       name: "SoundSport Free",                        category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x402C, codename: "celine",     name: "Frames",                                 category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x402D, codename: "revel",      name: "Sport Earbuds",                          category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x402F, codename: "lando",      name: "QuietComfort Earbuds",                   category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x403A, codename: "gwen",       name: "Sport Open Earbuds",                     category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x404C, codename: "celine_ii",  name: "Frames (2nd Gen)",                       category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x4060, codename: "olivia",     name: "Frames Tempo",                           category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x4061, codename: "vedder",     name: "Frames",                                 category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x4062, codename: "edith",      name: "QuietComfort Ultra Earbuds (2nd Gen)",   category: Category::Earbuds, config: Some("qc_ultra2") },
    BoseDevice { product_id: 0x4064, codename: "smalls",     name: "QuietComfort Earbuds II",                category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x4068, codename: "serena",     name: "Ultra Open Earbuds",                     category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x4072, codename: "scotty",     name: "QuietComfort Ultra Earbuds",             category: Category::Earbuds, config: None },
    // Speakers
    BoseDevice { product_id: 0x400A, codename: "isaac",      name: "AE2 SoundLink",                          category: Category::Speaker, config: None },
    BoseDevice { product_id: 0x400D, codename: "foreman",    name: "SoundLink Color II",                     category: Category::Speaker, config: None },
    BoseDevice { product_id: 0x4010, codename: "folgers",    name: "SoundLink Revolve",                      category: Category::Speaker, config: None },
    BoseDevice { product_id: 0x4011, codename: "harvey",     name: "SoundLink Revolve+",                     category: Category::Speaker, config: None },
    BoseDevice { product_id: 0x4017, codename: "kleos",      name: "SoundWear",                              category: Category::Speaker, config: None },
    BoseDevice { product_id: 0x4022, codename: "minnow",     name: "SoundLink Micro",                        category: Category::Speaker, config: None },
    BoseDevice { product_id: 0x4085, codename: "troy",       name: "SoundLink Plus",                         category: Category::Speaker, config: None },
    BoseDevice { product_id: 0xA211, codename: "chibi",      name: "S1 Pro",                                 category: Category::Speaker, config: None },
    BoseDevice { product_id: 0xBC58, codename: "billie",     name: "SoundLink Micro 2",                      category: Category::Speaker, config: None },
    BoseDevice { product_id: 0xBC59, codename: "phelps",     name: "SoundLink Flex",                         category: Category::Speaker, config: None },
    BoseDevice { product_id: 0xBC60, codename: "phelps_ii",  name: "SoundLink Flex (2nd Gen)",               category: Category::Speaker, config: None },
    BoseDevice { product_id: 0xBC61, codename: "mathers",    name: "SoundLink Flex 2",                       category: Category::Speaker, config: None },
    BoseDevice { product_id: 0xBC63, codename: "stan",       name: "SoundLink Flex SE 2",                    category: Category::Speaker, config: None },
];

/// Look up a Bose device by product ID.
pub fn lookup_device(product_id: u16) -> Option<&'static BoseDevice> {
    CATALOG.iter().find(|d| d.product_id == product_id)
}

/// All devices with active library support.
pub fn supported_devices() -> Vec<&'static BoseDevice> {
    CATALOG.iter().filter(|d| d.config.is_some()).collect()
}

/// Check if a product ID has an active library implementation.
pub fn is_supported(product_id: u16) -> bool {
    lookup_device(product_id).map_or(false, |d| d.config.is_some())
}

/// Get USB vendor/product ID pair for a known device.
pub fn usb_ids(product_id: u16) -> Option<(u16, u16)> {
    if lookup_device(product_id).is_some() {
        Some((BOSE_USB_VID, product_id))
    } else {
        None
    }
}

/// Generate a Bluetooth Modalias string for a known device.
pub fn modalias(product_id: u16) -> Option<String> {
    if lookup_device(product_id).is_some() {
        Some(format!("bluetooth:v{:04X}p{:04X}d0000", BOSE_USB_VID, product_id))
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lookup_known() {
        let dev = lookup_device(0x4082).unwrap();
        assert_eq!(dev.codename, "wolverine");
        assert_eq!(dev.config, Some("qc_ultra2"));
    }

    #[test]
    fn test_lookup_unknown() {
        assert!(lookup_device(0xFFFF).is_none());
    }

    #[test]
    fn test_is_supported() {
        assert!(is_supported(0x4082));
        assert!(is_supported(0x4020));
        assert!(!is_supported(0x4024)); // NCH 700, no config
        assert!(!is_supported(0xFFFF));
    }

    #[test]
    fn test_supported_devices() {
        let devs = supported_devices();
        assert!(devs.len() >= 2); // at least QC35 + QC Ultra 2
        assert!(devs.iter().all(|d| d.config.is_some()));
    }

    #[test]
    fn test_usb_ids() {
        let (vid, pid) = usb_ids(0x4082).unwrap();
        assert_eq!(vid, 0x05A7);
        assert_eq!(pid, 0x4082);
        assert!(usb_ids(0xFFFF).is_none());
    }

    #[test]
    fn test_modalias() {
        let m = modalias(0x4082).unwrap();
        assert_eq!(m, "bluetooth:v05A7p4082d0000");
        assert!(modalias(0xFFFF).is_none());
    }
}
