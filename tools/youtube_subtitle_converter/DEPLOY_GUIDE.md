# YouTube 字幕轉換器 - Google Cloud Run 部署指南

本指南將教你如何將 YouTube 字幕轉換器部署到 Google Cloud Run，讓其他人可以透過網址使用。

## 目錄

1. [前置準備](#前置準備)
2. [建立 Google Cloud 專案](#建立-google-cloud-專案)
3. [安裝 Google Cloud CLI](#安裝-google-cloud-cli)
4. [部署應用程式](#部署應用程式)
5. [設定環境變數](#設定環境變數)
6. [測試與使用](#測試與使用)
7. [費用說明](#費用說明)
8. [常見問題](#常見問題)

---

## 前置準備

在開始之前，你需要：

- ✅ Google 帳號
- ✅ 信用卡（Google Cloud 需要，但新用戶有 $300 免費額度）
- ✅ Gemini API 金鑰（從 [Google AI Studio](https://aistudio.google.com/apikey) 取得）

---

## 建立 Google Cloud 專案

### 步驟 1：進入 Google Cloud Console

1. 前往 [Google Cloud Console](https://console.cloud.google.com)
2. 使用你的 Google 帳號登入

### 步驟 2：建立新專案

1. 點擊頂部的專案選擇器
2. 點擊「新增專案」
3. 輸入專案名稱，例如：`youtube-subtitle-converter`
4. 點擊「建立」

### 步驟 3：啟用必要的 API

在 Cloud Console 中，前往「API 和服務」>「啟用 API 和服務」，啟用以下服務：

- **Cloud Run API**
- **Cloud Build API**
- **Container Registry API**

或直接執行：
```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com containerregistry.googleapis.com
```

---

## 安裝 Google Cloud CLI

### Mac 安裝

```bash
# 使用 Homebrew 安裝
brew install google-cloud-sdk

# 初始化並登入
gcloud init
```

### Windows 安裝

1. 下載 [Google Cloud SDK 安裝程式](https://cloud.google.com/sdk/docs/install)
2. 執行安裝程式
3. 開啟終端機執行 `gcloud init`

### 驗證安裝

```bash
gcloud --version
```

---

## 部署應用程式

### 方法一：一鍵部署（推薦）

```bash
# 1. 進入專案目錄
cd ~/ai_class_flywheel/tools/youtube_subtitle_converter

# 2. 設定專案 ID（替換成你的專案 ID）
gcloud config set project YOUR_PROJECT_ID

# 3. 執行自動部署
gcloud builds submit --config cloudbuild.yaml
```

### 方法二：手動部署

```bash
# 1. 建構 Docker 映像
docker build -t gcr.io/YOUR_PROJECT_ID/youtube-subtitle-converter .

# 2. 推送到 Container Registry
docker push gcr.io/YOUR_PROJECT_ID/youtube-subtitle-converter

# 3. 部署到 Cloud Run
gcloud run deploy youtube-subtitle-converter \
    --image gcr.io/YOUR_PROJECT_ID/youtube-subtitle-converter \
    --region asia-east1 \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 900
```

---

## 設定環境變數

部署完成後，設定 Gemini API 金鑰：

```bash
gcloud run services update youtube-subtitle-converter \
    --region asia-east1 \
    --set-env-vars "GEMINI_API_KEY=你的API金鑰"
```

或在 Cloud Console 介面：

1. 前往 [Cloud Run](https://console.cloud.google.com/run)
2. 點擊你的服務
3. 點擊「編輯並部署新版本」
4. 展開「變數與密鑰」
5. 新增環境變數：`GEMINI_API_KEY` = `你的金鑰`
6. 點擊「部署」

---

## 測試與使用

### 取得服務網址

部署完成後會顯示網址，格式類似：
```
https://youtube-subtitle-converter-xxxxxxxxx-de.a.run.app
```

### 分享給他人

把這個網址分享給你的學生或朋友，他們就可以直接使用了！

---

## 費用說明

### 新用戶優惠

- **$300 美元免費額度**（90 天內使用）
- 足夠免費使用約 3-6 個月

### 預估費用（用完免費額度後）

| 使用量 | 預估月費 |
|--------|----------|
| 100 次轉換/月 | ~$1-5 |
| 500 次轉換/月 | ~$10-20 |
| 1000 次轉換/月 | ~$20-40 |

### 費用組成

- **Cloud Run**：按 CPU 和記憶體使用時間計費
- **Cloud Build**：每天前 120 分鐘免費
- **Container Registry**：儲存費用很低

### 設定預算警報

建議設定預算警報避免意外費用：

1. 前往「計費」>「預算與快訊」
2. 建立預算，設定金額（例如 $10）
3. 設定在 50%、90%、100% 時發送通知

---

## 常見問題

### Q: 部署失敗怎麼辦？

查看建構日誌：
```bash
gcloud builds list
gcloud builds log BUILD_ID
```

### Q: 如何查看應用程式日誌？

```bash
gcloud run services logs read youtube-subtitle-converter --region asia-east1
```

### Q: 如何更新應用程式？

修改程式碼後，重新執行部署指令：
```bash
gcloud builds submit --config cloudbuild.yaml
```

### Q: 如何刪除服務（停止計費）？

```bash
gcloud run services delete youtube-subtitle-converter --region asia-east1
```

### Q: 處理速度很慢？

可以增加資源：
```bash
gcloud run services update youtube-subtitle-converter \
    --region asia-east1 \
    --memory 4Gi \
    --cpu 4
```

### Q: 想限制只有特定人能用？

移除公開存取，改用身份驗證：
```bash
gcloud run services update youtube-subtitle-converter \
    --region asia-east1 \
    --no-allow-unauthenticated
```

---

## 進階設定

### 自訂網域

如果你有自己的網域，可以設定：

1. 前往 Cloud Run 控制台
2. 點擊服務 > 「網域對應」
3. 按照指示設定 DNS

### 設定最低實例數（減少冷啟動）

```bash
gcloud run services update youtube-subtitle-converter \
    --region asia-east1 \
    --min-instances 1
```

> 注意：這會增加費用，因為始終有一個實例在運行

---

## 需要幫助？

如有問題，請參考：
- [Google Cloud Run 官方文件](https://cloud.google.com/run/docs)
- [Gradio 部署指南](https://www.gradio.app/guides/deploying-gradio-with-docker)
