import sys
import serial
import serial.tools.list_ports
import pylablib as pll
from pylablib.devices import Andor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QLabel, QMessageBox, QDialog, QTableWidget, 
                           QTableWidgetItem, QDialogButtonBox)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon
from PyQt6 import uic
import numpy as np

# Andor SDK 경로 설정
pll.par["devices/dlls/andor_sdk2"] = "C:/Program Files/Andor SOLIS"

class GratingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Gratings")
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # 그레이팅 테이블 생성
        self.table = QTableWidget(3, 3)  # 3행 3열
        self.table.setHorizontalHeaderLabels(["Grating", "Lines", "Blaze"])
        
        # 기본 데이터 설정
        default_data = [
            ["Grating 1", "1200", "750UM"],
            ["Grating 2", "1200", "1UM"],
            ["Grating 3", "150", "1"]
        ]
        
        for i, row in enumerate(default_data):
            for j, item in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(item))
        
        layout.addWidget(self.table)
        
        # 버튼 추가
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # UI 설정
        uic.loadUi('ui_sp.ui', self)
        
        # Andor 카메라 초기화
        self.camera = None
        self.camera_connected = False
        
        # 아이콘 설정
        self.setup_icons()
        
        # 타이머 초기화 (실시간 업데이트용)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        
        self.ToolbarWidget.read(canvas=self.plotWidget)
        
        # COM 포트 초기화
        self.init_com_ports()
        
        # 시그널 연결
        self.connect_signals()
        
        # 초기 상태 설정
        self.detector_connected = False
        self.spectrograph_connected = False
        self.cooling_active = False
        
        # dry run 모드 초기화
        self.dry_run_mode = False
        self.dryRunCheckBox.stateChanged.connect(self.toggle_dry_run_mode)
        
        # Plot Setting 초기화
        self.init_plot_settings()
        
    def setup_icons(self):
        """SVG 아이콘 설정"""
        # 아이콘 파일 경로
        icon_path = "res/"
        
        # 각 버튼에 아이콘 설정
        self.singleShotButton.setIcon(QIcon(icon_path + "camera.svg"))
        self.backgroundButton.setIcon(QIcon(icon_path + "background.svg"))
        self.realTimeButton.setIcon(QIcon(icon_path + "play.svg"))
        self.abortButton.setIcon(QIcon(icon_path + "stop.svg"))
        self.saveButton.setIcon(QIcon(icon_path + "save.svg"))
        
        # 아이콘 크기 설정
        icon_size = QSize(30, 30)
        self.singleShotButton.setIconSize(icon_size)
        self.backgroundButton.setIconSize(icon_size)
        self.realTimeButton.setIconSize(icon_size)
        self.abortButton.setIconSize(icon_size)
        self.saveButton.setIconSize(icon_size)
        
    def init_com_ports(self):
        """사용 가능한 COM 포트 목록 업데이트"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.comPortComboBox.addItems(ports)
    
    def connect_signals(self):
        """시그널-슬롯 연결"""
        # Action 버튼 컨트롤
        self.singleShotButton.clicked.connect(self.single_shot)
        self.realTimeButton.clicked.connect(self.real_time)
        self.abortButton.clicked.connect(self.abort_acquisition)
        self.saveButton.clicked.connect(self.save_data)
        self.backgroundButton.clicked.connect(self.measure_background)
        
        # Detector 컨트롤
        self.connectButton.clicked.connect(self.toggle_detector_connection)
        self.coolingCheckBox.stateChanged.connect(self.toggle_cooling)
        self.setTempButton.clicked.connect(self.set_target_temperature)
        self.setExposeButton.clicked.connect(self.set_expose_time)
        self.readoutModeComboBox.currentTextChanged.connect(self.change_readout_mode)
        
        # Spectrograph 컨트롤
        self.connectMotorButton.clicked.connect(self.toggle_spectrograph_connection)
        self.loadDefaultsButton.clicked.connect(self.load_spectrograph_defaults)
        self.editGratingsButton.clicked.connect(self.show_grating_dialog)
        self.gratingComboBox.currentTextChanged.connect(self.change_grating)
        self.centerWavelengthEdit.returnPressed.connect(self.set_center_wavelength)
        self.offsetEdit.returnPressed.connect(self.set_offset)
        self.homeButton.clicked.connect(self.home_spectrograph)
        self.stopButton.clicked.connect(self.stop_spectrograph)
        
    def toggle_dry_run_mode(self, state):
        """dry run 모드 토글"""
        self.dry_run_mode = bool(state)
        if self.dry_run_mode:
            self.detector_connected = True
            self.spectrograph_connected = True
            self.connectionStatusLabel.setText("Status: Dry Run Mode")
        else:
            self.detector_connected = False
            self.spectrograph_connected = False
            self.connectionStatusLabel.setText("Status: Disconnected")
            self.update_timer.stop()
            
    def update_status(self):
        """상태 정보 업데이트"""
        if self.camera_connected or self.dry_run_mode:
            try:
                if self.dry_run_mode:
                    # dry run 모드에서는 테스트 데이터 생성
                    current_temp = -70.0
                    temp_status = "Cooling"
                else:
                    # 실제 카메라에서 데이터 읽기
                    current_temp = self.camera.get_temperature()
                    temp_status = self.camera.get_temperature_status()
                
                # GUI 업데이트
                self.currentTempValueLabel.setText(f"{current_temp:.1f} °C")
                self.tempStatusValueLabel.setText(temp_status)
                
            except Exception as e:
                print(f"상태 업데이트 오류: {str(e)}")
                # 에러 발생 시 GUI 상태 초기화
                self.currentTempValueLabel.setText("-- °C")
                self.tempStatusValueLabel.setText("--")
            
    def init_plot_settings(self):
        """Plot Setting 위젯 초기화"""
        # 폰트 크기 설정
        self.labelFontSizeSpinBox.valueChanged.connect(self.update_font_sizes)
        self.tickFontSizeSpinBox.valueChanged.connect(self.update_font_sizes)
        
        # 선 설정
        self.lineWidthSpinBox.valueChanged.connect(self.update_line_settings)
        self.lineColorComboBox.currentTextChanged.connect(self.update_line_settings)
        
        # Y축 스케일 설정
        self.autoScaleCheckBox.stateChanged.connect(self.toggle_y_axis_scale)
        self.yMinSpinBox.valueChanged.connect(self.update_y_axis_range)
        self.yMaxSpinBox.valueChanged.connect(self.update_y_axis_range)
        
    def update_font_sizes(self):
        """폰트 크기 업데이트"""
        label_size = self.labelFontSizeSpinBox.value()
        tick_size = self.tickFontSizeSpinBox.value()
        
        self.plotWidget.axes.set_xlabel('Wavelength (nm)', fontsize=label_size)
        self.plotWidget.axes.set_ylabel('Intensity (Counts)', fontsize=label_size)
        self.plotWidget.axes.tick_params(axis="both", direction="in", pad=10, labelsize=tick_size)
        self.plotWidget.draw()
        
    def update_line_settings(self):
        """선 설정 업데이트"""
        line_width = self.lineWidthSpinBox.value()
        line_color = self.lineColorComboBox.currentText()  # HEX 코드를 직접 사용
        
        for line in self.plotWidget.axes.lines:
            line.set_linewidth(line_width)
            line.set_color(line_color)
        self.plotWidget.draw()
        
    def toggle_y_axis_scale(self, state):
        """Y축 스케일 자동/수동 전환"""
        auto_scale = bool(state)
        self.yMinSpinBox.setEnabled(not auto_scale)
        self.yMaxSpinBox.setEnabled(not auto_scale)
        
        if auto_scale:
            self.plotWidget.axes.set_ylim(auto=True)
        else:
            self.update_y_axis_range()
            
    def update_y_axis_range(self):
        """Y축 범위 업데이트"""
        if not self.autoScaleCheckBox.isChecked():
            y_min = self.yMinSpinBox.value()
            y_max = self.yMaxSpinBox.value()
            self.plotWidget.axes.set_ylim(y_min, y_max)
            self.plotWidget.draw()
            
    def plot_test_data(self, add_noise=True):
        """테스트 데이터 플롯"""
        try:
            # 테스트 데이터 생성 (가우시안 피크)
            x = np.linspace(0, 1000, 1000)
            
            # 기본 피크
            y1 = np.exp(-(x-500)**2/(2*20**2)) * 1000
            
            # 선폭이 다른 피크 추가
            y2 = np.exp(-(x-300)**2/(2*100**2)) * 500
            
            # 두 피크 합성
            y = y1 + y2
            
            if add_noise:
                # 랜덤 노이즈 추가
                noise = np.random.normal(0, 50, len(x))
                y += noise
            
            # 플롯 업데이트
            self.plotWidget.axes.clear()
            self.plotWidget.axes.plot(x, y, 
                                    linewidth=self.lineWidthSpinBox.value(),
                                    color=self.lineColorComboBox.currentText())  # HEX 코드를 직접 사용
            self.plotWidget.axes.set_xlabel('Wavelength (nm)', fontsize=self.labelFontSizeSpinBox.value())
            self.plotWidget.axes.set_ylabel('Intensity (Counts)', fontsize=self.labelFontSizeSpinBox.value())
            self.plotWidget.axes.tick_params(axis="both", direction="in", pad=10, labelsize=self.tickFontSizeSpinBox.value())
            
            if not self.autoScaleCheckBox.isChecked():
                self.plotWidget.axes.set_ylim(self.yMinSpinBox.value(), self.yMaxSpinBox.value())
                
            self.plotWidget.figure.tight_layout()
            self.plotWidget.draw()
        except Exception as e:
            print(f"테스트 플롯 오류: {str(e)}")
    
    def toggle_detector_connection(self):
        """Detector 연결/해제"""
        self.connect_andor_camera()
    
    def toggle_cooling(self, state):
        """냉각 시스템 ON/OFF"""
        try:
            if not self.camera_connected:
                QMessageBox.warning(self, "경고", "카메라가 연결되지 않았습니다.")
                return
                
            self.camera.set_cooler(bool(state))
            temp_status = self.camera.get_temperature_status()
            self.tempStatusValueLabel.setText(temp_status)
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"냉각 시스템 제어 오류: {str(e)}")
    
    def set_target_temperature(self):
        """목표 온도 설정"""
        try:
            if not self.camera_connected:
                QMessageBox.warning(self, "경고", "카메라가 연결되지 않았습니다.")
                return
                
            value = self.targetTempSpinBox.value()
            self.camera.set_temperature(value)
            print(f"목표 온도 설정: {value}°C")
            
            # 온도 상태 업데이트
            temp_status = self.camera.get_temperature_status()
            self.tempStatusValueLabel.setText(temp_status)
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"온도 설정 오류: {str(e)}")
    
    def set_expose_time(self):
        """노출 시간 설정"""
        try:
            if not self.camera_connected:
                QMessageBox.warning(self, "경고", "카메라가 연결되지 않았습니다.")
                return
                
            value = self.exposeTimeSpinBox.value()
            self.camera.set_exposure(value)
            print(f"노출 시간 설정: {value}초")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"노출 시간 설정 오류: {str(e)}")
    
    def change_readout_mode(self, mode):
        """판독 모드 변경"""
        try:
            # TODO: 실제 판독 모드 변경 구현
            print(f"판독 모드 변경: {mode}")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"판독 모드 변경 오류: {str(e)}")
    
    def toggle_spectrograph_connection(self):
        """Spectrograph 연결/해제"""
        try:
            port = self.comPortComboBox.currentText()
            if not self.spectrograph_connected:
                # TODO: 실제 Spectrograph 연결 구현
                self.spectrograph_connected = True
                self.connectMotorButton.setText("Disconnect")
            else:
                # TODO: 실제 Spectrograph 해제 구현
                self.spectrograph_connected = False
                self.connectMotorButton.setText("Connect")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"Spectrograph 연결 오류: {str(e)}")
    
    def load_spectrograph_defaults(self):
        """Spectrograph 기본 정보 로드"""
        try:
            # TODO: 실제 정보 로드 구현
            self.focalLengthEdit.setText("0.3")
            self.angularDevEdit.setText("45.0")
            self.focalTiltEdit.setText("0.0")
            self.dataSetPixelEdit.setText("13.5")
            self.acquisitionPixelEdit.setText("13.5")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"기본 정보 로드 오류: {str(e)}")
    
    def show_grating_dialog(self):
        """그레이팅 설정 다이얼로그 표시"""
        dialog = GratingDialog(self)
        dialog.exec()
    
    def change_grating(self, grating):
        """그레이팅 변경"""
        try:
            # TODO: 실제 그레이팅 변경 구현
            print(f"그레이팅 변경: {grating}")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"그레이팅 변경 오류: {str(e)}")
    
    def set_center_wavelength(self):
        """중심 파장 설정"""
        try:
            wavelength = float(self.centerWavelengthEdit.text())
            # TODO: 실제 중심 파장 설정 구현
            print(f"중심 파장 설정: {wavelength}nm")
        except ValueError:
            QMessageBox.warning(self, "경고", "올바른 파장 값을 입력하세요.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파장 설정 오류: {str(e)}")
    
    def set_offset(self):
        """오프셋 설정"""
        try:
            offset = float(self.offsetEdit.text())
            # TODO: 실제 오프셋 설정 구현
            print(f"오프셋 설정: {offset}픽셀")
        except ValueError:
            QMessageBox.warning(self, "경고", "올바른 오프셋 값을 입력하세요.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"오프셋 설정 오류: {str(e)}")
    
    def home_spectrograph(self):
        """Spectrograph 홈 위치로 이동"""
        try:
            if not self.spectrograph_connected:
                QMessageBox.warning(self, "경고", "Spectrograph가 연결되지 않았습니다.")
                return
            # TODO: 실제 홈 위치 이동 구현
            print("Spectrograph 홈 위치로 이동 중...")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"홈 위치 이동 오류: {str(e)}")
    
    def stop_spectrograph(self):
        """Spectrograph 이동 정지"""
        try:
            if not self.spectrograph_connected:
                QMessageBox.warning(self, "경고", "Spectrograph가 연결되지 않았습니다.")
                return
            # TODO: 실제 정지 구현
            print("Spectrograph 이동 정지")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"이동 정지 오류: {str(e)}")

    def single_shot(self):
        """단일 측정 수행"""
        try:
            if not self.detector_connected and not self.dry_run_mode:
                QMessageBox.warning(self, "경고", "Detector가 연결되지 않았습니다.")
                return
                
            if self.dry_run_mode:
                self.plot_test_data(add_noise=False)
            else:
                # TODO: 실제 단일 측정 구현
                pass
        except Exception as e:
            QMessageBox.critical(self, "오류", f"단일 측정 오류: {str(e)}")

    def real_time(self):
        """실시간 측정 수행"""
        try:
            if not self.detector_connected and not self.dry_run_mode:
                QMessageBox.warning(self, "경고", "Detector가 연결되지 않았습니다.")
                return
                
            if self.dry_run_mode:
                self.update_timer.start(100)  # 0.1초마다 업데이트
                self.update_timer.timeout.connect(lambda: self.plot_test_data(add_noise=True))
                # 버튼 상태 변경
                self.realTimeButton.setEnabled(False)
                self.abortButton.setEnabled(True)
            else:
                # TODO: 실제 실시간 측정 구현
                pass
        except Exception as e:
            QMessageBox.critical(self, "오류", f"실시간 측정 오류: {str(e)}")

    def abort_acquisition(self):
        """측정 중단"""
        try:
            if self.dry_run_mode:
                self.update_timer.stop()
                self.update_timer.timeout.disconnect()
                # 버튼 상태 변경
                self.realTimeButton.setEnabled(True)
                self.abortButton.setEnabled(False)
            else:
                # TODO: 실제 측정 중단 구현
                pass
        except Exception as e:
            QMessageBox.critical(self, "오류", f"측정 중단 오류: {str(e)}")

    def save_data(self):
        """데이터 저장"""
        try:
            # TODO: 실제 데이터 저장 구현
            print("데이터 저장됨")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"데이터 저장 오류: {str(e)}")

    def measure_background(self):
        """배경 측정 수행"""
        try:
            if not self.detector_connected:
                QMessageBox.warning(self, "경고", "Detector가 연결되지 않았습니다.")
                return
            # TODO: 실제 배경 측정 구현
            print("배경 측정 중...")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"배경 측정 오류: {str(e)}")

    def connect_andor_camera(self):
        """Andor 카메라 연결 및 초기화"""
        try:
            if not self.camera_connected:
                # 카메라 초기화
                self.camera = Andor.AndorSDK2Camera()
                
                # 온도 범위 가져오기
                temp_range = self.camera.get_temperature_range()
                self.tempRangeValueLabel.setText(f"{temp_range[0]:.1f} to {temp_range[1]:.1f} °C")
                
                # 기본 설정
                target_temp = self.targetTempSpinBox.value()
                self.camera.set_temperature(target_temp)  # 타겟 온도로 설정
                self.camera.set_cooler(True)     # 냉각기 켜기
                self.coolingCheckBox.setChecked(True)  # 체크박스 체크 상태로 설정
                
                # 연결 상태 업데이트
                self.camera_connected = True
                self.detector_connected = True
                self.connectButton.setText("Disconnect")
                self.connectionStatusLabel.setText("Status: Connected")
                
                # GUI 상태 업데이트
                current_temp = self.camera.get_temperature()
                temp_status = self.camera.get_temperature_status()
                self.currentTempValueLabel.setText(f"{current_temp:.1f} °C")
                self.tempStatusValueLabel.setText(temp_status)
                
                # 컨트롤 활성화
                self.coolingCheckBox.setEnabled(True)
                self.targetTempSpinBox.setEnabled(True)
                
                # 상태 업데이트 타이머 시작
                self.update_timer.start(1000)
                
                QMessageBox.information(self, "연결 성공", "Andor 카메라가 성공적으로 연결되었습니다.")
            else:
                # 카메라 연결 해제
                if self.camera:
                    self.camera.set_cooler(False)
                    self.camera.close()
                    self.camera = None
                
                # 연결 상태 업데이트
                self.camera_connected = False
                self.detector_connected = False
                self.connectButton.setText("Connect")
                self.connectionStatusLabel.setText("Status: Disconnected")
                
                # GUI 상태 업데이트
                self.currentTempValueLabel.setText("-- °C")
                self.tempStatusValueLabel.setText("--")
                
                # 컨트롤 비활성화
                self.coolingCheckBox.setEnabled(False)
                self.targetTempSpinBox.setEnabled(False)
                
                self.update_timer.stop()
                
                QMessageBox.information(self, "연결 해제", "Andor 카메라 연결이 해제되었습니다.")
                
        except Exception as e:
            QMessageBox.critical(self, "연결 오류", f"Andor 카메라 연결 중 오류가 발생했습니다:\n{str(e)}")
            self.camera_connected = False
            self.detector_connected = False
            self.connectButton.setText("Connect")
            self.connectionStatusLabel.setText("Status: Connection Failed")
            
            # GUI 상태 초기화
            self.currentTempValueLabel.setText("-- °C")
            self.tempStatusValueLabel.setText("--")
            
            # 컨트롤 비활성화
            self.coolingCheckBox.setEnabled(False)
            self.targetTempSpinBox.setEnabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())