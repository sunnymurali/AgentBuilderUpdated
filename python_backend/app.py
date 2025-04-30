import os
import io
import traceback
from typing import List, Dict, Optional, Any, Union
import json
import uuid
from fastapi import FastAPI, HTTPException, Response, status, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime

# Import document processing
from document_processor import process_document, chunk_text

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("dotenv not installed, skipping load_dotenv")

# Initialize FastAPI app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Set up OpenAI/Azure OpenAI client - wrapped in try/except for flexibility
try:
    import openai
    
    # Check for Azure OpenAI credentials first
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_key = os.getenv("AZURE_OPENAI_KEY")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    azure_api_version = "2024-08-01-preview"  # Latest API version
    
    if azure_endpoint and azure_key and azure_deployment:
        print("Using Azure OpenAI as primary provider")
        # Initialize Azure OpenAI client
        azure_client = openai.AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_key,
            api_version=azure_api_version
        )
        openai_client = azure_client
        using_azure = True
        
        # Define embedding model
        embedding_model = "text-embedding-r-large"  # Azure embedding model
    else:
        # Fallback to regular OpenAI
        print("Azure OpenAI credentials not complete, falling back to OpenAI")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            print("WARNING: OPENAI_API_KEY environment variable not set")
        openai_client = openai.OpenAI(api_key=openai_api_key)
        using_azure = False
        
        # Define embedding model for OpenAI
        embedding_model = "text-embedding-ada-002"  # OpenAI embedding model
except ImportError:
    print("OpenAI API not installed or key not available, some features will be limited")
    openai_client = None
    using_azure = False
    embedding_model = None

# Pydantic models for data validation
class AgentBase(BaseModel):
    name: str
    systemPrompt: str
    model: str

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    systemPrompt: Optional[str] = None
    model: Optional[str] = None

class AgentCreateResponse(AgentBase):
    id: int
    createdAt: str
    updatedAt: str

class MessageBase(BaseModel):
    agentId: int
    role: str
    content: str

class MessageResponse(MessageBase):
    id: int
    timestamp: str

class MessagePair(BaseModel):
    userMessage: MessageResponse
    assistantMessage: MessageResponse

class ErrorResponse(BaseModel):
    message: str
    error: Optional[str] = None

