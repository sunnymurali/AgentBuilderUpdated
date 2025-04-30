import os
import json
from typing import Dict, List, Any, Optional, Union, TypedDict
from datetime import datetime

import openai
from langgraph.graph import StateGraph, END
import chromadb

# Define state schema for graph
class GraphState(TypedDict):
    """State tracked across graph execution."""
    messages: List[Dict[str, str]]  # List of message objects with role and content
    context: List[Dict[str, Any]]   # List of document contexts with content and metadata
    query: str                      # Current user query
    response: str                   # Generated response
    agent_id: Optional[Union[int, str]]  # Agent ID for filtering documents
    validated: bool                 # Whether the response has been validated
    document_ids: List[str]         # IDs of retrieved documents

# Initialize clients with error handling
try:
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
        
        # Set embedding model for Azure
        embedding_model = "text-embedding-r-large"  # Azure embedding model
        azure_embedding_deployment = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "Embedding-Model")
    else:
        # Fallback to regular OpenAI
        print("Azure OpenAI credentials not complete, falling back to OpenAI")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            print("WARNING: OPENAI_API_KEY environment variable not set")
        openai_client = openai.OpenAI(api_key=openai_api_key)
        using_azure = False
        
        # Set embedding model for OpenAI
        embedding_model = "text-embedding-ada-002"  # OpenAI embedding model
    
    # Initialize ChromaDB client with embedding configuration
    # Create embedding function based on provider (Azure or OpenAI)
    if using_azure:
        # Configure for Azure OpenAI embeddings
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        embedding_function = OpenAIEmbeddingFunction(
            api_key=azure_key,
            api_base=azure_endpoint,
            api_type="azure",
            api_version=azure_api_version,
            model_name=embedding_model,
            deployment_id=azure_embedding_deployment
        )
    else:
        # Configure for regular OpenAI embeddings
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        embedding_function = OpenAIEmbeddingFunction(
            api_key=openai_api_key,
            model_name=embedding_model
        )
    
    # Initialize ChromaDB with the configured embedding function
    chroma_client = chromadb.Client()
    print("Successfully initialized ChromaDB client with embedding function")
except Exception as e:
    print(f"Error initializing clients: {str(e)}")
    # Create fallback clients to avoid crashes
    openai_client = None
    chroma_client = None
    using_azure = False

def get_documents_collection():
    """Get or create the documents collection with error handling."""
    if chroma_client is None:
        print("ChromaDB client not initialized")
        return None
    
    try:
        # Get the collection with embedding function
        return chroma_client.get_collection(
            name="documents",
            embedding_function=embedding_function
        )
    except Exception as e:
        try:
            print(f"Creating new ChromaDB collection: {str(e)}")
            return chroma_client.create_collection(
                name="documents", 
                metadata={"hnsw:space": "cosine"},
                embedding_function=embedding_function
            )
        except Exception as e2:
            print(f"Failed to create ChromaDB collection: {str(e2)}")
            return None

