#!/usr/bin/env python3
"""
Simple and robust file transfer server using Flask
"""

import os
import json
import time
import threading
import secrets
import gzip
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
import tempfile
import shutil

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 * 1024  # 5GB limit

# Persistent key generation
def get_or_create_key():
    key_file = 'encryption.key'
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

KEY = get_or_create_key()
fernet = Fernet(KEY)

# Setup upload directory
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Analytics database
class AnalyticsDB:
    def __init__(self):
        self.db_path = 'analytics.db'
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                file_size INTEGER,
                file_type TEXT,
                upload_time TIMESTAMP,
                ip_address TEXT,
                compressed_size INTEGER,
                download_count INTEGER DEFAULT 0,
                is_compressed BOOLEAN DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()
    
    def log_upload(self, filename, file_size, file_type, ip_address, compressed_size, is_compressed):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO uploads (filename, file_size, file_type, upload_time, ip_address, compressed_size, is_compressed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (filename, file_size, file_type, datetime.now(), ip_address, compressed_size, is_compressed))
        conn.commit()
        conn.close()
    
    def increment_download(self, filename):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE uploads SET download_count = download_count + 1 WHERE filename = ?', (filename,))
        conn.commit()
        conn.close()
    
    def get_stats(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*), SUM(file_size), SUM(compressed_size) FROM uploads')
        total_files, total_size, total_compressed = cursor.fetchone()
        
        today = datetime.now().date()
        cursor.execute('SELECT COUNT(*) FROM uploads WHERE DATE(upload_time) = ?', (today,))
        today_uploads = cursor.fetchone()[0]
        
        cursor.execute('SELECT file_type, COUNT(*) FROM uploads GROUP BY file_type ORDER BY COUNT(*) DESC LIMIT 5')
        popular_types = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_files': total_files or 0,
            'total_size': total_size or 0,
            'total_compressed': total_compressed or 0,
            'today_uploads': today_uploads or 0,
            'popular_types': popular_types,
            'compression_ratio': round((1 - (total_compressed or 1) / (total_size or 1)) * 100, 1) if total_size else 0
        }

analytics = AnalyticsDB()

def generate_token():
    return secrets.token_urlsafe(16)

def should_compress_file(filename, data_size):
    compressed_formats = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3', '.zip', '.rar', '.7z', '.gz', '.bz2'}
    ext = os.path.splitext(filename)[1].lower()
    
    if ext in compressed_formats:
        return False
    
    if data_size < 1024:
        return False
    
    if data_size > 100 * 1024 * 1024:
        return False
    
    return True

def compress_file_data(data, filename):
    if not should_compress_file(filename, len(data)):
        return data, len(data), False
    
    try:
        compressed = gzip.compress(data, compresslevel=6)
        if len(compressed) < len(data) * 0.9:
            return compressed, len(compressed), True
        else:
            return data, len(data), False
    except Exception as e:
        print(f"⚠️ Compression failed for {filename}: {e}")
        return data, len(data), False

def decompress_file_data(data, filename, was_compressed):
    if not was_compressed:
        return data
    
    try:
        return gzip.decompress(data)
    except Exception as e:
        print(f"⚠️ Decompression failed for {filename}: {e}")
        return data

def get_file_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f} {size_names[i]}"

# File cleanup thread
def cleanup_old_files():
    while True:
        try:
            now = time.time()
            for filename in os.listdir(UPLOAD_FOLDER):
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.isfile(filepath) and not filename.endswith('.token') and not filename.endswith('.meta'):
                    file_age = now - os.path.getctime(filepath)
                    if file_age > 86400:  # 24 hours
                        os.remove(filepath)
                        for ext in ['.token', '.meta']:
                            associated_file = f"{filepath}{ext}"
                            if os.path.exists(associated_file):
                                os.remove(associated_file)
                        print(f"🗑️ Auto-deleted (24h): {filename}")
        except Exception as e:
            print(f"⚠️ Cleaner error: {e}")
        time.sleep(3600)  # Check every hour

cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

