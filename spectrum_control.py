import serial
import numpy as np
import matplotlib.pyplot as plt
from time import sleep, time
from ctypes import *
from sp_ctrl import ActonSpectrometer  # 추가된 import

class SpectrometerControl:
    def __init__(self, port='COM5', baudrate=9600):
        """스펙트로미터 제어 클래스 초기화"""
        self.spectrometer = ActonSpectrometer(port=port, debug=False, echo=True, dummy=False)
        self.current_grating = 1
        self.gratings = self.spectrometer.read_grating_info()
        
    def connect(self):
        """스펙트로미터 연결"""
        try:
            # ActonSpectrometer는 초기화 시 자동으로 연결됨
            print("스펙트로미터 연결 성공")
            self.get_grating_info()  # 현재 grating 정보 확인
            return True
        except Exception as e:
            print(f"스펙트로미터 연결 실패: {e}")
            return False

    def disconnect(self):
        """스펙트로미터 연결 해제"""
        self.spectrometer.close()
        print("스펙트로미터 연결 해제")

    def set_wavelength(self, wavelength):
        """파장 설정 (nm)"""
        self.spectrometer.write_wl(wavelength)

    def get_wavelength(self):
        """현재 파장 확인"""
        return self.spectrometer.read_wl()

    def get_grating_info(self):
        """현재 grating 정보 읽기"""
        grating_num = self.spectrometer.read_grating()
        self.current_grating = grating_num
        return f"{grating_num} - {self.gratings[grating_num-1][1]}"

    def set_grating(self, grating_num):
        """Grating 변경"""
        if not any(g[0] == grating_num for g in self.gratings):
            raise ValueError(f"Invalid grating number: {grating_num}")
        self.spectrometer.write_grating(grating_num)
        self.current_grating = grating_num
        print(f"Grating 변경됨: {self.get_grating_info()}")

    def set_center_wavelength(self, wavelength):
        """Center wavelength 설정"""
        current_wavelength = self.get_wavelength()
        
        if current_wavelength is None:
            print("현재 파장을 읽을 수 없습니다. 이동을 중단합니다.")
            return False
            
        wavelength_diff = abs(wavelength - current_wavelength)
        
        if wavelength_diff < 1:
            print(f"현재 파장 {current_wavelength}nm가 목표 파장 {wavelength}nm에 이미 충분히 가깝습니다. 이동하지 않습니다.")
            return True
            
        print(f"현재 파장: {current_wavelength}nm -> 목표 파장: {wavelength}nm로 이동 중...")
        self.spectrometer.write_wl(wavelength)
        
        sleep(2)  # 이동 완료 대기 시간
        
        new_wavelength = self.get_wavelength()
        if new_wavelength is not None:
            if abs(new_wavelength - wavelength) < 1:
                print(f"이동 완료. 현재 파장: {new_wavelength}nm")
                return True
            else:
                print(f"이동 실패. 현재 파장: {new_wavelength}nm")
                return False
        else:
            print("이동 후 파장 확인 실패")
            return False

