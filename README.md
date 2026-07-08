---
title: Whisper Meeting Transcriber
emoji: 💻
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# WhisperX Meeting Transcriber

[![Live Demo](https://img.shields.io/badge/Live-Demo-brightgreen)](http://localhost:8501) [![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/downloads/)

A powerful AI-powered meeting transcription tool built with Streamlit, FastAPI, and WhisperX. This application enables you to transcribe meetings from various sources including video URLs (YouTube, TikTok, Vimeo, Zoom, Google Drive) and uploaded video files.

## Features

### 🎯 AI-Powered Transcription
- **Automatic Speaker Diarization**: Accurately identifies and labels different speakers in the conversation
- **Advanced Voice Activity Detection (VAD)**: Efficiently detects speech segments to reduce processing time
- **Smart Speaker Labeling**: Auto-detects and suggests speaker names (John, Mary, etc.)
- **Timestamp Alignment**: Every word includes precise start and end timestamps

### 📹 Versatile Input Sources
- **Direct URL Input**: Paste links from:
  - 🚀 Zoom meetings
  - 📁 Google Drive
  - ▶️ YouTube (including shorts and live streams)
  - 🎵 TikTok
  - 📹 Vimeo
  - 🌐 Any direct media URL
- **File Upload**: Upload MP4, MOV, AVI, and other video formats (Windows only)

### ⚡ Blazing Fast Performance
- **Optimized for CPU**: Runs efficiently on standard computers without dedicated GPU
- **Automatic Model Selection**: Smartly chooses model size based on your hardware
- **Parallel Processing**: Converts multiple files concurrently

### 📊 Rich Output Formats
- **Transcript with Timestamps**: Professional-looking SRT-style transcript
- **Speaker Labels**: Automatically assigned speaker names
- **Word-Level Timestamps**: Detailed timing for every word
- **Confidence Scores**: Per-word confidence levels for accuracy assessment
- **Download Options**: Export to TXT, SRT, or JSON

### ⚙️ Advanced Configuration
- **Model Selection**: Choose between `base`, `small`, `medium`, and `large` models
- **Language Control**: Auto-detect or manually set language (Vietnamese, English, Chinese, etc.)
- **Beam Size**: Adjust transcription beam width for accuracy/speed trade-off
- **Thread Control**: Optimize for CPU cores (default 6)

## Prerequisites

- **Python 3.8+**
- **Windows 10/11** (for file upload feature)
- **Node.js** (for running the frontend locally)
- **Git**

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Whisper
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Node.js dependencies**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

## Usage

### Option 1: Run the Web App

**Start the server:**
```bash
python server.py
```

Access the application at:
- **Web App**: http://localhost:8000
- **Frontend Demo**: http://localhost:3000

### Option 2: Run with Docker

```bash
# Build the Docker image
docker-compose build

# Start the containers
docker-compose up
```

The web app will be available at http://localhost:8000.

### Option 3: Run on Hugging Face Spaces

1. **Log in to Hugging Face Hub**
   ```bash
   huggingface-cli login
   ```

2. **Run the script**
   ```bash
   python main.py --server=huggingface
   ```

## Configuration

You can configure the application using environment variables:

- **`HF_TOKEN`**: Hugging Face API token (required for model downloads)
- **`HF_MODEL`**: Default model to use (`base`, `small`, `medium`, `large`)
- **`HF_DEVICE`**: Device to run on (`cpu`, `cuda`, `mps`, `tpu`)
- **`COMPUTE_TYPE`**: Model computation type (`int8`, `float16`, `bfloat16`)
- **`MAX_SPEAKERS`**: Maximum number of speakers to detect
- **`FRONTEND_DIR`**: Path to frontend directory

## How It Works

1. **Input Processing**: Detects source type and downloads media using `yt-dlp` or processes uploaded file
2. **Preprocessing**: Converts media to 16kHz mono WAV format for Whisper
3. **WhisperX Transcription**: Uses Whisper model with advanced diarization and VAD
4. **Output Generation**: Creates timestamped transcripts with speaker labels and confidence scores
5. **Web Interface**: Streamlit UI for seamless user interaction

## Development

### Adding New Platforms

To add support for new platforms:

1. Edit `downloader.py` and add regex patterns to `URL_PATTERNS`:
   ```python
   URL_PATTERNS = {
       "new_platform": re.compile(r"(https?://)?(www\.)?newplatform\.com/"),
       # ... existing patterns
   }
   ```

2. Update `detect_source_type()` to handle the new platform

3. (Optional) Add platform icon to `frontend/index.html`

### Updating Models

To use different model sizes:

- **Frontend**: Change `DEFAULT_MODEL` in `frontend/app.js`
- **Backend**: Update `WhisperXTranscriber` class in `transcriber.py`

## Technology Stack

### Backend
- **Framework**: FastAPI
- **AI/ML**: WhisperX, PyTorch, Transformers,sentence-transformers
- **Utilities**: yt-dlp, ffmpeg, static-ffmpeg

### Frontend
- **Framework**: Streamlit
- **UI/UX**: Tailwind CSS, custom animations
- **Icons**: Lucide React

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Support

If you encounter any issues, please:
1. Check the **Troubleshooting** section in the wiki
2. Verify all dependencies are installed correctly
3. Review the console logs for error messages
4. Report the issue with detailed information

---
**Built with ❤️ for automatic transcription**
