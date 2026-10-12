"""
Complete YOLO Training Workflow for Dot Detection
"""
import os
import sys
from pathlib import Path


def run_data_conversion():
    """Run data conversion from labeling format to YOLO format"""
    print("Step 1: Converting labeling data to YOLO format...")
    
    try:
        from convert_data import YOLODataConverter
        
        converter = YOLODataConverter()
        converted_count, total_dots = converter.convert_all()
        
        if converted_count > 0:
            print(f"✅ Converted {converted_count} files with {total_dots} dots")
            return True
        else:
            print("❌ No data was converted")
            return False
            
    except Exception as e:
        print(f"❌ Data conversion failed: {e}")
        return False


def run_data_splitting():
    """Run data splitting into train/val/test sets"""
    print("\nStep 2: Splitting data into train/val/test sets...")
    
    try:
        from split_data import YOLODataSplitter
        
        splitter = YOLODataSplitter()
        train_count, val_count, test_count = splitter.split_data()
        
        if train_count + val_count + test_count > 0:
            print(f"✅ Split: {train_count} train, {val_count} val, {test_count} test")
            return True
        else:
            print("❌ No data was split")
            return False
            
    except Exception as e:
        print(f"❌ Data splitting failed: {e}")
        return False


def run_training():
    """Run YOLO training"""
    print("\nStep 3: Starting YOLO training...")
    
    try:
        from train_yolo import YOLOTrainer
        
        trainer = YOLOTrainer(
            dataset_yaml="data/dataset_split.yaml",
            model_size="n",  # nano model
            epochs=30,        # Start with fewer epochs
            batch_size=8,     # Smaller batch size
            img_size=640
        )
        
        # Check dependencies
        if not trainer.yolo_available:
            print("❌ ultralytics not installed. Please run: pip install ultralytics")
            return False
        
        # Prepare dataset
        if not trainer.prepare_dataset():
            print("❌ Dataset preparation failed")
            return False
        
        # Initialize model
        if not trainer.initialize_model():
            print("❌ Model initialization failed")
            return False
        
        # Train model
        if trainer.train():
            print("✅ Training completed successfully!")
            
            # Validate model
            trainer.validate()
            
            # Save model
            trainer.save_model()
            
            return True
        else:
            print("❌ Training failed")
            return False
            
    except Exception as e:
        print(f"❌ Training failed: {e}")
        return False


def main():
    """Main workflow function"""
    print("YOLO Custom Training Workflow for Dot Detection")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("data").exists():
        print("❌ Please run this script from the yolo directory")
        return
    
    # Step 1: Convert data
    if not run_data_conversion():
        print("❌ Workflow stopped at data conversion")
        return
    
    # Step 2: Split data
    if not run_data_splitting():
        print("❌ Workflow stopped at data splitting")
        return
    
    # Step 3: Train model
    if not run_training():
        print("❌ Workflow stopped at training")
        return
    
    print("\n🎉 Complete workflow finished successfully!")
    print("Your custom YOLO model is ready for dot detection!")


if __name__ == "__main__":
    main()