class AndorCamera:
    def __init__(self):
        """Andor SDK2 카메라 제어 클래스 초기화"""
        # DLL 로드
        try:
            sdk_path = r"C:\Program Files\Andor SDK"  # SDK 설치 경로
            if sizeof(c_voidp) == 4:
                self.dll = windll.LoadLibrary(sdk_path + r"\atmcd32d.dll")
            else:
                self.dll = windll.LoadLibrary(sdk_path + r"\atmcd64d.dll")
            print("DLL 로드 성공")
        except Exception as e:
            print(f"DLL 로드 실패: {e}")
            raise
            
        self.background = None
        self.spectrometer = None  # SpectrometerControl 객체를 연결할 변수 추가
        self.target_temperature = -70  # 기본 목표 온도 설정
        
    def connect(self):
        """카메라 연결"""
        try:
            # 카메라 초기화
            ret = self.dll.Initialize(b"")
            if ret != 20002:  # DRV_SUCCESS
                print(f"카메라 초기화 실패: {ret}")
                return False
                
            # 카메라 쿨링
            self.dll.SetTemperature(c_int(-70))  # -70도로 설정
            self.dll.CoolerON()
            
            # 기본 설정
            self.dll.SetReadMode(c_int(4))  # Full Vertical Binning
            self.dll.SetAcquisitionMode(c_int(1))  # Single Scan
            self.dll.SetTriggerMode(c_int(0))  # Internal Trigger
            self.dll.SetExposureTime(c_float(1.0))  # 1초 노출
            
            # 이미지 크기 설정
            width = c_int()
            height = c_int()
            self.dll.GetDetector(byref(width), byref(height))
            self.width = width.value
            self.height = height.value
            
            print("Andor 카메라 연결 성공")
            return True
            
        except Exception as e:
            print(f"카메라 연결 실패: {e}")
            return False
        
    def disconnect(self):
        """카메라 연결 해제"""
        try:
            self.dll.CoolerOFF()
            self.dll.ShutDown()
            print("카메라 연결 해제")
        except Exception as e:
            print(f"카메라 연결 해제 중 오류 발생: {e}")
        
    def set_spectrometer(self, spectrometer):
        """스펙트로미터 객체 연결"""
        self.spectrometer = spectrometer

    def calculate_wavelengths(self, center_wavelength, grating_num, pixel_count):
        """그레이팅과 중심 파장을 기반으로 파장 배열 계산"""
        # 그레이팅에 따른 분해능 (예시 값, 실제 값으로 수정 필요)
        grating_resolutions = {
            1: 0.1,  # 1200 g/mm, 750nm blaze
            2: 0.1,  # 1200 g/mm, 1.0um blaze
            3: 0.5   # 150 g/mm, 1.2um blaze
        }
        
        # 그레이팅 분해능 가져오기
        resolution = grating_resolutions.get(grating_num, 0.1)  # 기본값 0.1nm
        
        # 파장 범위 계산 (픽셀 수 * 분해능 / 2)
        wavelength_range = (pixel_count * resolution) / 2
        
        # 파장 배열 생성
        wavelengths = np.linspace(center_wavelength - wavelength_range,
                                 center_wavelength + wavelength_range,
                                 pixel_count)
        return wavelengths

    def capture_spectrum(self, exposure_time=1.0):
        """스펙트럼 캡처"""
        try:
            # 노출 시간 설정
            self.dll.SetExposureTime(c_float(exposure_time))
            
            # 데이터 배열 준비
            data = np.zeros(self.width, dtype=np.int32)
            c_data = data.ctypes.data_as(POINTER(c_long))
            
            # 데이터 수집 시작
            self.dll.StartAcquisition()
            
            # 데이터 수집 완료 대기
            status = c_int()
            while True:
                self.dll.GetStatus(byref(status))
                if status.value == 20073:  # DRV_IDLE
                    break
                sleep(0.1)
            
            # 데이터 가져오기
            self.dll.GetAcquiredData(c_data, c_ulong(self.width))
            
            # 파장 보정
            if self.spectrometer:
                center_wavelength = self.spectrometer.get_wavelength()
                grating_num = self.spectrometer.current_grating
                wavelengths = self.calculate_wavelengths(center_wavelength, grating_num, self.width)
            else:
                wavelengths = np.linspace(200, 800, len(data))  # 기본값
            
            return wavelengths, data
            
        except Exception as e:
            print(f"스펙트럼 캡처 중 오류 발생: {e}")
            return None, None

    def set_exposure_time(self, exposure_time):
        """노출 시간 설정"""
        try:
            ret = self.dll.SetExposureTime(c_float(exposure_time))
            if ret == 20002:  # DRV_SUCCESS
                print(f"노출 시간이 {exposure_time}초로 설정되었습니다.")
            else:
                print(f"노출 시간 설정 실패: {ret}")
        except Exception as e:
            print(f"노출 시간 설정 실패: {e}")
            
    def single_shot(self):
        """단일 측정"""
        return self.capture_spectrum()
        
    def real_time_measurement(self, duration=10, interval=0.5):
        """실시간 측정"""
        try:
            start_time = time()
            while time() - start_time < duration:
                wavelengths, spectrum = self.single_shot()
                if wavelengths is not None:
                    # 실시간 데이터 처리 (예: 그래프 업데이트)
                    self.update_real_time_plot(wavelengths, spectrum)
                sleep(interval)
        except KeyboardInterrupt:
            print("실시간 측정 중지")
            
    def measure_background(self):
        """배경 측정"""
        self.background = self.single_shot()[1]
        print("배경 측정 완료")
        
    def update_real_time_plot(self, wavelengths, spectrum):
        """실시간 그래프 업데이트"""
        plt.clf()
        plt.plot(wavelengths, spectrum)
        plt.xlabel('Wavelength (nm)')
        plt.ylabel('Intensity')
        plt.title('Real-time Spectrum')
        plt.pause(0.01)

    def get_temperature(self, retries=3):
        """현재 온도 읽기 (재시도 로직 추가)"""
        for attempt in range(retries):
            try:
                temperature = c_float()
                status = self.dll.GetTemperature(byref(temperature))
                print(f'Status : {status}')
                
                # 상태 코드 처리
                if status == 20037:  # DRV_TEMPERATURE_NOT_REACHED
                    print("온도가 아직 목표치에 도달하지 않았습니다.")
                    return temperature.value  # 현재 온도는 반환
                elif status != 20002:  # DRV_SUCCESS가 아닌 경우
                    print(f"온도 읽기 실패: 상태 코드 {status}")
                    sleep(1)  # 재시도 전 대기
                    continue
                
                # 유효한 온도 값인지 확인
                temp_value = temperature.value
                if not (isinstance(temp_value, float) and -100 <= temp_value <= 100):
                    print(f"유효하지 않은 온도 값: {temp_value}")
                    sleep(1)  # 재시도 전 대기
                    continue
                
                return temp_value
                
            except Exception as e:
                print(f"온도 읽기 중 오류 발생: {e}")
                sleep(1)  # 재시도 전 대기
        
        print(f"온도 읽기 실패: {retries}번 재시도 후에도 성공하지 못했습니다.")
        return None

    def get_target_temperature(self):
        """목표 온도 읽기"""
        try:
            target_temp = c_float()
            status = self.dll.GetTemperatureF(byref(target_temp))
            
            # 상태 코드 확인 (DRV_SUCCESS = 20002)
            if status == 20002:
                return target_temp.value
            else:
                print(f"목표 온도 읽기 실패: 상태 코드 {status}")
                return None
                
        except Exception as e:
            print(f"목표 온도 읽기 중 오류 발생: {e}")
            return None

    def wait_for_temperature(self, timeout=300, check_interval=5):
        """목표 온도에 도달할 때까지 대기"""
        start_time = time()
        while time() - start_time < timeout:
            current_temp = self.get_temperature()
            target_temp = self.get_target_temperature()  # 목표 온도 읽기
            
            if current_temp is None or target_temp is None:
                print("온도 읽기 실패. 측정을 중단합니다.")
                return False
            
            print(f"현재 온도: {current_temp:.1f}°C / 목표 온도: {target_temp:.1f}°C")
            
            if abs(current_temp - target_temp) < 1.0:  # 1°C 이내면 도달한 것으로 판단
                print("목표 온도에 도달했습니다.")
                return True
            
            sleep(check_interval)
        
        print(f"시간 초과: {timeout}초 내에 목표 온도에 도달하지 못했습니다.")
        return False

