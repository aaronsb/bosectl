"""Tests for Linux RFCOMM Bluetooth socket transport.

This module tests the Linux RfcommTransport class which uses Python's
socket module with AF_BLUETOOTH for raw RFCOMM communication.

These tests are designed to run on Linux systems with BlueZ support.
They do NOT require actual Bluetooth hardware — they use mocking to test
error handling, state management, and protocol compliance.
"""

import sys
import socket
import pytest
from unittest.mock import Mock, patch, MagicMock

# Only run on Linux
pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Only runs on Linux")

from pybmap.errors import BmapConnectionError, BmapTimeoutError
from pybmap.transport import RfcommTransport


@pytest.fixture(autouse=True)
def _no_stale_discard(request, monkeypatch):
    """Keep the pre-send discard out of tests that script recv() calls.

    TestLinuxTransportDiscardPending exercises it directly.
    """
    if request.cls is not None and request.cls.__name__ == "TestLinuxTransportDiscardPending":
        return
    monkeypatch.setattr(RfcommTransport, "_discard_pending", lambda self: None)


class TestLinuxTransportInitialization:
    """Test transport initialization and basic setup."""

    def test_init_with_defaults(self):
        """Test transport initialization with default parameters."""
        transport = RfcommTransport("68:F2:1F:00:00:00")
        assert transport.mac == "68:F2:1F:00:00:00"
        assert transport.channel == 2  # RFCOMM_CHANNEL
        assert transport.timeout == 3.0
        assert transport._sock is None

    def test_init_with_custom_channel(self):
        """Test transport initialization with custom RFCOMM channel."""
        transport = RfcommTransport("68:F2:1F:00:00:00", channel=8)
        assert transport.channel == 8

    def test_init_with_custom_timeout(self):
        """Test transport initialization with custom timeout."""
        transport = RfcommTransport("68:F2:1F:00:00:00", timeout=5.0)
        assert transport.timeout == 5.0


class TestLinuxTransportConnection:
    """Test socket connection and error handling."""

    @patch("socket.socket")
    def test_connect_success(self, mock_socket_class):
        """Test successful connection to device."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()

        # Verify socket was created with correct parameters
        mock_socket_class.assert_called_once_with(
            socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM
        )

        # Verify timeout was set
        mock_sock.settimeout.assert_called_with(3.0)

        # Verify connection was attempted
        mock_sock.connect.assert_called_once_with(("68:F2:1F:00:00:00", 2))

        # Verify socket is stored
        assert transport._sock is mock_sock

    @patch("socket.socket")
    def test_connect_error_carries_errno(self, mock_socket_class):
        """The probe's EBUSY/ECONNREFUSED backoff keys off this errno."""
        import errno
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = OSError(errno.EBUSY, "Device or resource busy")

        transport = RfcommTransport("00:11:22:33:44:55")
        with pytest.raises(BmapConnectionError) as exc_info:
            transport.connect()
        assert exc_info.value.errno == errno.EBUSY
        assert "Device or resource busy" in str(exc_info.value)

    @patch("socket.socket")
    def test_connect_invalid_mac_format(self, mock_socket_class):
        """Test connection with invalid MAC address format."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = OSError("Invalid MAC address")

        transport = RfcommTransport("invalid-mac")

        with pytest.raises(BmapConnectionError) as exc_info:
            transport.connect()

        error_msg = str(exc_info.value)
        assert "Failed to connect" in error_msg
        assert "invalid-mac" in error_msg
        assert transport._sock is None

    @patch("socket.socket")
    def test_connect_device_not_found(self, mock_socket_class):
        """Test connection when device is not found."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = OSError("No route to host")

        transport = RfcommTransport("00:11:22:33:44:55")

        with pytest.raises(BmapConnectionError) as exc_info:
            transport.connect()

        error_msg = str(exc_info.value)
        assert "Failed to connect" in error_msg
        assert transport._sock is None

    @patch("socket.socket")
    def test_connect_permission_denied(self, mock_socket_class):
        """Test connection when permission is denied (not in bluetooth group)."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = PermissionError("Operation not permitted")

        transport = RfcommTransport("68:F2:1F:00:00:00")

        with pytest.raises(BmapConnectionError) as exc_info:
            transport.connect()

        error_msg = str(exc_info.value)
        assert "Failed to connect" in error_msg
        assert transport._sock is None

    @patch("socket.socket")
    def test_connect_socket_creation_fails(self, mock_socket_class):
        """Test when socket creation itself fails."""
        mock_socket_class.side_effect = OSError("Protocol not supported")

        transport = RfcommTransport("68:F2:1F:00:00:00")

        with pytest.raises(BmapConnectionError) as exc_info:
            transport.connect()

        error_msg = str(exc_info.value)
        assert "Failed to connect" in error_msg
        assert transport._sock is None

    @patch("socket.socket")
    def test_connect_timeout_setting(self, mock_socket_class):
        """Test that connection timeout is properly set."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        transport = RfcommTransport("68:F2:1F:00:00:00", timeout=2.5)
        transport.connect()

        mock_sock.settimeout.assert_called_with(2.5)


