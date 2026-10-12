import pyvisa
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMessageBox


class SteppingMotor:
    def __init__(self):
        self.inst = None
        self.rm = pyvisa.ResourceManager()

    def gpib_conn(self, gpib_addr):
        self.inst = self.rm.open_resource(f'{gpib_addr}')
        self.inst.term_chars = "\r\n"
        self.inst.read_termination = '\n'
        return True

    def gpib_disconn(self):
        self.inst.close()
        return True
