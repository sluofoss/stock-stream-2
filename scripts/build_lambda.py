#!/usr/bin/env python3
"""Build script for Lambda deployment package.

This script creates a deployment package for AWS Lambda that includes:
- Lambda function code
- Dependencies from requirements.txt
- Optimized PyArrow installation (stripped down for Lambda)

Usage:
    python scripts/build_lambda.py --module stock_data_fetcher --output dist/stock_data_fetcher.zip
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Build Lambda deployment package")
    parser.add_argument(
        "--module",
        required=True,
        help="Module name (e.g., stock_data_fetcher)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output zip file path",
    )
    parser.add_argument(
        "--python-version",
        default="3.12",
        help="Python version (default: 3.12)",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Optimize package size (strip debug symbols, remove tests)",
    )
    return parser.parse_args()


def install_dependencies(
    requirements_file: Path, target_dir: Path, python_version: str
) -> None:
    """Install dependencies to target directory.
    
    Args:
        requirements_file: Path to requirements.txt
        target_dir: Directory to install dependencies into
        python_version: Python version string (e.g., "3.12")
    """
    print(f"Installing dependencies from {requirements_file}...")
    
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        str(requirements_file),
        "-t",
        str(target_dir),
        "--platform",
        "manylinux2014_x86_64",
        "--only-binary=:all:",
        "--python-version",
        python_version,
    ]
    
    subprocess.run(cmd, check=True)
    print("Dependencies installed successfully")


def optimize_pyarrow(package_dir: Path) -> None:
    """Optimize PyArrow installation for Lambda.
    
    Removes unnecessary files from PyArrow to reduce package size:
    - Test files
    - Documentation
    - Static libraries
    - Debug symbols
    
    Args:
        package_dir: Directory containing installed packages
    """
    print("Optimizing PyArrow installation...")
    
    pyarrow_dir = package_dir / "pyarrow"
    if not pyarrow_dir.exists():
        print("PyArrow not found, skipping optimization")
        return
    
    # Remove test files
    tests_dir = pyarrow_dir / "tests"
    if tests_dir.exists():
        shutil.rmtree(tests_dir)
        print(f"Removed {tests_dir}")
    
    # Remove documentation
    docs_patterns = ["*.md", "*.rst", "*.txt"]
    for pattern in docs_patterns:
        for doc_file in pyarrow_dir.rglob(pattern):
            doc_file.unlink()
    
    # Remove static libraries (.a files)
    for static_lib in pyarrow_dir.rglob("*.a"):
        static_lib.unlink()
        print(f"Removed {static_lib.name}")
    
    # Strip debug symbols from shared libraries
    for so_file in pyarrow_dir.rglob("*.so"):
        try:
            subprocess.run(
                ["strip", "--strip-debug", str(so_file)],
                check=False,
                capture_output=True,
            )
            print(f"Stripped {so_file.name}")
        except FileNotFoundError:
            print("Warning: 'strip' command not found, skipping symbol stripping")
            break
    
    print("PyArrow optimization complete")


def copy_module_code(module_name: str, target_dir: Path) -> None:
    """Copy module code to target directory.
    
    Args:
        module_name: Name of the module (e.g., "stock_data_fetcher")
        target_dir: Directory to copy code into
    """
    print(f"Copying module code: {module_name}...")
    
    # Copy module directory
    module_src = Path("modules") / module_name
    module_dst = target_dir / "modules" / module_name
    
    if not module_src.exists():
        raise FileNotFoundError(f"Module not found: {module_src}")
    
    shutil.copytree(module_src, module_dst)
    
    # Copy common utilities
    common_src = Path("modules") / "common"
    common_dst = target_dir / "modules" / "common"
    shutil.copytree(common_src, common_dst)
    
    # Copy root __init__.py
    modules_init_src = Path("modules") / "__init__.py"
    modules_init_dst = target_dir / "modules" / "__init__.py"
    shutil.copy2(modules_init_src, modules_init_dst)
    
    print("Module code copied successfully")


def remove_unnecessary_files(package_dir: Path) -> None:
    """Remove unnecessary files to reduce package size.
    
    Args:
        package_dir: Directory containing the package
    """
    print("Removing unnecessary files...")
    
    # Patterns to remove
    patterns = [
        "*.pyc",
        "*.pyo",
        "__pycache__",
        "*.dist-info",
        "*.egg-info",
        "tests",
        "test",
        "*.md",
        "*.rst",
        "LICENSE*",
        "NOTICE*",
    ]
    
    removed_count = 0
    for pattern in patterns:
        for item in package_dir.rglob(pattern):
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            removed_count += 1
    
    print(f"Removed {removed_count} unnecessary files/directories")


def create_zip(source_dir: Path, output_file: Path) -> None:
    """Create ZIP archive of the package.
    
    Args:
        source_dir: Directory to zip
        output_file: Output ZIP file path
    """
    print(f"Creating ZIP archive: {output_file}...")
    
    # Create output directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = Path(root) / file
                arc_name = file_path.relative_to(source_dir)
                zipf.write(file_path, arc_name)
    
    # Get file size
    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"ZIP archive created: {output_file} ({size_mb:.2f} MB)")


def main() -> None:
    """Main build function."""
    args = parse_args()
    
    # Setup paths
    module_name = args.module
    output_file = Path(args.output)
    build_dir = Path("build") / module_name
    
    # Clean build directory
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)
    
    print(f"Building Lambda package for module: {module_name}")
    print(f"Build directory: {build_dir}")
    
    # Install dependencies
    requirements_file = Path("modules") / module_name / "requirements.txt"
    if requirements_file.exists():
        install_dependencies(requirements_file, build_dir, args.python_version)
    else:
        print(f"Warning: No requirements.txt found at {requirements_file}")
    
    # Optimize packages if requested
    if args.optimize:
        optimize_pyarrow(build_dir)
        remove_unnecessary_files(build_dir)
    
    # Copy module code
    copy_module_code(module_name, build_dir)
    
    # Create ZIP archive
    create_zip(build_dir, output_file)
    
    print("\n✅ Build complete!")
    print(f"Deployment package: {output_file}")
    
    # Print Lambda upload command
    lambda_name = f"stock-stream-{module_name.replace('_', '-')}"
    print(f"\nTo deploy to Lambda, run:")
    print(f"  aws lambda update-function-code \\")
    print(f"    --function-name {lambda_name} \\")
    print(f"    --zip-file fileb://{output_file}")


if __name__ == "__main__":
    main()