def retrieve_documents(state: GraphState) -> GraphState:
    """
    Retrieve relevant documents for the query.
    
    This function:
    1. Gets the query and agent_id from the state
    2. Queries ChromaDB for relevant documents
    3. Processes the results and adds them to the state
    """
    # Extract query and agent_id from state
    query = state.get("query", "")
    agent_id = state.get("agent_id")
    
    if not query:
        print("Empty query received")
        return {
            **state,
            "context": [],
            "document_ids": []
        }
    
    # Convert agent_id to string for ChromaDB if it's not None
    agent_id_str = str(agent_id) if agent_id is not None else None
    
    try:
        # Get documents collection
        documents_collection = get_documents_collection()
        if not documents_collection:
            print("Could not get documents collection")
            return {
                **state,
                "context": [],
                "document_ids": []
            }
        
        # Query the collection with robust error handling
        try:
            # Log query details for debugging
            print(f"Retrieving documents for query: '{query[:50]}...' with agent_id: {agent_id_str}")
            
            # Query relevant documents
            if agent_id_str:
                results = documents_collection.query(
                    query_texts=[query],
                    n_results=10,  # Get more results for better context
                    where={"agentId": agent_id_str}
                )
            else:
                results = documents_collection.query(
                    query_texts=[query],
                    n_results=10
                )
            
            # Process results
            docs = []
            doc_ids = []
            
            if results.get("documents") and len(results["documents"]) > 0:
                for i, doc in enumerate(results["documents"][0]):
                    if not doc:  # Skip empty documents
                        continue
                        
                    # Get metadata with error handling
                    metadata = {}
                    if (results.get("metadatas") and len(results["metadatas"]) > 0 
                            and i < len(results["metadatas"][0]) and results["metadatas"][0][i]):
                        metadata_raw = results["metadatas"][0][i]
                        if isinstance(metadata_raw, dict):
                            # Remove large fields to reduce payload size
                            metadata = {k: v for k, v in metadata_raw.items() if k != "text"}
                    
                    # Get document ID
                    doc_id = metadata.get("id", f"unknown_{i}")
                    if doc_id not in doc_ids:
                        doc_ids.append(doc_id)
                    
                    # Add to relevant docs
                    docs.append({
                        "content": doc,
                        "metadata": metadata
                    })
            
            print(f"Retrieved {len(docs)} relevant document chunks from {len(doc_ids)} unique documents")
            
            # Update state with retrieved documents
            return {
                **state,
                "context": docs,
                "document_ids": doc_ids
            }
        except Exception as e:
            print(f"Error in document retrieval: {str(e)}")
            return {
                **state,
                "context": [],
                "document_ids": []
            }
    except Exception as e:
        print(f"Unexpected error in retrieve_documents: {str(e)}")
        return {
            **state,
            "context": [],
            "document_ids": []
        }

def generate_draft_response(state: GraphState) -> GraphState:
    """
    Generate a response based on the query and retrieved documents.
    
    This function:
    1. Formats the context from retrieved documents
    2. Prepares the message history
    3. Creates a detailed system prompt
    4. Calls the OpenAI API to generate a response
    """
    # Extract data from state
    query = state.get("query", "")
    documents = state.get("context", [])
    messages = state.get("messages", [])
    document_ids = state.get("document_ids", [])
    
    # Format document context
    context_parts = []
    for i, doc in enumerate(documents):
        if isinstance(doc, dict) and "content" in doc:
            metadata = doc.get("metadata", {})
            filename = metadata.get("filename", "Unknown") if isinstance(metadata, dict) else "Unknown"
            doc_id = metadata.get("id", f"doc_{i}") if isinstance(metadata, dict) else f"doc_{i}"
            content = doc["content"]
            
            # Add metadata to context
            context_parts.append(
                f"Document: {filename} (ID: {doc_id})\n"
                f"Content: {content}\n"
            )
    
    # Join all context parts
    context_content = "\n\n".join(context_parts) if context_parts else "No relevant documents found."
    
    # Prepare chat history
    chat_history = []
    if messages and isinstance(messages, list):
        for msg in messages[-5:]:  # Use last 5 messages for context
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                role = msg["role"]
                if role not in ["system", "user", "assistant"]:
                    role = "user"  # Default to user if invalid role
                
                chat_history.append({
                    "role": role,
                    "content": str(msg["content"])
                })
    
    try:
        if not openai_client:
            print("OpenAI client not initialized")
            return {
                **state,
                "response": "Error: The AI service is not available. Please check the API key configuration.",
                "validated": False
            }
        
        # Create detailed system prompt with enhanced CSV data analysis capabilities
        system_message = (
            "You are a helpful assistant that answers questions based on the provided documents. "
            "Your task is to analyze the document content carefully and provide accurate responses "
            "that directly answer the user's query.\n\n"
            "Guidelines:\n"
            "1. Focus on extracting relevant facts from the documents\n"
            "2. If the documents contain the answer, cite specific information from them\n"
            "3. If the documents don't contain the answer, clearly state this fact\n"
            "4. Include document IDs when referencing specific information\n"
            "5. Be concise but thorough\n\n"
            "When analyzing CSV data:\n"
            "1. If the query involves statistics or trends, provide quantitative analysis\n"
            "2. Calculate relevant metrics like totals, averages, min/max values when appropriate\n"
            "3. For time-series data, identify trends and patterns\n"
            "4. Offer data-driven insights based on the numbers\n"
            "5. For categorical data, summarize by category\n"
            "6. Include specific numerical values in your response\n\n"
            f"Retrieved documents ({len(document_ids)} unique sources):\n{context_content}"
        )
        
        # Prepare API request
        api_messages = [{"role": "system", "content": system_message}]
        
        # Add chat history
        api_messages.extend(chat_history)
        
        # Add current query
        api_messages.append({"role": "user", "content": query})
        
        # Call OpenAI API - different parameters for Azure vs. OpenAI
        if using_azure:
            # For Azure OpenAI, use the deployment name instead of model
            response = openai_client.chat.completions.create(
                deployment_id=azure_deployment,  # Use deployment name for Azure
                messages=api_messages,
                temperature=0.3,  # Lower temperature for factual responses
                max_tokens=1500
            )
        else:
            # For regular OpenAI
            response = openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024
                messages=api_messages,
                temperature=0.3,  # Lower temperature for factual responses
                max_tokens=1500
            )
        
        # Extract the assistant's message
        response_content = response.choices[0].message.content
        
        # Update state with generated response
        return {
            **state,
            "response": response_content,
            "validated": False  # Mark as needing validation
        }
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return {
            **state,
            "response": "I'm sorry, I couldn't process your query at this time. Please try again later.",
            "validated": False
        }

