# B-Transfer Pro - Secure File Sharing Solution

A professional, secure, and fast file transfer application with end-to-end encryption, smart compression, and modern UI.

## 🚀 Features

### Core Features
- **🔐 End-to-End Encryption**: All files are encrypted using Fernet (AES-128) before storage
- **🗜️ Smart Compression**: Automatic compression for text files and documents (saves up to 90% space)
- **⚡ Lightning Fast**: Optimized for local network transfers
- **📱 PWA Support**: Install as native app on mobile and desktop
- **🔄 Auto-Cleanup**: Files automatically deleted after 24 hours
- **📊 Analytics**: Real-time statistics and usage tracking

### Security Features
- **Persistent Encryption Keys**: Keys are saved and reused across server restarts
- **Owner Authentication**: Only file owners can delete their files
- **Secure Token System**: Unique tokens for each uploaded file
- **Input Sanitization**: Filenames are sanitized to prevent security issues

### UI/UX Features
- **Modern Design**: Clean, professional interface with gradient backgrounds
- **Responsive Layout**: Works perfectly on mobile, tablet, and desktop
- **Dark/Light Theme**: Toggle between themes
- **Drag & Drop**: Intuitive file upload interface
- **Progress Tracking**: Real-time upload progress with percentage
- **File Previews**: Visual file type indicators
- **Status Notifications**: Clear feedback for all operations

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.7 or higher
- pip (Python package manager)

### Quick Start

