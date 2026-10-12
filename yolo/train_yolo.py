"""
YOLO Custom Training Script for Dot Detection
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any
import torch


class YOLOTrainer:
    """
    YOLO custom training class for dot detection
    """
    
    def __init__(self, 
                 dataset_yaml: str = "data/dataset_split.yaml",
                 model_size: str = "m",  # n, s, m, l, x
                 epochs: int = 100,
                 batch_size: int = 16,
                 img_size: int = 640,
                 device: str = None):
        """
        Initialize YOLO trainer
        
        Args:
            dataset_yaml: Path to dataset YAML file
            model_size: YOLO model size (n, s, m, l, x)
            epochs: Number of training epochs
            batch_size: Batch size for training
            img_size: Image size for training
            device: Device to use ('cpu', 'cuda', or None for auto)
        """
        self.dataset_yaml = dataset_yaml
        self.model_size = model_size
        self.epochs = epochs
        self.batch_size = batch_size
        self.img_size = img_size
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        
        self.model = None
        self.results = None
        
        # Check if ultralytics is available
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if required dependencies are available"""
        try:
            from ultralytics import YOLO
            self.yolo_available = True
        except ImportError:
            print("❌ ultralytics not installed. Please install: pip install ultralytics")
            self.yolo_available = False
    
    def prepare_dataset(self):
        """
        Prepare dataset for training
        """
        print("=== Preparing Dataset ===")
        
        # Check if dataset YAML exists
        if not Path(self.dataset_yaml).exists():
            print(f"❌ Dataset YAML not found: {self.dataset_yaml}")
            print("Please run convert_data.py and split_data.py first")
            return False
        
        # Load and validate dataset YAML
        with open(self.dataset_yaml, 'r') as f:
            dataset_config = yaml.safe_load(f)
        
        print(f"✅ Dataset config loaded: {self.dataset_yaml}")
        print(f"   Classes: {dataset_config.get('nc', 'unknown')}")
        print(f"   Class names: {dataset_config.get('names', 'unknown')}")
        
        # Check if data directories exist
        data_path = Path(dataset_config['path'])
        train_path = data_path / dataset_config['train']
        val_path = data_path / dataset_config['val']
        
        if not train_path.exists():
            print(f"❌ Training data not found: {train_path}")
            return False
        
        if not val_path.exists():
            print(f"❌ Validation data not found: {val_path}")
            return False
        
        train_images = len(list(train_path.glob("*.png")))
        val_images = len(list(val_path.glob("*.png")))
        
        print(f"✅ Found {train_images} training images")
        print(f"✅ Found {val_images} validation images")
        
        return True
    
    def initialize_model(self):
        """
        Initialize YOLO model
        """
        if not self.yolo_available:
            return False
        
        try:
            from ultralytics import YOLO
            
            # Load pre-trained model
            model_name = f"yolov8{self.model_size}.pt"
            print(f"Loading pre-trained model: {model_name}")
            
            self.model = YOLO(model_name)
            print(f"✅ Model initialized: {model_name}")
            print(f"   Device: {self.device}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize model: {e}")
            return False
    
    def train(self, **kwargs):
        """
        Train YOLO model
        
        Args:
            **kwargs: Additional training parameters
        """
        if not self.yolo_available or self.model is None:
            print("❌ Model not initialized")
            return False
        
        print("=== Starting YOLO Training ===")
        print(f"Dataset: {self.dataset_yaml}")
        print(f"Epochs: {self.epochs}")
        print(f"Batch size: {self.batch_size}")
        print(f"Image size: {self.img_size}")
        print(f"Device: {self.device}")
        
        try:
            # Training parameters
            train_params = {
                'data': self.dataset_yaml,
                'epochs': self.epochs,
                'batch': self.batch_size,
                'imgsz': self.img_size,
                'device': self.device,
                'project': 'results',
                'name': 'dot_detection',
                'save': True,
                'save_period': 10,  # Save checkpoint every 10 epochs
                'patience': 20,     # Early stopping patience
                'verbose': True,
                **kwargs
            }
            
            print(f"Training parameters: {train_params}")
            
            # Start training
            self.results = self.model.train(**train_params)
            
            print("✅ Training completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Training failed: {e}")
            return False
    
    def validate(self):
        """
        Validate trained model
        """
        if not self.yolo_available or self.model is None:
            print("❌ Model not initialized")
            return False
        
        print("=== Validating Model ===")
        
        try:
            # Run validation
            val_results = self.model.val()
            
            print("✅ Validation completed!")
            print(f"mAP50: {val_results.box.map50:.4f}")
            print(f"mAP50-95: {val_results.box.map:.4f}")
            
            return True
            
        except Exception as e:
            print(f"❌ Validation failed: {e}")
            return False
    
    def save_model(self, output_path: str = "models/dot_detection.pt"):
        """
        Save trained model
        
        Args:
            output_path: Path to save the model
        """
        if self.model is None:
            print("❌ No model to save")
            return False
        
        try:
            # Create output directory
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Save model
            self.model.save(output_path)
            print(f"✅ Model saved to: {output_path}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to save model: {e}")
            return False
    
    def get_training_summary(self) -> Dict[str, Any]:
        """
        Get training summary
        
        Returns:
            Dictionary with training summary
        """
        if self.results is None:
            return {"status": "No training results available"}
        
        return {
            "status": "Training completed",
            "epochs": self.epochs,
            "model_size": self.model_size,
            "device": self.device,
            "results_path": "results/dot_detection"
        }


def main():
    """Main training function"""
    print("YOLO Custom Training for Dot Detection")
    print("=" * 50)
    
    # Initialize trainer
    trainer = YOLOTrainer(
        dataset_yaml="data/dataset_split.yaml",
        model_size="m",  # nano model (fastest)
        epochs=50,       # Start with fewer epochs
        batch_size=8,     # Smaller batch size
        img_size=640
    )
    
    # Check dependencies
    if not trainer.yolo_available:
        print("Please install ultralytics: pip install ultralytics")
        return
    
    # Prepare dataset
    if not trainer.prepare_dataset():
        print("❌ Dataset preparation failed")
        return
    
    # Initialize model
    if not trainer.initialize_model():
        print("❌ Model initialization failed")
        return
    
    # Train model
    if trainer.train():
        print("🎉 Training completed successfully!")
        
        # Validate model
        trainer.validate()
        
        # Save model
        trainer.save_model()
        
        # Print summary
        summary = trainer.get_training_summary()
        print(f"\n=== Training Summary ===")
        for key, value in summary.items():
            print(f"{key}: {value}")
    else:
        print("❌ Training failed")


if __name__ == "__main__":
    main()
