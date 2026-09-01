import os
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stream_secure_key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 1. لاپەرێ سەرەکی (بینەر - Viewer)
VIEWER_HTML = """
<!DOCTYPE html>
<html lang="ku" dir="rtl">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Stream Viewer</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { 
            font-family: system-ui, -apple-system, sans-serif; 
            background: #010409; 
            color: white; 
            margin: 0; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            min-height: 100vh; 
            padding: 20px;
            box-sizing: border-box;
        }
        .box { 
            width: 420px; 
            height: 750px; 
            max-height: 90vh; 
            border: 2px solid #30363d; 
            border-radius: 20px; 
            overflow: hidden; 
            background: #000; 
            box-shadow: 0 0 35px rgba(46, 160, 67, 0.2); 
            display: flex;
            align-items: center;
            justify-content: center;
        }
        img { 
            width: 100%; 
            height: 100%; 
            object-fit: contain; 
        }
    </style>
</head>
<body>
    <div class="box">
        <img id="liveView" src="" alt="ل هیڤیا دەستپێکرنا پەخشی...">
    </div>

    <script>
        const socket = io();
        const liveView = document.getElementById('liveView');

        socket.on('new_frame', function(data) {
            // وەرگرتنا داتایێ ب شێوازێ وێنەیێ ڕاستەوخۆ
            if (typeof data === 'string') {
                liveView.src = data;
            } else {
                const blob = new Blob([data], { type: 'image/jpeg' });
                liveView.src = URL.createObjectURL(blob);
            }
        });
    </script>
</body>
</html>
"""

# 2. لاپەرێ مۆبایلێ (پەخشکەر - Stream)
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
                if (navigator.mediaDevices && typeof navigator.mediaDevices.getDisplayMedia === "function") {
                    stream = await navigator.mediaDevices.getDisplayMedia({
                        video: { frameRate: { ideal: 15, max: 20 } },
                        audio: false
                    });
                } else if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === "function") {
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

                // فرێکرنا فرێمان ب کێمترین قەبارە و زووترین دەم
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
