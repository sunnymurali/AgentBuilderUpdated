# Installation Guide for Local Development

## Python Dependencies

Install the following Python packages to run the application locally:

```bash
pip install fastapi uvicorn pydantic python-multipart PyPDF2 python-docx pandas openpyxl openai langchain langchain-community langgraph python-dotenv faiss-cpu chromadb flask-cors
```

The application uses FAISS (Facebook AI Similarity Search) as the primary vector store for improved performance. ChromaDB is available as an alternative implementation.

## Node.js Dependencies

The frontend dependencies are managed through package.json. Install them with:

```bash
npm install
```

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```
OPENAI_API_KEY=your_openai_api_key
```

## Running the Application

**NOTE:** The scripts below are designed to avoid conflicts. They will check if ports are already in use before starting servers.

### Option 1: All-in-one with the start script (Recommended)

The simplest way to run the application is:

```bash
./start.sh
```

This script will:
1. Check if the required packages are installed
2. Check if a Python server is already running on port 5001
3. Start both the Python backend and Node.js frontend

### Option 2: Running Python and Node.js separately

This option is useful for development when you want to see separate logs for frontend and backend.

1. Start the Python backend:
```bash
./start-python.sh
```

Or to use the FAISS implementation (recommended):
```bash
./run_faiss_backend.sh
```

2. In a separate terminal, start only the Node.js frontend:
```bash
./start-frontend.sh
```

**Important**: Make sure you're not running the all-in-one script at the same time, as it will cause port conflicts.

### Option 3: Skip Python Backend Check

If you already have a Python backend running or want to run only the frontend with an existing backend:

```bash
./start.sh --skip-python
```

### Troubleshooting

If you encounter errors such as "address already in use":

1. Check if you have other server processes running:
   ```bash
   ps aux | grep python
   ps aux | grep node
   ```

2. Kill any existing processes:
   ```bash
   kill -9 <process_id>
   ```

3. Or restart the Replit environment to clean up all processes

## Accessing the Application

The application should be accessible at http://localhost:5000
