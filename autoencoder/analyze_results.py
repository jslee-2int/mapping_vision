"""테스트 결과 분석"""
import json
import numpy as np
import sys
import io

# UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load results
with open('test_results/detailed_results.json', 'r') as f:
    data = json.load(f)

print("=" * 70)
print("테스트 결과 분석")
print("=" * 70)

print(f"\n전체 통계:")
print(f"  Total samples: {data['total_samples']}")
print(f"  Valid (GT): {data['valid_samples']}")
print(f"  Invalid (GT): {data['invalid_samples']}")
print(f"  Accuracy: {data['accuracy']:.2%}")
print(f"  Threshold: {data['threshold']:.6f}")

# Confusion matrix
samples = data['samples']
tp = sum(1 for s in samples if s['ground_truth'] == 1 and s['prediction'] == 1)
fp = sum(1 for s in samples if s['ground_truth'] == 0 and s['prediction'] == 1)
tn = sum(1 for s in samples if s['ground_truth'] == 0 and s['prediction'] == 0)
fn = sum(1 for s in samples if s['ground_truth'] == 1 and s['prediction'] == 0)

print(f"\nConfusion Matrix:")
print(f"                Predicted")
print(f"              Invalid  Valid")
print(f"Actual Invalid  {tn:6d}  {fp:5d}")
print(f"       Valid    {fn:6d}  {tp:5d}")

# Metrics
valid_precision = tp / (tp + fp) if (tp + fp) > 0 else 0
valid_recall = tp / (tp + fn) if (tp + fn) > 0 else 0
valid_f1 = 2 * valid_precision * valid_recall / (valid_precision + valid_recall) if (valid_precision + valid_recall) > 0 else 0

invalid_precision = tn / (tn + fn) if (tn + fn) > 0 else 0
invalid_recall = tn / (tn + fp) if (tn + fp) > 0 else 0
invalid_f1 = 2 * invalid_precision * invalid_recall / (invalid_precision + invalid_recall) if (invalid_precision + invalid_recall) > 0 else 0

print(f"\nValid 클래스:")
print(f"  Precision: {valid_precision:.2%}")
print(f"  Recall: {valid_recall:.2%}")
print(f"  F1-Score: {valid_f1:.2%}")

print(f"\nInvalid 클래스:")
print(f"  Precision: {invalid_precision:.2%}")
print(f"  Recall: {invalid_recall:.2%}")
print(f"  F1-Score: {invalid_f1:.2%}")

# Error analysis
valid_errors = [s['reconstruction_error'] for s in samples if s['ground_truth'] == 1]
invalid_errors = [s['reconstruction_error'] for s in samples if s['ground_truth'] == 0]

print(f"\nReconstruction Error 분석:")
print(f"  Valid 점 평균 error: {np.mean(valid_errors):.6f} (std: {np.std(valid_errors):.6f})")
print(f"  Invalid 점 평균 error: {np.mean(invalid_errors):.6f} (std: {np.std(invalid_errors):.6f})")
print(f"  Error 차이 (Invalid - Valid): {np.mean(invalid_errors) - np.mean(valid_errors):.6f}")

# 문제 진단
print(f"\n" + "=" * 70)
print("문제 진단:")
print("=" * 70)

if np.mean(invalid_errors) - np.mean(valid_errors) < 0.001:
    print("[!] 문제 1: Valid와 Invalid의 error 차이가 너무 작습니다!")
    print("    -> Autoencoder가 두 클래스를 구분하지 못하고 있습니다.")
    print("    -> 해결: 모델 재학습, 더 많은 데이터, 다른 아키텍처 시도")

if data['threshold'] < 0.001:
    print("[!] 문제 2: Threshold가 너무 낮습니다!")
    print("    -> 대부분의 점이 Valid로 예측됩니다.")
    print(f"    -> 현재 threshold: {data['threshold']:.6f}")

if fp > tn:
    print("[!] 문제 3: False Positive가 너무 많습니다!")
    print(f"    -> Invalid 점 중 {fp/(fp+tn):.1%}를 Valid로 잘못 예측")
    print("    -> Threshold를 높여야 합니다.")

if fn > tp:
    print("[!] 문제 4: False Negative가 너무 많습니다!")
    print(f"    -> Valid 점 중 {fn/(fn+tp):.1%}를 Invalid로 잘못 예측")

# 권장 사항
print(f"\n" + "=" * 70)
print("권장 해결 방법:")
print("=" * 70)
print("1. Threshold 수동 조정 시도")
print("2. 더 긴 학습 (더 많은 에폭)")
print("3. 학습 데이터 증강")
print("4. Improved 모델 사용 (skip connections)")
print("5. Latent dimension 조정")
print("6. 패치 크기 변경")

