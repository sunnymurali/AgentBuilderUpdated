"""
RAG implementation using FAISS vector store for the Finance AI Assistant.
"""

import os
import logging
from typing import Dict, List, Any, Optional, Union, TypedDict

import openai
from langgraph.graph import StateGraph, END

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    retriever_strategy: str         # Strategy to use for retrieval: "default" or "contextual"

# Initialize OpenAI client with error handling
try:
    # Check for Azure OpenAI credentials first
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_key = os.getenv("AZURE_OPENAI_KEY")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    azure_api_version = "2024-08-01-preview"  # Latest API version
    
    if azure_endpoint and azure_key and azure_deployment:
        logger.info("Using Azure OpenAI as primary provider")
        # Initialize Azure OpenAI client
        azure_client = openai.AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_key,
            api_version=azure_api_version
        )
        openai_client = azure_client
        using_azure = True
    else:
        # Fallback to regular OpenAI
        logger.info("Azure OpenAI credentials not complete, falling back to OpenAI")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            logger.warning("WARNING: OPENAI_API_KEY environment variable not set")
        openai_client = openai.OpenAI(api_key=openai_api_key)
        using_azure = False
except Exception as e:
    logger.error(f"Error initializing OpenAI client: {e}")
    openai_client = None
    using_azure = False

def retrieve_documents(state: GraphState) -> GraphState:
    """
    Retrieve relevant documents for the query using either standard FAISS or contextual compression.
    """
    # Import storage from the singleton module
    from python_backend.storage_singleton import storage
    
    query = state["query"]
    agent_id = state["agent_id"]
    retriever_strategy = state.get("retriever_strategy", "default")
    
    logger.info(f"Retrieving documents for query: {query}, agent_id: {agent_id}, strategy: {retriever_strategy}")
    
    # Use contextual compression if specified
    if retriever_strategy == "contextual":
        try:
            from python_backend.compression_retriever import retrieve_with_compression
            
            # Use compression retriever
            results = retrieve_with_compression(
                query=query, 
                faiss_index=storage.document_index,
                embedding_function=storage.embedding_function,
                agent_id=agent_id, 
                limit=5
            )
            
            logger.info(f"Retrieved documents using contextual compression: {len(results)}")
        except Exception as e:
            logger.error(f"Error using compression retriever: {e}")
            logger.info("Falling back to standard retrieval")
            # Fall back to standard retrieval
            results = storage.retrieve_relevant_documents(query, agent_id, limit=5)
    else:
        # Use standard retrieval
        results = storage.retrieve_relevant_documents(query, agent_id, limit=5)
    
    # Process results into context
    context = []
    document_ids = []
    
    for result in results:
        content = result.get("content", "")
        metadata = result.get("metadata", {})
        score = result.get("score", 0.0)
        
        # Skip empty results
        if not content.strip():
            continue
            
        # Add to context
        doc_id = metadata.get("id", "")
        if doc_id:
            document_ids.append(doc_id)
            
        context.append({
            "content": content,
            "metadata": metadata,
            "score": score
        })
        
    # Update state
    state["context"] = context
    state["document_ids"] = list(set(document_ids))  # Remove duplicates
    
    logger.info(f"Found {len(context)} relevant document chunks using {retriever_strategy} strategy")
    return state

