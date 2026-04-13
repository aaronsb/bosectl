"""Tests for the Bose device catalog."""

from pybmap.catalog import (
    BOSE_USB_VID, CATALOG, BoseDevice,
    lookup_device, known_devices, supported_devices,
    is_supported, usb_ids, modalias,
)


class TestLookup:
    def test_known_device(self):
        dev = lookup_device(0x4082)
        assert dev is not None
        assert dev.codename == "wolverine"
        assert dev.name == "QuietComfort Ultra Headphones (2nd Gen)"
        assert dev.config == "qc_ultra2"

    def test_qc35(self):
        dev = lookup_device(0x4020)
        assert dev.codename == "baywolf"
        assert dev.config == "qc35"

    def test_qc35_original(self):
        dev = lookup_device(0x400C)
        assert dev.codename == "wolfcastle"
        assert dev.config == "qc35"

    def test_qc_ultra2_earbuds(self):
        dev = lookup_device(0x4062)
        assert dev.codename == "edith"
        assert dev.config == "qc_ultra2"

    def test_unsupported_known(self):
        dev = lookup_device(0x4024)
        assert dev is not None
        assert dev.codename == "goodyear"
        assert dev.config is None

    def test_unknown(self):
        assert lookup_device(0xFFFF) is None


class TestSupport:
    def test_is_supported(self):
        assert is_supported(0x4082)  # wolverine
        assert is_supported(0x4062)  # edith
        assert is_supported(0x4020)  # baywolf
        assert is_supported(0x400C)  # wolfcastle

    def test_not_supported(self):
        assert not is_supported(0x4024)  # NCH 700
        assert not is_supported(0xFFFF)  # unknown

    def test_supported_devices(self):
        devs = supported_devices()
        assert len(devs) >= 4  # wolfcastle, baywolf, edith, wolverine
        assert all(d.config is not None for d in devs)

    def test_known_devices(self):
        devs = known_devices()
        assert len(devs) == len(CATALOG)


class TestUsbIds:
    def test_known(self):
        vid, pid = usb_ids(0x4082)
        assert vid == BOSE_USB_VID
        assert pid == 0x4082

    def test_unknown(self):
        assert usb_ids(0xFFFF) is None


class TestModalias:
    def test_known(self):
        m = modalias(0x4082)
        assert m == "bluetooth:v05A7p4082d0000"

    def test_qc35(self):
        m = modalias(0x4020)
        assert m == "bluetooth:v05A7p4020d0000"

    def test_unknown(self):
        assert modalias(0xFFFF) is None


class TestCatalogIntegrity:
    def test_no_duplicate_pids(self):
        pids = [d.product_id for d in CATALOG.values()]
        assert len(pids) == len(set(pids))

    def test_all_have_codename(self):
        for dev in CATALOG.values():
            assert dev.codename, "Device 0x%04x missing codename" % dev.product_id

    def test_all_have_name(self):
        for dev in CATALOG.values():
            assert dev.name, "Device 0x%04x missing name" % dev.product_id

    def test_vid_constant(self):
        assert BOSE_USB_VID == 0x05A7
