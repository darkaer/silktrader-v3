# Installation Guide

## System Requirements

- Python 3.12+ (3.13 recommended)
- Linux (Arch Linux recommended)
- 4GB+ RAM
- Internet connection

## Step 1: Install System Dependencies

### Arch Linux
```bash
sudo pacman -S python python-pip base-devel
yay -S ta-lib

Ubuntu/Debian

bash
sudo apt update
sudo apt install python3 python3-pip python3-venv build-essential
sudo apt install ta-lib

Step 2: Clone Repository

bash
git clone https://github.com/YOUR_USERNAME/silktrader-v3.git
cd silktrader-v3

Step 3: Setup Virtual Environment

bash
python -m venv venv
source venv/bin/activate
pip install --upgrade pip

Step 4: Install Python Dependencies

bash
pip install -r requirements.txt
pip install TA-Lib

Step 5: Configuration

bash
cp credentials/pionex.json.example credentials/pionex.json
nano credentials/pionex.json

Add your API keys and adjust risk limits.
Step 6: Test Installation

bash
python tests/test_foundation.py

Troubleshooting
TA-Lib Installation Issues

If pip fails to install TA-Lib, install from source:

bash
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
pip install TA-Lib