class TestLinuxTransportClose:
    """Test socket cleanup and close behavior."""

    @patch("socket.socket")
    def test_close_connected_socket(self, mock_socket_class):
        """Test closing an active socket."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()
        transport.close()

        mock_sock.close.assert_called_once()
        assert transport._sock is None

    @patch("socket.socket")
    def test_close_socket_close_fails(self, mock_socket_class):
        """Test closing when socket.close() raises an error."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.close.side_effect = OSError("Bad file descriptor")

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()

        # Should not raise, just log the error
        transport.close()
        assert transport._sock is None

    def test_close_unconnected_socket(self):
        """Test closing when not connected."""
        transport = RfcommTransport("68:F2:1F:00:00:00")
        # Should not raise
        transport.close()
        assert transport._sock is None


class TestLinuxTransportContextManager:
    """Test context manager (with statement) behavior."""

    @patch("socket.socket")
    def test_context_manager_success(self, mock_socket_class):
        """Test context manager with successful connection."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        with RfcommTransport("68:F2:1F:00:00:00") as transport:
            assert transport._sock is mock_sock
            mock_sock.connect.assert_called_once()

        # Socket should be closed after context
        mock_sock.close.assert_called_once()

    @patch("socket.socket")
    def test_context_manager_connection_fails(self, mock_socket_class):
        """Test context manager when connection fails."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = OSError("Connection refused")

        with pytest.raises(BmapConnectionError):
            with RfcommTransport("68:F2:1F:00:00:00") as transport:
                pass

    @patch("socket.socket")
    def test_context_manager_with_exception(self, mock_socket_class):
        """Test that context manager cleans up even if exception occurs."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        try:
            with RfcommTransport("68:F2:1F:00:00:00") as transport:
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Socket should still be closed
        mock_sock.close.assert_called_once()


class TestLinuxTransportSendRecv:
    """Test packet sending and receiving."""

    @patch("socket.socket")
    @patch("time.sleep")
    def test_send_recv_success(self, mock_sleep, mock_socket_class):
        """Test successful send and receive."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        # Mock successful send
        mock_sock.send.return_value = 5

        # Mock response data
        response_data = b"\x1f\x01\x06\x02\x80\x64"
        mock_sock.recv.return_value = response_data

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()

        # Send packet
        request = b"\x1f\x01\x02\x02\x05\x00"
        result = transport.send_recv(request)

        # Verify send was called
        mock_sock.send.assert_called_with(request)

        # Verify sleep for protocol delay
        mock_sleep.assert_called_with(0.2)

        # Verify receive was called
        mock_sock.recv.assert_called()

        # Verify result
        assert result == response_data

    @patch("socket.socket")
    def test_send_recv_not_connected(self, mock_socket_class):
        """Test send_recv when not connected."""
        transport = RfcommTransport("68:F2:1F:00:00:00")

        with pytest.raises(BmapConnectionError) as exc_info:
            transport.send_recv(b"\x1f\x01\x02\x02\x05\x00")

        assert "Not connected" in str(exc_info.value)

    @patch("socket.socket")
    @patch("time.sleep")
    def test_send_recv_timeout(self, mock_sleep, mock_socket_class):
        """Test timeout when device does not respond."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.send.return_value = 5
        mock_sock.recv.side_effect = socket.timeout("Timeout")

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()

        with pytest.raises(BmapTimeoutError) as exc_info:
            transport.send_recv(b"\x1f\x01\x02\x02\x05\x00")

        assert "No response" in str(exc_info.value)

    @patch("socket.socket")
    @patch("time.sleep")
    def test_send_recv_communication_error(self, mock_sleep, mock_socket_class):
        """Test communication error handling."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.send.return_value = 5
        mock_sock.recv.side_effect = OSError("Broken pipe")

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()

        with pytest.raises(BmapConnectionError) as exc_info:
            transport.send_recv(b"\x1f\x01\x02\x02\x05\x00")

        error_msg = str(exc_info.value)
        assert "Communication error" in error_msg
        assert "Broken pipe" in error_msg

    @patch("socket.socket")
    @patch("time.sleep")
    def test_send_recv_send_fails(self, mock_sleep, mock_socket_class):
        """Test when send operation fails."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.send.side_effect = OSError("Connection reset")

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()

        with pytest.raises(BmapConnectionError) as exc_info:
            transport.send_recv(b"\x1f\x01\x02\x02\x05\x00")

        error_msg = str(exc_info.value)
        assert "Communication error" in error_msg


class TestLinuxTransportDrain:
    """Test packet draining for multi-response handling."""

    @patch("socket.socket")
    @patch("time.sleep")
    def test_send_recv_drain_single_response(self, mock_sleep, mock_socket_class):
        """Test drain mode with single response (no additional data)."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.send.return_value = 5

        # First recv returns data, second returns empty (EOF)
        mock_sock.recv.side_effect = [
            b"\x1f\x01\x06\x02\x80\x64",  # First response
            b"",  # Drain read returns empty
        ]

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()

        result = transport.send_recv(b"\x1f\x01\x02\x02\x05\x00", drain=True)

        assert result == b"\x1f\x01\x06\x02\x80\x64"

        # Verify timeout was changed for drain and restored
        calls = mock_sock.settimeout.call_args_list
        assert calls[0][0] == (3.0,)  # Initial
        assert calls[1][0] == (0.5,)  # Drain timeout
        assert calls[2][0] == (3.0,)  # Restored

    @patch("socket.socket")
    @patch("time.sleep")
    def test_send_recv_drain_multiple_responses(self, mock_sleep, mock_socket_class):
        """Test drain mode with multiple response packets."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.send.return_value = 5

        # Simulate receiving multiple responses
        mock_sock.recv.side_effect = [
            b"\x1f\x01\x06\x02\x80\x64",  # First response
            b"\x1f\x03\x06\x03\x01\x02\x03",  # Additional data 1
            b"\x1f\x05\x06\x02\x04\x05",  # Additional data 2
            socket.timeout("Drain timeout"),  # Drain ends with timeout
        ]

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()

        result = transport.send_recv(b"\x1f\x01\x02\x02\x05\x00", drain=True)

        expected = b"\x1f\x01\x06\x02\x80\x64\x1f\x03\x06\x03\x01\x02\x03\x1f\x05\x06\x02\x04\x05"
        assert result == expected

    @patch("socket.socket")
    @patch("time.sleep")
    def test_send_recv_drain_with_blocking_io_error(self, mock_sleep, mock_socket_class):
        """Test drain mode gracefully handles BlockingIOError."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.send.return_value = 5

        # First recv returns data, subsequent raises BlockingIOError
        mock_sock.recv.side_effect = [
            b"\x1f\x01\x06\x02\x80\x64",  # First response
            BlockingIOError("No data available"),  # Drain error
        ]

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()

        result = transport.send_recv(b"\x1f\x01\x02\x02\x05\x00", drain=True)

        assert result == b"\x1f\x01\x06\x02\x80\x64"


