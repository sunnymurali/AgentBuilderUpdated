export interface Agent {
  id: number;
  name: string;
  systemPrompt: string;
  model: string;
  retrieverStrategy?: string; // Added for contextual compression retriever
  createdAt: string | Date;
  updatedAt: string | Date;
}

export interface ChatMessage {
  id: number;
  agentId: number;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string | Date;
}

export interface CreateAgentRequest {
  name: string;
  systemPrompt: string;
  model: string;
  retrieverStrategy?: string; // "default" or "contextual"
}

export interface CreateMessageRequest {
  agentId: number;
  role: 'user' | 'assistant';
  content: string;
}

export interface CreateMessageResponse {
  userMessage: ChatMessage;
  assistantMessage: ChatMessage;
}

export const defaultAgent: CreateAgentRequest = {
  name: "",
  systemPrompt: "",
  model: "gpt-4o",
  retrieverStrategy: "default"
};

export const availableModels = [
  { value: "gpt-4o", label: "GPT-4o (Default)" },
  { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
  { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" }
];

export const retrieverStrategies = [
  { 
    value: "default", 
    label: "Standard Retrieval (Default)",
    description: "Uses direct similarity search to find relevant documents"
  },
  { 
    value: "contextual", 
    label: "Contextual Compression",
    description: "First retrieves documents, then uses AI to extract only the most relevant content"
  }
];

export function getTimeAgo(date: string | Date): string {
  const now = new Date();
  const pastDate = new Date(date);
  const diffInSeconds = Math.floor((now.getTime() - pastDate.getTime()) / 1000);
  
  if (diffInSeconds < 60) {
    return 'Just now';
  }
  
  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) {
    return `${diffInMinutes}m ago`;
  }
  
  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) {
    return `${diffInHours}h ago`;
  }
  
  const diffInDays = Math.floor(diffInHours / 24);
  return `${diffInDays}d ago`;
}
