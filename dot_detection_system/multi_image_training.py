"""
여러 이미지에서 딥러닝 모델 학습하기

이 스크립트는 여러 이미지에서 점 검출 모델을 학습시킵니다.
"""

import os
import glob
from deep_learning_dot_detection import DeepLearningDotDetector

def find_training_images(image_dir, extensions=['*.png', '*.jpg', '*.jpeg']):
    """학습용 이미지 파일들을 찾습니다."""
    image_paths = []
    for ext in extensions:
        pattern = os.path.join(image_dir, ext)
        image_paths.extend(glob.glob(pattern))
    return sorted(image_paths)

def main():
    """메인 함수"""
    print("=== 여러 이미지에서 딥러닝 모델 학습 ===")
    
    # 설정
    image_dir = r"C:\Pycode\camera_test\imgs"  # 이미지 디렉토리
    template_path = "dot_img.png"
    model_path = "dot_detection_model.pth"
    
    # 학습용 이미지 찾기
    image_paths = find_training_images(image_dir)
    
    if not image_paths:
        print(f"이미지 디렉토리에서 이미지를 찾을 수 없습니다: {image_dir}")
        print("지원 형식: .png, .jpg, .jpeg")
        return
    
    print(f"발견된 이미지: {len(image_paths)}개")
    for i, path in enumerate(image_paths):
        print(f"  {i+1}. {os.path.basename(path)}")
    
    # 사용자 확인 (자동 진행)
    print(f"\n{len(image_paths)}개 이미지로 학습을 시작합니다...")
    # response = input(f"\n{len(image_paths)}개 이미지로 학습을 시작하시겠습니까? (y/n): ")
    # if response.lower() != 'y':
    #     print("학습을 취소했습니다.")
    #     return
    
    # 검출기 초기화
    detector = DeepLearningDotDetector()
    
    # 학습 데이터 생성 (여러 이미지)
    print(f"\n=== {len(image_paths)}개 이미지에서 학습 데이터 생성 ===")
    patches, labels = detector.create_training_data(image_paths, template_path)
    
    if patches is None or labels is None:
        print("학습 데이터 생성에 실패했습니다.")
        return
    
    print(f"\n총 학습 데이터: {len(patches)}개 패치")
    print(f"유효한 점: {sum(labels)}개")
    print(f"무효한 점: {len(labels) - sum(labels)}개")
    
    # 모델 학습
    print(f"\n=== 모델 학습 시작 ===")
    detector.train_model(patches, labels, epochs=100, batch_size=32)
    
    # 모델 저장
    detector.save_model(model_path)
    
    print(f"\n=== 학습 완료! ===")
    print(f"모델이 저장되었습니다: {model_path}")
    print("이제 딥러닝 필터링을 사용할 수 있습니다.")

if __name__ == "__main__":
    main()
