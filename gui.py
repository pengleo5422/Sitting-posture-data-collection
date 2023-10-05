import typing
from PyQt5.QtMultimedia import QAudioDeviceInfo, QAudio
from PyQt5.QtCore import QObject, pyqtSlot
from PyQt5 import uic
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QAction
import sounddevice as sd
import numpy as np
import queue
import matplotlib.ticker as ticker
from matplotlib.figure import Figure

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import sys
import os
import matplotlib
from PyQt5 import QtGui
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import *

import serial
import glob

import threading
import math
import time

from serial_thread import *
from ui.pressure_monitor import PressureMonitor
import ctypes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


# UAC重开
def uac_reload():
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit()

#uac_reload()


matplotlib.use("Qt5Agg")

bauds = (110, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 128000, 256000)

class ColorGradient:
    def __init__(self) -> None:
        self.colors = []

    def add_color(self, color, val):
        self.colors.append((color, val))
    
    def clear_color(self):
        self.colors = []
    
    def add_default_colors(self):
        self.add_color((0,0,0),0) #black
        self.add_color((0,0,255),1/6) #blue
        self.add_color((0,255,255),2/6) #cyan
        self.add_color((0,255,0), 3/6) #green
        self.add_color((255,255,0), 4/6) #yellow
        self.add_color((255,0,0), 5/6) #red
        self.add_color((255,255,255),1) #white
    
    def get_gradient_bar(self, size, vertical = True):
        grads = QtGui.QLinearGradient(0, 0, 0, 1) if vertical else QtGui.QLinearGradient(0, 0, 1, 0)
        reversed_grads = QtGui.QLinearGradient(0, 0, 0, 1) if vertical else QtGui.QLinearGradient(0, 0, 1, 0)
        grads.setCoordinateMode(grads.ObjectBoundingMode)
        reversed_grads.setCoordinateMode(reversed_grads.ObjectBoundingMode)
        for color, val in self.colors:
            grads.setColorAt(1-val, QColor(*color))
            reversed_grads.setColorAt(val, QColor(*color))
        pixmap = QtGui.QPixmap(*size)
        painter = QtGui.QPainter(pixmap)
        painter.fillRect(pixmap.rect(), reversed_grads)
        painter.fillRect(pixmap.rect().marginsRemoved(QtCore.QMargins(2,2,2,2)), grads)
        painter.end()
        bar = QLabel()
        bar.setPixmap(pixmap)
        #bar.setScaledContents(True)
        #bar.setMinimumSize(*size)
        #bar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        return bar

    def get_color(self, value):
        if not self.colors:
            return None

        for i, (color, val) in enumerate(self.colors):
            if value < val:
                diff = val - self.colors[i-1][1]
                fract = ((value-self.colors[i-1][1]) / diff) if diff else 0
                return tuple(int((color[j]-self.colors[i-1][0][j]) * fract + self.colors[i-1][0][j]) for j in range(3))
        return tuple(self.colors[-1][0][j] for j in range(3))

