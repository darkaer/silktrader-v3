#!/usr/bin/env python3
import os

# Optimize pandas for multi-threading
os.environ['OMP_NUM_THREADS'] = '8'  # Adjust based on your Xeon core count
os.environ['OPENBLAS_NUM_THREADS'] = '8'
os.environ['MKL_NUM_THREADS'] = '8'

# Optional: Configure for GPU acceleration if using cuDF
# os.environ['CUDA_VISIBLE_DEVICES'] = '0'
