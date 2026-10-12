"""
실시간 딥러닝 점 검출 데모 실행 파일

pth 모델을 불러와서 특정 폴더의 이미지들에 실시간으로 적용하고
오버레이로 결과를 보여주는 데모를 실행합니다.
"""

import os
import sys
from realtime_detection_demo import RealtimeDetectionDemo

def main():
    """실시간 데모 실행"""
    print("실시간 딥러닝 점 검출 데모")
    print("=" * 50)
    
    # 설정
    model_path = "batch_dot_detection_model.pth"
    image_dir = r"C:\Pycode\camera_test\imgs"
    template_path = "dot_img.png"
    confidence_threshold = 0.5
    
    # 파일 존재 확인
    if not os.path.exists(model_path):
        print(f"모델 파일이 존재하지 않습니다: {model_path}")
        print("먼저 모델을 학습시켜주세요.")
        return
    
    if not os.path.exists(image_dir):
        print(f"이미지 디렉토리가 존재하지 않습니다: {image_dir}")
        return
    
    if not os.path.exists(template_path):
        print(f"템플릿 파일이 존재하지 않습니다: {template_path}")
        return
    
    print(f"모델 파일: {model_path}")
    print(f"이미지 디렉토리: {image_dir}")
    print(f"템플릿 파일: {template_path}")
    print(f"신뢰도 임계값: {confidence_threshold}")
    
    # 데모 실행
    try:
        demo = RealtimeDetectionDemo(model_path, image_dir, template_path, confidence_threshold)
        demo.run_demo()
        print("\n데모가 종료되었습니다.")
    except Exception as e:
        print(f"\n오류 발생: {e}")

if __name__ == "__main__":
    main()
