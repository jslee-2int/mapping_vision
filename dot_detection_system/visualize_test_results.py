"""
테스트 결과 시각화

학습된 모델의 테스트 결과를 시각화하고 분석합니다.
"""

import os
import json
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

def load_test_results(results_file="test_results_low_threshold/test_results.json"):
    """테스트 결과 불러오기"""
    if not os.path.exists(results_file):
        print(f"테스트 결과 파일이 존재하지 않습니다: {results_file}")
        return None
    
    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"테스트 결과 불러오기 성공: {results_file}")
        return data
    except Exception as e:
        print(f"테스트 결과 불러오기 실패: {e}")
        return None

def plot_test_statistics(data, output_dir="test_results"):
    """테스트 통계 시각화"""
    if not data:
        return
    
    results = data['results']
    
    # 데이터 추출 (간단한 통계만)
    image_names = [os.path.basename(r['image_path']) for r in results]
    initial_dots = [int(r['initial_dots']) for r in results]
    filtered_dots = [int(r['filtered_dots']) for r in results]
    valid_dots = [int(r['valid_dots']) for r in results]
    invalid_dots = [int(r['invalid_dots']) for r in results]
    confidences = [float(r['confidence_avg']) for r in results]
    filter_ratios = [float(r['filter_ratio']) for r in results]
    
    # 그래프 생성
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('딥러닝 모델 테스트 결과 분석', fontsize=16)
    
    # 1. 점 개수 비교
    x = np.arange(len(image_names))
    width = 0.25
    
    axes[0, 0].bar(x - width, initial_dots, width, label='초기 점', alpha=0.8)
    axes[0, 0].bar(x, filtered_dots, width, label='필터링된 점', alpha=0.8)
    axes[0, 0].bar(x + width, valid_dots, width, label='유효한 점', alpha=0.8)
    
    axes[0, 0].set_xlabel('이미지')
    axes[0, 0].set_ylabel('점 개수')
    axes[0, 0].set_title('점 개수 비교')
    axes[0, 0].legend()
    axes[0, 0].tick_params(axis='x', rotation=45)
    
    # 2. 신뢰도 분포
    axes[0, 1].hist(confidences, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
    axes[0, 1].set_xlabel('평균 신뢰도')
    axes[0, 1].set_ylabel('빈도')
    axes[0, 1].set_title('신뢰도 분포')
    axes[0, 1].axvline(np.mean(confidences), color='red', linestyle='--', 
                      label=f'평균: {np.mean(confidences):.3f}')
    axes[0, 1].legend()
    
    # 3. 필터링 비율
    axes[1, 0].bar(range(len(image_names)), filter_ratios, alpha=0.7, color='lightgreen')
    axes[1, 0].set_xlabel('이미지')
    axes[1, 0].set_ylabel('필터링 비율 (%)')
    axes[1, 0].set_title('필터링 비율')
    axes[1, 0].tick_params(axis='x', rotation=45)
    axes[1, 0].axhline(np.mean(filter_ratios), color='red', linestyle='--', 
                      label=f'평균: {np.mean(filter_ratios):.1f}%')
    axes[1, 0].legend()
    
    # 4. 유효/무효 점 비율
    total_valid = sum(valid_dots)
    total_invalid = sum(invalid_dots)
    
    labels = ['유효한 점', '무효한 점']
    sizes = [total_valid, total_invalid]
    colors = ['lightgreen', 'lightcoral']
    
    axes[1, 1].pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    axes[1, 1].set_title('전체 점 분류 비율')
    
    plt.tight_layout()
    
    # 그래프 저장
    output_file = os.path.join(output_dir, "test_analysis.png")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"📊 분석 그래프 저장: {output_file}")
    
    plt.show()

def print_detailed_statistics(data):
    """상세 통계 출력"""
    if not data:
        return
    
    results = data['results']
    
    print("\n=== 상세 테스트 결과 ===")
    print(f"테스트된 이미지: {data['total_images']}개")
    print(f"총 초기 점: {data['total_initial_dots']}개")
    print(f"총 필터링된 점: {data['total_filtered_dots']}개")
    print(f"총 유효한 점: {data['total_valid_dots']}개")
    print(f"총 무효한 점: {data['total_invalid_dots']}개")
    print(f"평균 신뢰도: {data['avg_confidence']:.3f}")
    print(f"평균 필터링 비율: {data['avg_filter_ratio']:.1f}%")
    
    print(f"\n=== 이미지별 상세 결과 ===")
    for i, result in enumerate(results):
        filename = os.path.basename(result['image_path'])
        print(f"{i+1:2d}. {filename}")
        print(f"    초기 점: {result['initial_dots']}개")
        print(f"    필터링된 점: {result['filtered_dots']}개")
        print(f"    유효한 점: {result['valid_dots']}개")
        print(f"    무효한 점: {result['invalid_dots']}개")
        print(f"    신뢰도: {result['confidence_avg']:.3f}")
        print(f"    필터링 비율: {result['filter_ratio']:.1f}%")
        print()

def main():
    """메인 함수"""
    print("테스트 결과 시각화 및 분석")
    print("=" * 50)
    
    # 테스트 결과 파일 경로
    results_file = "test_results_low_threshold/test_results.json"
    
    # 결과 불러오기
    data = load_test_results(results_file)
    if not data:
        return
    
    # 상세 통계 출력
    print_detailed_statistics(data)
    
    # 시각화
    try:
        plot_test_statistics(data)
        print("시각화 완료!")
    except Exception as e:
        print(f"시각화 중 오류 발생: {e}")
        print("matplotlib이 설치되어 있는지 확인해주세요.")

if __name__ == "__main__":
    main()
