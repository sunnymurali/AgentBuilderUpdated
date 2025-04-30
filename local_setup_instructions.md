# Local Setup Instructions

## Running the Finance AI Assistant Locally

When running this application locally, there are a few important considerations to avoid import errors with the Python backend.

### Python Module Imports

The Python backend relies on importing modules from the `python_backend` directory. When running locally, you may encounter issues with imports in files like `faiss_rag.py` and `app_faiss.py`.

### Solutions for Local Setup

There are three ways to resolve this:

1. **Set the PYTHONPATH environment variable**:
   ```bash
   # On Linux/Mac
   export PYTHONPATH=$PYTHONPATH:/path/to/your/project

   # On Windows (Command Prompt)
   set PYTHONPATH=%PYTHONPATH%;C:\path\to\your\project

   # On Windows (PowerShell)
   $env:PYTHONPATH = "$env:PYTHONPATH;C:\path\to\your\project"
   ```

2. **Run from the project root**:
   ```bash
   # Instead of running from within the python_backend directory
   cd /path/to/your/project
   python -m python_backend.run_faiss
   ```

3. **Install the package in development mode**:
   ```bash
   cd /path/to/your/project
   pip install -e .
   ```
   This requires a `setup.py` file in your project root.

### Recommended Approach

The most reliable approach is using option 1 or 2. Set your PYTHONPATH to include the project root directory before running the application.

### Starting the Backend

Use the provided scripts to start the application:

```bash
# Start the full application (frontend + backend)
./start.sh

# Start only the Python backend (with FAISS)
./run_faiss_backend.sh
```

### Troubleshooting Import Errors

If you still encounter import errors:

1. Make sure `python_backend/__init__.py` exists
2. Check that you're using the correct Python version (3.9+ recommended)
3. Verify that all required packages are installed:
   ```bash
   pip install -r requirements.txt
   ```

4. Try directly importing the modules:
   ```python
   import sys
   sys.path.insert(0, '/path/to/your/project')
   import python_backend.faiss_storage
   ```