def validate_response(state: GraphState) -> GraphState:
    """
    Validate the generated response for accuracy and quality.
    
    This function:
    1. Checks if the response properly uses the document context
    2. Ensures the response directly answers the user's query
    3. Improves the response if necessary
    """
    # Get data from state
    query = state.get("query", "")
    documents = state.get("context", [])
    response = state.get("response", "")
    document_ids = state.get("document_ids", [])
    
    # Skip validation if no documents were found
    if not documents or len(documents) == 0:
        print("No documents to validate against, skipping validation")
        return {
            **state,
            "validated": True
        }
    
    # Skip validation if response indicates no information was found
    if "do not contain" in response.lower() or "don't contain" in response.lower():
        # If there are actually documents, double-check this claim
        if len(documents) > 3:  # Only validate if we have a substantial number of docs
            try:
                # Extract document content for validation
                doc_content = "\n\n".join([
                    doc["content"] for doc in documents[:5] if isinstance(doc, dict) and "content" in doc
                ])
                
                # Create validation prompt
                validation_messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a validation assistant. Your job is to verify if the documents "
                            "contain information that answers the user's query. Be thorough and check "
                            "carefully before concluding that information is not present."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Query: {query}\n\n"
                            f"Response claims documents don't contain relevant information: {response}\n\n"
                            f"Document excerpts to verify:\n{doc_content}\n\n"
                            "Do the documents actually contain information that answers the query? "
                            "If yes, what specific information should be included in the response?"
                        )
                    }
                ]
                
                # Call OpenAI for validation
                if openai_client:
                    if using_azure:
                        validation_response = openai_client.chat.completions.create(
                            deployment_id=azure_deployment,
                            messages=validation_messages,
                            temperature=0.2,
                            max_tokens=500
                        )
                    else:
                        validation_response = openai_client.chat.completions.create(
                            model="gpt-4o",
                            messages=validation_messages,
                            temperature=0.2,
                            max_tokens=500
                        )
                    
                    validation_result = validation_response.choices[0].message.content
                    
                    # If validation finds information, regenerate the response
                    if "yes" in validation_result.lower() and "information" in validation_result.lower():
                        print("Validation found that documents DO contain relevant information")
                        
                        correction_messages = [
                            {
                                "role": "system",
                                "content": (
                                    "You are a helpful assistant answering questions based on document content. "
                                    "Use the specific information found in the documents to craft an accurate response."
                                )
                            },
                            {
                                "role": "user",
                                "content": f"Query: {query}"
                            },
                            {
                                "role": "assistant", 
                                "content": "I'll check the documents for information about this."
                            },
                            {
                                "role": "user",
                                "content": (
                                    "Your previous response claimed the documents don't contain this information, "
                                    "but further analysis shows they do. Here's what was found:\n\n"
                                    f"{validation_result}\n\n"
                                    "Please provide a new response that accurately uses this information."
                                )
                            }
                        ]
                        
                        if using_azure:
                            corrected_response = openai_client.chat.completions.create(
                                deployment_id=azure_deployment,
                                messages=correction_messages,
                                temperature=0.3,
                                max_tokens=1000
                            )
                        else:
                            corrected_response = openai_client.chat.completions.create(
                                model="gpt-4o",
                                messages=correction_messages,
                                temperature=0.3,
                                max_tokens=1000
                            )
                        
                        return {
                            **state,
                            "response": corrected_response.choices[0].message.content,
                            "validated": True
                        }
            except Exception as e:
                print(f"Error in validation process: {str(e)}")
    
    # For normal responses, check if they actually address the query
    try:
        if openai_client and len(query) > 10:  # Only validate substantial queries
            # Create validation prompt
            validation_check = [
                {
                    "role": "system",
                    "content": (
                        "You are a quality control assistant. Your job is to check if a response "
                        "properly addresses the user's query and uses the available document information effectively."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Query: {query}\n\n"
                        f"Response: {response}\n\n"
                        f"Number of documents available: {len(documents)}\n"
                        f"Document IDs: {', '.join(document_ids[:5])}...\n\n"
                        "Rate this response on a scale of 1-10 for how well it addresses the query. "
                        "If the rating is below 7, explain what specific improvements are needed."
                    )
                }
            ]
            
            # Get quality rating
            if using_azure:
                quality_check = openai_client.chat.completions.create(
                    deployment_id=azure_deployment,
                    messages=validation_check,
                    temperature=0.2,
                    max_tokens=300
                )
            else:
                quality_check = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=validation_check,
                    temperature=0.2,
                    max_tokens=300
                )
            
            quality_result = quality_check.choices[0].message.content
            
            # If low quality, improve the response
            if any(score in quality_result.lower() for score in ["1/10", "2/10", "3/10", "4/10", "5/10", "6/10"]):
                print(f"Response quality check failed: {quality_result}")
                
                # Sample a few document excerpts for context
                doc_samples = "\n\n".join([
                    f"Document {i+1}: {doc['content'][:200]}..." 
                    for i, doc in enumerate(documents[:3]) 
                    if isinstance(doc, dict) and "content" in doc
                ])
                
                improvement_messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant answering questions based on document content. "
                            "Your task is to improve the previous response to better address the user's query."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Query: {query}"
                    },
                    {
                        "role": "assistant", 
                        "content": response
                    },
                    {
                        "role": "user",
                        "content": (
                            "Your response needs improvement. Here's what our quality check found:\n\n"
                            f"{quality_result}\n\n"
                            f"Document samples to help improve the response:\n{doc_samples}\n\n"
                            "Please provide an improved response that better addresses the query."
                        )
                    }
                ]
                
                if using_azure:
                    improved_response = openai_client.chat.completions.create(
                        deployment_id=azure_deployment,
                        messages=improvement_messages,
                        temperature=0.3,
                        max_tokens=1000
                    )
                else:
                    improved_response = openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=improvement_messages,
                        temperature=0.3,
                        max_tokens=1000
                    )
                
                return {
                    **state,
                    "response": improved_response.choices[0].message.content,
                    "validated": True
                }
    except Exception as e:
        print(f"Error in quality validation: {str(e)}")
    
    # If we reach here, validation passed or couldn't be completed
    return {
        **state,
        "validated": True
    }

