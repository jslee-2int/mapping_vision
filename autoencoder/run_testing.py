"""
간단한 테스트 실행 스크립트
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test import main

if __name__ == "__main__":
    print("=" * 70)
    print(" " * 20 + "Autoencoder Testing")
    print("=" * 70)
    print("\nThis will evaluate the trained autoencoder on test data.")
    print("Make sure you have trained the model first (run_training.py).")
    print("\nResults will be saved in './test_results/' directory.")
    print("=" * 70)
    print()
    
    try:
        main()
    except FileNotFoundError as e:
        print(f"\n\nError: {e}")
        print("\nPlease train the model first by running:")
        print("  python run_training.py")
    except Exception as e:
        print(f"\n\nError during testing: {e}")
        import traceback
        traceback.print_exc()

