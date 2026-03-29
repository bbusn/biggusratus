# Ipconfig command - get network configuration.

import logging
from typing import Any, Dict, List

import netifaces

from client.commands.base import BaseCommand

logger = logging.getLogger(__name__)


class IpconfigCommand(BaseCommand):
    # Get network configuration for all interfaces.

    @property
    def name(self) -> str:
        return "ipconfig"

    @property
    def description(self) -> str:
        return "Get network configuration"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Execute the ipconfig command and return network interfaces.
        try:
            interfaces = self._get_all_interfaces()
            logger.info(f"Retrieved configuration for {len(interfaces)} network interfaces")
            return {
                "success": True,
                "interfaces": interfaces,
                "count": len(interfaces),
                "message": f"Found {len(interfaces)} network interface(s)",
            }
        except Exception as e:
            logger.error(f"Error getting network configuration: {e}")
            return self._error_response(f"Failed to get network configuration: {e}")

    def _get_all_interfaces(self) -> List[Dict[str, Any]]:
        # Get configuration for all network interfaces.
        interfaces = []
        interface_names = netifaces.interfaces()

        for interface_name in interface_names:
            interface_info = self._get_interface_info(interface_name)
            if interface_info:
                interfaces.append(interface_info)

        return interfaces

    def _get_interface_info(self, interface_name: str) -> Dict[str, Any]:
        # Get configuration for a single network interface.
        info: Dict[str, Any] = {
            "name": interface_name,
            "addresses": [],
            "gateway": None,
        }

        # Get addresses for each address family
        addrs = netifaces.ifaddresses(interface_name)

        # IPv4 addresses (AF_INET = 2)
        if netifaces.AF_INET in addrs:
            for addr_info in addrs[netifaces.AF_INET]:
                info["addresses"].append({
                    "family": "ipv4",
                    "address": addr_info.get("addr", ""),
                    "netmask": addr_info.get("netmask", ""),
                    "broadcast": addr_info.get("broadcast", ""),
                })

        # IPv6 addresses (AF_INET6 = 10)
        if netifaces.AF_INET6 in addrs:
            for addr_info in addrs[netifaces.AF_INET6]:
                # IPv6 addresses may have scope id after %
                addr = addr_info.get("addr", "")
                info["addresses"].append({
                    "family": "ipv6",
                    "address": addr,
                    "netmask": addr_info.get("netmask", ""),
                })

        # MAC addresses (AF_PACKET on Linux, AF_LINK on macOS/BSD)
        # AF_PACKET = 17, AF_LINK = 18
        for af in [17, 18]:
            if af in addrs:
                for addr_info in addrs[af]:
                    mac = addr_info.get("addr", "")
                    if mac:
                        info["mac_address"] = mac
                        break

        # Get gateway information
        try:
            gateways = netifaces.gateways()
            if "default" in gateways:
                default_gw = gateways["default"]
                # Check if this interface is the default gateway
                for af_family, gw_info in default_gw.items():
                    if gw_info[1] == interface_name:
                        info["gateway"] = gw_info[0]
                        info["default_gateway"] = True
        except Exception:
            pass

        return info

    def _error_response(self, message: str) -> Dict[str, Any]:
        # Create an error response.
        return {
            "success": False,
            "error": message,
        }
