"""
학습된 모델 테스트 실행 파일

이 파일을 실행하면 학습된 모델을 불러와서 
폴더의 모든 이미지에 대해 일괄 테스트를 수행합니다.
"""

import os
import sys
from batch_model_test import batch_test_model

def main():
    """모델 테스트 실행"""
    print("학습된 모델 일괄 테스트 시작")
    print("=" * 50)
    
    # 설정
    image_dir = r"C:\Pycode\camera_test\imgs"
    template_path = "dot_img.png"
    model_path = "batch_dot_detection_model.pth"
    output_dir = "test_results"
    confidence_threshold = 0.8
    
    # 파일 존재 확인
    if not os.path.exists(image_dir):
        print(f"이미지 디렉토리가 존재하지 않습니다: {image_dir}")
        return
    
    if not os.path.exists(template_path):
        print(f"템플릿 파일이 존재하지 않습니다: {template_path}")
        return
    
    if not os.path.exists(model_path):
        print(f"모델 파일이 존재하지 않습니다: {model_path}")
        print("먼저 모델을 학습시켜주세요.")
        return
    
    print(f"이미지 디렉토리: {image_dir}")
    print(f"템플릿 파일: {template_path}")
    print(f"모델 파일: {model_path}")
    print(f"출력 디렉토리: {output_dir}")
    print(f"신뢰도 임계값: {confidence_threshold}")
    
    # 자동 진행
    print(f"\n일괄 테스트를 시작합니다...")
    
    # 일괄 테스트 실행
    try:
        batch_test_model(image_dir, template_path, model_path, confidence_threshold, output_dir)
        print("\n일괄 테스트 완료!")
    except Exception as e:
        print(f"\n오류 발생: {e}")

if __name__ == "__main__":
    main()
