#!/usr/bin/env python3
import os
import json
import socket
import time
import threading
import uuid
import hashlib
import base64
import secrets
import gzip
import io
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import unquote, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import cgi
import shutil
import mimetypes
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    pass

# Persistent key generation for encryption purposes
def get_or_create_key():
    """Get existing key or create new one and save it"""
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

# Advanced Analytics Database
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
        
        # Total files and size
        cursor.execute('SELECT COUNT(*), SUM(file_size), SUM(compressed_size) FROM uploads')
        total_files, total_size, total_compressed = cursor.fetchone()
        
        # Today's uploads
        today = datetime.now().date()
        cursor.execute('SELECT COUNT(*) FROM uploads WHERE DATE(upload_time) = ?', (today,))
        today_uploads = cursor.fetchone()[0]
        
        # Popular file types
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

# A simple token generator for user session management
def generate_token():
    return secrets.token_urlsafe(16)

# Improved file compression with better error handling
def should_compress_file(filename, data_size):
    """Determine if file should be compressed based on type and size"""
    # Don't compress already compressed formats
    compressed_formats = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3', '.zip', '.rar', '.7z', '.gz', '.bz2'}
    ext = os.path.splitext(filename)[1].lower()
    
    # Don't compress if already compressed format
    if ext in compressed_formats:
        return False
    
    # Don't compress very small files (less than 1KB)
    if data_size < 1024:
        return False
    
    # Don't compress very large files (more than 100MB) to avoid memory issues
    if data_size > 100 * 1024 * 1024:
        return False
    
    return True

def compress_file_data(data, filename):
    """Compress file data if beneficial"""
    if not should_compress_file(filename, len(data)):
        return data, len(data), False
    
    try:
        compressed = gzip.compress(data, compresslevel=6)
        # Only use compression if it saves at least 10% of space
        if len(compressed) < len(data) * 0.9:
            return compressed, len(compressed), True
        else:
            return data, len(data), False
    except Exception as e:
        print(f"⚠️ Compression failed for {filename}: {e}")
        return data, len(data), False

def decompress_file_data(data, filename, was_compressed):
    """Decompress file data if it was compressed"""
    if not was_compressed:
        return data
    
    try:
        return gzip.decompress(data)
    except Exception as e:
        print(f"⚠️ Decompression failed for {filename}: {e}")
        return data  # Fallback to original if decompression fails

def add_file_expiry(filepath, hours=24):
    expiry_time = datetime.now() + timedelta(hours=hours)
    os.utime(filepath, (expiry_time.timestamp(), expiry_time.timestamp()))

class FileCleaner(threading.Thread):
    def run(self):
        while True:
            try:
                now = time.time()
                if os.path.exists('uploads'):
                    for filename in os.listdir('uploads'):
                        filepath = os.path.join('uploads', filename)
                        if os.path.isfile(filepath) and not filename.endswith('.token') and not filename.endswith('.meta'):
                            # Check if file is older than 24 hours
                            file_age = now - os.path.getctime(filepath)
                            if file_age > 86400:  # 24 hours in seconds
                                os.remove(filepath)
                                # Also remove associated files
                                for ext in ['.token', '.meta']:
                                    associated_file = f"{filepath}{ext}"
                                    if os.path.exists(associated_file):
                                        os.remove(associated_file)
                                print(f"🗑️ Auto-deleted (24h): {filename}")
            except Exception as e:
                print(f"⚠️ Cleaner error: {e}")
            time.sleep(3600)  # Check every hour

# Start cleaner thread
cleaner = FileCleaner()
cleaner.daemon = True
cleaner.start()

class FileTransferHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.upload_dir = "uploads"
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)
        super().__init__(*args, **kwargs)
    
    def setup(self):
        """Set up connection with timeout"""
        super().setup()
        self.request.settimeout(300)  # 5 minute timeout for large uploads
    
    def log_message(self, format, *args):
        """Override to reduce console spam"""
        return
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.serve_file('index.html', 'text/html')
        elif self.path == '/manifest.json':
            self.serve_file('manifest.json', 'application/json')
        elif self.path == '/sw.js':
            self.serve_file('sw.js', 'application/javascript')
        elif self.path == '/files':
            self.list_files()
        elif self.path == '/analytics':
            self.get_analytics()
        elif self.path == '/health':
            self.health_check()
        elif self.path.startswith('/download/'):
            filename = unquote(self.path[10:])  # Remove '/download/'
            self.download_file(filename)
        elif self.path.startswith('/preview/'):
            filename = unquote(self.path[9:])  # Remove '/preview/'
            self.preview_file(filename)
        else:
            self.send_error(404)
    
    def do_POST(self):
        if self.path == '/upload':
            self.upload_file()
        else:
            self.send_error(404)
    
    def do_DELETE(self):
        if self.path.startswith('/delete/'):
            filename = unquote(self.path[8:])  # Remove '/delete/'
            self.delete_file(filename)
        else:
            self.send_error(404)
    
    def serve_file(self, filename, content_type):
        try:
            with open(filename, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)
    
    def upload_file(self):
        try:
            # Parse the multipart form data
            content_type = self.headers.get('Content-Type')
            if not content_type or not content_type.startswith('multipart/form-data'):
                self.send_error(400, "Bad Request: Expected multipart/form-data")
                return
            
            # Get content length
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "Bad Request: No content")
                return
            
            # Check file size limit (5GB)
            if content_length > 5 * 1024 * 1024 * 1024:
                self.send_error(413, "File too large. Maximum size is 5GB")
                return
            
            # Parse form data using a simpler approach
            try:
                # Read the entire request body first
                request_body = self.rfile.read(content_length)
                
                # Find the boundary
                boundary = None
                for line in content_type.split(';'):
                    if 'boundary=' in line:
                        boundary = line.split('=')[1].strip()
                        break
                
                if not boundary:
                    self.send_error(400, "No boundary found in content type")
                    return
                
                # Parse the multipart data manually
                parts = request_body.split(b'--' + boundary.encode())
                
                # Find the file part
                file_data = None
                filename = None
                
                for part in parts:
                    if b'Content-Disposition: form-data; name="file"' in part:
                        # Extract filename
                        lines = part.split(b'\r\n')
                        for line in lines:
                            if b'filename=' in line:
                                filename = line.split(b'filename=')[1].strip(b'"').decode('utf-8')
                                break
                        
                        # Extract file data (everything after the double CRLF)
                        file_data = part.split(b'\r\n\r\n', 1)[1]
                        # Remove trailing CRLF
                        if file_data.endswith(b'\r\n'):
                            file_data = file_data[:-2]
                        break
                
                if not file_data or not filename:
                    self.send_error(400, "No file found in request")
                    return
                    
            except Exception as e:
                print(f"❌ Manual parsing error: {e}")
                self.send_error(400, f"Request parsing failed: {str(e)}")
                return
            
            # Sanitize filename
            filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
            
            filepath = os.path.join(self.upload_dir, filename)
            
            # Handle duplicate filenames
            counter = 1
            original_filepath = filepath
            while os.path.exists(filepath):
                name, ext = os.path.splitext(original_filepath)
                filepath = f"{name}_{counter}{ext}"
                counter += 1
            
            # Generate unique owner token
            owner_token = generate_token()
            
            # Write file data directly
            original_size = len(file_data)
            try:
                with open(filepath, 'wb') as f:
                    f.write(file_data)
            except Exception as e:
                print(f"❌ File write error: {e}")
                self.send_error(500, f"File write failed: {str(e)}")
                return
            
            # For large files (>100MB), skip compression
            if original_size > 100 * 1024 * 1024:
                compressed_size = original_size
                was_compressed = False
                print(f"📁 Large file detected ({self.get_file_size(original_size)}), skipping compression")
            else:
                # Compress if beneficial
                compressed_data, compressed_size, was_compressed = compress_file_data(file_data, filename)
                
                # If compression was beneficial, write compressed data
                if was_compressed:
                    with open(filepath, 'wb') as f:
                        f.write(compressed_data)
            
            # Encrypt the file
            try:
                with open(filepath, 'rb') as f:
                    file_content = f.read()
                
                encrypted_data = fernet.encrypt(file_content)
                
                with open(filepath, 'wb') as f:
                    f.write(encrypted_data)
                        
            except Exception as e:
                print(f"❌ Encryption failed for {filename}: {e}")
                if os.path.exists(filepath):
                    os.remove(filepath)
                self.send_error(500, "Encryption failed")
                return

            # Save metadata
            metadata = {
                'original_size': original_size,
                'compressed_size': compressed_size,
                'was_compressed': was_compressed,
                'upload_time': datetime.now().isoformat(),
                'filename': os.path.basename(filepath),
                'owner_token': owner_token
            }
            
            meta_path = f"{filepath}.meta"
            with open(meta_path, 'w') as f:
                json.dump(metadata, f)

            # Save owner token
            token_path = f"{filepath}.token"
            with open(token_path, 'w') as token_file:
                token_file.write(owner_token)
            
            # Log to analytics
            file_type = os.path.splitext(filename)[1].lower() or 'unknown'
            client_ip = self.client_address[0]
            analytics.log_upload(filename, original_size, file_type, client_ip, compressed_size, was_compressed)
            
            print(f"✅ File uploaded: {os.path.basename(filepath)} ({self.get_file_size(filepath)})")
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('X-Owner-Token', owner_token)
            self.end_headers()
            response = json.dumps({
                "status": "success", 
                "filename": os.path.basename(filepath), 
                "owner_token": owner_token,
                "original_size": original_size,
                "compressed_size": compressed_size,
                "was_compressed": was_compressed
            })
            self.wfile.write(response.encode())
            
        except Exception as e:
            print(f"❌ Upload error: {str(e)}")
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
            self.send_error(500, f"Internal Server Error: {str(e)}")
    
    def list_files(self):
        try:
            files = []
            for filename in os.listdir(self.upload_dir):
                filepath = os.path.join(self.upload_dir, filename)
                if os.path.isfile(filepath) and not filename.endswith('.token') and not filename.endswith('.meta'):
                    # Get metadata if available
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
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = json.dumps(files)
            self.wfile.write(response.encode())
            
        except Exception as e:
            print(f"❌ List files error: {str(e)}")
            self.send_error(500)
    
    def download_file(self, filename):
        try:
            filepath = os.path.join(self.upload_dir, filename)
            if not os.path.exists(filepath) or not os.path.isfile(filepath):
                self.send_error(404, "File not found")
                return
            
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
            
            # For large files, stream directly without loading into memory
            if file_size > 100 * 1024 * 1024:  # > 100MB
                print(f"📥 Streaming large file: {filename} ({self.get_file_size(file_size)})")
                
                # Send headers
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Content-Length', str(file_size))
                self.end_headers()
                
                # Stream file in chunks
                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                
                # Update download counter
                analytics.increment_download(filename)
                print(f"📥 Large file downloaded: {filename}")
                
            else:
                # For smaller files, process normally
                with open(filepath, 'rb') as f:
                    encrypted_data = f.read()
                
                try:
                    # Decrypt first
                    decrypted_data = fernet.decrypt(encrypted_data)
                    
                    # Then decompress if needed
                    was_compressed = metadata.get('was_compressed', False)
                    final_data = decompress_file_data(decrypted_data, filename, was_compressed)
                    
                    # Update download counter
                    analytics.increment_download(filename)
                    
                    # Send file
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                    self.send_header('Content-Length', str(len(final_data)))
                    self.end_headers()
                    
                    # Send data in chunks
                    offset = 0
                    chunk_size = 8192
                    while offset < len(final_data):
                        chunk = final_data[offset:offset + chunk_size]
                        self.wfile.write(chunk)
                        offset += chunk_size
                    
                    print(f"📥 File downloaded: {filename}")
                    
                except Exception as e:
                    print(f"❌ Decryption/decompression error for {filename}: {e}")
                    # Fallback: send as-is if processing fails
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                    self.send_header('Content-Length', str(len(encrypted_data)))
                    self.end_headers()
                    self.wfile.write(encrypted_data)
                    print(f"⚠️ Sent encrypted file as fallback: {filename}")
            
        except Exception as e:
            print(f"❌ Download error: {str(e)}")
            self.send_error(500)
    
    def delete_file(self, filename):
        try:
            filepath = os.path.join(self.upload_dir, filename)
            if not os.path.exists(filepath) or not os.path.isfile(filepath):
                self.send_error(404, "File not found")
                return
            
            # Get owner token from request header
            owner_token = self.headers.get('X-Owner-Token')
            if not owner_token:
                self.send_error(403, "Forbidden: No owner token provided")
                return
            
            # Check if token matches
            token_path = f"{filepath}.token"
            if not os.path.exists(token_path):
                self.send_error(404, "Token file not found")
                return
                
            with open(token_path, 'r') as token_file:
                saved_token = token_file.read()
            if owner_token != saved_token:
                self.send_error(403, "Forbidden: Invalid owner token")
                return

            # Remove all associated files
            for ext in ['', '.token', '.meta']:
                associated_file = f"{filepath}{ext}"
                if os.path.exists(associated_file):
                    os.remove(associated_file)
            
            print(f"🗑️ File manually deleted: {filename}")
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({"status": "success", "message": "File deleted successfully"})
            self.wfile.write(response.encode())
            
        except Exception as e:
            print(f"❌ Delete error: {str(e)}")
            self.send_error(500, f"Internal Server Error: {str(e)}")
    
    def get_analytics(self):
        """Return analytics data as JSON"""
        try:
            stats = analytics.get_stats()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = json.dumps(stats)
            self.wfile.write(response.encode())
            
        except Exception as e:
            print(f"❌ Analytics error: {str(e)}")
            self.send_error(500)
    
    def health_check(self):
        """Health check endpoint for monitoring"""
        try:
            # Check if uploads directory exists
            uploads_ok = os.path.exists('uploads')
            
            # Check database connection
            try:
                analytics.get_stats()
                db_ok = True
            except:
                db_ok = False
            
            # Check encryption
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
                'version': '3.0.0',
                'service': 'B-Transfer Pro by Balsim Productions',
                'checks': {
                    'uploads_directory': uploads_ok,
                    'database': db_ok,
                    'encryption': encryption_ok
                }
            }
            
            self.send_response(200 if health_status['status'] == 'healthy' else 503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = json.dumps(health_status, indent=2)
            self.wfile.write(response.encode())
            
        except Exception as e:
            print(f"❌ Health check error: {str(e)}")
            self.send_error(500)
    
    def get_file_size(self, filepath):
        size_bytes = os.path.getsize(filepath)
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {size_names[i]}"

def get_local_ip():
    """Get the local IP address"""
    try:
        # Connect to a remote address (doesn't actually connect)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def main():
    port = int(os.environ.get('PORT', 8081))  # Use Heroku's port or default to 8081
    local_ip = get_local_ip()
    
    print("🚀 B-Transfer Pro Server Starting...")
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
    
    try:
        server = ThreadedHTTPServer(('0.0.0.0', port), FileTransferHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 B-Transfer Pro server stopped. Thanks for using B-Transfer by Balsim Productions!")
        server.shutdown()

if __name__ == '__main__':
    main() 