class TestLinuxTransportBufferManagement:
    """Test buffer size and data handling."""

    @patch("socket.socket")
    @patch("time.sleep")
    def test_send_recv_large_response(self, mock_sleep, mock_socket_class):
        """Test receiving large response packets."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.send.return_value = 5

        # Create a large response (close to 4096 buffer size)
        large_response = b"\x1f\x01\x06\x02" + (b"\x00" * 4000)
        mock_sock.recv.return_value = large_response

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()

        result = transport.send_recv(b"\x1f\x01\x02\x02\x05\x00")

        assert result == large_response
        assert len(result) == 4004

    @patch("socket.socket")
    @patch("time.sleep")
    def test_send_recv_empty_response(self, mock_sleep, mock_socket_class):
        """Test handling of empty response."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.send.return_value = 5
        mock_sock.recv.return_value = b""

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()

        result = transport.send_recv(b"\x1f\x01\x02\x02\x05\x00")
        assert result == b""


class TestLinuxTransportMultipleDevices:
    """Test handling multiple device connections."""

    @patch("socket.socket")
    def test_multiple_transport_instances(self, mock_socket_class):
        """Test that multiple transport instances don't interfere."""
        mock_sock1 = MagicMock()
        mock_sock2 = MagicMock()
        mock_socket_class.side_effect = [mock_sock1, mock_sock2]

        transport1 = RfcommTransport("68:F2:1F:00:00:00")
        transport2 = RfcommTransport("68:F2:1F:00:00:01")

        transport1.connect()
        transport2.connect()

        assert transport1._sock is mock_sock1
        assert transport2._sock is mock_sock2

        # Verify connections to different devices
        mock_sock1.connect.assert_called_with(("68:F2:1F:00:00:00", 2))
        mock_sock2.connect.assert_called_with(("68:F2:1F:00:00:01", 2))


