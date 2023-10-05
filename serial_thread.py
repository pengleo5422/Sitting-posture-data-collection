from PyQt5 import QtCore
import threading
import serial
import math
import time

import wifi

import socket

class SerialThread(QtCore.QThread):
    def __init__(self) -> None:
        super().__init__()
        self.messages = []
        self.numerics = []
        self.running = True
        self.message_lock = threading.Lock()
        self.numeric_lock = threading.Lock()
    
    def run(self):
        pass
    
    def stop(self):
        self.running = False

class Mega2560SerialThread(SerialThread):
    def __init__(self, port, baud) -> None:
        super().__init__()
        self.port = port
        self.baud = baud
    
    def run(self):
        self.serial = serial.Serial(self.port, self.baud)
        while self.running:
            try:
                message = self.serial.readline()
                message = message.decode()
            except:
                message = str(message)
            numeric = []
            for sub in message.split(","):
                sub = sub.strip()
                try:
                    numeric.append(float(sub))
                except:
                    break
            else:
                self.numeric_lock.acquire()
                self.numerics.append(numeric)
                self.numeric_lock.release()
                continue
            self.message_lock.acquire()
            self.messages.append(message)
            self.message_lock.release()
    
    def stop(self):
        super().stop()
        if self.serial:
            self.serial.cancel_read()

class WifiThread(SerialThread):
    def __init__(self, SSID, pwd) -> None:
        super().__init__()
        self.mega_ssid = SSID
        self.mega_pwd = pwd
        self.target_ssid = None
        self.target_pwd = ""
    
    def run(self):
        success = False
        while not success:
            connections = wifi.Wifi.get_connections()
            for connection in connections:
                if connection.ssid == self.mega_ssid:
                    success = True
                    break
            else:
                if self.target_ssid:
                    wifi.Wifi.connect(self.mega_ssid, self.mega_pwd)
                elif connections:
                    profile = wifi.Wifi.get_profile(connections[0].ssid)
                    self.target_ssid = profile.ssid
                    self.target_pwd = profile.pwd
                else:
                    pass

            time.sleep(1)
        
        port = 8888
        ip_address = "ip address"

        success = False

        local_ip = socket.gethostbyname(socket.gethostname())
        local_port = 8888

        while not success:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.connect((ip_address, 8888))

                    sock.sendall(f"APdata:\n{self.target_ssid}\n{self.target_pwd}\n{local_ip}\n{local_port}".encode())
                    if sock.recv(1024).decode() == "received":
                        success = True
            except:
                pass
            
            time.sleep(1)
        
        while self.running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.bind((local_ip, local_port))
                    sock.listen(1)
                    conn, addr = sock.accept()
                    with conn:
                        while self.running:
                            data = conn.recv(1024)
                            if not data:
                                break
                            self.handle_data(data)
            except:
                pass
        
    def handle_data(self, data):
        try:
            message = data.decode()
        except:
            message = str(message)
        for line in message.splitlines():
            self.handle_line(line)

    def handle_line(self, message):
        numeric = []
        for sub in message.split(","):
            sub = sub.strip()
            try:
                numeric.append(float(sub))
            except:
                break
        else:
            self.numeric_lock.acquire()
            self.numerics.append(numeric)
            self.numeric_lock.release()
            return
        self.message_lock.acquire()
        self.messages.append(message)
        self.message_lock.release()
    
        



class TestSerialThread(SerialThread):
    def __init__(self) -> None:
        super().__init__()
        self.counter = 0
    
    def run(self):
        while self.running:
            self.message_lock.acquire()
            self.messages.append(f"test {self.counter}")
            self.message_lock.release()
            
            numeric = [math.sin(self.counter*math.pi/256 + (i*math.pi/4.5))*512+512 for i in range(9)]
            self.numeric_lock.acquire()
            self.numerics.append(numeric)
            self.numeric_lock.release()
            self.counter += 1
            self.counter %= 1024
            time.sleep(0.01)