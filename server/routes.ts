import type { Express, Request, Response } from "express";
import { createServer, type Server } from "http";
import axios from "axios";
import { log } from "./vite";
import { spawn } from "child_process";
import path from "path";
import FormData from "form-data";
import multer from "multer";
import fs from "fs";

// Check if Python backend is already running
async function isPythonBackendRunning(): Promise<boolean> {
  try {
    const response = await axios.get('http://localhost:5001/health', { timeout: 1000 });
    if (response.status === 200) {
      log("Python backend is already running", "python-backend");
      return true;
    }
  } catch (error) {
    // If there's an error, the backend is probably not running
    return false;
  }
  return false;
}

// Start the Python backend server
async function startPythonBackend() {
  // Check if the SKIP_PYTHON_BACKEND environment variable is set
  if (process.env.SKIP_PYTHON_BACKEND === 'true') {
    log("Skipping Python backend start (SKIP_PYTHON_BACKEND=true)", "python-backend");
    return;
  }
  
  // Check if the backend is already running
  const isRunning = await isPythonBackendRunning();
  if (isRunning) {
    log("Python backend is already running, skipping start", "python-backend");
    return;
  }

  const pythonProcess = spawn("python3", ["python_backend/run.py"], {
    cwd: process.cwd(),
    stdio: "pipe",
  });

  pythonProcess.stdout.on("data", (data) => {
    log(`Python backend: ${data}`, "python-backend");
  });

  pythonProcess.stderr.on("data", (data) => {
    log(`Python backend error: ${data}`, "python-backend");
  });

  pythonProcess.on("close", (code) => {
    log(`Python backend process exited with code ${code}`, "python-backend");
    // Restart the process if it crashes
    if (code !== 0) {
      log("Restarting Python backend...", "python-backend");
      setTimeout(startPythonBackend, 5000);
    }
  });

  log("Python backend started", "python-backend");
  
  // Give the Python backend some time to start up
  return new Promise<void>((resolve) => {
    setTimeout(() => {
      resolve();
    }, 3000);
  });
}

// Configure multer for file uploads
const upload = multer({ 
  dest: 'uploads/',
  limits: { fileSize: 10 * 1024 * 1024 } // 10MB limit
});

// Proxy middleware for API requests
const createProxyMiddleware = (pathPrefix: string) => {
  return async (req: Request, res: Response) => {
    const url = `http://localhost:5001${req.originalUrl}`;
    const method = req.method.toLowerCase();
    
    try {
      log(`Proxying ${method.toUpperCase()} ${req.originalUrl} to Python backend`, "proxy");
      
      let response;
      
      // Check if this is a file upload request (document upload endpoint)
      const isDocumentUpload = req.originalUrl.includes('/documents') && method === 'post';
      
      if (isDocumentUpload) {
        // Handle as multipart form data
        return upload.single('file')(req, res, async (err) => {
          if (err) {
            return res.status(400).json({ message: "File upload error", error: err.message });
          }
          
          try {
            // Create a form data object
            const formData = new FormData();
            
            // Get the uploaded file
            const file = (req as any).file;
            if (!file) {
              return res.status(400).json({ message: "No file uploaded" });
            }
            
            // Add the file to the form data
            formData.append('file', fs.createReadStream(file.path), {
              filename: file.originalname,
              contentType: file.mimetype,
            });
            
            // Add other form fields
            if (req.body.description) {
              formData.append('description', req.body.description);
            }
            
            // Send the request to the Python backend
            const uploadResponse = await axios.post(url, formData, {
              headers: {
                ...formData.getHeaders(),
              },
            });
            
            // Delete the temporary file
            fs.unlinkSync(file.path);
            
            // Return the response
            res.status(uploadResponse.status).json(uploadResponse.data);
          } catch (error: any) {
            // Clean up the file
            if ((req as any).file) {
              fs.unlinkSync((req as any).file.path);
            }
            
            log(`File upload proxy error: ${error.message}`, "proxy");
            if (error.response) {
              res.status(error.response.status).json(error.response.data);
            } else {
              res.status(500).json({ message: "Failed to connect to Python backend", error: error.message });
            }
          }
        });
      }
      
      // Handle regular requests
      if (method === "get") {
        response = await axios.get(url);
      } else if (method === "post") {
        response = await axios.post(url, req.body);
      } else if (method === "put") {
        response = await axios.put(url, req.body);
      } else if (method === "patch") {
        response = await axios.patch(url, req.body);
      } else if (method === "delete") {
        response = await axios.delete(url);
      } else {
        return res.status(405).json({ message: "Method not allowed" });
      }
      
      res.status(response.status).json(response.data);
    } catch (error: any) {
      log(`Proxy error: ${error.message}`, "proxy");
      if (error.response) {
        res.status(error.response.status).json(error.response.data);
      } else {
        res.status(500).json({ message: "Failed to connect to Python backend", error: error.message });
      }
    }
  };
};

export async function registerRoutes(app: Express): Promise<Server> {
  // Start Python backend and wait for it to initialize
  await startPythonBackend();
  
  // API routes - proxy to Python backend
  app.all("/api/agents", createProxyMiddleware("/api/agents"));
  app.all("/api/agents/:id", createProxyMiddleware("/api/agents/:id"));
  app.all("/api/agents/:id/messages", createProxyMiddleware("/api/agents/:id/messages"));
  // "/api/messages" endpoint is not used - messages should go to "/api/agents/:id/messages"
  
  // Document routes
  app.all("/api/agents/:id/documents", createProxyMiddleware("/api/agents/:id/documents"));
  app.all("/api/documents/:id", createProxyMiddleware("/api/documents/:id"));
  app.all("/api/agents/:id/rag", createProxyMiddleware("/api/agents/:id/rag"));

  const httpServer = createServer(app);
  return httpServer;
}
