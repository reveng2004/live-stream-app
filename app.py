import os
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stream_secure_key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 1. لاپەرێ سەرەکی (بینەر + تۆمارکرن ب فۆرماتێ MP4)
VIEWER_HTML = """
<!DOCTYPE html>
<html lang="ku" dir="rtl">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Stream & MP4 Recorder</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { 
            font-family: system-ui, -apple-system, sans-serif; 
            background: #010409; 
            color: white; 
            margin: 0; 
            display: flex; 
            flex-direction: column;
            align-items: center; 
            justify-content: center; 
            min-height: 100vh; 
            padding: 20px;
            box-sizing: border-box;
        }
        .box { 
            width: 400px; 
            height: 680px; 
            max-height: 80vh; 
            border: 2px solid #30363d; 
            border-radius: 20px; 
            overflow: hidden; 
            background: #000; 
            box-shadow: 0 0 35px rgba(46, 160, 67, 0.2); 
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }
        #canvasView { 
            width: 100%; 
            height: 100%; 
            object-fit: contain; 
        }
        .controls {
            margin-top: 20px;
            display: flex;
            gap: 15px;
            align-items: center;
        }
        .rec-btn {
            background: #da3633;
            color: white;
            border: none;
            padding: 12px 24px;
            font-size: 16px;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: 0.2s;
        }
        .rec-btn.recording {
            background: #238636;
        }
        .dot {
            width: 12px;
            height: 12px;
            background: white;
            border-radius: 50%;
            display: inline-block;
        }
        .recording .dot {
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        #recTimer {
            font-family: monospace;
            font-size: 18px;
            color: #8b949e;
        }
    </style>
</head>
<body>
    <div class="box">
        <canvas id="canvasView" width="400" height="700"></canvas>
    </div>

    <div class="controls">
        <button id="recBtn" class="rec-btn" onclick="toggleRecording()">
            <span class="dot"></span>
            <span id="btnText">دەستپێکرنا تۆمارکرنێ</span>
        </button>
        <span id="recTimer">00:00</span>
    </div>

    <script>
        const socket = io();
        const canvas = document.getElementById('canvasView');
        const ctx = canvas.getContext('2d');
        const img = new Image();

        let mediaRecorder;
        let recordedChunks = [];
        let isRecording = false;
        let timerInterval;
        let seconds = 0;
        let selectedMimeType = 'video/mp4';

        img.onload = () => {
            canvas.width = img.width || 400;
            canvas.height = img.height || 700;
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        };

        socket.on('new_frame', function(data) {
            img.src = data;
        });

        function toggleRecording() {
            if (!isRecording) {
                startRecording();
            } else {
                stopRecording();
            }
        }

        function startRecording() {
            recordedChunks = [];
            const stream = canvas.captureStream(20); // 20 FPS

            // پشکنین و هەلبژارتنا فۆرماتێ MP4
            if (MediaRecorder.isTypeSupported('video/mp4;codecs=avc1')) {
                selectedMimeType = 'video/mp4;codecs=avc1';
            } else if (MediaRecorder.isTypeSupported('video/mp4')) {
                selectedMimeType = 'video/mp4';
            } else {
                selectedMimeType = 'video/webm;codecs=vp9';
            }

            try {
                mediaRecorder = new MediaRecorder(stream, { mimeType: selectedMimeType });
            } catch (e) {
                mediaRecorder = new MediaRecorder(stream);
            }

            mediaRecorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) {
                    recordedChunks.push(e.data);
                }
            };

            mediaRecorder.onstop = saveVideo;
            mediaRecorder.start(1000); // کۆمکرنا داتایێ هەر چرکە

            isRecording = true;
            document.getElementById('recBtn').classList.add('recording');
            document.getElementById('btnText').innerText = 'ڕاگرتن و دابەزاندن (MP4)';
            
            seconds = 0;
            timerInterval = setInterval(() => {
                seconds++;
                const mins = String(Math.floor(seconds / 60)).padStart(2, '0');
                const secs = String(seconds % 60).padStart(2, '0');
                document.getElementById('recTimer').innerText = `${mins}:${secs}`;
            }, 1000);
        }

        function stopRecording() {
            mediaRecorder.stop();
            isRecording = false;
            clearInterval(timerInterval);
            document.getElementById('recBtn').classList.remove('recording');
            document.getElementById('btnText').innerText = 'دەستپێکرنا تۆمارکرنێ';
            document.getElementById('recTimer').innerText = '00:00';
        }

        function saveVideo() {
            const ext = selectedMimeType.includes('mp4') ? 'mp4' : 'webm';
            const blob = new Blob(recordedChunks, { type: selectedMimeType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `stream_record_${new Date().toISOString().slice(0,19).replace(/[:T]/g,"-")}.${ext}`;
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            }, 100);
        }
    </script>
</body>
</html>
"""

# 2. لاپەرێ مۆبایلێ (پەخشکەر)
PHONE_HTML = """
<!DOCTYPE html>
<html lang="ku" dir="rtl">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stream Source</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { 
            font-family: system-ui, -apple-system, sans-serif; 
            background: #0d1117; 
            color: #c9d1d9; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            min-height: 100vh; 
            margin: 0; 
            text-align: center;
        }
        #status { 
            font-weight: 700; 
            font-size: 24px; 
            color: #2ea043; 
        }
        video { display: none !important; }
    </style>
</head>
<body>
    <div id="status">ل هیڤیا دەستپێکرنێ...</div>
    <video id="v" autoplay playsinline muted></video>

    <script>
        const socket = io();

        async function initStream() {
            const status = document.getElementById('status');
            const video = document.getElementById('v');

            try {
                let stream;
                if (navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) {
                    stream = await navigator.mediaDevices.getDisplayMedia({
                        video: { frameRate: { ideal: 15, max: 20 } },
                        audio: false
                    });
                } else if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                    stream = await navigator.mediaDevices.getUserMedia({
                        video: { facingMode: "user" },
                        audio: false
                    });
                } else {
                    throw new Error("ئەڤ وێبگەڕە پشتگیرییا ڤیدیۆیێ ناکەت!");
                }

                video.srcObject = stream;
                await video.play();

                status.innerText = "تو یێ ل بن پەخشی دا";

                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                let isSending = false;

                setInterval(() => {
                    if (video.videoWidth > 0 && !isSending) {
                        isSending = true;
                        canvas.width = 400;
                        canvas.height = (video.videoHeight / video.videoWidth) * 400;
                        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                        
                        socket.emit('stream_frame', canvas.toDataURL('image/jpeg', 0.4), () => {
                            isSending = false;
                        });
                    }
                }, 65);

            } catch (err) {
                status.innerText = "خەلەتی: " + err.message;
                status.style.color = "#da3633";
            }
        }

        window.addEventListener('DOMContentLoaded', initStream);
    </script>
</body>
</html>
"""

@app.route('/')
def viewer():
    return render_template_string(VIEWER_HTML)

@app.route('/stream')
def stream_source():
    return render_template_string(PHONE_HTML)

@socketio.on('stream_frame')
def handle_stream(data):
    emit('new_frame', data, broadcast=True, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
