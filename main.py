import sys, time, os, json, csv
import warnings

# 경고 메시지 숨기기
warnings.filterwarnings('ignore', message='pkg_resources is deprecated')
warnings.filterwarnings('ignore', message="model number.*doesn't match the device ID prefix")
os.environ['PYTHONWARNINGS'] = 'ignore'

# Qt 경고 메시지 핸들러
def qt_message_handler(mode, context, message):
    """Qt 경고 메시지 필터링"""
    # 숨길 메시지 패턴들
    ignored_messages = [
        'OleInitialize',
        'SetProcessDpiAwarenessContext',
        'setGeometry',
        'DPI_AWARENESS_CONTEXT'
    ]
    # 무시할 메시지가 아니면 출력
    if not any(pattern in message for pattern in ignored_messages):
        pass  # 필요시 print(message) 로 변경

from sub_py import nncam
import numpy as np

import win32con
import win32gui
import win32com.client

import cv2
import serial, pyvisa
from scipy.optimize import curve_fit
from multiprocessing.connection import Client
import threading

# YOLO imports
from ultralytics import YOLO

from ui_main import Ui_MainWindow
from sdk2_form_widget import AndorSdk2FormWidget
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QMenu, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QTabWidget, QFileDialog, QLineEdit
from PyQt6.QtGui import QImage, QPixmap, QAction, QShortcut, QKeySequence, QGuiApplication
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QAbstractListModel, QModelIndex, QDateTime, qInstallMessageHandler
from PyQt6.QtTest import QTest

# Qt 메시지 핸들러 설치
qInstallMessageHandler(qt_message_handler)

from sub_py.flipper import Thorlabs_MFF101
from sub_py.snipping import SnippingWidget
from sub_py.matplotlibwidget import MatplotlibWidget
from sub_py.solis_win32con import Solis_win32
from sub_py.read_sif import SIF
from sub_py.rotation_filter import FW102C

# 가까운 점 추적: 거리가 임계값 미만이면 종료, 최대 반복 횟수 상한
CLOSEST_DOT_DISTANCE_THRESHOLD = 1
CLOSEST_DOT_MAX_ITERATIONS = 10


