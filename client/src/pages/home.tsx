import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import Header from "@/components/header";
import AgentSidebar from "@/components/agent-sidebar";
import ChatInterface from "@/components/chat-interface";
import CreateAgentModal from "@/components/create-agent-modal";
import { Agent } from "@/lib/types";
import { useToast } from "@/hooks/use-toast";

export default function Home() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const { toast } = useToast();

  // Fetch agents
  const { 
    data: agents = [], 
    isLoading, 
    isError 
  } = useQuery({
    queryKey: ['/api/agents'],
  });

  // Select first agent by default if none is selected
  useEffect(() => {
    if (agents.length > 0 && selectedAgentId === null) {
      setSelectedAgentId(agents[0].id);
    }
  }, [agents, selectedAgentId]);

  // Delete agent mutation
  const deleteAgentMutation = useMutation({
    mutationFn: async (agentId: number) => {
      await fetch(`/api/agents/${agentId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/agents'] });
      toast({
        title: "Agent deleted",
        description: "The agent has been successfully deleted.",
      });

      // If the deleted agent was selected, reset selection
      if (agents.length > 1) {
        const remainingAgents = agents.filter((a: Agent) => a.id !== selectedAgentId);
        setSelectedAgentId(remainingAgents[0].id);
      } else {
        setSelectedAgentId(null);
      }
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: `Failed to delete agent: ${error.message}`,
        variant: "destructive",
      });
    }
  });

  const handleDeleteAgent = (agentId: number) => {
    if (confirm("Are you sure you want to delete this agent? All chat history will be lost.")) {
      deleteAgentMutation.mutate(agentId);
    }
  };

  const selectedAgent = agents.find((agent: Agent) => agent.id === selectedAgentId);

  return (
    <div className="flex flex-col h-screen">
      <Header />
      
      <main className="flex-1 overflow-hidden">
        <div className="container mx-auto p-4 h-full flex flex-col md:flex-row gap-4">
          <AgentSidebar 
            agents={agents}
            selectedAgentId={selectedAgentId}
            onSelectAgent={setSelectedAgentId}
            onCreateAgent={() => setIsModalOpen(true)}
            onDeleteAgent={handleDeleteAgent}
            isLoading={isLoading}
            onSelectDocument={setSelectedDocumentId}
          />
          
          {selectedAgent ? (
            <ChatInterface 
              agent={selectedAgent} 
              selectedDocumentId={selectedDocumentId}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center bg-white dark:bg-neutral-darkest rounded-lg shadow">
              {isLoading ? (
                <p>Loading agents...</p>
              ) : isError ? (
                <p className="text-status-error">Error loading agents. Please try again.</p>
              ) : agents.length === 0 ? (
                <div className="text-center p-8">
                  <h2 className="text-xl font-medium mb-4">No Agents Available</h2>
                  <p className="mb-6">Create your first AI agent to get started.</p>
                  <button 
                    onClick={() => setIsModalOpen(true)}
                    className="bg-primary hover:bg-primary-dark text-white py-2 px-4 rounded-lg shadow transition-colors"
                  >
                    Create New Agent
                  </button>
                </div>
              ) : (
                <p>Select an agent from the sidebar to start chatting</p>
              )}
            </div>
          )}
        </div>
      </main>
      
      <CreateAgentModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
      />
    </div>
  );
}
