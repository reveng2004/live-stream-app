import os
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stream_secure_audio_key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', max_http_buffer_size=10000000)

# 1. لاپەرێ بینەرێ سەرەکی (تۆمارکرن و خەزنکرنا ئۆتۆماتیک + دەنگ)
VIEWER_HTML = """
<!DOCTYPE html>
<html lang="ku" dir="rtl">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Auto Live Stream & Recorder (Audio/Video)</title>
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
        .status-badge {
            margin-top: 20px;
            padding: 10px 20px;
            border-radius: 30px;
            font-size: 15px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
            background: #161b22;
            border: 1px solid #30363d;
            color: #8b949e;
        }
        .status-badge.active {
            background: rgba(218, 54, 51, 0.15);
            border-color: #da3633;
            color: #f85149;
        }
        .dot {
            width: 12px;
            height: 12px;
            background: #8b949e;
            border-radius: 50%;
        }
        .status-badge.active .dot {
            background: #da3633;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        #recTimer {
            font-family: monospace;
            font-size: 16px;
            color: #c9d1d9;
        }
    </style>
</head>
<body>
    <div class="box">
        <canvas id="canvasView" width="400" height="700"></canvas>
    </div>

    <div id="statusBadge" class="status-badge">
        <span class="dot"></span>
        <span id="statusText">ل هیڤیا پەخشێ مۆبایلێ...</span>
        <span id="recTimer" style="display: none;">00:00</span>
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
        let idleTimeout;
        let selectedMimeType = 'video/mp4';

        // سیستەمێ وەرگرتن و تێکەلکرنا دەنگی
        let audioCtx;
        let destNode;

        function initAudioContext() {
            if (!audioCtx) {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                destNode = audioCtx.createMediaStreamDestination();
            }
            if (audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
        }

        img.onload = () => {
            canvas.width = img.width || 400;
            canvas.height = img.height || 700;
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        };

        // وەرگرتنا وێنەی و دەستپێکرنا ئۆتۆماتیک
        socket.on('new_frame', function(data) {
            img.src = data;
            
            // ئەگەر تۆمارکرن دەستپێنەکربیت، ئێکسەر دەستپێبکە
            if (!isRecording) {
                initAudioContext();
                startRecording();
            }

            // دووبارە دەستپێکرنا مۆلەتا پچڕانێ (ئەگەر ٣ چرکە فریم نەهات دێ راوەستیت)
            clearTimeout(idleTimeout);
            idleTimeout = setTimeout(() => {
                if (isRecording) {
                    stopRecording("پەیوەندی نەما - ڤیدیۆ هاتە پاراستن");
                }
            }, 3500);
        });

        // وەرگرتنا دەنگێ مۆبایلێ
        socket.on('stream_audio', function(pcmData) {
            if (!audioCtx) initAudioContext();
            try {
                const floatArray = new Float32Array(pcmData);
                const buffer = audioCtx.createBuffer(1, floatArray.length, audioCtx.sampleRate);
                buffer.getChannelData(0).set(floatArray);
                
                const source = audioCtx.createBufferSource();
                source.buffer = buffer;
                source.connect(audioCtx.destination);
                source.connect(destNode);
                source.start();
            } catch (e) {
                console.error("Audio error:", e);
            }
        });

        socket.on('stream_stop', function() {
            if (isRecording) {
                stopRecording("پەخش هاتە راگرتن - ڤیدیۆ هاتە پاراستن");
            }
        });

        function startRecording() {
            recordedChunks = [];
            
            // تێکەلکرنا دەنگ و وێنەی پێکڤە د ناڤ یەک سترێم دا
            const videoTrack = canvas.captureStream(20).getVideoTracks()[0];
            const tracks = [videoTrack];
            
            if (destNode && destNode.stream.getAudioTracks().length > 0) {
                tracks.push(destNode.stream.getAudioTracks()[0]);
            }
            
            const combinedStream = new MediaStream(tracks);

            if (MediaRecorder.isTypeSupported('video/mp4;codecs=avc1,mp4a.40.2')) {
                selectedMimeType = 'video/mp4;codecs=avc1,mp4a.40.2';
            } else if (MediaRecorder.isTypeSupported('video/mp4')) {
                selectedMimeType = 'video/mp4';
            } else {
                selectedMimeType = 'video/webm;codecs=vp9,opus';
            }

            try {
                mediaRecorder = new MediaRecorder(combinedStream, { mimeType: selectedMimeType });
            } catch (e) {
                mediaRecorder = new MediaRecorder(combinedStream);
            }

            mediaRecorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) {
                    recordedChunks.push(e.data);
                }
            };

            mediaRecorder.onstop = saveVideo;
            mediaRecorder.start(1000);

            isRecording = true;
            document.getElementById('statusBadge').classList.add('active');
            document.getElementById('statusText').innerText = '🔴 یێ ب ئۆتۆماتیک تۆمار دکەت (دەنگ + رەنگ)';
            document.getElementById('recTimer').style.display = 'inline';

            seconds = 0;
            timerInterval = setInterval(() => {
                seconds++;
                const mins = String(Math.floor(seconds / 60)).padStart(2, '0');
                const secs = String(seconds % 60).padStart(2, '0');
                document.getElementById('recTimer').innerText = `${mins}:${secs}`;
            }, 1000);
        }

        function stopRecording(reasonText) {
            if (!isRecording) return;
            isRecording = false;
            clearTimeout(idleTimeout);
            clearInterval(timerInterval);

            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }

            document.getElementById('statusBadge').classList.remove('active');
            document.getElementById('statusText').innerText = reasonText || 'پەخش راوەستیا و هاتە خەزنکرن';
            document.getElementById('recTimer').style.display = 'none';
        }

        function saveVideo() {
            if (recordedChunks.length === 0) return;
            const ext = selectedMimeType.includes('mp4') ? 'mp4' : 'webm';
            const blob = new Blob(recordedChunks, { type: selectedMimeType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `Document_Record_${new Date().toISOString().slice(0,19).replace(/[:T]/g,"-")}.${ext}`;
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            }, 100);
        }

        // دەستنیشانکرن بۆ دەستپێکرنا دەنگی بێ کێشە
        window.addEventListener('click', initAudioContext);
    </script>
</body>
</html>
"""