@app.route('/')
def index():
    return render_template_string(open('index.html').read())

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
        
        # Generate token early
        owner_token = generate_token()
        
        # Save file to temporary location first
        temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{filename}")
        file.save(temp_path)
        
        # Get original size
        original_size = os.path.getsize(temp_path)
        
        # Read file data
        with open(temp_path, 'rb') as f:
            file_data = f.read()
        
        # Compress if beneficial (only for smaller files)
        if original_size > 100 * 1024 * 1024:
            compressed_size = original_size
            was_compressed = False
            print(f"📁 Large file detected ({get_file_size(original_size)}), skipping compression")
        else:
            compressed_data, compressed_size, was_compressed = compress_file_data(file_data, filename)
            if was_compressed:
                file_data = compressed_data
        
        # Encrypt the data
        try:
            encrypted_data = fernet.encrypt(file_data)
        except Exception as e:
            print(f"❌ Encryption failed for {filename}: {e}")
            os.remove(temp_path)
            return jsonify({'error': 'Encryption failed'}), 500
        
        # Write encrypted data
        with open(filepath, 'wb') as f:
            f.write(encrypted_data)
        
        # Clean up temp file
        os.remove(temp_path)
        
        # Save metadata
        metadata = {
            'original_size': original_size,
            'compressed_size': compressed_size,
            'was_compressed': was_compressed,
            'upload_time': datetime.now().isoformat(),
            'filename': filename,
            'owner_token': owner_token
        }
        
        meta_path = f"{filepath}.meta"
        with open(meta_path, 'w') as f:
            json.dump(metadata, f)
        
        # Save owner token
        token_path = f"{filepath}.token"
        with open(token_path, 'w') as f:
            f.write(owner_token)
        
        # Log to analytics
        file_type = os.path.splitext(filename)[1].lower() or 'unknown'
        client_ip = request.remote_addr
        analytics.log_upload(filename, original_size, file_type, client_ip, compressed_size, was_compressed)
        
        print(f"✅ File uploaded: {filename} ({get_file_size(filepath)})")
        
        return jsonify({
            'status': 'success',
            'filename': filename,
            'owner_token': owner_token,
            'original_size': original_size,
            'compressed_size': compressed_size,
            'was_compressed': was_compressed
        }), 200, {'X-Owner-Token': owner_token}
        
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/files')
def list_files():
    try:
        files = []
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(filepath) and not filename.endswith('.token') and not filename.endswith('.meta'):
                meta_path = f"{filepath}.meta"
                metadata = {}
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, 'r') as f:
                            metadata = json.load(f)
                    except:
                        pass
                
                files.append({
                    'name': filename,
                    'size': os.path.getsize(filepath),
                    'original_size': metadata.get('original_size', os.path.getsize(filepath)),
                    'was_compressed': metadata.get('was_compressed', False)
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
        
        # Get metadata
        meta_path = f"{filepath}.meta"
        metadata = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r') as f:
                    metadata = json.load(f)
            except:
                pass
        
        file_size = os.path.getsize(filepath)
        
        # For large files, stream directly
        if file_size > 100 * 1024 * 1024:
            print(f"📥 Streaming large file: {filename} ({get_file_size(file_size)})")
            analytics.increment_download(filename)
            return send_file(filepath, as_attachment=True, download_name=filename)
        
        # For smaller files, process normally
        with open(filepath, 'rb') as f:
            encrypted_data = f.read()
        
        try:
            decrypted_data = fernet.decrypt(encrypted_data)
            was_compressed = metadata.get('was_compressed', False)
            final_data = decompress_file_data(decrypted_data, filename, was_compressed)
            
            analytics.increment_download(filename)
            
            # Create temporary file for download
            temp_path = os.path.join(UPLOAD_FOLDER, f"download_{filename}")
            with open(temp_path, 'wb') as f:
                f.write(final_data)
            
            print(f"📥 File downloaded: {filename}")
            
            return send_file(temp_path, as_attachment=True, download_name=filename)
            
        except Exception as e:
            print(f"❌ Decryption/decompression error for {filename}: {e}")
            # Fallback: send encrypted file
            analytics.increment_download(filename)
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
        
        # Check owner token
        owner_token = request.headers.get('X-Owner-Token')
        if not owner_token:
            return jsonify({'error': 'No owner token provided'}), 403
        
        token_path = f"{filepath}.token"
        if not os.path.exists(token_path):
            return jsonify({'error': 'Token file not found'}), 404
        
        with open(token_path, 'r') as f:
            saved_token = f.read()
        
        if owner_token != saved_token:
            return jsonify({'error': 'Invalid owner token'}), 403
        
        # Remove all associated files
        for ext in ['', '.token', '.meta']:
            associated_file = f"{filepath}{ext}"
            if os.path.exists(associated_file):
                os.remove(associated_file)
        
        print(f"🗑️ File manually deleted: {filename}")
        return jsonify({'status': 'success', 'message': 'File deleted successfully'})
        
    except Exception as e:
        print(f"❌ Delete error: {str(e)}")
        return jsonify({'error': 'Delete failed'}), 500

@app.route('/analytics')
def get_analytics():
    try:
        stats = analytics.get_stats()
        return jsonify(stats)
    except Exception as e:
        print(f"❌ Analytics error: {str(e)}")
        return jsonify({'error': 'Analytics failed'}), 500

@app.route('/health')
def health_check():
    try:
        uploads_ok = os.path.exists(UPLOAD_FOLDER)
        
        try:
            analytics.get_stats()
            db_ok = True
        except:
            db_ok = False
        
        try:
            test_data = b"test"
            encrypted = fernet.encrypt(test_data)
            decrypted = fernet.decrypt(encrypted)
            encryption_ok = decrypted == test_data
        except:
            encryption_ok = False
        
        health_status = {
            'status': 'healthy' if uploads_ok and db_ok and encryption_ok else 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'version': '3.1.0',
            'service': 'B-Transfer Pro by Balsim Productions',
            'checks': {
                'uploads_directory': uploads_ok,
                'database': db_ok,
                'encryption': encryption_ok
            }
        }
        
        return jsonify(health_status), 200 if health_status['status'] == 'healthy' else 503
        
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return jsonify({'error': 'Health check failed'}), 500

if __name__ == '__main__':
    import socket
    
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
    
    print("🚀 B-Transfer Pro Server Starting (Flask Version)...")
    print("=" * 60)
    print(f"📱 Access from your phone: http://{local_ip}:{port}")
    print(f"💻 Access from this computer: http://localhost:{port}")
    print("=" * 60)
    print("📁 Files encrypted and saved in 'uploads' folder")
    print("🔄 Server supports up to 5GB file transfers")
    print("🔐 Advanced security with owner authentication")
    print("⚡ Smart compression for optimal performance")
    print("🏢 Powered by Balsim Productions")
    print("=" * 60)
    print("Press Ctrl+C to stop the server")
    print("")
    
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False) 