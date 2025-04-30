import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Agent, ChatMessage } from "@/lib/types";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { Bot, User, Info, Send, Book, FileIcon } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

interface ChatInterfaceProps {
  agent: Agent;
  selectedDocumentId?: string | null;
}

export default function ChatInterface({ agent, selectedDocumentId }: ChatInterfaceProps) {
  const [message, setMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Fetch chat messages for the selected agent
  const { 
    data: messages = [] as ChatMessage[], 
    isLoading,
    isError
  } = useQuery<ChatMessage[]>({
    queryKey: ['/api/agents', agent.id, 'messages'],
    enabled: !!agent.id,
  });

  // Get information about the selected document if any
  const {
    data: selectedDocument,
    isLoading: documentLoading
  } = useQuery({
    queryKey: ['/api/documents', selectedDocumentId],
    queryFn: () => selectedDocumentId 
      ? apiRequest(`/api/documents/${selectedDocumentId}`) 
      : Promise.resolve(null),
    enabled: !!selectedDocumentId,
  });

  // Send message mutation - using RAG if a document is selected
  const sendMessageMutation = useMutation({
    mutationFn: async (content: string) => {
      // If a document is selected, use the RAG endpoint
      if (selectedDocumentId) {
        return apiRequest(`/api/agents/${agent.id}/rag`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: content
          })
        });
      }
      
      // Otherwise use the regular message endpoint
      return apiRequest(`/api/agents/${agent.id}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agentId: agent.id,
          role: 'user',
          content: content
        })
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['/api/agents', agent.id, 'messages'] });
      setMessage("");
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: `Failed to send message: ${error.message}`,
        variant: "destructive",
      });
    }
  });

  // Scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;
    sendMessageMutation.mutate(message);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${e.target.scrollHeight}px`;
  };

  return (
    <div className="flex-1 flex flex-col h-full">
      <div className="p-4 border-b dark:border-neutral-dark flex items-center justify-between bg-neutral-lightest dark:bg-neutral-dark rounded-t-lg shadow">
        <div className="flex items-center">
          <div className="h-10 w-10 rounded-full bg-primary flex items-center justify-center text-white mr-3">
            <Bot size={20} />
          </div>
          <div>
            <h2 className="font-medium">{agent.name}</h2>
            <div className="text-xs text-neutral flex items-center">
              <span className="flex items-center">
                <Bot className="mr-1" size={12} />
                {agent.model}
              </span>
            </div>
          </div>
        </div>
        <div>
          <button className="p-2 rounded-full hover:bg-neutral-light dark:hover:bg-neutral-dark transition-colors">
            <Info className="text-neutral-dark dark:text-neutral" size={18} />
          </button>
        </div>
      </div>
      
      {/* Document context indicator - if a document is selected */}
      {selectedDocumentId && (
        <div className="px-4 py-2 bg-neutral-lightest dark:bg-neutral border-b dark:border-neutral-dark flex items-center justify-between">
          <div className="flex items-center text-sm">
            <FileIcon size={16} className="mr-2 text-primary" />
            {documentLoading ? (
              <span>Loading document...</span>
            ) : selectedDocument ? (
              <span>
                Using document: <strong>{selectedDocument.filename}</strong>
                <Badge variant="outline" className="ml-2">{selectedDocument.type.toUpperCase()}</Badge>
              </span>
            ) : (
              <span>Document selected</span>
            )}
          </div>
        </div>
      )}
      
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-white dark:bg-neutral-darkest">
        {isLoading ? (
          Array(3).fill(0).map((_, index) => (
            <div key={`msg-skeleton-${index}`} className="flex items-start mb-4">
              <Skeleton className="h-8 w-8 rounded-full mr-2" />
              <div className="space-y-2">
                <Skeleton className="h-20 w-64 rounded-lg" />
              </div>
            </div>
          ))
        ) : isError ? (
          <div className="text-center p-4 text-status-error">
            Error loading messages. Please try refreshing.
          </div>
        ) : messages.length === 0 ? (
          <div className="flex items-start mb-4">
            <div className="h-8 w-8 rounded-full bg-primary flex-shrink-0 flex items-center justify-center text-white mr-2">
              <Bot size={16} />
            </div>
            <div className="chat-message-agent max-w-[80%] p-3 shadow-sm">
              <p className="text-sm">
                Hello! I'm your {agent.name}. How can I assist you today?
              </p>
            </div>
          </div>
        ) : (
          messages.map((msg: ChatMessage) => (
            <div key={msg.id} className={`flex items-start mb-4 ${msg.role === 'user' ? 'justify-end' : ''}`}>
              {msg.role === 'assistant' && (
                <div className="h-8 w-8 rounded-full bg-primary flex-shrink-0 flex items-center justify-center text-white mr-2">
                  <Bot size={16} />
                </div>
              )}
              
              <div className={msg.role === 'user' ? 'chat-message-user max-w-[80%] p-3 shadow-sm' : 'chat-message-agent max-w-[80%] p-3 shadow-sm'}>
                <p className="text-sm whitespace-pre-line">{msg.content}</p>
              </div>
              
              {msg.role === 'user' && (
                <div className="h-8 w-8 rounded-full bg-neutral-lightest dark:bg-neutral-dark flex-shrink-0 flex items-center justify-center ml-2 border dark:border-neutral-dark">
                  <User size={16} className="text-neutral-dark dark:text-neutral" />
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <div className="p-3 border-t dark:border-neutral-dark bg-neutral-lightest dark:bg-neutral-dark">
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <div className="flex-1 bg-white dark:bg-neutral-darkest rounded-lg shadow-sm border dark:border-neutral-dark overflow-hidden">
            <textarea 
              ref={textareaRef}
              className="w-full p-3 resize-none outline-none text-sm bg-transparent"
              placeholder="Type your message here..."
              rows={1}
              value={message}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              disabled={sendMessageMutation.isPending}
            />
          </div>
          <button 
            type="submit" 
            className="bg-primary hover:bg-primary-dark text-white p-3 rounded-lg shadow transition-colors flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={!message.trim() || sendMessageMutation.isPending}
          >
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
