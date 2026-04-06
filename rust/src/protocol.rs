//! Universal BMAP packet encoding and decoding.
//!
//! The BMAP framing is shared across all Bose Bluetooth devices.
//! This module handles packet construction and parsing with no
//! device-specific knowledge and no I/O.

/// BMAP operators.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Operator {
    Set = 0,
    Get = 1,
    SetGet = 2,
    Status = 3,
    Error = 4,
    Start = 5,
    Result = 6,
    Processing = 7,
}

impl Operator {
    pub fn from_u8(v: u8) -> Option<Self> {
        match v & 0x0F {
            0 => Some(Self::Set),
            1 => Some(Self::Get),
            2 => Some(Self::SetGet),
            3 => Some(Self::Status),
            4 => Some(Self::Error),
            5 => Some(Self::Start),
            6 => Some(Self::Result),
            7 => Some(Self::Processing),
            _ => None,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Self::Set => "SET",
            Self::Get => "GET",
            Self::SetGet => "SETGET",
            Self::Status => "STATUS",
            Self::Error => "ERROR",
            Self::Start => "START",
            Self::Result => "RESULT",
            Self::Processing => "PROCESSING",
        }
    }
}

/// BMAP error codes.
pub fn error_name(code: u8) -> &'static str {
    match code {
        0 => "Unknown",
        1 => "Length",
        2 => "Chksum",
        3 => "FblockNotSupp",
        4 => "FuncNotSupp",
        5 => "OpNotSupp(auth)",
        6 => "InvalidData",
        7 => "DataUnavail",
        8 => "Runtime",
        9 => "Timeout",
        10 => "InvalidState",
        15 => "InvalidTransition",
        20 => "InsecureTransport",
        _ => "Unknown",
    }
}

/// A parsed BMAP response.
#[derive(Debug, Clone)]
pub struct BmapResponse {
    pub fblock: u8,
    pub func: u8,
    pub op: Operator,
    pub payload: Vec<u8>,
}

impl BmapResponse {
    /// Format as human-readable string (e.g. "[31.3] RESULT: 00").
    pub fn fmt(&self) -> String {
        let hex: String = self.payload.iter().map(|b| format!("{:02x}", b)).collect();
        if self.op == Operator::Error && !self.payload.is_empty() {
            let err = error_name(self.payload[0]);
            format!("[{}.{}] {}: {} ({})", self.fblock, self.func, self.op.name(), err, hex)
        } else {
            format!("[{}.{}] {}: {}", self.fblock, self.func, self.op.name(), hex)
        }
    }
}

/// Build a BMAP packet from components.
pub fn bmap_packet(fblock: u8, func: u8, op: Operator, payload: &[u8]) -> Vec<u8> {
    let mut pkt = Vec::with_capacity(4 + payload.len());
    pkt.push(fblock);
    pkt.push(func);
    pkt.push(op as u8);
    pkt.push(payload.len() as u8);
    pkt.extend_from_slice(payload);
    pkt
}

/// Parse a single BMAP response from raw bytes.
pub fn parse_response(data: &[u8]) -> Option<BmapResponse> {
    if data.len() < 4 {
        return None;
    }
    let fblock = data[0];
    let func = data[1];
    let op = Operator::from_u8(data[2])?;
    let length = data[3] as usize;
    let end = std::cmp::min(4 + length, data.len());
    let payload = data[4..end].to_vec();
    Some(BmapResponse { fblock, func, op, payload })
}

/// Parse concatenated BMAP responses into a list.
pub fn parse_all_responses(data: &[u8]) -> Vec<BmapResponse> {
    let mut responses = Vec::new();
    let mut pos = 0;
    while pos + 4 <= data.len() {
        let fblock = data[pos];
        let func = data[pos + 1];
        let op = match Operator::from_u8(data[pos + 2]) {
            Some(op) => op,
            None => break,
        };
        let length = data[pos + 3] as usize;
        if pos + 4 + length > data.len() {
            break; // Truncated packet
        }
        let payload = data[pos + 4..pos + 4 + length].to_vec();
        responses.push(BmapResponse { fblock, func, op, payload });
        pos += 4 + length;
    }
    responses
}

/// Encode a mode name as a 32-byte null-terminated, null-padded array.
pub fn encode_mode_name(name: &str) -> [u8; 32] {
    let mut buf = [0u8; 32];
    let bytes = name.as_bytes();
    let end = std::cmp::min(bytes.len(), 31);
    buf[..end].copy_from_slice(&bytes[..end]);
    buf
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bmap_packet_get() {
        let pkt = bmap_packet(2, 2, Operator::Get, &[]);
        assert_eq!(pkt, vec![0x02, 0x02, 0x01, 0x00]);
    }

    #[test]
    fn test_bmap_packet_start() {
        let pkt = bmap_packet(31, 3, Operator::Start, &[0, 0]);
        assert_eq!(pkt, vec![0x1f, 0x03, 0x05, 0x02, 0x00, 0x00]);
    }

    #[test]
    fn test_parse_response() {
        let data = vec![31, 3, 0x06, 1, 0x00];
        let resp = parse_response(&data).unwrap();
        assert_eq!(resp.fblock, 31);
        assert_eq!(resp.func, 3);
        assert_eq!(resp.op, Operator::Result);
        assert_eq!(resp.payload, vec![0x00]);
    }

    #[test]
    fn test_parse_response_too_short() {
        assert!(parse_response(&[1, 2]).is_none());
    }

    #[test]
    fn test_parse_all_responses() {
        let mut data = vec![31, 6, 0x03, 2, 0xAA, 0xBB];
        data.extend_from_slice(&[31, 3, 0x06, 1, 0x00]);
        let responses = parse_all_responses(&data);
        assert_eq!(responses.len(), 2);
        assert_eq!(responses[0].func, 6);
        assert_eq!(responses[1].func, 3);
    }

    #[test]
    fn test_parse_all_truncated() {
        // Length says 10 bytes but only 2 available
        let data = vec![31, 3, 0x06, 10, 0x00, 0x01];
        let responses = parse_all_responses(&data);
        assert_eq!(responses.len(), 0);
    }

    #[test]
    fn test_encode_mode_name() {
        let buf = encode_mode_name("Custom");
        assert_eq!(buf.len(), 32);
        assert_eq!(&buf[..6], b"Custom");
        assert_eq!(buf[6], 0);
    }

    #[test]
    fn test_encode_mode_name_truncation() {
        let long = "A".repeat(50);
        let buf = encode_mode_name(&long);
        assert_eq!(buf.len(), 32);
        assert_eq!(buf[31], 0);
    }

    #[test]
    fn test_fmt_result() {
        let resp = BmapResponse {
            fblock: 31, func: 3, op: Operator::Result, payload: vec![0x00],
        };
        assert!(resp.fmt().contains("RESULT"));
    }

    #[test]
    fn test_fmt_error() {
        let resp = BmapResponse {
            fblock: 1, func: 5, op: Operator::Error, payload: vec![5],
        };
        let s = resp.fmt();
        assert!(s.contains("ERROR"));
        assert!(s.contains("auth"));
    }

    #[test]
    fn test_fmt_error_invalid_transition() {
        let resp = BmapResponse {
            fblock: 3, func: 2, op: Operator::Error, payload: vec![15],
        };
        let s = resp.fmt();
        assert!(s.contains("InvalidTransition"));
    }
}
