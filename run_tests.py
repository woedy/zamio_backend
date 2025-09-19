#!/usr/bin/env python
"""
Test runner script for ZamIO backend tests.
Provides different test execution modes and reporting options.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.test_settings')

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Run ZamIO backend tests')
    parser.add_argument(
        '--mode',
        choices=['unit', 'integration', 'performance', 'all', 'quick'],
        default='all',
        help='Test mode to run'
    )
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Run with coverage reporting'
    )
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Run tests in parallel'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--failfast',
        action='store_true',
        help='Stop on first failure'
    )
    
    args = parser.parse_args()
    
    # Base pytest command
    cmd = ['python', '-m', 'pytest']
    
    # Add verbosity
    if args.verbose:
        cmd.append('-v')
    else:
        cmd.append('-q')
    
    # Add fail fast
    if args.failfast:
        cmd.append('-x')
    
    # Add parallel execution
    if args.parallel:
        cmd.extend(['-n', 'auto'])
    
    # Add coverage
    if args.coverage:
        cmd.extend(['--cov=.', '--cov-report=term-missing', '--cov-report=html'])
    
    # Add test selection based on mode
    if args.mode == 'unit':
        cmd.extend(['-m', 'unit'])
    elif args.mode == 'integration':
        cmd.extend(['-m', 'integration'])
    elif args.mode == 'performance':
        cmd.extend(['-m', 'performance'])
    elif args.mode == 'quick':
        cmd.extend(['-m', 'not slow and not performance'])
    # 'all' mode runs everything (no additional markers)
    
    # Run the tests
    success = run_command(cmd, f"Backend tests ({args.mode} mode)")
    
    if success:
        print(f"\n🎉 All tests passed!")
        if args.coverage:
            print("📊 Coverage report generated in htmlcov/index.html")
    else:
        print(f"\n💥 Some tests failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()