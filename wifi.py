import tempfile

import os

import subprocess

import sys

import time

class WifiInterface:
    @classmethod
    def parse(cls, raw: str):
        name = None
        ssid = None
        bssid = None
        state = None
        for line in raw.splitlines():
            if " : " not in line:
                continue
            key, value = map(str.strip,line.split(" : ",1))
            if key == "名稱":
                name = value
            elif key == "SSID":
                ssid = value
            elif key == "狀態":
                state = value == "連線"
            elif key == "BSSID":
                bssid = value
        
        return cls(name, ssid, bssid, state)

    def __init__(self, name, ssid, bssid, state) -> None:
        self.name = name
        self.ssid = ssid
        self.bssid = bssid
        self.state = state

class WifiProfile:
    @classmethod
    def parse(cls, raw: str) -> 'WifiProfile':
        ssid = None
        pwd = None
        for line in raw.splitlines():
            if " : " not in line:
                continue
            key, value = map(str.strip,line.split(" : ",1))
            if key == "SSID 名稱":
                ssid = value[1:-1]
            elif key == "金鑰內容":
                pwd = value
        
        return cls(ssid, pwd)

    def __init__(self, ssid, pwd) -> None:
        self.ssid = ssid
        self.pwd = pwd
        pass

    def xml(self):
        return """
<?xml version=\"1.0\"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>"""+self.ssid+"""</name>
    <SSIDConfig>
        <SSID>
            <name>"""+self.ssid+"""</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>"""+self.pwd+"""</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>
"""

class Wifi:
    @classmethod
    def run(cls, *args, timeout: int = 3, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
                ['netsh'] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout, check=check, encoding=sys.stdout.encoding)

    @classmethod
    def get_interfaces(cls) -> list[WifiInterface]:
        raw = cls.run("wlan show interfaces").stdout
        return list(map(WifiInterface.parse,
                        [out for out in raw.split('\n\n') if out.startswith('    名稱')]))

    @classmethod
    def get_connections(cls) -> list[WifiInterface]:
        return list(filter(lambda i: i.state, cls.get_interfaces()))
    
    @classmethod
    def get_profile(cls, ssid) -> WifiProfile:
        raw = cls.run(f'wlan show profile name="{ssid}" key=clear').stdout
        return WifiProfile.parse(raw)
    
    @classmethod
    def gen_profile(cls, profile: WifiProfile):
        fd, path = tempfile.mkstemp()

        os.write(fd, profile.xml().encode())
        cls.run("wlan add profile filename=", path)
        os.close(fd)
        os.remove(path)
    
    @classmethod
    def connect(cls, ssid, pwd):
        original = cls.get_profile(ssid)
        if original.pwd != pwd:
            cls.gen_profile(WifiProfile(ssid, pwd))
        
        cls.run("wlan connect name=",ssid)