// Auto-detect paired BMAP devices via bluetoothctl.
#pragma once

#include <optional>
#include <string>
#include <utility>

namespace bmap {

/// Auto-detect a paired, connected BMAP device.
/// Returns (mac, device_type) or nullopt.
std::optional<std::pair<std::string, std::string>> find_bmap_device();

} // namespace bmap
