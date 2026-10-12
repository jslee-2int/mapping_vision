"""
낮은 신뢰도 임계값으로 모델 테스트

신뢰도 임계값을 낮춰서 더 많은 점이 통과하도록 테스트합니다.
"""

import os
import sys
from batch_model_test import batch_test_model

def main():
    """낮은 임계값으로 모델 테스트"""
    print("낮은 신뢰도 임계값으로 모델 테스트")
    print("=" * 50)
    
    # 설정
    image_dir = r"C:\Pycode\camera_test\imgs"
    template_path = "dot_img.png"
    model_path = "batch_dot_detection_model.pth"
    output_dir = "test_results_low_threshold"
    confidence_threshold = 0.5  # 낮은 임계값
    
    print(f"이미지 디렉토리: {image_dir}")
    print(f"템플릿 파일: {template_path}")
    print(f"모델 파일: {model_path}")
    print(f"출력 디렉토리: {output_dir}")
    print(f"신뢰도 임계값: {confidence_threshold} (낮은 임계값)")
    
    # 일괄 테스트 실행
    try:
        batch_test_model(image_dir, template_path, model_path, confidence_threshold, output_dir)
        print("\n낮은 임계값 테스트 완료!")
    except Exception as e:
        print(f"\n오류 발생: {e}")

if __name__ == "__main__":
    main()
