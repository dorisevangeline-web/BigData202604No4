# 使用官方 Python 輕量基礎鏡像
FROM python:3.10-slim

# 安裝 Google Chrome 瀏覽器與依賴套件
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    apt-transport-https \
    && wget -q -O - https://google.com | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://google.com stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 設定容器內的工作目錄
WORKDIR /app

# 複製環境清單並安裝 Python 套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案內的所有檔案（包含 app.py 和 templates 資料夾）
COPY . .

# 宣告對外通訊埠（會自動讀取 Render 分配的 PORT）
EXPOSE 8080

# 啟動指令
CMD ["python", "app.py"]