def generate_draft_response(state: GraphState) -> GraphState:
    """
    Generate a response based on the query and retrieved documents.
    """
    if not openai_client:
        logger.error("OpenAI client not initialized")
        state["response"] = "Error: AI service not available"
        return state
    
    try:
        # Prepare context from retrieved documents
        context_text = ""
        reference_info = []
        
        if state["context"]:
            context_text = "Here are the most relevant document sections:\n\n"
            for i, ctx in enumerate(state["context"]):
                # Get source information
                source = ctx["metadata"].get("filename", "Unknown")
                
                # Check if we have page information
                page_info = ""
                page_num = ctx["metadata"].get("page")
                source_ref = ctx["metadata"].get("source_ref")
                
                if source_ref:
                    # Use pre-formatted source reference if available
                    reference = source_ref
                elif page_num:
                    # Format reference with page number
                    reference = f"{source}, page {page_num}"
                else:
                    # Just use the filename
                    reference = source
                
                # Store reference info for citation in response
                ref_id = i + 1
                reference_info.append({
                    "id": ref_id,
                    "reference": reference
                })
                
                # Add to context text
                content = ctx["content"]
                context_text += f"[Document {ref_id}: {reference}]\n{content}\n\n"
        
        # Get agent details for system prompt
        agent_system_prompt = "You are a helpful AI assistant."
        agent_model = "gpt-4o"
        
        if state["agent_id"] is not None:
            # Get agent from storage using singleton
            from python_backend.storage_singleton import storage
            
            agent = storage.get_agent(state["agent_id"])
            if agent:
                agent_system_prompt = agent.get("systemPrompt", agent_system_prompt)
                agent_model = agent.get("model", agent_model)
        
        # Create enhanced system prompt with context
        system_prompt = f"""{agent_system_prompt}

When answering, use the provided document sections as your primary knowledge source.
If the documents don't contain relevant information, use your general knowledge but
clearly indicate when you're doing so.

Always cite the document number and page number (when available) when using information from the documents.
For example: 
- "According to Document 2 (Annual Report.pdf, page 5), the company reported revenue of $10M in 2023."
- "Document 1 (Financial Analysis.csv) shows that Q1 sales increased by 15%."

Be specific about where information comes from. Document references include both the 
source file and page number (for PDFs). This helps users verify your answers.

If asked about specific data points from the documents, refer directly to the information
found in those documents rather than making up values.
"""

        if context_text:
            system_prompt += f"\n\n{context_text}"
        else:
            system_prompt += "\n\nNo specific document sections were found for this query. Please use your general knowledge to respond."
            
        # Prepare messages for the API call
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add previous messages for context
        for msg in state["messages"]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add the current query
        messages.append({"role": "user", "content": state["query"]})
        
        # Choose appropriate API based on environment
        if using_azure:
            # Azure OpenAI
            response = openai_client.chat.completions.create(
                model=azure_deployment,  # Azure uses deployment name instead of model
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
        else:
            # Regular OpenAI
            response = openai_client.chat.completions.create(
                model=agent_model,  # Use the agent's selected model or default
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
        
        # Extract response text
        assistant_response = response.choices[0].message.content
        
        # Update state with the response
        state["response"] = assistant_response
        state["validated"] = False
        
        return state
    
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        import traceback
        traceback.print_exc()
        state["response"] = f"Error generating response: {str(e)}"
        state["validated"] = False
        return state

def validate_response(state: GraphState) -> GraphState:
    """
    Validate the generated response for accuracy and quality.
    """
    # In a production system, this would have a more sophisticated validation
    # but for now we'll just mark it as validated
    state["validated"] = True
    return state

def create_rag_graph():
    """Create a three-step LangGraph RAG workflow with retrieval, generation, and validation"""
    # Define the graph
    workflow = StateGraph(GraphState)
    
    # Add nodes for each step
    workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("generate", generate_draft_response)
    workflow.add_node("validate", validate_response)
    
    # Connect the nodes in sequence
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "validate")
    workflow.add_edge("validate", END)
    
    # Set the entry point
    workflow.set_entry_point("retrieve")
    
    # Compile the graph
    return workflow.compile()

def process_query(query: str, messages: List[Dict[str, Any]], agent_id: int = None, retriever_strategy: str = "default") -> Dict[str, Any]:
    """
    Process a query through the RAG graph
    
    Args:
        query: The user's question
        messages: List of chat messages so far
        agent_id: Optional agent ID to filter documents
        retriever_strategy: Strategy to use for retrieval ("default" or "contextual")
        
    Returns:
        Response from the RAG system
    """
    logger.info(f"Processing query with FAISS RAG: {query} using {retriever_strategy} strategy")
    
    try:
        # Get agent to determine retriever strategy if not provided
        if retriever_strategy == "default" and agent_id is not None:
            # Get agent from storage using singleton
            from python_backend.storage_singleton import storage
            
            agent = storage.get_agent(agent_id)
            if agent and "retrieverStrategy" in agent:
                retriever_strategy = agent.get("retrieverStrategy")
                logger.info(f"Using agent's retriever strategy: {retriever_strategy}")
        
        # Create RAG graph
        graph = create_rag_graph()
        
        # Initial state
        initial_state = {
            "messages": messages,
            "context": [],
            "query": query,
            "response": "",
            "agent_id": agent_id,
            "validated": False,
            "document_ids": [],
            "retriever_strategy": retriever_strategy
        }
        
        # Execute the graph
        logger.info(f"Executing RAG graph with {retriever_strategy} retriever strategy")
        result_state = graph.invoke(initial_state)
        
        # Format the result
        response_text = result_state["response"]
        doc_ids = result_state["document_ids"]
        
        return {
            "response": response_text,
            "document_ids": doc_ids,
            "using_azure": using_azure,
            "retriever_strategy": retriever_strategy
        }
    
    except Exception as e:
        logger.error(f"Error in RAG process: {e}")
        import traceback
        traceback.print_exc()
        return {"response": f"Error generating response: {str(e)}"}