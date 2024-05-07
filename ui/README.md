# AgileCoder Installation Guide

## Prerequisites

Before you begin, ensure you have Docker installed on your machine. If not, you can download it from [Docker's official website](https://www.docker.com/products/docker-desktop).

## Setup Instructions

### 1. **Clone the repository:**
   Clone the AgileCoder repository to your local machine using the following command:
   ```bash
   git clone https://github.com/FSoft-AI4Code/AgileCoder.git
   ```
### 2 **Navigate to the ui project directory:**
```bash
    cd ui
    pip install -r requirements.txt
```
### 3 **Navigate to the AgileCoder directory:**     
```bash
    cd src/AgileCoder
    pip install -e .
```
### 4 **Finaly cd to the UI diretory and run backend and frontend:**
```bash
    python agilecoder_ui.py
    docker-compose up --build
```

