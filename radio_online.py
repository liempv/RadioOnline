from flask import Flask, render_template_string, request, jsonify, redirect, Response
import subprocess
import time
import requests
import threading
import os
import re

app = Flask(__name__)

# --- CẤU HÌNH HỆ THỐNG ---
AUDIO_DEV = "alsa/hw:1,0"  # Card âm thanh USB
CHANNELS_FILE = "/home/pi/channels.txt"
YOUTUBE_CHANNELS_FILE = "/home/pi/youtube_channels.txt"  # File riêng cho YouTube
DEFAULT_VOL = 100
DEFAULT_URL = "https://audio-lss.vov.vn/han/live/vov1/audio/haudio-eng.m3u8"
DEFAULT_NAME = "VOV1"

# Trạng thái hệ thống
system_state = {
    "current_name": "Đang khởi động...",
    "volume": DEFAULT_VOL,
    "current_type": "radio"
}

def set_hardware_vol(val):
    """Thiết lập âm lượng tầng cứng cho Card USB"""
    try:
        subprocess.run(["/usr/bin/amixer", "-c", "1", "set", "PCM", f"{val}%"], stderr=subprocess.DEVNULL)
        subprocess.run(["/usr/bin/amixer", "-c", "1", "set", "Speaker", f"{val}%"], stderr=subprocess.DEVNULL)
        system_state["volume"] = val
    except: pass

