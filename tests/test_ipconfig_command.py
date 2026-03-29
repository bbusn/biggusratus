# Tests for IpconfigCommand.

from unittest.mock import MagicMock, patch

import pytest

from client.commands.ipconfig import IpconfigCommand


class TestIpconfigCommand:
    # Test cases for IpconfigCommand.

    @pytest.fixture
    def command(self) -> IpconfigCommand:
        return IpconfigCommand()

    def test_name_property(self, command: IpconfigCommand) -> None:
        # Test that command name is 'ipconfig'.
        assert command.name == "ipconfig"

    def test_description_property(self, command: IpconfigCommand) -> None:
        # Test that description is returned.
        assert command.description == "Get network configuration"

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_returns_interfaces(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test that execute returns network interfaces.
        mock_netifaces.interfaces.return_value = ["lo", "eth0"]
        mock_netifaces.ifaddresses.return_value = {}
        mock_netifaces.gateways.return_value = {}

        result = command.execute({})

        assert result["success"] is True
        assert "interfaces" in result
        assert isinstance(result["interfaces"], list)
        assert len(result["interfaces"]) == 2

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_includes_interface_names(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test that interface names are included.
        mock_netifaces.interfaces.return_value = ["eth0", "wlan0"]
        mock_netifaces.ifaddresses.return_value = {}
        mock_netifaces.gateways.return_value = {}

        result = command.execute({})

        interface_names = [iface["name"] for iface in result["interfaces"]]
        assert "eth0" in interface_names
        assert "wlan0" in interface_names

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_ipv4_addresses(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test that IPv4 addresses are extracted.
        mock_netifaces.interfaces.return_value = ["eth0"]
        mock_netifaces.AF_INET = 2
        mock_netifaces.AF_INET6 = 10
        mock_netifaces.ifaddresses.return_value = {
            2: [{"addr": "192.168.1.100", "netmask": "255.255.255.0"}]
        }
        mock_netifaces.gateways.return_value = {}

        result = command.execute({})

        addresses = result["interfaces"][0]["addresses"]
        assert len(addresses) == 1
        assert addresses[0]["family"] == "ipv4"
        assert addresses[0]["address"] == "192.168.1.100"
        assert addresses[0]["netmask"] == "255.255.255.0"

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_ipv6_addresses(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test that IPv6 addresses are extracted.
        mock_netifaces.interfaces.return_value = ["eth0"]
        mock_netifaces.AF_INET = 2
        mock_netifaces.AF_INET6 = 10
        mock_netifaces.ifaddresses.return_value = {
            10: [{"addr": "fe80::1", "netmask": "64"}]
        }
        mock_netifaces.gateways.return_value = {}

        result = command.execute({})

        addresses = result["interfaces"][0]["addresses"]
        assert len(addresses) == 1
        assert addresses[0]["family"] == "ipv6"
        assert addresses[0]["address"] == "fe80::1"

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_mac_address_linux(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test that MAC address is extracted on Linux (AF_PACKET = 17).
        mock_netifaces.interfaces.return_value = ["eth0"]
        mock_netifaces.AF_INET = 2
        mock_netifaces.AF_INET6 = 10
        mock_netifaces.ifaddresses.return_value = {
            17: [{"addr": "00:11:22:33:44:55"}]
        }
        mock_netifaces.gateways.return_value = {}

        result = command.execute({})

        assert result["interfaces"][0]["mac_address"] == "00:11:22:33:44:55"

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_mac_address_macos(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test that MAC address is extracted on macOS (AF_LINK = 18).
        mock_netifaces.interfaces.return_value = ["en0"]
        mock_netifaces.AF_INET = 2
        mock_netifaces.AF_INET6 = 10
        mock_netifaces.ifaddresses.return_value = {
            18: [{"addr": "aa:bb:cc:dd:ee:ff"}]
        }
        mock_netifaces.gateways.return_value = {}

        result = command.execute({})

        assert result["interfaces"][0]["mac_address"] == "aa:bb:cc:dd:ee:ff"

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_gateway_detection(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test that default gateway is detected.
        mock_netifaces.interfaces.return_value = ["eth0"]
        mock_netifaces.ifaddresses.return_value = {}
        mock_netifaces.gateways.return_value = {
            "default": {2: ("192.168.1.1", "eth0")}
        }

        result = command.execute({})

        assert result["interfaces"][0]["gateway"] == "192.168.1.1"
        assert result["interfaces"][0]["default_gateway"] is True

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_multiple_interfaces(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test handling multiple interfaces with different configs.
        mock_netifaces.interfaces.return_value = ["lo", "eth0", "wlan0"]

        def mock_ifaddresses(interface: str):
            if interface == "eth0":
                return {2: [{"addr": "192.168.1.100", "netmask": "255.255.255.0"}]}
            elif interface == "wlan0":
                return {2: [{"addr": "10.0.0.50", "netmask": "255.0.0.0"}]}
            return {}

        mock_netifaces.ifaddresses.side_effect = mock_ifaddresses
        mock_netifaces.AF_INET = 2
        mock_netifaces.gateways.return_value = {}

        result = command.execute({})

        assert len(result["interfaces"]) == 3

        # Find each interface and check its address
        eth0 = next(i for i in result["interfaces"] if i["name"] == "eth0")
        wlan0 = next(i for i in result["interfaces"] if i["name"] == "wlan0")

        assert eth0["addresses"][0]["address"] == "192.168.1.100"
        assert wlan0["addresses"][0]["address"] == "10.0.0.50"

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_ignores_params(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test that execute ignores any passed params.
        mock_netifaces.interfaces.return_value = ["eth0"]
        mock_netifaces.ifaddresses.return_value = {}
        mock_netifaces.gateways.return_value = {}

        result1 = command.execute({})
        result2 = command.execute({"foo": "bar"})

        assert result1 == result2

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_returns_count(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test that count is returned correctly.
        mock_netifaces.interfaces.return_value = ["lo", "eth0", "wlan0"]
        mock_netifaces.ifaddresses.return_value = {}
        mock_netifaces.gateways.return_value = {}

        result = command.execute({})

        assert "count" in result
        assert result["count"] == 3

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_handles_exception(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test that exceptions are handled gracefully.
        mock_netifaces.interfaces.side_effect = OSError("Network error")

        result = command.execute({})

        assert result["success"] is False
        assert "error" in result
        assert "Network error" in result["error"]

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_broadcast_address(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test that broadcast address is included when available.
        mock_netifaces.interfaces.return_value = ["eth0"]
        mock_netifaces.AF_INET = 2
        mock_netifaces.ifaddresses.return_value = {
            2: [{"addr": "192.168.1.100", "netmask": "255.255.255.0", "broadcast": "192.168.1.255"}]
        }
        mock_netifaces.gateways.return_value = {}

        result = command.execute({})

        addresses = result["interfaces"][0]["addresses"]
        assert addresses[0]["broadcast"] == "192.168.1.255"

    @patch("client.commands.ipconfig.netifaces")
    def test_execute_gateway_exception_handling(
        self, mock_netifaces: MagicMock, command: IpconfigCommand
    ) -> None:
        # Test that gateway exceptions are handled without failing.
        mock_netifaces.interfaces.return_value = ["eth0"]
        mock_netifaces.ifaddresses.return_value = {}
        mock_netifaces.gateways.side_effect = Exception("Gateway error")

        result = command.execute({})

        # Should still succeed, just without gateway info
        assert result["success"] is True
        assert result["interfaces"][0].get("gateway") is None