# Storage initialization with fallback mechanism
try:
    import chromadb
    from rag_graph import process_query, chroma_client
    
    # ChromaDB storage implementation
    class ChromaDBStorage:
        def __init__(self):
            # Initialize ChromaDB client
            try:
                # Try to reuse the existing client from rag_graph.py if it exists
                if chroma_client is not None:
                    self.client = chroma_client
                    print("Successfully initialized ChromaDB client")
                else:
                    # Create a new client with basic settings
                    self.client = chromadb.Client()
                    print("Created new ChromaDB client")
            except Exception as e:
                print(f"Warning: {str(e)}")
                # Fallback to basic client
                self.client = chromadb.Client()
            
            # Create collections if they don't exist
            try:
                self.agents_collection = self.client.get_collection("agents")
            except:
                self.agents_collection = self.client.create_collection("agents")
                
            try:
                self.messages_collection = self.client.get_collection("messages")
            except:
                self.messages_collection = self.client.create_collection("messages")
                
            # Initialize ID counters
            self.initialize_counters()
        
        def initialize_counters(self):
            # Get the maximum agent ID
            try:
                agents = self.get_agents()
                self.agent_id_counter = max([agent["id"] for agent in agents]) if agents else 0
            except:
                self.agent_id_counter = 0
                
            # Get the maximum message ID
            try:
                all_messages = self.messages_collection.get()
                message_metadatas = all_messages.get("metadatas", [])
                self.message_id_counter = max([msg.get("id", 0) for msg in message_metadatas]) if message_metadatas else 0
            except:
                self.message_id_counter = 0

        def get_agents(self) -> List[Dict]:
            agents_data = self.agents_collection.get()
            
            metadatas = agents_data.get("metadatas", [])
            agents = []
            
            # Convert metadatas to agent objects
            for metadata in metadatas:
                if metadata:  # Check if metadata is not None
                    agents.append(metadata)
                    
            return agents

        def get_agent(self, agent_id: int) -> Optional[Dict]:
            # Query for the specific agent by ID
            try:
                result = self.agents_collection.get(
                    where={"id": agent_id}
                )
                
                if result["metadatas"] and len(result["metadatas"]) > 0:
                    return result["metadatas"][0]
            except:
                pass
                
            return None

        def create_agent(self, agent_data: Dict) -> Dict:
            self.agent_id_counter += 1
            now = datetime.now().isoformat()
            
            new_agent = {
                "id": self.agent_id_counter,
                "name": agent_data["name"],
                "systemPrompt": agent_data["systemPrompt"],
                "model": agent_data["model"],
                "createdAt": now,
                "updatedAt": now
            }
            
            # Store agent in ChromaDB
            # We're using dummy embeddings since we don't need semantic search for agents
            self.agents_collection.add(
                ids=[f"agent_{self.agent_id_counter}"],
                metadatas=[new_agent],
                documents=[json.dumps(new_agent)],
                embeddings=[[0.0] * 5]  # Dummy embedding
            )
            
            return new_agent

        def update_agent(self, agent_id: int, updates: Dict) -> Optional[Dict]:
            agent = self.get_agent(agent_id)
            if not agent:
                return None
            
            if "name" in updates and updates["name"] is not None:
                agent["name"] = updates["name"]
            if "systemPrompt" in updates and updates["systemPrompt"] is not None:
                agent["systemPrompt"] = updates["systemPrompt"]
            if "model" in updates and updates["model"] is not None:
                agent["model"] = updates["model"]
            
            agent["updatedAt"] = datetime.now().isoformat()
            
            # Update in ChromaDB
            self.agents_collection.update(
                ids=[f"agent_{agent_id}"],
                metadatas=[agent],
                documents=[json.dumps(agent)],
                embeddings=[[0.0] * 5]  # Dummy embedding
            )
            
            return agent

        def delete_agent(self, agent_id: int) -> bool:
            agent = self.get_agent(agent_id)
            if not agent:
                return False
            
            # Delete agent from ChromaDB
            self.agents_collection.delete(
                ids=[f"agent_{agent_id}"]
            )
            
            # Delete associated messages
            messages = self.get_agent_messages(agent_id)
            for message in messages:
                self.messages_collection.delete(
                    ids=[f"message_{message['id']}"]
                )
                
            return True

        def get_agent_messages(self, agent_id: int) -> List[Dict]:
            try:
                # Query messages for the specific agent
                result = self.messages_collection.get(
                    where={"agentId": agent_id}
                )
                
                # Sort messages by ID to maintain order
                messages = result["metadatas"] if result["metadatas"] else []
                return sorted(messages, key=lambda x: x["id"])
            except:
                return []

        def create_message(self, message_data: Dict) -> Dict:
            self.message_id_counter += 1
            
            new_message = {
                "id": self.message_id_counter,
                "agentId": message_data["agentId"],
                "role": message_data["role"],
                "content": message_data["content"],
                "timestamp": datetime.now().isoformat()
            }
            
            # Store message in ChromaDB
            # We use the content for semantic search capability
            self.messages_collection.add(
                ids=[f"message_{self.message_id_counter}"],
                metadatas=[new_message],
                documents=[new_message["content"]],
                # We're not setting embeddings, allowing ChromaDB to compute them
            )
            
            return new_message
            
    # Use ChromaDB storage
    storage = ChromaDBStorage()
    using_fallback = False
    print("ChromaDB initialization successful")
    
except ImportError:
    # If ChromaDB is not available, use the fallback storage
    from fallback_storage import MemoryStorage
    storage = MemoryStorage()
    # Simplified query processing for fallback mode
    def process_query(query, messages, agent_id=None):
        if openai_client is None:
            return {"response": "OpenAI API not available. Please install the openai package and set OPENAI_API_KEY."}
        
        # Get agent details for system prompt
        agent = None
        for a in storage.get_agents():
            if a.get("id") == agent_id:
                agent = a
                break
        
        system_prompt = "You are a helpful assistant."
        if agent and "systemPrompt" in agent:
            system_prompt = agent["systemPrompt"]
        
        # Simple direct completion without RAG
        try:
            # Prepare messages
            formatted_messages = [
                {"role": "system", "content": system_prompt},
                *[{"role": m["role"], "content": m["content"]} for m in messages],
                {"role": "user", "content": query}
            ]
            
            # Use appropriate API call based on provider
            if using_azure:
                response = openai_client.chat.completions.create(
                    deployment_id=azure_deployment,
                    messages=formatted_messages,
                    temperature=0.7,
                    max_tokens=800
                )
            else:
                # Fallback to regular OpenAI
                response = openai_client.chat.completions.create(
                    model="gpt-4o",  # Use modern model
                    messages=formatted_messages,
                    temperature=0.7,
                    max_tokens=800
                )
                
            return {"response": response.choices[0].message.content}
        except Exception as e:
            print(f"Error in fallback query processing: {str(e)}")
            return {"response": f"Error generating response: {str(e)}"}
    
    using_fallback = True
    print("Using fallback storage (MemoryStorage) as ChromaDB is not available")