def create_rag_graph():
    """Create a three-step LangGraph RAG workflow with retrieval, generation, and validation"""
    try:
        # Create a new state graph
        workflow = StateGraph(GraphState)
        
        # Add nodes for each step
        workflow.add_node("retrieve", retrieve_documents)
        workflow.add_node("generate", generate_draft_response)
        workflow.add_node("validate", validate_response)
        
        # Define the edges between nodes
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", "validate")
        workflow.add_edge("validate", END)
        
        # Set the entry point
        workflow.set_entry_point("retrieve")
        
        # Compile the graph
        return workflow.compile()
    except Exception as e:
        print(f"Error creating RAG graph: {str(e)}")
        return None

# Create the graph
rag_graph = create_rag_graph()

def process_query(query: str, messages: List[Dict[str, Any]], agent_id: int = None) -> Dict[str, Any]:
    """
    Process a query through the RAG graph
    
    Args:
        query: The user's question
        messages: List of chat messages so far
        agent_id: Optional agent ID to filter documents
        
    Returns:
        Response from the RAG system
    """
    print(f"Processing RAG query: '{query[:50]}...' with agent_id: {agent_id}")
    
    # Format chat messages for consistency
    formatted_messages = []
    if messages and isinstance(messages, list):
        for msg in messages[-10:]:  # Use last 10 messages for context
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                # Ensure role is valid
                role = msg["role"]
                if role not in ["system", "user", "assistant"]:
                    role = "user"  # Default to user if invalid role
                
                formatted_messages.append({
                    "role": role,
                    "content": str(msg["content"])
                })
    
    # Prepare initial state
    initial_state = {
        "messages": formatted_messages,
        "context": [],
        "query": query,
        "response": "",
        "agent_id": agent_id,
        "validated": False,
        "document_ids": []
    }
    
    try:
        # Execute the LangGraph workflow
        if rag_graph:
            print("Running LangGraph RAG workflow")
            result = rag_graph.invoke(initial_state)
            
            # Ensure we have a valid response
            if isinstance(result, dict) and "response" in result and result["response"]:
                return {
                    "response": result["response"],
                    "context": result.get("context", [])
                }
        
        print("LangGraph execution failed or returned invalid result, falling back to direct processing")
        
        # Fallback to direct processing if LangGraph fails
        return fallback_rag_process(query, formatted_messages, agent_id)
    except Exception as e:
        print(f"Error in LangGraph RAG process: {str(e)}")
        return fallback_rag_process(query, formatted_messages, agent_id)

