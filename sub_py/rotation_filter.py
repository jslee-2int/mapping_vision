"""
FW102C Motorized Filter Wheel Controller
COM11 포트를 통한 시리얼 통신 제어
"""

import serial
import time
import re
from typing import Optional, Literal


class FW102C:
    """FW102C 필터 휠 제어 클래스"""
    
    def __init__(self, port: str = 'COM11', baudrate: int = 115200, timeout: float = 1.0):
        """
        FW102C 초기화
        
        Args:
            port: COM 포트 (기본값: 'COM11')
            baudrate: 통신 속도 (기본값: 115200)
            timeout: 타임아웃 시간 (초)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None
        
    def connect(self) -> bool:
        """
        시리얼 포트 연결
        
        Returns:
            연결 성공 여부
        """
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            time.sleep(0.5)  # 연결 안정화 대기
            
            # 버퍼 클리어
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            print(f"FW102C connected to {self.port}")
            return True
            
        except serial.SerialException as e:
            print(f"Failed to connect to {self.port}: {e}")
            return False
    
    def disconnect(self):
        """시리얼 포트 연결 해제"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"FW102C disconnected from {self.port}")
    
    def _send_command(self, command: str) -> str:
        """
        명령어 전송 및 응답 수신
        
        Args:
            command: 전송할 명령어 (CR은 자동 추가됨)
            
        Returns:
            장치의 응답 문자열
        """
        if not self.ser or not self.ser.is_open:
            raise ConnectionError("Serial port is not open")
        
        # Clear input buffer before sending command
        self.ser.reset_input_buffer()
        
        # 명령어 전송 (CR 추가)
        cmd_with_cr = command + '\r'
        self.ser.write(cmd_with_cr.encode('ascii'))
        
        # 응답 대기
        time.sleep(0.2)
        
        # 응답 수신
        response = ""
        if self.ser.in_waiting > 0:
            raw_response = self.ser.read(self.ser.in_waiting).decode('ascii', errors='ignore')
            
            # Remove prompt ">" and clean up response
            lines = raw_response.strip().split('\n')
            
            # Filter out empty lines and prompts
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                # Remove prompt ">" from beginning
                if line.startswith('>'):
                    line = line[1:].strip()
                # Skip empty lines and command echoes
                if line and not line.startswith(command.split('=')[0]):
                    cleaned_lines.append(line)
            
            # Return the last non-empty line
            if cleaned_lines:
                response = cleaned_lines[-1]
            else:
                response = raw_response.strip()
        
        return response
    
    def get_id(self) -> str:
        """
        장치 ID 및 펌웨어 버전 조회
        
        Returns:
            모델 번호 및 펌웨어 버전
        """
        response = self._send_command('*idn?')
        return response
    
    def set_position(self, position: int) -> str:
        """
        필터 위치 설정
        
        Args:
            position: 필터 위치 (1-6 또는 1-12)
            
        Returns:
            장치 응답
        """
        response = self._send_command(f'pos={position}')
        return response
    
    def get_position(self) -> int:
        """
        현재 필터 위치 조회
        
        Returns:
            현재 필터 위치
        """
        response = self._send_command('pos?')
        try:
            # 응답에서 숫자만 추출 (여러 가지 형식 지원)
            # Find first number in response
            match = re.search(r'\d+', response)
            if match:
                position = int(match.group())
                return position
            else:
                print(f"Invalid position response: {response}")
                return -1
        except (ValueError, AttributeError) as e:
            print(f"Invalid position response: {response} (Error: {e})")
            return -1
    
    def set_position_count(self, count: Literal[6, 12]) -> str:
        """
        휠 타입 설정 (6개 또는 12개 필터)
        
        Args:
            count: 6 또는 12
            
        Returns:
            장치 응답
        """
        if count not in [6, 12]:
            raise ValueError("Position count must be 6 or 12")
        
        response = self._send_command(f'pcount={count}')
        return response
    
    def get_position_count(self) -> int:
        """
        휠 타입 조회
        
        Returns:
            필터 개수 (6 또는 12)
        """
        response = self._send_command('pcount?')
        try:
            # 응답에서 숫자만 추출 (여러 가지 형식 지원)
            # Find first number in response
            match = re.search(r'\d+', response)
            if match:
                count = int(match.group())
                return count
            else:
                print(f"Invalid position count response: {response}")
                return -1
        except (ValueError, AttributeError) as e:
            print(f"Invalid position count response: {response} (Error: {e})")
            return -1
    
    def set_trigger_mode(self, mode: Literal[0, 1]) -> str:
        """
        외부 트리거 모드 설정
        
        Args:
            mode: 0 = 입력 모드, 1 = 출력 모드
            
        Returns:
            장치 응답
        """
        response = self._send_command(f'trig={mode}')
        return response
    
    def get_trigger_mode(self) -> int:
        """
        트리거 모드 조회
        
        Returns:
            트리거 모드 (0 또는 1)
        """
        response = self._send_command('trig?')
        try:
            match = re.search(r'\d+', response)
            if match:
                mode = int(match.group())
                return mode
            else:
                print(f"Invalid trigger mode response: {response}")
                return -1
        except (ValueError, AttributeError) as e:
            print(f"Invalid trigger mode response: {response} (Error: {e})")
            return -1
    
    def set_speed_mode(self, mode: Literal[0, 1]) -> str:
        """
        속도 모드 설정
        
        Args:
            mode: 0 = 저속, 1 = 고속
            
        Returns:
            장치 응답
        """
        response = self._send_command(f'speed={mode}')
        return response
    
    def get_speed_mode(self) -> int:
        """
        속도 모드 조회
        
        Returns:
            속도 모드 (0 = 저속, 1 = 고속)
        """
        response = self._send_command('speed?')
        try:
            match = re.search(r'\d+', response)
            if match:
                mode = int(match.group())
                return mode
            else:
                print(f"Invalid speed mode response: {response}")
                return -1
        except (ValueError, AttributeError) as e:
            print(f"Invalid speed mode response: {response} (Error: {e})")
            return -1
    
    def set_sensor_mode(self, mode: Literal[0, 1]) -> str:
        """
        센서 모드 설정
        
        Args:
            mode: 0 = 휠이 정지 시 센서 끔 (광 누출 방지), 1 = 센서 항상 활성
            
        Returns:
            장치 응답
        """
        response = self._send_command(f'sensors={mode}')
        return response
    
    def get_sensor_mode(self) -> int:
        """
        센서 모드 조회
        
        Returns:
            센서 모드 (0 또는 1)
        """
        response = self._send_command('sensors?')
        try:
            match = re.search(r'\d+', response)
            if match:
                mode = int(match.group())
                return mode
            else:
                print(f"Invalid sensor mode response: {response}")
                return -1
        except (ValueError, AttributeError) as e:
            print(f"Invalid sensor mode response: {response} (Error: {e})")
            return -1
    
    def set_baud_rate(self, rate: Literal[0, 1]) -> str:
        """
        통신 속도 설정
        
        Args:
            rate: 0 = 9600 bps, 1 = 115200 bps
            
        Returns:
            장치 응답
        """
        response = self._send_command(f'baud={rate}')
        return response
    
    def get_baud_rate(self) -> int:
        """
        통신 속도 조회
        
        Returns:
            통신 속도 (0 = 9600, 1 = 115200)
        """
        response = self._send_command('baud?')
        try:
            match = re.search(r'\d+', response)
            if match:
                rate = int(match.group())
                return rate
            else:
                print(f"Invalid baud rate response: {response}")
                return -1
        except (ValueError, AttributeError) as e:
            print(f"Invalid baud rate response: {response} (Error: {e})")
            return -1
    
    def save_settings(self) -> str:
        """
        현재 설정을 기본값으로 저장 (전원 켜짐 시 적용)
        
        Returns:
            장치 응답
        """
        response = self._send_command('save')
        return response
    
    def __enter__(self):
        """컨텍스트 매니저 진입"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.disconnect()


def demo():
    """사용 예제"""
    # 방법 1: 일반 사용
    fw = FW102C(port='COM11')
    
    if fw.connect():
        try:
            # 장치 ID 확인
            device_id = fw.get_id()
            print(f"Device ID: {device_id}")
            
            # 현재 위치 확인
            current_pos = fw.get_position()
            print(f"Current position: {current_pos}")
            
            # 필터 개수 확인
            pos_count = fw.get_position_count()
            print(f"Position count: {pos_count}")
            
            # 위치 1로 이동
            fw.set_position(1)
            print("Moving to position 1...")
            time.sleep(1)
            
            # 위치 확인
            new_pos = fw.get_position()
            print(f"New position: {new_pos}")
            
            # 속도 모드 확인
            speed = fw.get_speed_mode()
            print(f"Speed mode: {speed} (0=slow, 1=fast)")
            
            # 센서 모드 확인
            sensor = fw.get_sensor_mode()
            print(f"Sensor mode: {sensor} (0=off when idle, 1=always on)")
            
        finally:
            fw.disconnect()
    
    print("\n" + "="*50)
    
    # 방법 2: 컨텍스트 매니저 사용 (권장)
    with FW102C(port='COM11') as fw:
        print("\nUsing context manager:")
        device_id = fw.get_id()
        print(f"Device ID: {device_id}")
        
        # 위치 3으로 이동
        fw.set_position(3)
        print("Moving to position 3...")
        time.sleep(1)
        
        current_pos = fw.get_position()
        print(f"Current position: {current_pos}")


if __name__ == '__main__':
    demo()