# Initialize document manager with storage-dependent implementation
if using_fallback:
    # Fallback document manager using MemoryStorage
    document_manager = storage  # MemoryStorage already has document management capabilities
else:
    # Document collection manager for ChromaDB
    class DocumentManager:
        def __init__(self):
            # Initialize ChromaDB client - reuse the same client instance
            try:
                # Try to reuse the existing client from storage if possible
                self.client = storage.client
                print("DocumentManager: Using shared ChromaDB client")
            except Exception as e:
                print(f"DocumentManager init error: {str(e)}")
                # Fallback to creating a new client with basic settings
                try:
                    if 'chroma_client' in globals() and chroma_client is not None:
                        self.client = chroma_client
                        print("DocumentManager: Using RAG client")
                    else:
                        # Create a basic client as a last resort
                        self.client = chromadb.Client()
                except:
                    # Very last resort
                    self.client = chromadb.Client()
            
            # Create document collection if it doesn't exist with proper embedding function
            try:
                # Import embedding function from rag_graph.py module if not available in this scope
                # This ensures we use the same embedding configuration
                try:
                    from rag_graph import embedding_function
                    print("Using embedding function from rag_graph module")
                except ImportError:
                    # Fallback to creating our own embedding function if rag_graph's isn't available
                    from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
                    
                    # Check for Azure OpenAI credentials
                    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
                    azure_key = os.getenv("AZURE_OPENAI_KEY")
                    azure_api_version = "2024-08-01-preview"
                    
                    if azure_endpoint and azure_key:
                        # Configure for Azure OpenAI
                        azure_embedding_deployment = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "Embedding-Model")
                        embedding_model = "text-embedding-r-large"  # Azure embedding model
                        
                        embedding_function = OpenAIEmbeddingFunction(
                            api_key=azure_key,
                            api_base=azure_endpoint,
                            api_type="azure",
                            api_version=azure_api_version,
                            model_name=embedding_model,
                            deployment_id=azure_embedding_deployment
                        )
                        print("Created Azure OpenAI embedding function")
                    else:
                        # Use OpenAI
                        openai_api_key = os.getenv("OPENAI_API_KEY")
                        embedding_model = "text-embedding-ada-002"  # OpenAI embedding model
                        
                        embedding_function = OpenAIEmbeddingFunction(
                            api_key=openai_api_key,
                            model_name=embedding_model
                        )
                        print("Created OpenAI embedding function")
                
                # Get or create collection with the embedding function
                self.document_collection = self.client.get_collection(
                    name="documents",
                    embedding_function=embedding_function
                )
                print("Successfully retrieved document collection")
            except Exception as e:
                print(f"Error getting document collection: {str(e)}")
                try:
                    # Create new collection with embedding function
                    self.document_collection = self.client.create_collection(
                        name="documents",
                        metadata={"hnsw:space": "cosine"},
                        embedding_function=embedding_function
                    )
                    print("Created new document collection with embedding function")
                except Exception as e2:
                    print(f"Error creating document collection: {str(e2)}")
                    # Last resort - create without embedding function
                    self.document_collection = self.client.create_collection("documents")
                    print("Created document collection without embedding function (fallback)")
            
            # Document ID counter
            self.doc_id_counter = self.initialize_counter()
        
        def initialize_counter(self) -> int:
            """Initialize the document ID counter based on existing documents"""
            try:
                # Get all documents and find the maximum ID
                all_docs = self.document_collection.get()
                metadatas = all_docs.get("metadatas", [])
                if not metadatas:
                    return 0
                    
                ids = [meta.get("id", 0) if meta else 0 for meta in metadatas]
                return max(ids) if ids else 0
            except:
                return 0
        
        def get_agent_documents(self, agent_id: int) -> List[Dict]:
            """Get all documents for a specific agent"""
            try:
                # Convert agent_id to string for ChromaDB
                agent_id_str = str(agent_id)
                
                # Query documents where agentId equals the string version of agent_id
                results = self.document_collection.get(
                    where={"agentId": agent_id_str}
                )
                
                # Dictionary to keep track of unique documents by ID
                unique_documents = {}
                
                if results.get("metadatas"):
                    for meta in results["metadatas"]:
                        if meta and "id" in meta:  # Check if metadata is not None and has ID
                            doc_id = meta["id"]
                            if doc_id not in unique_documents:
                                # Remove the full text to keep response size smaller
                                doc_info = meta.copy()
                                if "text" in doc_info:
                                    del doc_info["text"]
                                unique_documents[doc_id] = doc_info
                
                # Return the list of unique documents
                return list(unique_documents.values())
            except Exception as e:
                print(f"Error getting agent documents: {str(e)}")
                return []
        
        def get_document(self, document_id: str) -> Optional[Dict]:
            """Get a specific document by ID"""
            try:
                results = self.document_collection.get(
                    where={"id": document_id}
                )
                
                if results.get("metadatas") and len(results["metadatas"]) > 0:
                    return results["metadatas"][0]
                return None
            except:
                return None
        
        def add_document(self, document_info: Dict, text_chunks: List[str]) -> Dict:
            """Add a document and its chunked text to the collection"""
            try:
                # Generate a unique document ID
                self.doc_id_counter += 1
                document_id = f"doc_{self.doc_id_counter}"
                
                # Add document ID to the metadata
                document_info["id"] = document_id
                
                # Print debugging information for document_info
                print(f"Document info before sanitization:")
                for key, value in document_info.items():
                    if key != "text":  # Skip the full text to keep log manageable
                        print(f"  - {key}: {type(value).__name__} = {str(value)[:50]}")
                
                # Ensure all metadata values are strings to prevent type issues in ChromaDB
                # Create a sanitized copy of the metadata for ChromaDB
                sanitized_metadata = {}
                for key, value in document_info.items():
                    # Skip the full text when adding to metadata (it goes in documents field)
                    if key == "text":
                        continue
                        
                    if value is None:
                        sanitized_metadata[key] = ""
                    else:
                        try:
                            # Special case for agent_id_int which must be converted to string 
                            if key == "agent_id_int" and isinstance(value, int):
                                sanitized_metadata[key] = str(value)
                                print(f"  Converting agent_id_int from int to string: {value} -> '{sanitized_metadata[key]}'")
                            else:
                                sanitized_metadata[key] = str(value)
                        except Exception as conv_err:
                            print(f"Error converting {key}: {str(conv_err)}")
                            sanitized_metadata[key] = f"[Error: Could not convert value]"
                
                # Verify all values are strings before adding to ChromaDB
                print(f"Sanitized metadata:")
                for key, value in sanitized_metadata.items():
                    if not isinstance(value, str):
                        print(f"  WARNING: {key} is not a string but {type(value).__name__}")
                        sanitized_metadata[key] = str(value)
                    else:
                        print(f"  - {key}: string = {value[:50]}")
                
                # Store each chunk with the sanitized metadata
                for i, chunk in enumerate(text_chunks):
                    try:
                        # Ensure chunk is a string
                        chunk_text = str(chunk) if chunk is not None else ""
                        
                        # Verify all expected fields are present in the metadata
                        chunk_id = f"{document_id}_chunk_{i}"
                        print(f"Adding chunk {i+1}/{len(text_chunks)}: id={chunk_id}, text length={len(chunk_text)}")
                        
                        self.document_collection.add(
                            ids=[chunk_id],
                            metadatas=[sanitized_metadata],
                            documents=[chunk_text],
                        )
                    except Exception as chunk_err:
                        print(f"Error adding chunk {i}: {str(chunk_err)}")
                        # Continue with other chunks instead of failing completely
                
                # Return the original document info (with id added)
                return document_info
            except Exception as e:
                print(f"Error adding document: {str(e)}")
                print(traceback.format_exc())
                raise
        
        def delete_document(self, document_id: str) -> bool:
            """Delete a document and all its chunks"""
            try:
                # Find all chunks for this document
                matches = self.document_collection.get(
                    where={"id": document_id}
                )
                
                if not matches.get("ids"):
                    return False
                    
                # Delete all matching chunks
                for doc_id in matches["ids"]:
                    self.document_collection.delete(ids=[doc_id])
                    
                return True
            except:
                return False
    
    document_manager = DocumentManager()

