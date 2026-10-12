"""
라벨링 데이터 확인 유틸리티

저장된 라벨링 데이터를 확인하고 통계를 보여줍니다.
"""

import os
import json
import glob
from datetime import datetime

def check_labeling_data(output_dir="labeling_data"):
    """라벨링 데이터 확인"""
    print("=== 라벨링 데이터 확인 ===")
    
    if not os.path.exists(output_dir):
        print(f"라벨링 데이터 디렉토리가 존재하지 않습니다: {output_dir}")
        return
    
    # JSON 파일 찾기
    json_files = glob.glob(os.path.join(output_dir, "*_labels.json"))
    
    if not json_files:
        print("라벨링 데이터 파일이 없습니다.")
        return
    
    print(f"발견된 라벨링 데이터: {len(json_files)}개")
    
    # 전체 통계
    total_images = len(json_files)
    total_points = 0
    total_valid = 0
    total_invalid = 0
    
    print(f"\n=== 라벨링 데이터 상세 ===")
    
    for json_file in sorted(json_files):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            filename = os.path.basename(data['image_path'])
            points = data['total_points']
            valid = data['valid_points']
            invalid = data['invalid_points']
            
            print(f"📄 {filename}")
            print(f"   총 점: {points}개")
            print(f"   유효한 점: {valid}개")
            print(f"   무효한 점: {invalid}개")
            print(f"   유효 비율: {valid/points*100:.1f}%" if points > 0 else "   유효 비율: 0%")
            print()
            
            total_points += points
            total_valid += valid
            total_invalid += invalid
            
        except Exception as e:
            print(f"❌ {json_file} 파일 읽기 실패: {e}")
    
    # 전체 통계
    print(f"=== 전체 통계 ===")
    print(f"총 이미지: {total_images}개")
    print(f"총 점: {total_points}개")
    print(f"유효한 점: {total_valid}개")
    print(f"무효한 점: {total_invalid}개")
    print(f"전체 유효 비율: {total_valid/total_points*100:.1f}%" if total_points > 0 else "전체 유효 비율: 0%")

def main():
    """메인 함수"""
    check_labeling_data()

if __name__ == "__main__":
    main()
