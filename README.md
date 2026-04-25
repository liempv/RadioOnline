# 📻 Orange Pi Radio Online

Ứng dụng **Radio Online chạy trên Orange Pi** được viết bằng **Python (single file)**, cho phép thiết bị hoạt động như một **đài radio internet độc lập**.

---

## 🚀 Giới thiệu

Dự án sử dụng duy nhất file:

```bash
radio_online.py
```

👉 Mục tiêu:

* Đơn giản – dễ chạy
* Nhẹ – phù hợp Orange Pi
* Hoạt động ổn định 24/7

Ứng dụng có thể dùng làm:

* Đài radio gia đình
* Loa phát nhạc quán cafe
* Hệ thống phát thanh nội bộ

---

## ✨ Tính năng chính

### 📻 Radio Online

* Phát link radio (MP3, AAC, HLS)
* Chuyển kênh nhanh
* Tự động reconnect khi mất mạng

### 🎬 YouTube Audio

* Phát nhạc từ link YouTube
* Hoạt động như một kênh radio

### 🧠 Quản lý kênh

* ➕ Thêm kênh radio
* ❌ Xóa kênh
* 📌 Chọn kênh phát
* 💾 Lưu danh sách kênh (JSON/local)

### 🌐 Điều khiển

* Truy cập qua trình duyệt (Web UI / API)
* Dùng được trên điện thoại, PC

---

## 📂 Cấu trúc dự án

```bash
RadioOnline/
│── radio_online.py    # File chính (toàn bộ logic)
│── channels.txt        # Danh sách kênh 
│── youtube_channels.txt   # Danh sách kênh 
```

---

## ⚙️ Cài đặt trên Orange Pi

### 1. Clone project

```bash
git clone https://github.com/liempv/RadioOnline.git
cd RadioOnline
```

### 2. Cài đặt môi trường

```bash
sudo apt update
sudo apt install python3 python3-pip mpv ffmpeg -y
pip3 install flask yt-dlp
```

---

## ▶️ Chạy ứng dụng

```bash
python3 radio_online.py
```

Truy cập:

```
http://<ip-orange-pi>:5000
```

---

## 🔊 Cấu hình âm thanh

Mở mixer:

```bash
alsamixer
```

Test loa:

```bash
speaker-test -t sine -f 1000
```

---

## 🔁 Tự khởi động cùng hệ thống

Tạo service:

```bash
sudo nano /etc/systemd/system/radio.service
```

```ini
[Unit]
Description=Radio Online (Python)
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/RadioOnline/radio_online.py
WorkingDirectory=/home/pi/RadioOnline
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Kích hoạt:

```bash
sudo systemctl daemon-reexec
sudo systemctl enable radio
sudo systemctl start radio
```

---

## 🧪 API cơ bản (ví dụ)

```bash
GET /play?id=1
GET /stop
GET /youtube?url=<link>
```

---

## 📌 Ưu điểm

* ✅ Chỉ 1 file Python → cực dễ deploy
* ✅ Chạy nhẹ trên Orange Pi
* ✅ Không cần GUI
* ✅ Dễ tùy biến



## 👨‍💻 Tác giả

**Liêm Phan**
IT Engineer – System & Infrastructure

---

⭐ Nếu thấy hữu ích, hãy Star repo để ủng hộ!
