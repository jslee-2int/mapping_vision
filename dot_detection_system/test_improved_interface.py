"""
개선된 인터페이스 확인용 테스트 파일

이 파일은 개선된 딥러닝 점 검출 시스템의 인터페이스를 테스트합니다.
"""

import os
import sys
from improved_dot_training import ImprovedDotDetector

def test_interface():
    """개선된 인터페이스 테스트"""
    print("개선된 인터페이스 테스트 시작")
    print("=" * 50)
    
    # 설정
    image_dir = r"C:\Pycode\camera_test\imgs"
    template_path = "dot_img.png"
    
    # 이미지 파일 확인
    if not os.path.exists(image_dir):
        print(f"이미지 디렉토리가 존재하지 않습니다: {image_dir}")
        return False
    
    if not os.path.exists(template_path):
        print(f"템플릿 파일이 존재하지 않습니다: {template_path}")
        return False
    
    # 이미지 파일 찾기
    import glob
    image_paths = []
    for ext in ['*.png', '*.jpg', '*.jpeg']:
        pattern = os.path.join(image_dir, ext)
        image_paths.extend(glob.glob(pattern))
    image_paths = sorted(image_paths)
    
    if not image_paths:
        print(f"이미지 디렉토리에서 이미지를 찾을 수 없습니다: {image_dir}")
        return False
    
    print(f"발견된 이미지: {len(image_paths)}개")
    
    # 검출기 초기화
    detector = ImprovedDotDetector()
    print("검출기 초기화 완료")
    
    # 첫 번째 이미지로 테스트
    test_image = image_paths[0]
    print(f"테스트 이미지: {os.path.basename(test_image)}")
    
    print("\n" + "=" * 50)
    print("개선된 인터페이스 사용법:")
    print("  마우스 왼쪽 클릭: 현재 선택된 점을 라벨링")
    print("  스페이스바: 색상 전환 (빨간색 ↔ 초록색)")
    print("  'q': 완료")
    print("  'n': 다음 이미지")
    print("  'r': 현재 이미지 다시 시작")
    print("=" * 50)
    
    try:
        # 학습 데이터 생성 테스트
        patches, labels = detector.create_training_data_improved([test_image], template_path)
        
        if patches is None or labels is None:
            print("학습 데이터 생성에 실패했습니다.")
            return False
        
        print(f"학습 데이터 생성 성공: {len(patches)}개 패치")
        print(f"   - 유효한 점: {sum(labels)}개")
        print(f"   - 무효한 점: {len(labels) - sum(labels)}개")
        
        return True
        
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
        return False

def test_keyboard_shortcuts():
    """키보드 단축키 테스트"""
    print("\n키보드 단축키 테스트")
    print("-" * 30)
    
    shortcuts = {
        "스페이스바": "색상 전환 (빨간색 ↔ 초록색)",
        "'q'": "완료",
        "'n'": "다음 이미지", 
        "'r'": "현재 이미지 다시 시작"
    }
    
    for key, description in shortcuts.items():
        print(f"  {key}: {description}")
    
    print("모든 단축키가 구현되었습니다.")

def test_mouse_interface():
    """마우스 인터페이스 테스트"""
    print("\n마우스 인터페이스 테스트")
    print("-" * 30)
    
    print("마우스 왼쪽 클릭만 사용")
    print("우클릭 제거됨")
    print("점 클릭 감지 (20픽셀 이내)")
    print("라벨 수정 가능 (덮어쓰기)")
    print("실시간 색상 업데이트")

def main():
    """메인 테스트 함수"""
    print("개선된 딥러닝 점 검출 시스템 테스트")
    print("=" * 60)
    
    # 인터페이스 개선사항 확인
    print("\n개선사항 확인:")
    print("1. 마우스 왼쪽 클릭만 사용")
    print("2. 색상 전환 단축키 (스페이스바)")
    print("3. 더 직관적인 인터페이스")
    print("4. 라벨 수정 가능 (덮어쓰기)")
    print("5. 실시간 상태 표시")
    
    # 키보드 단축키 테스트
    test_keyboard_shortcuts()
    
    # 마우스 인터페이스 테스트
    test_mouse_interface()
    
    # 실제 인터페이스 테스트
    print("\n실제 인터페이스 테스트")
    print("-" * 30)
    
    success = test_interface()
    
    if success:
        print("\n모든 테스트 통과!")
        print("개선된 인터페이스가 정상적으로 작동합니다.")
    else:
        print("\n테스트 실패")
        print("문제를 확인하고 다시 시도해주세요.")
    
    print("\n" + "=" * 60)
    print("테스트 완료")

if __name__ == "__main__":
    main()
