// Auto-detect paired BMAP devices via bluetoothctl.
#pragma once

#include <optional>
#include <string>

namespace bmap {

std::optional<std::string> find_bmap_device();

} // namespace bmap
