# Skylark Drone Operations Coordinator AI

## Local Run
1. pip install -r requirements.txt
2. Update config.json with Sheet IDs
3. Share sheets (Editor) with service account email from credentials.json
4. python app.py
5. http://localhost:5000

## Features
- Natural language queries (e.g., "pilots in Bangalore with Mapping")
- Real-time conflicts (double-book, skills, location, maintenance)
- 2-way sync: Update status via chat → writes to sheets
- Live status, tables, urgent reassign suggestions