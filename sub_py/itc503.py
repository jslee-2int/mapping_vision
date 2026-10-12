import pyvisa

# VISA 리소스 매니저 생성
rm = pyvisa.ResourceManager()

# 연결 가능한 GPIB 장비 목록 확인
print(rm.list_resources())  # 예: ('GPIB0::4::INSTR',)

# 장비 연결
itc = rm.open_resource("GPIB0::24::INSTR")  # 주소는 장비에 따라 다를 수 있음
itc.read_termination = '\r'
# 통신 테스트: 식별자 요청 (*IDN?이 안 될 수도 있음, ITC503은 비표준일 수 있음)
# 대부분은 직접적인 명령으로 테스트

# 온도 읽기
# ITC503의 온도 읽기 명령은 일반적으로 'R1' (Channel 1 읽기)
temperature = itc.query("R1")
print("현재 온도:", temperature, "K")