class TestLinuxTransportIntegration:
    """Integration-style tests for common workflows."""

    @patch("socket.socket")
    @patch("time.sleep")
    def test_full_workflow(self, mock_sleep, mock_socket_class):
        """Test a complete workflow: connect, send/receive, disconnect."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.send.return_value = 5
        mock_sock.recv.return_value = b"\x1f\x01\x06\x02\x80\x64"

        with RfcommTransport("68:F2:1F:00:00:00") as transport:
            # Send status request
            result1 = transport.send_recv(b"\x1f\x01\x02\x02\x05\x00")
            assert result1 == b"\x1f\x01\x06\x02\x80\x64"

            # Send another command
            result2 = transport.send_recv(b"\x1f\x01\x02\x02\x07\x00")
            assert result2 == b"\x1f\x01\x06\x02\x80\x64"

        # Verify connection was closed
        mock_sock.close.assert_called_once()

    @patch("socket.socket")
    @patch("time.sleep")
    def test_rapid_reconnection(self, mock_sleep, mock_socket_class):
        """Test rapidly connecting and disconnecting."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        for i in range(3):
            transport = RfcommTransport("68:F2:1F:00:00:00")
            transport.connect()
            transport.close()

        # Should have created 3 sockets
        assert mock_socket_class.call_count == 3


class TestLinuxTransportDiscardPending:
    """Bytes left on the socket must not be read as the next reply."""

    @patch("socket.socket")
    @patch("time.sleep")
    def test_stale_bytes_dropped_before_send(self, mock_sleep, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        stale = b"\x1f\x03\x03\x01\x00"  # late [31.3] STATUS
        reply = b"\x02\x02\x03\x01\x50"
        mock_sock.recv.side_effect = [stale, BlockingIOError(), reply]

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()
        assert transport.send_recv(b"\x02\x02\x01\x00") == reply

        # Non-blocking during the discard, timeout restored before the send.
        timeouts = [c[0][0] for c in mock_sock.settimeout.call_args_list]
        assert timeouts == [3.0, 0, 3.0]

    @patch("socket.socket")
    @patch("time.sleep")
    def test_discard_is_bounded(self, mock_sleep, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = b"\x1f\x03\x03\x01\x00"

        transport = RfcommTransport("68:F2:1F:00:00:00")
        transport.connect()
        transport._discard_pending()
        assert mock_sock.recv.call_count == RfcommTransport._MAX_STALE_CHUNKS
