#!/usr/bin/env python3
"""
Ultra-fast file transfer server - Simple and fast
"""

import os
import time
import threading
from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename
import socket

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 * 1024  # 10GB limit

# Setup upload directory
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_file_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f} {size_names[i]}"

# Simple file cleanup (24 hours)
def cleanup_old_files():
    while True:
        try:
            now = time.time()
            for filename in os.listdir(UPLOAD_FOLDER):
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.isfile(filepath):
                    file_age = now - os.path.getctime(filepath)
                    if file_age > 86400:  # 24 hours
                        os.remove(filepath)
                        print(f"🗑️ Auto-deleted: {filename}")
        except Exception as e:
            print(f"⚠️ Cleaner error: {e}")
        time.sleep(3600)  # Check every hour

cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

@app.route('/')
def index():
    return render_template_string(open('simple_index.html').read())

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Secure filename
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'error': 'Invalid filename'}), 400
        
        # Handle duplicate filenames
        counter = 1
        original_filename = filename
        while os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
            name, ext = os.path.splitext(original_filename)
            filename = f"{name}_{counter}{ext}"
            counter += 1
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        # Save file directly - no processing, no encryption, no compression
        file.save(filepath)
        
        file_size = os.path.getsize(filepath)
        print(f"✅ File uploaded: {filename} ({get_file_size(file_size)})")
        
        return jsonify({
            'status': 'success',
            'filename': filename,
            'size': file_size
        }), 200
        
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/files')
def list_files():
    try:
        files = []
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(filepath):
                files.append({
                    'name': filename,
                    'size': os.path.getsize(filepath)
                })
        
        files.sort(key=lambda x: x['name'])
        return jsonify(files)
        
    except Exception as e:
        print(f"❌ List files error: {str(e)}")
        return jsonify({'error': 'Failed to list files'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        print(f"📥 File downloaded: {filename}")
        return send_file(filepath, as_attachment=True, download_name=filename)
        
    except Exception as e:
        print(f"❌ Download error: {str(e)}")
        return jsonify({'error': 'Download failed'}), 500

@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        os.remove(filepath)
        print(f"🗑️ File deleted: {filename}")
        return jsonify({'status': 'success', 'message': 'File deleted successfully'})
        
    except Exception as e:
        print(f"❌ Delete error: {str(e)}")
        return jsonify({'error': 'Delete failed'}), 500

@app.route('/health')
def health_check():
    try:
        uploads_ok = os.path.exists(UPLOAD_FOLDER)
        
        health_status = {
            'status': 'healthy' if uploads_ok else 'unhealthy',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'version': '1.0.0',
            'service': 'Ultra-Fast File Transfer',
            'checks': {
                'uploads_directory': uploads_ok
            }
        }
        
        return jsonify(health_status), 200 if health_status['status'] == 'healthy' else 503
        
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return jsonify({'error': 'Health check failed'}), 500

if __name__ == '__main__':
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    port = int(os.environ.get('PORT', 8081))
    local_ip = get_local_ip()
    
    print("⚡ Ultra-Fast File Transfer Server Starting...")
    print("=" * 60)
    print(f"📱 Access from your phone: http://{local_ip}:{port}")
    print(f"💻 Access from this computer: http://localhost:{port}")
    print("=" * 60)
    print("📁 Files saved directly in 'uploads' folder")
    print("🔄 Server supports up to 10GB file transfers")
    print("⚡ Ultra-fast - No encryption, no compression")
    print("🕐 Auto-delete after 24 hours")
    print("=" * 60)
    print("Press Ctrl+C to stop the server")
    print("")
    
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False) 