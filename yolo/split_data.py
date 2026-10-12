"""
Split data into train/val/test sets for YOLO training
"""
import os
import shutil
import random
from pathlib import Path
from typing import Tuple


class YOLODataSplitter:
    """
    Split YOLO dataset into train/validation/test sets
    """
    
    def __init__(self, 
                 data_dir: str = "data",
                 train_ratio: float = 0.7,
                 val_ratio: float = 0.2,
                 test_ratio: float = 0.1,
                 random_seed: int = 42):
        """
        Initialize data splitter
        
        Args:
            data_dir: Data directory containing images and labels
            train_ratio: Ratio for training set
            val_ratio: Ratio for validation set  
            test_ratio: Ratio for test set
            random_seed: Random seed for reproducibility
        """
        self.data_dir = Path(data_dir)
        self.images_dir = self.data_dir / "images"
        self.labels_dir = self.data_dir / "labels"
        
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        
        # Validate ratios
        if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-6:
            raise ValueError("Train, validation, and test ratios must sum to 1.0")
        
        # Set random seed
        random.seed(random_seed)
        
        # Create split directories
        self.train_dir = self.data_dir / "train"
        self.val_dir = self.data_dir / "val"
        self.test_dir = self.data_dir / "test"
        
        for split_dir in [self.train_dir, self.val_dir, self.test_dir]:
            (split_dir / "images").mkdir(parents=True, exist_ok=True)
            (split_dir / "labels").mkdir(parents=True, exist_ok=True)
    
    def get_available_files(self) -> list:
        """
        Get list of available image files
        
        Returns:
            List of image filenames (without extension)
        """
        image_files = list(self.images_dir.glob("*.png"))
        label_files = list(self.labels_dir.glob("*.txt"))
        
        # Get common filenames
        image_names = {f.stem for f in image_files}
        label_names = {f.stem for f in label_files}
        common_names = image_names.intersection(label_names)
        
        return sorted(list(common_names))
    
    def split_data(self) -> Tuple[int, int, int]:
        """
        Split data into train/val/test sets
        
        Returns:
            Tuple of (train_count, val_count, test_count)
        """
        print("=== Splitting data into train/val/test sets ===")
        
        # Get available files
        available_files = self.get_available_files()
        total_files = len(available_files)
        
        if total_files == 0:
            print("❌ No files found to split")
            return 0, 0, 0
        
        print(f"Found {total_files} files to split")
        
        # Shuffle files
        random.shuffle(available_files)
        
        # Calculate split indices
        train_end = int(total_files * self.train_ratio)
        val_end = train_end + int(total_files * self.val_ratio)
        
        train_files = available_files[:train_end]
        val_files = available_files[train_end:val_end]
        test_files = available_files[val_end:]
        
        print(f"Split: {len(train_files)} train, {len(val_files)} val, {len(test_files)} test")
        
        # Copy files to respective directories
        self._copy_files(train_files, self.train_dir, "train")
        self._copy_files(val_files, self.val_dir, "val")
        self._copy_files(test_files, self.test_dir, "test")
        
        return len(train_files), len(val_files), len(test_files)
    
    def _copy_files(self, files: list, target_dir: Path, split_name: str):
        """
        Copy files to target directory
        
        Args:
            files: List of filenames to copy
            target_dir: Target directory
            split_name: Name of the split (for logging)
        """
        for filename in files:
            # Copy image
            src_image = self.images_dir / f"{filename}.png"
            dst_image = target_dir / "images" / f"{filename}.png"
            shutil.copy2(src_image, dst_image)
            
            # Copy label
            src_label = self.labels_dir / f"{filename}.txt"
            dst_label = target_dir / "labels" / f"{filename}.txt"
            shutil.copy2(src_label, dst_label)
        
        print(f"Copied {len(files)} files to {split_name} set")
    
    def create_split_yaml(self, output_path: str = "data/dataset_split.yaml"):
        """
        Create dataset.yaml file for split data
        
        Args:
            output_path: Path to save dataset.yaml
        """
        yaml_content = f"""# Dot Detection Dataset - Split Version
path: {os.path.abspath('data')}  # dataset root dir
train: train/images  # train images (relative to 'path')
val: val/images      # val images (relative to 'path')
test: test/images    # test images (relative to 'path')

# Classes
nc: 1  # number of classes
names: ['dot']  # class names
"""
        
        with open(output_path, 'w') as f:
            f.write(yaml_content)
        
        print(f"Split dataset YAML created: {output_path}")
    
    def get_split_statistics(self) -> dict:
        """
        Get statistics for each split
        
        Returns:
            Dictionary with split statistics
        """
        stats = {}
        
        for split_name, split_dir in [("train", self.train_dir), 
                                     ("val", self.val_dir), 
                                     ("test", self.test_dir)]:
            images_count = len(list((split_dir / "images").glob("*.png")))
            labels_count = len(list((split_dir / "labels").glob("*.txt")))
            
            # Count total dots in labels
            total_dots = 0
            for label_file in (split_dir / "labels").glob("*.txt"):
                with open(label_file, 'r') as f:
                    lines = f.readlines()
                    total_dots += len(lines)
            
            stats[split_name] = {
                "images": images_count,
                "labels": labels_count,
                "total_dots": total_dots,
                "avg_dots_per_image": total_dots / images_count if images_count > 0 else 0
            }
        
        return stats


def main():
    """Main splitting function"""
    splitter = YOLODataSplitter()
    
    # Split data
    train_count, val_count, test_count = splitter.split_data()
    
    if train_count + val_count + test_count > 0:
        # Create split YAML
        splitter.create_split_yaml()
        
        # Print statistics
        stats = splitter.get_split_statistics()
        print(f"\n=== Split Statistics ===")
        for split_name, split_stats in stats.items():
            print(f"{split_name.upper()}:")
            print(f"  Images: {split_stats['images']}")
            print(f"  Total dots: {split_stats['total_dots']}")
            print(f"  Avg dots/image: {split_stats['avg_dots_per_image']:.2f}")
        
        print(f"\nData splitting completed!")
        print(f"Ready for YOLO training with {train_count} train, {val_count} val, {test_count} test images")
    else:
        print("No data was split")


if __name__ == "__main__":
    main()