def fallback_rag_process(query: str, messages: List[Dict[str, Any]], agent_id: int = None) -> Dict[str, Any]:
    """Fallback RAG implementation using direct API calls"""
    print("Using fallback RAG implementation")
    
    try:
        # Step 1: Retrieve relevant documents from ChromaDB
        relevant_docs = []
        agent_id_str = str(agent_id) if agent_id is not None else None
        
        try:
            # Get documents collection
            documents_collection = get_documents_collection()
            if documents_collection:
                print(f"Querying documents for agent ID: {agent_id_str}")
                
                # Query relevant documents
                if agent_id_str:
                    results = documents_collection.query(
                        query_texts=[query],
                        n_results=10,  # Get more results for better context
                        where={"agentId": agent_id_str}
                    )
                else:
                    results = documents_collection.query(
                        query_texts=[query],
                        n_results=10
                    )
                
                # Process results
                doc_ids = []
                if results.get("documents") and len(results["documents"]) > 0:
                    for i, doc in enumerate(results["documents"][0]):
                        if doc:
                            # Get metadata
                            metadata = {}
                            if results.get("metadatas") and len(results["metadatas"]) > 0 and i < len(results["metadatas"][0]):
                                metadata_raw = results["metadatas"][0][i]
                                if isinstance(metadata_raw, dict):
                                    # Remove the text field to reduce size
                                    metadata = {k: v for k, v in metadata_raw.items() if k != "text"}
                                    
                                    # Track document IDs 
                                    if "id" in metadata and metadata["id"] not in doc_ids:
                                        doc_ids.append(metadata["id"])
                            
                            # Add to relevant docs
                            relevant_docs.append({
                                "content": doc,
                                "metadata": metadata
                            })
                
                print(f"Retrieved {len(relevant_docs)} relevant document chunks from {len(doc_ids)} unique documents")
            else:
                print("Could not access document collection")
        except Exception as e:
            print(f"Error retrieving documents: {str(e)}")
        
        # Step 2: Format context from documents
        context_parts = []
        for i, doc in enumerate(relevant_docs):
            if isinstance(doc, dict) and "content" in doc:
                metadata = doc.get("metadata", {})
                filename = metadata.get("filename", "Unknown") if isinstance(metadata, dict) else "Unknown"
                doc_id = metadata.get("id", f"doc_{i}") if isinstance(metadata, dict) else f"doc_{i}"
                content = doc["content"]
                
                # Add metadata to context
                context_parts.append(
                    f"Document: {filename} (ID: {doc_id})\n"
                    f"Content: {content}\n"
                )
        
        context_content = "\n\n".join(context_parts) if context_parts else "No relevant documents found."
            
        # Step 3: Call OpenAI API directly
        if openai_client:
            try:
                system_message = (
                    "You are a helpful assistant that answers questions based on the provided documents. "
                    "Your task is to analyze the document content carefully and provide accurate responses "
                    "that directly answer the user's query.\n\n"
                    "Guidelines:\n"
                    "1. Focus on extracting relevant facts from the documents\n"
                    "2. If the documents contain the answer, cite specific information from them\n"
                    "3. If the documents don't contain the answer, clearly state this fact\n"
                    "4. Include document IDs when referencing specific information\n"
                    "5. Be concise but thorough\n\n"
                    f"Retrieved documents ({len(relevant_docs)} chunks):\n{context_content}"
                )
                
                api_messages = [{"role": "system", "content": system_message}]
                
                # Add chat history
                api_messages.extend(messages)
                
                # Add current query
                api_messages.append({"role": "user", "content": query})
                
                # Make API call - handle Azure vs OpenAI differently
                if using_azure:
                    response = openai_client.chat.completions.create(
                        deployment_id=azure_deployment,
                        messages=api_messages,
                        temperature=0.3,  # Lower temperature for factual responses
                        max_tokens=1500
                    )
                else:
                    response = openai_client.chat.completions.create(
                        model="gpt-4o",  # the newest OpenAI model is "gpt-4o"
                        messages=api_messages,
                        temperature=0.3,  # Lower temperature for factual responses
                        max_tokens=1500
                    )
                
                response_content = response.choices[0].message.content
                
                # Return successful response
                return {
                    "response": response_content,
                    "context": relevant_docs
                }
                
            except Exception as e:
                print(f"Error calling OpenAI API: {str(e)}")
                return {
                    "response": "I'm sorry, I couldn't analyze the documents effectively for your query. Please try again later.",
                    "context": relevant_docs,
                    "error": str(e)
                }
        else:
            return {
                "response": "The AI service is currently unavailable. Please ensure the API key is properly configured.",
                "context": relevant_docs,
                "error": "OpenAI client not initialized"
            }
    
    except Exception as e:
        print(f"Critical error in fallback RAG processing: {str(e)}")
        return {
            "response": "I encountered a technical issue while trying to answer your question. Please try again later.",
            "context": [],
            "error": str(e)
        }