def extract_youtube_id(url):
    """Trích xuất YouTube video ID từ URL"""
    patterns = [
        r'youtube\.com/watch\?v=([^&]+)',
        r'youtu\.be/([^?]+)',
        r'youtube\.com/embed/([^?]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_youtube_audio_url(youtube_url):
    """Lấy URL audio stream từ YouTube sử dụng yt-dlp"""
    try:
        cmd = [
            "yt-dlp",
            "--get-url",
            "--format",
            "bestaudio[ext=m4a]/bestaudio",
            youtube_url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            audio_url = result.stdout.strip().split('\n')[-1]
            return audio_url
        return None
    except Exception as e:
        print(f"Error getting YouTube audio: {e}")
        return None

def get_youtube_title(youtube_url):
    """Lấy tiêu đề video YouTube"""
    try:
        cmd = ["yt-dlp", "--get-title", youtube_url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return result.stdout.strip()
        return "YouTube Video"
    except:
        return "YouTube Video"

def play_audio(url, name, is_youtube=False):
    """Tắt mpv cũ và phát luồng mới"""
    system_state["current_name"] = name
    system_state["current_type"] = "youtube" if is_youtube else "radio"
    subprocess.run(["/usr/bin/pkill", "-9", "mpv"], stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    
    cmd = [
        "/usr/bin/mpv",
        "--no-video",
        f"--audio-device={AUDIO_DEV}",
        "--volume=100",
        "--cache=yes",
        "--cache-secs=10",
        "--ao=alsa",
        url
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def auto_start_logic():
    """Đợi mạng ổn định rồi tự phát kênh mặc định"""
    time.sleep(12)
    set_hardware_vol(DEFAULT_VOL)
    
    for i in range(15):
        try:
            r = requests.get("https://google.com", timeout=3)
            if r.status_code == 200:
                play_audio(DEFAULT_URL, DEFAULT_NAME, False)
                return
        except:
            system_state["current_name"] = f"Đang đợi mạng ({i+1})..."
            time.sleep(5)
    system_state["current_name"] = "Không có kết nối mạng"

def get_radio_channels():
    """Đọc danh sách radio từ file"""
    channels = []
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, "r", encoding='utf-8') as f:
            for line in f:
                if "|" in line:
                    parts = line.strip().split("|")
                    if len(parts) == 2:
                        name, url = parts
                        channels.append({"name": name, "url": url})
    return channels

def get_youtube_channels():
    """Đọc danh sách YouTube từ file"""
    channels = []
    if os.path.exists(YOUTUBE_CHANNELS_FILE):
        with open(YOUTUBE_CHANNELS_FILE, "r", encoding='utf-8') as f:
            for line in f:
                if "|" in line:
                    parts = line.strip().split("|")
                    if len(parts) == 2:
                        name, url = parts
                        channels.append({"name": name, "url": url})
    return channels

def save_radio_channels(channels):
    """Lưu danh sách radio vào file"""
    with open(CHANNELS_FILE, "w", encoding='utf-8') as f:
        for ch in channels:
            f.write(f"{ch['name']}|{ch['url']}\n")

def save_youtube_channels(channels):
    """Lưu danh sách YouTube vào file"""
    with open(YOUTUBE_CHANNELS_FILE, "w", encoding='utf-8') as f:
        for ch in channels:
            f.write(f"{ch['name']}|{ch['url']}\n")

# --- WEB ROUTES ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, 
                                 radio_channels=get_radio_channels(),
                                 youtube_channels=get_youtube_channels(),
                                 current=system_state["current_name"],
                                 current_type=system_state["current_type"],
                                 vol=system_state["volume"])

@app.route('/play')
def play_route():
    url = request.args.get('url')
    name = request.args.get('name')
    is_youtube = request.args.get('youtube', 'false').lower() == 'true'
    if url:
        play_audio(url, name, is_youtube)
    return jsonify(res="ok")

@app.route('/play_youtube', methods=['POST'])
def play_youtube_route():
    """API để phát YouTube URL trực tiếp"""
    data = request.get_json()
    youtube_url = data.get('url')
    
    if not youtube_url:
        return jsonify({"error": "No URL provided"}), 400
    
    # Lấy audio URL
    audio_url = get_youtube_audio_url(youtube_url)
    if audio_url:
        title = get_youtube_title(youtube_url)
        play_audio(audio_url, f"YouTube: {title}", True)
        return jsonify({"success": True, "title": title})
    else:
        return jsonify({"error": "Cannot extract audio from YouTube"}), 500

@app.route('/volume')
def volume_route():
    lvl = request.args.get('level')
    if lvl:
        set_hardware_vol(lvl)
    return jsonify(res="ok")

@app.route('/stop')
def stop_route():
    subprocess.run(["/usr/bin/pkill", "-9", "mpv"])
    system_state["current_name"] = "Đã dừng đài"
    return redirect('/')

@app.route('/add_radio', methods=['POST'])
def add_radio():
    """Thêm kênh radio mới"""
    data = request.get_json()
    name = data.get('name')
    url = data.get('url')
    
    if name and url:
        channels = get_radio_channels()
        channels.append({"name": name, "url": url})
        save_radio_channels(channels)
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route('/add_youtube_channel', methods=['POST'])
def add_youtube_channel():
    """Thêm kênh YouTube vào danh sách"""
    data = request.get_json()
    name = data.get('name')
    url = data.get('url')
    
    if name and url:
        channels = get_youtube_channels()
        channels.append({"name": name, "url": url})
        save_youtube_channels(channels)
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route('/delete_radio', methods=['POST'])
def delete_radio():
    """Xóa kênh radio"""
    data = request.get_json()
    channel_name = data.get('name')
    
    if channel_name:
        channels = get_radio_channels()
        channels = [ch for ch in channels if ch['name'] != channel_name]
        save_radio_channels(channels)
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route('/delete_youtube', methods=['POST'])
def delete_youtube():
    """Xóa kênh YouTube"""
    data = request.get_json()
    channel_name = data.get('name')
    
    if channel_name:
        channels = get_youtube_channels()
        channels = [ch for ch in channels if ch['name'] != channel_name]
        save_youtube_channels(channels)
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route('/current')
def current_status():
    """API trả về trạng thái hiện tại"""
    return jsonify({
        "name": system_state["current_name"],
        "volume": system_state["volume"],
        "type": system_state["current_type"]
    })

# --- GIAO DIỆN HTML/JS ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>OPi Radio - YouTube Support</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            user-select: none;
            -webkit-tap-highlight-color: transparent;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: rgba(0, 0, 0, 0.85);
            backdrop-filter: blur(10px);
            border-radius: 30px;
            padding: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        
        .header {
            text-align: center;
            margin-bottom: 20px;
        }
        
        .header h1 {
            font-size: 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .status-card {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 15px;
            margin-bottom: 20px;
            border-left: 4px solid #667eea;
        }
        
        .status-label {
            font-size: 12px;
            opacity: 0.7;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .status-name {
            font-size: 18px;
            font-weight: bold;
            margin-top: 5px;
            word-break: break-word;
        }
        
        .volume-control {
            margin-bottom: 20px;
        }
        
        .volume-label {
            font-size: 12px;
            opacity: 0.7;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }
        
        input[type="range"] {
            width: 100%;
            height: 4px;
            -webkit-appearance: none;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 2px;
            outline: none;
        }
        
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            background: #667eea;
            border-radius: 50%;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }
        
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid rgba(255, 255, 255, 0.1);
        }
        
        .tab {
            flex: 1;
            padding: 12px;
            background: none;
            border: none;
            color: white;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.3s;
            opacity: 0.6;
        }
        
        .tab.active {
            opacity: 1;
            border-bottom: 2px solid #667eea;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .channel-list {
            max-height: 400px;
            overflow-y: auto;
            margin-bottom: 15px;
        }
        
        .channel-item {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: 0.2s;
        }
        
        .channel-item:active {
            background: rgba(255, 255, 255, 0.2);
        }
        
        .channel-name {
            font-weight: 500;
            flex: 1;
            cursor: pointer;
        }
        
        .delete-btn {
            background: rgba(255, 68, 68, 0.3);
            border: none;
            color: #ff4444;
            padding: 6px 12px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 12px;
            transition: 0.2s;
        }
        
        .delete-btn:active {
            background: rgba(255, 68, 68, 0.6);
        }
        
        .add-form {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .add-form input {
            width: 100%;
            padding: 12px;
            margin-bottom: 8px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            color: white;
            font-size: 14px;
        }
        
        .add-form input::placeholder {
            color: rgba(255, 255, 255, 0.5);
        }
        
        .add-form input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .btn {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 12px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: 0.2s;
        }
        
        .btn:active {
            transform: scale(0.98);
        }
        
        .btn-stop {
            background: rgba(255, 68, 68, 0.8);
            margin-top: 10px;
        }
        
        .btn-youtube {
            background: linear-gradient(135deg, #ff0000 0%, #cc0000 100%);
            margin-bottom: 10px;
        }
        
        .message {
            padding: 10px;
            margin: 10px 0;
            border-radius: 12px;
            display: none;
            animation: slideIn 0.3s ease;
        }
        
        .message.success {
            background: rgba(102, 126, 234, 0.3);
            border: 1px solid #667eea;
        }
        
        .message.error {
            background: rgba(255, 68, 68, 0.3);
            border: 1px solid #ff4444;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .playing-badge {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #4ade80;
            border-radius: 50%;
            margin-left: 8px;
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        ::-webkit-scrollbar {
            width: 6px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.3);
            border-radius: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📻 Orange Pi Radio</h1>
        </div>
        
        <div class="status-card">
            <div class="status-label">🎧 ĐANG PHÁT</div>
            <div class="status-name" id="current-name">
                {{ current }}
                {% if current != "Đã dừng đài" and current != "Đang khởi động..." %}
                <span class="playing-badge"></span>
                {% endif %}
            </div>
        </div>
        
        <div class="volume-control">
            <div class="volume-label">
                <span>🔊 Âm lượng</span>
                <span id="vol-value">{{ vol }}%</span>
            </div>
            <input type="range" min="0" max="100" value="{{ vol }}" id="volume-slider" onchange="setVolume(this.value)">
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="switchTab('radio')">📻 Radio</button>
            <button class="tab" onclick="switchTab('youtube')">🎵 YouTube</button>
        </div>
        
        <!-- Tab Radio -->
        <div id="radio-tab" class="tab-content active">
            <div class="channel-list" id="radio-list">
                {% for ch in radio_channels %}
                <div class="channel-item">
                    <span class="channel-name" onclick="playRadio('{{ ch.url }}', '{{ ch.name }}')">{{ ch.name }}</span>
                    <button class="delete-btn" onclick="deleteChannel('radio', '{{ ch.name }}')">Xóa</button>
                </div>
                {% endfor %}
            </div>
            
            <div class="add-form">
                <input type="text" id="radio-name" placeholder="Tên đài (VD: VOV1)">
                <input type="text" id="radio-url" placeholder="URL stream (VD: http://...)">
                <button class="btn" onclick="addRadio()">➕ Thêm radio</button>
                <button class="btn btn-stop" onclick="stopPlay()">⏹ Dừng phát</button>
            </div>
        </div>
        
        <!-- Tab YouTube -->
        <div id="youtube-tab" class="tab-content">
            <div class="channel-list" id="youtube-list">
                {% for ch in youtube_channels %}
                <div class="channel-item">
                    <span class="channel-name" onclick="playYoutubeChannel('{{ ch.url }}', '{{ ch.name }}')">{{ ch.name }}</span>
                    <button class="delete-btn" onclick="deleteChannel('youtube', '{{ ch.name }}')">Xóa</button>
                </div>
                {% endfor %}
            </div>
            
            <div class="add-form">
                <input type="text" id="youtube-name" placeholder="Tên kênh (VD: Nhạc Chill)">
                <input type="text" id="youtube-url" placeholder="YouTube URL (VD: https://youtu.be/...)">
                <button class="btn btn-youtube" onclick="playYouTubeNow()">▶ Phát ngay</button>
                <button class="btn" onclick="addYoutubeChannel()">💾 Lưu vào danh sách</button>
            </div>
        </div>
        
        <div id="message" class="message"></div>
    </div>
    
    <script>
        // Phát radio
        function playRadio(url, name) {
            fetch(`/play?url=${encodeURIComponent(url)}&name=${encodeURIComponent(name)}&youtube=false`);
            updateCurrentPlaying(name);
            showMessage(`Đang phát: ${name}`, 'success');
        }
        
        // Phát YouTube từ danh sách đã lưu
        function playYoutubeChannel(url, name) {
            fetch(`/play?url=${encodeURIComponent(url)}&name=${encodeURIComponent(name)}&youtube=true`);
            updateCurrentPlaying(name);
            showMessage(`Đang phát: ${name}`, 'success');
        }
        
        // Phát YouTube trực tiếp
        async function playYouTubeNow() {
            const url = document.getElementById('youtube-url').value.trim();
            if (!url) {
                showMessage('Vui lòng nhập YouTube URL', 'error');
                return;
            }
            
            showMessage('Đang xử lý YouTube...', 'success');
            
            try {
                const response = await fetch('/play_youtube', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url})
                });
                const data = await response.json();
                
                if (data.success) {
                    updateCurrentPlaying(data.title);
                    showMessage(`Đang phát: ${data.title}`, 'success');
                    document.getElementById('youtube-url').value = '';
                } else {
                    showMessage(data.error || 'Không thể phát video này', 'error');
                }
            } catch (error) {
                showMessage('Lỗi kết nối đến server', 'error');
            }
        }
        
        // Thêm radio mới
        async function addRadio() {
            const name = document.getElementById('radio-name').value.trim();
            const url = document.getElementById('radio-url').value.trim();
            
            if (!name || !url) {
                showMessage('Vui lòng nhập đầy đủ tên và URL', 'error');
                return;
            }
            
            try {
                const response = await fetch('/add_radio', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: name, url: url})
                });
                const data = await response.json();
                
                if (data.success) {
                    showMessage('Đã thêm kênh radio thành công!', 'success');
                    setTimeout(() => location.reload(), 1000);
                } else {
                    showMessage('Không thể thêm kênh', 'error');
                }
            } catch (error) {
                showMessage('Lỗi kết nối', 'error');
            }
        }
        
        // Thêm YouTube vào danh sách
        async function addYoutubeChannel() {
            const name = document.getElementById('youtube-name').value.trim();
            const url = document.getElementById('youtube-url').value.trim();
            
            if (!name || !url) {
                showMessage('Vui lòng nhập đầy đủ tên và URL', 'error');
                return;
            }
            
            try {
                const response = await fetch('/add_youtube_channel', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: name, url: url})
                });
                const data = await response.json();
                
                if (data.success) {
                    showMessage('Đã thêm YouTube vào danh sách!', 'success');
                    setTimeout(() => location.reload(), 1000);
                } else {
                    showMessage('Không thể thêm kênh', 'error');
                }
            } catch (error) {
                showMessage('Lỗi kết nối', 'error');
            }
        }
        
        // Xóa kênh
        async function deleteChannel(type, name) {
            if (!confirm(`Xóa kênh "${name}"?`)) return;
            
            const endpoint = type === 'radio' ? '/delete_radio' : '/delete_youtube';
            
            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: name})
                });
                const data = await response.json();
                
                if (data.success) {
                    showMessage('Đã xóa kênh!', 'success');
                    setTimeout(() => location.reload(), 500);
                } else {
                    showMessage('Không thể xóa kênh', 'error');
                }
            } catch (error) {
                showMessage('Lỗi kết nối', 'error');
            }
        }
        
        // Dừng phát
        function stopPlay() {
            fetch('/stop');
            document.getElementById('current-name').innerHTML = 'Đã dừng đài';
            showMessage('Đã dừng phát', 'success');
        }
        
        // Chỉnh âm lượng
        function setVolume(value) {
            document.getElementById('vol-value').innerText = value + '%';
            fetch(`/volume?level=${value}`);
        }
        
        // Cập nhật hiển thị đang phát
        function updateCurrentPlaying(name) {
            document.getElementById('current-name').innerHTML = name + '<span class="playing-badge"></span>';
        }
        
        // Hiển thị thông báo
        function showMessage(msg, type) {
            const msgDiv = document.getElementById('message');
            msgDiv.textContent = msg;
            msgDiv.className = `message ${type}`;
            msgDiv.style.display = 'block';
            setTimeout(() => {
                msgDiv.style.display = 'none';
            }, 3000);
        }
        
        // Chuyển tab
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            if (tab === 'radio') {
                document.querySelectorAll('.tab')[0].classList.add('active');
                document.getElementById('radio-tab').classList.add('active');
            } else {
                document.querySelectorAll('.tab')[1].classList.add('active');
                document.getElementById('youtube-tab').classList.add('active');
            }
        }
        
        // Tự động cập nhật trạng thái
        setInterval(async () => {
            try {
                const response = await fetch('/current');
                const data = await response.json();
                const currentElem = document.getElementById('current-name');
                if (!currentElem.innerHTML.includes(data.name) && data.name !== 'Đã dừng đài') {
                    currentElem.innerHTML = data.name + '<span class="playing-badge"></span>';
                }
            } catch(e) {}
        }, 3000);
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    # Tạo file mặc định nếu chưa có
    if not os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, "w", encoding='utf-8') as f:
            f.write("VOV1|https://audio-lss.vov.vn/han/live/vov1/audio/haudio-eng.m3u8\n")
            f.write("VOV2|https://stream.vovmedia.vn/vov2/index.m3u8\n")
            f.write("VOV3|https://stream.vovmedia.vn/vov3/index.m3u8\n")
    
    if not os.path.exists(YOUTUBE_CHANNELS_FILE):
        with open(YOUTUBE_CHANNELS_FILE, "w", encoding='utf-8') as f:
            f.write("Nhạc Chill|https://www.youtube.com/watch?v=example\n")
    
    # Kiểm tra yt-dlp
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
        print("✓ yt-dlp đã sẵn sàng")
    except:
        print("📦 Đang cài đặt yt-dlp...")
        subprocess.run(["pip", "install", "yt-dlp"])
    
    # Chạy auto start
    threading.Thread(target=auto_start_logic, daemon=True).start()
    
    print("\n🎵 Orange Pi Radio với YouTube Support đã khởi động!")
    print(f"📱 Truy cập: http://{subprocess.getoutput('hostname -I').split()[0]}:5000")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)