"""
검출 결과 시각화 실행 파일

학습된 모델의 검출 결과를 이미지 위에 박스로 표시하여 시각화합니다.
"""

import os
import sys
from visualize_detection_results import visualize_all_detections, create_summary_visualization, load_test_results

def main():
    """검출 결과 시각화 실행"""
    print("검출 결과 시각화 시작")
    print("=" * 50)
    
    # 테스트 결과 파일 경로
    results_file = "test_results_low_threshold/test_results.json"
    output_dir = "detection_visualization"
    
    # 파일 존재 확인
    if not os.path.exists(results_file):
        print(f"테스트 결과 파일이 존재하지 않습니다: {results_file}")
        print("먼저 모델 테스트를 실행해주세요.")
        return
    
    print(f"결과 파일: {results_file}")
    print(f"출력 디렉토리: {output_dir}")
    
    # 결과 불러오기
    data = load_test_results(results_file)
    if not data:
        return
    
    # 시각화 실행
    try:
        # 모든 이미지 시각화
        visualize_all_detections(data, output_dir)
        
        # 요약 시각화
        create_summary_visualization(data, output_dir)
        
        print("\n검출 결과 시각화 완료!")
        print(f"결과가 저장되었습니다: {output_dir}/")
        
    except Exception as e:
        print(f"\n오류 발생: {e}")

if __name__ == "__main__":
    main()
