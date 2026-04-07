//! Bose device catalog — known BMAP-capable devices.
//!
//! Source: <https://downloads.bose.com/lookup.xml>

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
    BoseDevice { product_id: 0x4017, codename: "kleos",     name: "QuietComfort 35",                 category: Category::Headphones, config: Some("qc35") },
    BoseDevice { product_id: 0x4020, codename: "baywolf",   name: "QuietComfort 35 II",              category: Category::Headphones, config: Some("qc35") },
    BoseDevice { product_id: 0x4024, codename: "goodyear",  name: "Noise Cancelling Headphones 700", category: Category::Headphones, config: None },
    BoseDevice { product_id: 0x4061, codename: "vedder",    name: "QuietComfort 45",                 category: Category::Headphones, config: None },
    BoseDevice { product_id: 0x4082, codename: "wolverine", name: "QuietComfort Ultra Headphones",   category: Category::Headphones, config: Some("qc_ultra2") },
    // Earbuds
    BoseDevice { product_id: 0x4060, codename: "olivia",    name: "QuietComfort Earbuds II",         category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x4063, codename: "edith",     name: "Ultra Open Earbuds",              category: Category::Earbuds, config: None },
    BoseDevice { product_id: 0x4075, codename: "prince",    name: "QuietComfort Ultra Earbuds",      category: Category::Earbuds, config: None },
    // Speakers
    BoseDevice { product_id: 0x402D, codename: "revel",     name: "Home Speaker 300",                category: Category::Speaker, config: None },
    BoseDevice { product_id: 0x402F, codename: "lando",     name: "Portable Home Speaker",           category: Category::Speaker, config: None },
    BoseDevice { product_id: 0x4039, codename: "duran",     name: "SoundLink Flex",                  category: Category::Speaker, config: None },
    BoseDevice { product_id: 0x403A, codename: "gwen",      name: "SoundLink Revolve+ II",           category: Category::Speaker, config: None },
    BoseDevice { product_id: 0x4066, codename: "lonestarr", name: "SoundLink Max",                   category: Category::Speaker, config: None },
    BoseDevice { product_id: 0x4073, codename: "scotty",    name: "SoundLink Flex 2nd Gen",          category: Category::Speaker, config: None },
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