def serial_ports():
    """ Lists serial port names

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result: list[str] = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

class ScatterGraph(FigureCanvas):
    pass

class SelectCOMMenu(QMenu):
    def __init__(self, parent = None, callback=None):
        super().__init__("select COM", parent)
        self.callback = callback
        self.update_ports()
        
    def update_ports(self):
        self.clear()
        self.addAction("")
        for port in serial_ports():
            action = QAction(port)
            if self.callback:
                action.triggered.connect(self.callback)
            self.addAction(action)


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        self.resize(800, 600)

        self.color_gradient = ColorGradient()
        self.color_gradient.add_color((255,255,255),0) #white
        self.color_gradient.add_color((0,255,255),1/3) #cyan
        self.color_gradient.add_color((0,0,255),2/3) #blue
        self.color_gradient.add_color((0,0,0),1) #black

        menu = self.menuBar()

        self.serial_setting_menu = menu.addMenu("Serial setting")

        self.select_COM_menu = self.serial_setting_menu.addMenu("COM")
        self.update_ports()
        self.select_baud_menu = self.serial_setting_menu.addMenu("baud")

        for baud in bauds:
            action = self.select_baud_menu.addAction(str(baud))
            action.triggered.connect(self.baud_select)
        

        main_layout = QHBoxLayout()
        self.setCentralWidget(QWidget())
        self.centralWidget().setLayout(main_layout)

        communication_section = QVBoxLayout()
        self.logger = QPlainTextEdit()
        self.logger.setReadOnly(True)
        communication_section.addWidget(self.logger, 5)
        self.serial_input = QPlainTextEdit()
        communication_section.addWidget(self.serial_input, 1)
        main_layout.addLayout(communication_section, 10)

        pressure_layout = QGridLayout()
        #pressure_layout.setContentsMargins(2,2,2,2)
        #pressure_layout.setSpacing(2)
        zero_color = QColor(*self.color_gradient.get_color(0.0))
        one_color = QColor(*self.color_gradient.get_color(1.0))
        for i in range(3):
            for j in range(3):
                pressure_value = PressureMonitor()
                pressure_value.setFrameStyle(QFrame.Panel | QFrame.Sunken)
                pressure_layout.addWidget(pressure_value, i, j)
                """
                pressure_value = QLabel("0.0")
                pressure_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                pressure_value.setStyleSheet(f"background-color: {zero_color.name()}; color: {one_color.name()}")
                pressure_value.setFrameStyle(QFrame.Panel | QFrame.Sunken)
                pressure_layout.addWidget(pressure_value, i, j)
                """
        main_layout.addWidget(self.color_gradient.get_gradient_bar((30, 500)))
        main_layout.addLayout(pressure_layout, 10)
        self.pressure_layout = pressure_layout

        self.com = None
        self.baud = 115200

        self.serial_data = {"numeric":[0]*9, "string":[]}
        self.serial_thread = TestSerialThread()
        self.serial_thread.start()
        self.timer = QtCore.QTimer()
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.timer_tick)
        self.timer.start()

        self.show()
    
    def update_ports(self):
        self.select_COM_menu.clear()
        self.select_COM_menu.addAction(" ")
        for port in serial_ports():
            action = self.select_COM_menu.addAction(port)
            action.triggered.connect(self.COM_selected)
    
    def baud_select(self):
        action: QAction = self.sender()
        print("click", action.text())
        if self.serial_thread:
            self.serial_thread.stop()
        if self.com:
            self.serial_thread = Mega2560SerialThread(self.com, self.baud)
            self.serial_thread.start()

        
        
    def COM_selected(self):
        action: QAction = self.sender()
        self.com = action.text()
        if self.serial_thread:
            self.serial_thread.stop()
        self.serial_thread = Mega2560SerialThread(self.com, self.baud)
        self.serial_thread.start()
    
    def timer_tick(self):
        #self.update_ports()
        messages = self.serial_data["string"]
        if self.serial_thread:
            self.serial_thread.message_lock.acquire()
            messages.extend(self.serial_thread.messages)
            self.logger.appendPlainText("\n".join(self.serial_thread.messages))
            self.serial_thread.messages = []
            self.serial_thread.message_lock.release()
            self.serial_thread.numeric_lock.acquire()
            if self.serial_thread.numerics:
                self.serial_data["numeric"] = self.serial_thread.numerics[-1] + [0] * (9-len(self.serial_thread.numerics[-1]))
            self.serial_thread.numerics = []
            self.serial_thread.numeric_lock.release()
        if len(messages) > 10000:
            self.serial_data["string"] = messages[len(messages)-10000:]
        
        cursor = self.logger.textCursor()
        while self.logger.document().lineCount() > 10000:
            cursor.movePosition(QtGui.QTextCursor.Start)
            cursor.select(QtGui.QTextCursor.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
        
        #self.logger.setPlainText("\n".join(self.serial_data["string"]))
        
        for i in range(3):
            for j in range(3):
                index = i*3+j
                monitor: PressureMonitor = self.pressure_layout.itemAt(index).widget()
                pressure_value = self.serial_data["numeric"][index]
                monitor.add_pressure(pressure_value)
                """
                label: QLabel = self.pressure_layout.itemAt(index).widget()
                pressure_value = self.serial_data["numeric"][index]
                label.setText(f"{pressure_value :.1f}")
                background_color = self.color_gradient.get_color(pressure_value / 1024)
                font_color = QColor(*(255-background_color[k] for k in range(3)))
                background_color = QColor(*background_color)
                label.setStyleSheet(f"background-color: {background_color.name()}; color: {font_color.name()}")
                """
        
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mw = MainWindow()
    sys.exit(app.exec_())