def main():
    # 스펙트로미터 초기화
    spec = SpectrometerControl(port='COM5')  # 실제 사용하는 포트로 변경 필요
    if not spec.connect():
        return
        
    # 카메라 초기화
    camera = AndorCamera()
    if not camera.connect():
        spec.disconnect()
        return
        
    # 카메라와 스펙트로미터 연결
    camera.set_spectrometer(spec)
    
    try:
        # 온도 확인 및 대기
        print("카메라 온도 확인 중...")
        if not camera.wait_for_temperature():
            print("온도가 목표치에 도달하지 않아 측정을 중단합니다.")
            return
        
        # Grating 정보 확인
        grating_info = spec.get_grating_info()
        print(f"현재 Grating 정보: {grating_info}")
        
        # Center wavelength를 900nm로 설정
        target_wavelength = 900
        if not spec.set_center_wavelength(target_wavelength):
            print("파장 이동 실패. 측정을 중단합니다.")
            return
            
        # 단일 측정 수행
        wavelengths, spectrum = camera.capture_spectrum(exposure_time=0.5)
        print(wavelengths, spectrum)
        if wavelengths is not None:
            # 측정 결과 플롯
            plt.plot(wavelengths, spectrum)
            plt.xlabel('Wavelength (nm)')
            plt.ylabel('Intensity')
            plt.title(f'Spectrum Measurement (Grating: {grating_info}, Center: {target_wavelength}nm)')
            plt.show()
            
    finally:
        # 연결 해제
        camera.disconnect()
        spec.disconnect()

if __name__ == "__main__":
    main() 