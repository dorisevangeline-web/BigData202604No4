```dockerfile
FROM python:3.11-slim

# 安裝 Chromium 與必要套件
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    curl \
    unzip \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /app

# 複製 requirements
COPY requirements.txt .

# 安裝 Python 套件
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有檔案
COPY . .

# Render 使用的 Port
ENV PORT=10000

# 啟動程式
CMD ["python", "main.py"]
```
