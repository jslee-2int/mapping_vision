"""
추론 데모 실행 스크립트
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from inference import demo

if __name__ == "__main__":
    print("=" * 70)
    print(" " * 20 + "Autoencoder Inference Demo")
    print("=" * 70)
    print("\nThis demo will show how to use the trained model for inference.")
    print("Make sure you have trained and tested the model first.")
    print("=" * 70)
    print()
    
    try:
        demo()
    except FileNotFoundError as e:
        print(f"\n\nError: {e}")
        print("\nPlease train the model first by running:")
        print("  python run_training.py")
    except Exception as e:
        print(f"\n\nError during inference: {e}")
        import traceback
        traceback.print_exc()

