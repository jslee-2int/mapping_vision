"""
간단한 학습 실행 스크립트
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from train import main

if __name__ == "__main__":
    print("=" * 70)
    print(" " * 20 + "Autoencoder Training")
    print("=" * 70)
    print("\nThis will train an autoencoder to classify valid/invalid dots.")
    print("The model will be trained only on valid dots (anomaly detection).")
    print("\nTraining will take some time depending on your hardware.")
    print("Progress will be saved in './checkpoints/' directory.")
    print("\nPress Ctrl+C to stop training at any time.")
    print("=" * 70)
    print()
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user.")
    except Exception as e:
        print(f"\n\nError during training: {e}")
        import traceback
        traceback.print_exc()