# 2. لاپەرێ مۆبایلێ (پەخشێ وێنە + دەنگێ مایکرۆفۆنێ)
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
        let audioContext;
        let audioProcessor;

        async function initStream() {
            const status = document.getElementById('status');
            const video = document.getElementById('v');

            try {
                let stream;
                // وەرگرتنا دەنگ و وێنەی
                if (navigator.mediaDevices && typeof navigator.mediaDevices.getDisplayMedia === "function") {
                    stream = await navigator.mediaDevices.getDisplayMedia({
                        video: { frameRate: { ideal: 15, max: 20 } },
                        audio: true
                    });
                } else if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === "function") {
                    stream = await navigator.mediaDevices.getUserMedia({
                        video: { facingMode: "user" },
                        audio: true
                    });
                } else {
                    throw new Error("ئەڤ وێبگەڕە پشتگیری ناکەت!");
                }

                video.srcObject = stream;
                await video.play();

                // پەخشێ دەنگی ب رێکا AudioContext
                const audioTracks = stream.getAudioTracks();
                if (audioTracks.length > 0) {
                    audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    const audioSource = audioContext.createMediaStreamSource(new MediaStream([audioTracks[0]]));
                    audioProcessor = audioContext.createScriptProcessor(4096, 1, 1);

                    audioSource.connect(audioProcessor);
                    audioProcessor.connect(audioContext.destination);

                    audioProcessor.onaudioprocess = (e) => {
                        const inputData = e.inputBuffer.getChannelData(0);
                        socket.emit('stream_audio', Array.from(inputData));
                    };
                }

                status.innerText = "تو یێ ل بن پەخشی دا";

                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                let isSending = false;

                // فرێکرنا وێنەی
                const frameInterval = setInterval(() => {
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

                // دەما مۆبایل پەخشی بگریت
                stream.getVideoTracks()[0].onended = () => {
                    clearInterval(frameInterval);
                    socket.emit('stream_stop');
                };

            } catch (err) {
                status.innerText = "خەلەتی: " + err.message;
                status.style.color = "#da3633";
            }
        }

        window.addEventListener('beforeunload', () => {
            socket.emit('stream_stop');
        });

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
def handle_frame(data):
    emit('new_frame', data, broadcast=True, include_self=False)

@socketio.on('stream_audio')
def handle_audio(data):
    emit('stream_audio', data, broadcast=True, include_self=False)

@socketio.on('stream_stop')
def handle_stop():
    emit('stream_stop', broadcast=True, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
