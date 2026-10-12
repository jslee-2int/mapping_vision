"""
성능 개선을 위한 스크립트
다양한 방법으로 모델 성능을 개선
"""

import os
import sys

print("=" * 70)
print("Autoencoder 성능 개선 가이드")
print("=" * 70)

print("\n현재 문제:")
print("  - 정확도: 36%")
print("  - Valid/Invalid Error 차이가 너무 작음 (0.000011)")
print("  - False Positive가 너무 많음 (83.8%)")

print("\n" + "=" * 70)
print("해결 방법 (우선순위 순)")
print("=" * 70)

print("\n[방법 1] 더 긴 학습 시간 ⭐⭐⭐⭐⭐")
print("  현재: 50 epochs 정도")
print("  권장: 200-300 epochs")
print("  실행: train.py에서 num_epochs=200으로 변경")
print()
print("  # train.py 수정:")
print("  CONFIG = {")
print("      'num_epochs': 200,  # 50 -> 200으로 증가")
print("      'learning_rate': 5e-4,  # 조금 낮춤")
print("      ...") 
print("  }")

print("\n[방법 2] 학습률 조정 ⭐⭐⭐⭐")
print("  현재: 1e-3")
print("  권장: 5e-4 (절반으로 줄임)")
print("  이유: 더 안정적인 학습")

print("\n[방법 3] Latent Dimension 증가 ⭐⭐⭐⭐")
print("  현재: 128")
print("  권장: 256 또는 512")
print("  이유: 더 많은 특징을 학습할 수 있음")
print()
print("  CONFIG = {")
print("      'latent_dim': 256,  # 128 -> 256으로 증가")
print("      ...") 
print("  }")

print("\n[방법 4] 데이터 증강 강화 ⭐⭐⭐")
print("  현재 증강: 기본")
print("  권장: 더 강한 증강")
print()
print("  dataset.py에서 augment transform 수정:")
print("  transforms.Compose([")
print("      transforms.ToPILImage(),")
print("      transforms.RandomHorizontalFlip(p=0.5),")
print("      transforms.RandomVerticalFlip(p=0.5),")
print("      transforms.RandomRotation(degrees=30),  # 15 -> 30")
print("      transforms.ColorJitter(brightness=0.3, contrast=0.3),  # 0.2 -> 0.3")
print("      transforms.RandomAffine(degrees=0, translate=(0.1, 0.1)),  # 추가")
print("      transforms.ToTensor(),")
print("  ])")

print("\n[방법 5] 배치 크기 조정 ⭐⭐⭐")
print("  현재: 64")
print("  권장: 32 (더 안정적인 학습)")
print()
print("  CONFIG = {")
print("      'batch_size': 32,  # 64 -> 32로 감소")
print("      ...") 
print("  }")

print("\n[방법 6] Loss Function 변경 ⭐⭐⭐")
print("  현재: MSE Loss")
print("  권장: MSE + Perceptual Loss 또는 SSIM Loss")
print("  이유: 더 의미있는 특징 학습")

print("\n[방법 7] 패치 크기 증가 ⭐⭐")
print("  현재: 32x32")
print("  권장: 64x64")
print("  이유: 더 많은 컨텍스트 정보")
print()
print("  CONFIG = {")
print("      'patch_size': 64,  # 32 -> 64로 증가")
print("      ...") 
print("  }")

print("\n" + "=" * 70)
print("빠른 실행 가이드")
print("=" * 70)

print("\n1단계: train.py 설정 변경")
print("   파일: autoencoder/train.py")
print("   변경할 부분:")
print("   CONFIG = {")
print("       'num_epochs': 200,        # 더 긴 학습")
print("       'learning_rate': 5e-4,    # 더 낮은 학습률")
print("       'latent_dim': 256,        # 더 큰 latent space")
print("       'batch_size': 32,         # 더 작은 배치")
print("       'augment': True,")
print("       'early_stopping_patience': 30,  # 더 긴 patience")
print("   }")

print("\n2단계: 학습 실행")
print("   python autoencoder/run_training.py")

print("\n3단계: 테스트")
print("   python autoencoder/run_testing.py")

print("\n" + "=" * 70)
print("예상 결과")
print("=" * 70)
print("  - 학습 시간: 30분~1시간 (GPU 사용 시)")
print("  - 예상 정확도: 70~85%")
print("  - Error 차이: 0.001 이상")

print("\n" + "=" * 70)
print("자동 설정 파일 생성 중...")
print("=" * 70)

# Create improved config
improved_config_content = '''"""
개선된 학습 설정
"""

IMPROVED_CONFIG = {
    'label_dir': r'C:\\Pycode\\camera_test\\dot_detection_system\\labeling_data',
    'model_type': 'improved',
    'patch_size': 64,          # 32 -> 64로 증가
    'latent_dim': 256,         # 128 -> 256로 증가
    'batch_size': 32,          # 64 -> 32로 감소
    'num_epochs': 200,         # 100 -> 200으로 증가
    'learning_rate': 5e-4,     # 1e-3 -> 5e-4로 감소
    'val_split': 0.2,
    'augment': True,
    'early_stopping_patience': 30,  # 15 -> 30으로 증가
    'device': 'cuda',  # if available
    'num_workers': 0,
}
'''

with open('improved_config.py', 'w', encoding='utf-8') as f:
    f.write(improved_config_content)

print("✓ improved_config.py 생성 완료!")
print()
print("이 설정을 사용하려면:")
print("  1. train.py를 열어서")
print("  2. CONFIG를 improved_config.py의 IMPROVED_CONFIG로 교체")
print("  3. 또는 아래 명령으로 직접 학습:")
print()
print("     python autoencoder/train_improved.py")