# Create default agents if no agents exist yet
agents = storage.get_agents()
if not agents:
    storage.create_agent({
        "name": "General Assistant",
        "systemPrompt": "You are a helpful assistant that provides accurate and concise information.",
        "model": "gpt-4o"
    })

# API routes
@app.get("/api/agents", response_model=List[AgentCreateResponse])
async def get_agents():
    """Get all agents"""
    try:
        return storage.get_agents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents/{agent_id}", response_model=AgentCreateResponse)
async def get_agent(agent_id: int):
    """Get a specific agent by ID"""
    agent = storage.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.post("/api/agents", response_model=AgentCreateResponse)
async def create_agent(agent: AgentBase):
    """Create a new agent"""
    try:
        new_agent = storage.create_agent(agent.dict())
        return new_agent
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/agents/{agent_id}", response_model=AgentCreateResponse)
async def update_agent(agent_id: int, agent_update: AgentUpdate):
    """Update an existing agent"""
    updated_agent = storage.update_agent(agent_id, agent_update.dict(exclude_unset=True))
    if not updated_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return updated_agent

@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: int):
    """Delete an agent and all associated data"""
    success = storage.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent deleted successfully"}

@app.get("/api/agents/{agent_id}/messages", response_model=List[MessageResponse])
async def get_agent_messages(agent_id: int):
    """Get all messages for a specific agent"""
    return storage.get_agent_messages(agent_id)

