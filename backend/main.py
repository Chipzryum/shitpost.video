
from generate_video import generateAudio, generateBackgroundVideo, addSubtitles
from fetch import fetch_aita_post, fetch_askreddit_post, fetch_from_link
from flask import Flask, request, send_file
from flask_socketio import SocketIO
from unidecode import unidecode
from flask_cors import CORS
import subprocess
import zipfile
import random
import shutil
import time
import io
import os

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Get post, background footage choice, and directory location for temporary storage
script_dir = os.path.dirname(os.path.abspath(__file__))

# Main script execution
script_start_time = time.time()

# Save video function
def save(video, audio, username, i):
    output_video = f"video{username}{i}.mp4"

    ffmpeg_command = [
        "ffmpeg",
        "-y",
        "-nostats",
        "-loglevel", "panic",
        "-i", video,
        "-i", audio,
        "-vf", "scale=trunc(iw/2)*2:ih,format=yuv420p",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "160k",
        "-movflags", "+faststart",
        "-strict", "experimental",
        "-map", "0:v:0",
        "-map", "1:a:0",
        output_video
    ]

    try:
        subprocess.run(ffmpeg_command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")

def emit_progress(username, step):
    socketio.emit('progress', {'username': username, 'step': step})

@app.route('/generate-link', methods=['POST'])
def generate_link():
    data = request.get_json()
    username = data.get('username')

    try:
        subreddit = random.randint(1, 2)
        if subreddit == 1:
            data = fetch_aita_post(username)
            return { 'url': data['url'] }
        elif subreddit == 2:
            data = fetch_askreddit_post(username)
            return { 'url': data['url'] }
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, 500

@app.route('/generate-video', methods=['POST'])
def generate_video():
    data = request.get_json()
    link = data.get('link')
    footage_type = data.get('footage_type')
    subtitle_color = data.get('subtitle_color')
    username = data.get('username')
    result = fetch_from_link(link)

    if not os.path.exists(os.path.join(script_dir, f'temporary{username}')):
        os.makedirs(os.path.join(script_dir, f'temporary{username}'))

    try:
        if result:
            if 'top_comment' in result:
                posttext = result['content'] + ', ' + result['top_comment']['content']
            else:
                posttext = result['title'] + ', ' + result['content']
            cut = 920
            parts, start = [], 0
            while start < len(posttext):
                end = start + cut
                end = max(posttext.rfind('.', start, end), posttext.rfind('!', start, end), posttext.rfind('?', start, end))
                if end == -1 or end <= start:
                    end = min(start + cut, len(posttext))
                part = posttext[start:end+1].strip()
                if part:
                    parts.append(part)
                start = end + 1
                
        else:
            return "Link not sufficient", 500

        video_files = [os.path.join(script_dir, f'video{username}{i+1}.mp4') for i in range(len(parts))]
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for video_file in video_files:
                if os.path.exists(video_file):
                    zip_file.write(video_file, os.path.basename(video_file))
                else:
                    return f"File {video_file} not found", 404

        zip_buffer.seek(0)
        return send_file(zip_buffer, as_attachment=True, download_name='videos.zip', mimetype='application/zip')
        
    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        shutil.rmtree(f'temporary{username}', ignore_errors=True)

if __name__ == '__main__':
    app.run(debug=True)