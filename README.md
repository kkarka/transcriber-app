   git clone https://github.com/yourusername/transcriber-app.git
   cd transcriber-app
   ```

2. **Setup the Backend:**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Setup the Frontend:**
   ```bash
   cd ../frontend
   npm install
   ```

### Running the Application

1. **Start the Backend Server:**
   ```bash
   cd backend
   python main.py
   ```

2. **Start the Frontend Development Server:**
   ```bash
   cd frontend
   npm run dev
   