@app.post("/api/agents/{agent_id}/messages", response_model=MessagePair)
async def create_message(agent_id: int, message: MessageBase):
    """Create a new message and generate a response"""
    try:
        # Store the user message
        user_message = storage.create_message(message.dict())
        
        # Get the agent's system prompt
        agent = storage.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Get conversation history for context
        messages = storage.get_agent_messages(agent_id)
        
        # Generate response using OpenAI
        try:
            response_content = "I'm sorry, I couldn't generate a response."
            
            if openai_client is not None:
                # Prepare the messages
                api_messages = [
                    {"role": "system", "content": agent["systemPrompt"]},
                    *[{"role": m["role"], "content": m["content"]} for m in messages]
                ]
                
                # If it's a simple chat without document context
                if using_azure:
                    # Use Azure OpenAI
                    completion = openai_client.chat.completions.create(
                        deployment_id=azure_deployment,
                        messages=api_messages,
                        temperature=0.7,
                        max_tokens=800
                    )
                else:
                    # Use regular OpenAI
                    completion = openai_client.chat.completions.create(
                        model=agent["model"],
                        messages=api_messages,
                        temperature=0.7,
                        max_tokens=800
                    )
                
                response_content = completion.choices[0].message.content
            else:
                response_content = "OpenAI API is not available. Please check your configuration."
        except Exception as e:
            response_content = f"Error generating response: {str(e)}"
        
        # Store the assistant's response
        assistant_message = storage.create_message({
            "agentId": agent_id,
            "role": "assistant",
            "content": response_content
        })
        
        return {"userMessage": user_message, "assistantMessage": assistant_message}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents/{agent_id}/documents")
async def get_agent_documents(agent_id: int):
    """Get all documents for a specific agent"""
    return document_manager.get_agent_documents(agent_id)

@app.post("/api/agents/{agent_id}/documents")
async def upload_document(
    agent_id: int, 
    file: UploadFile = File(...),
    description: str = Form(None)
):
    """Upload and process a document for a specific agent"""
    try:
        # Read the file content
        content = await file.read()
        
        # Process the document
        document_info = process_document(
            io.BytesIO(content),
            file.filename,
            agent_id,
            description
        )
        
        # Extract text chunks
        text = document_info.get("text", "")
        text_chunks = chunk_text(text)
        
        # Add the document to storage
        document = document_manager.add_document(document_info, text_chunks)
        
        # Remove the full text to keep response size smaller
        if "text" in document:
            del document["text"]
        
        return document
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents/{document_id}")
async def get_document(document_id: str):
    """Get a specific document by ID"""
    document = document_manager.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document"""
    success = document_manager.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}

@app.post("/api/agents/{agent_id}/rag")
async def generate_rag_response(agent_id: int, request: Request):
    """Generate a response using RAG"""
    try:
        # Parse the request body
        data = await request.json()
        query = data.get("query", "")
        
        # Get the agent
        agent = storage.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Get conversation history for context
        chat_history = storage.get_agent_messages(agent_id)
        
        # Process the query with RAG
        result = process_query(query, chat_history, agent_id)
        
        # Store the user message
        user_message = storage.create_message({
            "agentId": agent_id,
            "role": "user",
            "content": query
        })
        
        # Store the assistant's response
        response_content = result.get("response", "I'm sorry, I couldn't generate a response.")
        assistant_message = storage.create_message({
            "agentId": agent_id,
            "role": "assistant",
            "content": response_content
        })
        
        return {
            "userMessage": user_message,
            "assistantMessage": assistant_message,
            "documents": result.get("documents", [])
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Default route for testing
@app.get("/")
async def root():
    return {"message": "Python backend API is running", "storage_type": "fallback" if using_fallback else "chromadb"}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}