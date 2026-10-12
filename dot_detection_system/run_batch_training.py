"""
일괄 딥러닝 점 검출 학습 실행 파일

이 파일을 실행하면 폴더의 모든 이미지에 대해 일괄로 라벨링합니다.
"""

import os
import sys
from batch_dot_training import batch_process_images

def main():
    """일괄 학습 실행"""
    print("🚀 일괄 딥러닝 점 검출 학습 시작")
    print("=" * 50)
    
    # 설정
    image_dir = r"C:\Pycode\camera_test\imgs"
    template_path = "dot_img.png"
    output_dir = "labeling_data"
    
    # 파일 존재 확인
    if not os.path.exists(image_dir):
        print(f"❌ 이미지 디렉토리가 존재하지 않습니다: {image_dir}")
        return
    
    if not os.path.exists(template_path):
        print(f"❌ 템플릿 파일이 존재하지 않습니다: {template_path}")
        return
    
    print(f"📁 이미지 디렉토리: {image_dir}")
    print(f"🎯 템플릿 파일: {template_path}")
    print(f"💾 출력 디렉토리: {output_dir}")
    
    # 사용자 확인
    response = input(f"\n일괄 처리를 시작하시겠습니까? (y/n): ")
    if response.lower() != 'y':
        print("처리를 취소했습니다.")
        return
    
    # 일괄 처리 실행
    try:
        batch_process_images(image_dir, template_path, output_dir, skip_existing=True)
        print("\n🎉 일괄 처리 완료!")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")

if __name__ == "__main__":
    main()
