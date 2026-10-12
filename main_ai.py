import sys, time, nncam
import numpy as np
import math

import cv2
from PIL import ImageGrab
import serial, pyvisa, pickle
from vision import Vision
from multiprocessing.connection import Client

from ui_main import Ui_MainWindow
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QMenu, QWidget, QLabel, QPushButton, QVBoxLayout
from PyQt6.QtGui import QImage, QPixmap, QAction, QCursor, QPen, QColor, QPainter, QShortcut, QKeySequence
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint, QPointF, QRectF, QAbstractListModel, QModelIndex, QDateTime, QSignalBlocker
from PyQt6.QtTest import QTest

from flipper import Thorlabs_MFF101


class MainWindow(QMainWindow, Ui_MainWindow):
    evtCallback = pyqtSignal(int)
    useQThread = True

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        self.showMaximized()

        # Configuration
        self.load_config()
        self.client_socket = None
        self.short_delay = 500
        self.sutter_delay = 1000
        self.led_delay = 2000
        self.flip_delay = 3500
        self.subwindow_delay = 1000
        self.move_delay = 1000

        # Time (btw stage move and measurement)
        self.delay_time = 1000
        self.expose_time = 1000

        self.find_dot = False
        self.find_laser = False

        # Camera Val.
        self.hcam = None
        self.timer = QTimer(self)
        self.imgWidth = 0
        self.imgHeight = 0
        self.pData = None
        self.res = 0
        self.count = 0

        self.btn_open.clicked.connect(self.onBtnOpen)
        self.btn_setET.clicked.connect(lambda: self.onExpoTime(int(self.horizontalSlider_expotime.value())))
        self.btn_setEG.clicked.connect(lambda: self.onExpoGain(int(self.horizontalSlider_expogain.value())))

        self.timer.timeout.connect(self.onTimer)
        self.evtCallback.connect(self.onevtCallback)

        # Vision Val.
        self.val_thre_dot = float(self.thre_dots.text())
        self.val_thre_laser = float(self.thre_laser.text())
        self.points = []
        self.coordinate_model = None
        self.vision_laser_pos = False
        self.find_laser = False
        self.laser_dot = Vision('laser_dot.png')
        self.find_dot = False
        self.vision_dot = Vision('dot_img.png')
        self.pushButton_9.clicked.connect(self.thre_set)
        self.pushButton_10.clicked.connect(self.thre_set)
        self.pushButton_11.clicked.connect(self.ft_find_laser)
        self.pushButton_15.clicked.connect(self.toggle_find_laser)
        self.btn_find_dot.clicked.connect(self.toggle_find_dot)

        # Snipping Img Val.
        self.snipping_laser = False
        self.snipping_dot = False

        self.snippingWidget = SnippingWidget(app=QApplication.instance())
        self.snippingWidget.onSnippingCompleted = self.onSnippingCompleted
        self.btn_area_dot.clicked.connect(lambda: self.snipArea('dot'))
        self.btn_area_laser.clicked.connect(lambda: self.snipArea('laser'))

        # Flip Mount MFF101 Thorlabs
        self.mff101 = Thorlabs_MFF101()
        self.btn_flip_m90.clicked.connect(self.mff101_move1)
        self.btn_flip_p90.clicked.connect(self.mff101_move2)

        # LED Control Val.
        self.serial_connection = False
        self.btn_ledconn.clicked.connect(self.LED_connect)
        self.btn_LED_ON.clicked.connect(self.LED_on)
        self.btn_LED_OFF.clicked.connect(self.LED_off)
        self.btn_LEDBV_SET.clicked.connect(self.LED_bright)

        # Shutter Control Val.
        self.serial_connection_2 = False
        self.btn_shutter_conn.clicked.connect(self.shutter_conn)
        self.btn_shutter_time.clicked.connect(self.shutter_time)
        self.btn_shutter_oepn.clicked.connect(self.shutter_open)
        self.btn_shutter_close.clicked.connect(self.shutter_close)

        # Stepping Motor Controller
        self.inst = False
        self.btn_gpib_conn.clicked.connect(self.Gpib_conn)
        self.shortcut_key()
        self.btn_motor_read.clicked.connect(self.motor_read_s)
        self.btn_motor_init.clicked.connect(self.init_position)
        self.btn_goto_origin.clicked.connect(self.goto_origin)
        self.checkBox.stateChanged.connect(self.toggleLineEdit)

        # Start
        self.init_isOk = False
        self.laser_litho_spec_meas = False
        self.laser_litho_offset_time = 1000 # ADD Shutter delay time
        self.btn_start.clicked.connect(self.main_process_start)

        # Timer Setting
        self.startTime = None
        self.timer2 = QTimer()
        self.timer2.timeout.connect(self.updateProgress)

        # TCP/IP Comm.
        self.client_socket = None
        self.pushButton_14.clicked.connect(self.server_connect)
        self.btn_acq.clicked.connect(self.snap_spectrum)
        self.btn_read_frame.clicked.connect(self.read_spe)

        # Define digit patterns (simple example for 5x7 grid)
        self.braille_patterns = {
            '0': [0, 1, 0, 0, 1, 1],
            '1': [1, 0, 0, 0, 0, 0],
            '2': [1, 1, 0, 0, 0, 0],
            '3': [1, 0, 0, 0, 0, 1],
            '4': [1, 0, 0, 0, 1, 1],
            '5': [1, 0, 0, 0, 1, 0],
            '6': [1, 1, 0, 0, 0, 1],
            '7': [1, 1, 0, 0, 1, 0],
            '8': [1, 1, 0, 0, 1, 1],
            '9': [0, 1, 0, 0, 0, 1],
        }

    # 스테핑 모터 제어 함수 (cw/ccw 방향과 스텝 수를 전달)
    # def focus_move_motor(self, direction, steps):
    #     command = f'{direction},{steps}\n'
    #     ser.write(command.encode())
    #
    #     # 이동이 끝날 때까지 대기 (done 문자열을 기다림)
    #     while True:
    #         response = ser.readline().decode().strip()
    #         if response == 'done':
    #             break
    #         time.sleep(0.1)

    def focus_measure(self, image):
        # 이미지 사이즈를 줄입니다. (예: 50% 축소)
        resized_image = cv2.resize(image, (0, 0), fx=0.05, fy=0.05)

        # 라플라시안 변환을 적용하고 분산을 구합니다.
        laplacian_var = cv2.Laplacian(resized_image, cv2.CV_64F).var()
        # laplacian_var = cv2.Laplacian(image, cv2.CV_64F).var()  # Laplacian의 분산을 계산
        return laplacian_var

    # Function to draw a single digit
    # def draw_digit(self, digit, size):
    #     pattern = self.digit_patterns.get(digit, [])
    #     for steps, direction in pattern:
    #         self.shutter_open()
    #         if direction == 'right':
    #             # move_motor(stepper_x, steps * size, "forward")
    #             self.move_step('r', steps * size)
    #         elif direction == 'left':
    #             self.move_step('l', steps * size)
    #         elif direction == 'up':
    #             # move_motor(stepper_y, steps * size, "forward")
    #             self.move_step('u', steps * size)
    #         elif direction == 'down':
    #             # move_motor(stepper_y, steps * size, "backward")
    #             self.move_step('d', steps * size)
    #         self.shutter_close()

    def draw_braille_digit(self, digit, size):
        pattern = self.braille_patterns.get(digit, [])
        for i in range(3):
            if pattern[i]:
                self.shutter_open()
                QTest.qWait(int(self.lineEdit_shutter_time.text()))
            else:
                self.shutter_close()
            if i < 2:
                self.move_step('d', size)
        self.move_step('r', size)
        for i in range(3):
            if pattern[5 - i]:
                self.shutter_open()
                QTest.qWait(int(self.lineEdit_shutter_time.text()))
            else:
                self.shutter_close()
            if i < 2:
                self.move_step('u', size)

    # Function to draw a number
    def draw_number(self, number, size):
        number_str = str(number)
        for digit in number_str:
            self.draw_braille_digit(digit, size)
            # Move to the right before drawing the next digit
            self.move_step('r', size)
            # self.status_motor()
            QTest.qWait(2000)
        QTest.qWait(3000)
        self.goto_origin()
        QTest.qWait(2000)

    def thre_set(self):
        self.val_thre_dot = float(self.thre_dots.text())
        self.val_thre_laser = float(self.thre_laser.text())

    def ft_find_laser(self):
        self.vision_laser_pos = not self.vision_laser_pos

    def toggle_find_laser(self):
        self.find_laser = not self.find_laser

    def toggle_find_dot(self):
        self.find_dot = not self.find_dot

    def main_process_start(self):
        self.save_config()
        if self.rb_mapping.isChecked():
            self.mapping_start()
        elif self.rb_laser_litho.isChecked():
            self.laser_litho_start()

    def laser_litho_start(self):
        self.startProgress()
        size = int(self.label_31.text()) / 2
        self.move_step('d', size * 2)
        # Marking Number
        self.draw_number({int(self.lineEdit_shutter_time.text())}, abs(size))
        # Laser litho Init.
        # Get Val.
        x_value = int(self.spinBox.value())
        y_value = int(self.spinBox_2.value())
        total_point_no = x_value * y_value
        self.label_35.setText("[{}, {}] = Total Points # {}".format(
            x_value, y_value, total_point_no))
        self.progressBar.setValue(0)
        hx_val = int(self.label_26.text())
        hy_val = int(self.label_29.text())
        vx_val = int(self.label_31.text())
        vy_val = int(self.label_33.text())

        if self.laser_litho_spec_meas:
            # TODO: Check the spectrometer PC TCP/IP Connection
            # TODO: 2024 10. 4. Changed Eq. (spec. PI -> Andor)
            pass

        # if self.shutter_close():
        #     QTest.qWait(self.short_delay)
        #     if self.mff101_move1():
        #         QTest.qWait(self.short_delay)
        #         if self.LED_on():
        #             self.init_isOk = True

        self.init_isOk = True # debug mode
        if self.init_isOk:
            for j in range(y_value):
                for i in range(x_value):
                    self.label_35.setText("[{}, {}] = Total Points # {} / Curr. {}, {}".format(
                        x_value, y_value, total_point_no, (i + 1), (j + 1)))
                    pb_val = (j * x_value) + (i + 1)
                    if i != (x_value - 1):
                        self.mapping_move(hx_val, hy_val)
                        QTest.qWait(1000)
                        QTest.qWait(self.short_delay)
                        print(self.motor_read_s())
                        QTest.qWait(self.short_delay)
                        self.shutter_time()
                        QTest.qWait(int(self.lineEdit_shutter_time.text()) + self.laser_litho_offset_time)
                    self.progressBar.setValue(int(round(100 * (pb_val / total_point_no), 0)))
                QTest.qWait(self.delay_time)
                self.motor_read_s()
                QTest.qWait(self.short_delay)
                self.motor_read_s()
                QTest.qWait(self.short_delay)
                linex_val = int(self.label_19.text()) - vx_val * (j + 1)
                liney_val = int(self.label_21.text()) - vy_val * (j + 1)
                if j != (y_value - 1):
                    if j == 0:
                        self.mapping_move(-linex_val, -liney_val)
                        QTest.qWait(self.short_delay)
                        print(self.motor_read_s())
                        QTest.qWait(self.short_delay)
                        self.shutter_time()
                        QTest.qWait(int(self.lineEdit_shutter_time.text()) + self.laser_litho_offset_time)
                        const_x = linex_val
                        const_y = liney_val
                    else:
                        self.mapping_move(-const_x, -const_y)
                        QTest.qWait(self.short_delay)
                        print(self.motor_read_s())
                        QTest.qWait(self.short_delay)
                        self.shutter_time()
                        QTest.qWait(int(self.lineEdit_shutter_time.text()) + self.laser_litho_offset_time)
        else:
            QMessageBox.warning(self, "Warning", f"Failed to initialize eq.")

    def mapping_start(self):
        if self.client_socket is not None:
            x_value = int(self.spinBox.value())
            y_value = int(self.spinBox_2.value())
            total_point_no = x_value * y_value
            self.label_35.setText("[{}, {}] = Total Points # {}".format(
                x_value, y_value, total_point_no))
            self.progressBar.setValue(0)
            hx_val = int(self.label_26.text())
            hy_val = int(self.label_29.text())
            vx_val = int(self.label_31.text())
            vy_val = int(self.label_33.text())
            self.shutter_close()
            for j in range(y_value):
                self.find_laser = True
                QTest.qWait(self.short_delay)
                for i in range(x_value):
                    self.label_35.setText("[{}, {}] = Total Points # {} / Curr. {}, {}".format(
                        x_value, y_value, total_point_no, (i + 1), (j + 1)))
                    # self.find_laser = True
                    # QTest.qWait(self.short_delay)
                    pb_val = (j * x_value) + (i + 1)
                    self.shutter_close()
                    # Flip Mount Msg.
                    # self.show_message_box('Adjust Flip Mirror (SPEC.)')
                    QTest.qWait(self.sutter_delay)
                    self.find_laser = True
                    QTest.qWait(self.short_delay)
                    self.LED_off()
                    QTest.qWait(self.led_delay)
                    self.mff101_move2()
                    QTest.qWait(self.flip_delay)
                    self.snap_spectrum()
                    # self.show_message_box('Adjust Flip Mirror (IMG.)')
                    # QTest.qWait(3000)
                    self.LED_on()
                    QTest.qWait(self.led_delay)
                    self.mff101_move1()
                    QTest.qWait(self.flip_delay)
                    self.find_laser = True
                    QTest.qWait(self.short_delay)

                    if i != (x_value - 1):
                        # Stutter Close
                        self.shutter_open()
                        QTest.qWait(self.sutter_delay)
                        self.mapping_move(hx_val, hy_val)
                        self.find_dot = True
                        QTest.qWait(self.move_delay)
                        # Move to Closet point
                        # TODO : DIS. 100넘어 갈때 건너 띄기
                        if [i, j] not in self.except_point:
                            for i in range(3):
                                # TODO : Error Flip mirror 안올라 오는 경우
                                self.cal_closest_dot()
                                distance = float(self.label_78.text())
                                QTest.qWait(self.short_delay)
                                if distance < 100:
                                    self.move_closest_dot()
                                    QTest.qWait(self.short_delay)
                                else:
                                    if self.not_find_img:
                                        break
                                    else:
                                        self.w = AnotherWindow()
                                        self.w.show()
                                        print(self.w.isVisible())
                                        while 1:
                                            if self.w.isVisible():
                                                pass
                                            else:
                                                break
                                            QTest.qWait(self.subwindow_delay)
                                        break
                            QTest.qWait(self.short_delay)
                        self.find_dot = False
                        # Stutter Open
                        self.shutter_close()
                    self.progressBar.setValue(int(round(100 * (pb_val / total_point_no), 0)))
                QTest.qWait(self.delay_time)
                self.motor_read_s()
                QTest.qWait(self.short_delay)
                self.motor_read_s()
                QTest.qWait(self.short_delay)
                linex_val = int(self.label_19.text()) - vx_val * (j + 1)
                liney_val = int(self.label_21.text()) - vy_val * (j + 1)
                # print(linex_val, liney_val)
                self.shutter_open()
                QTest.qWait(self.sutter_delay)
                if j != (y_value - 1):
                    if j == 0:
                        self.mapping_move(-linex_val, -liney_val)
                        const_x = linex_val
                        const_y = liney_val
                    else:
                        self.mapping_move(-const_x, -const_y)
                ## ADD
                self.find_dot = True
                QTest.qWait(self.move_delay)
                # Move to Closet point
                if [i, j] not in self.except_point:
                    for i in range(3):
                        self.cal_closest_dot()
                        distance = float(self.label_78.text())
                        if distance < 100:
                            self.move_closest_dot()
                            QTest.qWait(self.short_delay)
                        else:
                            if self.not_find_img:
                                break
                            else:
                                self.w = AnotherWindow()
                                self.w.show()
                                print(self.w.isVisible())
                                while 1:
                                    if self.w.isVisible():
                                        pass
                                    else:
                                        break
                                    QTest.qWait(self.subwindow_delay)
                                break
                    QTest.qWait(self.short_delay)
                self.find_dot = False
                ###
                QTest.qWait(self.delay_time)
        else:
            self.show_message_box('Connect Server')

    def mapping_move(self, x_value, y_value):
        QTest.qWait(100)
        self.inst.write("{}".format('a1?s'))
        previous_data = self.inst.read()
        QTest.qWait(100)
        if y_value < 0:
            self.inst.write("X#P{}DG".format(y_value))
        elif y_value == 0:
            pass
        else:
            self.inst.write("X#P{}UG".format(y_value))
        # Need for delay
        self.status_motor(previous_data, "X")
        QTest.qWait(100)
        self.inst.write("{}".format('a2?s'))
        previous_data = self.inst.read()
        QTest.qWait(100)
        if x_value < 0:
            self.inst.write("Y#P{}DG".format(x_value))
        elif x_value == 0:
            pass
        else:
            self.inst.write("Y#P{}UG".format(x_value))
        QTest.qWait(100)
        self.status_motor(previous_data, "Y")
        QTest.qWait(100)
        # print(f'Move : {x_value}, {y_value}')

    def read_spe(self):
        self.client_socket.send('read')
        # print('Received data list:', self.client_socket.recv())
        recv_data = self.client_socket.recv()
        self.x_data = recv_data[0]
        self.x_data = [round(num, 2) for num in self.x_data] # .xx
        self.y_data = recv_data[1]
        # print(self.x_data)
        # print(self.y_data)
        self.plot_spe(x_data=self.x_data, y_data=self.y_data)

    def save_config(self):
        config_list = ([self.lineEdit_2.text(), self.lineEdit_6.text(),
                        self.lineEdit_3.text(), self.lineEdit_7.text(),
                        self.lineEdit_8.text(), self.lineEdit_4.text(),
                        self.spinBox.value(), self.spinBox_2.value(),
                        self.label_26.text(), self.label_29.text(),
                        self.label_31.text(), self.label_33.text()])
        with open('config.pkl', 'wb') as file:
            pickle.dump(config_list, file)

    def load_config(self):
        with open('config.pkl', 'rb') as file:
            config_list = pickle.load(file)
        obj_list = ([self.lineEdit_2, self.lineEdit_6,
                     self.lineEdit_3, self.lineEdit_7,
                     self.lineEdit_8, self.lineEdit_4,
                     self.spinBox, self.spinBox_2])
        for i in range(6):
            obj_list[i].setText(config_list[i])
        obj_list[6].setValue(config_list[6])
        obj_list[7].setValue(config_list[7])
        self.label_26.setText("{}".format(config_list[8]))
        self.label_29.setText("{}".format(config_list[9]))
        self.label_31.setText("{}".format(config_list[10]))
        self.label_33.setText("{}".format(config_list[11]))

    def gpib_conn_obj(self, bool_val):
        self.btn_left.setEnabled(bool_val)
        self.btn_up.setEnabled(bool_val)
        self.btn_down.setEnabled(bool_val)
        self.btn_right.setEnabled(bool_val)
        self.btn_sw.setEnabled(bool_val)
        self.btn_sw_2.setEnabled(bool_val)
        self.btn_sw_3.setEnabled(bool_val)
        self.btn_motor_init.setEnabled(bool_val)
        self.btn_motor_read.setEnabled(bool_val)
        self.btn_goto_origin.setEnabled(bool_val)
        self.spinBox.setEnabled(bool_val)
        self.spinBox_2.setEnabled(bool_val)
        self.pushButton_3.setEnabled(bool_val)
        self.pushButton_4.setEnabled(bool_val)
        self.btn_3_move.setEnabled(bool_val)
        self.radioButton.setEnabled(bool_val)
        self.radioButton_2.setEnabled(bool_val)
        self.radioButton_3.setEnabled(bool_val)
        self.radioButton_4.setEnabled(bool_val)
        self.radioButton_5.setEnabled(bool_val)
        self.radioButton_6.setEnabled(bool_val)
        self.lineEdit_2.setEnabled(bool_val)
        self.lineEdit_3.setEnabled(bool_val)
        self.lineEdit_8.setEnabled(bool_val)
        self.lineEdit_6.setEnabled(bool_val)
        self.lineEdit_7.setEnabled(bool_val)
        self.lineEdit_4.setEnabled(bool_val)
        self.label_26.setEnabled(bool_val)
        self.label_29.setEnabled(bool_val)
        self.label_31.setEnabled(bool_val)
        self.label_33.setEnabled(bool_val)

    def Gpib_conn(self):
        if str(self.btn_gpib_conn.text()) == 'Connect':
            try:
                rm = pyvisa.ResourceManager()
                self.inst = rm.open_resource(f'{self.lineEdit_gpib.text()}')
                self.inst.term_chars = "\r\n"
                self.inst.read_termination = '\n'
                self.inst.write("{}".format('a1?s'))
                previous_data = self.inst.read()
                QTest.qWait(100)
                self.gpib_conn_obj(True)
                self.btn_gpib_conn.setText('Disconnect')
            except pyvisa.errors.VisaIOError as e:
                QMessageBox.warning(self, "Warning", f"Failed to connect Stepping Motor Controller\n\n{e}")
        else:
            self.gpib_conn_obj(False)
            self.inst.close()
            self.btn_gpib_conn.setText('Connect')

    def shutter_conn(self):
        if str(self.btn_shutter_conn.text()) == 'Connect':
            try:
                self.lineEdit_shutter_time.setEnabled(True)
                self.btn_shutter_time.setEnabled(True)
                self.btn_shutter_oepn.setEnabled(True)
                self.btn_shutter_close.setEnabled(True)
                port = str(self.lineEdit_shutter_port.text())
                self.serial_connection_2 = serial.Serial(port, baudrate=115200, timeout=8)
                self.btn_shutter_conn.setText('Disconnect')
            except serial.serialutil.SerialException as e:
                QMessageBox.warning(self, "Warning", f"Failed to connect Shutter.\n\n{e}")
        else:
            self.lineEdit_shutter_time.setEnabled(False)
            self.btn_shutter_time.setEnabled(False)
            self.btn_shutter_oepn.setEnabled(False)
            self.btn_shutter_close.setEnabled(False)
            self.serial_connection_2.close()
            self.btn_shutter_conn.setText('Connect')

    def shutter_open(self):
        if str(self.btn_shutter_conn.text()) == 'Disconnect':
            # self.serial_connection_2.write(bytes('60,0\r\n', encoding='ascii'))
            self.serial_connection_2.write(bytes('open,0\r\n', encoding='ascii'))
            self.serial_connection_2.flush()
            line = self.serial_connection_2.readline()
            print(line)
            return True
        else:
            QMessageBox.warning(self, "Warning", f"Failed to connect Shutter. Click the Shutter connect btn")
            return False

    def shutter_close(self):
        if str(self.btn_shutter_conn.text()) == 'Disconnect':
            # self.serial_connection_2.write(bytes('80,0\r\n', encoding='ascii'))
            self.serial_connection_2.write(bytes('close,0\r\n', encoding='ascii'))
            self.serial_connection_2.flush()
            line = self.serial_connection_2.readline()
            print(line)
            return True
        else:
            QMessageBox.warning(self, "Warning", f"Failed to connect Shutter. Click the Shutter connect btn")
            return False

    def shutter_time(self):
        if str(self.btn_shutter_conn.text()) == 'Disconnect':
            # self.serial_connection_2.write(bytes(f'60,{self.lineEdit_shutter_time.text()}\r\n', encoding='ascii'))
            self.serial_connection_2.write(bytes(f'open,{self.lineEdit_shutter_time.text()}\r\n', encoding='ascii'))
            line = self.serial_connection_2.readline()
            print(line)
        else:
            QMessageBox.warning(self, "Warning", f"Failed to connect Shutter. Click the Shutter connect btn")

    def LED_connect(self):
        if str(self.btn_ledconn.text()) == 'Connect':
            try:
                self.lineEdit_LEDBV.setEnabled(True)
                self.btn_LEDBV_SET.setEnabled(True)
                self.btn_LED_ON.setEnabled(True)
                self.btn_LED_OFF.setEnabled(True)
                port = str(self.lineEdit_ledport.text())
                self.serial_connection = serial.Serial(port, baudrate=115200)
                self.btn_ledconn.setText('Disconnect')
            except serial.serialutil.SerialException as e:
                QMessageBox.warning(self, "Warning", f"Failed to connect RED LED.\n\n{e}")
        else:
            self.lineEdit_LEDBV.setEnabled(False)
            self.btn_LEDBV_SET.setEnabled(False)
            self.btn_LED_ON.setEnabled(False)
            self.btn_LED_OFF.setEnabled(False)
            self.serial_connection.close()
            self.btn_shutter_conn.setText('Connect')

    def LED_on(self):
        if str(self.btn_ledconn.text()) == 'Disconnect':
            self.serial_connection.write(bytes('on\r\n', encoding='ascii'))
            return True
        else:
            QMessageBox.warning(self, "Warning", f"Failed to connect RED LED. Click the LED connect btn")
            return False

    def LED_off(self):
        self.serial_connection.write(bytes('off\r\n', encoding='ascii'))

    def LED_bright(self):
        pass
        #self.serial_connection.write(bytes(f'{self.lineEdit_LEDBV.text()}', encoding='ascii'))

    def onSnippingCompleted(self, frame):
        self.setWindowState(Qt.WindowState.WindowActive)
        if frame is None:
            return
        image = QImage(frame, frame.shape[1], frame.shape[0], frame.strides[0], QImage.Format.Format_RGB888)
        if self.snipping_laser:
            image.save('laser_dot.png')
            self.laser_dot = Vision('laser_dot.png')
            pixmap = QPixmap.fromImage(image)
            # self._pixmap = self.resizeImage(pixmap)
            self.label_img_laser.setPixmap(pixmap)
            self.snipping_laser = False
        elif self.snipping_dot:
            image.save('dot_img.png')
            self.vision_dot = Vision('dot_img.png')
            pixmap = QPixmap.fromImage(image)
            # self._pixmap = self.resizeImage(pixmap)
            self.label_img_dot.setPixmap(pixmap)
            self.snipping_dot = False

    def snipArea(self, find):
        if find == 'dot':
            self.snipping_dot = True
        elif find == 'laser':
            self.snipping_laser = True
        # self.setWindowState(Qt.WindowState.WindowMinimized)
        self.snippingWidget.start()

    def mff101_move1(self):
        self.mff101.mirror('on')
        return True

    def mff101_move2(self):
        self.mff101.mirror('off')
        return True

    def onTimer(self):
        if self.hcam:
            nFrame, nTime, nTotalFrame = self.hcam.get_FrameRate()
            self.lbl_frame.setText("{}, fps = {:.1f}".format(nTotalFrame, nFrame * 1000.0 / nTime))

    def closeCamera(self):
        if self.hcam:
            self.hcam.Close()
        self.hcam = None
        self.pData = None

        self.btn_open.setText("Camera Open")
        # self.timer.stop()
        self.lbl_frame.clear()
        self.lbl_frame.setText("State : Camera Stop")
        # self.cbox_auto.setEnabled(False)
        # self.slider_expoGain.setEnabled(False)
        # self.slider_expoTime.setEnabled(False)
        # self.btn_autoWB.setEnabled(False)
        # self.slider_temp.setEnabled(False)
        # self.slider_tint.setEnabled(False)
        # self.btn_snap.setEnabled(False)
        # self.cmb_res.setEnabled(False)
        # self.cmb_res.clear()

    def onExpoTime(self, value):
        if self.hcam:
            self.hcam.put_ExpoTime(value)

    def onExpoGain(self, value):
        if self.hcam:
            self.hcam.put_ExpoAGain(value)

    def startCamera(self):
        self.pData = bytes(nncam.TDIBWIDTHBYTES(self.imgWidth * 24) * self.imgHeight)
        uimin, uimax, uidef = self.hcam.get_ExpTimeRange()
        self.label_expotr.setText(f'[{uimin} - {uimax}]')
        usmin, usmax, usdef = self.hcam.get_ExpoAGainRange()
        self.label_expogr.setText(f'[{usmin} - {usmax}]')
        self.handleExpoEvent()
        if self.cur.model.flag & nncam.NNCAM_FLAG_MONO == 0:
            self.handleTempTintEvent()
        try:
            self.hcam.StartPullModeWithCallback(self.eventCallBack, self)
        except nncam.HRESULTException:
            self.closeCamera()
            QMessageBox.warning(self, "Warning", "Failed to start camera.")
        else:
            # self.cmb_res.setEnabled(True)
            # self.cbox_auto.setEnabled(True)
            self.btn_open.setText("Camera Close")
            # self.btn_snap.setEnabled(True)
            bAuto = self.hcam.get_AutoExpoEnable()
            # self.cbox_auto.setChecked(1 == bAuto)
            self.timer.start(1000)

    def openCamera(self):
        self.hcam = nncam.Nncam.Open(self.cur.id)
        if self.hcam:
            self.res = self.hcam.get_eSize()
            self.imgWidth = self.cur.model.res[self.res].width
            self.imgHeight = self.cur.model.res[self.res].height
            # with QSignalBlocker(self.cmb_res):
            #     self.cmb_res.clear()
            #     for i in range(0, self.cur.model.preview):
            #         self.cmb_res.addItem("{}*{}".format(self.cur.model.res[i].width, self.cur.model.res[i].height))
            #     self.cmb_res.setCurrentIndex(self.res)
            #     self.cmb_res.setEnabled(True)
            self.hcam.put_Option(nncam.NNCAM_OPTION_BYTEORDER, 0) #Qimage use RGB byte order
            self.hcam.put_AutoExpoEnable(0)
            self.hcam.put_Chrome(1)
            self.hcam.put_Contrast(150)
            self.hcam.put_ExpoTime(50000)
            self.hcam.put_ExpoAGain(200)
            self.startCamera()

    def onBtnOpen(self):
        if self.hcam:
            self.closeCamera()
        else:
            arr = nncam.Nncam.EnumV2()
            if 0 == len(arr):
                QMessageBox.warning(self, "Warning", "No camera found.")
            elif 1 == len(arr):
                self.cur = arr[0]
                self.openCamera()
            else:
                menu = QMenu()
                for i in range(0, len(arr)):
                    action = QAction(arr[i].displayname, self)
                    action.setData(i)
                    menu.addAction(action)
                action = menu.exec(self.mapToGlobal(self.btn_open.pos()))
                if action:
                    self.cur = arr[action.data()]
                    self.openCamera()

    @staticmethod
    def eventCallBack(nEvent, self):
        '''callbacks come from nncam.dll/so internal threads, so we use qt signal to post this event to the UI thread'''
        self.evtCallback.emit(nEvent)

    def onevtCallback(self, nEvent):
        '''this run in the UI thread'''
        if self.hcam:
            if nncam.NNCAM_EVENT_IMAGE == nEvent:
                self.handleImageEvent()
            elif nncam.NNCAM_EVENT_EXPOSURE == nEvent:
                self.handleExpoEvent()
            elif nncam.NNCAM_EVENT_TEMPTINT == nEvent:
                self.handleTempTintEvent()
            elif nncam.NNCAM_EVENT_STILLIMAGE == nEvent:
                self.handleStillImageEvent()
            elif nncam.NNCAM_EVENT_ERROR == nEvent:
                self.closeCamera()
                QMessageBox.warning(self, "Warning", "Generic Error.")
            elif nncam.NNCAM_EVENT_STILLIMAGE == nEvent:
                self.closeCamera()
                QMessageBox.warning(self, "Warning", "Camera disconnect.")

    def qimage_to_np_array(self, qimage):
        # Ensure QImage is in the correct format
        qimage = qimage.convertToFormat(QImage.Format.Format_RGB32)
        width = qimage.width()
        height = qimage.height()

        ptr = qimage.bits()
        ptr.setsize(qimage.sizeInBytes())

        arr = np.array(ptr).reshape(height, width, 4)  # 4 channels for Format_RGB32
        return arr

    def np_array_to_qimage(self, arr):
        height, width, channel = arr.shape
        bytes_per_line = channel * width
        qimage = QImage(arr.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        return qimage

    def qimage_to_cv2(self, qimage):
        qimage = qimage.convertToFormat(QImage.Format.Format_RGB888)
        width = qimage.width()
        height = qimage.height()
        ptr = qimage.bits()
        ptr.setsize(qimage.sizeInBytes())  # sizeInBytes()로 수정
        arr = np.array(ptr).reshape(height, width, 3)  # RGB888 포맷에 맞게 변환
        return arr

    def handleImageEvent(self):
        try:
            self.hcam.PullImageV3(self.pData, 0, 24, 0, None)
        except nncam.HRESULTException:
            pass
        else:
            image = QImage(self.pData, self.imgWidth, self.imgHeight, QImage.Format.Format_RGB888)
            lv = self.focus_measure(self.qimage_to_cv2(image))
            lv = round(lv, 2)
            newimage = image.scaled(self.lbl_video.width(), self.lbl_video.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            newimage_np = self.qimage_to_np_array(newimage)
            newimage_np = cv2.cvtColor(newimage_np, cv2.COLOR_RGBA2BGR)

            if self.find_laser:
                laser_point = self.laser_dot.find(newimage_np, self.val_thre_laser, 'points')
                print(laser_point)
                print(len(laser_point))
                if len(laser_point) == 1:
                    self.lp_x.setValue(int(laser_point[0][0]))
                    self.lp_y.setValue(int(laser_point[0][1]))
                self.find_laser = False

            if self.find_dot:
                self.points = self.vision_dot.find(newimage_np, self.val_thre_dot, 'points')
                self.label_no_dots.setText('{}'.format(len(self.points)))
                self.coordinate_model = CoordinateListModel(self.points)
                self.listView.setModel(self.coordinate_model)
            else:
                if len(self.points) > 0:
                    for (x, y) in self.points:
                        newimage_np = cv2.line(newimage_np, (x - 10, y), (x + 10, y), (0, 255, 0), 1)  # 수평 십자가 라인
                        newimage_np = cv2.line(newimage_np, (x, y - 10), (x, y + 10), (0, 255, 0), 1)  # 수직 십자가 라인
                else:
                    # print('Not find points.')
                    pass

            if self.vision_laser_pos:
                x = self.lp_x.value()
                y = self.lp_y.value()
                radius = 10
                color = (255, 255, 255)  # White color
                thickness = 1  # Set to -1 to fill the circle
                # Draw circle and cross lines
                newimage_np = cv2.circle(newimage_np, (x, y), radius, color, thickness)
                newimage_np = cv2.line(newimage_np, (x - 50, y), (x + 50, y), color, thickness)
                newimage_np = cv2.line(newimage_np, (x, y - 50), (x, y + 50), color, thickness)

            # 텍스트 삽입
            text = "Laplcian Var : {}".format(lv)
            org = (20, 50)  # 텍스트 위치
            font = cv2.FONT_HERSHEY_SIMPLEX
            fontScale = 1
            color = (255, 255, 255)  # 흰색
            thickness = 2

            # 텍스트를 이미지에 삽입
            newimage_np = cv2.putText(newimage_np, text, org, font, fontScale, color, thickness)

            # Convert BGR (OpenCV) to RGB (QImage)
            newimage_np = cv2.cvtColor(newimage_np, cv2.COLOR_BGR2RGB)

            # Convert NumPy array back to QImage
            newimage = self.np_array_to_qimage(newimage_np)

            self.lbl_video.setPixmap(QPixmap.fromImage(newimage))

    def handleExpoEvent(self):
        time = self.hcam.get_ExpoTime()
        gain = self.hcam.get_ExpoAGain()
        # with QSignalBlocker(self.slider_expoTime):
        #     self.slider_expoTime.setValue(time)
        # with QSignalBlocker(self.slider_expoGain):
        #     self.slider_expoGain.setValue(gain)
        # self.lbl_expoTime.setText(str(time))
        self.horizontalSlider_expotime.setValue(int(time))
        # self.lbl_expoGain.setText(str(gain))
        self.horizontalSlider_expogain.setValue(int(gain))

    def handleTempTintEvent(self):
        nTemp, nTint = self.hcam.get_TempTint()
        # with QSignalBlocker(self.slider_temp):
        #     self.slider_temp.setValue(nTemp)
        # with QSignalBlocker(self.slider_tint):
        #     self.slider_tint.setValue(nTint)
        # self.lbl_temp.setText(str(nTemp))
        # self.lbl_tint.setText(str(nTint))

    def handleStillImageEvent(self):
        info = nncam.NncamFrameInfoV3()
        try:
            self.hcam.PullImageV3(None, 1, 24, 0, info) # peek
        except nncam.HRESULTException:
            pass
        else:
            if info.width > 0 and info.height > 0:
                buf = bytes(nncam.TDIBWIDTHBYTES(info.width * 24) * info.height)
                try:
                    self.hcam.PullImageV3(buf, 1, 24, 0, info)
                except nncam.HRESULTException:
                    pass
                else:
                    image = QImage(buf, info.width, info.height, QImage.Format_RGB888)
                    self.count += 1
                    image.save("pyqt{}.jpg".format(self.count))

    def toggleLineEdit(self):
        if self.checkBox.isChecked():
            self.lineEdit_2.setEnabled(True)
            self.lineEdit_6.setEnabled(True)
            self.lineEdit_3.setEnabled(True)
            self.lineEdit_7.setEnabled(True)
            self.lineEdit_8.setEnabled(True)
            self.lineEdit_4.setEnabled(True)
        else:
            self.lineEdit_2.setEnabled(False)
            self.lineEdit_6.setEnabled(False)
            self.lineEdit_3.setEnabled(False)
            self.lineEdit_7.setEnabled(False)
            self.lineEdit_8.setEnabled(False)
            self.lineEdit_4.setEnabled(False)

    def arrow_btn_enable(self, bools=True):
        self.btn_up.setEnabled(bools)
        self.btn_down.setEnabled(bools)
        self.btn_left.setEnabled(bools)
        self.btn_right.setEnabled(bools)

    def move_step(self, dir_str, step_str):
        if str(self.btn_gpib_conn.text()) == 'Disconnect':
            self.arrow_btn_enable(False)
            start_time = time.time()
            p_val = '0'
            if step_str == 'm':
                if dir_str == 'u' or dir_str == 'd':
                    p_val = self.lineEdit_3.text()
                else:
                    p_val = self.lineEdit_7.text()
            elif step_str == 's':
                if dir_str == 'u' or dir_str == 'd':
                    p_val = self.lineEdit_8.text()
                else:
                    p_val = self.lineEdit_4.text()
            elif step_str == 'l':
                if dir_str == 'u' or dir_str == 'd':
                    p_val = self.lineEdit_2.text()
                else:
                    p_val = self.lineEdit_6.text()
            else:
                p_val = int(float(step_str))
            if dir_str == 'u':
                if self.radioButton.isChecked():
                    if self.radioButton_5.isChecked():
                        self.lineEdit.setText('X#P{}UG'.format(p_val))
                    else:
                        self.lineEdit.setText('Y#P{}DG'.format(p_val))
                else:
                    if self.radioButton_5.isChecked():
                        self.lineEdit.setText('X#P{}DG'.format(p_val))
                    else:
                        self.lineEdit.setText('Y#P{}UG'.format(p_val))
            elif dir_str == 'd':
                if self.radioButton_2.isChecked():
                    if self.radioButton_5.isChecked():
                        self.lineEdit.setText('X#P{}UG'.format(p_val))
                    else:
                        self.lineEdit.setText('Y#P{}DG'.format(p_val))
                else:
                    if self.radioButton_5.isChecked():
                        self.lineEdit.setText('X#P{}DG'.format(p_val))
                    else:
                        self.lineEdit.setText('Y#P{}UG'.format(p_val))
            elif dir_str == 'l':
                if self.radioButton_3.isChecked():
                    if self.radioButton_5.isChecked():
                        self.lineEdit.setText('Y#P{}UG'.format(p_val))
                    else:
                        self.lineEdit.setText('X#P{}UG'.format(p_val))
                else:
                    if self.radioButton_5.isChecked():
                        self.lineEdit.setText('Y#P{}DG'.format(p_val))
                    else:
                        self.lineEdit.setText('X#P{}DG'.format(p_val))
            elif dir_str == 'r':
                if self.radioButton_4.isChecked():
                    if self.radioButton_5.isChecked():
                        self.lineEdit.setText('Y#P{}UG'.format(p_val))
                    else:
                        self.lineEdit.setText('X#P{}UG'.format(p_val))
                else:
                    if self.radioButton_5.isChecked():
                        self.lineEdit.setText('Y#P{}DG'.format(p_val))
                    else:
                        self.lineEdit.setText('X#P{}DG'.format(p_val))
            # Add Read LineEdit --> GPIB CMD
            QTest.qWait(100)
            str_cmd = self.lineEdit.text()
            QTest.qWait(100)
            if "X#" in str_cmd:
                self.inst.write("{}".format('a1?s'))
            elif "Y#" in str_cmd:
                self.inst.write("{}".format('a2?s'))
            previous_data = self.inst.read()
            self.inst.write("{}".format(str_cmd))
            QTest.qWait(100)
            self.status_motor(previous_data, "Y")
            QTest.qWait(100)
            self.motor_read_s()
            self.arrow_btn_enable(True)
        else:
            QMessageBox.warning(self, "Warning", "GPIB disconnect.")


    def init_position(self):
        self.inst.write("{}".format('a1#s0'))
        QTest.qWait(100)
        self.inst.write("{}".format('a2#s0'))

    def status_motor(self, previous_data, xyor):
        while True:
            QTest.qWait(100)
            if xyor == "X":
                self.inst.write("{}".format('a1?s'))
            elif xyor == "Y":
                self.inst.write("{}".format('a2?s'))
            data = self.inst.read()
            if data != previous_data:
                # 데이터 변화가 있음
                # print("Received data: {}".format(data))
                previous_data = data
            else:
                # 데이터 변화가 없음
                # print("No data change.")
                break
            previous_data = data

    def motor_read_s(self):
        self.inst.write("{}".format('a1?s'))
        s_a1 = self.inst.read()
        QTest.qWait(100)
        self.inst.write("{}".format('a2?s'))
        s_a2 = self.inst.read()
        self.label_19.setText('{}'.format(s_a2))
        self.label_21.setText('{}'.format(s_a1))
        return int(s_a1), int(s_a2)

    def goto_origin(self):
        self.btn_goto_origin.setEnabled(False)
        self.motor_read_s()
        x_value = int(self.label_19.text())
        y_value = int(self.label_21.text())
        QTest.qWait(100)
        self.inst.write("{}".format('a1?s'))
        previous_data = self.inst.read()
        QTest.qWait(100)
        if y_value < 0:
            self.inst.write("X#P{}UG".format(y_value))
        elif y_value == 0:
            pass
        else:
            self.inst.write("X#P{}DG".format(y_value))
        # Need for delay
        # QTest.qWait(int(abs(y_value * 5)))
        self.status_motor(previous_data, "X")
        QTest.qWait(100)
        self.inst.write("{}".format('a2?s'))
        previous_data = self.inst.read()
        QTest.qWait(100)
        if x_value < 0:
            self.inst.write("Y#P{}UG".format(x_value))
        elif x_value == 0:
            pass
        else:
            self.inst.write("Y#P{}DG".format(x_value))
        # QTest.qWait(int(abs(x_value * 5)))
        self.status_motor(previous_data, "Y")
        QTest.qWait(100)
        self.motor_read_s()
        self.btn_goto_origin.setEnabled(True)

    def shortcut_key(self):
        self.btn_up.clicked.connect(lambda: self.move_step('u', 'm'))
        self.btn_down.clicked.connect(lambda: self.move_step('d', 'm'))
        self.btn_left.clicked.connect(lambda: self.move_step('l', 'm'))
        self.btn_right.clicked.connect(lambda: self.move_step('r', 'm'))

        self.btn_up.setShortcut(QKeySequence(Qt.Key.Key_F20))
        self.btn_down.setShortcut(QKeySequence(Qt.Key.Key_F21))
        self.btn_left.setShortcut(QKeySequence(Qt.Key.Key_F22))
        self.btn_right.setShortcut(QKeySequence(Qt.Key.Key_F23))

        shortcut_up = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_F20), self)
        shortcut_up.activated.connect(lambda: self.move_step('u', 's'))
        shortcut_down = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_F21), self)
        shortcut_down.activated.connect(lambda: self.move_step('d', 's'))
        shortcut_left = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_F22), self)
        shortcut_left.activated.connect(lambda: self.move_step('l', 's'))
        shortcut_right = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_F23), self)
        shortcut_right.activated.connect(lambda: self.move_step('r', 's'))

        shortcut_up_l = QShortcut(QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_F20), self)
        shortcut_up_l.activated.connect(lambda: self.move_step('u', 'l'))
        shortcut_down_l = QShortcut(QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_F21), self)
        shortcut_down_l.activated.connect(lambda: self.move_step('d', 'l'))
        shortcut_left_l = QShortcut(QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_F22), self)
        shortcut_left_l.activated.connect(lambda: self.move_step('l', 'l'))
        shortcut_right_l = QShortcut(QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_F23), self)
        shortcut_right_l.activated.connect(lambda: self.move_step('r', 'l'))

    def closeEvent(self, event):
        re = QMessageBox.question(self, "Question", "Are you sure you want to quit?",
                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if re == QMessageBox.StandardButton.Yes:
            self.closeCamera()
            try:
                if self.serial_connection.is_open:
                    self.serial_connection.close()
            except AttributeError as e:
                print(f'Msg err : {e}')
            try:
                if self.serial_connection_2.is_open:
                    self.serial_connection_2.close()
            except AttributeError as e:
                print(f'Msg err : {e}')
            self.snippingWidget.close()
            event.accept()
        else:
            event.ignore()

    def startProgress(self):
        self.startTime = QDateTime.currentDateTime()
        self.timer2.start(1000)  # 1초마다 업데이트

    def updateProgress(self):
        value = self.progressBar.value()
        self.label_stime.setText(self.startTime.toString('yyyy-MM-dd HH:mm:ss'))
        if value < 100:
            value += 1
            # self.progressBar.setValue(value)

            current_time = QDateTime.currentDateTime().toString('yyyy-MM-dd HH:mm:ss')

            # 남은 시간 계산
            elapsed_seconds = self.startTime.secsTo(QDateTime.currentDateTime())
            remaining_seconds = (100 - value) * elapsed_seconds // value if value > 0 else 0
            remaining_time = QDateTime.currentDateTime().addSecs(remaining_seconds)
            end_time = self.startTime.addSecs(elapsed_seconds + remaining_seconds)

            # 남은 시간과 종료 시간 표시
            self.label_rtime.setText(f"{remaining_seconds // 60} minutes {remaining_seconds % 60} seconds")
            self.label_etime.setText(f"{end_time.toString('yyyy-MM-dd HH:mm:ss')}")
        else:
            self.timer2.stop()

    def server_connect(self):
        if str(self.pushButton_14.text()) == 'Server Connect':
            address = (f'{self.lineEdit_5.text()}', 9999)
            self.client_socket = Client(address, authkey=b'p7473')
            QTest.qWait(500)
            self.pushButton_14.setText("Server Disconnect")
            self.btn_acq.setEnabled(True)
            self.btn_read_frame.setEnabled(True)
        else:
            self.client_socket.close()
            QTest.qWait(500)
            self.btn_acq.setEnabled(False)
            self.btn_read_frame.setEnabled(False)
            self.pushButton_14.setText("Server Connect")

    def recv_data(self):
        while True:
            data = self.client_socket.recv()
            print(data)
            if data == "done":
                print("msg : done!")
                break

    def snap_spectrum(self):
        self.client_socket.send('snap')
        self.recv_data()

    def plot_spe(self, x_data, y_data):
        self.widget.axes.cla()
        self.widget.figure.subplots_adjust(left=0.1)
        self.widget.figure.subplots_adjust(bottom=0.1)

        # widget.axes.set_title(file_name)
        self.widget.axes.set_title(
            r"Winspec32 Spectrum", fontsize=12)
        self.widget.axes.set_xlabel(r"Wavelength (nm)", fontsize=12)
        self.widget.axes.set_ylabel(r"Intensity (a.u.)", fontsize=12)
        self.widget.axes.tick_params(axis="y", direction="in", pad=10, labelsize=10)
        self.widget.axes.tick_params(axis="x", direction="in", pad=10, labelsize=10)

        self.widget.axes.plot(x_data, y_data, ms=100, lw=2)
        self.widget.draw()


class SnippingWidget(QWidget):
    is_snipping = False

    def __init__(self, parent=None, app=None):
        super(SnippingWidget, self).__init__()
        self.parent = parent
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.showFullScreen()

        self.screen = app.primaryScreen()
        self.setGeometry(0, 0, self.screen.size().width(), self.screen.size().height())
        self.begin = QPoint()
        self.end = QPoint()
        self.onSnippingCompleted = None

    def fullscreen(self):
        img = ImageGrab.grab(bbox=(0, 0, self.screen.size().width(), self.screen.size().height()))

        try:
            img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        except:
            img = None

        if self.onSnippingCompleted is not None:
            self.onSnippingCompleted(img)

    def start(self):
        SnippingWidget.is_snipping = True
        self.setWindowOpacity(0.3)
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.show()

    def paintEvent(self, event):
        if SnippingWidget.is_snipping:
            brush_color = (128, 128, 255, 100)
            lw = 3
            opacity = 0.3
        else:
            self.begin = QPoint()
            self.end = QPoint()
            brush_color = (0, 0, 0, 0)
            lw = 0
            opacity = 0

        self.setWindowOpacity(opacity)
        qp = QPainter(self)
        qp.setPen(QPen(QColor('black'), lw))
        qp.setBrush(QColor(*brush_color))
        # rect = QRectF(self.begin, self.end)
        rect = QRectF(QPointF(self.begin), QPointF(self.end)).normalized()
        qp.drawRect(rect)

    def mousePressEvent(self, event):
        self.begin = event.pos()
        self.end = self.begin
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        SnippingWidget.is_snipping = False
        QApplication.restoreOverrideCursor()
        x1 = min(self.begin.x(), self.end.x())
        y1 = min(self.begin.y(), self.end.y())
        x2 = max(self.begin.x(), self.end.x())
        y2 = max(self.begin.y(), self.end.y())

        self.repaint()
        QApplication.processEvents()
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))

        try:
            img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        except:
            img = None

        if self.onSnippingCompleted is not None:
            self.onSnippingCompleted(img)

        self.close()


class AnotherWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setGeometry(50, 165, 250, 120)
        layout = QVBoxLayout()

        close_button = QPushButton('Close', self)
        close_button.clicked.connect(self.close)
        self.label = QLabel("Manual Adjusting")
        layout.addWidget(self.label)
        layout.addWidget(close_button)
        self.setLayout(layout)

        close_button.setShortcut(QKeySequence(Qt.Key.Key_E))


class CoordinateListModel(QAbstractListModel):
    def __init__(self, coordinates, parent=None):
        super().__init__(parent)
        self.coordinates = coordinates

    def rowCount(self, parent=QModelIndex()):
        return len(self.coordinates)

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            x, y = self.coordinates[index.row()]
            return f"ID {index.row()} : ({x}, {y})"
        return None


if __name__ == '__main__':
    nncam.Nncam.GigeEnable(None, None)
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())