1. **Clone or download the project**
   ```bash
   cd file-transfer-project
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server**
   ```bash
   python3 server.py
   ```

4. **Access the application**
   - **Local**: http://localhost:8081
   - **Network**: http://[YOUR_IP]:8081

### Advanced Setup

#### Custom Port
Set a custom port using environment variable:
```bash
PORT=9000 python3 server.py
```

#### Production Deployment
For production use, consider:
- Using a reverse proxy (nginx)
- Setting up SSL/TLS certificates
- Running as a system service
- Implementing rate limiting

## 📁 Project Structure

```
file-transfer-project/
├── server.py              # Main server application
├── index.html             # Frontend interface
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── manifest.json         # PWA manifest
├── sw.js                 # Service worker
├── uploads/              # File storage directory
├── analytics.db          # SQLite database for analytics
└── encryption.key        # Persistent encryption key
```

## 🔧 Configuration

### Server Configuration
The server can be configured by modifying these variables in `server.py`:

- **Port**: Default 8081, can be changed via `PORT` environment variable
- **File Retention**: Default 24 hours, modify in `FileCleaner` class
- **Max File Size**: Currently supports up to 5GB (limited by available memory)
- **Compression Threshold**: Files smaller than 1KB are not compressed

### Security Configuration
- **Encryption**: Uses Fernet (AES-128) with persistent keys
- **Token Length**: 16 bytes (configurable in `generate_token()`)
- **File Sanitization**: Removes special characters from filenames

## 🚀 Usage

### Uploading Files
1. **Drag & Drop**: Simply drag files onto the upload area
2. **Click to Select**: Click the upload area to open file browser
3. **Multiple Files**: Select multiple files at once
4. **Progress Tracking**: Watch real-time upload progress

### Downloading Files
1. **Direct Download**: Click the download button for any file
2. **Automatic Processing**: Files are automatically decrypted and decompressed
3. **Original Filenames**: Files maintain their original names

### Managing Files
1. **View All Files**: All uploaded files are listed with details
2. **Delete Your Files**: Only file owners can delete their uploads
3. **File Information**: See file size, compression status, and upload time

## 🔍 Troubleshooting

### Common Issues

#### File Upload Fails
- **Check file size**: Ensure file is under 5GB
- **Check permissions**: Ensure uploads directory is writable
- **Check disk space**: Ensure sufficient storage space
- **Check network**: Ensure stable network connection

#### File Download Fails
- **File expired**: Files are automatically deleted after 24 hours
- **File corrupted**: Check server logs for encryption/compression errors
- **Network issues**: Try refreshing the page

#### Server Won't Start
- **Port in use**: Change port or stop conflicting service
- **Permission denied**: Run with appropriate permissions
- **Python version**: Ensure Python 3.7+ is installed

#### Files Appear Corrupted
- **Encryption key**: Ensure encryption.key file is not corrupted
- **Server restart**: Restart server to regenerate key if needed
- **File format**: Some file types may not compress well

### Debug Mode
Enable debug logging by modifying the server:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Health Check
Access `/health` endpoint to check server status:
```bash
curl http://localhost:8081/health
```

## 📊 Analytics

The application tracks various metrics:
- **Total files uploaded**
- **Total storage used**
- **Compression ratios**
- **Daily upload counts**
- **Popular file types**
- **Download statistics**

Access analytics via the `/analytics` endpoint or view in the UI.

## 🔒 Security Considerations

### Data Protection
- **Encryption**: All files are encrypted at rest
- **Temporary Storage**: Files are automatically deleted
- **No Cloud Storage**: All data stays on your server
- **Local Network**: Designed for secure local transfers

### Access Control
- **Owner Tokens**: Each file has a unique owner token
- **Delete Protection**: Only owners can delete files
- **No Public Access**: Files are not publicly accessible

### Best Practices
- **Regular Updates**: Keep dependencies updated
- **Network Security**: Use HTTPS in production
- **Access Logs**: Monitor server logs for suspicious activity
- **Backup Keys**: Backup encryption keys securely

## 🚀 Performance Optimization

### Server Optimization
- **Threading**: Multi-threaded server for concurrent requests
- **Chunked Transfers**: Large files transferred in chunks
- **Smart Compression**: Only compress when beneficial
- **Memory Management**: Efficient memory usage for large files

### Client Optimization
- **PWA Caching**: Service worker for offline functionality
- **Lazy Loading**: UI elements loaded as needed
- **Efficient Updates**: Minimal DOM updates
- **Responsive Design**: Optimized for all screen sizes

## 🔄 Updates & Maintenance

### Regular Maintenance
- **Cleanup**: Old files are automatically removed
- **Database**: SQLite database is self-maintaining
- **Logs**: Server logs should be rotated regularly

### Updating
1. **Backup**: Backup your encryption keys and database
2. **Update Code**: Replace server.py and index.html
3. **Restart**: Restart the server
4. **Test**: Verify functionality

## 📱 Mobile Support

### PWA Features
- **Installable**: Add to home screen on mobile devices
- **Offline Support**: Basic functionality works offline
- **Native Feel**: Looks and feels like a native app

### Mobile Optimization
- **Touch Friendly**: Large touch targets
- **Responsive**: Adapts to all screen sizes
- **Fast Loading**: Optimized for mobile networks

## 🤝 Contributing

### Development Setup
1. **Fork the repository**
2. **Create feature branch**
3. **Make changes**
4. **Test thoroughly**
5. **Submit pull request**

### Code Standards
- **Python**: Follow PEP 8 guidelines
- **JavaScript**: Use modern ES6+ features
- **HTML/CSS**: Follow semantic HTML and modern CSS
- **Documentation**: Update README for new features

## 📄 License

This project is developed by Balsim Productions.

## 🆘 Support

### Getting Help
- **Check this README**: Most issues are covered here
- **Server Logs**: Check console output for errors
- **Health Check**: Use `/health` endpoint for diagnostics
- **Community**: Check for similar issues online

### Reporting Issues
When reporting issues, include:
- **Error messages**: Full error text
- **Steps to reproduce**: Detailed steps
- **Environment**: OS, Python version, browser
- **File types**: What types of files cause issues

---

**B-Transfer Pro** - Professional file sharing made simple and secure.

*Developed with ❤️ by Balsim Productions* 