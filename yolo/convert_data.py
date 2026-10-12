"""
Convert labeling data to YOLO format
"""
import json
import os
import shutil
from pathlib import Path
import cv2
import numpy as np


class YOLODataConverter:
    """
    Convert dot detection labeling data to YOLO format
    """
    
    def __init__(self, 
                 source_images_dir: str = "../imgs",
                 source_labels_dir: str = "../dot_detection_system/labeling_data",
                 output_images_dir: str = "data/images",
                 output_labels_dir: str = "data/labels"):
        """
        Initialize converter
        
        Args:
            source_images_dir: Source images directory
            source_labels_dir: Source labels directory  
            output_images_dir: Output images directory
            output_labels_dir: Output labels directory
        """
        self.source_images_dir = Path(source_images_dir)
        self.source_labels_dir = Path(source_labels_dir)
        self.output_images_dir = Path(output_images_dir)
        self.output_labels_dir = Path(output_labels_dir)
        
        # Create output directories
        self.output_images_dir.mkdir(parents=True, exist_ok=True)
        self.output_labels_dir.mkdir(parents=True, exist_ok=True)
        
        # Class mapping (0: invalid, 1: valid dot)
        self.class_mapping = {
            0: 0,  # invalid -> background (not used in YOLO)
            1: 0   # valid dot -> class 0 (dot)
        }
    
    def convert_single_file(self, image_name: str):
        """
        Convert single image and label file
        
        Args:
            image_name: Name of the image file (without extension)
        """
        # Paths
        source_image_path = self.source_images_dir / f"{image_name}.png"
        source_label_path = self.source_labels_dir / f"{image_name}_labels.json"
        
        if not source_image_path.exists():
            print(f"❌ Image not found: {source_image_path}")
            return False
            
        if not source_label_path.exists():
            print(f"❌ Label not found: {source_label_path}")
            return False
        
        # Load image to get dimensions
        image = cv2.imread(str(source_image_path))
        if image is None:
            print(f"❌ Failed to load image: {source_image_path}")
            return False
            
        img_height, img_width = image.shape[:2]
        
        # Load labels
        with open(source_label_path, 'r') as f:
            label_data = json.load(f)
        
        # Convert to YOLO format
        yolo_labels = []
        for point in label_data['points']:
            if point['status'] == 'valid' and point['label'] == 1:
                # Convert to YOLO format (normalized coordinates)
                x_center = point['x'] / img_width
                y_center = point['y'] / img_height
                
                # YOLO format: class_id x_center y_center width height
                # For dots, we'll use a small bounding box (e.g., 0.02 x 0.02)
                width = 0.02
                height = 0.02
                
                yolo_labels.append(f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")
        
        # Save YOLO label file
        output_label_path = self.output_labels_dir / f"{image_name}.txt"
        with open(output_label_path, 'w') as f:
            f.write('\n'.join(yolo_labels))
        
        # Copy image to output directory
        output_image_path = self.output_images_dir / f"{image_name}.png"
        shutil.copy2(source_image_path, output_image_path)
        
        print(f"Converted: {image_name} ({len(yolo_labels)} valid dots)")
        return True
    
    def convert_all(self):
        """
        Convert all available data
        """
        print("=== Converting labeling data to YOLO format ===")
        
        # Get all available image files
        image_files = list(self.source_images_dir.glob("*.png"))
        label_files = list(self.source_labels_dir.glob("*_labels.json"))
        
        print(f"Found {len(image_files)} images and {len(label_files)} label files")
        
        converted_count = 0
        total_dots = 0
        
        for image_path in image_files:
            image_name = image_path.stem
            if self.convert_single_file(image_name):
                converted_count += 1
                
                # Count dots in this file
                label_path = self.source_labels_dir / f"{image_name}_labels.json"
                if label_path.exists():
                    with open(label_path, 'r') as f:
                        label_data = json.load(f)
                    valid_dots = sum(1 for p in label_data['points'] if p['status'] == 'valid' and p['label'] == 1)
                    total_dots += valid_dots
        
        print(f"\n=== Conversion Summary ===")
        print(f"Converted {converted_count} files")
        print(f"Total valid dots: {total_dots}")
        print(f"Images saved to: {self.output_images_dir}")
        print(f"Labels saved to: {self.output_labels_dir}")
        
        return converted_count, total_dots
    
    def create_dataset_yaml(self, output_path: str = "data/dataset.yaml"):
        """
        Create dataset.yaml file for YOLO training
        
        Args:
            output_path: Path to save dataset.yaml
        """
        yaml_content = f"""# Dot Detection Dataset
path: {os.path.abspath('data')}  # dataset root dir
train: images  # train images (relative to 'path')
val: images    # val images (relative to 'path')
test: images   # test images (relative to 'path')

# Classes
nc: 1  # number of classes
names: ['dot']  # class names
"""
        
        with open(output_path, 'w') as f:
            f.write(yaml_content)
        
        print(f"Dataset YAML created: {output_path}")


def main():
    """Main conversion function"""
    converter = YOLODataConverter()
    
    # Convert all data
    converted_count, total_dots = converter.convert_all()
    
    if converted_count > 0:
        # Create dataset.yaml
        converter.create_dataset_yaml()
        
        print(f"\nData conversion completed!")
        print(f"Ready for YOLO training with {converted_count} images and {total_dots} dots")
    else:
        print("No data was converted")


if __name__ == "__main__":
    main()