class MainWindow(QMainWindow, Ui_MainWindow):
    evtCallback = pyqtSignal(int)
    useQThread = True

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        self._sdk2_widget = None
        self._main_process_abort = False
        self._main_process_running = False
        self.showMaximized()

        # Debug mode variable (initialize first)
        self.debug_mode = False
        self.timer = QTimer(self)
        self.timer2 = QTimer()
        self.snippingWidget = SnippingWidget(app=QApplication.instance())

        self.init_ui()

        self.short_delay = 250
        self.sutter_delay = 20
        self.led_delay = 100
        self.flip_delay = 1000
        self.subwindow_delay = 1000
        self.move_delay = 1000
        # Time (btw stage move and measurement)
        self.delay_time = 1000
        self.expose_time = 1000
        # Camera Val.
        self.hcam = None

        self.imgWidth = 0
        self.imgHeight = 0
        self.pData = None
        self.res = 0
        self.count = 0
        # Vision Val.
        self.val_thre_dot = float(self.thre_dots.text())
        self.val_thre_laser = float(self.thre_laser.text())
        self.points = []
        self.coordinate_model = None
        self.vision_laser_pos = False
        self.find_laser = False
        self.find_dot = False
        # Frame skipping for dot detection optimization
        self.dot_detection_frame_counter = 0
        self.dot_detection_frame_skip = 1  # Process every Nth frame (adjustable: lower = more accurate, higher = smoother)
        # Template caching for performance
        self.dot_template_cache = None
        self.laser_template_cache = None
        # Snipping Img Val.
        self.snipping_laser = False
        self.snipping_dot = False

        # Flip Mount MFF101 Thorlabs
        self.mff101 = Thorlabs_MFF101()
        # Connect to flip mirror on startup
        if self.mff101.is_connected():
            self.debug_print("Flip mirror connected successfully")
        else:
            self.debug_print("Warning: Flip mirror not connected")
            
        # Second Flip Mount MFF101 Thorlabs
        self.mff101_2 = Thorlabs_MFF101("37008033")
        # Connect to second flip mirror on startup
        if self.mff101_2.is_connected():
            self.debug_print("Second flip mirror connected successfully")
        else:
            self.debug_print("Warning: Second flip mirror not connected")
        
        # FW102C Filter Wheel
        self.fw102c = None
        self.fw102c_connected = False
        
        # LED Control Val.
        self.serial_connection = False
        # Shutter Control Val.
        self.serial_connection_2 = False
        # ITC503 Temperature Controller
        self.itc503_connection = None
        self.itc503_connected = False
        # Stepper Motor (Flipper Motor) Control
        self.fm_serial = None
        # Stepping Motor Controller
        self.inst = False
        # Start
        self.init_isOk = False
        self.laser_litho_spec_meas = False
        self.laser_litho_offset_time = 1000  # ADD Shutter delay time
        # Timer Setting
        self.startTime = None
        
        # Position update timer (like ds102.py) - using QTimer for UI safety
        self.position_timer = QTimer(self)
        self.position_timer.timeout.connect(self.update_position_status)
        self.position_update_active = False

        # DS102 Communication protection
        self.ds102_lock = threading.Lock()
        self.last_command_time = 0
        self.min_command_interval = 0.01  # Minimum 10ms between commands (reduced for responsiveness)

        # TCP/IP Comm.
        self.client_socket = None

        # Define digit patterns (simple example for 5x7 grid)??
        self.braille_patterns = {
            '0': [0, 0, 0, 1, 1, 0],
            '1': [0, 0, 0, 0, 0, 1],
            '2': [1, 0, 0, 0, 0, 1],
            '3': [0, 1, 0, 0, 0, 1],
            '4': [0, 0, 0, 0, 1, 0],
            '5': [1, 0, 0, 0, 1, 0],
            '6': [0, 0, 0, 0, 1, 1],
            '7': [0, 0, 0, 1, 0, 0],
            '8': [1, 1, 0, 0, 1, 1],
            '9': [0, 0, 0, 1, 0, 1],
        }

        self.except_point = []
        
        # Image saving related variables
        self.save_image_flag = False
        self.current_image_path = ""
        
        # Dot detection related variables
        self.dot_detection_method = "template"  # "improved", "contour", "template"
        self.min_radius = 3
        self.max_radius = 15
        self.min_area = 10
        self.max_area = 200
        
        # YOLO model initialization
        self.yolo_model = None
        self.yolo_model_path = r"C:\Pycode\camera_test\yolo\models\dot_detection.pt"
        try:
            self.yolo_model = YOLO(self.yolo_model_path)
            self.debug_print("YOLO model loaded successfully")
        except Exception as e:
            self.debug_print(f"Failed to load YOLO model: {e}")
            self.yolo_model = None
        
        # Image detection related variables
        self.not_find_img = False
        

        
        # Dot detection limit related variables
        self.max_detection_count = 80  # Maximum detection count limit

    def debug_print(self, *args, **kwargs):
        """디버깅 모드가 켜져 있을 때만 print 출력"""
        if self.debug_mode:
            print(*args, **kwargs)

    def get_save_folder_path(self):
        """
        label_fp 경로에 lineEdit_fn 기반 폴더를 생성하고, 저장할 폴더 경로 반환.
        - lineEdit_fn이 "B73"이면 label_fp/B73 폴더 생성 후 반환.
        - lineEdit_fn이 "exp1/data" 형태면 label_fp/exp1 폴더 생성 후 반환.
        """
        folder_path = self.label_fp.text()
        if not folder_path or folder_path == "None":
            return None
        
        fn_text = self.lineEdit_fn.text().strip() or "data"
        dir_part = os.path.dirname(fn_text)
        base_name = os.path.basename(fn_text)
        
        if dir_part:
            # "exp1/data" -> label_fp/exp1
            full_folder = os.path.join(folder_path, dir_part)
        else:
            # "B73" -> label_fp/B73 (이름으로 서브폴더 생성)
            full_folder = os.path.join(folder_path, base_name)
        
        os.makedirs(full_folder, exist_ok=True)
        return os.path.normpath(full_folder)

    def ds102_send_command(self, command, wait_response=False, timeout=2):
        """
        Send command to DS102 controller with protection against rapid commands
        
        Args:
            command: Command string to send (will be encoded to utf-8)
            wait_response: If True, wait for and return response
            timeout: Timeout for response (default 2 seconds)
            
        Returns:
            Response string if wait_response=True, None otherwise
        """
        with self.ds102_lock:
            try:
                # Ensure minimum time between commands
                current_time = time.time()
                time_since_last = current_time - self.last_command_time
                
                if time_since_last < self.min_command_interval:
                    time.sleep(self.min_command_interval - time_since_last)
                
                # Send command
                if hasattr(self, 'inst') and self.inst and hasattr(self.inst, 'is_open') and self.inst.is_open:
                    self.inst.write(command.encode('utf-8'))
                    self.last_command_time = time.time()
                    
                    # Wait for response if requested
                    if wait_response:
                        time.sleep(0.1)  # Standard delay for DS102
                        response = self.inst.read_until(b'\r').decode('utf-8').strip()
                        return response
                    else:
                        time.sleep(0.05)  # Brief delay for command processing
                        return None
                else:
                    self.debug_print("DS102: Serial connection not available")
                    return None
                    
            except Exception as e:
                self.debug_print(f"DS102 Command Error: {e}")
                return None

    def init_ui(self):
        # Configuration
        self.load_config()

        self.find_dot = False
        self.find_laser = False

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
        self.find_dot = False
        self.pushButton_9.clicked.connect(self.thre_set)
        self.pushButton_10.clicked.connect(self.thre_set)
        self.pushButton_11.clicked.connect(self.ft_find_laser)
        self.pushButton_15.clicked.connect(self.toggle_find_laser)
        self.btn_find_dot.clicked.connect(self.toggle_find_dot)
        self.btn_img_cla.clicked.connect(self.toggle_clear_image_markers)
        
        # Add dot detection method selection combobox
        from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSpinBox
        dot_detection_layout = QHBoxLayout()
        dot_detection_label = QLabel("Dot Detection Method:")
        self.dot_detection_combo = QComboBox()
        self.dot_detection_combo.addItems(["Template", "YOLO"])
        self.dot_detection_combo.setCurrentText("Template")
        self.dot_detection_combo.currentTextChanged.connect(self.on_dot_detection_method_changed)
        dot_detection_layout.addWidget(dot_detection_label)
        dot_detection_layout.addWidget(self.dot_detection_combo)
        
        # Add maximum detection count setting
        max_detection_layout = QHBoxLayout()
        max_detection_label = QLabel("Max Detection Count:")
        self.max_detection_spinbox = QSpinBox()
        self.max_detection_spinbox.setRange(10, 200)
        self.max_detection_spinbox.setValue(self.max_detection_count)
        self.max_detection_spinbox.valueChanged.connect(self.on_max_detection_count_changed)
        max_detection_layout.addWidget(max_detection_label)
        max_detection_layout.addWidget(self.max_detection_spinbox)
        
        # Add to existing layout (add to verticalLayout_6 of groupBox_4)
        self.groupBox_4.layout().addLayout(dot_detection_layout)

        self.snippingWidget.onSnippingCompleted = self.onSnippingCompleted
        self.btn_area_dot.clicked.connect(lambda: self.snipArea('dot'))
        self.btn_area_laser.clicked.connect(lambda: self.snipArea('laser'))

        self.btn_flip_m90.clicked.connect(self.mff101_move2)
        self.btn_flip_p90.clicked.connect(self.mff101_move1)

        self.btn_ledconn.clicked.connect(self.LED_connect)
        self.btn_LED_toggle.clicked.connect(self.LED_toggle)
        
        self.btn_ledconn_2.clicked.connect(self.ITC503_connect)
        
        # Stepper motor connections
        self.btn_fm.clicked.connect(self.fm_connect)
        self.btn_fm_enable.clicked.connect(self.fm_enable_disable)
        self.btn_fm_cw.clicked.connect(self.fm_cw)
        self.btn_fm_ccw.clicked.connect(self.fm_ccw)
        self.btn_af.clicked.connect(self.auto_focus)

        self.btn_shutter_conn.clicked.connect(self.shutter_conn)
        self.btn_shutter_time.clicked.connect(self.shutter_time)
        self.btn_shutter_toggle.clicked.connect(self.shutter_toggle)

        self.btn_gpib_conn.clicked.connect(self.Gpib_conn)
        
        # FW102C Filter Wheel connections
        self.btn_gpib_conn_2.clicked.connect(self.fw102c_connect)
        self.pushButton.clicked.connect(self.fw102c_position_up)
        self.pushButton_5.clicked.connect(self.fw102c_position_down)
        # Initialize FW102C control buttons as disabled
        self.pushButton.setEnabled(False)
        self.pushButton_5.setEnabled(False)
        self.label_38.setText('-')
        
        # Initialize Stepper Motor control buttons as disabled
        self.btn_fm_enable.setEnabled(False)
        self.btn_fm_enable.setCheckable(True)  # 토글 버튼으로 동작
        self.btn_fm_enable.setChecked(False)
        self.btn_fm_enable.setText('Disabled')
        # Set toggle button style (checked 시 배경/글씨만 변경)
        self.btn_fm_enable.setStyleSheet("QPushButton:checked { background-color: #4CAF50; color: white; }")
        self.btn_fm_cw.setEnabled(False)
        self.btn_fm_ccw.setEnabled(False)
        self.btn_af.setEnabled(False)
        # Sharpness 실시간 표시 (테스트용, focus peaking 방식)
        self.lbl_laplacian = QLabel("Sharpness: --")
        self.verticalLayout_27.addWidget(self.lbl_laplacian)
        self._laplacian_frame_counter = 0
        # Auto Focusing Peak 그래프
        self.af_peak_widget = MatplotlibWidget(
            parent=self.groupBox_20,
            title='AF Peak (#Dots vs Step)',
            xlabel='Step',
            ylabel='#Dots',
            width=4, height=2.5, hold=True
        )
        self.af_peak_widget.setMinimumHeight(120)
        self.verticalLayout_27.addWidget(self.af_peak_widget)
        
        self.shortcut_key()
        self.btn_motor_read.clicked.connect(self.motor_read_s)
        self.btn_motor_init.clicked.connect(self.init_position)
        self.btn_goto_origin.clicked.connect(self.goto_origin)
        self.checkBox.stateChanged.connect(self.toggleLineEdit)

        self.btn_start.setCheckable(True)
        self.btn_start.setChecked(False)
        self.btn_start.setStyleSheet(
            "QPushButton { margin-bottom: 10px; }\n"
            "QPushButton:checked { background-color: #4CAF50; color: white; }"
        )
        self.btn_start.clicked.connect(self._on_btn_start_clicked)

        self.timer2.timeout.connect(self.updateProgress)

        self.pushButton_14.clicked.connect(self.server_connect)
        
        # Disconnect existing connections before connecting btn_acq (prevent duplicates)
        try:
            self.btn_acq.clicked.disconnect()
        except TypeError:
            pass  # Ignore if no connected signals
        self.btn_acq.clicked.connect(self.on_btn_acq_clicked)
        
        self.btn_read_frame.clicked.connect(self.read_spe)

        # Connect move_closest_dot() method to btn_3_move button
        self.btn_3_move.clicked.connect(self.move_closest_dot)
        
        # Connect screenshot button
        self.btn_ss.clicked.connect(self.take_screenshot)
        
        # Connect folder selection buttons
        self.btn_fp.clicked.connect(self.select_folder_path)
        self.btn_open_fp.clicked.connect(self.open_folder_path)
        self.btn_sdk2.clicked.connect(self.open_sdk2_window)
        
        # Setup auto save system
        self._setup_auto_save()
        
        # Spectrum mode radios: Solis / SDK2 / (InGaAs+server)
        self.radioButton_7.toggled.connect(self._refresh_spectrum_acq_buttons)
        self.rbtn_sdk2.toggled.connect(self._refresh_spectrum_acq_buttons)
        self._refresh_spectrum_acq_buttons()

    @staticmethod
    def _leftmost_screen():
        screens = QGuiApplication.screens()
        if not screens:
            return None
        return min(screens, key=lambda s: s.geometry().left())

    def open_sdk2_window(self):
        if self._sdk2_widget is None:
            self._sdk2_widget = AndorSdk2FormWidget(self)
            self._sdk2_widget.setWindowFlags(Qt.WindowType.Window)
        left = self._leftmost_screen()
        if left is not None:
            self._sdk2_widget.setScreen(left)
            self._sdk2_widget.setGeometry(left.availableGeometry())
        self._sdk2_widget.show()
        self._sdk2_widget.showMaximized()
        self._sdk2_widget.raise_()
        self._sdk2_widget.activateWindow()

    def take_screenshot(self):
        """Function to save the current camera image as a screenshot"""
        import os
        from datetime import datetime
        
        # Create imgs folder if it doesn't exist
        if not os.path.exists('imgs'):
            os.makedirs('imgs')
            self.debug_print("Created 'imgs' folder")
        
        # Generate filename with current date and time
        current_time = datetime.now()
        date_str = current_time.strftime('%y-%m-%d')
        
        # Determine number by checking existing file count
        existing_files = [f for f in os.listdir('imgs') if f.startswith(f'{date_str}_') and f.endswith('.png')]
        if existing_files:
            # Extract numbers from existing files
            numbers = []
            for file in existing_files:
                try:
                    # Extract number from filename (e.g.: 24-12-19_1.png -> 1)
                    number = int(file.split('_')[1].split('.')[0])
                    numbers.append(number)
                except (IndexError, ValueError):
                    continue
            
            # Determine next number
            next_number = max(numbers) + 1 if numbers else 1
        else:
            next_number = 1
        
        # Generate filename
        filename = f'{date_str}_{next_number}.png'
        filepath = os.path.join('imgs', filename)
        
        # Save current camera image
        if hasattr(self, 'lbl_video') and self.lbl_video.pixmap():
            pixmap = self.lbl_video.pixmap()
            if pixmap.save(filepath):
                self.debug_print(f"Screenshot saved: {filepath}")
                QMessageBox.information(self, "Success", f"Screenshot saved as {filename}")
            else:
                self.debug_print(f"Failed to save screenshot: {filepath}")
                QMessageBox.warning(self, "Error", "Failed to save screenshot")
        else:
            self.debug_print("No camera image available")
            QMessageBox.warning(self, "Warning", "No camera image available")

    def draw_braille_digit(self, digit, size):
        pattern = self.braille_patterns.get(str(digit), [])
        if len(pattern) != 6:
            self.debug_print(f"Warning: Invalid pattern for digit {digit}")
            return

        for i in range(3):
            if pattern[i]:
                self.shutter_open()
                QTest.qWait(int(self.lineEdit_shutter_time.text()))
                self.shutter_close()
                QTest.qWait(500)
            else:
                self.shutter_close()
            if i < 2:
                self.move_step('d', size)
        self.move_step('r', size)
        for i in range(3):
            if pattern[5 - i]:
                self.shutter_open()
                QTest.qWait(int(self.lineEdit_shutter_time.text()))
                self.shutter_close()
                QTest.qWait(500)
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

    def toggle_clear_image_markers(self):
        # Disable dot detection
        self.find_dot = False
        self.find_laser = False
        # Exclude vision_laser_pos (keep laser position marking)
        # Initialize dot list
        self.points = []
        self.coordinate_model = CoordinateListModel(self.points)
        self.listView.setModel(self.coordinate_model)
        self.label_no_dots.setText('0')
        self.debug_print("Image markers cleared (laser position marking preserved)")

    def _abort_if_requested(self) -> bool:
        if self._main_process_abort:
            self.debug_print("Main process stopped by user")
            return True
        return False

    def _on_btn_start_clicked(self) -> None:
        if self.btn_start.isChecked():
            if self._main_process_running:
                self.btn_start.blockSignals(True)
                self.btn_start.setChecked(False)
                self.btn_start.setText("Start")
                self.btn_start.blockSignals(False)
                return
            self._main_process_abort = False
            self.btn_start.setText("Stop")
            QTimer.singleShot(0, self._run_main_process)
        else:
            self._main_process_abort = True
            self.btn_start.setText("Stopping…")

    def _run_main_process(self) -> None:
        if self._main_process_running:
            return
        self._main_process_running = True
        try:
            self.main_process_start()
        finally:
            self._main_process_running = False
            self._reset_btn_start_idle()

    def _reset_btn_start_idle(self) -> None:
        self.timer2.stop()
        self.btn_start.blockSignals(True)
        self.btn_start.setChecked(False)
        self.btn_start.setText("Start")
        self.btn_start.blockSignals(False)

    def main_process_start(self):
        self.save_config()
        if self.rb_mapping.isChecked():
            if self.mapping_expanding_chk.isChecked():
                # mapping_expanding_chk 체크 시: mapping -> (VX,VY 이동, 가까운점 3회) -> 파일명 증가 -> 반복
                try:
                    no_expanding = int(self.no_expanding.text().strip())
                except ValueError:
                    no_expanding = 1
                
                for expand_idx in range(no_expanding):
                    if self._abort_if_requested():
                        return
                    self.debug_print(f"Mapping expanding iteration {expand_idx + 1}/{no_expanding}")
                    self.mapping_start()
                    if self._abort_if_requested():
                        return
                    
                    if expand_idx < no_expanding - 1:  # 마지막이 아니면 확장 단계 후 다음 반복
                        if self._abort_if_requested():
                            return
                        vx_val = int(self.label_31.text())
                        vy_val = int(self.label_33.text())
                        # VX, VY 만큼 이동
                        self.mapping_move(vx_val, vy_val)
                        QTest.qWait(self.move_delay)
                        # 가까운 점으로 이동 (CLOSEST_DOT_MAX_ITERATIONS, CLOSEST_DOT_DISTANCE_THRESHOLD 미만 시 종료)
                        self.find_dot = True
                        for _ in range(CLOSEST_DOT_MAX_ITERATIONS):
                            if self._abort_if_requested():
                                self.find_dot = False
                                return
                            closest_point, distance = self.cal_closest_dot()
                            QTest.qWait(self.short_delay)
                            if distance < CLOSEST_DOT_DISTANCE_THRESHOLD:
                                self.debug_print(
                                    f"Distance {distance:.2f} < {CLOSEST_DOT_DISTANCE_THRESHOLD}, target reached"
                                )
                                break
                            self.move_closest_dot(closest_point)
                            QTest.qWait(self.short_delay)
                        self.find_dot = False
                        # lineEdit_fn 두번째 문자(숫자) +1
                        fn = self.lineEdit_fn.text().strip()
                        if len(fn) >= 3 and fn[1].isdigit():
                            new_val = (int(fn[1]) + 1) % 10  # 0-9 순환
                            self.lineEdit_fn.setText(fn[0] + str(new_val) + fn[2:])
                            self.debug_print(f"Filename incremented to: {self.lineEdit_fn.text()}")
                        # Auto Focusing 실행 (fm_step_2 CW/CCW 대체)
                        self.btn_af.click()
                        QTest.qWait(500)
                        # AF 후 가까운 점 재정렬 (파일명은 위에서 1회만 증가)
                        self.find_dot = True
                        for _ in range(CLOSEST_DOT_MAX_ITERATIONS):
                            if self._abort_if_requested():
                                self.find_dot = False
                                return
                            closest_point, distance = self.cal_closest_dot()
                            QTest.qWait(self.short_delay)
                            if distance < CLOSEST_DOT_DISTANCE_THRESHOLD:
                                self.debug_print(
                                    f"Distance {distance:.2f} < {CLOSEST_DOT_DISTANCE_THRESHOLD}, target reached"
                                )
                                break
                            self.move_closest_dot(closest_point)
                            QTest.qWait(self.short_delay)
                        self.find_dot = False
            else:
                if self._abort_if_requested():
                    return
                self.mapping_start()
        elif self.rb_laser_litho.isChecked():
            if self._abort_if_requested():
                return
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
                if self._abort_if_requested():
                    return
                for i in range(x_value):
                    if self._abort_if_requested():
                        return
                    self.label_35.setText("[{}, {}] = Total Points # {} / Curr. {}, {}".format(
                        x_value, y_value, total_point_no, (i + 1), (j + 1)))
                    pb_val = (j * x_value) + (i + 1)
                    if i != (x_value - 1):
                        self.mapping_move(hx_val, hy_val)
                        QTest.qWait(1000)
                        QTest.qWait(self.short_delay)
                        self.debug_print(self.motor_read_s())
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
                        self.debug_print(self.motor_read_s())
                        QTest.qWait(self.short_delay)
                        self.shutter_time()
                        QTest.qWait(int(self.lineEdit_shutter_time.text()) + self.laser_litho_offset_time)
                        const_x = linex_val
                        const_y = liney_val
                    else:
                        self.mapping_move(-const_x, -const_y)
                        QTest.qWait(self.short_delay)
                        self.debug_print(self.motor_read_s())
                        QTest.qWait(self.short_delay)
                        self.shutter_time()
                        QTest.qWait(int(self.lineEdit_shutter_time.text()) + self.laser_litho_offset_time)
        else:
            QMessageBox.warning(self, "Warning", f"Failed to initialize eq.")

    def mapping_start(self):
        try:
            # Check server connection
            if self.client_socket is not None or self.radioButton_7.isChecked() or self.rbtn_sdk2.isChecked():
                # 맨 처음 모터 초기화
                self.btn_motor_init.click()
                QTest.qWait(self.short_delay)

                if self.rbtn_sdk2.isChecked() and self._sdk2_widget is None:
                    self.open_sdk2_window()
                if self._sdk2_widget is not None:
                    self._sdk2_widget.ui.lineEdit_groupname.setText(self.lineEdit_fn.text())
                
                # Read number of points for X and Y axes
                x_value = int(self.spinBox.value())
                y_value = int(self.spinBox_2.value())
                self.label_35.setText("[{}, {}] = Total Points # {}".format(
                    x_value, y_value, x_value * y_value))
                self.progressBar.setValue(0)  # Initialize progress bar

                # Calculate movement distance for each axis
                hx_val = int(self.label_26.text())  # X-axis movement distance
                hy_val = int(self.label_29.text())  # Y-axis movement distance
                vx_val = int(self.label_31.text())  # Vertical X-axis movement distance
                vy_val = int(self.label_33.text())  # Vertical Y-axis movement distance

                # Close shutter
                try:
                    self.shutter_close()
                except Exception as e:
                    self.debug_print(f"Warning: Failed to close shutter: {e}")

                # 4개 포인트 완전 건너뛰기: (7,7), (7,8), (8,7), (8,8) — 그리드 범위 안일 때만 제외
                skip_positions = [(7, 7), (7, 8), (8, 7), (8, 8)]
                skip_in_grid = [
                    (x, y) for (x, y) in skip_positions
                    if 1 <= x <= x_value and 1 <= y <= y_value
                ]
                total_point_no = x_value * y_value - len(skip_in_grid)  # 실제 처리할 포인트 수
                processed_count = 0  # progressBar용

                
                # Loop in Y-axis direction
                for j in range(y_value):
                    QApplication.processEvents()
                    if self._abort_if_requested():
                        return
                    # Determine X-axis direction: zigzag pattern
                    # Even rows (j=0,2,4...): left to right (forward)
                    # Odd rows (j=1,3,5...): right to left (reverse)
                    if j % 2 == 0:
                        x_range = range(x_value)  # Forward: 0,1,2,...,x_value-1
                    else:
                        x_range = range(x_value - 1, -1, -1)  # Reverse: x_value-1,...,2,1,0
                    
                    # Loop in X-axis direction
                    last_visited_i, last_visited_j = None, None  # Y축 이동 시 실제 마지막 위치
                    for i in x_range:
                        QApplication.processEvents()  # UI 응답성 유지 (응답없음 방지)
                        if self._abort_if_requested():
                            return
                        current_position = (i + 1, j + 1)
                        if current_position in skip_positions:
                            self.debug_print(f"Skipping point {current_position}")
                            continue
                        
                        last_visited_i, last_visited_j = i, j
                        processed_count += 1
                        # Display current point and progress in English
                        self.label_35.setText("[{}, {}] = Total Points # {} / Current {}, {}".format(
                            x_value, y_value, total_point_no, (i + 1), (j + 1)))

                        # Prepare spectrum measurement (sequence changed)
                        try:
                            self.shutter_open()  # 1. Open shutter
                            QTest.qWait(self.sutter_delay)
                            self.mff101_move1()  # 2. Move beam to spectrum
                            QTest.qWait(self.flip_delay)
                            # Turn off LED (click() → LED_toggle의 QMessageBox가 매핑 중 UI 프리즈 유발 가능)
                            if self.btn_LED_toggle.isChecked():
                                self._led_off_for_mapping()
                            QTest.qWait(self.led_delay)                            
                        except Exception as e:
                            self.debug_print(f"Warning: Failed to prepare spectrum measurement: {e}")
                            continue  # Proceed to next point

                        # Save spectrum with unique filename for each point
                        file_name = self.lineEdit_fn.text().strip() or "data"
                        base_name = os.path.basename(file_name) if os.path.dirname(file_name) else file_name
                        point_filename = f"{base_name}_({i+1},{j+1})"
                        
                        # Collect spectrum data (Solis→SIF / SDK2→FVB / server→TCP)
                        QApplication.processEvents()  # snap_spectrum 전 UI 이벤트 처리
                        QTest.qWait(self.short_delay)
                        spectrum_success = self.snap_spectrum(custom_filename=point_filename)
                        if spectrum_success:
                            if self.rbtn_sdk2.isChecked():
                                # plot_spe + CSV는 snap_spectrum → _snap_spectrum_sdk2 에서 처리
                                pass
                            else:
                                try:
                                    # Generate the path for the saved SIF file
                                    folder_path = self.get_save_folder_path()
                                    if folder_path:
                                        sif_file_path = os.path.join(folder_path, f"{point_filename}.SIF")
                                        sif_file_path = os.path.normpath(sif_file_path)
                                    else:
                                        sif_file_path = f"{point_filename}.SIF"
                                    
                                    self.debug_print(f"Reading spectrum from: {sif_file_path}")
                                    sif_read = SIF(file_path=sif_file_path)
                                    wavelength, intensity = sif_read.read()
                                    
                                    # Plot spectrum data
                                    self.plot_spe(wavelength, intensity)
                                    
                                except Exception as e:
                                    self.debug_print(f"Error reading or saving spectrum data: {e}")
                        else:
                            self.debug_print("Spectrum acquisition failed, skipping spectrum data processing")
                        
                        if not self.rbtn_sdk2.isChecked():
                            # Show page2 of the tabWidget (Solis 경로에서 스펙트럼 탭 확인용)
                            self.tabWidget.setCurrentIndex(1)  # page2 is index 1
                            QTest.qWait(1500)
                            self.tabWidget.setCurrentIndex(0)  # page1 is index 0

                        # Prepare for image measurement
                        try:
                            self.mff101_move2()  # Move beam to camera
                            QTest.qWait(self.flip_delay)
                            # Turn on LED
                            if not self.btn_LED_toggle.isChecked():
                                self._led_on_for_mapping()
                            QTest.qWait(self.led_delay)
                            self.shutter_close()  # Close shutter
                            QTest.qWait(self.sutter_delay)
                        except Exception as e:
                            self.debug_print(f"Warning: Failed to prepare image measurement: {e}")
                            # Continue even if image measurement preparation fails
                        
                        if self.checkBox_imgSave.isChecked():
                            save_folder = self.get_save_folder_path()
                            if save_folder:
                                png_save_path = os.path.join(save_folder, f"{point_filename}.png")
                            else:
                                fallback_dir = os.path.normpath("Z:/.data/")
                                os.makedirs(fallback_dir, exist_ok=True)
                                png_save_path = os.path.join(fallback_dir, f"{point_filename}.png")
                            self.current_image_path = os.path.normpath(png_save_path)
                            self.save_image_flag = True
                            QApplication.processEvents()
                            QTest.qWait(500)

                        # X-axis movement (except for the last point in current row)
                        # Check if we need to move to next point in X direction
                        need_x_move = False
                        if j % 2 == 0:  # Forward direction (left to right)
                            if i != (x_value - 1):
                                next_i, next_j = i + 1, j
                                next_point = (next_i + 1, next_j + 1)
                                if next_point not in skip_positions:
                                    need_x_move = True
                                    move_hx = hx_val  # Move forward
                                    move_hy = hy_val
                        else:  # Reverse direction (right to left)
                            if i != 0:
                                next_i, next_j = i - 1, j
                                next_point = (next_i + 1, next_j + 1)
                                if next_point not in skip_positions:
                                    need_x_move = True
                                    move_hx = -hx_val  # Move backward
                                    move_hy = -hy_val
                        
                        if need_x_move:
                            self.mapping_move(move_hx, move_hy)  # X축 이동
                            self.find_dot = True  # Enable dot finding
                            QTest.qWait(self.move_delay)

                            # Move to closest dot (조정)
                            if [i, j] not in self.except_point:
                                for _ in range(4):
                                    closest_point, distance = self.cal_closest_dot()  # Calculate closest dot
                                    QTest.qWait(self.short_delay)
                                    
                                    # Move only if dot is detected and distance is less than 25
                                    # Skip move_closest_dot for specific coordinates: [7,7], [7,8], [8,7], [8,8]
                                    skip_positions = [(7, 7), (7, 8), (8, 7), (8, 8)]
                                    # 이동 후 도착 셀 (next_i, next_j) — 루프의 i는 아직 이전 열
                                    current_position = (next_i + 1, next_j + 1)
                                    
                                    if len(self.points) > 0 and distance < 60:
                                        if current_position in skip_positions:
                                            self.debug_print(f"Skipping move_closest_dot for position {current_position}")
                                        else:
                                            self.debug_print(f"Moving to closest dot, distance: {distance}")
                                            self.move_closest_dot(closest_point)
                                            QTest.qWait(self.short_delay)
                                    elif len(self.points) == 0:
                                        self.debug_print("No dots detected")
                                        self.not_find_img = True
                                        break
                                    else:
                                        self.debug_print(f"Distance too large: {distance}")
                                        if self.not_find_img:
                                            break
                                        else:
                                            # # Open manual adjustment window
                                            # self.w = AnotherWindow()
                                            # self.w.show()
                                            # while self.w.isVisible():
                                            #     QTest.qWait(self.subwindow_delay)
                                            break
                                QTest.qWait(self.short_delay)
                            self.find_dot = False  # Disable dot finding

                        # Update progress (실제 처리한 포인트 수 기준)
                        if total_point_no > 0:
                            self.progressBar.setValue(int(round(100 * (processed_count / total_point_no), 0)))
                        else:
                            self.progressBar.setValue(100)

                    # Y-axis movement (except last line)
                    if j != (y_value - 1):
                        # skip으로 인해 해당 row에 방문한 포인트가 없으면 Y축 이동 생략
                        if last_visited_i is None:
                            self.debug_print(f"Row {j+1} had only skip points, skipping Y-move")
                            continue
                        
                        QTest.qWait(self.delay_time)
                        self.motor_read_s()
                        QTest.qWait(self.short_delay)
                        self.motor_read_s()
                        QTest.qWait(self.short_delay)
                        
                        # 현재 위치에서 다음 라인의 시작 포인트로 이동 (Zigzag pattern)
                        # 상대 이동 거리로 계산
                        current_x = int(self.label_19.text())
                        current_y = int(self.label_21.text())
                        
                        # Y축은 항상 한 라인 위로 (vy_val만큼)
                        move_y = vy_val
                        # skip으로 row 끝이 아닌 중간에서 Y이동 시: (6,7)->(6,8)처럼 X이동 없이 같은 열 유지
                        # row 끝(정순: x_value-1, 역순: 0)이면 vx_val 사용, 아니면 move_x=0
                        row_end_i = (x_value - 1) if j % 2 == 0 else 0
                        if last_visited_i == row_end_i:
                            move_x = vx_val
                        else:
                            move_x = 0  # 같은 열 유지, (6,7)->(6,8)
                        
                        self.debug_print(f"Y-line move (zigzag): last({last_visited_i+1},{last_visited_j+1}) -> move({move_x},{move_y})")
                        self.mapping_move(move_x, move_y)  # 다음 라인의 시작 포인트로 이동
                    
                        self.find_dot = True  # Enable dot finding
                        QTest.qWait(self.move_delay)
                        # Move to closest dot (조정)
                        if [last_visited_i, last_visited_j] not in self.except_point:
                            # Y 이동 직후 맞출 셀 = 다음 행(j+1)의 지그재그 첫 열 (i는 방금 끝낸 행의 마지막 열이라 쓰면 안 됨)
                            next_j0 = j + 1
                            if next_j0 % 2 == 0:
                                first_i_next = 0
                            else:
                                first_i_next = x_value - 1
                            align_cell_1based = (first_i_next + 1, next_j0 + 1)
                            for _ in range(CLOSEST_DOT_MAX_ITERATIONS):
                                closest_point, distance = self.cal_closest_dot()  # Calculate the closest dot
                                QTest.qWait(self.short_delay)
                                
                                if distance < CLOSEST_DOT_DISTANCE_THRESHOLD:
                                    self.debug_print(
                                        f"Distance {distance:.2f} < {CLOSEST_DOT_DISTANCE_THRESHOLD}, target reached"
                                    )
                                    break
                                
                                # Move only if a dot is detected and the distance is less than 100
                                # Skip move_closest_dot for specific coordinates: [7,7], [7,8], [8,7], [8,8]
                                skip_positions = [(7, 7), (7, 8), (8, 7), (8, 8)]
                                current_position = align_cell_1based
                                
                                if len(self.points) > 0 and distance < 100:
                                    if current_position in skip_positions:
                                        self.debug_print(f"Skipping move_closest_dot for position {current_position}")
                                    else:
                                        self.debug_print(f"Moving to closest dot, distance: {distance}")
                                        self.move_closest_dot(closest_point)
                                        QTest.qWait(self.short_delay)
                                elif len(self.points) == 0:
                                    self.debug_print("No dots detected")
                                    self.not_find_img = True
                                    break
                                else:
                                    self.debug_print(f"Distance too large: {distance}")
                                    if self.not_find_img:
                                        break
                                    else:
                                        # Open manual adjustment window
                                        # self.w = AnotherWindow()
                                        # self.w.show()
                                        # while self.w.isVisible():
                                        #     QTest.qWait(self.subwindow_delay)
                                        break
                            QTest.qWait(self.short_delay)
                        self.find_dot = False  # Disable dot finding
                
                # Mapping 완료 시 소리 재생 (창 없이)
                # sound.wav 우선: winsound 사용 (창 안 뜸). 없으면 sound.mp3 → os.startfile (기본 플레이어)
                base_dir = os.path.dirname(os.path.abspath(__file__))
                sound_wav = os.path.join(base_dir, 'sound.wav')
                sound_mp3 = os.path.join(base_dir, 'sound.mp3')
                if os.path.exists(sound_wav):
                    try:
                        import winsound
                        winsound.PlaySound(sound_wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    except Exception as e:
                        self.debug_print(f"Could not play sound: {e}")
                elif os.path.exists(sound_mp3):
                    try:
                        if sys.platform == 'win32':
                            os.startfile(sound_mp3)
                        else:
                            import subprocess
                            cmd = ['xdg-open', sound_mp3] if sys.platform.startswith('linux') else ['open', sound_mp3]
                            subprocess.Popen(cmd)
                    except Exception as e:
                        self.debug_print(f"Could not play sound: {e}")
            else:
                self.show_message_box('Please connect to the server')  # Server connection notification message
        except Exception as e:
            self.debug_print(f"Critical error in mapping_start: {e}")
            QMessageBox.critical(self, "Error", f"Mapping process failed: {e}")
            # Reset progress bar and status label on error
            self.progressBar.setValue(0)
            self.label_35.setText("Mapping failed - check error log")

    def mapping_move(self, x_value, y_value):
        """DS102 형식으로 매핑 이동 (X축=axis1, Y축=axis2)"""
        QTest.qWait(100)
        
        # Y축 이동 (axis 1)
        if y_value != 0:
            axis_num = '1'
            direction = 'CW' if y_value > 0 else 'CCW'
            pulse_count = abs(y_value)
            
            # DS102 step command for axis 1 (Y)
            y_cmd = f'AXI{axis_num}:L0 100:R0 100:S0 100:F0 1000:PULS {pulse_count}:GO {direction}\r'
            self.ds102_send_command(y_cmd)
            
            # Wait for completion
            self.ds102_wait_for_completion(axis_num)
        QTest.qWait(200)
        
        # X축 이동 (axis 2)
        if x_value != 0:
            axis_num = '2'
            direction = 'CW' if x_value > 0 else 'CCW'
            pulse_count = abs(x_value)
            
            # DS102 step command for axis 2 (X)
            x_cmd = f'AXI{axis_num}:L0 100:R0 100:S0 100:F0 1000:PULS {pulse_count}:GO {direction}\r'
            self.ds102_send_command(x_cmd)
            
            # Wait for completion
            self.ds102_wait_for_completion(axis_num)
        QTest.qWait(100)
        
        # self.debug_print(f'Move : {x_value}, {y_value}')

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
        """Save configuration in modern JSON format (English)"""
        config = {
            "motor_settings": {
                "lineEdit_2": self.lineEdit_2.text(),
                "lineEdit_6": self.lineEdit_6.text(),
                "lineEdit_3": self.lineEdit_3.text(),
                "lineEdit_7": self.lineEdit_7.text(),
                "lineEdit_8": self.lineEdit_8.text(),
                "lineEdit_4": self.lineEdit_4.text(),
                "spinBox": self.spinBox.value(),
                "spinBox_2": self.spinBox_2.value(),
                "label_26": self.label_26.text(),
                "label_29": self.label_29.text(),
                "label_31": self.label_31.text(),
                "label_33": self.label_33.text()
            },
            "laser_settings": {
                "position_x": self.lp_x.value(),
                "position_y": self.lp_y.value(),
                "threshold_laser": self.thre_laser.text(),
                "threshold_dots": self.thre_dots.text()
            },
            "detection_settings": {
                "max_detection_count": self.max_detection_count
            },
            "file_settings": {
                "file_name": self.lineEdit_fn.text(),
                "folder_path": self.label_fp.text()
            },
            "itc503_settings": {
                "gpib_address": self.lineEdit_ledport_2.text()
            },
            "focus_mapping_settings": {
                "fm_step": self.fm_step.text(),
                "fm_step_2": self.fm_step_2.text(),
                "fm_step_3": self.fm_step_3.text(),
                "spinBox_afoffset": self.spinBox_afoffset.value(),
                "mapping_expanding_chk": self.mapping_expanding_chk.isChecked(),
                "no_expanding": self.no_expanding.text(),
            },
            "version": "1.0"
        }
        
        try:
            with open('config.json', 'w', encoding='utf-8') as file:
                json.dump(config, file, indent=2, ensure_ascii=False)
            self.debug_print("Configuration saved successfully to config.json")
        except Exception as e:
            self.debug_print(f"Error saving configuration: {e}")
            QMessageBox.warning(self, "Configuration Save Error", f"An error occurred while saving the configuration:\n{e}")

    def load_config(self):
        """Load configuration in JSON format"""
        # Try to load configuration in JSON format
        if self._load_json_config():
            return
        
        # Set default values if JSON loading fails
        self.debug_print("JSON config not found or invalid, using default values")
        self._set_default_config()
        
        # Create a new JSON file with default values
        self.save_config()
    
    def _load_json_config(self):
        """Load configuration in JSON format"""
        try:
            with open('config.json', 'r', encoding='utf-8') as file:
                config = json.load(file)
            
            # 모터 설정
            motor = config.get("motor_settings", {})
            self.lineEdit_2.setText(motor.get("lineEdit_2", ""))
            self.lineEdit_6.setText(motor.get("lineEdit_6", ""))
            self.lineEdit_3.setText(motor.get("lineEdit_3", ""))
            self.lineEdit_7.setText(motor.get("lineEdit_7", ""))
            self.lineEdit_8.setText(motor.get("lineEdit_8", ""))
            self.lineEdit_4.setText(motor.get("lineEdit_4", ""))
            self.spinBox.setValue(motor.get("spinBox", 0))
            self.spinBox_2.setValue(motor.get("spinBox_2", 0))
            self.label_26.setText(motor.get("label_26", ""))
            self.label_29.setText(motor.get("label_29", ""))
            self.label_31.setText(motor.get("label_31", ""))
            self.label_33.setText(motor.get("label_33", ""))
            
            # Laser settings
            laser = config.get("laser_settings", {})
            self.lp_x.setValue(laser.get("position_x", 0))
            self.lp_y.setValue(laser.get("position_y", 0))
            self.thre_laser.setText(laser.get("threshold_laser", "0.5"))
            self.thre_dots.setText(laser.get("threshold_dots", "0.5"))
            
            # Detection settings
            detection = config.get("detection_settings", {})
            self.max_detection_count = detection.get("max_detection_count", 80)
            
            # File settings
            file_settings = config.get("file_settings", {})
            self.lineEdit_fn.setText(file_settings.get("file_name", "data"))
            folder_path = file_settings.get("folder_path", "None")
            self.label_fp.setText(folder_path if folder_path and folder_path != "None" else "None")
            
            # ITC503 settings
            itc503 = config.get("itc503_settings", {})
            self.lineEdit_ledport_2.setText(itc503.get("gpib_address", "GPIB0::24::INSTR"))
            
            # Focus / mapping expanding (AF step, expanding repeat)
            fm_map = config.get("focus_mapping_settings", {})
            self.fm_step.setText(fm_map.get("fm_step", "20"))
            self.fm_step_2.setText(fm_map.get("fm_step_2", "5"))
            self.fm_step_3.setText(fm_map.get("fm_step_3", "30"))
            try:
                self.spinBox_afoffset.setValue(int(fm_map.get("spinBox_afoffset", 0)))
            except (TypeError, ValueError):
                self.spinBox_afoffset.setValue(0)
            self.mapping_expanding_chk.setChecked(bool(fm_map.get("mapping_expanding_chk", False)))
            self.no_expanding.setText(fm_map.get("no_expanding", "5"))
            
            self.debug_print("Configuration loaded successfully from config.json")
            return True
            
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            self.debug_print(f"Failed to load JSON config: {e}")
            return False
    
    def _set_default_config(self):
        """Apply default configuration values"""
        self.debug_print("Applying default configuration values")
        
        # 기본값들
        self.lp_x.setValue(0)
        self.lp_y.setValue(0)
        self.thre_laser.setText("0.5")
        self.thre_dots.setText("0.5")
        self.lineEdit_fn.setText("data")
        self.max_detection_count = 80
        self.label_fp.setText("None")
        self.lineEdit_ledport_2.setText("GPIB0::24::INSTR")
        self.fm_step.setText("20")
        self.fm_step_2.setText("5")
        self.fm_step_3.setText("30")
        self.spinBox_afoffset.setValue(0)
        self.mapping_expanding_chk.setChecked(False)
        self.no_expanding.setText("5")

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
                # Read COM port and baud rate from UI
                port = str(self.lineEdit_gpib.text())
                baud_rate = int(self.lineEdit_gpib_2.text())
                
                # Create serial connection (DS102 style)
                self.inst = serial.Serial(port, baudrate=baud_rate, timeout=2)
                
                # Initialize command timing
                self.last_command_time = 0
                
                # Request ID to check DS102/DS112 controller connection
                r_data = self.ds102_send_command('*IDN?\r', wait_response=True)
                
                if r_data and 'SURUGA,DS1' in str(r_data):
                    # Request version
                    version_data = self.ds102_send_command('DS102VER?\r', wait_response=True)
                    self.debug_print(f"DS102 Version: {version_data}")
                    
                    # Request number of control axes
                    axes_data = self.ds102_send_command('CONTA?\r', wait_response=True)
                    self.debug_print(f"Number of axes: {axes_data}")
                    
                    # Initialize axes (assuming 2 axes for X,Y)
                    try:
                        num_axes = int(axes_data)
                        for axNo in range(min(num_axes, 2)):  # Limit to 2 axes (X,Y)
                            init_cmd = f'AXI{axNo + 1}:UNIT 0:SELSP 0\r'
                            self.ds102_send_command(init_cmd)
                        self.debug_print(f"Initialized {min(num_axes, 2)} axes")
                    except ValueError:
                        self.debug_print("Warning: Could not parse number of axes")
                    
                    self.gpib_conn_obj(True)
                    self.btn_gpib_conn.setText('Disconnect')
                    self.debug_print(f"DS102 Controller connected successfully on {port}")
                else:
                    self.inst.close()
                    QMessageBox.warning(self, "Warning", f"DS102/DS112 controller is not connected to {port}")
                    
            except (serial.serialutil.SerialException, ValueError) as e:
                if hasattr(self, 'inst') and isinstance(self.inst, serial.Serial) and self.inst.is_open:
                    self.inst.close()
                QMessageBox.warning(self, "Warning", f"Failed to connect Stepping Motor Controller\n\n{e}")
        else:
            self.gpib_conn_obj(False)
            # Stop position update when disconnecting
            self.stop_position_update()
            if hasattr(self, 'inst') and isinstance(self.inst, serial.Serial) and self.inst.is_open:
                self.inst.close()
            self.btn_gpib_conn.setText('Connect')

    def fw102c_connect(self):
        """FW102C Filter Wheel 연결/해제"""
        if str(self.btn_gpib_conn_2.text()) == 'Connect':
            try:
                # Read COM port and baud rate from UI
                port = str(self.lineEdit_gpib_3.text()).strip()
                baud_rate = int(self.lineEdit_gpib_4.text().strip())
                
                if not port:
                    QMessageBox.warning(self, "Warning", "Please enter COM port")
                    return
                
                # Create FW102C instance and connect
                self.fw102c = FW102C(port=port, baudrate=baud_rate, timeout=2.0)
                
                if self.fw102c.connect():
                    # Connection successful
                    self.fw102c_connected = True
                    self.btn_gpib_conn_2.setText('Disconnect')
                    
                    # Get device ID
                    device_id = self.fw102c.get_id()
                    self.debug_print(f"FW102C Device ID: {device_id}")
                    
                    # Get and display current position
                    self.fw102c_update_position()
                    
                    # Enable control buttons
                    self.pushButton.setEnabled(True)
                    self.pushButton_5.setEnabled(True)
                    
                    self.debug_print(f"FW102C connected successfully on {port}")
                else:
                    QMessageBox.warning(self, "Warning", f"Failed to connect FW102C on {port}")
                    self.fw102c = None
                    self.fw102c_connected = False
                    
            except (ValueError, Exception) as e:
                QMessageBox.warning(self, "Warning", f"Failed to connect FW102C Filter Wheel\n\n{e}")
                self.fw102c = None
                self.fw102c_connected = False
        else:
            # Disconnect
            if self.fw102c:
                self.fw102c.disconnect()
                self.fw102c = None
            
            self.fw102c_connected = False
            self.btn_gpib_conn_2.setText('Connect')
            
            # Disable control buttons
            self.pushButton.setEnabled(False)
            self.pushButton_5.setEnabled(False)
            
            # Clear position display
            self.label_38.setText('-')
            
            self.debug_print("FW102C disconnected")

    def fw102c_update_position(self):
        """현재 필터 휠 위치 업데이트"""
        if self.fw102c_connected and self.fw102c:
            try:
                position = self.fw102c.get_position()
                if position > 0:
                    self.label_38.setText(str(position))
                    self.debug_print(f"FW102C current position: {position}")
                else:
                    self.label_38.setText('Error')
                    self.debug_print("Failed to read FW102C position")
            except Exception as e:
                self.debug_print(f"Error reading FW102C position: {e}")
                self.label_38.setText('Error')

    def fw102c_position_up(self):
        """필터 휠 위치 증가 (다음 위치로 이동)"""
        if not self.fw102c_connected or not self.fw102c:
            QMessageBox.warning(self, "Warning", "FW102C is not connected")
            return
        
        try:
            # Get current position
            current_pos = self.fw102c.get_position()
            if current_pos <= 0:
                QMessageBox.warning(self, "Warning", "Failed to read current position")
                return
            
            # Get position count (6 or 12)
            pos_count = self.fw102c.get_position_count()
            if pos_count <= 0:
                pos_count = 6  # Default to 6
            
            # Calculate next position (wrap around)
            next_pos = (current_pos % pos_count) + 1
            
            self.debug_print(f"Moving FW102C from position {current_pos} to {next_pos}")
            
            # Move to next position
            response = self.fw102c.set_position(next_pos)
            self.debug_print(f"FW102C response: {response}")
            
            # Wait for movement to complete
            QTest.qWait(500)
            
            # Update position display
            self.fw102c_update_position()
            
        except Exception as e:
            self.debug_print(f"Error moving FW102C up: {e}")
            QMessageBox.warning(self, "Error", f"Failed to move filter wheel\n\n{e}")

    def fw102c_position_down(self):
        """필터 휠 위치 감소 (이전 위치로 이동)"""
        if not self.fw102c_connected or not self.fw102c:
            QMessageBox.warning(self, "Warning", "FW102C is not connected")
            return
        
        try:
            # Get current position
            current_pos = self.fw102c.get_position()
            if current_pos <= 0:
                QMessageBox.warning(self, "Warning", "Failed to read current position")
                return
            
            # Get position count (6 or 12)
            pos_count = self.fw102c.get_position_count()
            if pos_count <= 0:
                pos_count = 6  # Default to 6
            
            # Calculate previous position (wrap around)
            prev_pos = ((current_pos - 2) % pos_count) + 1
            
            self.debug_print(f"Moving FW102C from position {current_pos} to {prev_pos}")
            
            # Move to previous position
            response = self.fw102c.set_position(prev_pos)
            self.debug_print(f"FW102C response: {response}")
            
            # Wait for movement to complete
            QTest.qWait(500)
            
            # Update position display
            self.fw102c_update_position()
            
        except Exception as e:
            self.debug_print(f"Error moving FW102C down: {e}")
            QMessageBox.warning(self, "Error", f"Failed to move filter wheel\n\n{e}")

    def shutter_conn(self):
        if str(self.btn_shutter_conn.text()) == 'Connect':
            try:
                self.lineEdit_shutter_time.setEnabled(True)
                self.btn_shutter_time.setEnabled(True)
                self.btn_shutter_toggle.setEnabled(True)
                port = str(self.lineEdit_shutter_port.text())
                # readline() 대기 상한: 너무 길면(예: 8s) 간헐적으로 UI가 멈춘 것처럼 보임
                self.serial_connection_2 = serial.Serial(port, baudrate=115200, timeout=0.6)
                self.btn_shutter_conn.setText('Disconnect')
            except serial.serialutil.SerialException as e:
                QMessageBox.warning(self, "Warning", f"Failed to connect Shutter.\n\n{e}")
        else:
            self.lineEdit_shutter_time.setEnabled(False)
            self.btn_shutter_time.setEnabled(False)
            self.btn_shutter_toggle.setEnabled(False)
            self.serial_connection_2.close()
            self.btn_shutter_conn.setText('Connect')

    def shutter_toggle(self):
        if str(self.btn_shutter_conn.text()) == 'Disconnect':
            if self.btn_shutter_toggle.isChecked():
                # Shutter Open
                self.serial_connection_2.write(bytes('0\n', encoding='ascii'))
                self.btn_shutter_toggle.setText('Shutter Open')
            else:
                # Shutter Close
                self.serial_connection_2.write(bytes('1\n', encoding='ascii'))
                self.btn_shutter_toggle.setText('Shutter Close')
            
            self.serial_connection_2.flush()
            line = self.serial_connection_2.readline()
            # self.debug_print(line)
            return True
        else:
            QMessageBox.warning(self, "Warning", f"Failed to connect Shutter. Click the Shutter connect btn")
            return False

    def shutter_open(self):
        """Open the shutter by setting button to checked state"""
        if str(self.btn_shutter_conn.text()) == 'Disconnect':
            if not self.btn_shutter_toggle.isChecked():
                # Set button to checked state (Open)
                self.btn_shutter_toggle.setChecked(True)
                # Send open command
                self.serial_connection_2.write(bytes('0\n', encoding='ascii'))
                self.btn_shutter_toggle.setText('Shutter Open')
                self.serial_connection_2.flush()
                line = self.serial_connection_2.readline()
            return True
        else:
            QMessageBox.warning(self, "Warning", f"Failed to connect Shutter. Click the Shutter connect btn")
            return False

    def shutter_close(self):
        """Close the shutter by setting button to unchecked state"""
        if str(self.btn_shutter_conn.text()) == 'Disconnect':
            if self.btn_shutter_toggle.isChecked():
                # Set button to unchecked state (Close)
                self.btn_shutter_toggle.setChecked(False)
                # Send close command
                self.serial_connection_2.write(bytes('1\n', encoding='ascii'))
                self.btn_shutter_toggle.setText('Shutter Close')
                self.serial_connection_2.flush()
                line = self.serial_connection_2.readline()
            return True
        else:
            QMessageBox.warning(self, "Warning", f"Failed to connect Shutter. Click the Shutter connect btn")
            return False

    def shutter_time(self):
        if str(self.btn_shutter_conn.text()) == 'Disconnect':
            # self.serial_connection_2.write(bytes(f'60,{self.lineEdit_shutter_time.text()}\r\n', encoding='ascii'))
            self.serial_connection_2.write(bytes(f't,{self.lineEdit_shutter_time.text()}\n', encoding='ascii'))
            line = self.serial_connection_2.readline()
            self.debug_print(line)
        else:
            QMessageBox.warning(self, "Warning", f"Failed to connect Shutter. Click the Shutter connect btn")

    def LED_connect(self):
        if str(self.btn_ledconn.text()) == 'Connect':
            try:
                self.btn_LED_toggle.setEnabled(True)
                port = str(self.lineEdit_ledport.text())
                self.serial_connection = serial.Serial(port, baudrate=115200, timeout=0.3)
                self.btn_ledconn.setText('Disconnect')
            except serial.serialutil.SerialException as e:
                QMessageBox.warning(self, "Warning", f"Failed to connect LED.\n\n{e}")
        else:
            # self.lineEdit_LEDBV.setEnabled(False)  # UI element not found
            # self.btn_LEDBV_SET.setEnabled(False)   # UI element not found
            self.btn_LED_toggle.setEnabled(False)
            self.serial_connection.close()
            self.btn_ledconn.setText('Connect')

    def LED_on(self):
        if str(self.btn_ledconn.text()) == 'Disconnect':
            self.serial_connection.write(bytes('0\r\n', encoding='ascii'))
            return True
        else:
            QMessageBox.warning(self, "Warning", f"Failed to connect LED. Click the LED connect btn")
            return False

    def LED_off(self):
        self.serial_connection.write(bytes('1\r\n', encoding='ascii'))

    def _led_off_for_mapping(self) -> None:
        """매핑 중 LED 끄기: 직렬 전송만 수행. 미연결 시 모달 없음(프리징 방지)."""
        if str(self.btn_ledconn.text()) != 'Disconnect':
            self.debug_print("Mapping: LED not connected, skip LED off")
            return
        try:
            self.serial_connection.write(bytes('1\r\n', encoding='ascii'))
            self.serial_connection.flush()
            self.btn_LED_toggle.blockSignals(True)
            self.btn_LED_toggle.setChecked(False)
            self.btn_LED_toggle.setText('LED OFF')
            self.btn_LED_toggle.blockSignals(False)
        except Exception as e:
            self.debug_print(f"Mapping: LED off failed: {e}")
            self.btn_LED_toggle.blockSignals(False)

    def _led_on_for_mapping(self) -> None:
        """매핑 중 LED 켜기: 직렬 전송만 수행. 미연결 시 모달 없음."""
        if str(self.btn_ledconn.text()) != 'Disconnect':
            self.debug_print("Mapping: LED not connected, skip LED on")
            return
        try:
            self.serial_connection.write(bytes('0\r\n', encoding='ascii'))
            self.serial_connection.flush()
            self.btn_LED_toggle.blockSignals(True)
            self.btn_LED_toggle.setChecked(True)
            self.btn_LED_toggle.setText('LED ON')
            self.btn_LED_toggle.blockSignals(False)
        except Exception as e:
            self.debug_print(f"Mapping: LED on failed: {e}")
            self.btn_LED_toggle.blockSignals(False)

    def LED_toggle(self):
        if str(self.btn_ledconn.text()) == 'Disconnect':
            if self.btn_LED_toggle.isChecked():
                # LED ON
                self.serial_connection.write(bytes('0\r\n', encoding='ascii'))
                self.btn_LED_toggle.setText('LED ON')
            else:
                # LED OFF
                self.serial_connection.write(bytes('1\r\n', encoding='ascii'))
                self.btn_LED_toggle.setText('LED OFF')
            
            self.serial_connection.flush()
            return True
        else:
            QMessageBox.warning(self, "Warning", f"Failed to connect RED LED. Click the LED connect btn")
            return False

    def ITC503_connect(self):
        """ITC503 Temperature Controller connection"""
        if str(self.btn_ledconn_2.text()) == 'Connect':
            try:
                # Get GPIB address from lineEdit
                gpib_address = str(self.lineEdit_ledport_2.text()).strip()
                if not gpib_address:
                    QMessageBox.warning(self, "Warning", "Please enter GPIB address (e.g., GPIB0::24::INSTR)")
                    return
                
                # Create VISA resource manager
                rm = pyvisa.ResourceManager()
                
                # Connect to ITC503
                self.itc503_connection = rm.open_resource(gpib_address)
                self.itc503_connection.read_termination = '\r'
                self.itc503_connection.timeout = 5000  # 5 second timeout
                
                # Test connection by reading temperature
                try:
                    temp = self.itc503_connection.query("R1")
                    self.label_5.setText(f"{temp.strip()} K")
                    self.debug_print(f"ITC503 connected: Temperature = {temp.strip()} K")
                except Exception as e:
                    self.debug_print(f"Warning: Connected but failed to read temperature: {e}")
                    self.label_5.setText("Connected")
                
                self.itc503_connected = True
                self.btn_ledconn_2.setText('Disconnect')
                
                # Start temperature monitoring timer (optional)
                if not hasattr(self, 'itc503_timer'):
                    self.itc503_timer = QTimer(self)
                    self.itc503_timer.timeout.connect(self.ITC503_read_temperature)
                self.itc503_timer.start(2000)  # Read every 2 seconds
                
                QMessageBox.information(self, "Success", f"ITC503 connected successfully\nAddress: {gpib_address}")
                
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Failed to connect ITC503.\n\n{e}")
                self.debug_print(f"ITC503 connection error: {e}")
                self.itc503_connected = False
        else:
            # Disconnect
            try:
                if hasattr(self, 'itc503_timer'):
                    self.itc503_timer.stop()
                
                if self.itc503_connection:
                    self.itc503_connection.close()
                    self.itc503_connection = None
                
                self.itc503_connected = False
                self.btn_ledconn_2.setText('Connect')
                self.label_5.setText("Disconnected")
                self.debug_print("ITC503 disconnected")
                
            except Exception as e:
                self.debug_print(f"Error disconnecting ITC503: {e}")

    def ITC503_read_temperature(self):
        """Read temperature from ITC503"""
        if self.itc503_connected and self.itc503_connection:
            try:
                # Read temperature (R1 = Channel 1)
                temperature = self.itc503_connection.query("R1")
                temp_value = temperature.strip()
                self.label_5.setText(f"{temp_value} K")
                return temp_value
            except Exception as e:
                self.debug_print(f"Failed to read ITC503 temperature: {e}")
                self.label_5.setText("Read Error")
                return None
        else:
            return None

    def fm_connect(self):
        """Connect/disconnect to stepper motor via serial"""
        if str(self.btn_fm.text()) == 'Connect':
            try:
                port = str(self.fm_port.text()).strip()
                baudrate = int(self.fm_br.text().strip())
                
                if not port:
                    QMessageBox.warning(self, "Warning", "Please enter COM port")
                    return
                
                # Create serial connection
                self.fm_serial = serial.Serial(port, baudrate=baudrate, timeout=2)
                
                # Update button state
                self.btn_fm.setText('Disconnect')
                
                # Enable control buttons
                self.btn_fm_enable.setEnabled(True)
                self.fm_step.setEnabled(True)
                self.btn_fm_cw.setEnabled(True)
                self.btn_fm_ccw.setEnabled(True)
                self.btn_af.setEnabled(True)
                
                self.debug_print(f"Stepper motor connected on {port} at {baudrate} baud")
                
                # Wait a bit and send disable command
                QTest.qWait(100)
                self.fm_serial.write(bytes('d\n', encoding='ascii'))
                self.fm_serial.flush()
                
                # Set button to unchecked state (disabled motor state)
                self.btn_fm_enable.setChecked(False)
                self.btn_fm_enable.setText('Disabled')
                
                self.debug_print("Stepper motor disabled (initial state)")
                
            except (serial.serialutil.SerialException, ValueError) as e:
                QMessageBox.warning(self, "Warning", f"Failed to connect stepper motor.\n\n{e}")
                if hasattr(self, 'fm_serial') and self.fm_serial.is_open:
                    self.fm_serial.close()
        else:
            # Disconnect
            try:
                if hasattr(self, 'fm_serial') and self.fm_serial.is_open:
                    self.fm_serial.close()
                
                # Update button state
                self.btn_fm.setText('Connect')
                
                # Disable control buttons
                self.btn_fm_enable.setEnabled(False)
                self.btn_fm_enable.setChecked(False)
                self.btn_fm_enable.setText('Disabled')
                self.fm_step.setEnabled(False)
                self.btn_fm_cw.setEnabled(False)
                self.btn_fm_ccw.setEnabled(False)
                self.btn_af.setEnabled(False)
                
                self.debug_print("Stepper motor disconnected")
                
            except Exception as e:
                self.debug_print(f"Error disconnecting stepper motor: {e}")

    def fm_enable_disable(self):
        """Enable/disable stepper motor (toggle button)"""
        if str(self.btn_fm.text()) == 'Disconnect':
            if self.btn_fm_enable.isChecked():
                # Button is checked -> Enable motor
                self.fm_serial.write(bytes('e\n', encoding='ascii'))
                self.fm_serial.flush()
                self.btn_fm_enable.setText('Enabled')
                self.debug_print("Stepper motor enabled")
            else:
                # Button is unchecked -> Disable motor
                self.fm_serial.write(bytes('d\n', encoding='ascii'))
                self.fm_serial.flush()
                self.btn_fm_enable.setText('Disabled')
                self.debug_print("Stepper motor disabled")
        else:
            QMessageBox.warning(self, "Warning", "Stepper motor is not connected")

    def fm_cw(self):
        """Rotate stepper motor clockwise"""
        if str(self.btn_fm.text()) == 'Disconnect':
            try:
                steps = int(self.fm_step.text().strip())
                
                if steps <= 0:
                    QMessageBox.warning(self, "Warning", "Steps must be a positive number")
                    return
                
                # Send CW command with steps
                command = f'cw,{steps}\n'
                self.fm_serial.write(bytes(command, encoding='ascii'))
                self.fm_serial.flush()
                
                self.debug_print(f"Stepper motor CW: {steps} steps")
                
            except ValueError:
                QMessageBox.warning(self, "Warning", "Please enter a valid number for steps")
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Failed to send CW command.\n\n{e}")
                self.debug_print(f"Error in fm_cw: {e}")
        else:
            QMessageBox.warning(self, "Warning", "Stepper motor is not connected")

    def fm_ccw(self):
        """Rotate stepper motor counter-clockwise"""
        if str(self.btn_fm.text()) == 'Disconnect':
            try:
                steps = int(self.fm_step.text().strip())
                
                if steps <= 0:
                    QMessageBox.warning(self, "Warning", "Steps must be a positive number")
                    return
                
                # Send CCW command with steps
                command = f'ccw,{steps}\n'
                self.fm_serial.write(bytes(command, encoding='ascii'))
                self.fm_serial.flush()
                
                self.debug_print(f"Stepper motor CCW: {steps} steps")
                
            except ValueError:
                QMessageBox.warning(self, "Warning", "Please enter a valid number for steps")
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Failed to send CCW command.\n\n{e}")
                self.debug_print(f"Error in fm_ccw: {e}")
        else:
            QMessageBox.warning(self, "Warning", "Stepper motor is not connected")

    def _get_focus_metric(self, img_bgr):
        """Focus peaking 방식: Gaussian blur -> Sobel gradient magnitude mean. 레이저 위치 중심 ROI."""
        if img_bgr is None or img_bgr.size == 0:
            return 0.0
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        # ROI 크기: 이미지의 약 15% (더 작게)
        roi_half = min(h, w) // 7
        if roi_half < 10:
            roi_half = 10
        # 레이저 위치를 raw 이미지 좌표로 변환 (lp_x,lp_y는 스케일된 디스플레이 좌표)
        lpx, lpy = self.lp_x.value(), self.lp_y.value()
        if (lpx > 0 or lpy > 0) and self.lbl_video.width() > 0 and self.lbl_video.height() > 0:
            scale = min(self.lbl_video.width() / w, self.lbl_video.height() / h)
            if scale > 0.01:
                cx = int(lpx / scale)
                cy = int(lpy / scale)
            else:
                cx, cy = w // 2, h // 2
        else:
            cx, cy = w // 2, h // 2
        x1 = max(0, cx - roi_half)
        x2 = min(w, cx + roi_half)
        y1 = max(0, cy - roi_half)
        y2 = min(h, cy + roi_half)
        roi = gray[y1:y2, x1:x2]
        if roi.size == 0:
            return 0.0
        # Focus peaking 방식: Gaussian blur -> Sobel gradient magnitude
        # https://github.com/GreenpantsDeveloper/focus-peaking
        blurred = cv2.GaussianBlur(roi, (5, 5), 0)
        gx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(gx ** 2 + gy ** 2)
        return float(gradient_magnitude.mean())

    def _capture_frame_for_focus(self, discard_first=False):
        """Capture frame from camera for focus measurement. discard_first=True면 1프레임 버리고 다음 프레임 사용 (AF용)."""
        if not self.hcam or not self.pData:
            return None
        try:
            if discard_first:
                self.hcam.WaitImageV3(3000, self.pData, 0, 24, 0, None)
            self.hcam.WaitImageV3(3000, self.pData, 0, 24, 0, None)
        except nncam.HRESULTException:
            return None
        arr = np.frombuffer(bytes(self.pData), dtype=np.uint8).copy().reshape(
            self.imgHeight, self.imgWidth, 3)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    def _get_dot_count(self, limit=True, discard_first=False):
        """캡처 후 Find Dots 실행, #Dots 개수 반환. limit=False면 limit_detection_count 미적용. discard_first=True면 1프레임 버리고 캡처 (AF용)."""
        img = self._capture_frame_for_focus(discard_first=discard_first)
        if img is None:
            return 0
        try:
            if self.dot_detection_method == "yolo":
                pts = self.find_dots_yolo(img, self.val_thre_dot)
            else:
                pts = self.find_dots_template_improved(img, self.val_thre_dot)
            if limit:
                pts = self.limit_detection_count(pts)
            return len(pts)
        except Exception:
            return 0

    def _gaussian_fit_peak(self, positions, dot_counts):
        """가우시안 피팅으로 peak 중심 위치(mu) 반환. 실패 시 argmax 사용."""
        def gaussian(x, a, mu, sigma, c):
            return a * np.exp(-(x - mu) ** 2 / (2 * sigma ** 2)) + c

        pos_arr = np.array(positions, dtype=float)
        cnt_arr = np.array(dot_counts, dtype=float)
        if len(pos_arr) < 3 or np.std(cnt_arr) < 1e-6:
            return float(positions[int(np.argmax(dot_counts))])

        amp = np.max(cnt_arr) - np.min(cnt_arr)
        mu0 = pos_arr[np.argmax(cnt_arr)]
        sigma0 = (np.max(pos_arr) - np.min(pos_arr)) / 4 or 1.0
        c0 = np.min(cnt_arr)
        try:
            popt, _ = curve_fit(
                gaussian, pos_arr, cnt_arr,
                p0=[amp, mu0, sigma0, c0],
                bounds=([0, pos_arr.min(), 0.1, -1e6], [1e6, pos_arr.max(), 1e6, 1e6]),
                maxfev=5000
            )
            return float(popt[1])  # mu = center
        except (RuntimeError, ValueError):
            return float(positions[int(np.argmax(dot_counts))])

    def auto_focus(self):
        """Auto focus: CW 100 -> CCW 스캔 100 -> Peak 그래프 표시 -> Peak 위치로 CW 이동."""
        if not self.hcam:
            QMessageBox.warning(self, "Warning", "Camera is not open.")
            return
        if str(self.btn_fm.text()) != 'Disconnect' or not self.fm_serial or not self.fm_serial.is_open:
            QMessageBox.warning(self, "Warning", "Stepper motor is not connected.")
            return
        if self.dot_detection_method != "yolo" and not os.path.exists('dot_img.png'):
            QMessageBox.warning(self, "Warning", "Find Dots (template) requires dot_img.png.")
            return
        try:
            step = int(self.fm_step.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Warning", "Please enter a valid step value.")
            return
        if step <= 0:
            QMessageBox.warning(self, "Warning", "Step must be a positive number.")
            return

        settle_delay = 300  # 스캔 속도 (2배 빠르게, 500->250ms)
        try:
            scan_range = int(self.fm_step_3.text().strip())
        except (ValueError, AttributeError):
            scan_range = 100
        if scan_range <= 0:
            QMessageBox.warning(self, "Warning", "AF Scan must be a positive number.")
            return
        cmd_cw = f'cw,{step}\n'
        cmd_ccw = f'ccw,{step}\n'

        self.btn_af.setEnabled(False)
        self.find_dot = True
        _af_motor_was_enabled = self.btn_fm_enable.isChecked()
        try:
            # AF 구간: btn_fm_enable 과 동일하게 enable(e) → 종료 시 disable(d)
            if not _af_motor_was_enabled:
                try:
                    self.fm_serial.write(bytes('e\n', encoding='ascii'))
                    self.fm_serial.flush()
                    self.btn_fm_enable.blockSignals(True)
                    self.btn_fm_enable.setChecked(True)
                    self.btn_fm_enable.setText('Enabled')
                    self.btn_fm_enable.blockSignals(False)
                    self.debug_print("Auto focus: stepper enabled for AF")
                except Exception as e:
                    self.debug_print(f"Auto focus: failed to enable stepper: {e}")
                    QMessageBox.warning(self, "Warning", f"Could not enable stepper for auto-focus.\n\n{e}")
                    self.find_dot = False
                    self.btn_af.setEnabled(True)
                    return
            else:
                self.debug_print("Auto focus: stepper already enabled, continuing")
            ax = self.af_peak_widget.axes if hasattr(self, 'af_peak_widget') else None
            # AF Scan 값을 절반씩 줄이면서 5번 반복 (coarse-to-fine)
            for repeat in range(5):
                current_scan = max(1, scan_range // (2 ** repeat))
                self.debug_print(f"AF repeat {repeat + 1}/5: scan_range={current_scan}")

                # 1. CW current_scan 이동
                self.debug_print(f"AF: moving CW {current_scan} steps")
                for _ in range(current_scan):
                    self.fm_serial.write(bytes(cmd_cw, encoding='ascii'))
                    self.fm_serial.flush()
                    QTest.qWait(settle_delay)

                # 2. CCW 스캔 (current_scan의 2배)하면서 #Dots 읽기, 실시간 그래프 갱신
                ccw_scan_steps = current_scan * 2
                positions = []
                dot_counts = []
                self.debug_print(f"AF: scanning CCW {ccw_scan_steps} steps")
                for i in range(ccw_scan_steps + 1):
                    pos = current_scan - i  # current_scan -> -current_scan
                    for _ in range(3):
                        QApplication.processEvents()
                        QTest.qWait(50)
                    try:
                        cnt = int(self.label_no_dots.text() or "0")
                    except ValueError:
                        cnt = 0
                    positions.append(pos)
                    dot_counts.append(cnt)
                    self.debug_print(f"AF pos {pos}: #Dots={cnt}")
                    if ax is not None:
                        ax.clear()
                        ax.plot(positions, dot_counts, 'b-', linewidth=1.5)
                        ax.set_xlabel('Step')
                        ax.set_ylabel('#Dots')
                        ax.set_title(f'AF Peak (repeat {repeat + 1}/5, pos {pos})')
                        ax.figure.tight_layout()
                        ax.figure.canvas.draw()
                        QApplication.processEvents()
                    if i < ccw_scan_steps:
                        self.fm_serial.write(bytes(cmd_ccw, encoding='ascii'))
                        self.fm_serial.flush()
                        QTest.qWait(settle_delay)

                # 3. Peak 그래프 표시 (가우시안 피팅)
                peak_pos = self._gaussian_fit_peak(positions, dot_counts)
                if ax is not None:
                    ax.clear()
                    ax.plot(positions, dot_counts, 'b-', linewidth=1.5, label='#Dots')
                    try:
                        def gaussian(x, a, mu, sigma, c):
                            return a * np.exp(-(x - mu) ** 2 / (2 * sigma ** 2)) + c
                        pos_arr = np.array(positions, dtype=float)
                        cnt_arr = np.array(dot_counts, dtype=float)
                        amp = np.max(cnt_arr) - np.min(cnt_arr)
                        mu0 = pos_arr[np.argmax(cnt_arr)]
                        sigma0 = (np.max(pos_arr) - np.min(pos_arr)) / 4 or 1.0
                        popt, _ = curve_fit(gaussian, pos_arr, cnt_arr, p0=[amp, mu0, sigma0, np.min(cnt_arr)],
                                            bounds=([0, pos_arr.min(), 0.1, -1e6], [1e6, pos_arr.max(), 1e6, 1e6]),
                                            maxfev=5000)
                        x_fit = np.linspace(min(positions), max(positions), 200)
                        ax.plot(x_fit, gaussian(x_fit, *popt), 'g-', linewidth=1, alpha=0.7, label='Gaussian fit')
                    except (RuntimeError, ValueError):
                        pass
                    ax.set_xlabel('Step')
                    ax.set_ylabel('#Dots')
                    ax.set_title(f'AF Peak (repeat {repeat + 1}/5)')
                    ax.axvline(x=peak_pos, color='r', linestyle='--', alpha=0.7, label=f'Center @ {peak_pos:.1f}')
                    ax.legend(loc='upper right', fontsize=7)
                    ax.figure.tight_layout()
                    ax.figure.canvas.draw()

                # 4. Peak 위치로 CW 이동
                steps_to_peak = int(round(peak_pos + current_scan))
                self.debug_print(f"AF repeat {repeat + 1}/5: center {peak_pos:.1f}, moving CW {steps_to_peak} steps")
                for _ in range(steps_to_peak):
                    self.fm_serial.write(bytes(cmd_cw, encoding='ascii'))
                    self.fm_serial.flush()
                    QTest.qWait(settle_delay)

            self.debug_print(f"AF complete: 5 repeats done")
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Auto focus failed.\n\n{e}")
            self.debug_print(f"Error in auto_focus: {e}")
        finally:
            self.find_dot = False
            # AF 종료 시 항상 disable(d) — 시작 시 이미 켜져 있어도 끝에서 한 번 끔
            if self.fm_serial and self.fm_serial.is_open and str(self.btn_fm.text()) == 'Disconnect':
                try:
                    self.fm_serial.write(bytes('d\n', encoding='ascii'))
                    self.fm_serial.flush()
                    self.btn_fm_enable.blockSignals(True)
                    self.btn_fm_enable.setChecked(False)
                    self.btn_fm_enable.setText('Disabled')
                    self.btn_fm_enable.blockSignals(False)
                    self.debug_print("Auto focus: stepper disabled after AF")
                except Exception as e:
                    self.debug_print(f"Auto focus: failed to disable stepper: {e}")
            self.btn_af.setEnabled(True)

    def onSnippingCompleted(self, frame):
        self.setWindowState(Qt.WindowState.WindowActive | Qt.WindowState.WindowMaximized)
        if frame is None:
            return
        image = QImage(frame, frame.shape[1], frame.shape[0], frame.strides[0], QImage.Format.Format_RGB888)
        if self.snipping_laser:
            image.save('laser_dot.png')
            pixmap = QPixmap.fromImage(image)
            # self._pixmap = self.resizeImage(pixmap)
            self.label_img_laser.setPixmap(pixmap)
            self.snipping_laser = False
        elif self.snipping_dot:
            image.save('dot_img.png')
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

    def mff101_toggle(self):
        """Toggle flip mirror position using CTRL+J shortcut"""
        self.debug_print("CTRL+J pressed - Toggling flip mirror...")
        success = self.mff101.toggle()
        if success:
            position_name = self.mff101.get_current_position_name()
            self.debug_print(f"Flip mirror toggled successfully. Current position: {position_name}")
        else:
            self.debug_print("Failed to toggle flip mirror")
        return success

    def mff101_2_toggle(self):
        """Toggle second flip mirror position using CTRL+U shortcut"""
        self.debug_print("CTRL+U pressed - Toggling second flip mirror...")
        success = self.mff101_2.toggle()
        if success:
            position_name = self.mff101_2.get_current_position_name()
            self.debug_print(f"Second flip mirror toggled successfully. Current position: {position_name}")
        else:
            self.debug_print("Failed to toggle second flip mirror")
        return success

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
        if hasattr(self, 'lbl_laplacian'):
            self.lbl_laplacian.setText("Sharpness: --")
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
            # Sharpen 설정: (threshold << 24) | (radius << 16) | strength
            # threshold=0, radius=2, strength=500
            # sharpen_value = (0 << 24) | (2 << 16) | 500
            # self.hcam.put_Option(nncam.NNCAM_OPTION_SHARPENING, sharpen_value)
            self.hcam.put_ExpoTime(90000)
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
        ptr.setsize(qimage.sizeInBytes())  # Use sizeInBytes() for correct buffer size
        arr = np.array(ptr).reshape(height, width, 3)  # Convert to array matching RGB888 format
        return arr

    def handleImageEvent(self):
        try:
            self.hcam.PullImageV3(self.pData, 0, 24, 0, None)
        except nncam.HRESULTException:
            pass
        else:
            image = QImage(self.pData, self.imgWidth, self.imgHeight, QImage.Format.Format_RGB888)
            newimage = image.scaled(self.lbl_video.width(), self.lbl_video.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            newimage_np = self.qimage_to_np_array(newimage)
            newimage_np = cv2.cvtColor(newimage_np, cv2.COLOR_RGBA2BGR)

            if self.find_laser:
                # Laser detection using template matching
                laser_point = self.find_laser_template(newimage_np, self.val_thre_laser)
                self.debug_print(laser_point)
                self.debug_print(len(laser_point))
                if len(laser_point) == 1:
                    self.lp_x.setValue(int(laser_point[0][0]))
                    self.lp_y.setValue(int(laser_point[0][1]))
                self.find_laser = False

            if self.find_dot:
                # Frame skipping optimization: only process every Nth frame
                self.dot_detection_frame_counter += 1
                if self.dot_detection_frame_counter >= self.dot_detection_frame_skip:
                    self.dot_detection_frame_counter = 0
                    
                    # Use template matching method only
                    try:
                        if self.dot_detection_method == "yolo":
                            # YOLO detection method
                            self.points = self.find_dots_yolo(newimage_np, self.val_thre_dot)
                        else:  # template
                            self.points = self.find_dots_template_improved(newimage_np, self.val_thre_dot)
                    except Exception as e:
                        self.debug_print(f"Error in dot detection: {e}")
                        # If an error occurs, use template method as fallback
                        self.points = self.find_dots_template_improved(newimage_np, self.val_thre_dot)

                    # Apply limit to the number of detected points
                    self.points = self.limit_detection_count(self.points)

                    self.label_no_dots.setText('{}'.format(len(self.points)))
                    self.coordinate_model = CoordinateListModel(self.points)
                    self.listView.setModel(self.coordinate_model)

                # Display detected dots with magenta cross markers (always show, even when not detecting)
                if len(self.points) > 0:
                    # Create overlay
                    overlay = newimage_np.copy()
                    for (x, y) in self.points:
                        # Draw magenta cross marker (same size as green, thickness 1)
                        cv2.line(overlay, (x - 10, y), (x + 10, y), (255, 0, 255), 1)  # horizontal magenta line
                        cv2.line(overlay, (x, y - 10), (x, y + 10), (255, 0, 255), 1)  # vertical magenta line
                    # Apply alpha value 0.5
                    alpha = 0.5
                    newimage_np = cv2.addWeighted(overlay, alpha, newimage_np, 1 - alpha, 0)
            else:
                if len(self.points) > 0:
                    # Create overlay
                    overlay = newimage_np.copy()
                    for (x, y) in self.points:
                        # Draw green cross marker (shows previous detection results)
                        cv2.line(overlay, (x - 10, y), (x + 10, y), (0, 255, 0), 1)  # horizontal cross line
                        cv2.line(overlay, (x, y - 10), (x, y + 10), (0, 255, 0), 1)  # vertical cross line
                    # Apply alpha value 0.5
                    alpha = 0.5
                    newimage_np = cv2.addWeighted(overlay, alpha, newimage_np, 1 - alpha, 0)
                else:
                    # print('Not find points.')
                    pass

            if self.vision_laser_pos:
                x = self.lp_x.value()
                y = self.lp_y.value()
                radius = 10
                color = (255, 255, 255)  # White color
                thickness = 1  # Use -1 to fill the circle
                # Create overlay
                overlay = newimage_np.copy()
                # Draw a circle and cross lines at the specified position
                cv2.circle(overlay, (x, y), radius, color, thickness)
                cv2.line(overlay, (x - 50, y), (x + 50, y), color, thickness)
                cv2.line(overlay, (x, y - 50), (x, y + 50), color, thickness)
                # Apply alpha blending with 0.5 transparency
                alpha = 0.5
                newimage_np = cv2.addWeighted(overlay, alpha, newimage_np, 1 - alpha, 0)
            # Sharpness 실시간 표시 (5프레임마다, focus peaking 방식)
            self._laplacian_frame_counter = getattr(self, '_laplacian_frame_counter', 0) + 1
            if self._laplacian_frame_counter % 5 == 0 and hasattr(self, 'lbl_laplacian'):
                try:
                    arr = np.frombuffer(bytes(self.pData), dtype=np.uint8).copy().reshape(
                        self.imgHeight, self.imgWidth, 3)
                    img_bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                    val = self._get_focus_metric(img_bgr)
                    self.lbl_laplacian.setText(f"Sharpness: {val:.1f}")
                except Exception:
                    pass

            # Convert BGR (OpenCV) to RGB (QImage)
            newimage_np = cv2.cvtColor(newimage_np, cv2.COLOR_BGR2RGB)

            # Convert NumPy array back to QImage
            newimage = self.np_array_to_qimage(newimage_np)

            # Image save flag is activated, save the image
            if self.save_image_flag and self.current_image_path:
                try:
                    newimage.save(self.current_image_path)
                    self.debug_print(f"Camera image saved: {self.current_image_path}")
                    self.save_image_flag = False
                    self.current_image_path = ""
                except Exception as e:
                    self.debug_print(f"Failed to save camera image: {e}")

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

    def get_step_size(self):
        """Return step size according to the radio button"""
        if self.rb_step_l.isChecked():
            return 'l'
        elif self.rb_step_m.isChecked():
            return 'm'
        elif self.rb_step_s.isChecked():
            return 's'
        else:
            return 'm'  # Default value

    def get_driving_speed(self, step_size):
        """Get driving speed based on step size (L/M/S) from lineEdit values"""
        try:
            if step_size == 'l':
                # L: lineEdit_2 값 사용
                speed = self.lineEdit_2.text().strip()
                return speed if speed else '1000'  # Default if empty
            elif step_size == 'm':
                # M: lineEdit_3 값 사용
                speed = self.lineEdit_3.text().strip()
                return speed if speed else '1000'  # Default if empty
            elif step_size == 's':
                # S: lineEdit_8 값 사용
                speed = self.lineEdit_8.text().strip()
                return speed if speed else '300'   # Default if empty
            else:
                return '1000'  # Default speed
        except Exception as e:
            self.debug_print(f"Error reading speed from lineEdit: {e}")
            return '1000'  # Fallback speed

    def move_continue(self, dir_str, step_size):
        """Move using DS102 Continue mode (mode 0) with keyboard shortcuts"""
        if str(self.btn_gpib_conn.text()) == 'Disconnect':
            # Get driving speed based on step size
            driving_speed = self.get_driving_speed(step_size)
            
            # Determine axis and direction based on direction string and radio button settings
            if dir_str == 'u':  # Up
                if self.radioButton.isChecked():  # Normal direction
                    if self.radioButton_5.isChecked():  # X axis
                        axis_num = '1'
                        direction = 'CW'
                    else:  # Y axis
                        axis_num = '2' 
                        direction = 'CCW'
                else:  # Reverse direction
                    if self.radioButton_5.isChecked():  # X axis
                        axis_num = '1'
                        direction = 'CCW'
                    else:  # Y axis
                        axis_num = '2'
                        direction = 'CW'
            elif dir_str == 'd':  # Down
                if self.radioButton_2.isChecked():  # Normal direction
                    if self.radioButton_5.isChecked():  # X axis
                        axis_num = '1'
                        direction = 'CW'
                    else:  # Y axis
                        axis_num = '2'
                        direction = 'CCW'
                else:  # Reverse direction
                    if self.radioButton_5.isChecked():  # X axis
                        axis_num = '1'
                        direction = 'CCW'
                    else:  # Y axis
                        axis_num = '2'
                        direction = 'CW'
            elif dir_str == 'l':  # Left
                if self.radioButton_3.isChecked():  # Normal direction
                    if self.radioButton_5.isChecked():  # Y axis (left/right controls Y)
                        axis_num = '2'
                        direction = 'CW'
                    else:  # X axis
                        axis_num = '1'
                        direction = 'CW'
                else:  # Reverse direction
                    if self.radioButton_5.isChecked():  # Y axis
                        axis_num = '2'
                        direction = 'CCW'
                    else:  # X axis
                        axis_num = '1'
                        direction = 'CCW'
            elif dir_str == 'r':  # Right
                if self.radioButton_4.isChecked():  # Normal direction
                    if self.radioButton_5.isChecked():  # Y axis
                        axis_num = '2'
                        direction = 'CW'
                    else:  # X axis
                        axis_num = '1'
                        direction = 'CW'
                else:  # Reverse direction
                    if self.radioButton_5.isChecked():  # Y axis
                        axis_num = '2'
                        direction = 'CCW'
                    else:  # X axis
                        axis_num = '1'
                        direction = 'CCW'
            
            # DS102 Continue mode command format (exactly like ds102.py)
            # AXI{axis}:L0 {start_speed}:R0 {accel_time}:S0 {s_curve}:F0 {driving_speed}:GO {direction}J
            ds102_cmd = f'AXI{axis_num}:L0 100:R0 100:S0 100:F0 {driving_speed}:GO {direction}J\r'
            
            self.debug_print(f"Continue mode command: {ds102_cmd.strip()}")
            
            # Send DS102 command
            self.ds102_send_command(ds102_cmd)
            
            # Start real-time position update (like ds102.py)
            self.start_position_update()
        else:
            QMessageBox.warning(self, "Warning", "GPIB disconnect.")

    def move_continue_start(self, dir_str):
        """Start continuous movement in specified direction"""
        if str(self.btn_gpib_conn.text()) == 'Disconnect':
            self.btn_movement_active[dir_str] = True
            step_size = self.get_step_size()
            self.move_continue(dir_str, step_size)
    
    def move_continue_stop(self, dir_str):
        """Stop continuous movement for specified direction"""
        if self.btn_movement_active.get(dir_str, False):
            self.btn_movement_active[dir_str] = False
            self.stop_continue()
    
    def stop_continue(self):
        """Stop DS102 Continue mode movement (exactly like ds102.py)"""
        if str(self.btn_gpib_conn.text()) == 'Disconnect':
            # Send stop command (same as ds102.py)
            stop_cmd = 'STOP 0\r'
            self.ds102_send_command(stop_cmd)
            self.debug_print("Continue mode stopped")
            
            # Stop position update timer
            self.stop_position_update()
            
            # Re-enable buttons after stopping
            self.arrow_btn_enable(True)

    def start_position_update(self):
        """Start real-time position update (like ds102.py)"""
        if str(self.btn_gpib_conn.text()) == 'Disconnect' and not self.position_update_active:
            self.position_update_active = True
            if not self.position_timer.isActive():
                self.position_timer.start(250)  # Update every 250ms (reduced frequency for smoother UI)

    def stop_position_update(self):
        """Stop real-time position update"""
        self.position_update_active = False
        if self.position_timer and self.position_timer.isActive():
            self.position_timer.stop()

    def update_position_status(self):
        """Update position status (like ds102.py update_status)"""
        if not self.position_update_active or str(self.btn_gpib_conn.text()) != 'Disconnect':
            return
            
        try:
            # Optimized: Read positions only (removed redundant status checks)
            # Read X axis (axis 1) position
            x_pos_data = self.ds102_send_command('AXI1:POS?\r', wait_response=True)
            
            # Update UI labels (X=label_21, Y=label_19)
            if x_pos_data:
                self.label_21.setText('{}'.format(x_pos_data))  # X axis
            
            # Read Y axis (axis 2) position  
            y_pos_data = self.ds102_send_command('AXI2:POS?\r', wait_response=True)
            
            if y_pos_data:
                self.label_19.setText('{}'.format(y_pos_data))  # Y axis
            
            # Note: Timer will be stopped by ds102_wait_for_completion when motor stops
            # This reduces serial communication from 4 calls to 2 calls per update
                
        except Exception as e:
            self.debug_print(f"Error updating position: {e}")
            self.position_update_active = False
            if self.position_timer.isActive():
                self.position_timer.stop()

    def check_axis_moving(self, axis_num):
        """Check if specific axis is moving (like ds102.py status check)"""
        try:
            # Request status binary 1 for the axis
            status_cmd = f'AXI{axis_num}:SB1?\r'
            status_data = self.ds102_send_command(status_cmd, wait_response=True)
            
            if status_data:
                status_val = int(status_data)
                # Check if motor is driving (bit 6 = 0x40)
                return bool(status_val & 0x40)
            return False
        except:
            return False

    def move_step(self, dir_str, step_str):
        """Move step using DS102 Step mode (mode 1)"""
        if str(self.btn_gpib_conn.text()) == 'Disconnect':
            self.arrow_btn_enable(False)
            
            # Get pulse count based on step size
            if step_str == 'm':
                if dir_str == 'u' or dir_str == 'd':
                    p_val = self.lineEdit_3.text().strip()
                else:
                    p_val = self.lineEdit_7.text().strip()
            elif step_str == 's':
                if dir_str == 'u' or dir_str == 'd':
                    p_val = self.lineEdit_8.text().strip()
                else:
                    p_val = self.lineEdit_4.text().strip()
            elif step_str == 'l':
                if dir_str == 'u' or dir_str == 'd':
                    p_val = self.lineEdit_2.text().strip()
                else:
                    p_val = self.lineEdit_6.text().strip()
            else:
                p_val = str(int(float(step_str)))
            
            # Default to 1000 if empty
            pulse_count = p_val if p_val else '1000'
            
            # Determine axis and direction based on direction string and radio button settings
            if dir_str == 'u':  # Up
                if self.radioButton.isChecked():  # Normal direction
                    if self.radioButton_5.isChecked():  # X axis
                        axis_num = '1'
                        direction = 'CW'
                    else:  # Y axis
                        axis_num = '2' 
                        direction = 'CCW'
                else:  # Reverse direction
                    if self.radioButton_5.isChecked():  # X axis
                        axis_num = '1'
                        direction = 'CCW'
                    else:  # Y axis
                        axis_num = '2'
                        direction = 'CW'
            elif dir_str == 'd':  # Down
                if self.radioButton_2.isChecked():  # Normal direction
                    if self.radioButton_5.isChecked():  # X axis
                        axis_num = '1'
                        direction = 'CW'
                    else:  # Y axis
                        axis_num = '2'
                        direction = 'CCW'
                else:  # Reverse direction
                    if self.radioButton_5.isChecked():  # X axis
                        axis_num = '1'
                        direction = 'CCW'
                    else:  # Y axis
                        axis_num = '2'
                        direction = 'CW'
            elif dir_str == 'l':  # Left
                if self.radioButton_3.isChecked():  # Normal direction
                    if self.radioButton_5.isChecked():  # Y axis (left/right controls Y)
                        axis_num = '2'
                        direction = 'CW'
                    else:  # X axis
                        axis_num = '1'
                        direction = 'CW'
                else:  # Reverse direction
                    if self.radioButton_5.isChecked():  # Y axis
                        axis_num = '2'
                        direction = 'CCW'
                    else:  # X axis
                        axis_num = '1'
                        direction = 'CCW'
            elif dir_str == 'r':  # Right
                if self.radioButton_4.isChecked():  # Normal direction
                    if self.radioButton_5.isChecked():  # Y axis
                        axis_num = '2'
                        direction = 'CW'
                    else:  # X axis
                        axis_num = '1'
                        direction = 'CW'
                else:  # Reverse direction
                    if self.radioButton_5.isChecked():  # Y axis
                        axis_num = '2'
                        direction = 'CCW'
                    else:  # X axis
                        axis_num = '1'
                        direction = 'CCW'
            
            # DS102 Step mode command format (like ds102.py mode 1)
            # AXI{axis}:L0 {start_speed}:R0 {accel_time}:S0 {s_curve}:F0 {driving_speed}:PULS {pulse_count}:GO {direction}
            ds102_cmd = f'AXI{axis_num}:L0 100:R0 100:S0 100:F0 1000:PULS {pulse_count}:GO {direction}\r'
            
            self.debug_print(f"Step mode command: {ds102_cmd.strip()}")
            
            # Send DS102 command
            self.ds102_send_command(ds102_cmd)
            
            # Start real-time position update and wait for completion
            self.start_position_update()
            self.ds102_wait_for_completion(axis_num)
            self.arrow_btn_enable(True)
        else:
            QMessageBox.warning(self, "Warning", "GPIB disconnect.")


    def ds102_wait_for_completion(self, axis_num):
        """Wait for DS102 motor movement to complete"""
        max_wait_time = 30  # Maximum wait time in seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            # Request status binary 1 for the axis
            status_cmd = f'AXI{axis_num}:SB1?\r'
            status_data = self.ds102_send_command(status_cmd, wait_response=True)
            
            try:
                if status_data:
                    status_val = int(status_data)
                    
                    # Check if motor is still driving (bit 6 = 0x40)
                    if not (status_val & 0x40):  # Motor stopped
                        # Stop position update when movement completes
                        self.stop_position_update()
                        break
                    
            except (ValueError, UnicodeDecodeError):
                pass  # Continue waiting if we can't parse the status
            
            # Longer wait interval for smoother UI (reduced polling frequency)
            QApplication.processEvents()  # Process UI events to prevent freezing
            QTest.qWait(150)  # Wait 150ms while allowing UI updates (was 100ms)

    def init_position(self):
        """Initialize position to 0 for both axes (DS102 format)"""
        # Set X axis (axis 1) position to 0
        self.ds102_send_command('AXI1:POS 0\r')
        # Set Y axis (axis 2) position to 0  
        self.ds102_send_command('AXI2:POS 0\r')

    def status_motor(self, previous_data, xyor):
        """DS102 status monitoring - deprecated, use ds102_wait_for_completion instead"""
        # This function is kept for compatibility but DS102 uses different status checking
        pass

    def motor_read_s(self):
        """Read current position from DS102 controller"""
        try:
            # Read X axis (axis 1) position
            s_a1_data = self.ds102_send_command('AXI1:POS?\r', wait_response=True)
            
            # Read Y axis (axis 2) position  
            s_a2_data = self.ds102_send_command('AXI2:POS?\r', wait_response=True)
            
            # Update UI labels
            if s_a2_data:
                self.label_19.setText('{}'.format(s_a2_data))
            if s_a1_data:
                self.label_21.setText('{}'.format(s_a1_data))
            
            if s_a1_data and s_a2_data:
                return int(float(s_a1_data)), int(float(s_a2_data))
            return 0, 0
        except (ValueError, UnicodeDecodeError):
            self.debug_print("Error reading motor positions")
            return 0, 0

    def goto_origin(self):
        """Move to origin position (0, 0) using current position"""
        if str(self.btn_gpib_conn.text()) != 'Disconnect':
            QMessageBox.warning(self, "Warning", "GPIB disconnect.")
            return
            
        self.btn_goto_origin.setEnabled(False)
        self.debug_print("Starting move to origin (0, 0)")
        
        try:
            # Read current positions
            self.motor_read_s()
            current_x = int(float(self.label_21.text()))  # X axis position
            current_y = int(float(self.label_19.text()))  # Y axis position
            
            self.debug_print(f"Current position: X={current_x}, Y={current_y}")
            
            # Calculate steps needed to reach (0, 0)
            steps_x = -current_x  # Steps needed for X axis
            steps_y = -current_y  # Steps needed for Y axis
            
            self.debug_print(f"Steps needed: X={steps_x}, Y={steps_y}")
            
            # Start real-time position update
            self.start_position_update()
            
            # Move X axis to 0 if needed
            if steps_x != 0:
                self.debug_print(f"Moving X axis by {steps_x} steps")
                axis_num = '1'
                direction = 'CW' if steps_x > 0 else 'CCW'
                pulse_count = abs(steps_x)
                
                # DS102 step command for X axis
                x_cmd = f'AXI{axis_num}:L0 100:R0 100:S0 100:F0 1000:PULS {pulse_count}:GO {direction}\r'
                self.ds102_send_command(x_cmd)
                
                # Wait for X axis movement to complete
                self.ds102_wait_for_completion(axis_num)
            
            # Move Y axis to 0 if needed
            if steps_y != 0:
                self.debug_print(f"Moving Y axis by {steps_y} steps")
                axis_num = '2'
                direction = 'CW' if steps_y > 0 else 'CCW'
                pulse_count = abs(steps_y)
                
                # DS102 step command for Y axis
                y_cmd = f'AXI{axis_num}:L0 100:R0 100:S0 100:F0 1000:PULS {pulse_count}:GO {direction}\r'
                self.ds102_send_command(y_cmd)
                
                # Wait for Y axis movement to complete
                self.ds102_wait_for_completion(axis_num)
            
            # Final position read
            self.motor_read_s()
            final_x = int(float(self.label_21.text()))
            final_y = int(float(self.label_19.text()))
            
            self.debug_print(f"Final position: X={final_x}, Y={final_y}")
            self.debug_print("Move to origin completed")
            
        except Exception as e:
            self.debug_print(f"Error in goto_origin: {e}")
            QMessageBox.warning(self, "Error", f"Move to origin failed: {e}")
        finally:
            self.btn_goto_origin.setEnabled(True)


    def shortcut_key(self):
        # Disconnect any existing clicked signals to prevent conflicts
        try:
            self.btn_up.clicked.disconnect()
            self.btn_down.clicked.disconnect()
            self.btn_left.clicked.disconnect()
            self.btn_right.clicked.disconnect()
        except TypeError:
            pass  # No signals were connected
        
        # Disconnect any old pressed/released connections
        try:
            self.btn_up.pressed.disconnect()
            self.btn_up.released.disconnect()
            self.btn_down.pressed.disconnect()
            self.btn_down.released.disconnect()
            self.btn_left.pressed.disconnect()
            self.btn_left.released.disconnect()
            self.btn_right.pressed.disconnect()
            self.btn_right.released.disconnect()
        except TypeError:
            pass  # No signals were connected
        
        # Disable autoRepeat for arrow buttons to ensure proper press/release behavior
        self.btn_up.setAutoRepeat(False)
        self.btn_down.setAutoRepeat(False)
        self.btn_left.setAutoRepeat(False)
        self.btn_right.setAutoRepeat(False)
        
        # Track button states to ensure stop is called
        self.btn_movement_active = {'u': False, 'd': False, 'l': False, 'r': False}
        
        # Connect buttons to press/release events for Continue mode
        self.btn_up.pressed.connect(lambda: self.move_continue_start('u'))
        self.btn_up.released.connect(lambda: self.move_continue_stop('u'))
        
        self.btn_down.pressed.connect(lambda: self.move_continue_start('d'))
        self.btn_down.released.connect(lambda: self.move_continue_stop('d'))
        
        self.btn_left.pressed.connect(lambda: self.move_continue_start('l'))
        self.btn_left.released.connect(lambda: self.move_continue_stop('l'))
        
        self.btn_right.pressed.connect(lambda: self.move_continue_start('r'))
        self.btn_right.released.connect(lambda: self.move_continue_stop('r'))

        # Remove shortcuts from buttons (we'll handle them in keyPressEvent/keyReleaseEvent)
        # self.btn_up.setShortcut(QKeySequence(Qt.Key.Key_F5))
        # self.btn_down.setShortcut(QKeySequence(Qt.Key.Key_F6))
        # self.btn_left.setShortcut(QKeySequence(Qt.Key.Key_F7))
        # self.btn_right.setShortcut(QKeySequence(Qt.Key.Key_F8))

        # Step size radio button shortcuts (Numpad only)
        shortcut_step_l = QShortcut(QKeySequence("Num+1"), self)
        shortcut_step_l.activated.connect(lambda: self.rb_step_l.setChecked(True))
        shortcut_step_m = QShortcut(QKeySequence("Num+2"), self)
        shortcut_step_m.activated.connect(lambda: self.rb_step_m.setChecked(True))
        shortcut_step_s = QShortcut(QKeySequence("Num+3"), self)
        shortcut_step_s.activated.connect(lambda: self.rb_step_s.setChecked(True))

        # Flip mirror toggle shortcut
        shortcut_flip_toggle = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_J), self)
        shortcut_flip_toggle.activated.connect(self.mff101_toggle)
        
        # Second flip mirror toggle shortcut
        shortcut_flip_toggle_2 = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_U), self)
        shortcut_flip_toggle_2.activated.connect(self.mff101_2_toggle)

        # Spectrum acquisition shortcut (Ctrl+N)
        shortcut_spectrum_acq = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_N), self)
        shortcut_spectrum_acq.activated.connect(self.on_btn_acq_clicked)

        # Shutter toggle shortcut - using keyPressEvent instead
        # shortcut_shutter_toggle = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Y), self)
        # shortcut_shutter_toggle.activated.connect(self.shutter_toggle)

    def keyPressEvent(self, event):
        # Handle Ctrl+Y for shutter toggle
        if event.key() == Qt.Key.Key_Y and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            QTest.mouseClick(self.btn_shutter_toggle, Qt.MouseButton.LeftButton)
        # Handle Ctrl+H for LED toggle
        elif event.key() == Qt.Key.Key_H and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            QTest.mouseClick(self.btn_LED_toggle, Qt.MouseButton.LeftButton)
        # Handle Z:\.data\data\a1_1_2.SIF   
        # -F8 keys for Continue mode movement (simulate button press)
        elif event.key() == Qt.Key.Key_F5 and not event.isAutoRepeat():
            self.btn_up.pressed.emit()
        elif event.key() == Qt.Key.Key_F6 and not event.isAutoRepeat():
            self.btn_down.pressed.emit()
        elif event.key() == Qt.Key.Key_F7 and not event.isAutoRepeat():
            self.btn_left.pressed.emit()
        elif event.key() == Qt.Key.Key_F8 and not event.isAutoRepeat():
            self.btn_right.pressed.emit()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        # Handle F5-F8 keys for Continue mode movement (simulate button release)
        if event.key() == Qt.Key.Key_F5 and not event.isAutoRepeat():
            self.btn_up.released.emit()
        elif event.key() == Qt.Key.Key_F6 and not event.isAutoRepeat():
            self.btn_down.released.emit()
        elif event.key() == Qt.Key.Key_F7 and not event.isAutoRepeat():
            self.btn_left.released.emit()
        elif event.key() == Qt.Key.Key_F8 and not event.isAutoRepeat():
            self.btn_right.released.emit()
        else:
            super().keyReleaseEvent(event)

    def closeEvent(self, event):
        # Setup save
        self.save_config()
        
        # Exit confirmation message
        re = QMessageBox.question(self, "Question", "Are you sure you want to quit?",
                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if re == QMessageBox.StandardButton.Yes:
            # Stop position update timer
            self.stop_position_update()
            self.closeCamera()
            try:
                if self.serial_connection.is_open:
                    self.serial_connection.close()
            except AttributeError as e:
                self.debug_print(f'Msg err : {e}')
            try:
                if self.serial_connection_2.is_open:
                    self.serial_connection_2.close()
            except AttributeError as e:
                self.debug_print(f'Msg err : {e}')
            # Close flip mirror connections
            try:
                if self.mff101:
                    self.mff101.close()
                    self.debug_print("Flip mirror connection closed")
            except Exception as e:
                self.debug_print(f'Flip mirror close error: {e}')
            try:
                if self.mff101_2:
                    self.mff101_2.close()
                    self.debug_print("Second flip mirror connection closed")
            except Exception as e:
                self.debug_print(f'Second flip mirror close error: {e}')
            # Close FW102C filter wheel connection
            try:
                if self.fw102c_connected and self.fw102c:
                    self.fw102c.disconnect()
                    self.debug_print("FW102C filter wheel connection closed")
            except Exception as e:
                self.debug_print(f'FW102C close error: {e}')
            if self._sdk2_widget is not None:
                self._sdk2_widget.close()
                self._sdk2_widget = None
            self.snippingWidget.close()
            event.accept()
        else:
            event.ignore()

    def startProgress(self):
        self.startTime = QDateTime.currentDateTime()
        self.timer2.start(1000)  # Update every 1 second

    def updateProgress(self):
        value = self.progressBar.value()
        self.label_stime.setText(self.startTime.toString('yyyy-MM-dd HH:mm:ss'))
        if value < 100:
            value += 1
            # self.progressBar.setValue(value)

            current_time = QDateTime.currentDateTime().toString('yyyy-MM-dd HH:mm:ss')

            # Calculate remaining time
            elapsed_seconds = self.startTime.secsTo(QDateTime.currentDateTime())
            remaining_seconds = (100 - value) * elapsed_seconds // value if value > 0 else 0
            remaining_time = QDateTime.currentDateTime().addSecs(remaining_seconds)
            end_time = self.startTime.addSecs(elapsed_seconds + remaining_seconds)

            # Display remaining time and end time
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
            self._refresh_spectrum_acq_buttons()
            self.debug_print("Server connected")
        else:
            self.client_socket.close()
            QTest.qWait(500)
            self.client_socket = None
            self._refresh_spectrum_acq_buttons()
            self.debug_print("Server disconnected")
            
            self.pushButton_14.setText("Server Connect")

    def recv_data(self):
        while True:
            data = self.client_socket.recv()
            self.debug_print(data)
            if data == "done":
                self.debug_print("msg : done!")
                break

    def wait_for_sif_file_ready(self, file_path, timeout_sec=15.0, stable_interval=0.5):
        """
        SIF 파일이 생성되고 쓰기가 완료될 때까지 대기 (파일 크기 안정화 확인)
        네트워크 드라이브(Z:) 저장 지연에 대응
        """
        if not file_path or not os.path.isabs(file_path):
            time.sleep(2.5)  # 경로 없으면 기본 대기
            return True
        start = time.time()
        last_size = -1
        stable_since = None
        while time.time() - start < timeout_sec:
            QApplication.processEvents()  # UI 응답성 유지
            try:
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path)
                    if size == last_size and size > 0:
                        if stable_since is None:
                            stable_since = time.time()
                        elif time.time() - stable_since >= stable_interval:
                            self.debug_print(f"SIF file ready: {file_path} ({size} bytes)")
                            return True
                    else:
                        stable_since = None
                    last_size = size
            except OSError:
                pass
            time.sleep(0.2)
        self.debug_print(f"SIF file wait timeout ({timeout_sec}s), proceeding anyway")
        return True  # 타임아웃 후에도 진행 (기존 동작 유지)

    def _snap_spectrum_sdk2(self, custom_filename=None, max_retries=3):
        """Andor SDK2 FVB 단발 측정 → 메인 plot_spe; 저장은 SDK2 Save Spectrum과 동일(플롯·X-cal·축 라벨 반영)."""
        self.debug_print(
            f"=== _snap_spectrum_sdk2 max_retries={max_retries}, custom_filename={custom_filename} ==="
        )
        if self._sdk2_widget is None:
            self.open_sdk2_window()
        w = self._sdk2_widget
        if w is None:
            self.debug_print("SDK2 window could not be created")
            return False
        if w.sdk is None:
            self.debug_print("SDK2: connect spectrometer in SDK2 window first (SDK2 Connect)")
            return False
        for attempt in range(max_retries):
            try:
                QApplication.processEvents()
                # Single shot과 동일: 측정 직전 dsb_expoT(초)를 캐시에 반영 (노출 불일치 방지)
                exp_sec = w.apply_exposure_from_ui()
                self.debug_print(f"SDK2 mapping FVB: exposure = {exp_sec} s")
                xy = w.acquire_fvb_xy_for_mapping()
                if xy is None:
                    self.debug_print(f"SDK2 FVB acquisition failed (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    continue
                x, y = xy
                self.plot_spe(x, y)
                if custom_filename:
                    fp = self.label_fp.text()
                    if not fp or fp == "None":
                        self.debug_print(
                            "SDK2 Save Spectrum: 메인 label_fp(저장 경로)가 없습니다."
                        )
                        if hasattr(w, "_append_log"):
                            w._append_log("Save Spectrum: 메인에서 폴더(label_fp)를 지정하세요.")
                        if attempt < max_retries - 1:
                            time.sleep(1)
                        continue
                    w.ui.lineEdit_dirpath.setText(fp)
                    w.ui.lineEdit_groupname.setText(self.lineEdit_fn.text().strip() or "data")
                    fn_csv = (
                        custom_filename
                        if custom_filename.lower().endswith(".csv")
                        else f"{custom_filename}.csv"
                    )
                    w.ui.lineEdit_fileName.setText(fn_csv)
                    QApplication.processEvents()
                    # btn_save_Spectrum 슬롯과 동일: matplotlib 플롯에서 읽어 CSV (xcal·축 라벨 포함)
                    if not w._on_save_spectrum():
                        self.debug_print(
                            f"SDK2 Save Spectrum failed (attempt {attempt + 1})"
                        )
                        if attempt < max_retries - 1:
                            time.sleep(1)
                        continue
                    self.debug_print(
                        f"SDK2 spectrum saved via Save Spectrum: "
                        f"{fp} / {w.ui.lineEdit_groupname.text().strip()} / {fn_csv}"
                    )
                return True
            except Exception as e:
                self.debug_print(f"_snap_spectrum_sdk2 attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        return False

    def snap_spectrum(self, max_retries=3, custom_filename=None):
        self.debug_print(f"=== snap_spectrum called with max_retries={max_retries}, custom_filename={custom_filename} ===")
        
        if self.rbtn_sdk2.isChecked():
            return self._snap_spectrum_sdk2(custom_filename, max_retries)
        
        if self.radioButton_7.isChecked():
            SOLIS = Solis_win32()
            
            self.debug_print(f"Starting spectrum acquisition loop with max_retries={max_retries}")
            for attempt in range(max_retries):
                try:
                    # Find window containing "Andor SOLIS"
                    andor_windows = SOLIS.find_window_with_string("Andor SOLIS")

                    if andor_windows:
                        hwnd, title = andor_windows[0]
                        self.debug_print(f"Found Andor SOLIS window: {title}")

                        # Save current active window handle
                        original_hwnd = win32gui.GetForegroundWindow()

                        # Create file path to save (folder + file name)
                        if custom_filename:
                            file_name = custom_filename
                        else:
                            fn_text = self.lineEdit_fn.text().strip() or "data"
                            file_name = os.path.basename(fn_text) if os.path.dirname(fn_text) else fn_text
                        
                        folder_path = self.get_save_folder_path()
                        if folder_path:
                            sif_file_path = os.path.join(folder_path, f"{file_name}.SIF")
                            sif_file_path = os.path.normpath(sif_file_path)
                        else:
                            sif_file_path = f"{file_name}.SIF"
                        
                        self.debug_print(f"Saving spectrum to: {sif_file_path}")
                        QApplication.processEvents()  # send_ctrl_s 전 UI 이벤트 처리
                        
                        # Check for backslash path for Solis compatibility
                        if '/' in sif_file_path:
                            sif_file_path = sif_file_path.replace('/', '\\')
                            self.debug_print(f"Converted path to Windows format: {sif_file_path}")
                        
                        # Send Ctrl+S (with dynamic file path)
                        # Control Solis in minimal foreground mode (fast control followed by immediate restoration)
                        # For manual execution, limit retries to 1, for mapping execution, use default (3 retries)
                        if max_retries == 1:  # For manual execution
                            success = SOLIS.send_ctrl_s(hwnd, sif_file_path, max_retries=1)
                        else:  # For mapping execution
                            success = SOLIS.send_ctrl_s(hwnd, sif_file_path)
                        
                        if success:
                            self.debug_print(f"Spectrum acquisition completed successfully on attempt {attempt + 1}")
                            self.debug_print("Waiting for file to be fully written...")
                            self.wait_for_sif_file_ready(sif_file_path)  # 파일 크기 안정화까지 대기 (네트워크 드라이브 대응)
                            
                            # Close MDI child windows
                            self.debug_print("Closing MDI child windows...")
                            mdi_child_windows = SOLIS.find_mdi_child_windows(hwnd)
                            for child_hwnd, child_title in mdi_child_windows:
                                try:
                                    win32gui.PostMessage(child_hwnd, win32con.WM_CLOSE, 0, 0)
                                except Exception as e:
                                    self.debug_print(f"Failed to close child window: {e}")

                            # Restore original active window (타임아웃으로 무한 블로킹 방지)
                            try:
                                QApplication.processEvents()
                                SOLIS.bring_window_to_foreground(original_hwnd, timeout_sec=5.0)
                            except Exception as e:
                                self.debug_print(f"Failed to restore original window: {e}")
                            
                            return True  # Successfully completed
                        else:
                            self.debug_print(f"Spectrum acquisition failed on attempt {attempt + 1}")
                            if attempt < max_retries - 1:
                                self.debug_print("Retrying...")
                                time.sleep(2)  # Wait before retrying
                            else:
                                self.debug_print("Failed to acquire spectrum after all attempts")
                                return False
                    else:
                        self.debug_print("'Andor SOLIS' window not found")
                        return False
                        
                except Exception as e:
                    self.debug_print(f"Error in snap_spectrum attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        self.debug_print("Retrying...")
                        time.sleep(2)  # Wait before retrying
                    else:
                        self.debug_print("Failed to acquire spectrum after all attempts due to errors")
                        return False
            
            return False

        else:
            # TCP/IP connection for spectrum acquisition
            try:
                self.client_socket.send('snap')
                self.recv_data()
                return True
            except Exception as e:
                self.debug_print(f"Error in TCP/IP spectrum acquisition: {e}")
                return False

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

    def cal_closest_dot(self):
        # Current position of the laser pointer
        laser_x = self.lp_x.value()
        laser_y = self.lp_y.value()
        
        # Display the current position of the laser pointer in label_71 and label_72
        self.label_71.setText(f"{laser_x}")
        self.label_72.setText(f"{laser_y}")
        
        # Handle the case where no dots are detected
        if len(self.points) == 0:
            self.label_73.setText("No dots")
            self.label_74.setText("No dots")
            self.label_75.setText("0")
            self.label_76.setText("0")
            self.label_78.setText("999.99")  # Set a large value
            return None, 999.99
        
        # Initialize the value for finding the closest point
        min_distance = float('inf')
        closest_point = None
        
        # Calculate the distance for all points
        for (x, y) in self.points:
            distance = ((x - laser_x) ** 2 + (y - laser_y) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                closest_point = (x, y)
        
        # Display the position of the closest point in label_73 and label_74
        if closest_point:
            self.label_73.setText(f"{closest_point[0]}")
            self.label_74.setText(f"{closest_point[1]}")
            
            # Display the difference between the two points in label_75 and label_76
            delta_x = closest_point[0] - laser_x
            delta_y = closest_point[1] - laser_y
            self.label_75.setText(f"{delta_x}")
            self.label_76.setText(f"{delta_y}")
        
        # Display the distance between the two points in label_78
        self.label_78.setText(f"{min_distance:.2f}")
        return closest_point, min_distance

    def move_closest_dot(self, closest_point=None):
        # closest_point가 있으면 직전 cal_closest_dot 결과 재사용 (이중 계산·label 불일치 방지)
        if closest_point is None:
            closest_point, _ = self.cal_closest_dot()
        if closest_point is None:
            self.debug_print("No closest point found, cannot move")
            return
        
        # Current position of the laser pointer
        laser_x = self.lp_x.value()
        laser_y = self.lp_y.value()
        
        # Calculate the difference between the closest point and the laser pointer
        target_x, target_y = closest_point
        delta_x = target_x - laser_x
        delta_y = target_y - laser_y
        
        self.debug_print(f"Moving from ({laser_x}, {laser_y}) to ({target_x}, {target_y})")
        self.debug_print(f"Delta: ({delta_x}, {delta_y})")
        
        # Convert pixel unit to motor step unit (e.g. 1 pixel = 10 steps)
        conversion_factor = 0.7  # Conversion ratio (adjust as needed)
        step_x = int(round(delta_x * conversion_factor))  # Round to integer
        step_y = int(round(delta_y * conversion_factor))  # Round to integer
        
        self.debug_print(f"Steps: ({step_x}, {step_y})")
        
        # X direction movement
        if step_x != 0:
            if step_x > 0:  # Moving right
                self.debug_print(f"Moving right by {abs(step_x)} steps")
                self.move_step('r', abs(step_x))
            else:  # Moving left
                self.debug_print(f"Moving left by {abs(step_x)} steps")
                self.move_step('l', abs(step_x))
        
        # Y direction movement
        if step_y != 0:
            if step_y > 0:  # Moving down
                self.debug_print(f"Moving down by {abs(step_y)} steps")
                self.move_step('d', abs(step_y))
            else:  # Moving up
                self.debug_print(f"Moving up by {abs(step_y)} steps")
                self.move_step('u', abs(step_y))



    def find_dots_template_improved(self, image, threshold=0.5):
        """
        Improved template matching method with noise processing
        """
        # Load template image (with caching for performance)
        if self.dot_template_cache is None:
            self.dot_template_cache = cv2.imread('dot_img.png', cv2.IMREAD_GRAYSCALE)
            if self.dot_template_cache is None:
                self.debug_print("Warning: dot_img.png not found")
                return []
        
        template = self.dot_template_cache
        if template is None:
            return []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Histogram equalization
        # equalized = cv2.equalizeHist(gray)
        
        # Template matching
        result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        
        # Find locations above threshold
        locations = np.where(result >= threshold)
        locations = list(zip(*locations[::-1]))
        
        # Rectangle grouping for duplicate removal
        rectangles = []
        template_h, template_w = template.shape[:2]
        for loc in locations:
            rect = [int(loc[0]), int(loc[1]), template_w, template_h]
            rectangles.append(rect)
            rectangles.append(rect)
        
        rectangles, weights = cv2.groupRectangles(rectangles, groupThreshold=1, eps=0.5)
        
        points = []
        for (x, y, w, h) in rectangles:
            center_x = x + int(w/2)
            center_y = y + int(h/2)
            points.append((center_x, center_y))
        
        return points

    def find_dots_yolo(self, image, confidence_threshold=0.5):
        """
        YOLO-based dot detection method
        """
        if self.yolo_model is None:
            self.debug_print("YOLO model not loaded, falling back to template method")
            return self.find_dots_template_improved(image, 0.5)
        
        try:
            # Run YOLO detection
            results = self.yolo_model(image, conf=confidence_threshold, verbose=False)
            
            points = []
            for result in results:
                if result.boxes is not None:
                    boxes = result.boxes.xyxy.cpu().numpy()  # Get bounding boxes
                    for box in boxes:
                        # Calculate center point of bounding box
                        x1, y1, x2, y2 = box
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)
                        points.append((center_x, center_y))
            
            self.debug_print(f"YOLO detected {len(points)} dots")
            return points
            
        except Exception as e:
            self.debug_print(f"YOLO detection error: {e}")
            # Fallback to template method
            return self.find_dots_template_improved(image, 0.5)

    def find_laser_template(self, image, threshold=0.5):
        """
        Laser detection using template matching
        """
        # Load laser template image (with caching for performance)
        if self.laser_template_cache is None:
            self.laser_template_cache = cv2.imread('laser_dot.png', cv2.IMREAD_GRAYSCALE)
            if self.laser_template_cache is None:
                self.debug_print("Warning: laser_dot.png not found")
                return []
        
        template = self.laser_template_cache
        if template is None:
            return []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Template matching
        result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        
        # Find locations above threshold
        locations = np.where(result >= threshold)
        locations = list(zip(*locations[::-1]))
        
        # Rectangle grouping for duplicate removal
        rectangles = []
        template_h, template_w = template.shape[:2]
        for loc in locations:
            rect = [int(loc[0]), int(loc[1]), template_w, template_h]
            rectangles.append(rect)
            rectangles.append(rect)
        
        rectangles, weights = cv2.groupRectangles(rectangles, groupThreshold=1, eps=0.5)
        
        points = []
        for (x, y, w, h) in rectangles:
            center_x = x + int(w/2)
            center_y = y + int(h/2)
            points.append((center_x, center_y))
        
        return points

    def on_dot_detection_method_changed(self, method):
        """Dot detection method changed"""
        self.dot_detection_method = method.lower()
        self.debug_print(f"Dot detection method changed to: {method}")
        
        # If switching to YOLO and model is not loaded, try to reload it
        if method.lower() == "yolo" and self.yolo_model is None:
            self.reload_yolo_model()

    def reload_yolo_model(self):
        """Reload YOLO model"""
        try:
            self.yolo_model = YOLO(self.yolo_model_path)
            self.debug_print("YOLO model reloaded successfully")
        except Exception as e:
            self.debug_print(f"Failed to reload YOLO model: {e}")
            self.yolo_model = None

    def limit_detection_count(self, points):
        """Limit the maximum detection count based on the laser pointer position"""
        if len(points) <= self.max_detection_count:
            return points
        
        # Current position of the laser pointer
        laser_x = self.lp_x.value()
        laser_y = self.lp_y.value()
        
        # Calculate the distance to each point
        distances = []
        for i, (x, y) in enumerate(points):
            distance = ((x - laser_x) ** 2 + (y - laser_y) ** 2) ** 0.5
            distances.append((distance, i))
        
        # Sort by distance (nearest first)
        distances.sort()
        
        # Select the nearest max_detection_count points
        limited_points = []
        for _, index in distances[:self.max_detection_count]:
            limited_points.append(points[index])
        
        self.debug_print(f"Detection limited: {len(points)} -> {len(limited_points)} points")
        return limited_points

    def on_max_detection_count_changed(self, value):
        """Max detection count changed"""
        self.max_detection_count = value
        self.debug_print(f"Max detection count changed to: {value}")

    def show_message_box(self, message):
        """Show message box"""
        QMessageBox.information(self, "Information", message)
    
    def select_folder_path(self):
        """Select folder path"""
        folder_path = QFileDialog.getExistingDirectory(
            self, 
            "Select folder", 
            self.label_fp.text() if self.label_fp.text() != "None" else os.getcwd()
        )
        
        if folder_path:
            self.label_fp.setText(folder_path)
            self.debug_print(f"Selected folder: {folder_path}")
            # Setup automatically saved
            self.save_config()
    
    def open_folder_path(self):
        """Open folder path"""
        folder_path = self.label_fp.text()
        
        if folder_path and folder_path != "None":
            if os.path.exists(folder_path):
                # Open folder in Windows explorer
                os.startfile(folder_path)
                self.debug_print(f"Opened folder: {folder_path}")
            else:
                QMessageBox.warning(self, "Warning", f"Folder does not exist: {folder_path}")
                self.debug_print(f"Folder does not exist: {folder_path}")
        else:
            QMessageBox.information(self, "Information", "Please select a folder first.")
            self.debug_print("No folder selected")
    
    def _setup_auto_save(self):
        """Automatic save system setup"""
        from PyQt6.QtCore import QTimer
        
        # Timer setup for debouncing
        self._auto_save_timer = QTimer()
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.timeout.connect(self.save_config)
        
        # Connect automatic save to UI element changes
        self._connect_auto_save_signals()
    
    def _connect_auto_save_signals(self):
        """Connect automatic save to UI element changes"""
        # Text input fields
        text_fields = [
            self.lineEdit_2, self.lineEdit_3, self.lineEdit_4,
            self.lineEdit_6, self.lineEdit_7, self.lineEdit_8,
            self.lineEdit_fn, self.thre_laser, self.thre_dots,
            self.fm_step, self.fm_step_2, self.fm_step_3, self.no_expanding,
        ]
        
        for field in text_fields:
            field.textChanged.connect(self._schedule_auto_save)
        
        # Spinboxes
        self.spinBox.valueChanged.connect(self._schedule_auto_save)
        self.spinBox_2.valueChanged.connect(self._schedule_auto_save)
        self.lp_x.valueChanged.connect(self._schedule_auto_save)
        self.lp_y.valueChanged.connect(self._schedule_auto_save)
        self.spinBox_afoffset.valueChanged.connect(self._schedule_auto_save)
        self.mapping_expanding_chk.stateChanged.connect(self._schedule_auto_save)
        
        # Maximum detection count spinbox (if exists)
        if hasattr(self, 'max_detection_spinbox'):
            self.max_detection_spinbox.valueChanged.connect(self._schedule_auto_save)
    
    def _schedule_auto_save(self):
        """Schedule automatic save (debouncing applied)"""
        # Save after 1 second (prevent continuous input)
        self._auto_save_timer.stop()
        self._auto_save_timer.start(1000)
    
    def get_config_summary(self):
        """Return the summary information of the current configuration"""
        return {
            "file_name": self.lineEdit_fn.text() or "data",
            "folder_path": self.label_fp.text() if self.label_fp.text() != "None" else "Not selected",
            "max_detection_count": self.max_detection_count,
            "laser_position": f"({self.lp_x.value()}, {self.lp_y.value()})",
            "thresholds": f"Laser: {self.thre_laser.text()}, Dots: {self.thre_dots.text()}"
        }
    
    def export_config(self, file_path):
        """Export the configuration to the specified file"""
        try:
            config = self._get_current_config()
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(config, file, indent=2, ensure_ascii=False)
            self.debug_print(f"Configuration exported to: {file_path}")
            return True
        except Exception as e:
            self.debug_print(f"Error exporting configuration: {e}")
            return False
    
    def import_config(self, file_path):
        """Import the configuration from the specified file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                config = json.load(file)
            
            # Setup apply
            self._apply_config(config)
            
            # Save current configuration
            self.save_config()
            
            self.debug_print(f"Configuration imported from: {file_path}")
            return True
        except Exception as e:
            self.debug_print(f"Error importing configuration: {e}")
            return False
    
    def _get_current_config(self):
        """Return the current configuration as a dictionary"""
        return {
            "motor_settings": {
                "lineEdit_2": self.lineEdit_2.text(),
                "lineEdit_6": self.lineEdit_6.text(),
                "lineEdit_3": self.lineEdit_3.text(),
                "lineEdit_7": self.lineEdit_7.text(),
                "lineEdit_8": self.lineEdit_8.text(),
                "lineEdit_4": self.lineEdit_4.text(),
                "spinBox": self.spinBox.value(),
                "spinBox_2": self.spinBox_2.value(),
                "label_26": self.label_26.text(),
                "label_29": self.label_29.text(),
                "label_31": self.label_31.text(),
                "label_33": self.label_33.text()
            },
            "laser_settings": {
                "position_x": self.lp_x.value(),
                "position_y": self.lp_y.value(),
                "threshold_laser": self.thre_laser.text(),
                "threshold_dots": self.thre_dots.text()
            },
            "detection_settings": {
                "max_detection_count": self.max_detection_count
            },
            "file_settings": {
                "file_name": self.lineEdit_fn.text(),
                "folder_path": self.label_fp.text()
            },
            "itc503_settings": {
                "gpib_address": self.lineEdit_ledport_2.text()
            },
            "focus_mapping_settings": {
                "fm_step": self.fm_step.text(),
                "fm_step_2": self.fm_step_2.text(),
                "fm_step_3": self.fm_step_3.text(),
                "spinBox_afoffset": self.spinBox_afoffset.value(),
                "mapping_expanding_chk": self.mapping_expanding_chk.isChecked(),
                "no_expanding": self.no_expanding.text(),
            },
            "version": "1.0"
        }
    
    def _apply_config(self, config):
        """Apply the configuration dictionary to the UI"""
        # Motor settings
        motor = config.get("motor_settings", {})
        self.lineEdit_2.setText(motor.get("lineEdit_2", ""))
        self.lineEdit_6.setText(motor.get("lineEdit_6", ""))
        self.lineEdit_3.setText(motor.get("lineEdit_3", ""))
        self.lineEdit_7.setText(motor.get("lineEdit_7", ""))
        self.lineEdit_8.setText(motor.get("lineEdit_8", ""))
        self.lineEdit_4.setText(motor.get("lineEdit_4", ""))
        self.spinBox.setValue(motor.get("spinBox", 0))
        self.spinBox_2.setValue(motor.get("spinBox_2", 0))
        self.label_26.setText(motor.get("label_26", ""))
        self.label_29.setText(motor.get("label_29", ""))
        self.label_31.setText(motor.get("label_31", ""))
        self.label_33.setText(motor.get("label_33", ""))
        
        # Laser settings
        laser = config.get("laser_settings", {})
        self.lp_x.setValue(laser.get("position_x", 0))
        self.lp_y.setValue(laser.get("position_y", 0))
        self.thre_laser.setText(laser.get("threshold_laser", "0.5"))
        self.thre_dots.setText(laser.get("threshold_dots", "0.5"))
        
        # Detection settings
        detection = config.get("detection_settings", {})
        self.max_detection_count = detection.get("max_detection_count", 80)
        
        # File settings
        file_settings = config.get("file_settings", {})
        self.lineEdit_fn.setText(file_settings.get("file_name", "data"))
        folder_path = file_settings.get("folder_path", "None")
        self.label_fp.setText(folder_path if folder_path and folder_path != "None" else "None")
        
        itc503 = config.get("itc503_settings", {})
        self.lineEdit_ledport_2.setText(itc503.get("gpib_address", "GPIB0::24::INSTR"))
        
        fm_map = config.get("focus_mapping_settings", {})
        self.fm_step.setText(fm_map.get("fm_step", "20"))
        self.fm_step_2.setText(fm_map.get("fm_step_2", "5"))
        self.fm_step_3.setText(fm_map.get("fm_step_3", "30"))
        try:
            self.spinBox_afoffset.setValue(int(fm_map.get("spinBox_afoffset", 0)))
        except (TypeError, ValueError):
            self.spinBox_afoffset.setValue(0)
        self.mapping_expanding_chk.setChecked(bool(fm_map.get("mapping_expanding_chk", False)))
        self.no_expanding.setText(fm_map.get("no_expanding", "5"))
    
    def _refresh_spectrum_acq_buttons(self):
        """Solis·SDK2 로컬 모드 또는 TCP 서버 연결 시 스펙트럼 취득 버튼 활성화."""
        if self.radioButton_7.isChecked() or self.rbtn_sdk2.isChecked():
            self.btn_acq.setEnabled(True)
            self.btn_read_frame.setEnabled(True)
            self.debug_print("Spectrum mode (Solis or SDK2): btn_acq / btn_read_frame enabled")
        elif hasattr(self, "client_socket") and self.client_socket is not None:
            self.btn_acq.setEnabled(True)
            self.btn_read_frame.setEnabled(True)
            self.debug_print("Server connected: btn_acq / btn_read_frame enabled")
        else:
            self.btn_acq.setEnabled(False)
            self.btn_read_frame.setEnabled(False)
            self.debug_print("Spectrum acq buttons disabled (select Solis/SDK2 or connect server)")

    def on_btn_acq_clicked(self):
        """btn_acq button clicked - spectrum acquisition"""
        self.debug_print(f"=== on_btn_acq_clicked called ===")
        
        # Prevent duplicate clicks
        if hasattr(self, '_acquiring_spectrum') and self._acquiring_spectrum:
            self.debug_print("Spectrum acquisition already in progress, ignoring click")
            return
        
        try:
            self._acquiring_spectrum = True
            self.btn_acq.setEnabled(False)  # Disable button
            self.debug_print("btn_acq clicked - Starting spectrum acquisition")
            self.debug_print(f"Current _acquiring_spectrum flag: {self._acquiring_spectrum}")
            
            if self.radioButton_7.isChecked():
                # Spectrum acquisition using Solis
                self.debug_print("Using Solis for spectrum acquisition")
                
                # Manual spectrum acquisition filename generation
                file_name = self.lineEdit_fn.text().strip()
                if not file_name:
                    file_name = "test"  # Default file name
                
                # Duplicate filename handling - generate unique filename
                manual_filename = self.generate_unique_filename(file_name)
                
                # Spectrum acquisition execution (manual execution - only 1 retry)
                success = self.snap_spectrum(max_retries=1, custom_filename=manual_filename)
                
                if success:
                    self.debug_print(f"Manual spectrum acquisition successful: {manual_filename}")
                else:
                    self.debug_print("Manual spectrum acquisition failed")
            
            elif self.rbtn_sdk2.isChecked():
                self.debug_print("Using Andor SDK2 for spectrum acquisition")
                file_name = self.lineEdit_fn.text().strip()
                if not file_name:
                    file_name = "test"
                manual_filename = self.generate_unique_filename(file_name)
                success = self.snap_spectrum(max_retries=1, custom_filename=manual_filename)
                if success:
                    self.debug_print(f"Manual SDK2 spectrum acquisition successful: {manual_filename}")
                else:
                    self.debug_print("Manual SDK2 spectrum acquisition failed")
            
            else:
                # TCP/IP server for spectrum acquisition (e.g. InGaAs remote)
                if hasattr(self, 'client_socket') and self.client_socket is not None:
                    self.debug_print("Using TCP/IP server for spectrum acquisition")
                    try:
                        self.client_socket.send('snap')
                        self.recv_data()
                        self.debug_print("TCP/IP spectrum acquisition successful")
                    except Exception as e:
                        self.debug_print(f"TCP/IP spectrum acquisition failed: {e}")
                else:
                    self.debug_print(
                        "No acquisition method available — select Andor SOLIS or SDK2, or connect TCP server"
                    )
        
        except Exception as e:
            self.debug_print(f"Error in on_btn_acq_clicked: {e}")
        
        finally:
            # Spectrum acquisition completed - flag released and button re-enabled
            self._acquiring_spectrum = False
            self.btn_acq.setEnabled(True)
            self.debug_print("Spectrum acquisition completed - button re-enabled")

    def generate_unique_filename(self, base_name):
        """
        Generate a unique filename that does not duplicate
        Args:
            base_name: base filename (e.g. "test" or "exp1/test")
        Returns:
            unique filename (e.g. "test", "test_1", "test_2", ...)
        """
        folder_path = self.get_save_folder_path()
        
        if not folder_path:
            folder_path = os.getcwd()
        
        # lineEdit_fn에 경로가 있으면 파일명만 사용
        file_base = os.path.basename(base_name) if os.path.dirname(base_name) else base_name
        
        # Try base filename
        sif_filename = f"{file_base}.sif"
        full_path = os.path.join(folder_path, sif_filename)
        
        # If file does not exist, use it
        if not os.path.exists(full_path):
            self.debug_print(f"Using filename: {file_base}")
            return file_base
        
        # If file exists, append number to create unique name
        counter = 1
        while True:
            sif_filename = f"{file_base}_{counter}.sif"
            full_path = os.path.join(folder_path, sif_filename)
            
            if not os.path.exists(full_path):
                unique_name = f"{file_base}_{counter}"
                self.debug_print(f"File exists, using unique filename: {unique_name}")
                return unique_name
            
            counter += 1
            
            # Prevent infinite loop (up to 1000 files)
            if counter > 1000:
                # Add timestamp to force unique name
                from datetime import datetime
                timestamp = datetime.now().strftime("%H%M%S")
                unique_name = f"{file_base}_{timestamp}"
                self.debug_print(f"Too many files, using timestamp: {unique_name}")
                return unique_name


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
    app.setStyle("Fusion")
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())