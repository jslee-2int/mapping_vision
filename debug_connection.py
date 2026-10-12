"""
FilterWheel102 연결 디버깅 도구
상세한 정보를 출력하여 연결 실패 원인 파악
"""

import os
import sys
import ctypes
import platform

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sub_py'))


def check_com_ports():
    """사용 가능한 모든 COM 포트 확인"""
    print("=" * 60)
    print("1. COM 포트 확인")
    print("=" * 60)
    
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        
        if ports:
            print(f"발견된 COM 포트: {len(ports)}개\n")
            for p in ports:
                print(f"  포트: {p.device}")
                print(f"  설명: {p.description}")
                print(f"  제조사: {p.manufacturer}")
                print(f"  HWID: {p.hwid}")
                print()
            return [p.device for p in ports]
        else:
            print("사용 가능한 COM 포트가 없습니다")
            return []
    except ImportError:
        print("pyserial이 설치되지 않았습니다")
        print("설치: pip install pyserial")
        return []


def test_dll_connection(dll_path, com_port):
    """DLL로 직접 연결 테스트"""
    print("=" * 60)
    print(f"2. DLL 직접 연결 테스트 - {com_port}")
    print("=" * 60)
    
    try:
        # DLL 로드
        print(f"\nDLL 경로: {dll_path}")
        print(f"DLL 존재: {os.path.exists(dll_path)}")
        
        dll = ctypes.CDLL(dll_path)
        print("[O] DLL 로드 성공 (CDLL)")
        
        # Open 함수 설정
        open_func = dll.Open
        open_func.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
        open_func.restype = ctypes.c_int
        print("[O] Open 함수 찾음")
        
        # 여러 설정으로 연결 시도
        configs = [
            (115200, 10, "115200 baud, 10초 timeout"),
            (9600, 10, "9600 baud, 10초 timeout"),
            (115200, 3, "115200 baud, 3초 timeout"),
            (19200, 10, "19200 baud, 10초 timeout"),
        ]
        
        for baud, timeout, desc in configs:
            print(f"\n테스트: {desc}")
            print(f"  COM 포트: {com_port}")
            print(f"  Baud Rate: {baud}")
            print(f"  Timeout: {timeout}초")
            
            com_bytes = com_port.encode('utf-8')
            result = open_func(com_bytes, baud, timeout)
            
            print(f"  결과: {result}")
            
            if result >= 0:
                print(f"  [SUCCESS] 연결 성공! Handle: {result}")
                
                # 추가 정보 가져오기
                try:
                    # GetPositionCount 시도
                    get_pcount = dll.GetPositionCount
                    get_pcount.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
                    get_pcount.restype = ctypes.c_int
                    
                    pcount = ctypes.c_int()
                    ret = get_pcount(result, ctypes.byref(pcount))
                    if ret == 0:
                        print(f"  위치 개수: {pcount.value}")
                    
                    # GetPosition 시도
                    get_pos = dll.GetPosition
                    get_pos.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
                    get_pos.restype = ctypes.c_int
                    
                    pos = ctypes.c_int()
                    ret = get_pos(result, ctypes.byref(pos))
                    if ret == 0:
                        print(f"  현재 위치: {pos.value}")
                    
                    # GetId 시도
                    try:
                        get_id = dll.GetId
                        get_id.argtypes = [ctypes.c_int, ctypes.c_char_p]
                        get_id.restype = ctypes.c_int
                        
                        id_buf = ctypes.create_string_buffer(256)
                        ret = get_id(result, id_buf)
                        if ret == 0:
                            print(f"  장치 ID: {id_buf.value.decode('utf-8', errors='ignore')}")
                    except:
                        pass
                    
                except Exception as e:
                    print(f"  정보 조회 중 오류: {e}")
                
                # Close
                try:
                    close_func = dll.Close
                    close_func.argtypes = [ctypes.c_int]
                    close_func.restype = ctypes.c_int
                    close_func(result)
                    print("  [O] 연결 해제")
                except:
                    pass
                
                return True
            else:
                print(f"  [X] 연결 실패 (에러 코드: {result})")
        
        return False
        
    except Exception as e:
        print(f"[X] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*60)
    print("FilterWheel102 연결 디버깅 도구")
    print("="*60 + "\n")
    
    # Python 아키텍처 확인
    arch = platform.architecture()[0]
    print(f"Python 아키텍처: {arch}")
    print(f"Python 버전: {platform.python_version()}")
    print()
    
    # COM 포트 확인
    available_ports = check_com_ports()
    
    # DLL 경로 설정
    if arch == '64bit':
        dll_name = 'FilterWheel102_win64.dll'
    else:
        dll_name = 'FilterWheel102_win32.dll'
    
    dll_path = os.path.join(os.path.dirname(__file__), 'sub_py', 'msvc', dll_name)
    
    print("\n" + "="*60)
    print("테스트할 COM 포트를 선택하세요")
    print("="*60)
    
    if available_ports:
        print("\n발견된 포트:")
        for i, port in enumerate(available_ports, 1):
            print(f"  {i}. {port}")
        print(f"  0. 직접 입력")
        
        try:
            choice = input("\n선택 (번호 입력): ").strip()
            if choice == '0':
                test_port = input("COM 포트 입력 (예: COM11): ").strip()
            elif choice.isdigit() and 1 <= int(choice) <= len(available_ports):
                test_port = available_ports[int(choice) - 1]
            else:
                print("잘못된 선택입니다. COM11로 테스트합니다.")
                test_port = "COM11"
        except:
            test_port = "COM11"
    else:
        test_port = input("\nCOM 포트를 입력하세요 (예: COM11): ").strip()
        if not test_port:
            test_port = "COM11"
    
    # 연결 테스트
    print()
    success = test_dll_connection(dll_path, test_port)
    
    print("\n" + "="*60)
    if success:
        print("[SUCCESS] 연결 성공! 위의 설정을 코드에 사용하세요.")
    else:
        print("[X] 모든 설정에서 연결 실패")
        print("\n가능한 원인:")
        print("1. COM 포트 번호가 틀림 (장치 관리자에서 확인)")
        print("2. 다른 프로그램이 포트 사용 중 (전용 프로그램 종료)")
        print("3. 드라이버 문제")
        print("4. 장치 전원 또는 연결 문제")
    print("="*60)


if __name__ == "__main__":
    main()

